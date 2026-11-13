# diagrams

A Claude Code plugin for diagrams that explain. It has four skills, and the question picks the skill:

| The reader asks | Skill | Output |
|---|---|---|
| What talks to what? In what order? | `diagrams:flow` | text in chat, or a picture page |
| Walk me through this flow | `diagrams:walkthrough` | the picture with a voice, cues and a quiz |
| What did this run do? What changed between two runs? | `diagrams:trace` | a sequence diagram of a recorded run, or a diff of two |
| How does this idea behave? Why this number? | `diagrams:concept` | an interactive page: a picture, its controls, one result line |

One Mermaid source gives chat text, a picture page and a walkthrough. A trace and a concept page have their own small sources:

```
Mermaid ─┬─► diagrams:flow ─────────► Unicode text in chat (terminal + desktop app)
         │                  └───────► picture page: clean (default) or sketch
         └─► diagrams:walkthrough ──► picture + local voice, word-timed cues, recall quiz

trace file(s) ─► diagrams:trace ──► Mermaid sequence (one run, or two runs with changes marked)
idea.concept.html ─► diagrams:concept ─► interactive page, checked by a page self-test
```

All pages share one look, a warm off-white panel with thin lines and muted colours: `skills/flow/tokens.css` holds the greys, the accent and the meaning colours.

## Install (each machine, once)

```text
/plugin marketplace add priyanshuN/diagrams
/plugin install diagrams@diagrams
```

Claude Code installs the Node libraries from `package.json` by itself.

To get new releases without running a command, turn on auto-update: `/plugin` → Marketplaces → diagrams → Enable auto-update. To update by hand, run `claude plugin update diagrams@diagrams` and then `/reload-plugins`.

## Example

`skills/flow/examples/` has one checkout, drawn both ways: `checkout.flow.mmd` (what talks to what) and `checkout.seq.mmd` (who calls whom, in order). Render the chat text with `skills/flow/fd <file>` and the picture with `skills/flow/pic <file> --look checkout.look.json -o out.html`.

`skills/concept/examples/` has two concept pages with different shapes: `stride.concept.html` (a ring: why a golden-ratio stride spreads Kafka messages) and `backoff.concept.html` (lanes on a time axis: retry backoff with and without jitter). Build one with `skills/concept/cx <file>`.

The concept skill has no picture types. It holds rules (the control the real system has, a baseline next to the idea, one plain result line), a page shell, a few drawing helpers and a self-test; Claude draws the shape each idea needs.

## Requirements

| Skill | Needs | Linux |
|---|---|---|
| `flow` | Node 18+, `uv` (it fetches Python 3.12 by itself) | yes |
| `walkthrough` | the above; `ffmpeg` on Linux for compact audio | yes |
| `trace` | Node 18+ (and the `flow` libraries for `--text`) | yes |
| `concept` | Node 18+ | yes |

Both skills run on uv's Python 3.12, so no system Python upgrade is needed on either machine. Without `uv`, the flow picture tool falls back to `python3` (3.9+).

The walkthrough voice is Kokoro-82M on every machine: MLX on Apple silicon, PyTorch (CPU-only wheels) on Linux and Intel Macs. Its environment lives in `~/.local/share/narrated-walkthrough/venv` (about 1.2 GB on Linux, mostly PyTorch). The first build downloads the Kokoro model (about 340 MB). Audio is AAC through `afconvert` on macOS or `ffmpeg` elsewhere; without either, the page holds WAV and is about ten times bigger.

## What it runs and fetches

Everything runs on your machine. The plugin sends no data anywhere: no telemetry, no API calls, no uploads.

| When | What runs or downloads | From |
|---|---|---|
| Plugin install | the Node packages in `package-lock.json`: beautiful-mermaid, libavoid-js (includes a WebAssembly router), roughjs, @fontsource/architects-daughter | the npm registry |
| `flow` | `node` scripts (`fd.mjs`, `avoid_route.mjs`, `rough.mjs`) and `python` (`diagram.py`, standard library only); they read your diagram file and write the page or text you ask for | nothing |
| `concept` | one `node` script (`cx.mjs`, standard library only); it reads your source file and writes one page | nothing |
| First `walkthrough` build | `uv run --frozen` creates a Python environment in `~/.local/share/narrated-walkthrough/venv` from `uv.lock` (on Linux, CPU-only PyTorch from download.pytorch.org) | PyPI, download.pytorch.org |
| First `walkthrough` build | the Kokoro-82M voice model (about 340 MB), cached in `~/.cache/huggingface` | huggingface.co |
| First `walkthrough` build | the English text-to-phoneme model that the misaki library loads, if it is not installed yet | the misaki/spaCy defaults |
| Each `walkthrough` build | `afconvert` (macOS) or `ffmpeg` (elsewhere) to compress the audio | nothing |

The pages the skills write are single, self-contained HTML files: fonts and scripts are inlined, and nothing loads from a CDN.

## Developing

Edit here, test with the scripts in place (`skills/flow/fd`, `skills/walkthrough/nw`, `skills/concept/cx`), then push. `.claude/launch.json` serves the repo on localhost:8765 so the browser pane can open the example pages. Validate with `claude plugin validate .`.

### Releases

Installed copies update only when `version` in `.claude-plugin/plugin.json` goes up. A push without a version bump reaches nobody, so work in progress stays on the branch.

1. Raise `version`: the third number for a fix (0.1.0 → 0.1.1), the second for a new feature (0.1.1 → 0.2.0).
2. Add a line for the version at the top of `CHANGELOG.md`.
3. Commit, push, and tag the commit `vX.Y.Z`.
4. On each machine: `claude plugin marketplace update skills`, then `claude plugin update diagrams@skills`, then restart Claude Code. The plugin is listed in the `skills` marketplace (priyanshuN/skills). With auto-update on, Claude Code does this at start-up.

## Ideas and bugs

Open an issue: ideas carry the `enhancement` label, bugs the `bug` label. An idea worth doing gets a short design note in its issue before any code.

## Licence

MIT, see `LICENSE`. Libraries: beautiful-mermaid (MIT), libavoid-js (LGPL-2.1, used unmodified at build time), roughjs (MIT), Architects Daughter font (OFL-1.1, see `skills/flow/FONT-LICENSE`).
