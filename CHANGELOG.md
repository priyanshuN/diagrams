# Changelog

Installed copies update only when the version in `.claude-plugin/plugin.json` goes up. See "Releases" in the README.

## 0.4.0 (2026-11-13)

- New default colours for every page (flow pictures, walkthroughs, concept pages): a warm off-white panel on a slightly darker warm page, warm-grey lines and muted meaning colours, with a matching warm dark mode. Only `skills/flow/tokens.css` changed; `--theme sketch` keeps its own paper colours.
- Concept pages: a fixed figure frame. `.frame` holds a side column with `.readout` (the one live number, and the rule) and a "How to read it" `.legend`, next to the cards. `.dot.hollow` and `.dot.line` are new legend marks. The stride example uses the frame; pages without a frame still build.

## 0.3.0 (2026-11-12)

- New skill `concept`: an interactive page that shows how an idea behaves (an algorithm, a number, a policy). It has no picture types: the skill gives rules, a page shell, drawing helpers (`kit`), a build (`cx`) and a page self-test (`window.__cx.selftest()`), and Claude draws the shape the idea has. Two examples: a golden-ratio stride on a ring of Kafka partitions, and retry backoff with jitter on a time axis.
- Clean theme: thinner lines (1 to 1.4 px), open arrowheads, lighter fills and 12 px arrow labels, so flow pictures, walkthroughs and concept pages share one look. The text weight rule of 0.2.0 stays.
- Colours moved to `skills/flow/tokens.css`, shared by flow pictures, walkthroughs and concept pages. The page greys are neutral; `--warn` is new.
- `flow` and `walkthrough` now send "how does this idea behave" questions to `concept`.

## 0.2.1 (2026-10-11)

- README: the update commands name the `skills` marketplace, where the plugin is now listed.
- Readability: unlit box names and arrow labels use the muted ink instead of the faint one (about 6:1 contrast on white instead of 3:1); unchanged steps in a `trace` diff fade to 55% instead of 38%.
- Walkthrough build: `node --check` runs on the page script before any audio is made, so a script error fails the build (`ok: false`, with the line) instead of shipping a page whose controls do nothing.

## 0.2.0 (2026-10-11)

- New skill `trace`: a recorded run (a trace file of steps with values) becomes a sequence diagram, and two runs become a diff with `[+]` added, `[-]` removed and `[~]` changed steps. Steps match on caller, callee and label; values that change every run (ids, times) are left out with `ignore`. Exit code 0 when the runs match and 1 when they differ. Renders through `flow` (`--text`) or as Mermaid for `pic`.
- Picture pages and walkthroughs now default to the clean theme; `--theme sketch` (or `"theme": "sketch"` in a scene) keeps the hand-drawn look.
- Clean theme: one text weight everywhere (title, box names, labels, step numbers). Bold only held text against the sketch lines; colour carries emphasis.
- Walkthrough: the page opens on an overview, the whole diagram at full strength with no step lit; play, a step or the arrow keys start the walk at step 1. A link with `#n` still opens at step n. Back to the overview: the Overview button, Esc, ← or the previous-step button from step 1, or the end of the narration.
- Walkthrough: a mute button in the player (and the M key). Mute lasts for the visit only, so a page never opens silent.
- Walkthrough: "Pause to predict" starts off (a viewer's own choice is still remembered). New "Copy image" and "Download image" buttons export the diagram as it looks at the current step, as a 2× PNG with the page's styles and font (an SVG file if the browser will not draw a PNG).
- Sequence pictures colour the diff marks from `trace`: `[+]` green, `[-]` red and dashed, `[~]` amber; unchanged steps fade.

## 0.1.1 (2026-10-11)

- Sketch theme: darker, easier text. Box names get a thin ink outline that thickens the hand-drawn letters; arrow labels are 1 px larger and keep their paper outline, so a line never runs through them. Hatching is lighter (light mode 16% → 10%, dark mode 24% → 16% at rest). All text stays sharp vector text.
- Walkthrough: phone-layout warnings suggest a fix that works, and the page self-test catches arrows that run side by side.

## 0.1.0 (2026-10-11)

First versioned release.

- `flow`: Mermaid to Unicode text for chat (`fd`), to sketch or clean picture pages (`pic`), and `fd --lint` for hand-drawn text diagrams. Small chat diagrams are drawn by hand and linted; `fd` checks its own output and falls back from a misrouted left-to-right layout to top-to-bottom.
- `flow`: sequence text uses dotted lines for async messages and one row less per message.
- `walkthrough`: narrated diagram pages with word-timed cues and a recall quiz. The Kokoro voice runs on MLX on Apple silicon and on CPU PyTorch elsewhere; audio goes through `afconvert` or `ffmpeg`.
- The README lists everything the plugin runs and downloads. The plugin sends no data anywhere.
