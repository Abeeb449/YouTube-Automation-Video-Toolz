# Danger & wonder style guide

Distilled from the 5:25 reference `reference/Why You'd Never Want To Meet A Sperm Whale_0_325.mp4` (about 16 hard cuts; scenes
mostly flow inside one underwater world).

## 1. The formula
1. **False safety (0:00–0:20):** "you" in a calm, sunlit place. A ✓ chip: "NOTHING IS HUNTING YOU".
2. **The turn (0:20–0:30):** something notices you. Use red target brackets and a red callout: "IT KNOWS WHERE YOU ARE".
3. **The myth (0:30–0:45):** what people *think* is dangerous (a card or comparison), then "but the real answer is…".
4. **The reveal:** the animal's name, big and red ("SQUID."), then scale (scale bar "~16 M") and stacked fact chips, with the last chip red.
5. **Wonder sections, 3–5 of them:** each is one superpower (anatomy, senses, diving depth, sound, intelligence). Each opens with a question
   ("Forehead?") and ends with a number reveal (a meter, counter or stat).
6. **The enemy or the hunt:** predator vs prey, sonar view, depth descent with a meter, "most sunlight: gone".
7. **The human story:** a historical encounter or scientific discovery (a map pin, date, place).
8. **Closing danger:** "Can it kill you? Yes / Rarely / No — but…", a final silhouette, and a subscribe line.

## 2. Beat → template
| Beat | Template / props |
|---|---|
| Calm open, "you" diving | `OceanScene` `depth: 0.1`, `surface: true`, `diver`, `check: {text, ok: true}` |
| Being watched | `OceanScene` with a looming `silhouette: "#05080b"` actor, `target: {at}` on the diver, red `callout` |
| Name reveal | `OceanScene` with `bigText: "SQUID."`, `bigAt`, `sfx: hit` |
| Size | `OceanScene` with `scaleBar`, or `BarCompare` (animal vs bus or human) |
| Fact stack | `OceanScene` `facts: [{text, at}, …, {text, red: true}]` |
| Close-up feature | `OceanScene` `zoom: [1, 2.5]`, `focus`, `ring: {x, y, r}`, `title` |
| Going deeper | `OceanScene` `depth: 0.15 → depthTo: 0.95`, `depthMeter: {to, unit: m}` |
| Sound or echolocation | `Sonar` (green blips) or an actor with `waves`; `Meter` for dB |
| Numbers (stomach contents, brain kg, hearts) | `StatCards`, `Counter`, `DotGrid` with `backdrop: abyss` |
| Where it happened | `MapScene` with `backdrop: abyss`, `pulses`, `title: "1820"` |
| Verdict | `StatCards` + `stamp` ("RARE", "CANCEL", "YES.") or `bigText` |

## 3. Look
- **Palette:** surface `#2f7fa3` → mid `#0c3550` → abyss `#020508`. Text white; **red `#e5372f` only for threat and reveals**;
  green `#39ff88` for sonar; a green ✓ or red ✕ in check chips.
- **Labels:** Inter 800, upper case, short (2–6 words). Titles go top-centre; red titles get a red underline.
- **Motion:** creatures always drift, bob, and swim their tails and arms. The camera pushes in slowly. Text fades with a slight blur.
- **Pacing:** a new visual element every 3–6 seconds. Hold no more than about 10 seconds on one composition.

## 4. Sound
Never use transition sounds (whoosh, swell, riser, glitch). Add `ticks` under echolocation, a soft `thud` when something appears in the dark,
`hit` on name reveals, `thud` on stamps or "TEETH.", and `boom` only for real impacts.
