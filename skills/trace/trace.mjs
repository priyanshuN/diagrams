// diagrams:trace: a recorded run (a trace file) -> a Mermaid sequence diagram, or two runs -> their diff.
//   trace <run>                    Mermaid on stdout (pipe it into flow's fd, or use --text)
//   trace <a> <b>                  diff: the steps of b against a, marked [+] added, [-] removed, [~] changed
//   --text                         render through flow's fd: Unicode text for a ```text fence
//   --json                         the parsed steps (one run) or the diff rows (two runs), for other tools
//   --ignore k1,k2                 value keys left out of the diff (ids and times that change every run)
//   --context N                    diff only: keep N unchanged steps around each change, fold the rest
//   --values none|short|all        how many step values to show on an arrow (default short)
//   --time                         prefix each arrow with the time since the first step (+120ms)
// Exit code: 0 ok (or no differences), 1 differences found, 2 error. Notes go to stderr.
import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const KINDS = { sync: '->>', reply: '-->>', async: '-)' }
const MAX_LABEL = 60, MAX_VALUE = 24, SHORT_VALUES = 3

// ---- reading
// A trace is {title?, participants?, ignore?, steps: [...]}, a bare array of steps, or JSONL (one step per line).
export function readTrace(raw, name = 'trace') {
  const text = raw.trim()
  let doc
  if (text.startsWith('{') && text.includes('\n{')) doc = { steps: text.split('\n').filter(l => l.trim()).map(l => JSON.parse(l)) }
  else doc = JSON.parse(text)
  if (Array.isArray(doc)) doc = { steps: doc }
  if (!Array.isArray(doc.steps) || !doc.steps.length) throw new Error(`${name} has no steps`)
  const steps = doc.steps.map((s, i) => {
    if (!s.from || !s.to || s.label == null) throw new Error(`${name} step ${i + 1} needs "from", "to" and "label"`)
    const kind = s.kind ?? 'sync'
    if (!KINDS[kind]) throw new Error(`${name} step ${i + 1}: kind "${kind}" is not one of ${Object.keys(KINDS).join(', ')}`)
    return { from: String(s.from), to: String(s.to), label: String(s.label), kind, t: s.t ?? null,
             values: s.values ?? {}, note: s.note ?? null }
  })
  return { title: doc.title ?? null, participants: doc.participants ?? [], ignore: doc.ignore ?? [], steps }
}

// ---- diff: align the two runs on (from, to, label), then compare values of the aligned steps
const key = s => `${s.from}\u0000${s.to}\u0000${s.label}`

function align(a, b) {
  const n = a.length, m = b.length
  const L = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1))
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      L[i][j] = key(a[i]) === key(b[j]) ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1])
  const rows = []
  let i = 0, j = 0
  while (i < n || j < m) {
    if (i < n && j < m && key(a[i]) === key(b[j])) rows.push({ a: a[i++], b: b[j++] })
    else if (j < m && (i === n || L[i][j + 1] >= L[i + 1][j])) rows.push({ b: b[j++] })
    else rows.push({ a: a[i++] })
  }
  return rows
}

const same = (x, y) => JSON.stringify(x) === JSON.stringify(y)

export function diffTraces(A, B, ignore = []) {
  const skip = new Set([...ignore, ...A.ignore, ...B.ignore])
  const rows = align(A.steps, B.steps).map(r => {
    if (!r.a) return { op: 'added', step: r.b }
    if (!r.b) return { op: 'removed', step: r.a }
    const keys = [...new Set([...Object.keys(r.a.values), ...Object.keys(r.b.values)])].filter(k => !skip.has(k))
    const changes = keys.filter(k => !same(r.a.values[k], r.b.values[k]))
                        .map(k => ({ key: k, before: r.a.values[k] ?? null, after: r.b.values[k] ?? null }))
    if (r.a.kind !== r.b.kind) changes.unshift({ key: 'kind', before: r.a.kind, after: r.b.kind })
    return { op: changes.length ? 'changed' : 'same', step: r.b, before: r.a, changes }
  })
  const summary = { added: 0, removed: 0, changed: 0, same: 0 }
  for (const r of rows) summary[r.op]++
  return { summary, differs: summary.added + summary.removed + summary.changed > 0, rows }
}

// ---- Mermaid
const clip = (s, max) => (s.length > max ? s.slice(0, max - 1) + '…' : s)
// Mermaid reads ";" as a statement end and "#" as an entity code; a newline would end the message
const safe = s => String(s).replace(/\s*[;\n\r]+\s*/g, ', ').replace(/#/g, 'no.').trim()
const show = v => clip(typeof v === 'string' ? v : JSON.stringify(v), MAX_VALUE)
const idOf = s => s.replace(/[^\w.-]/g, '_')

function valueText(values, mode, skip) {
  if (mode === 'none') return ''
  const pairs = Object.entries(values).filter(([k]) => !skip.has(k))
  const shown = mode === 'all' ? pairs : pairs.slice(0, SHORT_VALUES)
  if (!shown.length) return ''
  const more = pairs.length - shown.length
  return ` (${shown.map(([k, v]) => `${k}=${show(v)}`).join(', ')}${more > 0 ? `, +${more}` : ''})`
}

function elapsed(steps) {
  const ms = steps.map(s => (s.t == null ? NaN : typeof s.t === 'number' ? s.t : Date.parse(s.t)))
  const t0 = ms.find(x => !Number.isNaN(x))
  return ms.map(x => (Number.isNaN(x) || t0 === undefined ? '' : fmtMs(x - t0) + ' '))
}
const fmtMs = d => (d < 1000 ? `+${d}ms` : d < 60000 ? `+${(d / 1000).toFixed(1)}s` : `+${(d / 60000).toFixed(1)}m`)

function header(lines, participants, steps) {
  const named = new Map(participants.map(p => [String(p.id), p.label ?? p.id]))
  const order = [...named.keys()]
  for (const s of steps) for (const id of [s.from, s.to]) if (!order.includes(id)) order.push(id)
  for (const id of order) {
    const label = named.get(id)
    lines.push(label && label !== id ? `  participant ${idOf(id)} as ${safe(label)}` : `  participant ${idOf(id)}`)
  }
}

const arrow = (s, label) => `  ${idOf(s.from)}${KINDS[s.kind]}${idOf(s.to)}: ${safe(clip(label, MAX_LABEL))}`

export function traceToMermaid(T, { values = 'short', time = false, ignore = [] } = {}) {
  const skip = new Set(ignore)
  const lines = ['sequenceDiagram']
  header(lines, T.participants, T.steps)
  const when = time ? elapsed(T.steps) : T.steps.map(() => '')
  T.steps.forEach((s, i) => {
    lines.push(arrow(s, when[i] + s.label + valueText(s.values, values, skip)))
    if (s.note) lines.push(`  Note over ${idOf(s.to)}: ${safe(clip(s.note, MAX_LABEL))}`)
  })
  return lines.join('\n') + '\n'
}

const changeText = cs => ` (${cs.map(c => `${c.key}: ${show(c.before)} → ${show(c.after)}`).join(', ')})`

export function diffToMermaid(A, B, D, { context = Infinity } = {}) {
  const lines = ['sequenceDiagram']
  header(lines, [...A.participants, ...B.participants], D.rows.map(r => r.step))
  const near = D.rows.map((_, i) => D.rows.slice(Math.max(0, i - context), i + context + 1).some(r => r.op !== 'same'))
  let folded = []
  const flush = () => {
    if (!folded.length) return
    lines.push(`  Note over ${idOf(folded[0].from)}: ${folded.length} unchanged step${folded.length > 1 ? 's' : ''}`)
    folded = []
  }
  D.rows.forEach((r, i) => {
    if (r.op === 'same' && !near[i]) return void folded.push(r.step)
    flush()
    const mark = { added: '[+] ', removed: '[-] ', changed: '[~] ', same: '' }[r.op]
    lines.push(arrow(r.step, mark + r.step.label + (r.op === 'changed' ? changeText(r.changes) : '')))
  })
  flush()
  return lines.join('\n') + '\n'
}

// ---- command line
function main(argv) {
  const opt = (name, dflt) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : dflt }
  const valued = new Set(['--ignore', '--context', '--values'])
  const files = argv.filter((a, i) => !a.startsWith('--') && !valued.has(argv[i - 1]))
  if (files.length < 1 || files.length > 2) throw new Error('usage: trace <run> [<other run>] [--text|--json] [--ignore k1,k2] [--context N] [--values none|short|all] [--time]')
  const ignore = (opt('--ignore', '') || '').split(',').map(s => s.trim()).filter(Boolean)
  const values = opt('--values', 'short')
  if (!['none', 'short', 'all'].includes(values)) throw new Error(`--values must be none, short or all, not "${values}"`)
  const runs = files.map(f => readTrace(readFileSync(f === '-' ? 0 : f, 'utf8'), f))

  let mermaid, code = 0
  if (runs.length === 1) {
    if (argv.includes('--json')) return void process.stdout.write(JSON.stringify(runs[0]) + '\n')
    mermaid = traceToMermaid(runs[0], { values, time: argv.includes('--time'), ignore: [...ignore, ...runs[0].ignore] })
  } else {
    const D = diffTraces(runs[0], runs[1], ignore)
    const s = D.summary
    process.stderr.write(`trace: ${s.added} added, ${s.removed} removed, ${s.changed} changed, ${s.same} same\n`)
    code = D.differs ? 1 : 0
    if (argv.includes('--json')) { process.stdout.write(JSON.stringify(D) + '\n'); return code }
    const context = opt('--context')
    mermaid = diffToMermaid(runs[0], runs[1], D, { context: context == null ? Infinity : Number(context) })
  }
  if (!argv.includes('--text')) { process.stdout.write(mermaid); return code }
  const fd = join(dirname(fileURLToPath(import.meta.url)), '..', 'flow', 'fd.mjs')
  const r = spawnSync(process.execPath, [fd, '-'], { input: mermaid, encoding: 'utf8' })
  process.stdout.write(r.stdout)
  process.stderr.write(r.stderr)
  if (r.status !== 0) throw new Error('flow fd could not render the diagram')
  return code
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try { process.exitCode = main(process.argv.slice(2)) ?? 0 }
  catch (err) { process.stderr.write(`trace: error: ${err.message}\n`); process.exitCode = 2 }
}
