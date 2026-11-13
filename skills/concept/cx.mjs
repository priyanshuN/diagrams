// Build a concept page: one source fragment (controls, cards, a script that draws) -> one offline HTML file.
// usage: cx idea.concept.html [-o out.html] [--check] [--say] [--no-cache]
// Prints one JSON line: {"ok", "out", "kb", "warnings"}. Exit 2 = the source cannot be built.
// A source with a <script type="application/json" id="narration"> block becomes a narrated page: the walkthrough
// skill's voice reads each beat, and the page moves its own controls on the spoken words. --say = system voice.
import { spawnSync } from 'node:child_process'
import { homedir } from 'node:os'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const here = dirname(fileURLToPath(import.meta.url))
const args = process.argv.slice(2)
const check = args.includes('--check'), sysVoice = args.includes('--say')
const oAt = args.findIndex(a => a === '-o' || a === '--out')
const out = oAt >= 0 ? args[oAt + 1] : null
const src = args.find((a, i) => !a.startsWith('-') && (oAt < 0 || i !== oAt + 1))

function fail(msg) {
  process.stderr.write(`concept error:\n${msg}\n`)
  process.stdout.write(JSON.stringify({ ok: false, error: msg }) + '\n')
  process.exit(2)
}
if (!src) fail('usage: cx idea.concept.html [-o out.html] [--check]')

let raw
try { raw = readFileSync(src, 'utf8') } catch (e) { fail(`cannot read ${src}: ${e.message}`) }

// ---- header: <!--concept  title: ...  lead: ...  static: true  -->
const head = raw.match(/^\s*<!--concept\s*\n([\s\S]*?)-->/)
if (!head) fail('the file must start with a header:\n<!--concept\ntitle: ...\nlead: ...\n-->')
const meta = {}
for (const line of head[1].split('\n')) {
  const m = line.match(/^\s*([a-z]+)\s*:\s*(.+?)\s*$/)
  if (m) meta[m[1]] = m[2]
}
const unknown = Object.keys(meta).filter(k => !['title', 'lead', 'static'].includes(k))
if (unknown.length) fail(`unknown header key(s): ${unknown.join(', ')} (allowed: title, lead, static)`)
if (!meta.title || !meta.lead) fail('the header needs both "title" and "lead"')
let body = raw.slice(head[0].length).trim()
const isStatic = meta.static === 'true'

// ---- narration: beats the voice reads, and the control each beat moves
const NAR_KEYS = ['voice', 'speed', 'lexicon', 'reset', 'beats'], BEAT_KEYS = ['title', 'caption', 'say', 'do', 'expect']
const ACT_KEYS = ['at', 'press', 'times', 'every', 'set', 'to', 'show']
let nar = null
const narBlock = body.match(/<script\b[^>]*\bid\s*=\s*["']narration["'][^>]*>([\s\S]*?)<\/script>/)
if (narBlock) {
  body = body.replace(narBlock[0], '').trim()
  try { nar = JSON.parse(narBlock[1]) } catch (e) { fail(`the narration block is not valid JSON: ${e.message}`) }
  const bad = [], odd = (o, keys, where) => Object.keys(o).filter(k => !keys.includes(k)).forEach(k => bad.push(`${where}: unknown key "${k}" (allowed: ${keys.join(', ')})`))
  const hasId = id => new RegExp(`\\bid\\s*=\\s*["']${String(id).replace(/[^\w-]/g, '')}["']`).test(body)
  const act = (a, where, needAt) => {
    odd(a, needAt ? ACT_KEYS : ACT_KEYS.filter(k => k !== 'at'), where)
    const kinds = ['press', 'set', 'show'].filter(k => k in a)
    if (kinds.length !== 1) return bad.push(`${where}: give exactly one of "press", "set" or "show"`)
    if ('set' in a && !('to' in a)) bad.push(`${where}: "set" needs "to", the value the control moves to`)
    for (const id of [].concat(a[kinds[0]])) if (!hasId(id)) bad.push(`${where}: the page has no element with id "${id}"`)
    if ('times' in a && !(Number.isInteger(a.times) && a.times >= 1 && a.times <= 40)) bad.push(`${where}: "times" must be a whole number from 1 to 40`)
  }
  odd(nar, NAR_KEYS, 'narration')
  if (!Array.isArray(nar.beats) || nar.beats.length < 2 || nar.beats.length > 12) bad.push('narration: "beats" must be a list of 2 to 12 beats')
  else nar.beats.forEach((b, i) => {
    const where = `beat ${i + 1}`
    odd(b, BEAT_KEYS, where)
    if (!b.caption || typeof b.caption !== 'string') bad.push(`${where}: needs a "caption", the line the voice reads`)
    if (!b.title || b.title.length > 60) bad.push(`${where}: needs a "title" of 60 characters or fewer`)
    ;(b.do || []).forEach((a, k) => act(a, `${where}, action ${k + 1}`, true))
    if ('expect' in b && !Array.isArray(b.expect)) bad.push(`${where}: "expect" must be a list`)
    else (b.expect || []).forEach((x, k) => {            // what the page must show when the beat ends
      const w = `${where}, expect ${k + 1}`, text = typeof x.in === 'string' && typeof x.text === 'string' && x.text.trim(), count = typeof x.count === 'string' && Number.isInteger(x.is)
      odd(x, ['in', 'text', 'count', 'is'], w)
      if (!text === !count) bad.push(`${w}: give {"in": an element id or selector, "text": words the element must show} or {"count": a selector, "is": how many elements match}`)
    })
  })
  ;(nar.reset || []).forEach((a, k) => act(a, `reset, action ${k + 1}`, false))
  if (bad.length) fail(bad.join('\n'))
}

// ---- checks that need no browser
const warnings = []
const scripts = [...body.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1])
// A number the voice says must be a number the page shows: an "expect" of the beat, or a value the beat sets.
const numbers = v => String(v ?? '').match(/\d+(?:\.\d+)?/g) || []
if (nar) nar.beats.forEach((b, i) => {
  const known = new Set([...(b.expect || []).flatMap(x => [...numbers(x.text), ...numbers(x.is)]), ...(b.do || []).flatMap(a => [...numbers(a.to), ...numbers(a.times)])])
  const loose = [...new Set(numbers(`${b.title} ${b.caption}`))].filter(n => !known.has(n))
  if (loose.length) warnings.push(`beat ${i + 1} says ${loose.join(', ')}, but no "expect" of the beat has ${loose.length > 1 ? 'those numbers' : 'that number'}: add an "expect" with the page text that shows it, or reword the caption`)
})
if (nar && !/<button\b[^>]*\bid\s*=|<input\b|<select\b/.test(body) && !nar.beats.some(b => (b.do || []).some(a => 'show' in a))) warnings.push('the narration moves no control and points at nothing: give at least one beat a "do" action')
for (const code of scripts) {
  try { new vm.Script(code) } catch (e) { fail(`the page script does not parse: ${e.message}`) }
}
if (/<script\b[^>]*\bsrc\s*=|<link\b|@import|url\(\s*["']?https?:|(?:src|href)\s*=\s*["']https?:|\bfetch\s*\(|XMLHttpRequest/.test(body)) {
  warnings.push('the page loads something from outside (a script src, link, @import, URL or fetch); it must stay one offline file')
}
const hexes = [...new Set([...body.matchAll(/(?:[:=,(]\s*|["'`])(#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8}|[0-9a-fA-F]{3}))(?![0-9a-zA-Z_-])/g)].map(m => m[1]))]
if (hexes.length) warnings.push(`hard-coded colour(s) ${hexes.slice(0, 5).join(', ')}: use the tokens (var(--acc), var(--mut), ...) or a c-* class, or dark mode breaks`)
if (/\b(?:rgba?|hsla?)\s*\(/.test(body)) warnings.push('rgb() or hsl() colour found: use the tokens or a c-* class, or dark mode breaks')
for (const m of body.matchAll(/font(?:-size|Size)\s*[:=]\s*["'`]?\s*(\d+(?:\.\d+)?)px/g)) {
  if (+m[1] < 11) warnings.push(`font-size ${m[1]}px is below the 11 px minimum`)
}
for (const m of body.matchAll(/<svg\b[^>]*>/g)) {
  if (!/viewBox\s*=/.test(m[0])) warnings.push('an <svg> has no viewBox, so it cannot scale to a phone')
  if (!/class\s*=\s*["'`][^"'`]*\bpic\b/.test(m[0])) warnings.push('an <svg> lacks class="pic", so it misses the shared picture styles')
  if (!/role\s*=\s*["'`]img/.test(m[0]) || !/aria-label\s*=/.test(m[0])) warnings.push('an <svg> needs role="img" and an aria-label that says what it shows')
}
if (!/<svg\b/.test(body)) warnings.push('the page has no <svg> picture')
if (!isStatic && !/<(?:input|select|button)\b/.test(body)) warnings.push('the page has no control: give the picture the control the real system has, or set "static: true" in the header')
if (!/class\s*=\s*["'`][^"'`]*\bverdict\b/.test(body)) warnings.push('nothing has class="verdict": state the result in one plain line under the picture')
if (/<h1\b/.test(body)) warnings.push('the body has an <h1>; the page shell already writes the title from the header')
if (/position\s*:\s*fixed/.test(body)) warnings.push('position:fixed found; keep everything in the page flow')

// ---- assemble
const e = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
const css = readFileSync(join(here, '..', 'flow', 'tokens.css'), 'utf8') + readFileSync(join(here, 'concept.css'), 'utf8')
// ---- voice: one audio clip for all beats, a start time for each caption word, and the time of each "at" phrase
let narBar = '', narJs = '', narInfo = null
if (nar) {
  const walk = join(here, '..', 'walkthrough')
  const req = { voice: nar.voice, speed: nar.speed, lexicon: nar.lexicon, check, say: sysVoice, cache: !args.includes('--no-cache'),
    lines: nar.beats.map(b => ({ caption: b.caption, say: b.say, cues: (b.do || []).filter(a => a.at).map(a => a.at) })) }
  const run = spawnSync('uv', ['run', '-q', '--frozen', '--project', walk, join(walk, 'voice.py')], {
    input: JSON.stringify(req), encoding: 'utf8', maxBuffer: 256 * 1024 * 1024,
    env: { ...process.env, UV_PROJECT_ENVIRONMENT: join(homedir(), '.local', 'share', 'narrated-walkthrough', 'venv') } })
  if (run.error) fail(`the voice did not start (${run.error.message}); a narrated page needs "uv" and the walkthrough skill next to this one`)
  let res
  try { res = JSON.parse(run.stdout.trim().split('\n').pop()) } catch { fail(`the voice gave no result:\n${run.stderr.slice(-2000)}`) }
  if (!res.ok) fail((res.errors || ['the voice failed']).join('\n'))
  for (const [i, ln] of res.lines.entries()) {
    if (/[×÷%=<>→←≈]|\d\s*[-+*/]\s*\d/.test(ln.spoken)) warnings.push(`beat ${i + 1} is spoken with a symbol in it ("${ln.spoken.slice(0, 60)}"): give the beat a "say" with the words written out`)
  }
  if (!check) {
    const beats = nar.beats.map((b, i) => {
      const ln = res.lines[i]
      let c = 0
      return { t: ln.t, end: Math.round((ln.t + ln.dur) * 1000) / 1000, title: b.title, caption: b.caption, wt: ln.wt, expect: b.expect || [],
        acts: (b.do || []).map(a => ({ ...a, at: undefined, t: a.at ? ln.cues[c++] : ln.t })) }
    })
    const data = { beats, reset: nar.reset || [], seconds: res.seconds, engine: res.engine }
    narInfo = { beats: beats.length, seconds: res.seconds, actions: beats.reduce((n, b) => n + b.acts.length, 0), engine: res.engine, linesCached: res.cached, linesSpoken: res.spoken }
    narBar = readFileSync(join(here, 'narrate.html'), 'utf8').replace('{{AUDIO}}', `data:${res.mime};base64,${res.audio}`)
    narJs = `<script>window.__nar=${JSON.stringify(data).replace(/</g, '\\u003c')}\n${readFileSync(join(here, 'narrate.js'), 'utf8')}</script>`
  }
}
const parts = { TITLE: e(meta.title), LEAD: e(meta.lead), CSS: css + (nar ? readFileSync(join(here, 'narrate.css'), 'utf8') : ''), KIT: readFileSync(join(here, 'kit.js'), 'utf8'), BODY: body, STATIC: isStatic ? ' data-static' : '', NARBAR: narBar, NARJS: narJs }
const page = readFileSync(join(here, 'page.html'), 'utf8').replace(/\{\{([A-Z]+)\}\}/g, (_, k) => parts[k])
const target = resolve(out || src.replace(/\.concept\.html$|\.html$/, '') + (out ? '' : '.html'))
if (target === resolve(src)) fail('the output would overwrite the source; name the source *.concept.html or pass -o')
if (!check) writeFileSync(target, page)
process.stdout.write(JSON.stringify({ ok: warnings.length === 0, out: check ? null : target, kb: Math.round(page.length / 102.4) / 10, ...(narInfo ? { narration: narInfo } : {}), warnings }) + '\n')
