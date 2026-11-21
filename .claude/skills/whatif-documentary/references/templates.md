# Documentary template reference

Every template accepts the **shared overlay props** and every `at`/`*At` prop accepts **seconds or a cue word**.

## Cue words (resolved by `ytauto/cues.py`)
`at: 2.5` (seconds into the clip) · `at: "Hiroshima"` (when the word is spoken) · `at: "air raid"` (a phrase) ·
`at: "bomb#2"` (the second time it's said) · `at: "bomb+0.4"` / `at: "bomb-0.3"` (with an offset).
Words are matched case-insensitively, ignoring punctuation, within the scene's own narration.

## Shared overlay props (all templates)
| Prop | Example | Effect |
|---|---|---|
| `backdrop` | `navy` · `dark` · `horizon` · `ember` · `black` | Overrides the template's default background |
| `heading`, `headingColor`, `subheading`, `kicker` | `heading: Nuclear doctrine`, `headingColor: teal` | Top-left section title (white with a red underline, or teal) |
| `callout`, `calloutAt` | `callout: Built for the battlefield` | Bottom-centre key-phrase box |
| `source` | `source: "FAS · Status of World Nuclear Forces 2025"` | Tiny citation, bottom-left |
| `hud` | `{label: Local time, clock: 14652, format: time}` · `{label: Impact in, clock: -282}` · `{label: Since detonation, clock: 0, prefix: "T+", decimals: 3}` · `{label: Warheads, value: "1,500"}` | Top-right clock or value. `clock` is seconds at the clip start and ticks live. |
| `stats`, `statsAt` | `[{label: Nearest city, value: "20 km"}]` | Bottom-right data panel |

## Templates
**Horizon** (cinematic dusk). `mood: dusk|night|grey`, `title`, `subtitle`, `titleAt`,
`events: [{type: sun|flash|fireball|shockwave|mushroom, at, x: 0..1, size}]`, `ruler: ["0 KM","5 KM","10 KM"]`, `silhouettes: true`.

**Globe**: `from: [lon, lat]`, `to: [lon, lat]` (required), `zoomFrom` (0.8), `zoomTo` (1.6),
`marker: {label, note, at, ring}`, `highlight: [country names]`, `title`, `subtitle`.

**MapScene**: `focus: [country names]` or `bbox: [[west, south], [east, north]]`,
`highlight: [name | {name, at, color, opacity}]`, `countryLabels: [name | {name, lon, lat}]`,
`cities: [{name, lon, lat, at, color, note}]`, `arrows: [{from: [lon,lat], to: [lon,lat], at, dur, color, curve, label}]`,
`pulses: [{lon, lat, at, color, label}]`, `zoom` (1.06), `title`, `subtitle`.
The map data has country borders only (Natural Earth via world-atlas). Country names follow Natural Earth, e.g.
"United States of America" (aliases: USA, US, UK, Britain…), "Russia", "Dem. Rep. Congo".

**Counter**: `from`, `to`, `prefix`, `suffix`, `decimals`, `label`, `countAt`, `countDur`,
`timeline: {start, end, tickEvery, events: [{year, label, at}], band: {from, to, label}}`. Use a negative `tickEvery` for "years ago" axes.

**StatCards**: `cards: [{label, value, bar: 0..1, at}]`, `stamp: {text, at, color}`.

**DotGrid**: `count` (≤3000 dots), `highlight` (how many are coloured), `value`, `label`, `note`, `color`, `fillAt`, `fillDur`, `cols`.

**BarCompare**: `bars: [{label, value, display, color, at}]`, `unit`, `max`.

**SourceList**: `tag`, `tagNote`, `rows: [{title, source, at}]`.

**Clock**: `seconds` (to midnight), `value`, `label`, `series: [numbers]`, `seriesLabel`.

**Equation**: `lines: [{text, note, at, big}]`. `^2` becomes a superscript; the last line is teal.

**SplitCompare**: `left` and `right`: `{title, subtitle, footer, color, orb, at}`.

**Statement**: `kicker2`, `line1`, `line2` (red), `footnote`.

**Radius**: `rings: [{km, label, detail, color, at}]`, `centerLabel`.

**General templates** (also available): `TitleCard`, `KineticText`, `BulletList`, `BigNumber`, `Quote`.

## Scene-level keys (script.yaml)
`text` · `visual` (one or a list; the time is split evenly) · `chapter` · `duration` (minimum or fixed length) ·
`voice` (per-scene override) · `sfx` (built-in name, file, or a list of `{sound|file, at, volume, dur}`).
