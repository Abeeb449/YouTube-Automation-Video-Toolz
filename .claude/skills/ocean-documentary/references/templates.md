# Ocean template reference

## OceanScene
| Prop | Meaning |
|---|---|
| `depth` 0..1, `depthTo` | 0 = sunlit with light shafts, 1 = abyss. `depthTo` animates a descent over the scene. |
| `surface`, `rays` | Surface shimmer line; force light shafts on or off |
| `split: {y, land: ice\|rocks\|none, landWidth, sky: polar\|storm\|dusk, floes}` | Above/below-the-waterline shot: sky and an ice shelf or rocky shore on top, ocean below. Put resting animals at `y` just above the waterline, hunters below it |
| `footage`, `footageStart`, `footageDim` | Real B-roll instead of the drawn water: `assets/x.mp4` or `"pexels:query"` |
| `actors` | See below |
| `zoom: [from, to]`, `focus: [x, y]` | Camera push-in centred on a point (fractions of the frame) |
| `title`, `titleColor: white or red`, `titleAt` | Top-centre label (red titles get an underline) |
| `bigText`, `bigAt`, `bigColor` | Huge centred reveal word ("SQUID.") |
| `facts: [{text, at, red}]` | Stacked fact chips, right side |
| `check: {text, at, ok}` | Bottom-left chip with a ✓ (ok) or ✕ |
| `scaleBar: {x1, x2, y, label, at}` | Measuring line ("~13 M"), frame fractions |
| `depthMeter: {from, to, max, unit}` | Right-side depth ruler with a moving marker |
| `timer: {from, label}` | Rounded stopwatch, top-right ("0:04" breath hold) |
| `callout`, `heading`, `source`, `hud`, `stats` | Shared docu overlays |

## Actor
`creature` (spermWhale · giantSquid · orca · shark · anglerfish · jellyfish · diver · fishSchool · octopus · leopardSeal · seaLion / furSeal · penguin · krill) **or** `image: assets/x.png` **or** `lottie: assets/x.json`.
When `facts` are shown, actors are moved left automatically so they never sit under the fact boxes.
`x`, `y` (0..1) and `to: [x, y]` (movement over the scene) · `scale` (1 ≈ a third of the frame wide) and `scaleTo` · `flip` · `rotate` ·
`at` (appear time or cue word) · `enter: fade | left | right | none` · `silhouette: "#05080b"` (flat shape) · `opacity` · `blur` ·
`color` (recolour) · `detail: {teeth: true, scars: true, count: 40, jaw: 0..1 (leopardSeal), rest: true (seaLion on land), pup: true (seaLion), stand: true (penguin)}` · `label: {text, at, color, dy}` · `target: {at}` (red lock brackets) ·
`waves: {at, color}` (echolocation arcs) · `ring: {at, x, y, r}` (spotlight ring).

## Meter
`title` (red, underlined), `from`, `to`, `max`, `unit`, `note`, `footnote`, `countAt`, `depth`.

## Sonar
`title`, `blips: [{label, x, y, creature, scale, flip, at, color}]`. Creatures are drawn as green sonar silhouettes;
set `color: "#e5372f"` to mark "YOU" or a threat.

## Adding a creature
Add a component to `remotion/src/ocean/creatures.tsx`. Draw it facing right, centred on (0,0), about 600 units long, and animate it with `t`.
Register it in `CREATURES`. Check it with `cd remotion && npm run studio` (Demos → Demo-OceanScene).
