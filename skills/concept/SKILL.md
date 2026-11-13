---
name: concept
description: Draw an interactive picture page that shows how an idea behaves - an algorithm, a number, a data structure or a policy (hashing, modulo and round robin, a golden-ratio stride, backoff and jitter, rate limits, quorum, cache eviction, consistent hashing). You draw the shape the idea has (a ring, a number line, lanes on a time axis, buckets, a grid) with the control the real system has, a baseline next to it, and one plain result line. Use when the reader asks "how does X work", "why this number", "what happens if I change X", or "explain X" and the answer is not a set of boxes and arrows. For what talks to what, or who calls whom in what order, use diagrams:flow.
---

# Concept pictures

A flow diagram answers "what talks to what". It cannot answer "why does a stride of 7 spread messages better than a stride of 1". That answer is a shape and a number that the reader can change. This skill makes one page for one idea: a picture, its controls, and the result in one line.

```
idea ─► name the mechanism ─► pick its shape ─► write idea.concept.html
                                                       │
            self-test in the browser pane ◄── cx build ┘   (one offline page)
```

## First: is it a concept picture?

| The reader asks | Draw | Skill |
|---|---|---|
| What are the parts, and what flows between them? | flow | diagrams:flow |
| In what order do calls happen? Who waits? | sequence | diagrams:flow |
| How does this idea behave? Why this number? What happens if I change it? | concept page | this skill |
| Both (a new system and the algorithm inside it) | the flow first, then a concept page for the one idea that is hard | both |

A reply in chat still starts with the answer in one line and one small worked example with real numbers. The page is where the reader goes to try the idea.

## 1. Plan the picture before you write it

Write these six lines for yourself. If you cannot fill a line, read the code or ask; do not start to draw.

1. **Mechanism:** one sentence with the formula. "Each message goes to partition `(n × stride) % N`."
2. **Shape:** the geometry the mechanism already has (see the table). The picture must still make sense with every label removed.
3. **Controls:** the settings the real system has (partition count, stride, clients, first wait), and an action that moves time one step ("Send 1 message", "Send burst of 4", "Play").
4. **Baseline:** the simple method the idea replaces, drawn next to it with the same inputs. One card per method.
5. **Consequence:** the count the reader cares about (load per consumer, retries in one time slice), and one result line that changes as the controls move.
6. **Failure case:** a setting, reachable with the controls, where the idea breaks (a stride that shares a factor with the partition count). The result line must say why it breaks.

### Shapes are a starting list, not a set of types

| The idea is about | Shape that usually fits | Examples |
|---|---|---|
| Wrapping, modulo, taking turns | ring | round robin, stride, consistent hashing, a ring buffer |
| Ranges, thresholds, windows | number line | percentiles, rate-limit windows, bucket boundaries |
| Many actors over time | lanes on a time axis | backoff and jitter, races, lock waits, heartbeats |
| Spreading items into slots | row of buckets | hashing, sharding, load factor |
| State per cell | grid | a bloom filter, a matrix, a cache with ways |
| A level that fills and drains | tank or gauge | a token bucket, queue depth, a connection pool |
| Growth or decay | curve with a moving point | exponential backoff, a TTL, compounding |
| Parent and child | tree | a B-tree split, a heap, a trie |
| Order of arrival and removal | stack or queue | LRU eviction, a call stack |

There is no code per shape, and you must not add one. If the idea has a geometry that is not in the table, draw that geometry. `kit` gives a few helpers for the parts that are easy to get wrong (ring angles, arrows that stop at a shape's edge, bars, a repeatable random source); everything else is plain SVG that your script writes.

## 2. Write the source

One file, named `<idea>.concept.html`, in a working folder (not inside the plugin). It is a header, then HTML, then one script.

```html
<!--concept
title: Golden stride on a ring of Kafka partitions
lead: Each message takes the next Redis counter value n. The left ring steps one partition at a time. The right ring jumps by the stride.
-->
<div class="controls">
  <label>Partitions <input type="range" id="parts" min="8" max="24" step="1" value="12"><span class="val" id="partsVal">12</span></label>
  <button id="four">Send burst of 4</button>
</div>
<div class="frame">
  <aside class="side">
    <div>
      <div class="readout"><b id="msg">Message 4</b><span>the Redis counter value n</span></div>
      <div class="readout minor"><b id="rule">(n × 7) % 12</b><span>picks the partition for message n</span></div>
    </div>
    <div class="legend">
      <h3>How to read it</h3>
      <span class="chip"><span class="dot hollow"></span>Green ring: one of the last 4 messages</span>
      <span class="chip c-sky"><span class="dot line"></span>Outer arc: the partitions of one consumer</span>
    </div>
  </aside>
  <div class="grid">
    <section class="card" id="plain"></section>
    <section class="card" id="jump"></section>
  </div>
</div>
<script>
const { el, polar, arc, arrow, defs, bars, bind } = kit
function draw() { /* compute, then set each card's innerHTML: h2, .formula, svg.pic, .row, .verdict, bars */ }
bind(['parts'], c => { N = +c.value; draw() })
draw()
</script>
```

- **Header:** one key per line, and the value is the rest of the line (a colon inside the value is fine). `title` and `lead` are required; the page shell prints them, so the body has no `<h1>`. `static: true` is for the rare picture with nothing to change.
- **Read both examples before you write your first page:** `${CLAUDE_SKILL_DIR}/examples/stride.concept.html` (a ring) and `${CLAUDE_SKILL_DIR}/examples/backoff.concept.html` (lanes on a time axis). Read only these two source files, not any built page next to them. Copy their structure, not their shape.
- **One `draw()` function** reads the state and rebuilds every card. Each control changes the state and calls `draw()`. Do not patch single elements; a full redraw cannot go stale. `draw()` also writes each `.val`; a `.val` does not update by itself.
- **Use real names and numbers** from the user's system (12 partitions, 3 consumers, a 200 ms first wait). Never invent sample data when the real value is known.
- **On load, show a result.** Start in a state where something has already happened (4 messages sent, one burst sent), so the first thing the reader sees is the idea, not an empty picture.
- **Every control must change the page.** The self-test in section 5 fails a slider or a button that changes nothing. A change to a `.val` counts. A button may do nothing in one state (Reset at the start) if it does something after the sliders move.
- **Pick the baseline that isolates the reader's question.** "Why do we need both numbers?" means: remove one number and draw what is left. When several simpler methods exist, do not pick the best-known one; pick the one whose difference from the idea is the answer.
- **Every mark has a name.** A dot, a colour or a line that the reader must decode gets a label in the picture, a `.chip` under it, or an entry in the frame's "How to read it" legend.
- **Keep a fixed frame; only the data moves.** Put the cards in a `.frame`. Its side column holds, at the top, the one number the reader should watch (a `.readout`: "Message 4", "Hour 23.3") and the rule with its live numbers, and at the bottom a `.legend` titled "How to read it". These stay in place while the pictures change, so the reader learns the layout once. A value that belongs to one method (the load on each consumer) stays in that method's card.

### A picture that runs over time

Some ideas need a clock (a rate limiter, a retry, a queue).

- **State is the settings, a list of events and the clock.** `draw()` replays the events with the current settings. A settings change then shows the same events under the new settings, which is the comparison the reader wants. If a replay makes no sense for a setting, reset the events on that change and say so in the result line.
- **Give time a step button** ("Wait 100 ms") next to the action buttons, and a `kit.play` button that calls the same step.
- **Keep the window short.** Show a fixed span (the last 3 seconds, the last 60 slices). When an event leaves the window, first fold its effect into a saved start state (the level and the clock at the start of the window), then drop it. The replay starts from that saved state, so a dropped event never "un-happens" and a long Play does not slow down.
- **The result line judges what is in view.** When the event it describes leaves the window, go back to the `.quiet` line.
- **Draw the level two ways when both matter:** the state now (the shape), and the state over the window (a line with a `.mark` at "now", on an `.axis`).

### Page parts (classes from the shared stylesheet)

| Class | Use |
|---|---|
| `.controls` | a row of controls that wraps by itself; one row for settings, one for actions |
| `label` + `input[type=range]` + `.val` | a setting and its live value (your `draw()` writes the value) |
| `.frame` > `.side` + `.grid` | the figure: one panel with a fixed side column and the cards. Inside a frame the cards have no border of their own. On a phone the side column goes on top |
| `.readout` (`<b>` + `<span>`) | in `.side`: a large live value and a short grey caption under it. Use one large readout, then `.readout.minor` for a formula or a second value. Your `draw()` writes the `<b>` |
| `.legend` (`<h3>` + `.chip` rows + optional `.cap`) | in `.side`, at the bottom: "How to read it". One chip per mark. `.dot` is a filled dot, `.dot.hollow` a ring, `.dot.line` a short thick line; a `c-*` class on the chip colours it |
| `.grid` > `.card` | one card per method; side by side on a wide page, stacked on a phone |
| `.card h2`, `.formula` | the method's name, and its formula with the live numbers |
| `svg.pic` | the picture, one per card: `viewBox`, `role="img"`, and an `aria-label` that says what it shows |
| `.row` (with `<b>` for values) | a readout line; also works inside `.controls` for a counter or a clock |
| `.chip` + `.dot` | a legend entry, placed inside a `.row` or the `.legend`; the dot is the accent colour, or the chip's `c-*` colour. A chip may carry a value ("Consumer A: 2") |
| `.verdict` + a tone | the result line (tones below) |
| `kit.bars(counts)` + `.cap` | a small bar chart and its caption |

**Tone of the result line:** `.good` = the outcome the design wants. `.warn` = it works, at a cost the reader must see (part of a burst rejected, one consumer overloaded). `.bad` = the mechanism is defeated, or the baseline fails at the reader's goal. `.quiet` = nothing to judge yet. Write one or two sentences.

### Picture styles (inside `svg.pic`)

| Class | Put it on | It looks like |
|---|---|---|
| `.item` | circle, rect, path | page-colour fill, thin grey outline: an empty or idle slot |
| `.item.on` | the same | pale accent fill, accent outline: active, with room for a label inside |
| `.item.on.now` | the same | the same with a thick outline: the latest one |
| `.item.full` | the same | solid accent fill: a slot that holds something. No label inside |
| `.mark` | circle | a solid accent dot with no outline |
| `.link` | line, path | a thin accent line with no fill |
| `.band` | path, line | a thick (5 px) round-ended stroke with no fill: an arc or a range |
| `.axis` / `.guide` | line, path | a thin grey rule / a pale dashed rule |
| text (no class) | text | 12 px grey, centred on its `x` and its `y` |
| `.t` / `.th` | text | 13 px dark / 13 px dark and bold, for names |
| `.start` / `.end` / `.on` | text | left aligned / right aligned / accent colour and bold |

- Add a `c-*` class to any of these to give it a category colour: `class="mark c-rose"`, `class="link c-amber"`, `class="item full c-sky"`, text too. An arrowhead takes the colour of its line. One name (a label or a chip) covers every use of a colour.
- **A level:** draw things you can count (about 40 or fewer) as slots, `.item` for empty and `.item.full` for filled. Draw a continuous level as an `.item` outline with an `.item.full` rect inside it.
- **Size:** the `viewBox` is 320 to 360 wide and at most about 320 tall, so one card stays shorter than a phone screen. Text is about 6.5 px wide per character at 12 px and 7 px at 13 px, and two lines of text need centres at least 16 px apart: check that each label fits its space before you place it.

### kit helpers

Helpers that draw return a string; join the strings into the card's `innerHTML`.

| Call | Takes | Gives back |
|---|---|---|
| `kit.el(id)` | an element id | the element |
| `kit.bind(ids, fn)` | an array of ids | nothing. It calls `fn(element)` on `input` for a slider or a menu, and on `click` for a button |
| `kit.play(id, tick, ms = 700)` | a button id, a function, the real milliseconds between ticks | `{ stop() }`. A click starts it and shows "Pause"; the next click stops it |
| `kit.polar(cx, cy, r, deg)` | numbers | `[x, y]` on a ring; 0° is the top, angles grow clockwise |
| `kit.arc(cx, cy, r, deg0, deg1)` | numbers | a path `d` string |
| `kit.defs()` | nothing | the arrowhead marker as an SVG string. Put it once at the start of each `<svg>` that has arrows |
| `kit.arrow(a, b, { pad = 0, opacity = 1, cls = 'link', head = true })` | two `[x, y]` points | a `<line>` string. `pad` shortens both ends; `cls: 'link c-rose'` colours it; `head: false` gives a plain line |
| `kit.scale(d0, d1, r0, r1)` | a value range and a position range | a function from a value to a position. It does not clamp |
| `kit.bars(values, { flagZero = false, peak = false, max = 0 })` | an array of counts | a bar chart as an HTML string. Bars are the accent colour. They scale to the tallest value, or to `max` when you give it: **give both cards the same `max`**, or a bar of 1 looks as tall as a bar of 20. Use a fixed `max` from the settings when one exists (the client count, the bucket size), so the bars do not rescale as time moves. `flagZero` paints empty slots red; `peak` paints the tallest bars red. About 60 bars fit a phone card |
| `kit.random(seed)` | a whole number | a function that returns 0 to 1, the same sequence on every load |
| `kit.fmt(n, digits = 0)` | a number | a string with exactly `digits` decimals and thousands commas: `fmt(3000)` is "3,000", `fmt(1.5, 1)` is "1.5", `fmt(2, 1)` is "2.0". A whole number needs no `fmt` unless it can pass 999 |
| `kit.gcd(a, b)`, `kit.clamp(v, lo, hi)`, `kit.esc(text)` | | small maths, and text made safe for HTML |

## 3. Rules for the look

- **Colours come only from tokens and `c-*` classes.** Tokens: `var(--ink)`, `--mut`, `--line`, `--surf`, `--acc` (the accent: the active thing), `--warn`, `--bad`. Classes `c-sky`, `c-amber`, `c-slate`, `c-teal`, `c-rose`, `c-emerald` set `--c` and `--cw` for a category. A hex or `rgb()` colour breaks dark mode, and the build warns.
- **The look is a warm off-white panel on a slightly darker warm page**, with thin warm-grey lines and muted colours. Dark mode is the same idea on warm near-black. You get this from the tokens; do not add backgrounds, shadows or gradients.
- **Neutral, plus one accent, plus at most three category colours.** Colour says "active" or "which group"; it is never decoration. Every category colour gets a `.chip` legend.
- **Lines are thin (1 to 1.5 px) and stop at the edge of a shape.** Use `kit.arrow` with `pad`. A line must never cross a label.
- **Picture text is 12 or 13 px, in a `viewBox` 320 to 360 wide.** A phone card is about 320 px wide, so that width keeps text at full size. A card on a wide page is about 500 px, so always cap the growth: `style="max-width:440px"` on a 340-wide picture (about 1.3 times the `viewBox` width). Without the cap the picture text grows larger than the page text, and the self-test fails.
- **Words on the page:** the title, the lead, labels, the formula, readouts and the result line. No paragraphs. Sentence case. Every number with decimals goes through `kit.fmt`.
- **The result line is one or two plain sentences with the numbers in them.** "Stride 4 and 12 share the factor 4. Only 3 of 12 partitions ever get a message." Not "Bad stride".
- **One offline file.** No CDN script, no font download, no `fetch`.

## 4. Build

```bash
"${CLAUDE_SKILL_DIR}/cx" stride.concept.html            # writes stride.html next to the source
"${CLAUDE_SKILL_DIR}/cx" stride.concept.html --check    # checks only, writes nothing
```

Run `cx` from any folder; the page is written next to the source. `cx` prints one JSON line: `ok`, `out`, `kb` and `warnings`. Exit 2 means the header is wrong or the script does not parse. Fix every warning: an outside URL, a hard-coded colour, a font below 11 px, an `<svg>` without `viewBox`, `class="pic"` or a label, a page with no control, a page with no `.verdict`.

## 5. Verify in the browser pane, then hand over

1. Serve the folder on localhost (a launch.json preview entry, or `python3 -m http.server`) and open `http://localhost:<port>/<idea>.html?v=<n>`. Change `?v=` after every rebuild, because the pane caches pages. The pane cannot open `file://` URLs.
2. Run `JSON.stringify(window.__cx.selftest())`. It moves every slider to both ends, picks every menu option and clicks every button, and after each move it reports: script errors, a page that scrolls sideways, picture text that is cut off, overlaps other text, or is under 10 px on screen, a picture drawn more than 1.3 times its `viewBox` size, page text under 11 px, content wider than its card, and a control that changes nothing. `ok:true` is the bar to pass. Reload the page afterwards; the test leaves the controls moved.
3. Run it four times: at desktop width (`resize_window` 1100×900) and at `mobile`, each in `colorScheme` light and dark. Then reset to `desktop`.
4. Take one screenshot at desktop width and one at `mobile`, and look at them. The self-test cannot judge whether the picture explains the idea. Check: does the shape show the mechanism without its labels? Does the failure case look broken?
5. Give the user the path. Say which control shows the idea best ("set the stride to 4").
6. Publish it as an artifact only if the user wants to share it. The page is self-contained, so publish the HTML directly.

## Don'ts

- Do not draw boxes and arrows here. If the picture is nodes joined by labelled arrows, it is a flow: use diagrams:flow.
- Do not add a shape-specific helper, template or "type" to the plugin for a new idea. Draw it in the page's own script. Propose a `kit` helper only when three different pages needed the same hard geometry.
- Do not explain in paragraphs on the page. If the picture needs a paragraph, the shape is wrong.
- Do not animate for decoration. Motion shows one step of the mechanism (a message that lands), and "Play" is always a button the reader starts.
- Do not ship a page you have not opened. The build cannot see a label that sits under a line.
