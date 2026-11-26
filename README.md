# 🎬 YouTube Automation Video Toolz (`ytauto`)

Turn a **script** into a finished, narrated, captioned YouTube video. It handles 10–15 minute videos and runs **free on GitHub**.

```
script.yaml / script.txt
        │
        ├─► Voiceover   Kokoro (free, offline, commercial OK) · Edge · Chatterbox · Piper · ElevenLabs · eSpeak
        ├─► Visuals     your images/videos · Pexels/Pixabay stock · Remotion animations · Blender 3D · colour cards
        ├─► Captions    auto-timed from the voiceover → burned in + .srt for YouTube
        ├─► Audio mix   background music auto-ducked under the voice, loudness normalised to −14 LUFS
        └─► Output      MP4 (1080p) · thumbnail.jpg · captions.srt · description with chapters · manifest.json
                        → Actions artifact download and/or direct YouTube upload
```

Every tool comes pre-installed in one Docker image: **ffmpeg, Blender, Remotion (Node + Chromium), Python TTS and fonts**. The same image runs on GitHub Actions, in GitHub Codespaces, or on your own machine.

---

## 1. Where it runs (all free)

| Option | What you get | Best for |
|---|---|---|
| **GitHub Actions** (recommended) | 4 CPU / 16 GB runner, up to 6 h per job. **Unlimited minutes on public repos**, 2,000 min/month on private repos (free plan). | Hands-off rendering: click *Run workflow*, download the MP4 artifact |
| **GitHub Codespaces** | A cloud VS Code with every tool installed (`.devcontainer/`). Free monthly quota. | Editing scripts, previewing Remotion templates |
| **Your computer** | `docker build -t ytauto .` and run it | Unlimited, fastest iteration |

Rough render times for a **15-minute 1080p video** on a GitHub runner:
- Stock footage, images and colour cards: **~10–20 min**
- Mostly Remotion animated scenes: **~30–60 min**
- Blender: about **3–6 min per 3–5 s intro**. Rendered clips are cached between runs, so an unchanged intro renders only once.

## 2. Quick start on GitHub (no installs)

1. Push this repo to GitHub. Make it **public** if you want unlimited free Actions minutes.
2. *(Optional)* Add secrets under **Settings → Secrets and variables → Actions**:
   | Secret | Why | Where |
   |---|---|---|
   | `UNSPLASH_ACCESS_KEY` | free high-quality photos (Unsplash License, commercial use OK) | https://unsplash.com/developers → New Application → *Access Key* |
   | `PIXABAY_API_KEY` | free stock videos/photos | https://pixabay.com/api/docs/ (log in, the key is shown on that page) |
   | `SKETCHFAB_TOKEN` | optional: many more free 3D models (CC0 / CC BY) for the 3D shots | https://sketchfab.com/settings/password (free account → *API token*) |
   | `PEXELS_API_KEY` | optional second stock source, if you already have a key | https://www.pexels.com/api/ |
   | `ELEVENLABS_API_KEY` | premium voices | https://elevenlabs.io |

   | Variable `YTAUTO_CONTACT` (Actions *variable*, not a secret) | a URL or email Wikimedia's robot policy asks download tools to send; without it Wikimedia Commons refuses video downloads | Settings → Secrets and variables → Actions → *Variables* |

   Stock photos and clips also come **without any key** from iNaturalist (wildlife photos of the exact species),
   Openverse, Wikimedia Commons and NASA. Only CC0, public-domain and CC BY items are used (add the Actions
   *variable* `YTAUTO_STOCK_LICENSES` = `cc0,pdm,by,by-sa` to also allow CC BY-SA). Every item is credited
   in `description.txt` automatically, and `credits.json` keeps the licence record of each one.
   | `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | auto-upload to YouTube | see [YouTube upload](#8-youtube-upload-optional) |
3. Open **Actions → Render video → Run workflow**, enter `projects/example`, then click **Run**.
4. When it finishes, open the run and download the **Artifacts** zip at the bottom of the run page. It holds the MP4, thumbnail, captions and description. Artifacts are kept for 14 days. On a **private** repo only you (and collaborators) can download them. On a **public** repo any signed-in GitHub user who finds the run can.
   *(Optional: tick **Also publish as a GitHub Release** for a direct link. On a public repo that download is public.)*

Pushing a change to any `projects/<name>/script.yaml` on `main` also renders that project automatically.

## 3. Make your own video

```bash
# Option A: start from a template
python -m ytauto new projects/my-video --title "My First Video"

# Option B: paste your whole script as plain text (best for 10-15 min videos)
#   blank line = new scene, "# Heading" = new chapter + title card,
#   "[visual: pexels:ocean waves]" inside a paragraph = pick that scene's visual
python -m ytauto new projects/my-video --from-text my-script.txt --visuals stock   # or kinetic / photo

python -m ytauto render projects/my-video --preview   # fast 480p check of timing
python -m ytauto render projects/my-video             # full quality → projects/my-video/build/
```

With `--visuals stock`, ytauto picks keywords from each ~35 words of narration and pulls a matching Pexels/Pixabay clip. Long scripts therefore get fresh B-roll every ~12 seconds.

### Running locally with Docker

```bash
docker build -t ytauto .
docker run --rm -v "$PWD:/work" -e PEXELS_API_KEY ytauto python -m ytauto render projects/example
```

### Running locally without Docker
Install `ffmpeg`, Node 18+ and Python 3.10+, plus Blender if you use `blender:` visuals. Then run:
```bash
pip install -r requirements.txt
(cd remotion && npm install)
python -m ytauto doctor        # shows what's installed / missing
```

## 3b. Just a script → finished video

Write the narration in a text file. Leave a blank line between paragraphs; `# Heading` lines become chapters.
Your own directions go in the same file as short labelled lines. They are never read aloud:

```text
Intro: 4
Photo: antarctic coastline with icebergs | icebergs in antarctica

# Why Do Sea Lions Fear Leopard Seals?

A young fur seal stands at the edge of the rocks. Behind it, the colony.
B-roll: fur seal colony on a rocky beach
Details: many fur seals crowded together on rocks by the sea

The leopard seal is long, sleek and spotted.
Video: leopard seal swimming underwater

Sources: Krause et al. (2020); Muir, Barnes & Reid (2006)
```

| Line | What it does |
|---|---|
| `Intro: 4` | Seconds of music and picture before the narrator's first word (`0:04` also works). Default 4; `Intro: 0` starts straight away. Lines right under it are the opening's own pictures; without any, the opening shot holds. |
| `3D: <search words>` | A 3D model for the paragraph above, from free-licence model libraries (or your own file: `3D: assets/x.glb`). Written at the very top, before any narration, it names the model the whole video is built around. `3D: none` turns the automatic one off. |
| `B-roll: <search words>` | Stock footage for the paragraph above: a clip when the words or the line describe movement, a photo when they describe a still subject, a mix of both across the video. Each falls back to the other kind. |
| `Video: …` / `Photo: …` | The same, but only a clip / only a photo. |
| `a \| b` | Alternatives, tried in order (most exact first). |
| `Details: …` or `search -> must show` | What the picture has to show. Without it, the search words are what is checked. |
| `Visual: …`, `Note: …` | Kept as a note on the scene. Not narrated. |
| `Sources: …` | Listed in the description. Not narrated. |

**The video is built in 3D; b-roll is an extra.** Whatever the video is about is shown as a 3D model when a
free-licence one exists: the toolkit looks for the video's subject (or the words of your `3D:` line) in Smithsonian
Open Access 3D (CC0), Poly Haven (CC0), Wikimedia Commons, and Sketchfab if you add a free account token as
`SKETCHFAB_TOKEN`. Blender lights it and renders it turning (`blender/model3d.py`); scenes then push in, move
around it and label it. A model is used only if its own title names the subject and the render passes a check that
it looks like it; its credit goes in the description (a model whose licence requires attribution, CC BY, also
gets a small credit line on screen). Animals the toolkit models itself (seals, sea lions, whales,
squid, sharks, penguins…) are animated 3D scenes. **When no free model exists, one is built by hand** in Blender
(`blender/handmade/`, checked against the real thing from every side with `python -m ytauto model "<name>"`); the
Great Pyramid of Giza is the first. Where no model exists, the scene is a 3D motion graphic: kinetic
type in a 3D space, stat cards, counters, date cards, maps, quote and list cards, each chosen from what the line
itself says (several figures → stat cards, a country → a map, quoted words → a quote card, a list → a list card).

**B-roll comes from your script, never from guesses.** Stock video and photos are used only where the script asks
for them, with exactly the search words you wrote. Every other scene is an animated 3D/drawn scene or a graphic
(date cards, counters, statements). `--broll auto` brings back the old behaviour, where the toolkit picks search
words from each line itself.

**B-roll is collected before anything is edited.** The first step of every render (and `python -m ytauto broll
projects/<name>` on its own) reads the whole script, then searches, checks and downloads every item it asks for.
It writes `build/broll_report.txt` (what was asked, what was found, by whom, under which licence, or why nothing
passed) and `build/broll_sheet.jpg` (a thumbnail of each item with its scene and search words), so the material can
be reviewed before a single frame is rendered. The render then uses exactly those files and never searches again.
If nothing passes for a request, that scene keeps its drawn shot.

```bash
python -m ytauto make projects/<name>/script.txt                          # plan scenes + render (style picked from the topic)
python -m ytauto plan projects/<name>/script.txt                          # only write script.yaml (to review/edit)
python -m ytauto broll projects/<name>                                    # only collect the b-roll and write the report + sheet
python -m ytauto make projects/anglerfish/script.txt --style ocean        # or choose the look yourself
python -m ytauto make projects/<name>/script.txt --format shorts          # vertical 1080x1920 Short with captions
```

**Shorts.** `--format shorts` plans the same script as a vertical YouTube Short: 1080x1920, captions burned in,
photos and clips filling the frame, and motion graphics on a square stage over a blurred copy of themselves.
`ytauto check` fails a Short that runs longer than 3 minutes.

**Works for any topic.** `--style auto` (the default) looks at what the script is about: a sea animal the toolkit
can animate (seals, sea lions, whales, squid, sharks, penguins…) → `ocean` (animated 3D/drawn scenes); another
animal → `nature`; anything else (history, science, space, places, what-if scenarios) → `documentary` (date cards,
counters, statements, maps). Everything else is shared by
every video: the natural narration, the voice you pick, licence-checked stock photos and clips with automatic
credits, moving photos, music ducking and chapters.

On GitHub, commit `projects/<name>/script.txt` and push, or run **Render video** with that folder. The workflow plans the scenes, renders the video, and puts the generated `script.yaml` next to the MP4, so you can tweak it and re-render.

**Check before rendering:** `python -m ytauto check projects/<name>` reviews the script the way YouTube's
monetisation review looks at channels. It flags narration, openings or shot order repeated from your other
projects, facts (numbers, years, percentages) with no listed source, source clippings without a source, one template
or plain stock footage carrying most of the video, and YouTube basics (title length, 8-minute mid-roll threshold, AI
disclosure). List your research with `sources:` (a list) in `script.yaml`; it is added to the description. The
GitHub Action runs the check before every render and saves the report as `build/check.txt`.

**Every stock photo and clip is checked before it is used** (`ytauto/verify.py`, the open CLIP model). It must:
be a real camera photo or footage (not a map, chart, cartoon or screenshot); show the right subject (an animal has
to beat its look-alike species from iNaturalist); show it in the wild (not a zoo, aquarium or pool); show the
**scene the search words describe** (a "colony on rocks" is not one animal on sand, "lying on ice" is not swimming
in the surf, "at night", "aerial"…); and show **nothing graphic** (no kills, carcasses or skeletons). A video is
scanned along its length and only a 10-second stretch that passes on every sampled frame is used. Anything that
fails is skipped; if nothing passes, the scene keeps its drawn shot, never a wrong picture. The check is a model,
not a person: it can tell sand from ice reliably, but not six animals from sixty, so look at
`build/broll_sheet.jpg` before a long render.

**Animals face the right way.** In animated scenes an animal that travels faces where it is going, a hunter that
waits turns toward what it hunts, and `lookAt: <creature>` on an actor turns it toward another one. `ytauto check`
reports any that would still face away.

**The narrator follows the script too:** the narrator's overall delivery is decided from the whole script (a
grave or tense story gets a measured, suspenseful narrator; a story of discovery a warm, curious one; history a
confident one with gravitas), and each scene's delivery shifts with that scene's own emotion. A project's own
`voice.instruct` or a scene's `[tone …]` wins; `voice: {follow_content: false}` turns it off.

**Sound design follows the script, not a template** (`ytauto/sound_director.py`): for every scene the toolkit
reads the narration and its `[tone …]` directions and picks the music mood (danger, tension, mystery, wonder, epic,
calm) and places a soft accent at the exact word that calls for one (a low impact on "crashed", a deep thud on
"massive", ticks on a date, typing on "records"), only when the line is intense enough and never in quiet passages.
Hand-written `mood:` / `sfx:` win.

**No transition sounds, ever.** No whoosh on cuts or chapter changes, no swell, riser or glitch, not at the opening
and not on a reveal. They are not generated, and any that a script still lists are left out of the mix
(`ytauto/sound.py` `TRANSITION`). The music carries every change of scene on its own.

**The opening.** Every video starts with music and picture only, then the narrator comes in (4 seconds by default;
`Intro:` in the script sets it, Shorts start straight away).

**Sound that never jumps over the voice:** every music track is measured before use and plucky or percussive tracks
are skipped; sound effects are soft and capped below the narrator; after the mix, `build/audio_check.txt` lists any
sudden non-voice sound.

**Who decides the visuals? Free options only — no paid API anywhere.**
- **Built-in director** (automatic): recognises animals, depths, numbers, danger and wonder words and short punchy lines, and varies the shots. Good for drafts.
- **Your AI assistant** (best results, free): give it `agent/SYSTEM_PROMPT.md` and `agent/SKILL.md` plus your script, ask it for `script.yaml`, and save that file in the project folder. Free chat assistants work fine for this.

## 4. The script format (`script.yaml`)

```yaml
title: "5 Habits That Will Change Your Life"
description: |
  Shown on YouTube. Chapters (from `chapter:` below) are appended automatically.
tags: [habits, productivity]

settings:                       # everything here is optional
  width: 1920
  height: 1080
  fps: 30
  voice: {engine: edge, name: en-US-AndrewNeural, rate: "+5%", fallback: espeak}
  subtitles: {burn: true, font_size: 56, max_chars: 42, box: false}
  music: {file: assets/music.mp3, volume: 0.12, duck: true}   # loops + fades + ducks under the voice
  watermark: {file: assets/logo.png, position: top-right, opacity: 0.8, scale: 0.08}
  theme: {bg1: "#0f172a", bg2: "#312e81", accent: "#facc15"}  # colours for Remotion templates
  transition: fade              # fade | none
  padding: 0.35                 # pause after each scene

thumbnail: {text: "5 HABITS THAT CHANGE EVERYTHING", from_clip: 1}   # or {image: assets/thumb.jpg, text: ...}

youtube: {privacy: private, category_id: 27, playlist_id: PLxxxx, publish_at: "2026-12-01T15:00:00Z"}

scenes:
  - chapter: Intro                          # optional → YouTube chapters
    text: "Narration for this scene."       # spoken + captioned; the scene lasts as long as the voice
    visual: {remotion: TitleCard, props: {title: "Hello", subtitle: "World"}}

  - text: "Several visuals share the scene's time equally."
    visual: [pexels:city night, assets/photo.jpg, {video: assets/clip.mp4, start: 4}]

  - duration: 4                             # no narration → fixed length
    visual: {blender: intro, props: {text: "MY CHANNEL", subtext: "new videos weekly"}}
    sfx: assets/door-knock.mp3              # your own sound effect at the scene start

  - text: "Different voice just for this scene."
    voice: {name: en-US-JennyNeural}
    visual: "#111827"
```

### Visual types

| Visual | Example | Notes |
|---|---|---|
| Image | `assets/photo.jpg` or `{image: x.jpg, zoom: in\|out\|left\|right\|none, fit: cover\|contain}` | Smooth Ken Burns motion, alternating direction |
| Video | `assets/clip.mp4` or `{video: x.mp4, start: 12, speed: 0.8}` | Looped/trimmed to fit, cropped to 16:9 (`fit: contain` = blurred bars) |
| URL | `https://…/image.jpg` | Downloaded once and cached |
| Stock video | `pexels:ocean waves` | Needs `PEXELS_API_KEY` or `PIXABAY_API_KEY`. Without one it falls back to a text card. |
| Stock photo | `pexels-photo:mountain lake` | Same keys as stock video |
| Colour / text card | `"#0f172a"` or `{color: "#000", text: "Chapter 2", subtext: "..."}` | Pure ffmpeg, very fast |
| Remotion | `{remotion: TitleCard, props: {...}}` | Animated templates (see below) |
| Blender | `{blender: intro, props: {text: ...}}` · `{blender: spin}` · `{blender: scenes/logo.blend}` | 3D, CPU-rendered (Cycles) |
| Any animal, script only | `python -m ytauto make script.txt --style nature` | Real photos/video + close-ups of named body parts + date cards + infographics, planned automatically |
| 3D animals | automatic inside `OceanScene` | Blender-rendered sprite loops for leopard seal / sea lion / pup (`ytauto sprites`) |
| Motion graphics | `{remotion: Anatomy}` · `PhotoStory` · `ClipCard` · `DateStamp` | 3D close-ups with callouts, animated photos (parallax, 3D tilt, pen circles), highlighted source clippings, typed date cards |
| Free photos / clips | `stock:leopard seal` (no key) | Openverse, Wikimedia Commons, NASA; credits added to the description |

**Remotion templates** live in `remotion/src/`. Each one adapts to the scene length and the project's colours:

| Template | Props |
|---|---|
| `TitleCard` | `title`, `subtitle`, `kicker` |
| `KineticText` | `text` (defaults to the scene narration), `highlight: [words]` |
| `BulletList` | `title`, `items: [...]` |
| `BigNumber` | `value`, `prefix`, `suffix`, `label`, `decimals` |
| `Quote` | `quote`, `author` |

Preview and edit templates live with `cd remotion && npm run studio`. To add your own, create a component and register it in `remotion/src/Root.tsx`.

### What-if documentary kit (`preset: documentary`)

This is a second template set for **infographic "what-if" documentaries**: navy data screens, dark maps, a vector globe, HUD clocks and impact radii, in the style of `reference/What If Russia…mp4`. Start from `projects/whatif-yellowstone/script.yaml`. The full guide is a Claude Code skill in `.claude/skills/whatif-documentary/`, covering the workflow, style guide and every template's props.

| Template | For |
|---|---|
| `Horizon` | Cinematic dusk establishing shots; events such as flash, fireball, shockwave and mushroom cloud, with a scale ruler |
| `Globe` | Spin and zoom from space to a place, with a marker and a big date title |
| `MapScene` | Dark maps with highlighted countries, animated arrows, pulsing targets and city labels |
| `Counter` | A big number counting up, with an optional timeline and events |
| `StatCards` | Figures with bars, plus a slammed stamp ("EXPIRED") |
| `DotGrid` | "1,500 warheads" as dots |
| `BarCompare`, `SplitCompare`, `Equation`, `Clock`, `Statement`, `Radius`, `SourceList` | Comparisons, step-by-step maths, a doomsday clock, a thesis line, blast rings, sources |

Every template also takes `footage` (real B-roll behind the graphics: a video file or `"pexels:humpback whale"`), `heading`, `callout` (a bottom key-phrase box), `source` (a tiny citation), `hud` (a live clock or countdown) and `stats`.

**Graphics on the spoken word:** any `at:` can be a word instead of seconds, e.g. `at: "Hiroshima"`, `at: "bomb#2"` or `at: "launch+0.5"`. Edge voices return exact word timings; other voices estimate them.

**Sound design with no downloads:** the preset can add a low drone (no transition sounds, ever). Per scene you can add `sfx: [{sound: boom, at: "detonation"}]` (built-in sounds: boom, hit, thud, riser, swell, whoosh, tick, ticks, typing, glitch, beep, alarm) or your own files.

**QC:** every render writes `build/contact_sheet.jpg` with one frame per scene. Check it before publishing.

### Ocean / animal documentary kit (`preset: ocean`)

This kit makes "danger & wonder" deep-sea animal documentaries in the style of `reference/Why You'd Never Want To Meet A Sperm Whale.mp4`. Start from `projects/ocean-giant-squid/script.yaml`. The guide is in `.claude/skills/ocean-documentary/`.

- **`OceanScene`**: a procedural underwater world (light shafts at the surface, black abyss, drifting marine snow, animated descents) with animated flat-vector **creatures**: `spermWhale`, `giantSquid`, `orca`, `shark`, `anglerfish`, `jellyfish`, `diver`, `fishSchool`, `octopus`, `leopardSeal`, `seaLion`/`furSeal`, `penguin`, `krill`, plus `split` above/below-waterline shots with ice shelves, rocky shores and floes. For any other animal, use your own transparent PNG via `image: assets/x.png`. Overlays include big reveal words, fact chips, ✓/✕ chips, scale bars, a depth meter, a stopwatch, target lock-on brackets, echolocation waves, spotlight rings and camera push-ins.
- **B-roll:** set `footage: "pexels:sperm whale"` (or `assets/clip.mp4`) on any scene to play real footage behind the labels, fact boxes and drawn animals. Whole-scene stock clips still work as before with `visual: pexels:…`.
- **More animals:** use `lottie: assets/whale.json` for free animated animals from LottieFiles, or turn any photo or AI image into a cut-out with `python -m ytauto cutout photo.jpg --out assets --outline 4 --flip` and use it as `image: assets/photo.png`.
- **No text on top of animals:** when fact boxes are showing, animals are moved clear of them automatically.
- **`Meter`** (e.g. 0 → 236 dB), **`Sonar`** (green echolocation view), and all the documentary infographic templates with `backdrop: abyss` or `backdrop: ocean`.

**Blender templates** live in `blender/render.py` and are built from Python code, so no binary files are needed. Props: `text`, `subtext`, `color`, `accent`, `bg`, `font`, `resolution_percentage` (default 50 for speed; use 100 for full quality). Your own `.blend` file renders its animation for the scene's duration.

## 5. Voices

**Channel narrator:** `ryan` (Qwen3-TTS speaker Ryan, natural read, no audio watermark) is the default for every
project. Chatterbox voices are no longer offered because Chatterbox watermarks everything it speaks; the engine and
the invented reference voices in `voices/` remain available if you set `engine: chatterbox` yourself.

Narration style: `narration: natural` (default) reads the script as written; `narration: polished` re-records
sentences with broken words and moves pauses to punctuation.

| Engine | Licence | Quality / speed on a 4-core CPU | Example |
|---|---|---|---|
| `qwen` **(default for ocean/documentary)** | **Apache 2.0**, free, commercial OK | ★★★★★ very natural; **direct it in plain English per sentence**; about 6× slower than real time (10 min of narration ≈ 1 h) | `name: ryan` (or `eric`, `aiden`, `dylan`, `serena`, `vivian`), `instruct: "hushed nature narrator"`, or `name: design` + `description: "deep British narrator"` to invent a voice, or `reference: assets/my-voice.wav` to clone one you own |
| `chatterbox` | **MIT**, free, commercial OK | ★★★★ expressive; turbo ≈ 2.6× slower than real time; `model: standard` honours `exaggeration` (emotion) | `model: turbo`, `reference: assets/my-voice.wav` |
| `kokoro` | Apache 2.0 | ★★★ clear but flatter; 4× *faster* than real time | `bm_george`, `am_onyx` |
| `edge` | unofficial Microsoft service | ★★★★, exact word timings | `en-US-ChristopherNeural` |
| `elevenlabs` | paid for commercial use | ★★★★★ | your voice id |
| `piper`, `espeak` | free, offline | ★★ / ★ fallbacks | |

Compare them: `reference/voice-samples/voice-comparison-qwen-chatterbox.mp3` (same line in 7 voices). Every sentence's audio is cached, so editing one line only re-voices that line.

Hear the documentary narrator candidates in `reference/voice-samples/kokoro-documentary-voices.mp3`. Speed is set with `speed: 0.92` (or `rate: "-8%"`).

**Directing the voice from the script.** Emotion and flow come from the script itself. Put tags inline in a scene's `text`:

```yaml
text: "It is quiet down here. [pause 1.2] Too quiet. [speed 0.85] Something is moving in the dark. [emotion 0.9] It has already found you."
```
| Tag | Effect |
|---|---|
| `[pause]` / `[pause 1.5]` | Dramatic silence (default 0.7 s) |
| `[speed 0.85]` | Slower (or faster) delivery from here to the end of the scene |
| `[emotion 0.9]` | Intensity 0.25–1.0. With Chatterbox this drives real emotional exaggeration; with Kokoro or Edge it slows the delivery slightly |
| `[voice bm_lewis]` | Switch narrator mid-scene |
| `[tone hushed, awed]` | **Qwen3-TTS:** describe how to say the following sentences in plain English ("whispered and tense", "excited, full of wonder") |
| `[reset]` | Back to the scene's default voice |

Punctuation matters too: commas, em dashes, "…" and question marks all change the delivery. You can also set `voice:` per scene.

**Word-perfect sync.** When `faster-whisper` is installed (it's in the Docker image), ytauto listens back to every generated line and records exactly when each word is spoken. Labels, fact boxes and sound effects with `at: "word"` then land on the word for every voice engine. Without it, timings are estimated.

```bash
python -m ytauto voices --engine kokoro --locale en-gb   # list voices
python -m ytauto voices --engine edge --locale en
```

If the main engine fails, for example because the network is down, ytauto automatically switches to `fallback`. Each sentence's audio is cached, so editing one line only re-voices that line.

## 5b. Background music that follows the voice

**Real music, fetched automatically (default):** ytauto picks tracks from **Kevin MacLeod's Incompetech** library (1,400+ cinematic and ambient pieces, CC BY 4.0, widely used on YouTube) to match each scene's `mood`. It downloads them, loops and crossfades them, and adds the required credit lines to `description.txt`. You don't download anything. Other sources:

| `music:` | What happens |
|---|---|
| `{source: incompetech}` *(preset default)* | Kevin MacLeod tracks matched to moods by their "feel" tags; credits added automatically |
| `{source: openverse}` | Searches Openverse (Jamendo, Freesound…) for CC0 / CC BY music; credits added. Quality varies |
| `{source: library, library: assets/music}` | Your own folder, with sub-folders named after moods (`wonder/`, `danger/`…). Fill it once, e.g. from the YouTube Audio Library |
| `{generate: true}` | The built-in synthesized score (also the automatic fallback when offline) |
| `{file: assets/track.mp3}` | One specific track |

The **YouTube Audio Library can't be fetched automatically.** It has no public API and needs your YouTube login, so download tracks from it once into a mood folder and use `source: library`.

#### The built-in score

The `ocean` and `documentary` presets compose an **original background score** for every video. It is synthesized by `ytauto/music.py`, so it's free to monetise, with no samples and no Content ID claims. Set the feeling per scene with `mood:`. Each scene keeps the previous mood until you change it, and moods crossfade:

| `mood` | Sound | Use for |
|---|---|---|
| `wonder` | Bright, warm pads with soft high bells | Discoveries, scale, beauty |
| `mystery` | Suspended minor chords with sparse low bells | The deep, the unknown |
| `danger` | Low minor pads, a heartbeat pulse and a dissonant swell | Threat, the hunt |
| `tension` | Low cluster, rising tone, faster pulse | Build-ups before a reveal |
| `calm` | Soft open pads | Intros and outros |
| `none` | Silence | |

Listen to all five in `reference/voice-samples/background-score-moods.mp3`.

**It sits under the voice and fills the pauses.** ytauto detects exactly when the narrator is speaking from the narration audio, then dips the music just before each sentence (about 18 dB under the voice) and lets it swell back up in pauses, about 11 dB under. Short breaths between sentences lift it halfway, so the music never cuts in and out. In a test render the gaps came out at about −29 dB against −24 to −30 dB in your reference. The same pause-aware mixing applies to your own music:

```yaml
settings:
  music: {file: assets/my-track.mp3}            # or {generate: true, mood: mystery}
  # volume: 0.8 (pause level), duck: 0.45 (level while speaking), duck: false = no ducking
```

## 6. Installed tools (all free and open source, CPU only)

| Area | Tools |
|---|---|
| Video | ffmpeg (x264 with `tune animation` for crisp flat 2D), Remotion + headless Chromium (vector templates render sharp at any resolution), Lottie |
| 3D | Blender (Cycles CPU) |
| Drawing / images | Inkscape (SVG editing and conversion), ImageMagick, potrace (bitmap → vector), librsvg, rembg (AI background removal → `ytauto cutout`) |
| Voice | Kokoro, Piper, Edge, eSpeak; optional Chatterbox; faster-whisper word alignment |
| Audio | sox, built-in synthesized sound design |

Run `python -m ytauto doctor` to see what's installed. The Docker image includes all of it.

## 7. Outputs (`projects/<name>/build/`)

- `<title>.mp4`: H.264 + AAC, `+faststart`, chapters embedded
- `thumbnail.jpg`: 1280×720 with big outlined text
- `captions.srt`: upload to YouTube for accessibility and SEO (done automatically when uploading)
- `description.txt`: your description plus a `0:00 Intro …` chapter list
- `manifest.json`: everything the uploader needs
- `contact_sheet.jpg`: one frame per scene, for a quick visual check

Caching: `projects/<name>/.cache/` keeps voice clips, stock downloads and rendered clips. Re-rendering after a small edit takes seconds. On GitHub Actions this cache is persisted between runs. Use `--clean` to start fresh.

## 8. YouTube upload (optional)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project, enable **YouTube Data API v3**, and configure the OAuth consent screen. Add yourself as a test user.
2. Create **OAuth client ID → Desktop app** and download the JSON.
3. **On your own computer**, run:
   ```bash
   pip install google-api-python-client google-auth-oauthlib
   python -m ytauto youtube-auth --client-secrets client_secret.json
   ```
4. Save the three printed values as GitHub secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
5. Tick **Upload to YouTube** when running the workflow, or run `python -m ytauto upload projects/my-video --privacy unlisted`.

Notes: the API's default quota allows about 6 uploads per day. Custom thumbnails require a phone-verified channel. While your Google app is in "Testing" mode, refresh tokens expire after 7 days. Publish the app (no review is needed for personal use) to keep tokens working.

## 9. Tips for 10–15 minute videos

- ~150 spoken words per minute means **1,500–2,200 words** for 10–15 minutes.
- Change the visual every 8–15 seconds. Use lists of visuals or `--visuals stock`.
- Use `chapter:` on 5–10 scenes. YouTube needs ≥3 chapters, the first at 0:00 (automatic), each ≥10 s.
- Render with `--preview` first to check pacing. It renders at 540p with fast encoding, so it looks soft; full renders are 1080p and sharp.
- Render a Blender intro once (it stays cached), or render it to `assets/intro.mp4` and reuse it as a `video:` visual across projects.

## 10. Licences and YouTube policies

- **Remotion** is free for individuals and companies with up to 3 employees. Larger companies need a [company licence](https://www.remotion.dev/license).
- **Stock photos and clips** are licence-checked automatically: only CC0, public domain and CC BY (plus the
  Unsplash, Pexels and Pixabay licences); never NC or ND. Credits go into the description and `credits.json`.
- **AI labels:** the toolkit adds no AI tag or metadata to the MP4 (only the title and the ffmpeg encoder name).
  Qwen voices carry no watermark. **Chatterbox voices carry Resemble's inaudible PerTh watermark**, which marks
  the audio as AI speech for anyone with Resemble's detector.
- Use only **royalty-free music** you're allowed to use, e.g. the YouTube Audio Library.
- YouTube monetisation rejects "inauthentic" (mass-produced, repetitive, template-only) content; faceless channels
  are fine when each video adds original value: your own research, script and perspective.
- YouTube asks you to tick **Altered or synthetic content** for realistic content that viewers could mistake for
  real; its examples include a synthetically generated voice used for narration. Ticking it doesn't reduce reach or
  monetisation (`youtube: {synthetic_media: true}` sets it on upload).

## Project layout

```
ytauto/            Python pipeline (CLI, TTS, visuals, stock, assembly, YouTube upload)
remotion/          Animated scene templates (React + Remotion); remotion/src/docu = documentary kit
.claude/skills/    Claude Code skill: how to make what-if documentaries with this repo
blender/render.py  Procedural Blender templates + .blend renderer
projects/          One folder per video (script.yaml + assets/)
Dockerfile         ffmpeg + Blender + Node/Chromium + Python TTS environment
.github/workflows/ render.yml (render + artifact + optional upload) · ci.yml (smoke test)
.devcontainer/     GitHub Codespaces config
```
