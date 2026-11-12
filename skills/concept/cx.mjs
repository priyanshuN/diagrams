// Build a concept page: one source fragment (controls, cards, a script that draws) -> one offline HTML file.
// usage: cx idea.concept.html [-o out.html] [--check]
// Prints one JSON line: {"ok", "out", "kb", "warnings"}. Exit 2 = the source cannot be built.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const here = dirname(fileURLToPath(import.meta.url))
const args = process.argv.slice(2)
const check = args.includes('--check')
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
const body = raw.slice(head[0].length).trim()
const isStatic = meta.static === 'true'

// ---- checks that need no browser
const warnings = []
const scripts = [...body.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1])
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
const parts = { TITLE: e(meta.title), LEAD: e(meta.lead), CSS: css, KIT: readFileSync(join(here, 'kit.js'), 'utf8'), BODY: body, STATIC: isStatic ? ' data-static' : '' }
const page = readFileSync(join(here, 'page.html'), 'utf8').replace(/\{\{([A-Z]+)\}\}/g, (_, k) => parts[k])
const target = resolve(out || src.replace(/\.concept\.html$|\.html$/, '') + (out ? '' : '.html'))
if (target === resolve(src)) fail('the output would overwrite the source; name the source *.concept.html or pass -o')
if (!check) writeFileSync(target, page)
process.stdout.write(JSON.stringify({ ok: warnings.length === 0, out: check ? null : target, kb: Math.round(page.length / 102.4) / 10, warnings }) + '\n')
