# Changelog

Installed copies update only when the version in `.claude-plugin/plugin.json` goes up. See "Releases" in the README.

## 0.2.0 (2026-10-11)

- New skill `trace`: a recorded run (a trace file of steps with values) becomes a sequence diagram, and two runs become a diff with `[+]` added, `[-]` removed and `[~]` changed steps. Steps match on caller, callee and label; values that change every run (ids, times) are left out with `ignore`. Exit code 0 when the runs match and 1 when they differ. Renders through `flow` (`--text`) or as Mermaid for `pic`.

## 0.1.1 (2026-10-11)

- Sketch theme: darker, easier text. Box names get a thin ink outline that thickens the hand-drawn letters; arrow labels are 1 px larger and keep their paper outline, so a line never runs through them. Hatching is lighter (light mode 16% → 10%, dark mode 24% → 16% at rest). All text stays sharp vector text.
- Walkthrough: phone-layout warnings suggest a fix that works, and the page self-test catches arrows that run side by side.

## 0.1.0 (2026-10-11)

First versioned release.

- `flow`: Mermaid to Unicode text for chat (`fd`), to sketch or clean picture pages (`pic`), and `fd --lint` for hand-drawn text diagrams. Small chat diagrams are drawn by hand and linted; `fd` checks its own output and falls back from a misrouted left-to-right layout to top-to-bottom.
- `flow`: sequence text uses dotted lines for async messages and one row less per message.
- `walkthrough`: narrated diagram pages with word-timed cues and a recall quiz. The Kokoro voice runs on MLX on Apple silicon and on CPU PyTorch elsewhere; audio goes through `afconvert` or `ffmpeg`.
- The README lists everything the plugin runs and downloads. The plugin sends no data anywhere.
