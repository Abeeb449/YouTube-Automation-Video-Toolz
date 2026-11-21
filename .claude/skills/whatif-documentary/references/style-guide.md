# What-if documentary style guide

This is distilled from the 5-minute reference `reference/What If Russia Used a Nuke…mp4` (640×360 source, 30 fps).

## 1. Grammar
- **One continuous feel.** There are only about 12 hard cuts in 5 minutes. Scenes share a backdrop and fade only their *content*,
  so changing scene on the same backdrop looks like the graphics rearranging. Hard cuts are kept for world changes: globe → map, data → horizon.
- **Three worlds:** (1) a **navy infographic board** for numbers, (2) **dark-grey maps** and a **globe** for places, and
  (3) a **cinematic dusk horizon** for moments in the story (the cold open, "Day one, 4:12 a.m.", the event itself).
- **Everything is labelled:** small spaced-capitals kickers, mono-font numbers, and a tiny source line bottom-left on almost every screen.
- **The HUD tells time:** a top-right wall clock (`04:07:32`) or countdown (`T-04:42`) turning into `T+0.006 s` during the event.
- **Key-phrase callouts** sit bottom-centre (a dark box with a red underline) instead of full subtitles: "THE LAST PLACE THAT LOOKS NORMAL".
- **Motion:** elements blur and fade in, numbers count up, lines draw, rings expand. There's a slow push-in on everything and no bouncy easing.

## 2. Beat → template
| Beat in the script | Template | Notes |
|---|---|---|
| Cold open / location / time of day | `Horizon` + `title`, `hud {format: time}`, `stats` | Spaced-capitals location title, amber subtitle |
| Zoom from planet to place | `Globe` (`from` → `to`, `zoomTo` 2–3, `marker`) | Big date title bottom-left ("9 AUGUST 1945") |
| "This is a simulation, nothing made up" | `SourceList` | Red-bordered tag, numbered rows with sources |
| Years since / count of something | `Counter` (+ `timeline` with `events`) | Big number top-left, red label |
| Places, movements, borders | `MapScene` (`focus`/`bbox`, `highlight`, `arrows`, `pulses`, `cities`) | Date title top-left, HUD countdown |
| Treaty limits / key figures + verdict | `StatCards` + `stamp` (EXPIRED, FAILED) | At most 1–2 stamps per video |
| "Seconds to midnight" style risk | `Clock` (+ `series`) | Uses the ember backdrop |
| How many (warheads, people, cities) | `DotGrid` | `highlight` = how many are red |
| Compare sizes | `BarCompare` | The last bar is red by default |
| Step-by-step maths | `Equation` | Serif italic lines; `^2` → superscript |
| Two options side by side | `SplitCompare` | `orb: true` gives a glowing fireball icon |
| Thesis / turning point | `Statement` (`line2` in red) | Ember backdrop |
| The event, second by second | `Horizon` + `events` (flash, fireball, shockwave, mushroom), `hud {clock: -1.2, prefix: "T+"}`, `ruler` | Silent `duration` beat + `sfx: boom` |
| Blast or impact zones from above | `Radius` (rings in km + legend) | Label it "illustrative" |
| Narration-heavy filler | `KineticText` | Use rarely |

## 3. Tokens
- Navy board: radial `#15406a → #0c2640 → #06121d`. Maps: `#23282e → #0d0f12`, land `#33383e`, borders `#5d636b`.
- Red `#e5372f` · teal `#62b6cb` · amber `#f2b35a` · text `#f1f4f8` · dim `#8aa1b6` · faint `#4d6477`.
- Fonts: Inter (titles, 800 weight, upper case), DejaVu Sans Mono (numbers and HUD), DejaVu Serif italic (maths).

## 4. Pacing (measured from the reference)
- Cold open 0:00–0:30: establishing horizon → globe → "one bomb".
- 0:30–1:00: the simulation disclaimer and sources (the trust builder).
- 1:00–2:00: history and context (counter, timeline, map, doctrine, treaty "EXPIRED", doomsday clock).
- 2:00–3:00: the maths (equation, bars, freight-car comparison), then the thesis ("ESCALATE TO DE-ESCALATE").
- 3:00–5:00: the event, second by second: location title, launch map with countdown, the people (dot grid), detonation timeline,
  fireball → shockwave → mushroom → ground-zero radii → airburst vs ground burst.
- Scene length averages about 8 seconds. Number reveals hit on the spoken number.
