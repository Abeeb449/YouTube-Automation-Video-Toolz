## Output format

The video toolkit reads the finished script by itself and turns it into the video. It reads the layout below
exactly, so use it every time and add nothing outside it. Deliver the script as plain text (pasted in the chat, a
.txt file or a PDF). Use no tables, no columns and no text boxes.

```
TITLE: The video title
CENTRAL QUESTION: ...
SHAPE: ...
LENGTH: about ... words, about ... minutes at 140 words a minute
TITLE PROMISE: ... (delivered in scene ...)
INTRO: 4

SCENE 1: HOOK (0:00 to 0:40)
3D footage only in this scene.

First paragraph of narration.

Second paragraph of narration.

SCENE 2: THE SHARK CAPITAL (0:40 to 1:50)

[B-roll] IMAGE: Map of South Africa's south coast with Cape Town, False Bay and Gansbaai marked.
Keywords: "Western Cape coast map", "Gansbaai False Bay map"

The paragraph of narration that this picture covers.

The next paragraph, which goes back to 3D.

SCENE 3: ...

B-ROLL KEYWORD LIST
Videos: every video search phrase, no repeats
Images: every image search phrase, no repeats

SOURCES
1. Name of the source — https://full-link
2. Name of the source — https://full-link

NEEDS CHECKING
Any fact that is an estimate, is disputed, or rests on a single source.
```

### What the toolkit does with each part

- **The header** (TITLE to TITLE PROMISE) is never spoken. TITLE becomes the video title.
- **INTRO: 4** is the number of seconds of music and picture before the narrator's first word. Leave it at 4
  unless the user asks for another length.
- **Scene headings** become the chapters of the video and the chapter list in the description. Write them as
  `SCENE 2: PLAIN NAME (0:40 to 1:50)`. Give every scene a short, plain name a viewer would understand, two to
  five words. The first scene is always named HOOK. Name the last scene for what it is about (for example THE
  RETURN), never "CTA". Keep every scene longer than 10 seconds.
- **`3D footage only in this scene.`** is a note for the editor. The toolkit never reads it aloud and never
  shows it. Keep writing it under the heading of every scene that has no B-roll cue.
- **Narration** is every plain paragraph under a scene heading. The narrator reads these paragraphs word for
  word and reads nothing else, so they must hold only the words to be spoken.

### Rules for the narration paragraphs

- Leave one empty line between paragraphs. Each paragraph is one to four sentences about one idea, because each
  paragraph gets its own group of shots.
- Write only spoken words. Put no stage directions, no brackets, no bold or italics, no bullet points and no
  headings inside the narration.
- Start no narration line with a label and a colon (such as "Note:", "Visual:", "Video:", "Photo:",
  "Sources:"), because the toolkit treats such lines as directions and leaves them out of the voice.
- End every sentence with a full stop, a question mark or an exclamation mark, and start the next one with a
  capital letter. The toolkit splits shots at sentence ends.
- Write years as digits (2017) and other numbers the way they should be heard ("2.6 metres", "more than
  80,000", "the third of May").

### Rules for the B-roll cues

- Write every cue in exactly this form, on its own lines, with an empty line before it and after it:

  ```
  [B-roll] VIDEO: What the viewer must see, in one plain sentence.
  Keywords: "first search phrase", "second search phrase", "fallback phrase"
  ```

- The type is `VIDEO` or `IMAGE`, in capitals, straight after `[B-roll]`.
- Place the cue directly above the one paragraph it covers. The picture or clip is used for that paragraph only.
  When the real material should cover less, put those sentences in a paragraph of their own under the cue.
- The sentence after the type says what must be visible: the animal or thing, the place, and its state (for
  example "lying dead on the beach", "leaping out of the water", "seen from above"). The toolkit checks every
  picture it finds against this sentence and drops the ones that do not show it, so describe the picture and
  nothing else.
- Always give the `Keywords:` line. Put two or three phrases in double quotes with commas between them, the most
  exact one first. They are tried in that order.
- For a map, write `[B-roll] IMAGE: Map of <region> with <place>, <place> and <place> marked.` and name every
  place to mark. The toolkit draws the map itself.
- The toolkit searches free libraries only (iNaturalist, Unsplash, Pexels, Pixabay, Openverse, Wikimedia
  Commons, NASA), and uses only pictures whose licence allows commercial use. These libraries hold general
  pictures of animals and places. They do not hold news footage of one named event, which belongs to the person
  who filmed it.
- So write most cues for something a free library can answer, on a line that such a picture truthfully fits:
  the animal the line is about ("great white shark swimming", "Cape fur seal colony", "orca pod"), or the place
  ("Gansbaai harbour", "Seal Island False Bay", "Mossel Bay"). Give at least one keyword phrase of this plain
  kind in every cue.
- A cue for the real footage of a named event may stay where the moment matters. Its last keyword phrase must
  then still be a plain one that fits the same sentence. When nothing is found, the toolkit shows the moment in 3D.

### Rules for the closing sections

- `B-ROLL KEYWORD LIST`, `SOURCES` and `NEEDS CHECKING` each stand alone on their line, in capitals, after the
  last scene. Nothing after `B-ROLL KEYWORD LIST` is spoken.
- Number every source and write its full link after its name on the same line: `1. Name — https://…`. A link
  hidden behind the name is lost when the script is saved as a PDF. The numbered sources go into the video
  description.
