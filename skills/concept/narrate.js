// The narration player of a narrated concept page. The build puts window.__nar before this file:
//   { beats: [{ t, end, title, caption, wt, acts: [{ t, press | set + to | show, times, every }] }], reset: [...], seconds }
// The voice reads one beat at a time. On the spoken word, the player moves the page's own controls with the
// same events a viewer makes, so the picture is never a recording. A viewer who touches a control takes over.
;(function () {
  'use strict'
  const N = window.__nar, B = N.beats, $ = kit.el, a = $('narAudio'), stage = $('stage'), bar = $('nar')
  const cap = $('narCap'), prog = $('narProg'), note = $('narNote'), playBtn = $('narPlay')
  const ACTS = B.flatMap((b, i) => b.acts.map(x => ({ ...x, beat: i }))).sort((x, y) => x.t - y.t)
  const mmss = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
  const fire = (c, type) => c.dispatchEvent(new Event(type, { bubbles: true }))
  let done = 0          // ACTS[0 .. done) have started
  let queue = []        // moves of a started action that are still to come: { t, fn }
  let dirty = true      // the page is not in the state the story expects (not started, or the viewer moved a control)
  let quiet = false     // true while the page is rebuilt: no pulse, no scroll
  let beat = -1, words = [], shown = [], begun = false

  // ---- the three things the voice can do
  function pulse(node) {
    if (quiet || !node) return
    node.classList.remove('nar-press'); void node.offsetWidth; node.classList.add('nar-press')
    clearTimeout(node._nar); node._nar = setTimeout(() => node.classList.remove('nar-press'), 750)
  }
  // The bar names each move, because the control can be off the screen on a phone.
  const did = text => { if (!quiet) $('narDid').textContent = text ? ' · ' + text : '' }
  const nameOf = c => ((c.closest('label') || c).firstChild.textContent || c.id).trim()
  function press(id) { const b = $(id); b.click(); pulse(b); did(`pressed "${b.textContent.trim()}"`) }
  function setv(c, v) { c.value = v; fire(c, 'input'); fire(c, 'change'); pulse(c.closest('label') || c); did(`moved ${nameOf(c)} to ${v}`) }
  function show(ids) {
    shown.forEach(n => n.classList.remove('nar-show'))
    shown = ids.map($).filter(Boolean)
    shown.forEach(n => n.classList.add('nar-show'))
    if (quiet || a.paused || !shown.length) return
    const r = shown[0].getBoundingClientRect(), top = bar.getBoundingClientRect().bottom + 8
    if (r.top < top || r.bottom > innerHeight) shown[0].scrollIntoView({ block: r.height > innerHeight - top ? 'start' : 'nearest', behavior: 'smooth' })
  }
  // The moves of one action. A slider travels to its value in up to 12 steps, and each step is a real input event.
  function plan(x, t0) {
    if ('press' in x) return Array.from({ length: x.times || 1 }, (_, k) => ({ t: t0 + k * (x.every || 0.4), fn: () => press(x.press) }))
    if ('show' in x) return [{ t: t0, fn: () => show([].concat(x.show)) }]
    const c = $(x.set)
    if (c.type !== 'range') return [{ t: t0, fn: () => setv(c, x.to) }]
    const from = +c.value, to = +x.to, step = +c.step || 1, n = Math.min(12, Math.max(1, Math.round(Math.abs(to - from) / step)))
    return Array.from({ length: n }, (_, k) => ({ t: t0 + 0.6 * (k + 1) / n,
      fn: () => setv(c, k === n - 1 ? to : from + Math.round((to - from) * (k + 1) / n / step) * step) }))
  }
  const flush = () => { queue.forEach(m => m.fn()); queue = [] }
  const beatAt = T => { let i = 0; while (i + 1 < B.length && B[i + 1].t <= T) i++; return i }

  // Put the page in the state the story has at time T: the reset actions, then every action up to T, at once.
  function rebuild(T) {
    quiet = true
    kit.stopAll(); queue = []
    for (const x of N.reset) plan(x, 0).forEach(m => m.fn())
    for (done = 0; done < ACTS.length && ACTS[done].t <= T; done++) plan(ACTS[done], 0).forEach(m => m.fn())
    const bi = beatAt(T), last = ACTS.slice(0, done).filter(x => x.beat === bi && 'show' in x).pop()
    show(last ? [].concat(last.show) : [])
    quiet = false; dirty = false
  }

  // ---- caption, lit word by word
  const capHtml = i => B[i].caption.trim().split(/\s+/).map(w => `<span class="w">${kit.esc(w)}</span>`).join(' ')
  function setCap(i) {
    cap.classList.remove('hint'); cap.innerHTML = capHtml(i); words = [...cap.children]
    $('narNo').textContent = `Beat ${i + 1} of ${B.length}`; $('narTitle').textContent = B[i].title
  }
  function intro() {
    cap.classList.add('hint'); words = []
    cap.textContent = 'The voice explains this page and moves the controls for you. Touch any control to take over.'
    $('narNo').textContent = `Narrated · ${B.length} beats · ${mmss(N.seconds)}`; $('narTitle').textContent = 'Listen to the explanation'
  }
  function sizeBar() {              // the caption keeps the height of its longest line, so the page below never jumps
    const keep = cap.innerHTML, cls = cap.className
    cap.style.minHeight = ''; cap.className = 'nar-cap'
    let h = 0
    B.forEach((_, i) => { cap.innerHTML = capHtml(i); h = Math.max(h, cap.offsetHeight) })
    cap.innerHTML = keep; cap.className = cls; words = [...cap.querySelectorAll('.w')]
    if (h) cap.style.minHeight = h + 'px'
    document.documentElement.style.setProperty('--narh', bar.offsetHeight + 'px')
  }

  // ---- the clock: everything follows the audio time
  function tick() {
    if (!begun) return
    const T = a.currentTime, bi = beatAt(T)
    if (bi !== beat) { beat = bi; setCap(bi); did(''); if (done && ACTS[done - 1].beat !== bi) show([]) }
    while (done < ACTS.length && ACTS[done].t <= T) { flush(); queue = plan(ACTS[done], ACTS[done].t); done++ }
    while (queue.length && queue[0].t <= T) queue.shift().fn()
    words.forEach((w, k) => w.classList.toggle('on', T >= B[bi].wt[k] - 0.04))
    $('narFill').style.width = Math.min(100, T / N.seconds * 100) + '%'
    $('narTime').textContent = `${mmss(T)} / ${mmss(N.seconds)}`
  }
  function loop() { tick(); if (!a.paused) requestAnimationFrame(loop) }
  function seek(T) {
    begun = true
    T = kit.clamp(T, 0, N.seconds - 0.05)
    a.currentTime = T; rebuild(T); beat = -1; note.hidden = true; did('')
    tick(); label()
  }
  function play() {
    if (!begun || a.ended || a.currentTime >= N.seconds - 0.1) seek(0)
    else if (dirty) { rebuild(a.currentTime); beat = -1 }
    note.hidden = true
    a.play()
  }
  const label = () => { playBtn.textContent = !a.paused ? 'Pause' : a.ended ? 'Replay' : begun && a.currentTime > 0.05 ? 'Resume' : 'Play' }
  playBtn.addEventListener('click', () => a.paused ? play() : a.pause())
  $('narPrev').addEventListener('click', () => seek(B[Math.max(0, beatAt(a.currentTime) - (a.currentTime - B[beatAt(a.currentTime)].t > 1.5 ? 0 : 1))].t))
  $('narNext').addEventListener('click', () => { const i = beatAt(a.currentTime) + 1; if (begun && i < B.length) seek(B[i].t); else if (!begun) seek(0) })
  a.addEventListener('play', () => { label(); loop() })
  a.addEventListener('pause', label)
  a.addEventListener('timeupdate', tick)
  a.addEventListener('ended', () => {
    flush(); label()
    note.textContent = 'Your turn. The controls are yours: move one and see what changes.'; note.hidden = false
  })
  // the progress line: beat marks, click or drag to move in time
  B.slice(1).forEach(b => { const u = document.createElement('u'); u.style.left = b.t / N.seconds * 100 + '%'; prog.appendChild(u) })
  const at = e => { const r = prog.getBoundingClientRect(); seek(kit.clamp((e.clientX - r.left) / r.width, 0, 1) * N.seconds) }
  prog.addEventListener('pointerdown', e => { prog.setPointerCapture(e.pointerId); at(e) })
  prog.addEventListener('pointermove', e => { if (prog.hasPointerCapture(e.pointerId)) at(e) })

  // A viewer who moves a control takes over: the voice stops, and Resume puts the story state back.
  const mine = e => {
    if (!e.isTrusted || !begun || !e.target.closest('button,input,select')) return
    dirty = true
    if (a.paused) return
    a.pause()
    note.textContent = 'Paused, because you moved a control. Resume puts the page back where the story was.'; note.hidden = false
  }
  stage.addEventListener('click', mine, true)
  stage.addEventListener('input', mine, true)

  intro(); sizeBar(); label()
  addEventListener('resize', sizeBar)

  // ---- what the page says, as text lines. The story report and the "expect" checks read the same lines.
  const BLOCK = 'div,p,section,aside,article,header,footer,h1,h2,h3,h4,ul,ol,li,dl,dt,dd,table,tr,label,svg'
  const SKIP = 'svg,script,button,select,input,.bars,.controls'
  const squash = t => t.replace(/\s+/g, ' ').trim()
  function textOf(node, sep) {              // the text of a node without its pictures and controls
    const out = [], w = document.createTreeWalker(node, NodeFilter.SHOW_TEXT)
    while (w.nextNode()) if (!w.currentNode.parentElement.closest(SKIP)) out.push(w.currentNode.textContent)
    return squash(out.join(sep))
  }
  function snap() {                         // -> { id of the nearest named element: [lines] }
    const out = {}
    const walk = n => {
      if (n.matches(SKIP)) return
      if (n.querySelector(BLOCK)) return [...n.children].forEach(walk)
      const line = textOf(n, ' '), near = n.closest('[id]'), key = near !== stage ? near.id : (n.querySelector('[id]') || stage).id
      if (line) (out[key] = out[key] || []).push(line)
    }
    ;[...stage.children].forEach(walk)
    return out
  }
  const start = () => { const was = begun; quiet = true; kit.stopAll(); for (const x of N.reset) plan(x, 0).forEach(m => m.fn()); return was }
  const finish = was => { show([]); quiet = false; dirty = true; if (was) { rebuild(a.currentTime); beat = -1; tick() } }
  // The story report: run JSON.stringify(__cx.story()) and write each caption from the lines its beat changes.
  // story(true) lists every line of the page after each beat, not only the changed lines.
  function story(all) {
    const was = start()
    let prev = snap()
    const out = B.map((b, i) => {
      b.acts.forEach(x => plan(x, 0).forEach(m => m.fn()))
      const now = snap(), lines = {}
      for (const k in now) { const l = all ? now[k] : now[k].filter(t => !(prev[k] || []).includes(t)); if (l.length) lines[k] = l }
      prev = now
      return { beat: i + 1, title: b.title, caption: b.caption, checks: b.expect.length,
        controls: Object.fromEntries([...stage.querySelectorAll('input,select')].filter(c => c.id).map(c => [c.id, c.value])),
        [all ? 'shows' : 'changed']: lines }
    })
    finish(was)
    return out
  }
  // One "expect" of a beat -> '' when the page agrees, or what is wrong.
  function unmet(x) {
    if ('count' in x) {
      let n
      try { n = stage.querySelectorAll(x.count).length } catch { return `"${x.count}" is not a valid selector` }
      return n === x.is ? '' : `${n} element${n === 1 ? '' : 's'} match "${x.count}", but the story expects ${x.is}`
    }
    let node = $(x.in)
    try { node = node || stage.querySelector(x.in) } catch { node = null }
    if (!node) return `no element "${x.in}"`
    const want = squash(x.text), spaced = textOf(node, ' ')
    return spaced.includes(want) || textOf(node, '').includes(want) ? '' : `"${x.in}" does not show "${x.text}" (it shows "${spaced.slice(0, 110)}")`
  }

  // ---- self-test: play the story without sound and check the page in every state the voice makes
  window.__cx.extras.push(({ say, look, info }) => {
    const was = start()
    let states = 0, checks = 0
    B.forEach((b, i) => {
      if (b.wt.length !== b.caption.trim().split(/\s+/).length) say(`beat ${i + 1}: the caption has ${b.caption.trim().split(/\s+/).length} words but ${b.wt.length} word times`)
      if (b.wt.some((t, k) => k && t < b.wt[k - 1] - 0.01)) say(`beat ${i + 1}: the caption word times go backwards`)
      b.acts.forEach(x => {
        const ids = [].concat(x.press || x.set || x.show), gone = ids.filter(id => !$(id))
        if (gone.length) return say(`beat ${i + 1}: no element with id "${gone[0]}"`)
        if (x.t < b.t - 0.01 || x.t > b.end + 0.5) say(`beat ${i + 1}: an action is timed outside its beat`)
        const before = stage.innerHTML
        plan(x, 0).forEach(m => m.fn())
        if (!('show' in x) && stage.innerHTML === before) say(`beat ${i + 1}: ${'press' in x ? `pressing "${x.press}"` : `moving "${x.set}" to ${x.to}`} changes nothing on the page`)
        if ('set' in x && String($(x.set).value) !== String(x.to)) say(`beat ${i + 1}: "${x.set}" cannot take the value ${x.to} (it shows ${$(x.set).value})`)
      })
      b.expect.forEach(x => { checks++; const wrong = unmet(x); if (wrong) say(`beat ${i + 1}: ${wrong}`) })
      look(`the story is at beat ${i + 1}`); states++
    })
    const first = stage.innerHTML                     // a jump in time rebuilds the page, so two runs must agree
    for (const x of N.reset) plan(x, 0).forEach(m => m.fn())
    B.forEach(b => b.acts.forEach(x => plan(x, 0).forEach(m => m.fn())))
    if (stage.innerHTML !== first) say('the story gives a different page on its second run: the page must depend only on its controls (no Math.random, no clock), and "reset" must undo everything')
    if (isFinite(a.duration) && Math.abs(a.duration - N.seconds) > 0.6) say(`the audio is ${a.duration.toFixed(1)} s long but the story is timed for ${N.seconds} s`)
    if (a.error) say('the audio cannot be played')
    info.narration = { beats: B.length, actions: ACTS.length, statesChecked: states, expectsChecked: checks, seconds: N.seconds }
    finish(was)
  })
  window.__cx.story = story
  window.__cx.nar = { seek, play, tick, rebuild, at: () => ({ beat, done, dirty, begun, t: a.currentTime }) }
})()
