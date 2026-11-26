---
name: ocean-documentary
description: Use when the user asks to "make an animal documentary", "make a deep sea video", "make an ocean video", "why you'd never want to meet X", "danger and wonder video", "make a video about a sea creature", or wants a narrated flat-vector animal documentary with animated creatures, depth meters, sonar, fact chips and scale bars rendered to MP4 with ytauto.
---

# Ocean / Animal "Danger & Wonder" Documentary

Gives any ocean script the drawn look of `reference/Why You'd Never Want To Meet A Sperm Whale_0_325.mp4` (visual style
only; the script's own words decide the content, structure and tone).
That means flat-vector animals in a procedural underwater world (light shafts → abyss, marine snow), short bold labels, fact chips,
scale bars, depth meters, sonar views, target brackets, and a calm British narrator. Built on `ytauto` with `preset: ocean`
and the Remotion kit in `remotion/src/ocean/`. The infographic templates from `remotion/src/docu/` (StatCards, Counter,
MapScene, DotGrid, BarCompare…) also work here with `backdrop: abyss` or `backdrop: ocean`.

Worked example: `projects/ocean-giant-squid/script.yaml`. Copy it to start a new video.
Read `references/style-guide.md` (the danger & wonder formula and beat → template map) before writing.
Template props: `references/templates.md`, plus `.claude/skills/whatif-documentary/references/templates.md` for the docu kit.

## Workflow

Shortcut: if the user just gives narration, save it as `projects/<slug>/script.txt` and run
`python -m ytauto plan … --style ocean` (or, better, write script.yaml yourself following this guide).

1. **The creator picks the topic, title and angle** from their own research. This skill only supplies the drawn
   deep-sea look (animated creatures, depth meters, sonar); it doesn't prescribe titles or framing.
2. **Research.** Collect 8–12 verified facts: size, depth, senses, weapons, diet, a record ("loudest", "largest eye"), its enemy,
   a human encounter or historical event, and one open mystery. Prefer NOAA, MBARI, Smithsonian Ocean, the Natural History Museum and
   peer-reviewed papers. Phrase uncertain numbers as "around" or "up to".
3. **Script.** Use the creator's own script as written (about 150 words per minute fits this look). Don't rewrite
   it into a house style.
   Follow the **danger → wonder → danger** arc in the style guide. A 10-minute video is about 1,500 words and 60–80 scenes.
4. **Write the scenes.** Use one beat per scene and put cue words (`at: "teeth"`) on every reveal.
   Use the built-in creatures (`spermWhale`, `giantSquid`, `orca`, `shark`, `anglerfish`, `jellyfish`, `diver`, `fishSchool`, `octopus`).
   For other animals, put a transparent PNG/SVG in `assets/` and use `image: assets/<file>.png`
   (draw it, generate it with an image tool, or use a CC0 vector). Make cut-outs from any picture with
   `python -m ytauto cutout pic.jpg --out projects/<slug>/assets --outline 4`, or use a free LottieFiles animation: `lottie: assets/x.json`. For a few seconds of real footage, use `pexels:<animal>` stock clips.
   **Direct the voice in the text:** `[pause 1.2]` before reveals, `[speed 0.85]` for menace, `[emotion 0.8]` at the climax
   (real emotion with Chatterbox; a slower pace with Kokoro). Ellipses and em dashes also change delivery.
   **B-roll:** only where the creator's script has a `B-roll:` / `Video:` / `Photo:` line, with the script's own
   search words (`stock: "<words>"` or `footage: "stock:<words>"`). Never pick search words yourself. Run
   `python -m ytauto broll <project>` and look at `build/broll_sheet.jpg` before rendering.
5. **Preview.** Run `python -m ytauto render projects/<slug> --preview` and check `build/contact_sheet.jpg`. Check that creatures are framed,
   labels aren't covered, there are no empty frames, and nothing contradicts the narration.
6. **Render and deliver**, as in the whatif-documentary skill.

## 3D animals

Leopard seals, sea lions / fur seals and pups render as Blender 3D models (`blender/creatures3d.py`, procedural mesh,
spotted shader, armature swim loop) instead of flat drawings. Sprites are cached in `remotion/public/sprites/` and built
automatically when a video needs a set that is missing (`python -m ytauto sprites` to pre-build). Per actor:
`view: three_quarter` (leopard seal), `flat: true` for the 2D drawing. Project switch: `settings.render3d: false`.

## Show what is said

Use `Anatomy` (3D jaw / body with callout lines and push-ins) for body parts, `PhotoStory` (real photos from
Openverse / Wikimedia Commons / NASA, no key needed, with parallax, tilt, pen circles and credits) for real
animals and places, `ClipCard` (highlighted source clipping) for studies and terms, `DateStamp` for dates.
Editing tips from the documentary-explainer skill: a new shot every 3–6 s; Ken Burns on every still; source
clippings with a marker that draws on in sync; date cards typed on with ticks; monochrome-to-colour for a
reveal; cuts on phrase boundaries; music 18–22 dB under the voice. See agent/SKILL.md § motion-graphics kit.

## Voice

Default: **Qwen3-TTS `ryan`** (Apache 2.0, free, commercial OK) directed with the preset's `instruct`
("calm, deep-voiced nature documentary narrator…"). Direct individual sentences with `[tone …]` in plain English
(`[tone whispered and tense]`, `[tone awed, full of wonder]`) plus `[pause 0.8]` before reveals and `[speed 0.88]` for menace.
Alternatives: other Qwen speakers (`eric`, `aiden`, `dylan`), an invented voice (`name: design`, `description: "deep, warm
British narrator"`), a cloned voice the user owns (`reference: assets/voice.wav`), or `engine: chatterbox` (faster).
Kokoro is the automatic fallback. Exact word timings come from faster-whisper alignment, so cue words land precisely.
Natural phrasing is automatic: broken or misread takes are re-voiced, and pauses are moved to punctuation only
(ytauto/prosody.py). Check the narration alone first: `python -m ytauto voiceover <project>` → build/voiceover.mp3.
Qwen on CPU is about 6× slower than real time; voice audio is cached per sentence.

## Sound

**Music:** `preset: ocean` fetches real Kevin MacLeod (Incompetech, CC BY) tracks per mood and adds the credits to the description automatically (fallback: a generated score). Set `mood:` on scenes where the feeling changes
(wonder · mystery · danger · tension · calm · none). It holds until the next change and crossfades between moods.
It ducks about 18 dB under every sentence (detected from the narration audio) and swells into pauses, like the reference.
Typical arc: calm (false safety) → mystery (descent) → danger (reveal) → wonder (superpowers) → tension (the hunt) →
danger → wonder or mystery (outro). Use your own track instead with `settings.music: {file: assets/x.mp3}`; it gets the same ducking.
**Effects:** add `sfx: [{sound: hit|thud|ticks|boom…, at: "<word>"}]`; never transition sounds (whoosh, swell, riser, glitch) (see the style guide's Sound section).

## Rules

- **Accuracy first:** never invent attacks on humans, records or numbers. If something is a theory, say so ("one theory says…").
- **Honest facts:** whatever the script's framing, keep the pictures true to it; never exaggerate danger the
  script doesn't claim.
- **No gore:** threat is shown through target brackets, silhouettes, sound and red labels, never wounds.
- **Original work:** write your own script and visuals for every animal. Reuse templates, not stories.
  YouTube demonetises repetitive mass-produced content.
