// Run: node --test skills/trace/*.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { readTrace, diffTraces, traceToMermaid, diffToMermaid } from './trace.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const ex = f => join(here, 'examples', f)
const step = (from, to, label, extra = {}) => ({ from, to, label, ...extra })
const run = (...steps) => readTrace(JSON.stringify(steps))

test('reads an object, a bare array and JSONL', () => {
  const s = [step('a', 'b', 'x'), step('b', 'a', 'y', { kind: 'reply' })]
  assert.equal(readTrace(JSON.stringify({ steps: s })).steps.length, 2)
  assert.equal(readTrace(JSON.stringify(s)).steps.length, 2)
  assert.equal(readTrace(s.map(x => JSON.stringify(x)).join('\n')).steps[1].kind, 'reply')
})

test('rejects a step without from, to or label, and an unknown kind', () => {
  assert.throws(() => readTrace('[{"from":"a","to":"b"}]'), /needs "from", "to" and "label"/)
  assert.throws(() => readTrace('[{"from":"a","to":"b","label":"x","kind":"fast"}]'), /kind "fast"/)
  assert.throws(() => readTrace('{"steps":[]}'), /no steps/)
})

test('a run against itself has no differences', () => {
  const A = readTrace(readFileSync(ex('order.a.json'), 'utf8'))
  const D = diffTraces(A, A)
  assert.equal(D.differs, false)
  assert.deepEqual(D.summary, { added: 0, removed: 0, changed: 0, same: 6 })
})

test('the example runs differ by one changed and one added step; orderId is ignored', () => {
  const A = readTrace(readFileSync(ex('order.a.json'), 'utf8'))
  const B = readTrace(readFileSync(ex('order.b.json'), 'utf8'))
  const D = diffTraces(A, B)
  assert.deepEqual(D.summary, { added: 1, removed: 0, changed: 1, same: 5 })
  const changed = D.rows.find(r => r.op === 'changed')
  assert.deepEqual(changed.changes, [{ key: 'status', before: 'PAID', after: 'FAILED' }])
  assert.equal(D.rows.at(-1).op, 'added')
  assert.equal(D.rows.at(-1).step.label, 'order.retry')
})

test('without the ignore list, an id that changes every run counts as a change', () => {
  const A = run(step('a', 'b', 'x', { values: { id: 1 } }))
  const B = run(step('a', 'b', 'x', { values: { id: 2 } }))
  assert.equal(diffTraces(A, B).summary.changed, 1)
  assert.equal(diffTraces(A, B, ['id']).summary.same, 1)
})

test('a step that went to a different place shows as removed plus added', () => {
  const A = run(step('w', 'cache', 'read'), step('w', 'db', 'save'))
  const B = run(step('w', 'db', 'read'), step('w', 'db', 'save'))
  const ops = diffTraces(A, B).rows.map(r => `${r.op}:${r.step.to}`)
  assert.deepEqual(ops.sort(), ['added:db', 'removed:cache', 'same:db'])
})

test('a kind change (sync to async) is a change', () => {
  const D = diffTraces(run(step('a', 'b', 'x')), run(step('a', 'b', 'x', { kind: 'async' })))
  assert.deepEqual(D.rows[0].changes, [{ key: 'kind', before: 'sync', after: 'async' }])
})

test('Mermaid output escapes ";" and "#", and keeps ids Mermaid can read', () => {
  const m = traceToMermaid(run(step('svc a', 'db', 'save; then #2', { values: { n: 'x;y' } })))
  assert.match(m, /participant svc_a\n/)
  assert.match(m, /svc_a->>db: save, then no\.2 \(n=x, y\)/)
  assert.doesNotMatch(m.split('\n').slice(1).join('\n'), /[;#]/)
})

test('--context folds unchanged steps into one note', () => {
  const steps = Array.from({ length: 6 }, (_, i) => step('a', 'b', `s${i}`))
  const A = run(...steps)
  const B = run(...steps.slice(0, 5), step('a', 'b', 's5', { values: { v: 1 } }))
  const m = diffToMermaid(A, B, diffTraces(A, B), { context: 1 })
  assert.match(m, /Note over a: 4 unchanged steps/)
  assert.match(m, /a->>b: s4\n/)
  assert.match(m, /\[~\] s5 \(v: null → 1\)/)
})

test('exit codes: 0 when the same, 1 when different, 2 on bad input', () => {
  const cli = (...a) => spawnSync(process.execPath, [join(here, 'trace.mjs'), ...a], { encoding: 'utf8' })
  assert.equal(cli(ex('order.a.json'), ex('order.a.json')).status, 0)
  assert.equal(cli(ex('order.a.json'), ex('order.b.json')).status, 1)
  assert.equal(cli('/nonexistent.json').status, 2)
})
