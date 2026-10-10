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

`skills/flow/examples/` has one checkout, drawn both ways: `checkout.flow.mmd` (what talks to what) and `checkout.seq.mmd` (who calls whom, in order). Render the chat text with `skills/flow/fd <file>` and the picture with `skills/flow/pic <file> --look checkout.look.json -o out.html`.

## Requirements

| Skill | Needs | Linux |
|---|---|---|
| `flow` | Node 18+, `uv` (it fetches Python 3.12 by itself) | yes |
| `walkthrough` | the above; `ffmpeg` on Linux for compact audio | yes |

Both skills run on uv's Python 3.12, so no system Python upgrade is needed on either machine. Without `uv`, the flow picture tool falls back to `python3` (3.9+).

The walkthrough voice is Kokoro-82M on every machine: MLX on Apple silicon, PyTorch (CPU-only wheels) on Linux and Intel Macs. Its environment lives in `~/.local/share/narrated-walkthrough/venv` (about 1.2 GB on Linux, mostly PyTorch). The first build downloads the Kokoro model (about 340 MB). Audio is AAC through `afconvert` on macOS or `ffmpeg` elsewhere; without either, the page holds WAV and is about ten times bigger.

## Developing

Edit here, test with the scripts in place (`skills/flow/fd`, `skills/walkthrough/nw`), then push. Validate with `claude plugin validate .`. There is no `version` field on purpose, so every pushed commit reaches every machine.

## Licence

MIT, see `LICENSE`. Libraries: beautiful-mermaid (MIT), libavoid-js (LGPL-2.1, used unmodified at build time), roughjs (MIT), Architects Daughter font (OFL-1.1, see `skills/flow/FONT-LICENSE`).
