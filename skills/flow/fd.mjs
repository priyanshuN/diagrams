// diagrams:flow: Mermaid text -> Unicode box art for chat, or -> JSON for other tools.
//   fd <file|->            Unicode text (paste it into a ```text fence)
//   fd <file> --ascii      plain ASCII (+ - | >) for limited terminals
//   fd <file> --json       the parsed diagram, for diagrams:walkthrough
//   fd --lint <file|->     check a hand-drawn text diagram (a ```text fence is fine) before pasting it
// Input: a .mmd file, a Markdown file with a ```mermaid fence, a scene .json with a "diagram" key, or stdin.
// Notes about fit (width, height, unsupported syntax) go to stderr; stdout carries only the result.
import { readFileSync } from 'node:fs'
import { parseMermaid, renderMermaidASCII } from 'beautiful-mermaid'
import { lint } from './lint.mjs'

const MAX_COLS = 90, MAX_ROWS = 45
const args = process.argv.slice(2)
const flag = f => args.includes(f)
const file = args.find(a => !a.startsWith('--')) ?? '-'
const notes = []

function readSource(path) {
  const raw = readFileSync(path === '-' ? 0 : path, 'utf8')
  if (path.endsWith('.json')) {
    const d = JSON.parse(raw).diagram
    if (typeof d !== 'string') throw new Error(`${path} has no "diagram" string`)
    return d
  }
  const fence = raw.match(/```mermaid\s*\n([\s\S]*?)```/)
  return (fence ? fence[1] : raw).trim()
}

// ---- sequence parser (the library renders sequences but does not export their parser)
const ARROW = /^([\w.-]+?)\s*(-->>|->>|--\)|-\)|--x|-x|-->|->)\s*[+-]?\s*([\w.-]+)\s*:\s*(.*)$/
const NOTE = /^note\s+(over|left of|right of)\s+([\w.-]+)(?:\s*,\s*([\w.-]+))?\s*:\s*(.*)$/i
const PART = /^(participant|actor)\s+([\w.-]+)(?:\s+as\s+(.+))?$/i
const BLOCK = /^(alt|else|opt|loop|par|and|critical|break|rect|end)\b/i
const IGNORE = /^(autonumber|activate|deactivate|%%|title\b)/i

function parseSequence(src) {
  const participants = [], messages = [], seqNotes = []
  const ensure = (id, label) => {
    let p = participants.find(q => q.id === id)
    if (!p) participants.push(p = { id, label: label ?? id })
    else if (label) p.label = label
    return p
  }
  for (const [n, line0] of src.split('\n').slice(1).entries()) {
    const line = line0.trim()
    if (!line || IGNORE.test(line)) continue
    let m
    if ((m = line.match(PART))) ensure(m[2], m[3]?.trim())
    else if ((m = line.match(ARROW))) {
      ensure(m[1]); ensure(m[3])
      const a = m[2]
      messages.push({ n: messages.length + 1, from: m[1], to: m[3], label: m[4].trim(),
                      kind: a.endsWith(')') ? 'async' : a.startsWith('--') ? 'reply' : 'sync' })
    } else if ((m = line.match(NOTE))) {
      seqNotes.push({ after: messages.length, place: m[1].toLowerCase(), over: [m[2], m[3]].filter(Boolean), text: m[4].trim() })
    } else if (BLOCK.test(line)) {
      notes.push(`line ${n + 2}: "${line.split(/\s/)[0]}" blocks render badly as text; write the branch as a Note instead`)
    } else {
      throw new Error(`line ${n + 2}: cannot read "${line}"`)
    }
  }
  if (!messages.length) throw new Error('the sequence has no messages')
  return { type: 'sequence', participants, messages, notes: seqNotes }
}

function parseFlow(src) {
  const g = parseMermaid(src)
  // the library keeps a node's first mention: `a --> pay` before `pay[Payment API]` leaves the label "pay"
  const late = [...g.nodes.values()].filter(n => n.label === n.id &&
    new RegExp(`(^|[\\s;&|>-])${n.id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*[\\[({>]`, 'm').test(src))
  if (late.length) throw new Error(`define ${late.map(n => `"${n.id}"`).join(', ')} with its label before the first arrow that uses it`)
  return {
    type: 'flow', direction: g.direction,
    nodes: [...g.nodes.values()].map(({ id, label, shape }) => ({ id, label, shape })),
    edges: g.edges.map(e => ({ from: e.source, to: e.target, label: e.label ?? '', style: e.style })),
    groups: g.subgraphs.map(s => ({ id: s.id, label: s.label, nodes: s.nodeIds })),
  }
}

const isSequence = src => /^sequenceDiagram\b/.test(src)

function renderText(src, ascii) {
  const opts = { colorMode: 'none', useAscii: ascii, paddingX: 3, paddingY: 3, boxBorderPadding: 0 }
  let out = renderMermaidASCII(src, opts).split('\n').map(l => l.replace(/\s+$/, ''))
  if (isSequence(src)) {
    // the library repeats the participant boxes at the bottom; drop them to save 3 rows
    // compare the name rows only: the box borders differ (┬ above the lifelines, ┴ below)
    const last = out.map(l => l.trimEnd()).filter(Boolean)
    if (last.length > 8 && last[1] === last.at(-2)) out = out.slice(0, out.lastIndexOf(last.at(-3)))
  } else {
    // where two arrows merge into one box, the library draws the head one column right of the
    // line ("│▼"); put the head on the line so it points into the box, not past its edge
    out = out.map(l => l.replace(/[│┆]▼(?=\s|$)/g, '▼ ').replace(/\|v(?=\s|$)/g, 'v ').trimEnd())
  }
  while (out.length && !out[0]) out.shift()
  while (out.length && !out.at(-1)) out.pop()
  return out
}

try {
  if (flag('--lint')) {
    const res = lint(readFileSync(file === '-' ? 0 : file, 'utf8'), { maxCols: MAX_COLS, maxRows: MAX_ROWS })
    for (const e of res.errors) process.stderr.write(`fd: row ${e.row}, col ${e.col}: ${e.msg}\n`)
    for (const n of res.notes) process.stderr.write(`fd: note: ${n}\n`)
    process.stderr.write(`fd: lint ${res.ok ? 'ok' : `found ${res.errors.length + res.notes.length} problem(s)`}: ${res.width} cols x ${res.rows} rows\n`)
    process.exit(res.ok ? 0 : 1)
  }
  let src = readSource(file)
  if (flag('--json')) {
    process.stdout.write(JSON.stringify(isSequence(src) ? parseSequence(src) : parseFlow(src)) + '\n')
  } else {
    if (isSequence(src)) parseSequence(src)          // validates and collects notes about blocks
    else parseFlow(src)                              // catches nodes used before their definition
    let lines = renderText(src, flag('--ascii'))
    let width = Math.max(...lines.map(l => [...l].length))
    const lr = src.match(/^(graph|flowchart)\s+(LR|RL)\b/)
    if (lr && width > MAX_COLS) {
      // left-to-right text layouts get wide and misroute arrows; top-to-bottom stays clean
      src = src.replace(lr[0], `${lr[1]} TD`)
      lines = renderText(src, flag('--ascii'))
      width = Math.max(...lines.map(l => [...l].length))
      notes.push(`switched ${lr[2]} to TD: the left-to-right text was over ${MAX_COLS} columns`)
    }
    if (width > MAX_COLS) notes.push(`${width} columns is wider than ${MAX_COLS}: shorten labels, or split the diagram`)
    if (lines.length > MAX_ROWS) notes.push(`${lines.length} rows is taller than ${MAX_ROWS}: split it, or offer an HTML page`)
    process.stdout.write(lines.join('\n') + '\n')
    process.stderr.write(`fd: ${width} cols x ${lines.length} rows\n`)
  }
  for (const n of notes) process.stderr.write(`fd: note: ${n}\n`)
} catch (err) {
  process.stderr.write(`fd: error: ${err.message}\n`)
  process.exit(1)
}
