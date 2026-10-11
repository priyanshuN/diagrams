#!/usr/bin/env python3
"""Build a narrated walkthrough: scene JSON -> one self-contained HTML page.

The page holds an SVG flow diagram (desktop grid + phone column), one AAC audio track,
captions, a clickable step list, word-timed cues inside steps, a recall quiz, optional
"predict" pauses and source links. The voice is Kokoro-82M: mlx-audio on Apple silicon,
PyTorch (CPU) elsewhere. A system voice (macOS `say`, else espeak-ng) is used only with
--allow-fallback.

usage:
  nw scene.json [-o out.html] [--voice af_heart] [--speed 1.0]
  nw scene.json --check          # validate + layout + pronunciation preview, no audio
Prints one JSON object on stdout; everything else goes to stderr.
"""
import argparse, base64, contextlib, datetime, html, io, json, math, os, platform, re, shutil, subprocess, sys, tempfile, wave

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
# Layer 1 (the diagrams:flow skill, a sibling folder) draws every picture; this layer adds voice, cues and the quiz.
FLOW_DIR = os.environ.get('FLOW_DIAGRAM_DIR') or next(
    (d for d in (os.path.join(os.path.dirname(SKILL_DIR), n) for n in ('flow', 'flow-diagram')) if os.path.isdir(d)),
    os.path.join(os.path.dirname(SKILL_DIR), 'flow'))
sys.path.insert(0, FLOW_DIR)
import diagram as D  # noqa: E402
SR = 24_000
GAP_S = 0.45
KOKORO_MLX = 'mlx-community/Kokoro-82M-bf16'
KOKORO_TORCH = 'hexgrad/Kokoro-82M'
# Apple silicon runs Kokoro on MLX; every other machine runs the same model on PyTorch (CPU).
USE_MLX = sys.platform == 'darwin' and platform.machine() == 'arm64'
VOICE_RE = re.compile(r'^[abjzefhip][fm]_[a-z]+$')
VERSION = 4

TOP_KEYS = {'title', 'lead', 'voice', 'speed', 'cols', 'lexicon', 'repo', 'nodes', 'groups', 'edges', 'steps', 'legend',
            'diagram', 'look', 'theme'}
STEP_KEYS = {'say', 'caption', 'focus', 'edges', 'msgs', 'cues', 'ask', 'src', 'item', 'carry'}
CUE_KEYS = {'at', 'focus', 'edges', 'msgs', 'item', 'carry'}
_edge_key = D._edge_key


class SceneError(Exception):
    pass


def log(*a):
    print(*a, file=sys.stderr)


# ---------------------------------------------------------------- speech text

def load_lexicon(scene):
    lex = {}
    p = os.path.join(SKILL_DIR, 'lexicon.json')
    if os.path.exists(p):
        lex.update(json.load(open(p)))
    lex.update(scene.get('lexicon', {}))
    return lex


def _clock(m):
    if m.group(5) and m.group(5).upper() in ('AM', 'PM'):   # 9:30 PM: already 12-hour
        h, mi = int(m.group(3)), int(m.group(4))
        return str(h) if mi == 0 else f'{h} {mi:02d}'
    return _clock_hm(*(m.group(1, 2) if m.group(1) else m.group(3, 4)))


def _clock_hm(h, mi):
    h, mi = int(h), int(mi)
    suffix = 'AM' if h < 12 else 'PM'
    h12 = h % 12 or 12
    return f'{h12} {suffix}' if mi == 0 else f'{h12} {mi:02d} {suffix}'


def _indian(n):
    """842 -> '842'; 150000 -> '1 lakh 50 thousand'; 25000000 -> '2 crore 50 lakh'."""
    n = int(n)
    if n < 100_000:
        return str(n)
    parts = []
    for size, name in ((10_000_000, 'crore'), (100_000, 'lakh'), (1_000, 'thousand')):
        if n >= size:
            parts.append(f'{n // size} {name}'); n %= size
    if n:
        parts.append(str(n))
    return ' '.join(parts)


def _rupees(m):
    whole, frac = m.group(1).replace(',', ''), m.group(2)
    return f'{_indian(whole)} rupees' + (f' and {int(frac)} paise' if frac and int(frac) else '')


SPEECH_RULES = [
    (re.compile(r'`([^`]*)`'), r'\1'),
    (re.compile(r'(?:₹|\bRs\.?)\s?(\d[\d,]*)(?:\.(\d{1,2}))?'), _rupees),
    (re.compile(r'\b\d{1,2}(?:,\d{2})+,\d{3}\b'), lambda m: _indian(m.group(0).replace(',', ''))),
    # 24-hour clock: zero-padded (02:00, 14:30), or any H:MM followed by a zone or AM/PM
    (re.compile(r'(?<![\d:])(?:([01]\d|2[0-3]):([0-5]\d)|(1?\d|2[0-3]):([0-5]\d)(?=\s*(IST|UTC|GMT|AM|PM|am|pm)\b))(?![\d:])'),
     _clock),
    (re.compile(r'\bv(\d+)\.(\d+)(?:\.(\d+))?\b'),
     lambda m: 'version ' + ' point '.join(g for g in m.groups() if g is not None)),
    (re.compile(r'\s*(?:→|->|⟶)\s*'), ', then '),
    (re.compile(r'\s*(?:←|<-)\s*'), ', from '),
    (re.compile(r'\be\.g\.', re.I), 'for example'),
    (re.compile(r'\bi\.e\.', re.I), 'that is'),
    (re.compile(r'\s*&\s*'), ' and '),
    (re.compile(r'≈\s*'), 'about '),
]


def speakable(text, lex):
    for rx, rep in SPEECH_RULES:
        text = rx.sub(rep, text)
    for key in sorted(lex, key=len, reverse=True):
        if re.match(r'^\w', key):
            text = re.sub(r'(?<![\w\[])' + re.escape(key) + r'(?![\w\]])', lambda _m, v=lex[key]: v, text)
        else:
            text = text.replace(key, lex[key])
    return re.sub(r'\s{2,}', ' ', text).strip()


NOTABLE = re.compile(r'[A-Z]{2,}|\d|\bRs\b|[^\w\s.,;:!?\'"()\-]')


# ---------------------------------------------------------------- validation

def _edge_key(a, b):
    return f'{a}>{b}'


def validate(scene):
    errs = []
    if not isinstance(scene, dict):
        raise SceneError('the scene must be a JSON object')
    for k in set(scene) - TOP_KEYS:
        errs.append(f'unknown top-level key "{k}" (allowed: {", ".join(sorted(TOP_KEYS))})')
    if scene.get('diagram') is not None:
        if any(k in scene for k in ('nodes', 'edges', 'groups')):
            errs.append('use "diagram" (Mermaid) or "nodes"/"edges"/"groups", not both')
        elif not isinstance(scene['diagram'], str):
            errs.append('"diagram" must be Mermaid text (graph TD/LR or sequenceDiagram)')
        else:
            try:
                d = D.from_mermaid(scene['diagram'], dict(scene.get('look', {}), legend=scene.get('legend', [])))
                scene.update(type=d['type'], nodes=d['nodes'], edges=d['edges'], groups=d['groups'], notes=d['notes'])
            except D.DiagramError as ex:
                errs.append(f'diagram: {ex}')
    elif 'look' in scene:
        errs.append('"look" styles a Mermaid "diagram"; with "nodes", put at/color/kind on each node')
    for k in ('title', 'nodes', 'steps'):
        if not scene.get(k):
            errs.append(f'"{k}" is missing or empty' + (' (or give a Mermaid "diagram")' if k == 'nodes' else ''))
    if scene.get('theme', 'clean') not in D.THEMES:
        errs.append(f'"theme" must be one of {sorted(D.THEMES)}')
    if errs:
        raise SceneError('\n'.join(errs))
    if 'cols' in scene and not (isinstance(scene['cols'], int) and 1 <= scene['cols'] <= 8):
        errs.append('"cols" must be an integer from 1 to 8')
    for k in ('nodes', 'steps'):
        if not isinstance(scene[k], list) or not all(isinstance(x, dict) for x in scene[k]):
            errs.append(f'"{k}" must be a list of objects')
    if errs:
        raise SceneError('\n'.join(errs))
    scene.setdefault('type', 'flow')
    errs += D.validate_diagram(scene)
    idset = {n.get('id') for n in scene['nodes']}
    ekeys = {e['key'] for e in scene['edges']}
    seq = scene['type'] == 'sequence'
    nmsg = len(scene['edges'])

    def check_item(where, obj):
        it = obj.get('item')
        if it is not None and not (isinstance(it, dict) and isinstance(it.get('name'), str) and isinstance(it.get('fields', {}), dict)
                                   and set(it) <= {'name', 'fields'}):
            errs.append(f'{where}: "item" must be {{"name": "...", "fields": {{"key": "value"}}}}')
        if 'carry' in obj and not (isinstance(obj['carry'], str) and 0 < len(obj['carry']) <= 18):
            errs.append(f'{where}: "carry" must be a short label (18 characters or fewer)')

    def check_refs(where, obj):
        check_item(where, obj)
        if not all(isinstance(obj.get(k, []), list) for k in ('focus', 'edges', 'msgs')):
            errs.append(f'{where}: "focus", "edges" and "msgs" must be lists, e.g. "focus": ["ses"]')
            return
        for n in obj.get('focus', []):
            if n not in idset:
                errs.append(f'{where}: unknown node "{n}" in focus')
        if seq and obj.get('edges'):
            errs.append(f'{where}: a sequence lights messages by number: use "msgs": [3], not "edges"')
        if not seq and obj.get('msgs'):
            errs.append(f'{where}: "msgs" is for sequence diagrams; a flow uses "edges": [["a", "b"]]')
        for n in obj.get('msgs', []):
            if not (isinstance(n, int) and 1 <= n <= nmsg):
                errs.append(f'{where}: msgs {n} is not a message number (1 to {nmsg})')
        for pair in obj.get('edges', []):
            if not (isinstance(pair, list) and len(pair) == 2) or _edge_key(*pair) not in ekeys:
                errs.append(f'{where}: edge {pair} is not declared in the top-level "edges"')

    for i, s in enumerate(scene['steps']):
        w = f'step {i + 1}'
        for k in set(s) - STEP_KEYS:
            errs.append(f'{w}: unknown key "{k}"')
        if not (s.get('say') or s.get('caption')):
            errs.append(f'{w}: needs "caption" (and optionally "say")')
        check_refs(w, s)
        for j, c in enumerate(s.get('cues', [])):
            for k in set(c) - CUE_KEYS:
                errs.append(f'{w} cue {j + 1}: unknown key "{k}"')
            if not c.get('at') or not norm_words(str(c['at'])):
                errs.append(f'{w} cue {j + 1}: "at" must contain at least one word from the spoken line')
            check_refs(f'{w} cue {j + 1}', c)
        if 'ask' in s and not (isinstance(s['ask'], dict) and s['ask'].get('q') and s['ask'].get('a')):
            errs.append(f'{w}: "ask" needs "q" and "a"')
    if scene.get('voice') and not VOICE_RE.match(scene['voice']):
        errs.append(f'voice "{scene["voice"]}" is not a Kokoro voice name like af_heart')
    if errs:
        raise SceneError('\n'.join(errs))
    return scene


def lit_keys(part):
    """A step or cue -> the arrow keys it lights: flow pairs ["a", "b"] -> "a>b", sequence msgs 3 -> "m3"."""
    return [_edge_key(*p) for p in part.get('edges', [])] + [f'm{n}' for n in part.get('msgs', [])]


def resolve_src(scene, step_i, src, warnings):
    """'path:line' (relative to scene.repo) -> checked display string."""
    out = []
    for ref in ([src] if isinstance(src, str) else src):
        m = re.match(r'^(.+?)(?::(\d+))?$', ref)
        path, line = m.group(1), m.group(2)
        root = os.path.expanduser(scene.get('repo', ''))
        full = os.path.join(root, path) if root else os.path.expanduser(path)
        if root and not os.path.realpath(full).startswith(os.path.realpath(root) + os.sep):
            warnings.append(f'step {step_i + 1}: src "{ref}" is outside the repo {root}')
        elif line is not None and int(line) < 1:
            warnings.append(f'step {step_i + 1}: src "{ref}" line must be 1 or more')
        elif not os.path.isfile(full):
            warnings.append(f'step {step_i + 1}: src "{ref}" does not exist under {root or "cwd"}')
        elif line:
            n = sum(1 for _ in open(full, errors='replace'))
            if int(line) > n:
                warnings.append(f'step {step_i + 1}: src "{ref}" is past the end of the file ({n} lines)')
        out.append(ref)
    return out


def git_sha(scene):
    root = os.path.expanduser(scene.get('repo', ''))
    if not root:
        return None
    try:
        sha = subprocess.run(['git', '-C', root, 'rev-parse', '--short', 'HEAD'],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', root, 'status', '--porcelain'], capture_output=True, text=True).stdout.strip()
        return sha + ('+dirty' if dirty else '')
    except (OSError, subprocess.CalledProcessError):
        return None


# ---------------------------------------------------------------- voice

def kokoro_pipeline(lang):
    """Kokoro's pipeline for one language code. Both backends share its API: load_voice, g2p, and
    calls that yield results with .audio and .tokens (word start_ts / end_ts)."""
    with contextlib.redirect_stdout(sys.stderr):
        if USE_MLX:
            from mlx_audio.tts.utils import load_model
            return load_model(model_path=KOKORO_MLX)._get_pipeline(lang)
        from kokoro import KPipeline
        return KPipeline(lang_code=lang, repo_id=KOKORO_TORCH)


def kokoro_synth(lines, voice, speed):
    """-> list of (float32 audio, [(word, start_s, end_s)])"""
    import numpy as np
    pipe = kokoro_pipeline(voice[0])
    with contextlib.redirect_stdout(sys.stderr):
        out = []
        for line in lines:
            chunks, words, offset = [], [], 0.0
            for r in pipe(line, voice=voice, speed=speed):
                a = r.audio.detach().cpu().numpy() if hasattr(r.audio, 'detach') else r.audio  # torch tensor or MLX array
                a = np.array(a, dtype=np.float32).reshape(-1)
                for tk in r.tokens or []:
                    if tk.start_ts is not None and re.search(r'\w', tk.text):
                        words.append((tk.text, offset + tk.start_ts, offset + (tk.end_ts or tk.start_ts)))
                chunks.append(a); offset += len(a) / SR
            out.append((np.concatenate(chunks) if chunks else np.zeros(SR // 2, np.float32), words))
    return out


def fallback_voice():
    """The system voice for --say / --allow-fallback: macOS `say`, else espeak-ng; None when neither exists."""
    if shutil.which('say'):
        return 'macos-say'
    if shutil.which('espeak-ng'):
        return 'espeak-ng'
    return None


def fallback_synth(lines):
    """System voice. Word times are estimated from character position."""
    import numpy as np
    engine = fallback_voice()
    if engine is None:
        raise RuntimeError('no system voice: install espeak-ng (Linux) or use macOS')
    out = []
    with tempfile.TemporaryDirectory() as td:
        for i, line in enumerate(lines):
            p = os.path.join(td, f'{i}.wav')
            plain = re.sub(r'\[([^\]]+)\]\(/[^)]*/\)', r'\1', line)
            if engine == 'macos-say':
                subprocess.run(['say', '-o', p, f'--data-format=LEI16@{SR}', plain], check=True)
            else:
                subprocess.run(['espeak-ng', '-w', p, plain], check=True, capture_output=True)
            with wave.open(p) as w:
                rate = w.getframerate()
                a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
            if rate != SR:
                a = np.interp(np.arange(int(len(a) * SR / rate)) * rate / SR, np.arange(len(a)), a).astype(np.float32)
            dur, words = len(a) / SR, []
            for m in re.finditer(r'\w[\w\'-]*', plain):
                words.append((m.group(0), dur * m.start() / max(1, len(plain)), dur * m.end() / max(1, len(plain))))
            out.append((a, words))
    return out


def encode(audio):
    import numpy as np
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    wav = buf.getvalue()
    with tempfile.TemporaryDirectory() as td:
        src, dst = os.path.join(td, 'a.wav'), os.path.join(td, 'a.m4a')
        open(src, 'wb').write(wav)
        # AAC keeps the page about ten times smaller than WAV: afconvert on macOS, else ffmpeg.
        for cmd in (['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '64000', src, dst],
                    ['ffmpeg', '-v', 'error', '-y', '-i', src, '-c:a', 'aac', '-b:a', '64k', '-f', 'mp4', dst]):
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                return 'audio/mp4', open(dst, 'rb').read()
            except (OSError, subprocess.CalledProcessError):
                continue
        return 'audio/wav', wav


def norm_word(s):
    return re.sub(r'[^\w]', '', s).lower()


def norm_words(phrase):
    plain = re.sub(r'\[([^\]]+)\]\(/[^)]*/\)', r'\1', phrase)
    return [norm_word(w) for w in plain.split() if norm_word(w)]


def find_cue(words, phrase, start_idx):
    """words: [(text, start, end)] in spoken order. phrase is already speakable()."""
    want = norm_words(phrase)
    if not want:
        return None
    got = [norm_word(w[0]) for w in words]
    for i in range(start_idx, len(got) - len(want) + 1):
        if got[i:i + len(want)] == want:
            return i
    return None


def place_cues(scene, spoken, words_per_step, lex):
    """Match each cue phrase (spoken form) to a word index, in order. -> ([[(cue, idx)]], errors)"""
    placed, errors = [], []
    for i, (s, words) in enumerate(zip(scene['steps'], words_per_step)):
        row, idx = [], 0
        for c in s.get('cues', []):
            phrase = speakable(str(c['at']), lex)
            j = find_cue(words, phrase, idx)
            if j is None:
                errors.append(f'step {i + 1}: cue "{c["at"]}" (spoken as "{phrase}") is not in the spoken line '
                              f'after the previous cue: {spoken[i]!r}')
                continue
            row.append((c, j)); idx = j + 1
        placed.append(row)
    return placed, errors


# ---------------------------------------------------------------- main

def page_script_error():
    """Syntax-check page.html's script with `node --check`, before any audio is made.
    A syntax error stops every control on the page, and nothing else in the build would notice."""
    if not shutil.which('node'):
        return None
    src = open(os.path.join(SKILL_DIR, 'page.html')).read()
    js = src[src.index('<script>') + len('<script>'):src.rindex('</script>')].replace('__DATA__', '{}')
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write(js)
    try:
        r = subprocess.run(['node', '--check', f.name], capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return None if r.returncode == 0 else 'page.html script: ' + ' '.join(r.stderr.strip().splitlines()[:5])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scene')
    ap.add_argument('-o', '--out')
    ap.add_argument('--voice')
    ap.add_argument('--speed', type=float)
    ap.add_argument('--check', action='store_true', help='validate, check layout, preview pronunciation; no audio')
    ap.add_argument('--say', action='store_true', help='use the system voice (macOS say, else espeak-ng)')
    ap.add_argument('--allow-fallback', action='store_true', help='use the system voice if Kokoro fails')
    args = ap.parse_args()

    try:
        scene = validate(json.load(open(args.scene)))
    except (SceneError, json.JSONDecodeError, OSError) as ex:
        log(f'scene error:\n{ex}')
        print(json.dumps({'ok': False, 'error': str(ex)}))
        sys.exit(2)
    script_err = page_script_error()
    if script_err:
        log(script_err); print(json.dumps({'ok': False, 'error': script_err})); sys.exit(2)

    voice = args.voice or scene.get('voice', 'af_heart')
    if not VOICE_RE.match(voice):
        log(f'voice "{voice}" is not a Kokoro voice name'); print(json.dumps({'ok': False, 'error': 'bad voice'})); sys.exit(2)
    speed = args.speed or scene.get('speed', 1.0)
    lex = load_lexicon(scene)
    spoken = [speakable(s.get('say') or s['caption'], lex) for s in scene['steps']]

    warnings = []
    theme = scene.get('theme', 'clean')
    svg_desk, svg_phone = D.render_pair(scene, warnings, theme, scene.get('cols'))
    srcs = [resolve_src(scene, i, s['src'], warnings) if s.get('src') else [] for i, s in enumerate(scene['steps'])]
    for i, line in enumerate(spoken):
        left = re.findall(r'[^\w\s.,;:!?\'"()\[\]/ˈˌ$%+=-]', re.sub(r'\[[^\]]+\]\(/[^)]*/\)', '', line))
        if left:
            warnings.append(f'step {i + 1}: spoken line still has symbols {sorted(set(left))}; add them to the lexicon')
        if len(line.split()) > 45:
            warnings.append(f'step {i + 1}: spoken line has {len(line.split())} words; split the step (aim for under 40)')

    if args.check:
        pipe = kokoro_pipeline(voice[0])
        errors = []
        try:
            with contextlib.redirect_stdout(sys.stderr):
                pipe.load_voice(voice)
        except Exception as ex:
            errors.append(f'voice "{voice}" cannot be loaded: {ex}')
        preview, words_per_step = [], []
        for i, line in enumerate(spoken):
            with contextlib.redirect_stdout(sys.stderr):
                _, toks = pipe.g2p(line)
            words_per_step.append([(tk.text, 0.0, 0.0) for tk in toks if re.search(r'\w', tk.text)])
            notable = [f'{t.text}=/{t.phonemes}/' for t in toks
                       if t.phonemes and (NOTABLE.search(t.text) or t.text in lex)]
            preview.append({'step': i + 1, 'say': line, 'check_these': notable})
        errors += place_cues(scene, spoken, words_per_step, lex)[1]
        print(json.dumps({'ok': not warnings and not errors, 'errors': errors, 'warnings': warnings,
                          'pronunciation': preview}, ensure_ascii=False, indent=1))
        sys.exit(2 if errors else 0)

    import numpy as np
    engine = fallback_voice()
    if args.say:
        synth = fallback_synth(spoken)
    else:
        try:
            synth, engine = kokoro_synth(spoken, voice, speed), f'kokoro:{voice}'
        except Exception as ex:
            if not args.allow_fallback:
                log(f'Kokoro failed: {ex!r}\nRerun with --allow-fallback to use the system voice ({fallback_voice() or "none installed"}).')
                print(json.dumps({'ok': False, 'error': f'kokoro failed: {ex}'})); sys.exit(3)
            log(f'Kokoro failed ({ex!r}); using the system voice')
            synth = fallback_synth(spoken)

    placed, errors = place_cues(scene, spoken, [w for _, w in synth], lex)
    if errors:
        log('cue errors:\n' + '\n'.join(errors))
        print(json.dumps({'ok': False, 'error': 'cue errors', 'errors': errors})); sys.exit(2)
    gap = np.zeros(int(GAP_S * SR), np.float32)
    chunks, t, steps = [], 0.0, []
    for i, (s, (clip, words)) in enumerate(zip(scene['steps'], synth)):
        cues = [{'t': round(t + words[j][1], 3), 'focus': c.get('focus', []),
                 'edges': lit_keys(c), 'item': c.get('item'), 'carry': c.get('carry')}
                for c, j in placed[i]]
        steps.append({'t': round(t, 3), 'caption': s.get('caption') or s['say'],
                      'focus': s.get('focus', []), 'edges': lit_keys(s),
                      'cues': cues, 'ask': s.get('ask'), 'src': srcs[i], 'item': s.get('item'), 'carry': s.get('carry')})
        chunks += [clip, gap]; t += (len(clip) + len(gap)) / SR
    mime, data = encode(np.concatenate(chunks))

    meta = {'version': VERSION, 'seconds': round(t, 2), 'engine': engine, 'built': datetime.date.today().isoformat(),
            'sha': git_sha(scene), 'repo': os.path.basename(os.path.expanduser(scene['repo'])) if scene.get('repo') else None}
    labels = [n['label'] for n in scene['nodes']]
    vals = {
        'TITLE': html.escape(scene['title']),
        'LEAD': html.escape(scene.get('lead', '')),
        'SVGDESK': svg_desk, 'SVGPHONE': svg_phone,
        # the stage may grow past the text column to show the desktop diagram at full size (canvas padding + border = 34 px)
        'STAGEW': str(round(float(re.search(r'viewBox="\S+ \S+ (\S+)', svg_desk).group(1)) + 34)),
        'DATA': json.dumps({'steps': steps, 'meta': meta, 'labels': labels, 'title': scene['title'],
                            'lead': scene.get('lead', ''), 'colors': D.node_colors(scene), 'legend': scene.get('legend', [])},
                           ensure_ascii=False).replace('<', '\\u003c'),
        'MIME': mime, 'AUDIO': base64.b64encode(data).decode(),
        'DIAGRAMCSS': D.diagram_css(theme), 'THEME': theme,
    }
    page = re.sub(r'__(TITLE|LEAD|SVGDESK|SVGPHONE|DATA|MIME|AUDIO|STAGEW|DIAGRAMCSS|THEME)__', lambda m: vals[m.group(1)],
                  open(os.path.join(SKILL_DIR, 'page.html')).read())
    out = args.out or os.path.splitext(args.scene)[0] + '.html'
    open(out, 'w').write(page)
    for wmsg in warnings:
        log('warning:', wmsg)
    print(json.dumps({'ok': True, 'out': out, 'engine': engine, 'seconds': round(t, 1), 'steps': len(steps),
                      'cues': sum(len(s['cues']) for s in steps), 'kb': len(page) // 1024, 'warnings': warnings}))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as ex:  # every failure still prints one JSON line
        import traceback
        traceback.print_exc()
        print(json.dumps({'ok': False, 'error': f'{type(ex).__name__}: {ex}'}))
        sys.exit(1)
