---
name: whatif-documentary
description: Use when the user asks to "make a what-if video", "make a documentary video", "make a simulation documentary", "make a video like the reference", "write and render a what-if script", "turn this topic into an infographic documentary", or wants a narrated explainer with maps, a globe, counters, stat cards, HUD timers, impact radii and key-phrase callouts rendered to MP4 with ytauto.
---

# What-If Infographic Documentary

Make narrated "what-if" or explainer documentaries in the style of
`reference/What If Russia Used a Nuke Agains Ukraine_ We Mapped Every Strike That Follows_0_304.mp4`.
That means navy infographic screens, dark maps, a vector globe, counters and timelines, stat cards, dot grids,
HUD clocks, impact radii and a dusk horizon for "event" moments. Everything is driven by `ytauto` plus the Remotion kit in
`remotion/src/docu/`. The whole pipeline runs on CPU, locally or on GitHub Actions.

Read `references/style-guide.md` before writing the shot list.
Read `references/templates.md` for every template's props.
`projects/whatif-yellowstone/script.yaml` is the complete worked example. Copy it to start a new video.

## Workflow

1. **Intake.** Get the topic or question, the target length (default 10–12 min; that's about 150 words per minute, so 1,500–1,800 words),
   the voice (default Kokoro `bm_george`; see the ocean-documentary skill's Voice section) and the output (16:9 1080p by default; add `preset: [documentary, shorts]` for vertical).
   Use the defaults when the user doesn't say, and tell them which you used.
2. **Research and script.** Write the narration as short, punchy sentences in present tense ("Day one. 4:12 a.m."). Then:
   - Open with a **cold open** (an establishing Horizon with a location title and HUD), then the **"Simulation, but nothing is made up"** SourceList.
   - Structure it in chapters: *context → history → the numbers → the event, second by second → the aftermath → what it means.*
   - Every number needs a source. Put it in the scene's `source:` line, and on SourceList rows for the main sources.
   - Mark illustrative estimates as illustrative ("Illustrative · based on …").
3. **Shot list.** Plan **one scene per beat, 5–15 seconds each**. For each beat pick a template using the beat-to-template table in the
   style guide. Choose the **cue words**, the spoken words where elements appear (`at: "Hiroshima"`). Aim for one visual change
   every 4–8 seconds. Inside a scene, staggered cues provide that change.
4. **Write `projects/<slug>/script.yaml`.** Use `preset: documentary`. Each scene has `text` (narration), `visual: {remotion: <Template>, props: {...}}`,
   and optionally `chapter`, `sfx` and `duration` (a fixed length for silent beats such as an explosion).
5. **Preview.** Run `python -m ytauto render projects/<slug> --preview` (480p). Open `build/contact_sheet.jpg`, which has one frame per scene.
   Check that nothing is cut off, there are no empty frames, the maps frame the right area, and nothing on screen contradicts the narration.
   Watch for `cue word … not found` warnings and fix the cue or the narration.
6. **Render.** Run `python -m ytauto render projects/<slug>` locally, or push and run **Actions → Render video**. Kokoro cue timing is
   estimated within each sentence; for exact word timing use `voice: {engine: edge, name: en-US-ChristopherNeural}`.
7. **Deliver.** Use `build/*.mp4`, `thumbnail.jpg`, `captions.srt` (upload it; the preset doesn't burn captions in), `description.txt` (it has chapters)
   and `contact_sheet.jpg`.

## Rules

- **Facts:** use real data with a source on screen. Clearly label simulations and estimates. Never invent quotes or statistics.
- **Real people:** never download photos of real people. Use maps, data and silhouettes, or photos the user supplies (public-domain
  sources such as Wikimedia Commons or the Library of Congress are fine if the user provides them).
- **Violence:** keep it non-graphic: flashes, fireballs, rings, numbers. No gore, and no depicted casualties beyond counts.
- **Colour:** red (`#e5372f`) only carries meaning: danger, the subject, key numbers, stamps. Teal is for neutral data and section titles.
- **Captions:** at most one key-phrase `callout` per scene, 2–6 words, in upper case. Full subtitles go to YouTube as SRT.
- **Pacing:** slow early (8–15 s holds), faster at the climax (3–6 s). Use a `duration`-only silent beat with `sfx: boom` for impact moments.
- **Monetisation:** each video must add original research and narrative. Don't mass-produce near-identical scripts.

## Sound

The `documentary` preset enables a synthesized drone bed and soft whooshes on cuts (`ytauto/sound.py`, so nothing to download).
Per scene you can add `sfx: [{sound: boom|hit|thud|riser|swell|whoosh|tick|ticks|typing|glitch|beep|alarm, at: "<word>"|seconds, volume, dur}]`.
For music, add `settings.music: {file: assets/<royalty-free>.mp3, volume: 0.10}`. It is ducked under the voice automatically.

## Adding a template

Create `remotion/src/docu/<Name>.tsx`. Wrap it in `<DocuFrame {...p}>` so it gets the backdrop, overlays and fades. Use `useT()` and `prog()`
for timing, and accept `at` props in seconds. Register it in `remotion/src/Root.tsx`: once with `SAFE` defaults and once under `Demos`.
Never give production compositions demo `defaultProps`, because Remotion merges them into every render.
Check it with `cd remotion && npx tsc -p . && npm run studio`.
