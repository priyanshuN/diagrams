# diagrams

A Claude Code plugin for flow and sequence diagrams. One Mermaid source gives three outputs:

```
Mermaid ─┬─► diagrams:flow ─────────► Unicode text in chat (terminal + desktop app)
         │                  └───────► picture page: sketch (default) or clean
         └─► diagrams:walkthrough ──► picture + local voice, word-timed cues, recall quiz
```

## Install (each machine, once)

```text
/plugin marketplace add priyanshuN/diagrams
/plugin install diagrams@diagrams
```

Claude Code installs the Node libraries from `package.json` by itself.

To get pushes without running a command, turn on auto-update: `/plugin` → Marketplaces → diagrams → Enable auto-update. To update by hand, run `claude plugin update diagrams@diagrams` and then `/reload-plugins`.

## Example

`skills/flow/examples/` has one checkout, drawn both ways: `checkout.flow.mmd` (what talks to what) and `checkout.seq.mmd` (who calls whom, in order). Render the chat text with `skills/flow/fd <file>` and the picture with `python3 skills/flow/diagram.py <file> --look checkout.look.json -o out.html`.

## Requirements

| Skill | Needs | Linux |
|---|---|---|
| `flow` | Node 18+, Python 3.9+ | yes |
| `walkthrough` | the above, plus `uv`; the voice is Kokoro via MLX (Apple silicon) and `afconvert` (macOS) | everything except the voice |

The walkthrough voice environment lives in `~/.local/share/narrated-walkthrough/venv`. The first build downloads the Kokoro model (about 340 MB).

## Developing

Edit here, test with the scripts in place (`skills/flow/fd`, `skills/walkthrough/nw`), then push. Validate with `claude plugin validate .`. There is no `version` field on purpose, so every pushed commit reaches every machine.

## Licence

MIT, see `LICENSE`. Libraries: beautiful-mermaid (MIT), libavoid-js (LGPL-2.1, used unmodified at build time), roughjs (MIT), Architects Daughter font (OFL-1.1, see `skills/flow/FONT-LICENSE`).
