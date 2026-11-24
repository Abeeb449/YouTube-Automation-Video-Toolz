# Reference voices for cloning

5-10 s WAV clips that Chatterbox (or Qwen Base) can clone:
`settings.voice: {engine: chatterbox, reference: voices/<name>.wav}` or
`python -m ytauto voiceover <project> --engine chatterbox --reference voices/<name>.wav --scenes 8`.

| File | Source |
|---|---|
| `qwen-ryan.wav` | Qwen3-TTS CustomVoice speaker "ryan" (Apache-2.0 model output) |
| `narrator-*.wav` | Invented with Qwen3-TTS VoiceDesign from a text description, not a real person |

Only add voices you have the rights to: your own recordings or synthetic ones. Never clone a real person without permission.
