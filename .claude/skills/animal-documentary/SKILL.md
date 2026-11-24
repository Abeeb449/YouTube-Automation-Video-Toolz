---
name: animal-documentary
description: Use for ANY animal documentary on the faceless channel — land, air, rivers, insects, reptiles, birds, mammals or sea life ("make a video about honey badgers", "why nothing hunts the X", "the deadliest X", "danger and wonder video about X"). Turns a title or plain script into a narrated 1080p video with real photo and video B-roll from free sources, 3D close-ups with callouts, typed date cards, highlighted source clippings, infographics, natural narration and ducked music, using ytauto with `preset: nature`.
---

# Animal Documentary (any species)

This is the general workflow for every video on the channel. Nothing here is specific to one animal; the
leopard-seal project (`projects/sea-lions-fear-leopard-seals`) is only a worked example. Use the
`ocean-documentary` skill instead when you want the drawn deep-sea look (flat vector creatures, depth meters, sonar).

## Fastest path: script only

1. Save the narration as `projects/<slug>/script.txt`. First line `# Title`, blank lines between paragraphs,
   optional `# Chapter` lines. Add a line `Subject: <animal>` if the title doesn't name the animal plainly.
2. `python -m ytauto make projects/<slug>/script.txt --style nature` (or run the GitHub Action with style *nature*).

The planner then, for every beat:
- **names a body part** (teeth, claws, skin, eyes, tentacles, wings, stinger…) → close-up of exactly that part:
  the 3D model with a callout line if one exists (`ANATOMY_3D` in `ytauto/planner.py`), otherwise a real photo
  of "<animal> <part>" with the phrase as a callout;
- **gives a year or date** → a typed `DateStamp` (with the place if one is named), then the beat's visual;
- **gives a percentage** → `DotGrid`; another number with a unit → `Counter`;
- **is a short punchy line** → `Statement`;
- otherwise → real B-roll: free photos (`PhotoStory`: parallax push-ins, framed prints that tilt in 3D, grain,
  light leaks, credit chip) and free video clips, alternating so no two shots look the same.
Every stock shot has a fallback, so a failed search never leaves a blank or broken frame.

Then **review `script.yaml` before rendering** and sharpen it by hand (or ask any AI assistant with
`agent/SYSTEM_PROMPT.md` + `agent/SKILL.md`): pin the best photos under `assets/`, add `mark:` circles on the
detail being described, add `ClipCard`s for studies you actually cite, add maps for places.

## Rules that make it look professional (from the reference videos and the documentary-explainer skill)

- **Show exactly what is being said, at the word it is said.** Teeth → teeth. A place → a map or date card.
  A study → a clipping with the key phrase highlighted. Never a closed mouth during a line about teeth, never a
  swimming animal when the line says it rests on land.
- A new shot every 3–6 seconds; nothing is ever static (Ken Burns, parallax, camera push-ins on everything).
- Cuts land on phrase boundaries. Pauses in the voice only after complete thoughts.
- Real photos for real animals, places and events; 3D or drawings for what cameras rarely capture
  (inside a mouth, hunting from below, scale comparisons).
- Monochrome that blooms into colour for reveals; typed date cards with ticks; light leaks on photo cuts.
- Music 18–22 dB under the voice, ducked under every sentence; no drums.
- Facts on screen must be real. Never invent quotes or sources; `ClipCard` only for sources you can cite.

## Assets for a new animal

| Need | Free option |
|---|---|
| Photos | automatic (`stock:<query>`: iNaturalist for the exact species, then Unsplash with a key, Openverse, Wikimedia Commons, NASA; Pexels/Pixabay with a key) or your own files in `assets/` |
| Video clips | automatic (`stock:<query>` as a visual; Commons / NASA; Pexels/Pixabay with a key) |
| Cut-out for parallax | automatic with `parallax: true` (rembg) or `python -m ytauto cutout photo.jpg` |
| 3D close-up | add a builder to `blender/creatures3d.py` + an entry in `ytauto/sprites.py` SETS and `ANATOMY_3D` |
| Drawn animal | `image: assets/x.png` (transparent PNG) on any OceanScene actor, or a LottieFiles `lottie:` |

Licences are checked automatically: only CC0, public domain and CC BY (plus the Unsplash/Pexels/Pixabay licences);
never NC or ND. Each photo's author, licence and link go into the video description automatically, and
`build/credits.json` keeps the full licence record. Use a species' common name in `stock:` queries ("stock:honey
badger") so iNaturalist can match the exact animal.

## Voice

Two narration styles (`settings.narration`):
- `natural` (default): the voice reads the script as written, the way it naturally speaks. `[tone …]` and
  `[pause]` tags are ignored.
- `polished`: each sentence is listened back, re-voiced if a word breaks or is misread, its pauses moved to
  punctuation, and `[tone …]` / `[pause 0.4]` tags are performed.

Narrator: `settings: {voice: ryan}` (Qwen Ryan, default) or `settings: {voice: deep-british}` (Chatterbox, deep
British narrator; invented voice in `voices/`). Both work for any topic. Check the narration alone before
rendering: `python -m ytauto voiceover projects/<slug>` → `build/voiceover.mp3`; compare on the opening with
`--voice deep-british --scenes 8` (or any Qwen speaker: aiden, eric, dylan, serena, vivian, uncle_fu, ono_anna, sohee).

Full reference for every template and prop: `agent/SKILL.md`.
