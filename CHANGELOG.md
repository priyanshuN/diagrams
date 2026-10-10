# Changelog

Installed copies update only when the version in `.claude-plugin/plugin.json` goes up. See "Releases" in the README.

## 0.1.0 (2026-10-11)

First versioned release.

- `flow`: Mermaid to Unicode text for chat (`fd`), to sketch or clean picture pages (`pic`), and `fd --lint` for hand-drawn text diagrams. Small chat diagrams are drawn by hand and linted; `fd` checks its own output and falls back from a misrouted left-to-right layout to top-to-bottom.
- `flow`: sequence text uses dotted lines for async messages and one row less per message.
- `walkthrough`: narrated diagram pages with word-timed cues and a recall quiz. The Kokoro voice runs on MLX on Apple silicon and on CPU PyTorch elsewhere; audio goes through `afconvert` or `ffmpeg`.
- The README lists everything the plugin runs and downloads. The plugin sends no data anywhere.
