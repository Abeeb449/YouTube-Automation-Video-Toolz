# 🎬 YouTube Automation Video Toolz (`ytauto`)

Turn a **script** into a finished, narrated, captioned YouTube video. It handles 10–15 minute videos and runs **free on GitHub**.

```
script.yaml / script.txt
        │
        ├─► Voiceover   Edge neural voices (free) · Piper (free, offline) · ElevenLabs · eSpeak
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
   | `PEXELS_API_KEY` | free stock videos/photos | https://www.pexels.com/api/ |
   | `PIXABAY_API_KEY` | extra free stock source | https://pixabay.com/api/docs/ |
   | `ELEVENLABS_API_KEY` | premium voices | https://elevenlabs.io |
   | `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | auto-upload to YouTube | see [YouTube upload](#7-youtube-upload-optional) |
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
    sfx: assets/whoosh.mp3                  # sound effect at the scene start

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

Every template also takes `heading`, `callout` (a bottom key-phrase box), `source` (a tiny citation), `hud` (a live clock or countdown) and `stats`.

**Graphics on the spoken word:** any `at:` can be a word instead of seconds, e.g. `at: "Hiroshima"`, `at: "bomb#2"` or `at: "launch+0.5"`. Edge voices return exact word timings; other voices estimate them.

**Sound design with no downloads:** the preset adds a low drone and whooshes on cuts. Per scene you can add `sfx: [{sound: boom, at: "detonation"}]` (built-in sounds: boom, hit, thud, riser, swell, whoosh, tick, ticks, typing, glitch, beep, alarm) or your own files.

**QC:** every render writes `build/contact_sheet.jpg` with one frame per scene. Check it before publishing.

**Blender templates** live in `blender/render.py` and are built from Python code, so no binary files are needed. Props: `text`, `subtext`, `color`, `accent`, `bg`, `font`, `resolution_percentage` (default 50 for speed; use 100 for full quality). Your own `.blend` file renders its animation for the scene's duration.

## 5. Voices

| Engine | Cost | Quality | Example `name` |
|---|---|---|---|
| `edge` (default) | free, needs internet | ★★★★ natural neural | `en-US-AndrewNeural`, `en-US-AvaNeural`, `en-GB-RyanNeural` |
| `piper` | free, fully offline | ★★★ | `en_US-lessac-medium`, `en_US-ryan-high`, `en_GB-alan-medium` |
| `elevenlabs` | paid (free tier) | ★★★★★ | your ElevenLabs voice id |
| `espeak` | free, offline | ★ robotic, last-resort fallback | `en-us` |

```bash
python -m ytauto voices --engine edge --locale en     # list voices
python -m ytauto voices --engine piper --locale en
```

If the main engine fails, for example because the network is down, ytauto automatically switches to `fallback`. Each sentence's audio is cached, so editing one line only re-voices that line.

## 6. Outputs (`projects/<name>/build/`)

- `<title>.mp4`: H.264 + AAC, `+faststart`, chapters embedded
- `thumbnail.jpg`: 1280×720 with big outlined text
- `captions.srt`: upload to YouTube for accessibility and SEO (done automatically when uploading)
- `description.txt`: your description plus a `0:00 Intro …` chapter list
- `manifest.json`: everything the uploader needs
- `contact_sheet.jpg`: one frame per scene, for a quick visual check

Caching: `projects/<name>/.cache/` keeps voice clips, stock downloads and rendered clips. Re-rendering after a small edit takes seconds. On GitHub Actions this cache is persisted between runs. Use `--clean` to start fresh.

## 7. YouTube upload (optional)

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

## 8. Tips for 10–15 minute videos

- ~150 spoken words per minute means **1,500–2,200 words** for 10–15 minutes.
- Change the visual every 8–15 seconds. Use lists of visuals or `--visuals stock`.
- Use `chapter:` on 5–10 scenes. YouTube needs ≥3 chapters, the first at 0:00 (automatic), each ≥10 s.
- Render with `--preview` first to check pacing. It renders at 480p with `ultrafast` encoding.
- Render a Blender intro once (it stays cached), or render it to `assets/intro.mp4` and reuse it as a `video:` visual across projects.

## 9. Licences and YouTube policies

- **Remotion** is free for individuals and companies with up to 3 employees. Larger companies need a [company licence](https://www.remotion.dev/license).
- **Pexels/Pixabay** content is free to use, including commercially, without attribution.
- Use only **royalty-free music** you're allowed to use, e.g. the YouTube Audio Library.
- YouTube monetisation rejects "mass-produced / repetitive" content. Make sure each video adds original value: your own research, script and perspective. Disclose realistic synthetic media when required (`youtube: {synthetic_media: true}`).

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
