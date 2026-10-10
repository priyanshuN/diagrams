// Checks a hand-drawn Unicode box diagram before it goes into a chat reply.
// Every line character has "arms" (up, down, left, right). Each arm must meet a character that
// reaches back, so a line shifted by one column, a corner with nothing under it, or an arrowhead
// that stops short of its box is reported with its row and column.
// Rows that start with "Legend" or "Key" are skipped: they hold sample arrows that touch nothing.

const U = 1, D = 2, L = 4, R = 8
const ARMS = {}
const put = (chars, arms) => { for (const c of chars) ARMS[c] = arms }
put('─┄┈╌━═', L | R)
put('│┆┊╎┃║', U | D)
put('┌╭╔┏', D | R); put('┐╮╗┓', D | L); put('└╰╚┗', U | R); put('┘╯╝┛', U | L)
put('├╠┣', U | D | R); put('┤╣┫', U | D | L)
put('╟', R); put('╢', L)                       // queue-box corners: top and bottom look the same
put('┬╤╦┳', D | L | R); put('┴╧╩┻', U | L | R)
put('┼╪╫╬╋', U | D | L | R)

// arrowheads: the tail arm needs a line, the head side must touch a box
const HEADS = { '▼': U, '▽': U, '▲': D, '△': D, '▶': L, '▷': L, '►': L, '◀': R, '◁': R, '◄': R }
const OPP = { [U]: D, [D]: U, [L]: R, [R]: L }
const STEP = { [U]: [-1, 0], [D]: [1, 0], [L]: [0, -1], [R]: [0, 1] }
const NAME = { [U]: 'up', [D]: 'down', [L]: 'left', [R]: 'right' }
const WORD = /[\p{L}\p{N}]/u

export function lint(text, { maxCols = 90, maxRows = 45 } = {}) {
  const fence = text.match(/```[\w-]*\n([\s\S]*?)```/)
  const rows = (fence ? fence[1] : text).replace(/\s+$/, '').split('\n').map(l => [...l.replace(/\s+$/, '')])
  const errors = []
  const at = (r, c) => rows[r]?.[c] ?? ' '
  const arms = ch => ARMS[ch] ?? (HEADS[ch] ? HEADS[ch] : 0)
  const skip = rows.map(r => /^\s*(legend|key)\b/i.test(r.join('')))
  const err = (r, c, msg) => errors.push({ row: r + 1, col: c + 1, msg })
  // a label written across a line: a letter or digit, or punctuation with one within two columns ("gRPC / REST")
  const inLabel = (r, c) => {
    const ch = at(r, c)
    if (WORD.test(ch)) return true
    if (ch === ' ' || arms(ch) || ch === '◇') return false
    return [-2, -1, 1, 2].some(k => WORD.test(at(r, c + k)))
  }

  rows.forEach((row, r) => {
    if (row.includes('\t')) err(r, row.indexOf('\t'), 'tab character: use spaces')
    if (skip[r]) return
    row.forEach((ch, c) => {
      const own = ARMS[ch]
      if (own) {
        for (const dir of [U, D, L, R]) {
          if (!(own & dir)) continue
          const [dr, dc] = STEP[dir]
          const n = at(r + dr, c + dc)
          if (skip[r + dr] && dr) continue
          if (arms(n) & OPP[dir]) continue
          const vertical = dir === U || dir === D
          if (n === '◇') continue                                  // a decision corner takes lines from any side
          if (vertical && HEADS[n] & (L | R)) continue              // a message arrow lands on a lifeline
          if (vertical && n === ' ' && r + dr === rows.length) continue   // lifelines end at the last row
          if (vertical && '╟╢'.includes(n)) continue
          // a line that touches a horizontal line with no junction nearby is a crossing (a lifeline
          // under a message or a note); next to a junction whose arm reaches empty space, it is misplaced
          const near = [-2, -1, 1, 2].find(k => ARMS[at(r + dr, c + k)] & OPP[dir] && ARMS[at(r + dr, c + k)] & (L | R) && at(r, c + k) === ' ')
          if (vertical && (ARMS[n] & (L | R)) && near === undefined) continue
          if (!vertical && (ARMS[n] & (U | D))) continue          // a line leaving a box side, or a crossing
          if (vertical && inLabel(r + dr, c + dc)) continue        // a label sits in the line
          if (!vertical && n === ' ' && WORD.test(at(r, c + 2 * dc))) continue   // "─ Title ─" gap
          if (!vertical && inLabel(r, c + dc)) continue            // "──label──", "─gRPC─/─REST─"
          if (vertical && (ARMS[n] & (L | R)))
            err(r, c, `'${ch}' misses the '${at(r + dr, c + near)}' ${Math.abs(near)} column(s) to the ${near < 0 ? 'left' : 'right'}: shift the line`)
          else
            err(r, c, `'${ch}' reaches ${NAME[dir]} into ${n === ' ' ? 'empty space' : `'${n}'`}: the line is broken or one column off`)
        }
      }
      const tail = HEADS[ch]
      if (tail) {
        const [tr, tc] = STEP[tail], [hr, hc] = [-tr, -tc]
        const t = at(r + tr, c + tc), h = at(r + hr, c + hc)
        if (!(arms(t) & OPP[tail]) && !inLabel(r + tr, c + tc)) err(r, c, `arrowhead '${ch}' has no line behind it`)
        const into = tail === U || tail === D ? (L | R) : (U | D)
        const onLifeline = (ARMS[at(r - 1, c)] & D) && (ARMS[at(r + 1, c)] & U)
        if (!(ARMS[h] & into) && !WORD.test(h) && !onLifeline) err(r, c, `arrowhead '${ch}' points at ${h === ' ' ? 'empty space' : `'${h}'`}, not a box edge`)
      }
    })
  })
  const width = Math.max(0, ...rows.map(r => r.length))
  const notes = []
  if (width > maxCols) notes.push(`${width} columns is wider than ${maxCols}`)
  if (rows.length > maxRows) notes.push(`${rows.length} rows is taller than ${maxRows}`)
  return { ok: !errors.length && !notes.length, width, rows: rows.length, errors, notes }
}
