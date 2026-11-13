# Changelog

Installed copies update only when the version in `.claude-plugin/plugin.json` goes up. See "Releases" in the README.

## 0.6.0 (2026-11-13)

- Walkthrough: a second view, "Item story". The same scene is drawn as one record that changes: the boxes become a line of stops, the `item` is a large card, a field a step adds is marked "new", and a changed value shows the old value struck out. It needs no new scene fields and is offered when any step has an `item`. A switch changes between "Diagram" and "Item story" while the voice goes on.
- Walkthrough: "What if…" scenarios (`whatif`, 1 to 4, flows only). The viewer picks a failure and the same diagram replays with the broken part in red, a cross on a broken arrow, and the boxes the run never reaches drawn faint. Each scenario is its own voice clip after the main walk; the main walk stops before them.
- Walkthrough: the build passes the two ends of every arrow and message to the page, so the item story has a stop for every box an arrow touches, in a sequence too.
- Concept: a narrated page. A `narration` block in the source gives the page a voice (the walkthrough voice). The voice reads short beats, and on the spoken word the page presses its own buttons and moves its own sliders, puts a ring around the part it talks about, and lights the caption word by word. A viewer who touches a control takes over; "Resume" puts the story state back. The page self-test plays the story without sound and checks every state it makes. New files: `skills/concept/narrate.{js,css,html}` and `skills/walkthrough/voice.py`.
- Concept: checked captions. A beat's `expect` lists what the page must show when the beat ends (words in an element, or a count of elements), and the page self-test fails when the page differs. The build warns about a number in a caption that no `expect` of the beat has. `window.__cx.story()` lists the text each beat changes, so captions are written from the page.
- Voice cache: each spoken line is kept in `~/.cache/narrated-walkthrough/lines`, so a walkthrough or narrated concept build speaks only the lines that changed. A rebuild with no changed line takes under a second (before: 10 to 60 seconds). `--no-cache` turns it off.
- Flow pictures: an arrow label now stays off other arrows. It tries the middle of its arrow, then a third from each end, and takes the first spot clear of boxes, labels and other arrows. Two arrows between the same two boxes (a request and its reply, a delivery and its retry) can now both have a label; before, the second label had "no clear spot". A label that already had a clear spot does not move.
- Flow pictures: a box can hold `notes`, 1 to 8 detail lines under its name (the fields of a table, the settings of a queue). The box and its row grow to fit. A picture with more than 8 boxes uses two columns on a phone, and a phone picture never shrinks below a readable size: a picture wider than the screen scrolls sideways, as a sequence already did. The walkthrough self-test now measures the detail lines too (`detailPx`). The walkthrough guide now tells Claude how to draw a design picture (an HLD) at full detail instead of a small happy-path flow.
- Walkthrough: the page remembers the chosen view (Diagram or Item story) for each page, not for every page on the same site.

## 0.5.0 (2026-11-13)

- Walkthrough: a camera follows the voice. The frame moves to the boxes a step or cue names (never closer than 1.2 times the drawn size, never farther than 0.75 times), a box or arrow appears when the voice first names it, and a box cut by the frame fades out. The overview and "Test me" show the whole diagram. A "Follow the voice" switch turns the camera off.
- Walkthrough on a phone: the stage is a square that stays on screen with the caption under it, in place of one tall column that pushed the caption off screen.
- Walkthrough of a sequence: a message appears when a step first lights it. A sequence too large to read whole gets a frame around the lit message, with the participants' names pinned at the top.
- Walkthrough: the caption lights word by word while the voice plays, and a box's name in the caption takes the box's colour. Paused, the whole caption stays readable.
- Walkthrough: three optional scene fields. `title` is a step's headline, shown above the caption and in the step list. `state` replaces a box's second line with what the box holds now, when the data lands. `recap` is 2 to 4 points spoken at the end over the whole diagram.
- Walkthrough: the build warns about a box that no step names. The page self-test reports the label size in the camera frames and a `state` text wider than its box. Image export always gives the whole diagram.

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
