#!/usr/bin/env python3
"""Diagram pictures: a flow or sequence diagram -> SVG (clean or sketch theme), or a standalone HTML page.

Layer 1b of the diagrams:flow skill. The diagrams:walkthrough skill imports this module for its
pictures and adds voice, cues and the quiz on top.

usage:
  python3 diagram.py diagram.mmd [--look look.json] [--theme sketch|clean] [--title T] [-o out.html]
  python3 diagram.py scene.json [-o out.html]         # a scene with "diagram" (+ "look", "theme", "title")
Prints one JSON line on stdout: {"ok", "out", "warnings"}.

Input is Mermaid: `graph TD|LR` flows or `sequenceDiagram`. The optional look adds what Mermaid
cannot say: {"<node id>": {"at": [col, row], "color", "kind", "sub"}, "<subgraph id>": {"color"},
"<from>><to>": {"tone"}, "legend": [...]}.
Stdlib only; Node runs the bridges (fd.mjs parses Mermaid, avoid_route.mjs routes arrows, rough.mjs sketches).
"""
import argparse, base64, html, json, math, os, re, subprocess, sys

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))


def _node_modules():
    """The node_modules this skill uses: its own folder, else the nearest parent (a plugin keeps one at its root)."""
    d = SKILL_DIR
    while True:
        if os.path.isdir(os.path.join(d, 'node_modules')):
            return os.path.join(d, 'node_modules')
        if os.path.dirname(d) == d:
            return os.path.join(SKILL_DIR, 'node_modules')
        d = os.path.dirname(d)


NODE_MODULES = _node_modules()
NODE_KINDS = {'service', 'external', 'store', 'decision'}
# Colour carries meaning: who runs a box (node/group colour) and how a branch ends (edge tone).
COLORS = {'emerald', 'sky', 'amber', 'slate', 'rose', 'teal'}
TONES = {'good': 'emerald', 'warn': 'amber', 'bad': 'rose'}
EDGE_KINDS = {'sync', 'async', 'reply'}
THEMES = {'sketch', 'clean'}
NODE_KEYS = {'id', 'label', 'sub', 'at', 'kind', 'color'}
EDGE_KEYS = {'from', 'to', 'label', 'kind', 'tone'}
GROUP_KEYS = {'label', 'nodes', 'color', 'id'}
LOOK_NODE_KEYS = {'at', 'color', 'kind', 'sub', 'label'}


class DiagramError(Exception):
    pass


def _edge_key(a, b):
    return f'{a}>{b}'


def node_bridge(script, payload):
    """Run one of the Node bridges in this folder: JSON (or text) in, JSON out."""
    data = payload if isinstance(payload, str) else json.dumps(payload)
    r = subprocess.run(['node', os.path.join(SKILL_DIR, script)] + (['--json', '-'] if script == 'fd.mjs' else []),
                       input=data, capture_output=True, text=True, cwd=SKILL_DIR, timeout=60)
    if r.returncode != 0:
        raise DiagramError(f'{script} failed: ' + (r.stderr.strip().splitlines() or ['no output'])[-1])
    return json.loads(r.stdout)


# ---------------------------------------------------------------- Mermaid -> diagram

SHAPE_KIND = {'cylinder': 'store', 'diamond': 'decision'}


def _split_label(label):
    """Mermaid "Shop API<br/>order service" -> ("Shop API", "order service")."""
    parts = re.split(r'<br\s*/?>|\\n|\n', label or '')
    return parts[0].strip(), ' '.join(p.strip() for p in parts[1:]).strip()


def from_mermaid(src, look=None):
    """Mermaid text + look -> {"type": "flow"|"sequence", "nodes", "edges", "groups", "notes", "direction"}."""
    look = dict(look or {})
    g = node_bridge('fd.mjs', src)
    if g['type'] == 'sequence':
        nodes = [{'id': p['id'], 'label': p['label']} for p in g['participants']]
        edges = [{'from': m['from'], 'to': m['to'], 'label': m['label'], 'kind': m['kind'], 'key': f'm{m["n"]}', 'n': m['n']}
                 for m in g['messages']]
        groups, notes, direction = [], g['notes'], None
    else:
        nodes = []
        for n in g['nodes']:
            label, sub = _split_label(n['label'])
            node = {'id': n['id'], 'label': label, 'kind': SHAPE_KIND.get(n['shape'], 'service')}
            if sub:
                node['sub'] = sub
            nodes.append(node)
        edges = [{'from': e['from'], 'to': e['to'], 'label': e['label'], 'kind': 'async' if e['style'] == 'dotted' else 'sync'}
                 for e in g['edges'] if e['from'] != e['to']]
        groups = [{'id': s['id'], 'label': s['label'], 'nodes': s['nodes']} for s in g['groups']]
        notes, direction = [], g['direction']
    by_id = {n['id']: n for n in nodes}
    errs = []
    for key, val in look.items():
        if key == 'legend':
            continue
        if not isinstance(val, dict):
            errs.append(f'look "{key}": must be an object')
        elif key in by_id:
            for k in set(val) - LOOK_NODE_KEYS:
                errs.append(f'look "{key}": unknown key "{k}" (allowed: {", ".join(sorted(LOOK_NODE_KEYS))})')
            by_id[key].update({k: v for k, v in val.items() if k in LOOK_NODE_KEYS})
        elif any(gr['id'] == key for gr in groups):
            next(gr for gr in groups if gr['id'] == key).update({k: v for k, v in val.items() if k == 'color'})
        elif '>' in key and any(_edge_key(e['from'], e['to']) == key for e in edges):
            for e in edges:
                if _edge_key(e['from'], e['to']) == key:
                    e.update({k: v for k, v in val.items() if k == 'tone'})
        else:
            errs.append(f'look "{key}" matches no node, subgraph or arrow in the diagram')
    if errs:
        raise DiagramError('\n'.join(errs))
    if g['type'] == 'flow' and not any('at' in n for n in nodes):
        auto_at(nodes, edges, direction)
    return {'type': g['type'], 'nodes': nodes, 'edges': edges, 'groups': groups, 'notes': notes,
            'direction': direction, 'legend': look.get('legend', [])}


def auto_at(nodes, edges, direction):
    """Layered placement for flows without "at": rank = longest path from a source (back edges ignored),
    then order each rank by the mean position of its parents. TD/BT ranks are rows; LR/RL ranks are columns."""
    ids = [n['id'] for n in nodes]
    out = {i: [] for i in ids}
    for e in edges:
        out[e['from']].append(e['to'])
    state, back = {}, set()

    def dfs(u):                                   # find back edges so cycles do not loop the ranking
        state[u] = 1
        for v in out[u]:
            if state.get(v) == 1:
                back.add((u, v))
            elif v not in state:
                dfs(v)
        state[u] = 2
    for i in ids:
        if i not in state:
            dfs(i)
    rank = {i: 0 for i in ids}
    for _ in ids:                                 # Bellman-style relaxation on the acyclic part
        for e in edges:
            if (e['from'], e['to']) not in back and rank[e['to']] < rank[e['from']] + 1:
                rank[e['to']] = rank[e['from']] + 1
    layers = {}
    for i in ids:
        layers.setdefault(rank[i], []).append(i)
    pos = {}
    for r in sorted(layers):
        parents = lambda i: [pos[e['from']] for e in edges if e['to'] == i and e['from'] in pos]
        layers[r].sort(key=lambda i: (sum(parents(i)) / len(parents(i)) if parents(i) else ids.index(i) * 0.01))
        for k, i in enumerate(layers[r]):
            pos[i] = k
    for n in nodes:
        r, k = rank[n['id']], pos[n['id']]
        n['at'] = [k, r] if direction in ('TD', 'TB', 'BT') else [r, k]


def validate_diagram(d):
    """Shared checks for nodes, edges, groups and legend. Fills edge keys. -> list of error strings."""
    errs, ids = [], []
    for i, n in enumerate(d['nodes']):
        for k in set(n) - NODE_KEYS:
            errs.append(f'node {i}: unknown key "{k}"')
        if not n.get('id') or not n.get('label'):
            errs.append(f'node {i}: needs "id" and "label"')
            continue
        if n['id'] in ids:
            errs.append(f'node "{n["id"]}" is declared twice')
        ids.append(n['id'])
        if n.get('color') and n['color'] not in COLORS:
            errs.append(f'node "{n["id"]}": color must be one of {sorted(COLORS)}')
        if n.get('kind', 'service') not in NODE_KINDS:
            errs.append(f'node "{n["id"]}": kind must be one of {sorted(NODE_KINDS)}')
        if 'at' in n and not (isinstance(n['at'], list) and len(n['at']) == 2 and all(isinstance(v, int) and v >= 0 for v in n['at'])):
            errs.append(f'node "{n["id"]}": "at" must be [col, row] with non-negative integers')
    if d.get('type', 'flow') == 'flow':
        with_at = [n for n in d['nodes'] if 'at' in n]
        if with_at and len(with_at) != len(d['nodes']):
            errs.append('give "at" for every node or for none')
        cells = [tuple(n['at']) for n in with_at]
        for c in set(cells):
            if cells.count(c) > 1:
                errs.append(f'two nodes share the cell {list(c)}')
    idset, edges = set(ids), []
    for i, e in enumerate(d.get('edges', [])):
        if isinstance(e, list) and len(e) == 2:
            e = {'from': e[0], 'to': e[1]}
        if not isinstance(e, dict):
            errs.append(f'edge {i}: use ["a", "b"] or {{"from", "to", "label", "kind"}}')
            continue
        for k in set(e) - EDGE_KEYS - {'key', 'n'}:
            errs.append(f'edge {i}: unknown key "{k}"')
        for end in ('from', 'to'):
            if e.get(end) not in idset:
                errs.append(f'edge {i}: unknown node "{e.get(end)}" in "{end}"')
        if e.get('tone') and e['tone'] not in TONES:
            errs.append(f'edge {i}: tone must be one of {sorted(TONES)}')
        if e.get('kind', 'sync') not in EDGE_KINDS:
            errs.append(f'edge {i}: kind must be one of {sorted(EDGE_KINDS)}')
        e.setdefault('key', _edge_key(e.get('from'), e.get('to')))
        if any(x['key'] == e['key'] for x in edges):
            errs.append(f'edge {e["key"]} is declared twice')
        edges.append(e)
    groups = d.get('groups', [])
    for i, g in enumerate(groups):
        for k in set(g) - GROUP_KEYS:
            errs.append(f'group {i}: unknown key "{k}"')
        if g.get('color') and g['color'] not in COLORS:
            errs.append(f'group {i}: color must be one of {sorted(COLORS)}')
        if not g.get('label') or not g.get('nodes'):
            errs.append(f'group {i}: needs "label" and "nodes"')
        for n in g.get('nodes', []):
            if n not in idset:
                errs.append(f'group "{g.get("label")}": unknown node "{n}"')
    for i, g in enumerate(groups):
        for h in groups[i + 1:]:
            a, b = set(g.get('nodes', [])), set(h.get('nodes', []))
            if a & b and not (a <= b or b <= a):
                errs.append(f'groups "{g.get("label")}" and "{h.get("label")}" overlap; groups must be separate or one inside the other')
    for i, l in enumerate(d.get('legend', [])):
        if not (isinstance(l, dict) and l.get('color') in COLORS and isinstance(l.get('label'), str)):
            errs.append(f'legend {i}: use {{"color": one of {sorted(COLORS)}, "label": "..."}}')
    d['edges'] = edges
    return errs


# ---------------------------------------------------------------- layout

H, GX, GY, PADX, PADY, PADR = 64, 70, 76, 40, 44, 70


def text_w(s, size, bold=False):
    return len(s) * size * (0.6 if bold else 0.56)


def layout(nodes, cols, use_at, gx=GX):
    W = max(170, min(260, max(max(text_w(n['label'], 15, True), text_w(n.get('sub', ''), 12)) for n in nodes) + 28))
    cells = {}
    if use_at and all('at' in n for n in nodes):
        cells = {n['id']: tuple(n['at']) for n in nodes}
    else:
        for i, n in enumerate(nodes):
            r, c = divmod(i, cols)
            cells[n['id']] = (cols - 1 - c if r % 2 else c, r)
    ncols = max(c for c, _ in cells.values()) + 1
    nrows = max(r for _, r in cells.values()) + 1
    pos = {k: (PADX + c * (W + gx), PADY + r * (H + GY), W, H) for k, (c, r) in cells.items()}
    width = PADX + ncols * W + (ncols - 1) * gx + PADR
    height = PADY + nrows * H + (nrows - 1) * GY + 30
    return pos, cells, width, height


def bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def ports(e, cells):
    """Which side of each box an edge leaves from and arrives at."""
    (ac, ar), (bc, br) = cells[e['from']], cells[e['to']]
    if ar == br and abs(ac - bc) == 1:
        return ('right', 'left') if bc > ac else ('left', 'right')
    if ar == br:
        return ('top', 'top')
    if ac == bc and abs(ar - br) == 1:
        return ('bottom', 'top') if br > ar else ('top', 'bottom')
    if ac == bc:
        return ('right', 'right')
    return ('bottom', 'top') if br > ar else ('top', 'bottom')


def port_xy(rect, side, shift):
    x, y, w, h = rect
    return {'top': (x + w / 2 + shift, y), 'bottom': (x + w / 2 + shift, y + h),
            'left': (x, y + h / 2 + shift), 'right': (x + w, y + h / 2 + shift)}[side]


def route(e, pos, cells, reverse, lane, sa=0.0, sb=0.0):
    """Return (d, samples, (lx, ly), anchor). Every edge is one cubic so it can be sampled.
    `lane` spreads skip-edges that share a row or column; sa/sb spread edges that share a side of a box."""
    a, b = e['from'], e['to']
    (ac, ar), (bc, br) = cells[a], cells[b]
    ax, ay, aw, ah = pos[a]
    side_a, side_b = ports(e, cells)
    off = 7 if reverse else 0
    anchor = 'middle'
    if ar == br and abs(ac - bc) == 1:          # neighbours in a row
        o = off if bc > ac else -off
        p0, p3 = port_xy(pos[a], side_a, o + sa), port_xy(pos[b], side_b, o + sb)
        p1, p2 = p0, p3
        lx, ly = (p0[0] + p3[0]) / 2, (p0[1] + 16 if off and bc > ac else p0[1] - 9)
    elif ar == br:                               # skip edge in a row: arc over the top
        lift = 34 + 18 * lane
        spread = (lane % 4) * 9 - 13
        p0, p3 = port_xy(pos[a], 'top', off + spread + sa), port_xy(pos[b], 'top', -off + spread + sb)
        p1, p2 = (p0[0], ay - lift), (p3[0], p3[1] - lift)
        lx, ly = (p0[0] + p3[0]) / 2, ay - lift * 0.75 - 6
    elif ac == bc and abs(ar - br) == 1:         # neighbours in a column
        o = off if br > ar else -off
        p0, p3 = port_xy(pos[a], side_a, o + sa), port_xy(pos[b], side_b, o + sb)
        p1, p2 = p0, p3
        lx, ly, anchor = p0[0] + 8, (p0[1] + p3[1]) / 2 + 4, 'start'
        if off and br < ar:                      # reverse pair: the upward line sits left, label on the left
            lx, anchor = p0[0] - 8, 'end'
    elif ac == bc:                               # skip edge in a column: arc out to the right
        bulge = 34 + 30 * lane
        spread = (lane % 4) * 8 - 12
        p0, p3 = port_xy(pos[a], 'right', off + spread + sa), port_xy(pos[b], 'right', -off + spread + sb)
        p1, p2 = (p0[0] + bulge, p0[1]), (p3[0] + bulge, p3[1])
        lx, ly, anchor = p0[0] + bulge * 0.75 + 6, (p0[1] + p3[1]) / 2 + 4, 'start'
    else:                                        # diagonal
        p0, p3 = port_xy(pos[a], side_a, off + sa), port_xy(pos[b], side_b, off + sb)
        my = (p0[1] + p3[1]) / 2
        p1, p2 = (p0[0], my), (p3[0], my)
        lx, ly = (p0[0] + p3[0]) / 2, my - 6
    samples = [bezier(p0, p1, p2, p3, i / 40) for i in range(41)]
    d = f'M{p0[0]:.1f},{p0[1]:.1f} C{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} {p3[0]:.1f},{p3[1]:.1f}'
    return d, samples, (lx, ly), anchor


def side_shifts(edges, cells, pos):
    """Edges that share one side of a box get spread 22 px apart, ordered by where the other end is."""
    users = {}
    for ed in edges:
        sa, sb = ports(ed, cells)
        users.setdefault((ed['from'], sa), []).append((ed['key'], 'a', cells[ed['to']]))
        users.setdefault((ed['to'], sb), []).append((ed['key'], 'b', cells[ed['from']]))
    out = {}
    for (node, side), lst in users.items():
        if len(lst) < 2:
            continue
        horiz = side in ('top', 'bottom')
        lst.sort(key=lambda u: u[2][0] if horiz else u[2][1])
        for k, (key, end, _) in enumerate(lst):
            out[(key, end)] = (k - (len(lst) - 1) / 2) * 22
    return out


def inside(pt, rect, inset=2):
    x, y, w, h = rect
    return x + inset < pt[0] < x + w - inset and y + inset < pt[1] < y + h - inset


def group_rect(g, pos, depth=0):
    """depth = how many other groups sit inside this one; each level adds padding."""
    pad = 18 * depth
    rs = [pos[n] for n in g['nodes']]
    x0 = min(r[0] for r in rs) - 14 - pad; y0 = min(r[1] for r in rs) - 26 - pad
    x1 = max(r[0] + r[2] for r in rs) + 14 + pad; y1 = max(r[1] + r[3] for r in rs) + 14 + pad
    return (x0, y0, x1 - x0, y1 - y0)


def node_colors(scene):
    """id -> colour: the node's own, else its smallest group's, else emerald."""
    out = {}
    for n in scene['nodes']:
        gs = sorted((g for g in scene.get('groups', []) if n['id'] in g['nodes'] and g.get('color')), key=lambda g: len(g['nodes']))
        out[n['id']] = n.get('color') or (gs[0]['color'] if gs else 'emerald')
    return out


def story_order(scene):
    """Nodes in the order the narration first lights them (the phone column reads top to bottom)."""
    seen = []
    for s in scene.get('steps', []):
        for part in [s] + s.get('cues', []):
            for n in [x for pair in part.get('edges', []) for x in pair] + part.get('focus', []):
                if n not in seen:
                    seen.append(n)
    by_id = {n['id']: n for n in scene['nodes']}
    return [by_id[i] for i in seen] + [n for n in scene['nodes'] if n['id'] not in seen]


def build_svg(scene, cols, use_at, tag, warnings):
    nodes = scene['nodes']
    # the gap between columns must fit the widest label of an arrow running between two boxes in a row
    widest = max([text_w(ed['label'], 11.5) for ed in scene['edges'] if ed.get('label')] or [0])
    pos, cells, _, _ = layout(nodes, cols, use_at, gx=max(GX, min(150, widest + 26)))
    ncells = (max(c for c, _ in cells.values()) + 1) * (max(r for _, r in cells.values()) + 1)
    if len(nodes) > 2 and ncells > 2 * len(nodes):
        warnings.append(f'[{tag}] the grid has {ncells} cells for {len(nodes)} nodes; labels will render small. Pack the "at" positions')
    keys = {e['key'] for e in scene['edges']}
    colors = node_colors(scene)
    e = html.escape
    shifts = side_shifts(scene['edges'], cells, pos)
    boxes = list(pos.values())                     # everything drawn, for the viewBox
    groups, edges_out, labels, lanes, elabel_boxes = [], [], [], {}, []
    glabels, kept_glabels = [], []
    all_groups = scene.get('groups', [])
    for g in sorted(all_groups, key=lambda g: -len(g['nodes'])):
        depth = sum(1 for h in all_groups if h is not g and set(h['nodes']) < set(g['nodes']))
        gx, gy, gw, gh = group_rect(g, pos, depth)
        lbox = (gx + 12, gy + 5, text_w(g['label'], 12, True), 14)
        if any(abs(lbox[0] - o[0]) < max(lbox[2], o[2]) and abs(lbox[1] - o[1]) < 14 for o in glabels):
            warnings.append(f'[{tag}] group label "{g["label"]}" overlaps another group label')
        glabels.append(lbox)
        clash = [n['id'] for n in nodes if n['id'] not in g['nodes'] and
                 inside((pos[n['id']][0] + pos[n['id']][2] / 2, pos[n['id']][1] + pos[n['id']][3] / 2), (gx, gy, gw, gh), 0)]
        if clash:
            warnings.append(f'[{tag}] group "{g["label"]}" covers non-member node(s) {clash}; group dropped in this layout')
            continue
        gc = f' c-{g["color"]}' if g.get('color') else ''
        kept_glabels.append((gx + 8, gy + 3, text_w(g['label'], 12, True) + 8, 18))
        groups.append(f'<rect class="grp{gc}" x="{gx:.1f}" y="{gy:.1f}" width="{gw:.1f}" height="{gh:.1f}" rx="14"/>')
        labels.append(f'<text class="glbl{gc}" x="{gx + 12:.1f}" y="{gy + 17:.1f}">{e(g["label"])}</text>')
        boxes.append((gx, gy, gw, gh))
    routes = {}
    if avoid_available():
        shapes = []
        for n in nodes:
            x, y, w, h = pos[n['id']]
            dec = n.get('kind') == 'decision'
            shapes.append({'id': n['id'], 'x': x, 'y': y - 6 if dec else y, 'w': w, 'h': h + 12 if dec else h, 'diamond': dec})
        shapes += [{'id': f'glabel{i}', 'x': b[0], 'y': b[1], 'w': b[2], 'h': b[3], 'obstacle': True} for i, b in enumerate(kept_glabels)]
        try:
            routes = {k: simplify(v) for k, v in run_avoid(shapes, [{'key': ed['key'], 'from': ed['from'], 'to': ed['to']}
                                                                     for ed in scene['edges']]).items()}
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as ex:
            warnings.append(f'[{tag}] arrow routing failed, so arrows use the simple curves: {str(ex)[:160]}')
    else:
        warnings.append(f'[{tag}] libavoid-js is missing, so arrows use the simple curves. Run npm ci where package.json is')
    blocked = list(pos.values()) + kept_glabels
    for ed in scene['edges']:
        (ac, ar), (bc, br) = cells[ed['from']], cells[ed['to']]
        lane_key = ('row', ar) if ar == br and abs(ac - bc) > 1 else ('col', ac) if ac == bc and abs(ar - br) > 1 else None
        lane = lanes.get(lane_key, 0)
        if lane_key:
            lanes[lane_key] = lane + 1
        pts = routes.get(ed['key'])
        if pts and len(pts) >= 2:
            d, samples = rounded_path(pts), densify(pts)
            lane_key = None if len(pts) == 2 else lane_key
        else:
            rev = _edge_key(ed['to'], ed['from']) in keys
            d, samples, (lx, ly), anchor = route(ed, pos, cells, rev, lane,
                                                 shifts.get((ed['key'], 'a'), 0), shifts.get((ed['key'], 'b'), 0))
        hits = [n['id'] for n in nodes if n['id'] not in (ed['from'], ed['to'])
                and any(inside(p, pos[n['id']]) for p in samples)]
        if hits:
            warnings.append(f'[{tag}] edge {ed["key"]} passes behind node(s) {hits}; set "at" positions to route around')
        xs, ys = [p[0] for p in samples], [p[1] for p in samples]
        boxes.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
        skip = ' skip' if lane_key else ''
        col = TONES.get(ed.get('tone'), colors[ed['from']])
        skip += ' tone' if ed.get('tone') else ''
        edges_out.append(f'<path class="edge k-{ed.get("kind", "sync")} c-{col}{skip}" data-e="{e(ed["key"])}" d="{d}" marker-end="url(#arr-{tag})"/>')
        if ed.get('label'):
            if pts and len(pts) >= 2:
                lx, ly, anchor, lb, clear = place_label(pts, ed['label'], blocked + elabel_boxes)
                if not clear:
                    warnings.append(f'[{tag}] the label of edge {ed["key"]} has no clear spot on its arrow; shorten it or space the boxes')
            else:
                lw = text_w(ed['label'], 11.5)
                lb = (lx if anchor == 'start' else lx - lw if anchor == 'end' else lx - lw / 2, ly - 12, lw, 16)
                if any(overlaps(lb, o) for o in elabel_boxes):
                    warnings.append(f'[{tag}] the label of edge {ed["key"]} overlaps another edge label')
            elabel_boxes.append(lb); boxes.append(lb)
            labels.append(f'<text class="elbl c-{col}{skip}" data-e="{e(ed["key"])}" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{e(ed["label"])}</text>')
    for k1, k2 in side_by_side(routes):
        warnings.append(f'[{tag}] arrows {k1} and {k2} run side by side and read as one line; move a box with "at"')
    node_out = []
    for n in nodes:
        x, y, nw, nh = pos[n['id']]
        if text_w(n['label'], 15, True) > nw - 16:
            warnings.append(f'[{tag}] node "{n["id"]}" label is probably wider than its box; shorten it')
        sub = f'<text class="sub" x="{x + nw / 2:.1f}" y="{y + 44:.1f}">{e(n.get("sub", ""))}</text>' if n.get('sub') else ''
        ty = y + 28 if n.get('sub') else y + nh / 2 + 5
        kind = n.get('kind', 'service')
        if kind == 'decision':
            shape = (f'<polygon class="shape" points="{x:.1f},{y + nh / 2:.1f} {x + nw / 2:.1f},{y - 6:.1f} '
                     f'{x + nw:.1f},{y + nh / 2:.1f} {x + nw / 2:.1f},{y + nh + 6:.1f}"/>')
            if text_w(n['label'], 15, True) > nw * 0.62:
                warnings.append(f'[{tag}] decision "{n["id"]}" label is too long for a diamond; keep it to about {int(nw * 0.62 / 9)} characters')
        else:
            shape = f'<rect class="shape" x="{x:.1f}" y="{y:.1f}" width="{nw:.1f}" height="{nh:.1f}" rx="{18 if kind == "store" else 10}"/>'
        node_out.append(f'<g class="node kind-{kind} c-{colors[n["id"]]}" data-n="{e(n["id"])}">' + shape +
                        f'<text class="lbl" x="{x + nw / 2:.1f}" y="{ty:.1f}">{e(n["label"])}</text>{sub}</g>')
    x0 = min(b[0] for b in boxes) - 12; y0 = min(b[1] for b in boxes) - 12
    x1 = max(b[0] + b[2] for b in boxes) + 12; y1 = max(b[1] + b[3] for b in boxes) + 12
    head = (f'<svg class="dia {tag}" style="max-width:{(x1 - x0) * 1.15:.0f}px" viewBox="{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}" role="img" aria-label="{e(scene.get("title", "diagram"))}">'
            f'<defs><marker id="arr-{tag}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/></marker></defs>')
    return head + ''.join(groups + edges_out + node_out + labels) + '</svg>'


# ---------------------------------------------------------------- arrow routing (libavoid)
# The boxes stay where the author put them ("at"). libavoid (Adaptagrams, via libavoid-js at build
# time) routes right-angle arrows around them, spreads arrows that share a side, and avoids crossings.
# If node_modules is missing, the hand-drawn curves of route() are the fallback.

def avoid_available():
    return os.path.isfile(os.path.join(NODE_MODULES, 'libavoid-js', 'dist', 'libavoid.wasm'))


def run_avoid(shapes, conns):
    r = subprocess.run(['node', os.path.join(SKILL_DIR, 'avoid_route.mjs')], input=json.dumps({'shapes': shapes, 'conns': conns}),
                       capture_output=True, text=True, cwd=SKILL_DIR, timeout=60)
    if r.returncode != 0:
        raise RuntimeError('arrow routing failed: ' + r.stderr[-400:])
    return json.loads(r.stdout)['routes']


def simplify(pts):
    """Drop repeated and collinear points so corners can be rounded."""
    out = []
    for p in pts:
        p = (round(p[0], 1), round(p[1], 1))
        if out and p == out[-1]:
            continue
        if len(out) >= 2 and (out[-2][0] == out[-1][0] == p[0] or out[-2][1] == out[-1][1] == p[1]):
            out[-1] = p
            continue
        out.append(p)
    return out


def rounded_path(pts, r=9):
    """Orthogonal polyline -> path with rounded corners."""
    d = f'M{pts[0][0]:.1f},{pts[0][1]:.1f}'
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1, l2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
        k = min(r, l1 / 2, l2 / 2)
        if k < 1:
            d += f' L{x1:.1f},{y1:.1f}'; continue
        ax, ay = x1 - (x1 - x0) / l1 * k, y1 - (y1 - y0) / l1 * k
        bx, by = x1 + (x2 - x1) / l2 * k, y1 + (y2 - y1) / l2 * k
        d += f' L{ax:.1f},{ay:.1f} Q{x1:.1f},{y1:.1f} {bx:.1f},{by:.1f}'
    return d + f' L{pts[-1][0]:.1f},{pts[-1][1]:.1f}'


def densify(pts, step=6):
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    return out + [pts[-1]]


def overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def side_by_side(paths):
    """Pairs of arrows that share no box but run parallel and close (under 16 px apart, over 20 px long).
    They read as one tangled line, so the build warns. paths: {key: [(x, y), ...]}"""
    segs = [(k, a, b) for k, pts in paths.items() for a, b in zip(pts, pts[1:])]
    found = set()
    for i, (k1, a1, b1) in enumerate(segs):
        for k2, a2, b2 in segs[i + 1:]:
            if k1 == k2 or set(k1.split('>')) & set(k2.split('>')) or (k1, k2) in found:
                continue
            for ax in (0, 1):                    # ax 0: both horizontal; ax 1: both vertical
                o = 1 - ax
                if abs(a1[o] - b1[o]) < 0.5 and abs(a2[o] - b2[o]) < 0.5 and abs(a1[o] - a2[o]) < 16:
                    run = min(max(a1[ax], b1[ax]), max(a2[ax], b2[ax])) - max(min(a1[ax], b1[ax]), min(a2[ax], b2[ax]))
                    if run > 20:
                        found.add((k1, k2))
    return sorted(found)


def place_label(pts, text, blocked):
    """Put an arrow label on its route: above a horizontal segment, or beside a vertical one.
    Longest segment first; the first spot clear of boxes and other labels wins. Returns (x, y, anchor, box, clear)."""
    lw = text_w(text, 11.5)
    segs = sorted(zip(pts, pts[1:]), key=lambda s: -math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]))
    tries = []
    for (x0, y0), (x1, y1) in segs:
        if abs(y0 - y1) < 0.5:                    # horizontal: centred above, then below
            mx = (x0 + x1) / 2
            tries += [(mx, y0 - 6, 'middle', (mx - lw / 2, y0 - 18, lw, 16)),
                      (mx, y0 + 16, 'middle', (mx - lw / 2, y0 + 4, lw, 16))]
        else:                                     # vertical: right of the line, then left
            my = (y0 + y1) / 2 + 4
            tries += [(x0 + 7, my, 'start', (x0 + 7, my - 12, lw, 16)),
                      (x0 - 7, my, 'end', (x0 - 7 - lw, my - 12, lw, 16))]
    for t in tries:
        if not any(overlaps(t[3], o) for o in blocked):
            return t + (True,)
    return tries[0] + (False,)




# ---------------------------------------------------------------- sequence diagrams
# Participants across the top, a dashed lifeline under each, one row per message. Each message is a
# path with class "edge" and key "m<n>", so the walkthrough lights and animates it like a flow arrow.

SEQ_BOX_H, SEQ_ROW, SEQ_SELF_ROW, SEQ_NOTE_H = 46, 46, 58, 32


def seq_svg(d, tag, warnings):
    e = html.escape
    parts = d['nodes']
    idx = {p['id']: i for i, p in enumerate(parts)}
    colors = node_colors(d)
    bw = [max(84, text_w(p['label'], 15, True) + 30) for p in parts]
    gaps = [(bw[i] + bw[i + 1]) / 2 + 30 for i in range(len(parts) - 1)]
    right_pad = 0
    for m in d['edges']:                      # widen the gaps until every message label fits its span
        a, b = idx[m['from']], idx[m['to']]
        lw = text_w(f'{m["n"]}  {m["label"]}', 13) + 28
        if a == b:
            if a < len(gaps):
                gaps[a] = max(gaps[a], lw + 46)
            else:
                right_pad = max(right_pad, lw + 46)
            continue
        lo, hi = min(a, b), max(a, b)
        span = sum(gaps[lo:hi])
        if span < lw:
            for k in range(lo, hi):
                gaps[k] += (lw - span) / (hi - lo)
    xs = [bw[0] / 2]
    for g in gaps:
        xs.append(xs[-1] + g)
    out_parts, life, msgs, labels, notes_out, boxes = [], [], [], [], [], []
    y = SEQ_BOX_H + 34
    notes = d.get('notes', [])

    def put_notes(after):
        nonlocal y
        for nt in [n for n in notes if n['after'] == after]:
            cols = [xs[idx[p]] for p in nt['over'] if p in idx]
            if not cols:
                warnings.append(f'[{tag}] a note names unknown participants {nt["over"]}')
                continue
            tw = text_w(nt['text'], 13) + 24
            if nt['place'] == 'left of':
                x0 = cols[0] - 14 - tw
            elif nt['place'] == 'right of':
                x0 = cols[0] + 14
            else:
                w = max(tw, max(cols) - min(cols) + 60)
                x0 = (min(cols) + max(cols)) / 2 - w / 2
                tw = w
            notes_out.append(f'<g class="note"><rect class="nshape" x="{x0:.1f}" y="{y - 10:.1f}" width="{tw:.1f}" height="{SEQ_NOTE_H - 6}" rx="4"/>'
                             f'<text class="ntxt" x="{x0 + tw / 2:.1f}" y="{y + 10:.1f}">{e(nt["text"])}</text></g>')
            boxes.append((x0, y - 10, tw, SEQ_NOTE_H - 6))
            y += SEQ_NOTE_H + 8
    for i, m in enumerate(d['edges']):
        put_notes(i)
        a, b = idx[m['from']], idx[m['to']]
        col = TONES.get(m.get('tone'), colors[m['from']])
        cls = f'edge k-{m.get("kind", "sync")} c-{col}' + (' tone' if m.get('tone') else '')
        num = f'<tspan class="mnum">{m["n"]}</tspan> '
        if a == b:
            x = xs[a]
            dd = f'M{x:.1f},{y:.1f} L{x + 36:.1f},{y:.1f} L{x + 36:.1f},{y + 20:.1f} L{x + 3:.1f},{y + 20:.1f}'
            lx, ly, anchor = x + 44, y + 14, 'start'
            lw = text_w(f'{m["n"]}  {m["label"]}', 13)
            boxes.append((x, y - 4, 44 + lw, 28))
            step = SEQ_SELF_ROW
        else:
            x0, x1 = xs[a], xs[b]
            x1 += -3 if x1 > x0 else 3                  # the arrowhead tip stops on the lifeline
            dd = f'M{x0:.1f},{y:.1f} L{x1:.1f},{y:.1f}'
            lx, ly, anchor = (xs[a] + xs[b]) / 2, y - 8, 'middle'
            step = SEQ_ROW
        msgs.append(f'<path class="{cls}" data-e="{e(m["key"])}" d="{dd}" marker-end="url(#arr-{tag})"/>')
        labels.append(f'<text class="elbl mlbl c-{col}" data-e="{e(m["key"])}" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{num}{e(m["label"])}</text>')
        y += step
    put_notes(len(d['edges']))
    bottom = y - 10
    for i, p in enumerate(parts):
        x, w = xs[i], bw[i]
        kind = p.get('kind', 'service')
        rx = 18 if kind == 'store' else 10
        out_parts.append(f'<g class="node kind-{kind} c-{colors[p["id"]]}" data-n="{e(p["id"])}">'
                         f'<rect class="shape" x="{x - w / 2:.1f}" y="0" width="{w:.1f}" height="{SEQ_BOX_H}" rx="{rx}"/>'
                         f'<text class="lbl" x="{x:.1f}" y="{SEQ_BOX_H / 2 + 5:.1f}">{e(p["label"])}</text></g>')
        life.append(f'<path class="life" d="M{x:.1f},{SEQ_BOX_H + 2} L{x:.1f},{bottom:.1f}"/>')
        boxes.append((x - w / 2, 0, w, SEQ_BOX_H))
    boxes.append((xs[-1], 0, right_pad, bottom))
    x0 = min(b[0] for b in boxes) - 14; x1 = max(b[0] + b[2] for b in boxes) + 14
    y0, y1 = -14, bottom + 14
    size = f'width:{(x1 - x0) * 0.85:.0f}px;max-width:none' if tag == 'phone' else f'max-width:{(x1 - x0) * 1.15:.0f}px'
    head = (f'<svg class="dia seq {tag}" style="{size}" viewBox="{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}" '
            f'role="img" aria-label="{e(d.get("title", "sequence diagram"))}">'
            f'<defs><marker id="arr-{tag}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/></marker></defs>')
    return head + ''.join(life + notes_out + msgs + out_parts + labels) + '</svg>'


# ---------------------------------------------------------------- sketch theme
# rough.js (via rough.mjs at build time) redraws each box, group, arrow and lifeline by hand. The clean
# shapes stay in the SVG, invisible, so page scripts can still measure them and lights still toggle
# their classes; CSS colours the hand-drawn strokes from those classes.

def _round_rect(x, y, w, h, r):
    return (f'M{x + r:.1f},{y:.1f} H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h - r:.1f} '
            f'Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} H{x + r:.1f} Q{x:.1f},{y + h:.1f} {x:.1f},{y + h - r:.1f} '
            f'V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} Z')


def _attrs(s, *keys):
    return [float(re.search(rf'\b{k}="([-\d.]+)"', s).group(1)) for k in keys]


def _seed(key):
    return sum(ord(c) * (i + 1) for i, c in enumerate(key)) % 9973 + 1


def sketchify(svg):
    jobs = []

    def ph(job):
        jobs.append(job)
        return f'\x00{len(jobs) - 1}\x00'

    def node(m):
        whole, kind, tag, attrs = m.group(0), m.group(2), m.group(4), m.group(5)
        if tag == 'rect':
            x, y, w, h, rx = _attrs(attrs, 'x', 'y', 'width', 'height', 'rx')
            job = {'type': 'path', 'd': _round_rect(x, y, w, h, min(rx, h / 2) * 0.8), 'fill': True}
        else:
            pts = [[float(v) for v in p.split(',')] for p in re.search(r'points="([^"]+)"', attrs).group(1).split()]
            job = {'type': 'polygon', 'points': pts, 'fill': True}
        job['seed'] = _seed(m.group(1))
        return f'{whole}<g class="sk">{ph(job)}</g>'
    svg = re.sub(r'(<g class="node kind-(\w+) c-(\w+)" data-n="[^"]*">)<(rect|polygon) class="shape" ([^>]*)/>', node, svg)

    def group(m):
        x, y, w, h = _attrs(m.group(2), 'x', 'y', 'width', 'height')
        return f'{m.group(0)}<g class="sk skg{m.group(1)}">{ph({"type": "path", "d": _round_rect(x, y, w, h, 14), "roughness": 0.9, "seed": _seed(m.group(2))})}</g>'
    svg = re.sub(r'<rect class="grp([^"]*)" ([^>]*)/>', group, svg)

    def edge(m):
        pts = [(float(a), float(b)) for a, b in re.findall(r'(-?[\d.]+),(-?[\d.]+)', m.group(3))]
        (ax, ay), (bx, by) = pts[-2], pts[-1]
        ang, L = math.atan2(by - ay, bx - ax), 11
        head = [[bx - L * math.cos(ang + t), by - L * math.sin(ang + t)] for t in (-0.45, 0.45)]
        seed = _seed(m.group(2))
        body = ph({'type': 'path', 'd': m.group(3), 'roughness': 0.8, 'bowing': 0.6, 'seed': seed})
        tip = ph({'type': 'line', 'points': [head[0], [bx, by], head[1]], 'roughness': 0.5, 'seed': seed + 1})
        return f'{m.group(0)}<g class="ske{m.group(1)}"><g class="skb">{body}</g>{tip}</g>'
    svg = re.sub(r'<path class="edge([^"]*)" data-e="([^"]*)" d="([^"]+)"[^>]*/>', edge, svg)

    def lifeline(m):
        return f'{m.group(0)}<g class="sk skl">{ph({"type": "path", "d": m.group(1), "roughness": 0.7, "seed": _seed(m.group(1))})}</g>'
    svg = re.sub(r'<path class="life" d="([^"]+)"/>', lifeline, svg)

    def note(m):
        x, y, w, h = _attrs(m.group(1), 'x', 'y', 'width', 'height')
        return f'{m.group(0)}<g class="sk skn">{ph({"type": "path", "d": _round_rect(x, y, w, h, 4), "fill": True, "seed": _seed(m.group(1))})}</g>'
    svg = re.sub(r'<rect class="nshape" ([^>]*)/>', note, svg)

    drawn = node_bridge('rough.mjs', jobs)
    paths = ['' .join(f'<path class="sk{p["c"]}" d="{p["d"]}"/>' for p in ps) for ps in drawn]
    return re.sub(r'\x00(\d+)\x00', lambda m: paths[int(m.group(1))], svg)


def sketch_available():
    return os.path.isfile(os.path.join(NODE_MODULES, 'roughjs', 'bundled', 'rough.esm.js'))


# ---------------------------------------------------------------- pictures

FONT = os.path.join(NODE_MODULES, '@fontsource', 'architects-daughter', 'files',
                    'architects-daughter-latin-400-normal.woff2')


def diagram_css(theme):
    """Tokens, meaning colours and diagram styles, shared by pictures and the narrated page."""
    css = open(os.path.join(SKILL_DIR, 'diagram.css')).read()
    if theme == 'sketch' and os.path.isfile(FONT):
        font = base64.b64encode(open(FONT, 'rb').read()).decode()
        css = f"@font-face{{font-family:Hand;src:url(data:font/woff2;base64,{font}) format('woff2');font-display:block}}\n" + css
    return css


def render(d, tag, warnings, theme='sketch', cols=None, use_at=True):
    """One SVG for the diagram. Flows use the "at" grid (or `cols` snake); sequences ignore both."""
    if d.get('type') == 'sequence':
        svg = seq_svg(d, tag, warnings)
    else:
        svg = build_svg(d, cols or min(4, len(d['nodes'])), use_at, tag, warnings)
    if theme == 'sketch':
        if sketch_available():
            try:
                svg = sketchify(svg)
            except (OSError, DiagramError, ValueError, subprocess.TimeoutExpired) as ex:
                warnings.append(f'[{tag}] the sketch pass failed, so this picture is clean: {str(ex)[:160]}')
        else:
            warnings.append(f'[{tag}] roughjs is missing, so this picture is clean. Run npm ci where package.json is')
    return svg


def render_pair(d, warnings, theme='sketch', cols=None):
    """(desktop svg, phone svg). The phone flow is one column in story order; a sequence is the same on both."""
    desk = render(d, 'desk', warnings, theme, cols, True)
    if d.get('type') == 'sequence':
        return desk, render(d, 'phone', warnings, theme)
    return desk, render(dict(d, nodes=story_order(d)), 'phone', warnings, theme, 1, False)


def legend_html(legend):
    return ''.join(f'<span class="c-{l["color"]}"><i></i>{html.escape(l["label"])}</span>' for l in legend)


def picture_html(d, title, theme, lead=''):
    warnings = []
    desk, phone = render_pair(d, warnings, theme)
    # a picture has no "now": draw every box and arrow at full strength (the walkthrough's "done" state)
    desk, phone = (re.sub(r'class="(node|edge) ', r'class="\1 done ', s) for s in (desk, phone))
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', desk).group(1).split()]
    if vb[2] / vb[3] > 3.6:
        warnings.append(f'[desk] the picture is {vb[2] / vb[3]:.1f} times wider than tall and will render small; '
                        'give "at" positions in the look, or use graph TD')
    width = round(float(re.search(r'viewBox="\S+ \S+ (\S+)', desk).group(1)) + 34)
    e = html.escape
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<style>{diagram_css(theme)}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}}
main{{max-width:1040px;margin:0 auto;padding:28px 16px 40px}}
h1{{font-size:22px;line-height:1.25;font-weight:650;margin:0}}.sketch h1{{font:400 27px/1.2 Hand,cursive}}
.lead{{color:var(--mut);margin:4px 0 16px;max-width:64ch}}
.stage{{border:1px solid var(--line);border-radius:14px;background:var(--surf);--w:max(100%,min(var(--sw,100%),calc(100vw - 32px)));width:var(--w);margin-left:calc((100% - var(--w)) / 2)}}
.canvas{{padding:14px 16px 12px;border-radius:13px}}
</style></head>
<body class="{theme}"><main><h1>{e(title)}</h1><p class="lead">{e(lead)}</p>
<div class="stage" style="--sw:{width}px"><div class="canvas">{desk}{phone}<div class="legend">{legend_html(d.get("legend", []))}</div></div></div>
</main></body></html>'''
    return page, warnings


def main():
    ap = argparse.ArgumentParser(description='Mermaid flow or sequence -> picture page (SVG in HTML)')
    ap.add_argument('src', help='.mmd file, Markdown with a mermaid fence, or a scene .json with "diagram"')
    ap.add_argument('--look', help='JSON file with positions, colours, kinds, tones and legend')
    ap.add_argument('--theme', choices=sorted(THEMES))
    ap.add_argument('--title')
    ap.add_argument('--lead', default='')
    ap.add_argument('-o', '--out')
    a = ap.parse_args()
    try:
        raw = open(a.src).read()
        if a.src.endswith('.json'):
            scene = json.loads(raw)
            src, look = scene['diagram'], scene.get('look', {})
            theme, title, lead = a.theme or scene.get('theme', 'sketch'), a.title or scene.get('title', 'Diagram'), a.lead or scene.get('lead', '')
            if scene.get('legend'):
                look = dict(look, legend=scene['legend'])
        else:
            fence = re.search(r'```mermaid\s*\n([\s\S]*?)```', raw)
            src, look = (fence.group(1) if fence else raw).strip(), json.load(open(a.look)) if a.look else {}
            theme, title, lead = a.theme or 'sketch', a.title or os.path.splitext(os.path.basename(a.src))[0], a.lead
        d = from_mermaid(src, look)
        d['title'] = title
        errs = validate_diagram(d)
        if errs:
            raise DiagramError('\n'.join(errs))
        page, warnings = picture_html(d, title, theme, lead)
        out = a.out or os.path.splitext(a.src)[0] + '.html'
        open(out, 'w').write(page)
        print(json.dumps({'ok': True, 'out': out, 'type': d['type'], 'theme': theme, 'warnings': warnings}))
    except (DiagramError, OSError, KeyError, json.JSONDecodeError) as ex:
        print(f'diagram error:\n{ex}', file=sys.stderr)
        print(json.dumps({'ok': False, 'error': str(ex)}))
        sys.exit(2)


if __name__ == '__main__':
    main()
