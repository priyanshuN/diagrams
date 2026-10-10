---
name: flow
description: Draw a flow diagram (what talks to what) or a sequence diagram (who calls whom, in what order, who waits) from Mermaid. Renders Unicode box art to paste inline in a chat reply (terminal and desktop app), or a clean/sketch-style picture page. Use when a reply needs a diagram bigger than a few boxes, when the user asks for a flow or sequence diagram, or before building a narrated walkthrough (diagrams:walkthrough reads the same Mermaid).
---

# Flow and sequence diagrams

One Mermaid source, three outputs. The `diagrams:walkthrough` skill is the top layer and reads the same Mermaid.

```
Mermaid ─┬─► fd file.mmd ─────────► Unicode text in a ```text fence (chat)
         ├─► diagram.py file.mmd ─► picture page: sketch (default) or clean
         └─► walkthrough skill ──► picture + voice, cues, quiz
```

## Pick the diagram type by the question

| The reader asks | Draw | Mermaid header |
|---|---|---|
| What are the parts, and what flows between them? | flow | `graph TD` |
| In what order do calls happen? Who waits for whom? When does the reply go back? | sequence | `sequenceDiagram` |
| Both (a new system, an incident) | flow first, then the sequence of the one path that matters | both |

A sequence shows what a flow hides. Example: at checkout the shop tells the customer "processing" *before* the payment provider confirms; the confirmation arrives later by webhook. A flow diagram cannot show that ordering.

## 1. Chat text (works everywhere)

```bash
"${CLAUDE_SKILL_DIR}/fd" diagram.mmd
```

- Paste stdout into a ```` ```text ```` fence. It is plain Unicode, so it reads the same in the terminal and in the desktop app. Never paste raw Mermaid into chat: neither surface renders it.
- stderr reports the size (`fd: 43 cols x 37 rows`) and notes. Keep chat text within 90 columns and about 45 rows. If a note says it is too big, shorten labels, split the diagram, or make a picture instead.
- Use `graph TD` for chat. `fd` switches a too-wide `LR` flow to `TD` by itself, because left-to-right text gets wide and misroutes arrows.
- In a sequence, write branches as a `Note over X: ...`. `alt`/`opt`/`loop` blocks render badly as text, and `fd` warns about them.
- Chat text is single-colour by nature. Shapes carry meaning: `[( )]` store (rounded), `{ }` decision (◇), `-.->` async (dotted).
- `fd file --ascii` gives plain + - | > for limited terminals. `fd file --json` prints the parsed diagram.

## 2. Picture page (clean or sketch)

```bash
python3 "${CLAUDE_SKILL_DIR}/diagram.py" diagram.mmd --look look.json --title "Checkout" -o out.html
```

- **Sketch is the default**: hand-drawn boxes and arrows (rough.js) on graph paper, with the Architects Daughter font. `--theme clean` gives crisp lines for dense or precise diagrams.
- Colour means the same in both themes. The fill says who runs a box; the outline and labels stay dark ink so text always wins.
- Arrows are routed by libavoid. They never cross a box, and each one gets its own attachment point.
- Prints one JSON line `{"ok", "out", "warnings"}`. Read the warnings. "Wider than tall" means: give `at` positions in the look, or use `graph TD`.
- To show the page, serve its folder on localhost (a launch.json preview entry, or `python3 -m http.server`) and open it in the browser pane, which cannot open `file://` URLs. Look at it before you hand it over.

### The look file: what Mermaid cannot say

```json
{
  "customer": {"kind": "external", "color": "slate", "at": [0, 0]},
  "provider": {"color": "sky"},
  "decide>orders": {"tone": "good"},
  "legend": [{"color": "slate", "label": "Outside your system"}, {"color": "sky", "label": "Payment provider"}]
}
```

- **Node id** keys: `at` [col, row] (give it for every node or none; without it, nodes are placed in layers along the arrows), `color`, `kind` (`service`, `external` = dashed, `store`, `decision`), `sub`, `label`.
- **Subgraph id** keys: `color`.
- **`from>to`** keys: `tone` (`good`, `warn` or `bad`) on the arrows that leave a decision.
- **Colours mean something**, never decoration: slate = outside your system (people, their devices, third parties), sky = cloud or vendor services, emerald = your app (the default), amber = waits for a person, rose = failure. Add a `legend` whenever more than one colour appears.

### Mermaid rules that matter here

- Define each node with its label (`pay[Payment API]`) **before** the first arrow that uses it. The parser keeps a node's first mention, so `shop --> pay` first leaves the label as "pay". `fd` stops with an error when this happens.
- A second label line is the sub-label: `shop[Shop API<br/>order service]`.
- Shapes: `[ ]` service, `[( )]` store, `{ }` decision. Arrows: `-->` sync, `-.->` async, `-->|label|` labelled.
- Sequence arrows: `->>` call, `-->>` reply (dashed), `-)` async. Messages are numbered 1, 2, 3… in order. The walkthrough lights them by number.

## Setup and limits

- Needs Node 18+ and Python 3.9+. Libraries come from the plugin's `package.json`; Claude Code installs them on plugin install and update. In a loose copy, run `npm ci` where `package.json` is: beautiful-mermaid (MIT) for text and parsing, libavoid-js (LGPL) for arrows, roughjs (MIT) for the sketch, and @fontsource/architects-daughter (OFL). All run at build time; nothing loads from a CDN.
- If roughjs or libavoid is missing, the picture falls back (clean theme, simple curves) with a warning.
- The examples are in `examples/`: `checkout.flow.mmd` (+ `checkout.look.json`) and `checkout.seq.mmd`.
