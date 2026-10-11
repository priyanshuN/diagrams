# diagrams

A Claude Code plugin for flow and sequence diagrams. One Mermaid source gives three outputs:

```
Mermaid ─┬─► diagrams:flow ─────────► Unicode text in chat (terminal + desktop app)
         │                  └───────► picture page: clean (default) or sketch
         └─► diagrams:walkthrough ──► picture + local voice, word-timed cues, recall quiz

trace file(s) ─► diagrams:trace ──► Mermaid sequence (one run, or two runs with changes marked)
```

## Install (each machine, once)

```text
/plugin marketplace add priyanshuN/diagrams
/plugin install diagrams@diagrams
```

Claude Code installs the Node libraries from `package.json` by itself.

To get new releases without running a command, turn on auto-update: `/plugin` → Marketplaces → diagrams → Enable auto-update. To update by hand, run `claude plugin update diagrams@diagrams` and then `/reload-plugins`.

## Example

`skills/flow/examples/` has one checkout, drawn both ways: `checkout.flow.mmd` (what talks to what) and `checkout.seq.mmd` (who calls whom, in order). Render the chat text with `skills/flow/fd <file>` and the picture with `skills/flow/pic <file> --look checkout.look.json -o out.html`.

## Requirements

| Skill | Needs | Linux |
|---|---|---|
| `flow` | Node 18+, `uv` (it fetches Python 3.12 by itself) | yes |
| `walkthrough` | the above; `ffmpeg` on Linux for compact audio | yes |
| `trace` | Node 18+ (and the `flow` libraries for `--text`) | yes |

Both skills run on uv's Python 3.12, so no system Python upgrade is needed on either machine. Without `uv`, the flow picture tool falls back to `python3` (3.9+).

The walkthrough voice is Kokoro-82M on every machine: MLX on Apple silicon, PyTorch (CPU-only wheels) on Linux and Intel Macs. Its environment lives in `~/.local/share/narrated-walkthrough/venv` (about 1.2 GB on Linux, mostly PyTorch). The first build downloads the Kokoro model (about 340 MB). Audio is AAC through `afconvert` on macOS or `ffmpeg` elsewhere; without either, the page holds WAV and is about ten times bigger.

## What it runs and fetches

Everything runs on your machine. The plugin sends no data anywhere: no telemetry, no API calls, no uploads.

| When | What runs or downloads | From |
|---|---|---|
| Plugin install | the Node packages in `package-lock.json`: beautiful-mermaid, libavoid-js (includes a WebAssembly router), roughjs, @fontsource/architects-daughter | the npm registry |
| `flow` | `node` scripts (`fd.mjs`, `avoid_route.mjs`, `rough.mjs`) and `python` (`diagram.py`, standard library only); they read your diagram file and write the page or text you ask for | nothing |
| First `walkthrough` build | `uv run --frozen` creates a Python environment in `~/.local/share/narrated-walkthrough/venv` from `uv.lock` (on Linux, CPU-only PyTorch from download.pytorch.org) | PyPI, download.pytorch.org |
| First `walkthrough` build | the Kokoro-82M voice model (about 340 MB), cached in `~/.cache/huggingface` | huggingface.co |
| First `walkthrough` build | the English text-to-phoneme model that the misaki library loads, if it is not installed yet | the misaki/spaCy defaults |
| Each `walkthrough` build | `afconvert` (macOS) or `ffmpeg` (elsewhere) to compress the audio | nothing |

The pages the skills write are single, self-contained HTML files: fonts and scripts are inlined, and nothing loads from a CDN.

## Developing

Edit here, test with the scripts in place (`skills/flow/fd`, `skills/walkthrough/nw`), then push. Validate with `claude plugin validate .`.

### Releases

Installed copies update only when `version` in `.claude-plugin/plugin.json` goes up. A push without a version bump reaches nobody, so work in progress stays on the branch.

1. Raise `version`: the third number for a fix (0.1.0 → 0.1.1), the second for a new feature (0.1.1 → 0.2.0).
2. Add a line for the version at the top of `CHANGELOG.md`.
3. Commit, push, and tag the commit `vX.Y.Z`.
4. On each machine: `claude plugin marketplace update diagrams`, then `claude plugin update diagrams@diagrams`, then restart Claude Code. With auto-update on, Claude Code does this at start-up.

## Licence

MIT, see `LICENSE`. Libraries: beautiful-mermaid (MIT), libavoid-js (LGPL-2.1, used unmodified at build time), roughjs (MIT), Architects Daughter font (OFL-1.1, see `skills/flow/FONT-LICENSE`).
