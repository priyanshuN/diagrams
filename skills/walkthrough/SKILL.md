---
name: walkthrough
description: Build a narrated, step-synced diagram walkthrough (local Kokoro voice + animated SVG with a camera that follows the voice, one self-contained HTML page with a recall quiz, predict pauses and source links) for a long mechanism the user wants to learn once — onboarding, a pipeline, a request path. Use when the user asks for a walkthrough, a narrated explainer or a "video", or accepts an offer of one. Never build one unasked; for short flows a text diagram in the reply is enough. A walkthrough narrates a flow or a sequence (boxes and arrows); to explain how an idea, an algorithm or a number behaves, use diagrams:concept instead.
---

# Narrated walkthrough

The "video" is an HTML page, not an MP4. It is directed like a film:
- **The camera follows the voice.** The frame moves to the boxes a step names, and pulls back for the overview and the recap. A box or arrow appears when the voice first names it.
- **Captions light word by word**, and a box's name in the caption takes the box's colour.
- **Boxes show what they hold.** A box's second line changes when the data lands in it.

One scene gives several pictures, and the viewer switches between them while the voice goes on:

| The viewer asks | The picture | Comes from |
|---|---|---|
| What talks to what? | Flow diagram with the camera | `diagram` (`graph`) |
| Who waits for whom, in what order? | Sequence diagram | `diagram` (`sequenceDiagram`) |
| What happens to my order? | "Item story": one record that changes, on a line of stops | the `item` of each step |
| What happens when this part fails? | "What if…": the same flow with the broken part in red | `whatif` |

It also beats a video in four ways:
- **Arrows light up on the spoken word.** A cue lights the node or arrow when the voice says the matching word, not just at the start of the step.
- **Predict pauses.** The page stops before a step and asks what happens next.
- **"Test me" quiz.** It hides the labels and asks the viewer to click where each step happens.
- **Source links.** Each step shows the `file:line` it comes from in the real repo.

The page is one file of about 700 KB per minute of narration. It works offline and on a phone.

This skill is the top layer. The **diagrams:flow** skill draws every picture (Mermaid → arrows by libavoid → sketch or clean theme); this skill adds the voice, cues, quiz and item card. Read `${CLAUDE_SKILL_DIR}/../flow/SKILL.md` for the diagram rules: flow or sequence, the look file, colour meaning, Mermaid gotchas.

```
Mermaid diagram + look ─► scene.json ─► nw --check ─► fix ─► nw ─► page.html
 (diagrams:flow rules)                                                │
                        window.__nw.selftest() in the browser pane ◄┘
```

## 1. Write the scene

Write the scene in a working folder (not inside the plugin) and serve that folder on localhost: a launch.json preview entry or `python3 -m http.server`. The browser pane cannot open `file://` URLs.

```json
{
  "title": "What happens when you place an order",
  "lead": "One line saying what this explains.",
  "voice": "af_heart",
  "repo": "~/code/shop",
  "theme": "clean",
  "diagram": "graph LR\n  customer[Customer<br/>web browser]\n  shop[Shop API<br/>order service]\n  ...\n  shop -->|charge card| pay",
  "look": {"customer": {"kind": "external", "color": "slate", "at": [0, 0]}, "provider": {"color": "sky"}},
  "legend": [{"color": "slate", "label": "Outside your system"}],
  "steps": [
    {"title": "The shop asks for the charge",
     "caption": "The shop saves a pending order, then asks the payment provider to charge the card.",
     "focus": ["shop"], "edges": [["customer", "shop"]], "state": {"shop": "order: pending"},
     "cues": [{"at": "charge the card", "focus": ["pay"], "edges": [["shop", "pay"]], "state": {"pay": "charging card"}}],
     "ask": {"q": "The card is charged. How does the shop find out?", "a": "The provider sends a signed webhook."},
     "src": "src/checkout/create-order.js:42"}
  ],
  "recap": [
    {"text": "The shop saves the order before it charges the card.", "focus": ["shop"]},
    {"text": "A signed webhook, not the browser, marks the order paid.", "focus": ["pay", "shop"]}
  ],
  "whatif": [
    {"q": "The card is declined",
     "caption": "The provider refuses the charge. The shop marks the order failed, and nothing is shipped.",
     "fail": {"edges": [["shop", "pay"]]}, "skip": ["warehouse"],
     "focus": ["shop"], "state": {"shop": "order: failed"},
     "src": "src/checkout/create-order.js:71"}
  ]
}
```

**The diagram**
- `diagram` is Mermaid: `graph TD|LR` for a flow, `sequenceDiagram` for a sequence. `look` and `legend` follow the diagrams:flow rules. The same Mermaid also renders as chat text with `${CLAUDE_SKILL_DIR}/../flow/fd`.
- `theme` is `clean` (the default: crisp lines) or `sketch` (hand-drawn on graph paper).
- Use 4–8 nodes for one path through code. A design picture (the next rule) can have up to 12, because the camera frames the lit part; above 8 boxes the phone picture uses two columns. A phone picture never shrinks below a readable size (labels 10.5 px, detail lines 10 px): when it is wider than the screen, it scrolls sideways in the overview and the test, and the camera frames it while the voice plays. If the self-test says the labels or the detail lines are small on a desktop, pack the `at` grid into fewer columns (stack the client above the gateway, put a fan-out in one column). A label has at most 3 words; a sub-label (`<br/>` second line) has at most 4.
- **A design picture ("draw the HLD of X") is not a small flow. Do not shrink it to the happy path.** Before you draw, list what a design review would ask for, and put each one in the picture:
  - the entry point (client, API gateway) and every service behind it, the read path as well as the write path;
  - each store with its technology as the sub-label ("DynamoDB") and its tables or keys as `notes` in the look (`"notes": ["Jobs: id, userId, taskId", "Executions: time, jobId, status"]`);
  - each queue or stream with the settings that make the design work as `notes` ("delay until execution time", "retry, exponential backoff");
  - a fan-out drawn as 2 or 3 boxes when the point is that work runs in parallel;
  - the arrow that closes the loop (the status written back).
  If the user gives a reference picture, keep every box, table and note of the reference, and say which ones you left out and why. If there is no code and no reference, say in the `lead` that the design is generic and that the values are examples.
- **Flow:** give `at` positions in the look whenever the flow branches, loops back or skips a node. Without them, nodes are placed in layers, which can render long and small. The phone layout ignores `at` and stacks nodes in the order the narration first lights them.
- Give a decision's two outcomes different sides: one straight down, one straight right (for example `decide` at [2,1], `orders` at [3,1], `retry` at [2,2]). If the build warns that two arrows "run side by side", move a box with `at`.
- Two boxes can have an arrow each way (the queue delivers a run to the worker, and the worker sends a retry back). Draw both arrows and label both: each label goes on the outer side of its own arrow. Make the return arrow dashed (`-.->`) so the main direction stays clear.
- Draw the direction the *data* moves. If the worker reads a file from S3, the arrow is S3 → worker, not worker → S3. Label most arrows with the verb that travels them.
- **Sequence:** use it when the order matters, or who waits for whom ("the customer sees processing before the payment is confirmed"). Steps light messages by number with `"msgs": [3]` instead of `"edges"`. Participants are the `focus` ids. On a phone the camera frames the lit message; with the camera off, the sequence keeps readable text and scrolls sideways, following the lit message.
- The older format (`nodes`, `edges`, `groups` written as JSON) still builds. Do not mix it with `diagram`.

**Steps**
- Use 5–9 steps. Each `caption` is one or two short sentences, under about 40 spoken words. The voice reads it, and the page lights it word by word.
- `title` is the step's headline: 8 words or fewer, the one thing to remember from the step ("SNS tells the API"). It shows above the caption and in the step list. Give every step a title, or none.
- `say` is optional. By default the voice reads the caption after the speech rules and the lexicon (section 2). Write `say` only when the spoken wording must differ.
- `focus` and `edges` (flow) or `msgs` (sequence) light the step from its first word.
- `cues` relight the diagram when the voice reaches the `at` phrase: one or more consecutive words of the spoken line, matched in order. Use a cue when one step crosses several nodes, so a node is not lit for 10+ seconds while the narration moves on.
- `item` is the thing travelling through the flow, as it looks *at this moment*: `{"name": "Charge", "fields": {"status": "pending"}}`. It shows in a card beside the caption, coloured like the box it sits in, and carries forward until a later step or cue replaces it. Use real field names and values from the code or data, never invented ones. Mask personal values (card digits, addresses) with `…`. Set `item` on cues too, so the card changes on the spoken word ("parses" → the parsed payload).
- `state` is what a box holds from this moment: `{"api": "job: processing"}`. It replaces the box's second line (30 characters or fewer, and it must fit the box) until a later step or cue replaces it. Set it on the box where the data lands: when a lit arrow ends at that box, the line changes as the pill arrives. Use real values from the code or data, as for `item`. Flows only; a decision has no second line.
- `carry` (18 characters or fewer) labels the pill that rides each lit arrow for about 1.4 s after the step or cue starts ("order", "charge", "webhook", "yes"). Without it the pill shows the item's name.
- `ask` adds a predict pause before the step. Use it on 1–3 steps, at the "aha" points, where the next move is not obvious.
- `src` is `"path:line"` or a list of them, relative to `repo`. The build checks that each file and line exists and stamps the repo's git SHA in the footer.

**The camera**
- **Flow:** the frame holds the `focus` boxes and both ends of the lit `edges` of the step or cue, plus their neighbours. Keep each step or cue to 1–3 boxes that sit near each other. On a desktop, a step that lights boxes at both ends of the diagram gets the whole diagram.
- A box appears when a step first names it in `focus`, or as an end of a lit edge. The build warns about a box that no step names, because the walk never shows it.
- **Sequence:** every participant shows from the start, and a message appears when a step first lights it. A sequence that is readable at full width stays whole. A larger one (and any sequence on a phone) gets a frame around the lit message, with the participants' names pinned at the top of the frame.
- **Phone:** the stage is a square that stays on screen with the caption under it. The frame never shows the diagram smaller than 0.75 times its drawn size: when the lit parts need more room (a long arrow in a side lane), the frame stays on the `focus` boxes.
- The viewer can turn the camera off with "Follow the voice". The overview and "Test me" always show the whole diagram: in the same stage on a desktop, at full length on a phone. The recap shows the whole diagram on a desktop and follows each point's boxes on a phone.

**The recap**
- `recap` is 2–4 points, each one short sentence (under about 20 words), spoken after the last step while the camera shows the whole diagram. A point is a sentence, or `{"text": "...", "focus": ["box"], "edges": [["a", "b"]]}` to light its boxes as it is spoken.
- Write what to remember, not a list of the steps. Use the same words as the captions.

**Item story** (offered by itself when any step has an `item`; no extra fields)
- The view shows the `item` as one large card on a line of stops. The stops are the boxes in the order the voice first reaches them.
- Keep the same `name` while the thing is the same thing. The view then marks a field the step added as "new", and shows a changed value with the old value struck out.
- Change the `name` only when the thing becomes another thing ("Raw email file" → "email_jobs row"). Each new name is one more form in the trail above the card.
- Repeat the fields that still matter in each `item`. A field you leave out disappears from the card, and the viewer reads that as "removed".

**What if** (`whatif`: 1–4 scenarios; flows only)
- Each scenario replays the same diagram with one part broken. The viewer picks it from the "What if…" row under the player. It is not part of the main walk.
- `q` is the scenario as the viewer picks it: 48 characters or fewer, a plain statement ("The card is new", "S3 is down for a moment").
- `caption` is what the voice says, under about 40 words: what breaks, what the system does next, and where the run ends. `title` is an optional headline.
- `fail` is the part that breaks: `{"edges": [["a", "b"]]}` for an arrow, `{"focus": ["box"]}` for a box. It is drawn red, with a cross on a broken arrow.
- `skip` lists the boxes this run never reaches. They are drawn faint.
- `focus`, `edges`, `state`, `carry` and `cues` light the path the run takes instead, as in a step. Put the real reason code in `state` on the box where the run ends (`{"review": "NEW_ACCOUNT"}`).
- A scenario states a fact about the system, so check the code before you write one, and give its `src`. Do not guess a failure path.
- Pick failures that teach the design: one check that fails, one outage that passes, one loss that cannot be undone. Each scenario adds about 10 seconds of audio to the page.

**Content rules**
- Use real names and numbers from the work, never invented samples.
- Use the same word for the same thing in every step.
- Each node, label and arrow must match what the code really does. Check the code before you draw an edge.

## 2. Check, then build

`${CLAUDE_SKILL_DIR}/nw` wraps build.py with the shared venv. Run from the scenes folder:

```bash
"${CLAUDE_SKILL_DIR}/nw" my-scene.json --check 2>/dev/null
```

`--check` runs in about 2 seconds and generates no audio. It prints JSON with:
- **`warnings`:** schema errors, arrows that pass behind a node, two unrelated arrows that run side by side, an arrow label with no clear spot, labels too wide for their box, a group covering a node that isn't in it, symbols left in the spoken text, steps that are too long, and `src` paths that don't exist.
- **`ok`:** false when there is any warning or error. The full build still writes the page with warnings and reports `ok:true`; read its `warnings` too.
- **`[phone]` warnings** come from the phone column, which ignores `at`. Fix them by changing which step first lights one of the named boxes, or by dropping an arrow, not by moving `at`.
- **`pronunciation`:** each spoken line, plus the phonemes for every acronym, number and symbol. Read them. A wrong reading gets an entry in `lexicon`, either the scene's own or the shared `${CLAUDE_SKILL_DIR}/lexicon.json` for recurring terms. The value is plain words ("IST" → "India time") or misaki inline phonemes (`"ARC": "[ARC](/ˌAˌɑɹsˈi/)"`).
- The speech rules already handle ₹ amounts (→ "842 rupees and 82 paise"), 24-hour times (02:00 → "2 AM"), vN.N.N versions, arrows, "e.g.", "i.e." and "&".

```bash
"${CLAUDE_SKILL_DIR}/nw" my-scene.json 2>/dev/null
```

The build prints one JSON line: `ok`, `out`, `engine`, `seconds`, `voice`, `steps`, `recap`, `whatif`, `cues`, `kb` and `warnings`.
- **Voice cache:** each spoken line is kept in `~/.cache/narrated-walkthrough/lines`, keyed by its spoken text, the voice, the speed and the voice package version. A build speaks only the lines that changed (`voice: {"cached": 12, "spoken": 1}`), so a layout or look change builds in under a second. A line that no build used for 30 days is removed. `--no-cache` (or `NW_NO_CACHE=1`) speaks every line again.
- **Exit 2:** a scene error. **Exit 3:** Kokoro failed. A build never falls back to the system voice silently. Pass `--allow-fallback` (or `--say`) only if the user accepts the robotic voice: macOS `say`, or `espeak-ng` on Linux when it is installed.
- **Voices:** `af_heart` downloads with the model. Any other voice (`am_michael`, `bf_emma`, `bm_george`) downloads a small voice file on first use, which needs the network.

## 3. Verify in the browser pane, then hand over

1. Open the page from your localhost server: `http://localhost:<port>/<name>.html?v=<n>`. Change `?v=` after every rebuild, because the pane caches pages.
2. Wait for the audio metadata, then run `JSON.stringify(window.__nw.selftest())`. It walks every step and cue, and reports:
   - what each one lit;
   - a `state` text wider than its box;
   - `camera.stepLabelPx`, the smallest label size in a camera frame;
   - `item`, the number of stops and forms of the "Item story" view (the checks themselves run in the diagram view);
   - arrows that cross a node;
   - text wider than its box;
   - the on-screen label size, which must be at least 10 px;
   - the audio duration against the build;
   - arrow and group labels that overlap each other or a box;
   - two arrows that share no box but run side by side (flows only).
   `ok:true` is the bar to pass.
3. Run it once at desktop width (`resize_window` 1100×900) and once at `mobile`, then reset to `desktop`. Take one screenshot of each layout.
4. Give the user the path. Mention `#3`-style deep links, the number keys, the speed menu, the "Follow the voice" switch, the "Diagram / Item story" switch, the "What if…" buttons, "Test me" and "Copy as notes", which copies the walkthrough as Markdown notes.
   The browser pane must be visible while you judge motion: a hidden pane does not run the camera or the fades, so a screenshot can show a frame that is half moved. `selftest()` moves the camera without animation and is safe in a hidden pane.
5. Publish it as an artifact only if the user wants to share it. The page is self-contained, so publish the HTML directly.

## Don'ts

- No MP4 export. It throws away the cues, the quiz and the predict pauses.
- No CDN libraries. The page must stay one offline file. Diagram libraries run at build time in the diagrams plugin (Claude Code installs them from its package.json).
- Do not switch to an automatic box-placement engine (ELK, dagre) by default. ELK was tried: chain flows came out 7.8 times wider than tall, with 7 px labels.
- No extra voices, music or avatars. They add novelty, not recall.
