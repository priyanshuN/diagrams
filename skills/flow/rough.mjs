// Build-time bridge: hand-drawn versions of shapes with rough.js (the library behind Excalidraw's look).
// stdin:  [{"type": "path"|"polygon"|"line", "d"|"points", "fill", "roughness", "bowing", "seed"}]
// stdout: [[{"c": "o"|"h", "d"}]]  o = outline stroke, h = hachure fill stroke (CSS colours both)
import rough from 'roughjs/bundled/rough.esm.js'

let input = ''
for await (const chunk of process.stdin) input += chunk
const gen = rough.generator()
const OUT = '#000', FILL = '#fff'           // sentinels: tell the outline from the fill strokes
const drawn = JSON.parse(input).map(j => {
  const o = { seed: j.seed ?? 1, roughness: j.roughness ?? 1.2, bowing: j.bowing ?? 1, stroke: OUT, strokeWidth: 1.5,
              ...(j.fill ? { fill: FILL, fillStyle: 'hachure', hachureGap: 7, fillWeight: 1.5, hachureAngle: -41 } : {}) }
  const d = j.type === 'polygon' ? gen.polygon(j.points, o) : j.type === 'line' ? gen.linearPath(j.points, o) : gen.path(j.d, o)
  return gen.toPaths(d).map(p => ({ c: p.stroke === FILL ? 'h' : 'o', d: p.d }))
})
process.stdout.write(JSON.stringify(drawn))
