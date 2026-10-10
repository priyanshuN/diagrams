// Build-time bridge: route right-angle arrows around fixed boxes with libavoid (Adaptagrams).
// stdin:  {"shapes": [{"id", "x", "y", "w", "h", "diamond", "obstacle"}], "conns": [{"key", "from", "to"}]}
// An "obstacle" shape (a group title) gets no pins: arrows only route around it.
// stdout: {"routes": {"<key>": [[x, y], ...]}}
// Each box gets exclusive connection pins on all four sides, so the router picks the cheapest free
// side and two arrows never share one attachment point. A diamond gets one pin per corner.
import { AvoidLib } from 'libavoid-js'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'

let input = ''
for await (const chunk of process.stdin) input += chunk
const { shapes, conns } = JSON.parse(input)

// Node's lookup finds node_modules here or in a parent folder (a plugin keeps one at its root)
await AvoidLib.load(join(dirname(createRequire(import.meta.url).resolve('libavoid-js')), 'libavoid.wasm'))
const A = AvoidLib.getInstance()
const UP = 1, DOWN = 2, LEFT = 4, RIGHT = 8, PIN = 1

const router = new A.Router(A.RouterFlag.OrthogonalRouting.value)
router.setRoutingParameter(A.RoutingParameter.shapeBufferDistance, 14)
router.setRoutingParameter(A.RoutingParameter.idealNudgingDistance, 12)
router.setRoutingParameter(A.RoutingParameter.segmentPenalty, 60)
router.setRoutingParameter(A.RoutingParameter.crossingPenalty, 400)
router.setRoutingParameter(A.RoutingParameter.portDirectionPenalty, 100)
router.setRoutingOption(A.RoutingOption.nudgeOrthogonalSegmentsConnectedToShapes, true)
router.setRoutingOption(A.RoutingOption.nudgeSharedPathsWithCommonEndPoint, true)
router.setRoutingOption(A.RoutingOption.performUnifyingNudgingPreprocessingStep, true)

const refs = {}
for (const s of shapes) {
  const ref = new A.ShapeRef(router, new A.Rectangle(new A.Point(s.x + s.w / 2, s.y + s.h / 2), s.w, s.h))
  refs[s.id] = ref
  if (s.obstacle) continue
  const pins = s.diamond
    ? [[0.5, 0, UP], [1, 0.5, RIGHT], [0.5, 1, DOWN], [0, 0.5, LEFT]]
    : [0.3, 0.5, 0.7].flatMap(f => [[f, 0, UP], [f, 1, DOWN]]).concat([0.32, 0.5, 0.68].flatMap(f => [[0, f, LEFT], [1, f, RIGHT]]))
  for (const [px, py, dir] of pins) {
    const pin = new A.ShapeConnectionPin(ref, PIN, px, py, true, 0, dir)
    pin.setExclusive(true)
    // prefer the middle of a side; off-centre pins cost a little more
    if (!s.diamond && (px !== 0.5 && py !== 0.5)) pin.setConnectionCost(4)
  }
}
// libavoid lets the connector added last pick its pins first. Add the longest arrows first, so the
// shortest (usually two neighbours) get the straight pins and long arrows walk around them.
const centre = id => { const s = shapes.find(t => t.id === id); return [s.x + s.w / 2, s.y + s.h / 2] }
const span = c => { const [a, b] = [centre(c.from), centre(c.to)]; return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) }
const connRefs = {}
for (const c of [...conns].sort((p, q) => span(q) - span(p))) {
  const cr = new A.ConnRef(router, new A.ConnEnd(refs[c.from], PIN), new A.ConnEnd(refs[c.to], PIN))
  cr.setHateCrossings(true)
  connRefs[c.key] = cr
}
router.processTransaction()
const routes = {}
for (const [key, cr] of Object.entries(connRefs)) {
  const r = cr.displayRoute(), pts = []
  for (let i = 0; i < r.size(); i++) { const p = r.at(i); pts.push([p.x, p.y]) }
  routes[key] = pts
}
process.stdout.write(JSON.stringify({ routes }))
