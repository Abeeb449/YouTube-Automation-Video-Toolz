---
name: documentary-video-maker
description: Make complete faceless YouTube documentaries on any topic (animals, history, science, places, what-ifs) with the free open-source ytauto toolkit, from the creator's own researched script. Direct every scene (animated creatures, maps, data graphics, B-roll), let the narration, music and sound follow the script, render to 1080p MP4 and QC it. Use whenever the user wants a video made from a title, topic or script.
---

# Documentary Video Maker (ytauto)

Free and open source end to end. CPU only, no GPU needed, no paid APIs. Renders locally, in GitHub Codespaces,
or on free GitHub Actions.

---------------------------------------------------------------------------------------------------------
## 1. Software stack (all installed by the repo's Dockerfile)

| Job | Tool | Notes |
|---|---|---|
| Orchestration | **ytauto** (Python 3.10+) | `python -m ytauto …` CLI: plan → voice → visuals → mix → MP4 |
| Animated graphics | **Remotion** (React) + headless Chromium | All templates in `remotion/src/` (vector, sharp at any size) |
| Video encode and mix | **ffmpeg** (x264 `tune animation`, loudnorm −14 LUFS) | |
| Narration | **Qwen3-TTS 1.7B** (Apache 2.0) in its own venv `/opt/tts-qwen` | Default voice. Direct it in plain English |
| Narration alternatives | **Chatterbox** (MIT, `/opt/tts-chatterbox`), **Kokoro** (Apache 2.0, fast fallback), Piper, eSpeak | |
| Word timing | **faster-whisper** base.en | Aligns cue words to the spoken audio |
| Music | **Kevin MacLeod / Incompetech** (CC BY 4.0) fetched by mood; built-in synth score as fallback | Credits written to the description automatically |
| Sound effects | Built-in synthesizer (`ytauto/sound.py`) | hit, thud, boom, tick(s), typing, beep, alarm. Never transition sounds (whoosh, swell, riser, glitch): the mix drops them |
| Stock B-roll (photos + video) | **No key needed:** iNaturalist (research-grade photos of the exact species), Openverse, Wikimedia Commons (photos + clips), NASA Image & Video Library. **Free key:** Unsplash (`UNSPLASH_ACCESS_KEY`), Pexels, Pixabay | Only CC0 / public domain / CC BY by default (`YTAUTO_STOCK_LICENSES`, add `by-sa` to allow share-alike); NC/ND never. Credits (author, licence, link) go into the description automatically and `build/credits.json` keeps the licence record |
| 3D animals | **Blender** EEVEE (Mesa software GL, no GPU needed) | `blender/creatures3d.py` builds and rigs the leopard seal, sea lion and pup procedurally and renders looping transparent sprite sheets (`ytauto sprites`). OceanScene uses them automatically |
| 3D titles (optional) | **Blender** (Cycles CPU) | `{blender: intro}` titles |
| Images | **rembg** (`ytauto cutout`), Inkscape, ImageMagick, potrace, librsvg | Turn any picture into a transparent cut-out actor |
| Lottie | `@remotion/lottie` | Free LottieFiles animals: `lottie: assets/x.json` |
| Audio tools | sox, numpy | |

**Setup:** `docker build -t ytauto .` then
`docker run --rm -v "$PWD:/work" -e HF_HOME=/work/.cache/huggingface ytauto python -m ytauto render projects/<slug>`.
Without Docker: `pip install -r requirements.txt && (cd remotion && npm install)`, then run
`python -m ytauto doctor` to see what's installed.

---------------------------------------------------------------------------------------------------------
## 2. Workflow for one video

Works for any animal. Script only → video: `python -m ytauto make projects/<slug>/script.txt --style nature`
(auto-detects the animal from the title, or add a `Subject: <animal>` line). The planner turns body parts into
close-ups, dates into typed date cards, percentages into dot grids, punchy lines into statements, and fills the
rest with free photo/video B-roll, each with a fallback. Review and sharpen `script.yaml`, then render.


1. **The creator researches and writes `projects/<slug>/script.txt`** in their own words and structure
   (`# Heading` lines mark chapters; ~140 words per minute of video). Nothing about the writing is prescribed.
2. **Direct `projects/<slug>/script.yaml`.** Split the identical narration into scenes and add visuals and cues
   (sections 3–7). Quick draft: `python -m ytauto plan projects/<slug>/script.txt` (style picked from the
   topic), then improve it by hand. Music mood and effects follow the script automatically (sound director).
3. **Check:** `python -m ytauto check projects/<slug>` (sources, originality, variety).
4. **Preview:** `python -m ytauto render projects/<slug> --preview` (540p, fast). Open
   `build/contact_sheet.jpg` (one frame per scene) and fix tiny, empty, cluttered or mistimed scenes.
5. **Final:** `python -m ytauto render projects/<slug>`, or push to GitHub and run **Actions → Render video**.
   Outputs go to `build/`: `<title>.mp4`, `thumbnail.jpg`, `captions.srt`, `description.txt` (with chapters,
   music credits and stock credits), `contact_sheet.jpg`, `manifest.json`.

Voice audio is cached per passage: re-renders after visual edits take minutes. On a 4-core CPU, Qwen narration
takes roughly 5× the audio length, and visuals about 3–4 minutes per finished minute.

---------------------------------------------------------------------------------------------------------
## 3. script.yaml format

```yaml
preset: ocean                     # ocean (animal/sea docs) | documentary (what-if infographic) | add "shorts" for 9:16
title: "Why Do Sea Lions Fear Leopard Seals?"
description: |
  What the video covers, in the creator's words. Sources: …
tags: [leopard seal, sea lion, antarctica, wildlife documentary]
settings:
  voice: {engine: qwen, name: ryan}                 # narrator direction is decided from the script (instruct: "…" overrides)
  music: {source: incompetech, mood: mystery}       # real music by mood (default)
thumbnail: {text: "WHY SEA LIONS FEAR THIS SEAL"}
youtube: {privacy: private, category_id: 15}       # 15 = Pets & Animals, 27 = Education, 28 = Science & Tech
scenes:
  - chapter: Arrival              # optional: YouTube chapter from the script's own headings (>=3, first at the start)
    mood: mystery                 # optional override; normally chosen from the scene's words (sound director)
    text: "[tone hushed and intimate] A young fur seal stands at the edge of the rocks."
    visual: {remotion: OceanScene, props: {...}}   # or a list of visuals (time is split evenly)
    sfx: [{sound: thud, at: "edge", volume: 0.3}]  # optional (never whoosh/swell/riser/glitch)
    duration: 6                   # optional minimum length (silent beats, held reveals)
    voice: {name: eric}           # optional per-scene voice override
```

**Cue words:** any `at:` or `…At:` prop accepts seconds, or a word from that scene's narration: `"jaws"`,
`"seven"`, `"air raid"` (a phrase), `"bomb#2"` (the second time it's said), `"launch+0.5"` (with an offset).
The element appears exactly when the narrator says it.

---------------------------------------------------------------------------------------------------------
## 4. Voice direction (makes the narrator sound human)

Inline tags inside `text:` hold until the end of the scene (or `[reset]`):

| Tag | Use |
|---|---|
| `[tone hushed and intimate]` | Describe the delivery in plain English: tense, awed, urgent, warm, respectful, quietly shocked, playful |
| `[pause 0.4]` | A short silence before a reveal. Keep it 0.3–0.6 s, and never put one mid-thought |
| `[speed 0.9]` | Slightly slower for menace (0.85–0.95); faster for excitement (1.05–1.1) |
| `[emotion 0.8]` | Intensity 0.25–1.0 (calm → urgent) |
| `[voice eric]` | Switch voice. Qwen speakers: ryan (default), aiden, eric, dylan, serena, vivian, uncle_fu, ono_anna, sohee |
| `[reset]` | Back to the scene's defaults |

**Narration style (`settings.narration`).** `natural` (default in the nature/ocean/documentary presets): the voice
reads the script as written; tags in `[…]` are ignored and nothing is edited. `polished`: the phrasing pass below,
with tags performed.

**Polished phrasing (`narration: polished`, `voice_polish.mode: phrasing`):** every sentence is voiced on its own, then
listened back with faster-whisper. A take with a word broken in the middle ("leop… ard") or a misread word is
re-voiced (up to 2 retakes, best take kept). Then the pauses are re-timed so the narrator only breathes where the
meaning allows: gaps between words inside a phrase shrink to a normal word gap (< 0.08 s), commas get a short
breath (≤ 0.42 s), full stops 0.3–0.65 s, and sentences are separated by `sentence_gap` (0.4 s). Cuts happen only
inside silence, never through a sound. A pace target (`target_wpm: 148`, max +8 %) keeps it from dragging.
So: put `[pause]` only after a complete thought (after `.` `?` or a comma), never mid-phrase.
Preview the narration alone with `python -m ytauto voiceover <project>` (MP3, no video; `--plain` / `--polished` force a
style; `--voice aiden --scenes 8` voices just the opening in another speaker to compare).

Alternative voices: `name: design` + `description: "a deep warm British male narrator"` invents a voice;
`reference: assets/myvoice.wav` clones one you own; `engine: chatterbox` is faster; `engine: kokoro` is the fastest.

---------------------------------------------------------------------------------------------------------
## 5. Ocean / animal kit (`remotion: OceanScene`, `Meter`, `Sonar`)

### OceanScene props
| Prop | Meaning |
|---|---|
| `depth` 0–1, `depthTo` | 0 = sunlit with light shafts, 1 = black abyss. `depthTo` animates a descent |
| `split: {y, land: rocks\|ice\|none, landWidth, sky: polar\|storm\|dusk, floes}` | Above/below-waterline shot. Land animals with `rest`/`stand` snap onto the shore automatically |
| `surface`, `rays` | Surface shimmer line; force light shafts on or off |
| `zoom: [from, to]`, `focus: [x, y]` | Camera push-in toward a point (default gentle 1.0→1.06) |
| `title`, `titleColor: white\|red`, `titleAt` | Top-centre label |
| `bigText`, `bigAt`, `bigColor` | Huge centred reveal word ("LEOPARD SEAL", "PATIENCE.") |
| `facts: [{text, at, red}]` | Up to 3 stacked fact chips, right side (the last one red for danger) |
| `check: {text, at, ok}` | ✓ or ✕ chip, bottom-left |
| `scaleBar: {x1, x2, y, label, at}` | Measuring line ("~3.5 M") |
| `depthMeter: {from, to, max, unit}` | Right-side depth ruler with a moving marker |
| `timer: {from, label}` | Stopwatch |
| `footage: "pexels:<query>"`, `fallback: {…}` | Real B-roll behind the overlays, with drawn props if no clip is found |
| `callout`, `calloutAt`, `heading`, `source`, `hud`, `stats` | Shared overlays (key-phrase box, section title, citation, clock, data panel) |

### Actors (`actors: [ … ]`)
`creature:` one of **spermWhale, giantSquid, orca, shark, anglerfish, jellyfish, diver, fishSchool, octopus,
leopardSeal, seaLion (= furSeal), penguin, krill** (`view: jaw` on leopardSeal = the 3D open-jaw close-up). Or use `image: assets/x.png` (a transparent cut-out) or
`lottie: assets/x.json`.

| Actor prop | Meaning |
|---|---|
| `x, y` (0–1), `to: [x, y]` | Position and movement over the scene (swimmers drift gently by default) |
| `scale` (1 ≈ a third of the frame wide), `scaleTo` | Small values are raised to a readable minimum (`allowTiny: true` to opt out) |
| `flip`, `rotate` | Face left; tilt (e.g. −80 for an attack from below) |
| `at`, `enter: fade\|left\|right\|none` | When and how it appears |
| `silhouette: "#071118"`, `opacity`, `blur` | Looming dark shape (gets a soft rim so it stays visible) |
| `color`, `detail` | `detail: {jaw: 0-1}` (leopard seal mouth), `{rest: true}` (seal on land), `{pup: true}`, `{stand: true}` (penguin), `{teeth, scars}` (sperm whale), `{count}` (fish, krill) |
| `label: {text, at, dy}` | Name under the animal (above it for land animals) |
| `target: {at}` | Red lock-on brackets (the prey is being watched) |
| `waves: {at}` | Sound-wave arcs (song, echolocation) |
| `view: side\|three_quarter`, `flat: true` | 3D sprite angle; `flat: true` forces the 2D drawing for that actor |
| `ring: {at, local: [x, y], r}` | Spotlight ring on a point of the animal's own drawing (`local` is in creature units: leopardSeal head ≈ [248, −12], whiskers ≈ [292, 8]; resting seaLion ear ≈ [200, −166]; giantSquid eye ≈ [34, −2]) |

**3D sprites:** leopardSeal (side, three_quarter, rest), seaLion/furSeal (side, rest) and pups (side, rest) are drawn as
rendered Blender 3D models (swimming loops at 24 fps, resting poses grounded on the shore with a contact shadow).
The renderer builds any missing set before the video, about 2 min per swim loop on CPU, and caches them in
`remotion/public/sprites/`. Rebuild with `python -m ytauto sprites --force [creature:view …]`. Other creatures keep their
2D drawings. Turn 3D off for a project with `settings: {render3d: false}`.

### Motion-graphics kit (show exactly what the narrator says)

| Template | Use it when the line… | Key props |
|---|---|---|
| `Anatomy` | names a body part (teeth, jaws, ears, flippers, whiskers) | `sprite: {creature: leopardSealHead, view: jaw}` (3D jaw that opens: canines + three-pointed cheek teeth) or `{creature: seaLion, view: rest}`, or `image:`; `callouts: [{x, y, label, sub, at, side}]` (x, y = 0–1 inside the animal); `zoom: [{at, x, y, scale}]` camera push-ins; `title`, `kicker`, `backdrop` |
| `PhotoStory` | describes a real animal, place or event | `layout: full` (full-bleed, 2.5D parallax with `parallax: true`) · `print` (framed photo that drops in and tilts in 3D) · `pile` (several prints land one by one); `photos: [{photo: "stock:leopard seal" or assets/x.jpg, caption, credit, at, focus: [x, y], zoom: [a, b], mark: {x, y, r, at, label}, mono: true, colorAt}]`. Grain, light leaks, vignette and the credit chip are automatic. Give a `fallback_visual:` for stock searches |
| `ClipCard` | quotes a study, a term or an article | `publication, title, date, lines: [...]`, `highlight: [{text, at}]` (marker sweeps on the word), `source` |
| `DateStamp` | gives a date, time or place | `date: "JULY 2003"`, `time`, `place`, `at` (typed on; pair with `sfx: ticks`) |

Rules: never show a closed mouth while the narrator talks about teeth; never a swimming animal while the line says
it rests on the ice; every named thing (an ear, a whisker, a place, a year) gets a callout, mark or stamp *at that word*.
Only `mark` a stock photo you have looked at (pin it under `assets/` with its `credit`), because a search can return a
different photo next time. A scene may hold two visuals (`visuals: [ … , … ]`), which split its time in half; use it
when a scene has two ideas (the teeth, then the krill).

`Meter`: `title, from, to, unit, note, footnote, countAt` (e.g. 0 → 236 dB).
`Sonar`: `title, blips: [{label, x, y, creature, scale, at, color}]`.

---------------------------------------------------------------------------------------------------------
## 6. Infographic kit (works on any backdrop: `backdrop: navy | dark | ocean | abyss | ember | horizon | black`)

| Template | Key props |
|---|---|
| `Counter` | `from, to, prefix, suffix, label, countAt, countDur, plain` (no commas, for years), `timeline: {start, end, tickEvery, events: [{year, label, at}]}` |
| `DotGrid` | `count, highlight, cols, value, label, note, fillAt, color` ("7 in 10" = count 10, highlight 7) |
| `BarCompare` | `bars: [{label, value, display, color, at}], unit, heading` |
| `StatCards` | `cards: [{label, value, bar, at}], stamp: {text, at}` |
| `SourceList` | `tag, tagNote, rows: [{title, source, at}]` (great for "three ways…" lists) |
| `Statement` | `kicker2, line1, line2` (red), `footnote` (turning points, twists) |
| `MapScene` | `bbox: [[west, south], [east, north]]` or `focus: [countries]`, `countryLabels`, `cities`, `pulses: [{lon, lat, label, at}]`, `arrows`, `highlight`, `title`, `subtitle` |
| `Globe` | `from, to: [lon, lat], zoomFrom, zoomTo, marker: {label, at}, title, subtitle` |
| `Horizon` | `mood: dusk\|night\|grey, title, subtitle, events: [{type: flash\|fireball\|shockwave\|mushroom\|sun, at}]` |
| `Equation`, `Clock`, `SplitCompare`, `Radius` | Maths steps, doomsday clock, side by side, impact rings |
| `TitleCard`, `KineticText`, `BulletList`, `BigNumber`, `Quote` | General templates |
| `model: "<search words>"` (a visual, not a template) | A 3D model of the subject from free-licence libraries, or `model: assets/x.glb`. `props: {shot: turn\|push\|left\|right\|top\|base, callout, calloutAt, callouts: [{x, y, label, at}], heading, kicker, backdrop, tint, front}`. Credits go in the description automatically; a CC BY model also gets a small credit line on screen (`source:` overrides it). Always give a `fallback_visual`. |

All of them also take `heading`, `subheading`, `kicker`, `callout`, `calloutAt`, `source`, `hud`, `stats`,
`footage`.

---------------------------------------------------------------------------------------------------------
## 7. Example shot ideas (from the leopard-seal test video, not a template)

These are ways that particular script's beats were shown. Use them only where YOUR script has a similar beat;
every video's structure comes from its own script.

| Beat | Recipe |
|---|---|
| Hook / false safety | `split` rocks or ice, prey resting on land, storm sky, slow `zoom: [1.08, 1.0]`, hushed tone |
| Something is watching | Hunter as a `silhouette` below the waterline facing the prey, `target` on the prey, callout |
| Shock statistic | `DotGrid` or `Counter` on `backdrop: abyss`, a `thud` sfx, source line |
| Name reveal | Hunter large and drifting + `bigText` + a `hit` sfx, `[pause 0.4]` before the name |
| Anatomy | Push-in on the feature (`zoom`, `focus`), `ring.local`, ≤3 facts, `jaw` open for teeth |
| Diet or proportions | `BarCompare` (danger slice red) |
| Behaviour (song, rest) | `waves`, `split` ice shelf with the animal on the floe |
| The attack | Prey at the surface with `target`; the hunter rises from below (`rotate: -80`, `to` upward, jaw open) + a soft `hit` |
| Study or place | `MapScene` with a `pulse`, then the data templates |
| Twist | `Statement` on `abyss` → evidence scene → `DotGrid` |
| Human story | `Horizon` grey with a respectful title, then `StatCards` |
| Closing callback | The opening image again at dusk, a silhouette below, `bigText` callback, slow tempo |
| Ending | Whatever the script ends on: show what its last lines say |

General rules: change something every 3–6 s; keep text off subjects; one reveal word per scene; use red only for
danger.

---------------------------------------------------------------------------------------------------------
## 8. Music and sound

- `music: {source: incompetech}` (default) picks Kevin MacLeod tracks by mood, without drums, loops and
  crossfades them, holds steady levels with a limiter, and ducks the music about 18 dB under speech. Credits go
  in `description.txt` automatically. Other sources: `{source: library, library: assets/music}` (mood
  sub-folders you fill once, e.g. from the YouTube Audio Library), `{source: openverse}`, `{generate: true}`
  (synth score), or `{file: assets/track.mp3}`.
- `volume` sets the music level in pauses (default 0.8), and `duck` sets its level while speaking (0.45).
- **Sound director (automatic):** each scene's mood comes from its own words and `[tone …]` directions; soft
  effects land on the word that calls for one (a low impact, a deep thud, ticks on a date) within a budget. No
  transition sounds at all (no whoosh, swell, riser or glitch, anywhere). Hand-written
  `mood:` / `sfx:` override it; `sound: {director: false}` turns it off.

---------------------------------------------------------------------------------------------------------
## 9. Render and QC checklist

- [ ] `python -m ytauto render projects/<slug> --preview` runs with no `cue word … not found` warnings.
- [ ] Contact sheet: every scene has a clear subject filling at least a third of the frame, no text over
      animals, nothing empty.
- [ ] Watch the opening, every reveal and the ending at full speed: is the motion continuous, do cues land on
      their words, is the music under the voice, are there no loud spikes?
- [ ] `python -m ytauto check <project>` shows 0 to fix (sources listed with `sources:`, no repeated passages, varied shots).
- [ ] `description.txt` has chapters, sources, music credits and stock credits; `credits.json` lists every stock item's licence.
- [ ] Final render, then upload: `python -m ytauto upload projects/<slug> --privacy private` (YouTube OAuth
      secrets), or download the GitHub Actions artifact.

**GitHub Actions:** commit `projects/<slug>/script.txt` (and optionally `script.yaml`) and push, or run
**Actions → Render video** with `project: projects/<slug>`. Secrets: `PIXABAY_API_KEY` (free B-roll) and
optionally `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` (upload).

## 10. Licences

Qwen3-TTS (Apache 2.0), Chatterbox (MIT), Kokoro (Apache 2.0) and Incompetech music (CC BY 4.0, credited)
are all allowed in monetised videos. For Pixabay footage, credit Pixabay (done automatically). Remotion is
free for individuals and companies of up to 3 people. Write original scripts for every video, because
YouTube demonetises mass-produced, repetitive content.
