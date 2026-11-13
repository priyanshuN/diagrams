// kit: the small helpers every concept page gets, plus the page self-test.
// The build inlines this file before the page's own script. Helpers return SVG or HTML strings.
(function () {
  'use strict'
  const f = n => (Math.round(n * 10) / 10).toString()
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
  const kit = { esc }

  kit.el = id => document.getElementById(id)
  kit.gcd = (a, b) => { a = Math.abs(a); b = Math.abs(b); while (b) [a, b] = [b, a % b]; return a }
  kit.clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))
  // Every number that reaches the screen goes through fmt, so float noise (0.30000000000000004) never shows.
  kit.fmt = (n, digits = 0) => Number(n).toLocaleString('en', { minimumFractionDigits: digits, maximumFractionDigits: digits })
  // scale(0, 100, 30, 290) maps a value in 0..100 to an x in 30..290.
  kit.scale = (d0, d1, r0, r1) => v => r0 + (v - d0) / (d1 - d0 || 1) * (r1 - r0)
  // A repeatable random source, so a picture is the same on every load: const rnd = kit.random(7); rnd() -> 0..1
  kit.random = seed => { let s = seed >>> 0 || 1; return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296 }

  // Ring geometry. 0 degrees is the top of the ring, and angles grow clockwise.
  kit.polar = (cx, cy, r, deg) => { const a = (deg - 90) * Math.PI / 180; return [cx + r * Math.cos(a), cy + r * Math.sin(a)] }
  kit.arc = (cx, cy, r, d0, d1) => {
    const [x0, y0] = kit.polar(cx, cy, r, d0), [x1, y1] = kit.polar(cx, cy, r, d1)
    return `M${f(x0)} ${f(y0)} A${r} ${r} 0 ${Math.abs(d1 - d0) > 180 ? 1 : 0} ${d1 > d0 ? 1 : 0} ${f(x1)} ${f(y1)}`
  }

  // The arrowhead marker. Put kit.defs() once at the start of each <svg>.
  kit.defs = () => '<defs><marker id="kit-arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">' +
    '<path d="M2 1.5L8.5 5L2 8.5" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>'
  // A straight arrow from point a to point b that stops `pad` px short of both ends, so a line never runs into a shape.
  kit.arrow = (a, b, { pad = 0, cls = 'link', opacity = 1, head = true } = {}) => {
    const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len
    return `<line class="${cls}" x1="${f(a[0] + ux * pad)}" y1="${f(a[1] + uy * pad)}" x2="${f(b[0] - ux * pad)}" y2="${f(b[1] - uy * pad)}"` +
      ` opacity="${opacity}"${head ? ' marker-end="url(#kit-arrow)"' : ''}/>`
  }

  // A small bar chart of counts. Bars scale to the tallest value, or to `max` when given: pass the same max to
  // two charts so the reader can compare them. flagZero paints an empty slot red; peak paints the tallest bars red.
  kit.bars = (values, { flagZero = false, peak = false, max = 0 } = {}) => {
    const tallest = Math.max(0, ...values), top = Math.max(1, max, tallest)
    return '<div class="bars">' + values.map(v =>
      `<i${v === 0 && flagZero ? ' class="zero"' : peak && v === tallest && v > 1 ? ' class="peak"' : ''} style="height:${Math.round(v / top * 100)}%"></i>`).join('') + '</div>'
  }

  // Wire controls: bind(['parts', 'stride'], redraw) calls redraw on every slider move, select change or button click.
  kit.bind = (ids, fn) => ids.forEach(id => {
    const node = kit.el(id)
    if (!node) throw new Error(`kit.bind: no element with id "${id}"`)
    node.addEventListener(node.tagName === 'BUTTON' ? 'click' : 'input', () => fn(node))
  })
  // A Play / Pause button: play('play', tick, 700) calls tick every 700 ms while it runs.
  const players = []
  kit.play = (id, tick, ms = 700) => {
    const btn = kit.el(id), idle = btn.textContent
    let timer = null
    const stop = () => { if (timer) { clearInterval(timer); timer = null; btn.textContent = idle } }
    btn.addEventListener('click', () => { if (timer) return stop(); btn.textContent = 'Pause'; timer = setInterval(tick, ms) })
    players.push(stop)
    return { stop }
  }
  kit.stopAll = () => players.forEach(stop => stop())

  // ---------------------------------------------------------------- theme button
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.querySelector('button.theme')
    if (btn) btn.addEventListener('click', () => {
      const root = document.documentElement
      const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches
      root.dataset.theme = dark ? 'light' : 'dark'
    })
  })

  // ---------------------------------------------------------------- self-test
  // Run JSON.stringify(window.__cx.selftest()) in the browser pane. It moves every control to its ends and
  // checks the page after each move: script errors, sideways scroll, cut-off or overlapping picture text,
  // text that is too small or too large, content wider than its card, and controls that change nothing.
  const errors = [], extras = []
  addEventListener('error', e => errors.push(String(e.message)))
  addEventListener('unhandledrejection', e => errors.push(String(e.reason)))

  function selftest() {
    const stage = kit.el('stage'), problems = new Map()     // message -> the states it showed in
    const name = c => c.id || c.textContent.trim().slice(0, 24) || c.tagName.toLowerCase()
    const say = (msg, when) => { if (!problems.has(msg)) problems.set(msg, []); if (when) problems.get(msg).push(when) }
    const fire = (c, type) => c.dispatchEvent(new Event(type, { bubbles: true }))
    let texts = 0

    function look(when) {
      if (document.documentElement.scrollWidth > innerWidth + 1) say(`the page scrolls sideways at ${innerWidth} px wide`, when)
      stage.querySelectorAll('svg').forEach(svg => {
        const box = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal
        if (!vb || !vb.width) return say('an <svg> has no viewBox')
        const k = box.width / vb.width
        if (k > 1.31) say(`a picture is drawn at ${k.toFixed(2)} times its viewBox size (${Math.round(vb.width)} wide), so its text is larger than the page text; cap it with style="max-width:${Math.round(vb.width * 1.3)}px"`, when)
        const seen = []
        svg.querySelectorAll('text').forEach(t => {
          const s = t.textContent.trim()
          if (!s) return
          texts++
          const r = t.getBoundingClientRect()
          if (r.left < box.left - 1 || r.right > box.right + 1 || r.top < box.top - 1 || r.bottom > box.bottom + 1) say(`picture text "${s}" is cut off by the edge of its picture`, when)
          const px = parseFloat(getComputedStyle(t).fontSize) * k
          if (px < 10) say(`picture text "${s}" is ${px.toFixed(1)} px on screen; the minimum is 10 px`, when)
          for (const o of seen) {
            const w = Math.min(r.right, o.r.right) - Math.max(r.left, o.r.left), h = Math.min(r.bottom, o.r.bottom) - Math.max(r.top, o.r.top)
            if (w > 2 && h > 2 && w * h > 0.2 * Math.min(r.width * r.height, o.r.width * o.r.height)) say(`picture texts "${o.s}" and "${s}" overlap`, when)
          }
          seen.push({ s, r })
        })
      })
      stage.querySelectorAll('*').forEach(node => {
        if (node.closest('svg') || node.tagName === 'SCRIPT') return
        const own = [...node.childNodes].some(c => c.nodeType === 3 && c.textContent.trim())
        if (own && parseFloat(getComputedStyle(node).fontSize) < 11) say(`text "${node.textContent.trim().slice(0, 30)}" is smaller than 11 px`, when)
        if (node.classList.contains('card') && node.scrollWidth > node.clientWidth + 1) say('content is wider than its card', when)
      })
    }

    look('')
    const ranges = [...stage.querySelectorAll('input[type=range]')]
    const selects = [...stage.querySelectorAll('select')]
    const buttons = [...stage.querySelectorAll('button:not([data-skip])')]
    const set = (c, v) => { c.value = v; fire(c, 'input'); fire(c, 'change') }
    for (const c of ranges) {
      const start = c.value, before = stage.innerHTML
      let moved = false
      for (const v of [c.min, c.max]) { set(c, v); moved = moved || stage.innerHTML !== before; look(`${name(c)} = ${v}`) }
      if (!moved) say(`the slider "${name(c)}" changes nothing`)
      set(c, start)
    }
    for (const c of selects) {
      const start = c.value, before = stage.innerHTML
      let moved = false
      for (const o of c.options) { set(c, o.value); moved = moved || stage.innerHTML !== before; look(`${name(c)} = ${o.value}`) }
      if (!moved && c.options.length > 1) say(`the menu "${name(c)}" changes nothing`)
      set(c, start)
    }
    const dead = []
    for (const b of buttons) {
      const before = stage.innerHTML
      b.click()
      if (stage.innerHTML === before) dead.push(b)
      look(`"${name(b)}" is clicked`)
    }
    kit.stopAll()
    if (dead.length) {                       // a button can be a no-op in one state (Reset at the start): try another state
      const starts = ranges.map(c => c.value)
      ranges.forEach(c => set(c, c.min))
      for (const b of dead) {
        const before = stage.innerHTML
        b.click()
        if (stage.innerHTML === before) say(`the button "${name(b)}" changes nothing`)
      }
      ranges.forEach((c, i) => set(c, starts[i]))
      kit.stopAll()
    }
    const info = {}
    for (const extra of extras) extra({ say, look, info })       // a narrated page checks its story here
    const isStatic = document.body.hasAttribute('data-static')
    if (!isStatic && !ranges.length && !selects.length && !buttons.length) say('the page has no control; give it the control the real system has, or mark it static')
    if (!stage.querySelector('.verdict')) say('no element has class "verdict"; state the result in one plain line under the picture')
    if (!stage.querySelector('svg')) say('the page has no picture')
    errors.forEach(e => say(`script error: ${e}`))
    const root = document.documentElement
    return {
      ok: problems.size === 0, width: innerWidth,
      theme: root.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
      checked: { pictureTexts: texts, sliders: ranges.length, menus: selects.length, buttons: buttons.length, ...info },
      problems: [...problems].slice(0, 30).map(([msg, when]) => !when.length ? msg : `${msg} (when ${when[0]}${when.length > 1 ? `, and in ${when.length - 1} more states` : ''})`),
    }
  }

  window.kit = kit
  window.__cx = { selftest, errors, extras }
})()
