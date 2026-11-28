"""Director's notes for "The Two Orcas That Emptied a Great White Shark Coast" → script.yaml.

The narration is taken sentence by sentence from script.txt (never retyped), so the video says exactly what the
script says. Each S(n, visual) below gives the next n sentences their shot.

    python projects/two-orcas-great-white-coast/direct.py        # rewrites script.yaml beside it
"""
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from ytauto.scriptfmt import parse_script  # noqa: E402

script = parse_script((HERE / "script.txt").read_text(encoding="utf-8"))
SENT = [s for p in script.paras for s in re.split(r'(?<=[.!?])\s+(?=[A-Z"])', p.text)]
CUES = {b.search: b for p in script.paras for b in p.broll}
scenes: list[dict] = []
_pos = 0


def cue(first_words: str):
    """The script's own b-roll cue whose search words start with these words."""
    return next(b for k, b in CUES.items() if k.lower().startswith(first_words.lower()))


def S(n: int, visual, **extra) -> None:
    """Give the next n sentences of the script this shot (a visual, or a list of visuals that share the time)."""
    global _pos
    text = " ".join(SENT[_pos:_pos + n])
    _pos += n
    sc = {**{k: v for k, v in extra.items() if k == "chapter"}, **{k: v for k, v in extra.items() if k == "mood"}, "text": text}
    sc["visuals" if isinstance(visual, list) else "visual"] = visual
    sc.update({k: v for k, v in extra.items() if k not in ("chapter", "mood")})
    scenes.append(sc)


# ------------------------------------------------------------------------------------------ shot helpers
def A(creature, x, y, scale, **kw):
    return {"creature": creature, "x": x, "y": y, "scale": scale, **kw}


def gw(x, y, scale=0.9, **kw):
    return A("greatWhite", x, y, scale, **kw)


def port(x, y, scale=1.45, **kw):
    return A("orcaPort", x, y, scale, **kw)


def star(x, y, scale=1.45, **kw):
    return A("orcaStarboard", x, y, scale, **kw)


def orca(x, y, scale=1.3, **kw):
    return A("orca", x, y, scale, **kw)


def sg(x, y, scale=0.5, **kw):
    return A("sevengill", x, y, scale, **kw)


def bw(x, y, scale=0.6, **kw):
    return A("bronzeWhaler", x, y, scale, **kw)


def seal(x, y, scale=0.4, **kw):
    return A("seaLion", x, y, scale, **kw)


def sea(*actors, **props):
    return {"remotion": "OceanScene", "props": {**props, "actors": list(actors)}}


def beach(*actors, sky="overcast", **props):
    return sea(*actors, beach={"sky": sky}, **props)


def aerial(*actors, tone="bay", **props):
    return sea(*actors, aerial={"tone": tone}, **props)


def tpl(name, **props):
    return {"remotion": name, "props": props}


# The script's eight b-roll cues ask for footage of the actual events (the 4.9 m shark on Franskraal beach, Port and
# Starboard, the Farallon island, the 2022 drone hunt, a breach at Seal Island, the 2023 sevengill carcasses, the KZN
# nets, the September 2026 sighting). The collection runs of 27 November 2026 searched every library with the
# script's own keywords: nothing free for commercial use shows them (what came back was a captive orca, Cape Town
# harbour, a snorkeller …, all turned down). Those moments are therefore shown as 3D reconstructions. To use real
# footage of one, put the licensed file in assets/ and point the shot at it.
SEARCH_SCRIPT_CUES = False


def photo(first_words, fallback, **props):
    b = cue(first_words)
    if not SEARCH_SCRIPT_CUES:
        return fallback
    return {"remotion": "PhotoStory", "props": {"layout": "full", "photos": [{"photo": "stock:" + b.search, "parallax": True, "verify": b.detail}], **props},
            "fallback_visual": fallback}


def clip(first_words, fallback):
    b = cue(first_words)
    if not SEARCH_SCRIPT_CUES:
        return fallback
    return {"stock": b.search, "verify": b.detail, "fallback_visual": fallback}


RECON = "3D reconstruction"
SOUTH_COAST = [[17.3, -35.7], [23.4, -33.0]]
CAPE_TOWN = {"name": "Cape Town", "lon": 18.42, "lat": -33.92}
GANSBAAI = {"name": "Gansbaai", "lon": 19.35, "lat": -34.58}
MOSSEL = {"name": "Mossel Bay", "lon": 22.13, "lat": -34.18}
ALGOA = {"name": "Algoa Bay", "lon": 25.70, "lat": -33.85}


# ====================================================================================== 1. HOOK
S(1, beach(gw(0.5, 0.74, 1.7, view="beached"), sky="overcast", zoom=[1.0, 1.08],
           kicker="MAY 2017", heading="South Africa", scaleBar={"x1": 0.2, "x2": 0.8, "y": 0.9, "label": "Almost 5 metres", "at": "five"}),
  chapter="Intro", mood="mystery")
S(1, sea(gw(0.3, 0.5, 2.0, to=[0.5, 0.5], view="three_quarter"), A("fishSchool", 0.82, 0.3, 0.5, to=[1.1, 0.2]),
         depth=0.3, callout="Almost no enemies in the sea", calloutAt="enemies"))
S(1, tpl("Anatomy", sprite={"creature": "greatWhiteLiver", "view": "side"}, backdrop="abyss",
         callouts=[{"x": 0.63, "y": 0.66, "label": "One clean tear", "sub": "across the chest", "at": "tear", "side": "right"},
                   {"x": 0.44, "y": 0.58, "label": "The liver", "sub": "gone", "at": "liver", "side": "left"}]))
S(1, beach(gw(0.2, 0.7, 0.75, view="beached", at=0.2), gw(0.5, 0.78, 0.85, view="beached", at="three"),
           gw(0.8, 0.7, 0.75, view="beached", flip=True, at="ashore"), sky="dusk", zoom=[1.06, 1.0],
           callout="Three more, the same wound", calloutAt="same"))
S(1, sea(port(0.0, 0.42, 1.5, to=[0.34, 0.42], silhouette="#050b10", opacity=0.92, enter="left"),
         star(-0.1, 0.66, 1.5, to=[0.22, 0.64], silhouette="#050b10", opacity=0.92, enter="left", at="two"),
         depth=0.7, callout="Two orcas, known by name", calloutAt="name"))
S(1, sea(gw(0.55, 0.3, 0.7, to=[1.3, 0.22]), gw(0.7, 0.55, 0.85, to=[1.4, 0.5]), gw(0.5, 0.78, 0.6, to=[1.3, 0.84]),
         port(-0.2, 0.45, 1.4, to=[0.2, 0.45], at="whales"), star(-0.3, 0.68, 1.4, to=[0.1, 0.66], at="whales"),
         depth=0.4, callout="The great white shark capital of the world", calloutAt="capital"))
S(1, sea(port(0.3, 0.42, 1.5, view="three_quarter", to=[0.36, 0.42]), star(0.68, 0.64, 1.5, view="three_quarter", to=[0.74, 0.64]),
         depth=0.45, zoom=[1.0, 1.1], title="The Two Orcas That Emptied a Great White Shark Coast", titleAt=0.4))

# ====================================================================================== 2. THE SHARK CAPITAL
S(1, tpl("MapScene", bbox=SOUTH_COAST, countryLabels=[{"name": "South Africa", "lon": 21.0, "lat": -33.35}],
         cities=[{**CAPE_TOWN, "at": "Cape"}, {**GANSBAAI, "at": "Gansbaai"}, {**MOSSEL, "at": 0.6},
                 {"name": "False Bay", "lon": 18.68, "lat": -34.22, "at": 0.4}],
         pulses=[{"lon": 19.35, "lat": -34.58, "at": "Gansbaai"}], title="South Africa's south coast", zoom=1.1),
  chapter="The Shark Capital", mood="calm")
S(1, sea(seal(0.1, 0.3, 0.42, detail={"rest": True}), seal(0.24, 0.28, 0.38, detail={"rest": True}, flip=True),
         seal(0.37, 0.3, 0.4, detail={"rest": True}), seal(0.48, 0.3, 0.3, detail={"rest": True, "pup": True}),
         seal(0.7, 0.62, 0.45, to=[0.86, 0.56]), seal(0.62, 0.8, 0.4, to=[0.5, 0.74]),
         split={"y": 0.42, "land": "rocks", "landWidth": 0.6, "sky": "polar", "floes": False}, zoom=[1.08, 1.0],
         kicker="A FEW KILOMETRES OFFSHORE", heading="Dyer Island", callout="A large colony of Cape fur seals", calloutAt="colony"))
S(1, sea(seal(0.14, 0.3, 0.4, detail={"rest": True}), seal(0.3, 0.28, 0.36, detail={"rest": True}, flip=True),
         seal(0.52, 0.56, 0.42, to=[0.44, 0.5], target={"at": "great"}),
         gw(1.1, 0.76, 1.1, to=[0.72, 0.74], silhouette="#071118", opacity=0.9, at="great"),
         split={"y": 0.4, "land": "rocks", "landWidth": 0.45, "sky": "polar", "floes": False},
         callout="Where there are seals, great whites follow", calloutAt="follow"))
S(1, sea(gw(0.25, 0.34, 0.8, to=[0.55, 0.32]), gw(0.8, 0.58, 1.0, to=[0.5, 0.6], view="three_quarter"), gw(0.3, 0.82, 0.6, to=[0.6, 0.84]),
         depth=0.3, callout="Sharks on almost every day of the year", calloutAt="every"))
S(1, tpl("Statement", backdrop="ocean", kicker2="1991", line1="South Africa protects the great white", line2="The first country to do so"))
S(1, sea(gw(0.75, 0.5, 1.5, to=[0.5, 0.5], view="three_quarter"), depth=0.25, zoom=[1.0, 1.12],
         callout="Cage diving grew fast", calloutAt="cage"))
S(1, tpl("Counter", backdrop="ocean", to=80000, prefix="", suffix="+", label="Visitors a year", countAt="draw", heading="Shark tourism",
         kicker="THE SOUTHERN COAST"))
S(2, tpl("DotGrid", backdrop="ocean", count=120, highlight=120, cols=20, value="The logbooks", label="Every trip, every shark seen",
         note="Boat sighting logs, Gansbaai", fillAt="log", color="#3fb6c9"))
S(3, tpl("Counter", backdrop="ocean", **{"from": 2005}, to=2017, plain=True, label="Gaps of a week or more without a great white",
         countAt=0.6, countDur=6, timeline={"start": 2005, "end": 2017, "tickEvery": 2,
                                           "events": [{"year": 2007, "label": "1 week", "at": "week#2"}, {"year": 2016, "label": "3 weeks", "at": "three"}]}))
S(1, sea(A("fishSchool", 0.3, 0.4, 0.6, to=[0.45, 0.36]), seal(0.75, 0.6, 0.42, to=[0.6, 0.64]),
         depth=0.3, zoom=[1.0, 1.1], kicker="EARLY 2017", heading="Gansbaai", callout="Empty days in the logbooks", calloutAt="empty"))

# ====================================================================================== 3. BODIES ON THE BEACH
S(2, beach(gw(0.5, 0.76, 0.95, view="beached"), sky="overcast", zoom=[1.0, 1.06], kicker="FEBRUARY 2017", heading="Near Gansbaai",
           scaleBar={"x1": 0.335, "x2": 0.665, "y": 0.9, "label": "2.6 metres", "at": "metres"}),
  chapter="Bodies on the Beach", mood="mystery")
S(1, beach(gw(0.5, 0.74, 1.25, view="beached"), sky="overcast", zoom=[1.08, 1.2], callout="Body whole. Cause unknown.", calloutAt="nobody"))
S(1, beach(gw(0.5, 0.74, 1.7, view="beached"), sky="dusk", zoom=[1.1, 1.0], kicker="3 MAY 2017", heading="The big female"))
S(1, photo("4.9m great white", tpl("MapScene", bbox=[[18.95, -34.85], [19.85, -34.38]], cities=[{**GANSBAAI, "at": 0.3}],
                                   pulses=[{"lon": 19.395, "lat": -34.605, "label": "Franskraal beach", "at": 0.5}],
                                   title="3 May 2017", subtitle="Franskraal beach", zoom=1.1)))
S(1, beach(gw(0.5, 0.72, 1.7, view="beached"), sky="dusk", heading="Franskraal beach", kicker="DYER ISLAND CONSERVATION TRUST",
           scaleBar={"x1": 0.2, "x2": 0.8, "y": 0.9, "label": "4.9 metres · about 16 feet", "at": "measured"}))
S(2, tpl("StatCards", backdrop="ocean", center=True, cards=[{"label": "Length", "value": "4.9 m", "at": 0.3}, {"label": "Weight", "value": "1,110 kg", "at": "weight"}],
         stamp={"text": "Largest ever dissected in South Africa", "at": "larger"}))
S(1, sea(gw(0.2, 0.5, 1.3, to=[0.6, 0.48], view="three_quarter"), seal(0.85, 0.2, 0.36, to=[0.95, 0.14]),
         depth=0.3, kicker="ALMOST A YEAR EARLIER", heading="Alive at Dyer Island"))
S(1, tpl("Anatomy", sprite={"creature": "greatWhite", "view": "side"}, backdrop="abyss",
         callouts=[{"x": 0.66, "y": 0.72, "label": "The tear", "sub": "between the front fins", "at": "tear", "side": "right"}],
         zoom=[{"at": "tear", "x": 0.66, "y": 0.66, "scale": 1.5}]))
S(1, tpl("Anatomy", sprite={"creature": "greatWhiteLiver", "view": "side"}, backdrop="abyss",
         callouts=[{"x": 0.46, "y": 0.6, "label": "The liver", "sub": "the only thing missing", "at": "liver", "side": "left"}]))
S(2, beach(gw(0.36, 0.76, 1.25, view="beached"), gw(0.82, 0.66, 0.7, view="beached", flip=True, opacity=0.9), sky="overcast",
           kicker="4 MAY 2017", heading="A male", callout="Liver gone. Heart gone.", calloutAt="heart"))
S(2, tpl("SourceList", backdrop="ocean", tag="Gansbaai, 2017", tagNote="great whites washed ashore",
         rows=[{"title": "February · young female, 2.6 m", "source": "body whole", "at": 0.3},
               {"title": "3 May · female, 4.9 m", "source": "liver missing", "at": 0.9},
               {"title": "4 May · male", "source": "liver and heart missing", "at": 1.5},
               {"title": "Later in May · great white", "source": "the same torn chest", "at": "May"},
               {"title": "June · great white", "source": "the same torn chest", "at": "June"}]))
S(1, sea(orca(0.3, 0.45, 2.2, silhouette="#050b10", opacity=0.55, blur=3), gw(0.56, 0.56, 1.5, view="three_quarter"),
         depth=0.6, callout="Scratches left by orca teeth", calloutAt="scratches"))
S(1, sea(port(-0.2, 0.4, 1.4, to=[0.3, 0.42], silhouette="#050b10", opacity=0.9), star(-0.4, 0.66, 1.4, to=[0.12, 0.64], silhouette="#050b10", opacity=0.9),
         depth=0.7, callout="She had a good idea who had done it", calloutAt="idea"))
S(1, sea(sg(0.9, 0.6, 1.1, to=[0.55, 0.58], label={"text": "Sevengill shark", "at": "different"}), depth=0.55, zoom=[1.0, 1.1],
         callout="The same wound, on a different shark", calloutAt="different"))

# ====================================================================================== 4. TWO BENT FINS
S(1, tpl("MapScene", bbox=[[18.0, -34.6], [19.3, -33.75]], cities=[{**CAPE_TOWN, "at": "Cape"}],
         countryLabels=[{"name": "False Bay", "lon": 18.68, "lat": -34.22}],
         title="Two years earlier", subtitle="False Bay, 2015", zoom=1.14),
  chapter="Two Bent Fins", mood="mystery")
S(1, sea(sg(0.15, 0.62, 0.5, to=[0.4, 0.6]), sg(0.75, 0.7, 0.55, to=[0.5, 0.72]), sg(0.4, 0.8, 0.45, to=[0.62, 0.82]),
         sg(0.9, 0.52, 0.4, to=[0.7, 0.5]), sg(0.25, 0.44, 0.38, to=[0.45, 0.42]), sg(0.6, 0.36, 0.34, to=[0.4, 0.34]),
         depth=0.5, callout="Up to 70 sevengill sharks on one dive", calloutAt="count"))
S(1, sea(sg(0.3, 0.6, 1.5, to=[0.5, 0.6], label={"text": "Sevengill shark", "at": 0.5}), depth=0.55, zoom=[1.0, 1.08],
         callout="Hunts close to the seabed", calloutAt="seabed"))
S(1, sea(A("fishSchool", 0.7, 0.5, 0.5, to=[0.55, 0.46]), depth=0.5, kicker="9 NOVEMBER 2015", heading="The same reef", bigText="NONE", bigAt="none"))
S(1, sea(sg(0.3, 0.84, 0.7, view="beached", opacity=0.9), sg(0.66, 0.9, 0.6, view="beached", flip=True, opacity=0.85), sg(0.86, 0.8, 0.45, view="beached", opacity=0.8),
         depth=0.65, rays=False, callout="Carcasses on the seabed", calloutAt="carcasses"))
S(1, beach(sg(0.16, 0.7, 0.5, view="beached"), sg(0.36, 0.8, 0.6, view="beached", flip=True), sg(0.56, 0.7, 0.5, view="beached"),
           sg(0.76, 0.8, 0.6, view="beached"), sg(0.9, 0.68, 0.42, view="beached", flip=True), sky="overcast",
           kicker="APRIL 2016", heading="False Bay", callout="Alison Kock examined five", calloutAt="five"))
S(2, tpl("Anatomy", sprite={"creature": "sevengill", "view": "side"}, backdrop="abyss",
         callouts=[{"x": 0.6, "y": 0.7, "label": "Torn chest", "at": "torn", "side": "right"},
                   {"x": 0.42, "y": 0.62, "label": "No liver", "at": "liver", "side": "left"},
                   {"x": 0.75, "y": 0.4, "label": "Orca tooth marks", "sub": "on the skin", "at": "marks", "side": "right"}]))
S(1, tpl("Statement", backdrop="ocean", kicker2="The first proof", line1="Orcas were killing sharks", line2="for a single organ"))
S(1, sea(port(0.3, 0.42, 1.6, view="three_quarter", to=[0.34, 0.42]), star(0.7, 0.66, 1.6, view="three_quarter", to=[0.74, 0.66]),
         depth=0.3, surface=True, zoom=[1.0, 1.12], callout="Their tall back fins have folded over", calloutAt="folded"))
S(1, aerial(port(0.34, 0.47, 1.3, view="top", rotate=-90, idle=False, label={"text": "Leans left", "at": "left", "dy": 0.43}),
            star(0.66, 0.47, 1.3, view="top", rotate=-90, idle=False, label={"text": "Leans right", "at": "right", "dy": 0.43}),
            zoom=[1.0, 1.06], source="Seen from above"))
S(1, photo("Port and Starboard orcas",
           aerial(port(0.34, 0.45, 1.3, view="top", rotate=-90, idle=False, label={"text": "Port", "at": "Port", "dy": 0.42}),
                  star(0.66, 0.45, 1.3, view="top", rotate=-90, idle=False, label={"text": "Starboard", "at": "Starboard", "dy": 0.42}),
                  zoom=[1.06, 1.12], callout="Port = left · Starboard = right", calloutAt="sailor's")))
S(2, sea(port(0.2, 0.42, 1.5, to=[0.4, 0.42]), star(0.32, 0.68, 1.5, to=[0.52, 0.68]), depth=0.35,
         callout="They may be half-brothers", calloutAt="half-brothers"))
S(2, tpl("MapScene", bbox=[[11.0, -37.0], [29.5, -24.0]], countryLabels=["Namibia", "South Africa"],
         cities=[{**CAPE_TOWN, "at": 0.4}, {"name": "Port Elizabeth", "lon": 25.6, "lat": -33.96, "at": "Port"}],
         pulses=[{"lon": 15.16, "lat": -26.65, "label": "Lüderitz · 2009", "at": "Namibia"}],
         arrows=[{"from": [15.0, -27.2], "to": [18.6, -35.0], "at": "Since", "dur": 1.6, "curve": 0.25},
                 {"from": [18.9, -35.2], "to": [25.6, -34.4], "at": "coast", "dur": 1.6, "curve": 0.12}],
         title="Port and Starboard", subtitle="Where they have been seen"))
S(1, aerial(port(0.2, 0.42, 1.3, view="top", to=[0.5, 0.42]), star(0.1, 0.64, 1.3, view="top", to=[0.42, 0.62]),
            kicker="FEBRUARY 2017", heading="Off Gansbaai", callout="Seen the day before the first dead shark", calloutAt="day", source=RECON))
S(1, sea(star(0.24, 0.5, 1.5, to=[0.3, 0.5]), A("greatWhiteLiver", 0.74, 0.52, 1.1, flip=True, idle=False), depth=0.6,
         title="Why the liver?", titleAt="why"))

# ====================================================================================== 5. WHY THE LIVER
S(1, sea(gw(0.3, 0.6, 1.3, to=[0.55, 0.46]), depth=0.35, heading="Why the Liver", kicker="PART 4",
         callout="How does a shark stay afloat?", calloutAt="afloat"),
  chapter="Why the Liver", mood="wonder")
S(1, tpl("Anatomy", sprite={"creature": "fishBladder", "view": "side"}, backdrop="ocean", kicker="MOST FISH",
         callouts=[{"x": 0.5, "y": 0.42, "label": "Swim bladder", "sub": "a small bag of gas", "at": "bladder", "side": "right"}]))
S(1, tpl("Anatomy", sprite={"creature": "greatWhiteLiver", "view": "side"}, backdrop="ocean", kicker="A SHARK",
         callouts=[{"x": 0.46, "y": 0.6, "label": "The liver", "sub": "huge and oily", "at": "liver", "side": "left"}]))
S(2, tpl("Anatomy", sprite={"creature": "greatWhiteLiver", "view": "side"}, backdrop="abyss",
         callouts=[{"x": 0.46, "y": 0.6, "label": "A quarter to a third", "sub": "of the whole body weight", "at": "quarter", "side": "left"},
                   {"x": 0.56, "y": 0.64, "label": "Mostly fat", "at": "fat", "side": "right"}],
         zoom=[{"at": "quarter", "x": 0.5, "y": 0.6, "scale": 1.35}]))
S(1, sea(A("greatWhiteLiver", 0.12, 0.5, 1.2, to=[0.86, 0.48]), depth=0.5, zoom=[1.0, 1.04],
         callout="Fat is its fuel on long ocean trips", calloutAt="fuel"))
S(1, sea(star(0.22, 0.5, 1.5, to=[0.3, 0.5]), A("greatWhiteLiver", 0.75, 0.52, 1.1, flip=True, idle=False, ring={"at": "liver", "r": 0.09}),
         depth=0.5, callout="Hundreds of kilograms of rich food", calloutAt="hundreds"))
S(1, sea(A("orcaMale", 0.42, 0.5, 2.6, to=[0.46, 0.5]), depth=0.45, zoom=[1.3, 1.5], focus=[0.78, 0.52],
         callout="Taking only the liver may protect the teeth", calloutAt="protect"))
S(1, {"model": "shark skin", "props": {"shot": "push", "callout": "Tiny scales shaped like teeth", "calloutAt": "scales", "heading": "Shark skin, up close"},
      "fallback_visual": sea(gw(0.5, 0.5, 2.6, view="three_quarter"), depth=0.4, zoom=[1.4, 1.8], focus=[0.5, 0.5],
                             callout="Tiny scales shaped like teeth", calloutAt="scales")})
S(1, {"model": "orca teeth", "props": {"shot": "turn", "callout": "Worn down flat by shark skin", "calloutAt": "flat", "heading": "Orca teeth"},
      "fallback_visual": tpl("Statement", backdrop="ocean", kicker2="Orcas that eat a lot of shark", line1="wear their teeth", line2="down flat")})
S(1, tpl("StatCards", backdrop="ocean", center=True, cards=[{"label": "Since", "value": "1969", "at": 0.3},
                                                             {"label": "Dead orcas with flat-worn teeth and shark in the stomach", "value": "3", "at": "three"}],
         stamp={"text": "Washed up in South Africa", "at": "washed"}))
S(1, sea(port(0.2, 0.42, 1.5, to=[0.42, 0.42]), star(0.3, 0.68, 1.5, to=[0.52, 0.68]), depth=0.4,
         callout="The shark-eating type", calloutAt="shark-eating"))
S(1, sea(star(0.2, 0.5, 1.5, to=[0.34, 0.5]), A("greatWhiteLiver", 0.76, 0.52, 1.1, flip=True, idle=False, target={"at": "tear"}),
         depth=0.55, callout="The richest part, with very little chewing", calloutAt="richest"))
S(1, sea(gw(0.4, 0.36, 0.8, to=[0.5, 0.34]), gw(0.6, 0.6, 1.0, to=[0.7, 0.6]), gw(0.35, 0.8, 0.7, to=[0.45, 0.8]),
         depth=0.35, callout="The great whites made a move of their own", calloutAt="move"))

# ====================================================================================== 6. THE EMPTY SEA
S(1, sea(gw(0.45, 0.36, 0.8, to=[1.35, 0.3]), gw(0.6, 0.6, 1.0, to=[1.45, 0.62]), gw(0.4, 0.8, 0.7, to=[1.3, 0.86]),
         depth=0.35, bigText="THEY LEFT", bigAt="left", duration=3.5),
  chapter="The Empty Sea", mood="tension")
S(1, tpl("ClipCard", publication="African Journal of Marine Science", title="Fear at the top", date="2022",
         lines=["Five and a half years of boat sightings", "Signals from tagged great white sharks", "Gansbaai, South Africa"],
         highlight=[{"text": "Five and a half years", "at": "five"}, {"text": "tagged great white sharks", "at": "tagged"}],
         source="Towner et al. 2022"))
S(1, aerial(port(-0.1, 0.4, 1.2, view="top", to=[0.22, 0.42]), star(-0.2, 0.62, 1.2, view="top", to=[0.12, 0.6]),
            gw(0.5, 0.3, 0.75, view="top", to=[1.2, 0.1]), gw(0.6, 0.55, 0.8, view="top", to=[1.3, 0.5]), gw(0.5, 0.78, 0.7, view="top", to=[1.2, 0.95]),
            gw(0.72, 0.4, 0.6, view="top", to=[1.3, 0.28]), heading="14 tagged great whites", kicker="TRACKED LEAVING GANSBAAI",
            callout="They left when the orcas were near", calloutAt="near", source=RECON))
S(2, sea(seal(0.3, 0.4, 0.42, to=[0.5, 0.44]), A("fishSchool", 0.75, 0.62, 0.55, to=[0.6, 0.58]), depth=0.3,
         heading="Stayed away", stats=[{"label": "After the first attacks", "value": "Weeks"}, {"label": "Later", "value": "Months"}], statsAt="weeks"))
S(1, tpl("StatCards", backdrop="ocean", center=True, cards=[{"label": "Sightings kept dropping for", "value": "2½ years", "at": "dropping"}]))
S(1, sea(seal(0.2, 0.3, 0.4, to=[0.45, 0.34]), seal(0.8, 0.62, 0.42, to=[0.6, 0.58]), A("fishSchool", 0.5, 0.78, 0.6, to=[0.4, 0.74]),
         depth=0.25, surface=True, zoom=[1.0, 1.1], callout="Not a single great white", calloutAt="single"))
S(1, tpl("Statement", backdrop="ocean", kicker2="Alison Towner's comparison", line1="Wild dogs keep away from lions", line2="Great whites keep away from orcas"))
S(1, sea(orca(0.12, 0.5, 2.0, silhouette="#050b10", opacity=0.6, blur=4), gw(0.55, 0.52, 1.0, to=[1.3, 0.46]), depth=0.5,
         callout="The fear of being hunted was enough", calloutAt="fear"))
S(1, tpl("Globe", **{"from": [19.3, -34.6]}, to=[-123.0, 37.7], zoomFrom=1.0, zoomTo=2.2,
         marker={"label": "Southeast Farallon Island", "note": "off San Francisco", "at": "other"}))
S(1, tpl("MapScene", bbox=[[-123.7, 37.2], [-121.9, 38.2]], cities=[{"name": "San Francisco", "lon": -122.42, "lat": 37.77, "at": "San"}],
         pulses=[{"lon": -123.0, "lat": 37.7, "label": "Southeast Farallon Island", "at": "Farallon"}],
         title="2 November 2009", subtitle="Orcas pass the island"))
S(1, photo("Southeast Farallon Island aerial",
           aerial(orca(-0.1, 0.4, 1.2, view="top", to=[0.9, 0.36]), orca(-0.25, 0.6, 1.1, view="top", to=[0.75, 0.58]), tone="open",
                  hud={"label": "Near the island for", "value": "≈ 2.5 hours"}, source=RECON),
           hud={"label": "Orcas near the island for", "value": "≈ 2.5 hours"}))
S(1, tpl("DotGrid", backdrop="ocean", count=17, highlight=17, cols=9, value="17", label="Tagged great whites feeding at the island",
         note="Southeast Farallon Island, 2 November 2009", fillAt=0.4, color="#3fb6c9"))
S(1, aerial(gw(0.5, 0.36, 0.7, view="top", to=[1.2, 0.05]), gw(0.42, 0.5, 0.8, view="top", to=[-0.3, 0.3]), gw(0.56, 0.62, 0.75, view="top", to=[1.3, 0.9]),
            gw(0.4, 0.68, 0.65, view="top", to=[-0.25, 0.95]), gw(0.6, 0.46, 0.6, view="top", to=[1.3, 0.4]), tone="open",
            hud={"label": "Every one gone within", "value": "8 hours"}, source=RECON))
S(1, tpl("DotGrid", backdrop="ocean", count=17, highlight=16, cols=9, value="16 of 17", label="Stayed away for the rest of the season", fillAt="stayed"))
S(1, tpl("BarCompare", backdrop="ocean", heading="Elephant seals killed by great whites", kicker="SOUTHEAST FARALLON ISLAND",
         bars=[{"label": "A normal year", "value": 7, "display": "A normal year's kills", "at": 0.5},
               {"label": "A year when orcas visited", "value": 1, "display": "Sometimes only a seventh", "at": "seventh"}]))
S(1, sea(orca(0.22, 0.5, 1.5, to=[0.36, 0.5]), A("greatWhiteLiver", 0.76, 0.52, 1.0, flip=True, idle=False),
         depth=0.5, kicker="OCTOBER 1997", heading="Southeast Farallon Island", callout="It ate only the liver", calloutAt="liver", source=RECON))
S(1, sea(star(0.0, 0.5, 1.5, to=[0.4, 0.5], silhouette="#050b10", opacity=0.9), gw(0.8, 0.52, 0.9, to=[0.9, 0.5], silhouette="#0a1a24", opacity=0.9),
         depth=0.7, heading="South Africa", callout="Never caught on film", calloutAt="filmed"))
S(1, tpl("DateStamp", date="2022", place="Mossel Bay, South Africa", at=0.2))

# ====================================================================================== 7. CAUGHT ON CAMERA
S(1, tpl("MapScene", bbox=SOUTH_COAST, countryLabels=[{"name": "South Africa", "lon": 21.0, "lat": -33.35}],
         cities=[{**CAPE_TOWN, "at": 0.3}, {**GANSBAAI, "at": 0.4}],
         pulses=[{"lon": 22.13, "lat": -34.18, "label": "Mossel Bay", "at": "Mossel"}],
         arrows=[{"from": [19.6, -34.75], "to": [22.0, -34.35], "at": "further", "dur": 1.4, "curve": 0.15}],
         title="16 May 2022", subtitle="A drone over Mossel Bay"),
  chapter="Caught on Camera", mood="danger")
CHASE = aerial(gw(0.62, 0.46, 0.8, view="top", to=[0.9, 0.4]),
               star(0.34, 0.5, 1.2, view="top", to=[0.62, 0.46]), orca(0.2, 0.3, 1.05, view="top", to=[0.5, 0.28]),
               orca(0.16, 0.7, 1.05, view="top", to=[0.46, 0.68]), orca(0.02, 0.44, 1.0, view="top", to=[0.32, 0.4]),
               orca(-0.02, 0.62, 0.9, view="top", to=[0.26, 0.6]),
               heading="Mossel Bay", kicker="16 MAY 2022", callout="Five orcas, one great white", calloutAt="five", source=RECON)
S(1, clip("orcas kill great white", CHASE))
S(1, aerial(star(0.4, 0.5, 2.0, view="top", to=[0.52, 0.5], label={"text": "Starboard", "at": "Starboard", "dy": 0.2}),
            orca(0.08, 0.2, 1.1, view="top", to=[0.2, 0.2], opacity=0.85), orca(0.05, 0.84, 1.1, view="top", to=[0.18, 0.82], opacity=0.85),
            zoom=[1.0, 1.1], source=RECON))
S(1, aerial(gw(0.5, 0.4, 0.8, view="top", to=[0.85, 0.62]), star(0.2, 0.36, 1.2, view="top", to=[0.55, 0.52]),
            orca(0.1, 0.62, 1.05, view="top", to=[0.44, 0.74]), orca(0.0, 0.2, 1.0, view="top", to=[0.34, 0.3]),
            hud={"label": "The chase", "value": "≈ 1 hour"}, source=RECON))
S(2, aerial(orca(0.5, 0.5, 1.15, view="top", rotate=-20, idle=False),
            gw(0.5, 0.5, 0.75, view="top", orbit={"cx": 0.5, "cy": 0.5, "r": 0.2, "turns": 1.6, "phase": 0.6}),
            callout="Tight circles, keeping the hunter in sight", calloutAt="circles", source=RECON))
S(1, aerial(orca(0.5, 0.5, 1.1, view="top", rotate=-20, idle=False),
            gw(0.5, 0.5, 0.75, view="top", orbit={"cx": 0.5, "cy": 0.5, "r": 0.2, "turns": 0.9, "phase": 0.2}),
            star(0.02, 0.14, 1.15, view="top", to=[0.24, 0.26]), orca(0.98, 0.14, 1.0, view="top", to=[0.78, 0.26]),
            orca(0.02, 0.9, 1.0, view="top", to=[0.22, 0.76]), orca(0.98, 0.9, 1.0, view="top", to=[0.78, 0.76]),
            callout="It could only watch one at a time", calloutAt="watch", source=RECON))
S(1, sea(star(0.18, 0.5, 1.5, to=[0.34, 0.5]), A("greatWhiteLiver", 0.74, 0.52, 1.1, flip=True, idle=False, ring={"at": "liver", "r": 0.09}),
         depth=0.4, callout="Bitten right where the liver sits", calloutAt="liver", source=RECON))
S(1, tpl("StatCards", backdrop="ocean", center=True, cards=[{"label": "More sharks thought to have died that day", "value": "3", "at": "three"}]))
S(1, aerial(star(0.14, 0.5, 0.95, view="top", rotate=-90, idle=False, label={"text": "Starboard", "at": 0.4, "dy": 0.26}),
            orca(0.32, 0.5, 0.9, view="top", rotate=-90, idle=False, label={"text": "New", "at": "Four", "dy": 0.26, "color": "#e5372f"}),
            orca(0.5, 0.5, 0.85, view="top", rotate=-90, idle=False, label={"text": "New", "at": "Four+0.2", "dy": 0.26, "color": "#e5372f"}),
            orca(0.68, 0.5, 0.9, view="top", rotate=-90, idle=False, label={"text": "New", "at": "Four+0.4", "dy": 0.26, "color": "#e5372f"}),
            orca(0.86, 0.5, 0.8, view="top", rotate=-90, idle=False, label={"text": "New", "at": "Four+0.6", "dy": 0.26, "color": "#e5372f"}),
            heading="Four of the five", kicker="NEVER LINKED TO SHARK HUNTING BEFORE"))
S(1, sea(orca(0.3, 0.42, 1.4, to=[0.5, 0.42]), orca(0.2, 0.66, 1.0, to=[0.4, 0.64]), orca(0.08, 0.8, 0.75, to=[0.28, 0.78]),
         depth=0.35, callout="Orcas learn from one another", calloutAt="learn"))
S(2, tpl("StatCards", backdrop="ocean", center=True, heading="Great whites seen by survey boats", kicker="MOSSEL BAY",
         cards=[{"label": "Before the hunt", "value": "Every trip", "at": 0.4}, {"label": "45 days after", "value": "1", "at": "after"}]))
S(1, sea(star(0.2, 0.5, 1.9, view="three_quarter", to=[0.5, 0.5], label={"text": "Starboard", "at": "Starboard"}), depth=0.4,
         kicker="A YEAR LATER", heading="Alone"))
S(1, sea(star(0.1, 0.48, 1.5, to=[0.38, 0.5]), gw(0.6, 0.56, 0.5, to=[0.84, 0.6]), depth=0.35, kicker="18 JUNE 2023", heading="Mossel Bay",
         scaleBar={"x1": 0.74, "x2": 0.94, "y": 0.72, "label": "About 2.5 metres", "at": "metres"}, source=RECON))
S(1, tpl("Anatomy", sprite={"creature": "greatWhite", "view": "three_quarter"}, backdrop="abyss",
         callouts=[{"x": 0.6, "y": 0.78, "label": "Grabbed here", "sub": "the side fin", "at": "fin", "side": "right"}]))
S(1, sea(star(0.2, 0.5, 1.5, to=[0.36, 0.5]), A("greatWhiteLiver", 0.74, 0.54, 0.6, flip=True, idle=False), depth=0.4,
         hud={"label": "Start to finish", "value": "Under 2 minutes"}, callout="Torn open, liver taken", calloutAt="liver", source=RECON))
S(1, aerial(star(0.16, 0.5, 1.1, view="top", idle=False, label={"text": "Starboard", "at": 0.3, "dy": 0.2}),
            port(0.86, 0.5, 1.1, view="top", rotate=180, idle=False, label={"text": "Port", "at": "Port", "dy": 0.2}),
            scaleBar={"x1": 0.28, "x2": 0.74, "y": 0.5, "label": "About 100 metres", "at": "hundred"}, source=RECON))
S(1, beach(gw(0.5, 0.74, 1.25, view="beached"), sky="overcast", kicker="THE SAME DAY", heading="A second great white",
           scaleBar={"x1": 0.28, "x2": 0.72, "y": 0.9, "label": "3.5 metres", "at": "metres"}))
S(1, tpl("StatCards", backdrop="ocean", center=True, cards=[{"label": "Great whites kept away from that part of the bay for", "value": "≈ 4 months", "at": "four"}]))
S(1, sea(bw(1.1, 0.5, 0.7, to=[0.62, 0.5], at="other"), bw(1.2, 0.72, 0.6, to=[0.74, 0.7], at="other"), depth=0.3,
         callout="Other animals took their place", calloutAt="place"))

# ====================================================================================== 8. A COAST REARRANGED
S(1, sea(bw(0.9, 0.44, 0.9, to=[0.56, 0.46], label={"text": "Bronze whaler", "at": "bronze"}), bw(1.1, 0.72, 0.7, to=[0.74, 0.7]),
         depth=0.3, heading="Gansbaai", kicker="A SMALLER SHARK MOVES IN"),
  chapter="A Coast Rearranged", mood="wonder")
S(1, sea(gw(0.24, 0.5, 1.2, lookAt="right"), bw(0.8, 0.56, 0.65, to=[0.96, 0.58], target={"at": "eat"}),
         depth=0.4, callout="Great whites eat bronze whalers", calloutAt="eat"))
S(1, sea(bw(0.2, 0.34, 0.7, to=[0.44, 0.34]), bw(0.82, 0.52, 0.85, to=[0.56, 0.52]), bw(0.3, 0.74, 0.6, to=[0.5, 0.76]), bw(0.9, 0.82, 0.55, to=[0.7, 0.82]),
         depth=0.25, surface=True, callout="Bronze whalers on most trips", calloutAt="most"))
S(1, tpl("MapScene", bbox=[[18.0, -34.6], [19.3, -33.75]], cities=[{**CAPE_TOWN, "at": 0.4}],
         countryLabels=[{"name": "False Bay", "lon": 18.72, "lat": -34.3}], pulses=[{"lon": 18.58, "lat": -34.14, "label": "Seal Island", "at": 0.8}],
         title="False Bay", subtitle="The change went further", zoom=1.12))
S(1, clip("great white shark breach",
          sea(seal(0.62, 0.3, 0.4, to=[0.8, 0.22]), gw(0.36, 0.95, 1.3, to=[0.56, 0.3], rotate=-62, at=0.3),
              split={"y": 0.34, "land": "rocks", "landWidth": 0.24, "sky": "polar", "floes": False},
              heading="Seal Island", callout="Great whites leaping clear of the water", calloutAt="leaping", source=RECON)))
S(2, tpl("Counter", backdrop="ocean", **{"from": 2000}, to=2018, plain=True, label="Great whites recorded at Seal Island",
         countAt=0.5, countDur=6, timeline={"start": 2000, "end": 2026, "tickEvery": 4,
                                           "events": [{"year": 2000, "label": "Surveys begin", "at": "surveyed"}, {"year": 2018, "label": "None after August 2018", "at": "August"}],
                                           "band": {"from": 2018.6, "to": 2026, "label": "none recorded"}}))
S(2, tpl("BarCompare", backdrop="ocean", heading="Great white sightings", kicker="SHARK SPOTTERS, CAPE TOWN BEACHES",
         bars=[{"label": "2011", "value": 300, "display": "More than 300", "at": "logged"}, {"label": "2019", "value": 0, "display": "None", "at": "none"}]))
S(1, sea(sg(1.1, 0.5, 0.8, to=[0.6, 0.5], label={"text": "Sevengill shark", "at": "appear"}), sg(1.2, 0.74, 0.65, to=[0.74, 0.72]), sg(1.15, 0.3, 0.55, to=[0.7, 0.32]),
         depth=0.4, heading="Seal Island", kicker="NEVER RECORDED THERE BEFORE"))
S(1, sea(seal(0.08, 0.3, 0.4, detail={"rest": True}), seal(0.2, 0.28, 0.36, detail={"rest": True}, flip=True), seal(0.32, 0.3, 0.4, detail={"rest": True}),
         seal(0.43, 0.3, 0.34, detail={"rest": True}, flip=True), seal(0.53, 0.3, 0.3, detail={"rest": True, "pup": True}),
         seal(0.72, 0.6, 0.42, to=[0.86, 0.56]), seal(0.62, 0.8, 0.4, to=[0.48, 0.76]), seal(0.9, 0.82, 0.36, to=[0.74, 0.86]),
         split={"y": 0.42, "land": "rocks", "landWidth": 0.62, "sky": "polar", "floes": False},
         heading="Cape fur seal sightings", bigText="ABOUT 6×", bigAt="six", bigColor="#e6edf2"))
S(1, tpl("SourceList", backdrop="ocean", tag="Knock-on effects", tagNote="False Bay",
         rows=[{"title": "More fur seals", "source": "the fish they eat became harder to find", "at": "fish"},
               {"title": "More sevengill sharks", "source": "the small sharks they hunt became harder to find", "at": "small"}]))
S(1, sea(port(0.1, 0.42, 1.5, to=[0.5, 0.42]), star(0.0, 0.68, 1.5, to=[0.4, 0.68]), depth=0.4, callout="Port and Starboard kept hunting", calloutAt="kept"))
S(1, photo("sevengill sharks washed up",
           beach(sg(0.1, 0.66, 0.42, view="beached"), sg(0.26, 0.76, 0.55, view="beached", flip=True), sg(0.42, 0.66, 0.42, view="beached"),
                 sg(0.56, 0.8, 0.6, view="beached"), sg(0.72, 0.68, 0.45, view="beached", flip=True), sg(0.88, 0.78, 0.52, view="beached"),
                 sg(0.34, 0.9, 0.5, view="beached", flip=True), sg(0.76, 0.92, 0.5, view="beached"), sky="overcast",
                 kicker="FEBRUARY 2023", heading="Near Gansbaai", callout="About twenty sharks after one visit", calloutAt="twenty", source=RECON)))
S(1, tpl("Anatomy", sprite={"creature": "sevengill", "view": "side"}, backdrop="abyss",
         callouts=[{"x": 0.44, "y": 0.62, "label": "Liver removed", "sub": "nearly all were sevengills", "at": "liver", "side": "left"}]))
S(1, sea(port(0.3, 0.42, 1.5, view="three_quarter", silhouette="#050b10", opacity=0.92), star(0.7, 0.66, 1.5, view="three_quarter", silhouette="#050b10", opacity=0.92),
         depth=0.65, check={"text": "The case against the two orcas", "at": "case", "ok": True}))
S(1, tpl("Statement", backdrop="abyss", kicker2="Several shark scientists", line1="The case is missing", line2="a second suspect"))

# ====================================================================================== 9. THE SECOND SUSPECT
WHOLE_COAST = [[15.5, -36.6], [33.5, -26.5]]
S(1, tpl("MapScene", bbox=WHOLE_COAST, highlight=["South Africa"], countryLabels=["South Africa"],
         cities=[{**CAPE_TOWN, "at": 0.4}, {**GANSBAAI, "at": 0.6}, {**MOSSEL, "at": 0.8}, {**ALGOA, "at": 1.0}],
         title="2023", subtitle="Great white records from the whole coast"),
  chapter="The Second Suspect", mood="mystery")
S(2, tpl("MapScene", bbox=WHOLE_COAST, highlight=["South Africa"],
         pulses=[{"lon": 18.9, "lat": -34.5, "label": "West: sightings fell", "color": "#e5372f", "at": "fallen"},
                 {"lon": 25.7, "lat": -33.85, "label": "East: sightings rose", "color": "#3fb6c9", "at": "risen"}],
         title="Steady overall", subtitle="Fewer in the west, more in the east"))
S(1, tpl("BarCompare", backdrop="ocean", heading="Great whites caught by shore anglers", kicker="ALGOA BAY",
         bars=[{"label": "2013", "value": 6, "display": "6", "at": "six"}, {"label": "2019", "value": 59, "display": "59", "at": "2019"}]))
S(1, tpl("MapScene", bbox=WHOLE_COAST, highlight=["South Africa"], cities=[{**GANSBAAI, "at": 0.3}, {**ALGOA, "at": 0.5}],
         arrows=[{"from": [19.6, -35.0], "to": [25.6, -34.3], "at": "moved", "dur": 1.8, "curve": 0.14, "label": "Moved east?"}],
         title="Away from the orcas"))
S(1, tpl("Statement", backdrop="ocean", kicker2="2024", line1="Another group of scientists", line2="pushed back"))
S(2, tpl("Counter", backdrop="ocean", **{"from": 2010}, to=2015, plain=True, label="False Bay", countAt=0.5, countDur=7,
         timeline={"start": 2010, "end": 2018, "tickEvery": 1,
                   "events": [{"year": 2012, "label": "Sightings start falling", "at": "falling"}, {"year": 2015, "label": "Port and Starboard first seen hunting there", "at": "three"}]}))
S(1, sea(gw(0.7, 0.6, 1.0, to=[0.6, 0.6]), depth=0.3, net={"x0": 0.06, "x1": 0.5, "top": 0.06, "bottom": 0.8, "at": 0.3},
         bigText="PEOPLE", bigAt="people", bigColor="#e6edf2"))
S(1, [tpl("MapScene", bbox=[[27.5, -32.2], [34.5, -26.3]], highlight=["South Africa"], cities=[{"name": "Durban", "lon": 31.02, "lat": -29.86, "at": 0.4}],
          countryLabels=[{"name": "KwaZulu-Natal", "lon": 30.6, "lat": -28.6}], title="KwaZulu-Natal", subtitle="Shark nets and baited hooks"),
      clip("shark nets KwaZulu-Natal",
           sea(gw(0.8, 0.56, 1.0, to=[0.66, 0.56]), depth=0.25, surface=True, net={"x0": 0.05, "x1": 0.56, "top": 0.05, "bottom": 0.82},
               heading="Shark nets", callout="Protecting swimming beaches", calloutAt="protect"))])
S(1, tpl("StatCards", backdrop="ocean", center=True, heading="Nets and baited hooks, 1978 to 2018", kicker="KWAZULU-NATAL",
         cards=[{"label": "Great whites caught", "value": "1,317", "at": "caught"}, {"label": "Died", "value": "1,108", "at": "died"}]))
S(2, tpl("BarCompare", backdrop="ocean", heading="Great whites killed", bars=[{"label": "Nets and hooks, every year", "value": 28, "display": "About 28 a year", "at": "about"},
                                                                              {"label": "Orcas, known kills since 2017", "value": 8, "display": "8 in total", "at": "eight"}]))
S(2, sea(bw(0.25, 0.62, 0.5, to=[0.4, 0.6]), bw(0.6, 0.76, 0.45, to=[0.74, 0.74]), gw(1.1, 0.5, 0.95, to=[0.7, 0.46], at="great"),
         depth=0.35, longline={"y": 0.16, "hooks": 9}, heading="Fishing boats",
         facts=[{"text": "Take the smaller sharks great whites eat", "at": "food"}, {"text": "Long lines of hooks catch great whites too", "at": "hooks", "red": True}]))
S(1, tpl("DotGrid", backdrop="ocean", count=1000, highlight=300, cols=50, value="A few hundred to 1,000", label="Great whites in South Africa (estimates)",
         fillAt="estimates", color="#3fb6c9"))
S(1, tpl("DotGrid", backdrop="ocean", count=1000, highlight=36, cols=50, value="A few dozen a year", label="Lost: enough to push the population into decline",
         fillAt="dozen"))
S(2, tpl("Statement", backdrop="ocean", kicker2="So who is right?", line1="Orcas and people", line2="both played a part"))
S(1, aerial(port(-0.2, 0.4, 1.2, view="top", to=[0.25, 0.42]), star(-0.3, 0.62, 1.2, view="top", to=[0.14, 0.6]),
            gw(0.6, 0.3, 0.7, view="top", to=[1.25, 0.12]), gw(0.7, 0.56, 0.8, view="top", to=[1.3, 0.56]), gw(0.58, 0.78, 0.7, view="top", to=[1.2, 0.96]),
            heading="Orcas", kicker="THE SUDDEN EXITS", callout="A busy bay went quiet within days", calloutAt="quiet", source=RECON))
S(1, sea(gw(0.78, 0.6, 0.9, to=[0.68, 0.6]), depth=0.3, surface=True, net={"x0": 0.05, "x1": 0.5, "top": 0.05, "bottom": 0.82},
         heading="Nets and fishing", kicker="YEARS OF LOSSES", callout="Fewer sharks left to come back", calloutAt="fewer"))

# ====================================================================================== 10. OTHER OCEANS
S(1, tpl("Globe", **{"from": [19.3, -34.6]}, to=[-111.5, 26.5], zoomFrom=1.0, zoomTo=2.0, marker={"label": "Gulf of California", "at": "other"}),
  chapter="Other Oceans", mood="wonder")
S(1, aerial(gw(0.56, 0.5, 0.5, view="top", to=[0.7, 0.5]), orca(0.24, 0.34, 1.1, view="top", to=[0.44, 0.4]), orca(0.2, 0.66, 1.1, view="top", to=[0.42, 0.6]),
            orca(0.88, 0.24, 1.0, view="top", to=[0.78, 0.36]), orca(0.9, 0.78, 0.95, view="top", to=[0.8, 0.64]), tone="open",
            heading="Moctezuma's pod", kicker="GULF OF CALIFORNIA", stats=[{"label": "Filmed", "value": "August 2020"}, {"label": "Again", "value": "August 2022"}],
            statsAt="August", source=RECON))
S(1, sea(orca(0.36, 0.62, 1.4, to=[0.46, 0.5], rotate=-14), gw(0.56, 0.3, 0.7, view="upside", idle=False, to=[0.58, 0.2]),
         depth=0.15, surface=True, callout="Pushed to the surface and rolled onto its back", calloutAt="roll", source=RECON))
S(1, sea(gw(0.5, 0.46, 1.6, view="upside", idle=False), depth=0.2, surface=True, zoom=[1.0, 1.08],
         title="Tonic immobility", titleAt="tonic", callout="Held upside down, a shark goes limp", calloutAt="limp"))
S(1, sea(gw(0.56, 0.3, 0.8, view="upside", idle=False), orca(0.3, 0.58, 1.4, to=[0.4, 0.52], rotate=-12), orca(0.9, 0.66, 1.2, to=[0.78, 0.56], flip=True),
         depth=0.2, surface=True, callout="While it lies still, the orcas take the liver", calloutAt="liver", source=RECON))
S(1, sea(orca(0.28, 0.5, 1.5), gw(0.76, 0.56, 0.5, flip=True, keepFacing=True, label={"text": "Young great white", "at": "young"}), depth=0.35,
         callout="Every shark in those hunts was young", calloutAt="young"))
S(2, tpl("Statement", backdrop="ocean", kicker2="Salvador Jorgensen, biologist", line1="Young sharks may simply have", line2="no experience of orcas yet",
         footnote="He led the Farallon study"))
S(1, [tpl("Globe", **{"from": [-111.5, 26.5]}, to=[141.6, -38.35], zoomFrom=1.2, zoomTo=2.2, marker={"label": "Portland, Victoria", "note": "Australia", "at": 0.6}),
      beach(gw(0.5, 0.74, 1.6, view="beached"), sky="day", kicker="OCTOBER 2023", heading="Near Portland, Victoria",
            scaleBar={"x1": 0.22, "x2": 0.78, "y": 0.9, "label": "4.7 metres", "at": 0.5})])
S(2, beach(gw(0.5, 0.72, 1.9, view="beached"), sky="day", zoom=[1.05, 1.2], heading="Its liver was gone",
           callout="Orca DNA in the biggest bite wound", calloutAt="DNA"))
S(1, tpl("DateStamp", date="2026", place="South Africa", at=0.2))

# ====================================================================================== 11. THE RETURN
YOUNG = sea(gw(-0.1, 0.56, 0.75, to=[0.5, 0.5]), A("fishSchool", 0.8, 0.3, 0.5, to=[0.7, 0.26]), depth=0.2, surface=True, rays=True,
            kicker="23 SEPTEMBER 2026", heading="Just north of Seal Island", callout="A young great white, filmed from a tour boat", calloutAt="filmed", source=RECON)
S(1, clip("great white shark False Bay September 2026", YOUNG), chapter="The Return", mood="calm")
S(1, sea(gw(0.3, 0.5, 1.2, view="three_quarter", to=[0.5, 0.5]), depth=0.2, surface=True, rays=True,
         hud={"label": "The first seen there in", "value": "≈ 8 years"}))
S(1, sea(gw(0.1, 0.8, 0.7, to=[0.4, 0.5]), gw(0.9, 0.86, 0.8, to=[0.64, 0.58], at="two"), depth=0.2, surface=True, rays=True,
         kicker="3 NOVEMBER 2026", heading="Off Gansbaai", callout="Two great whites at a cage-diving boat", calloutAt="two"))
S(1, sea(gw(0.36, 0.48, 0.8, to=[0.46, 0.46]), gw(0.7, 0.6, 0.9, to=[0.6, 0.58]), depth=0.2, surface=True, rays=True,
         hud={"label": "The company's first in", "value": "Over a year"}))
S(2, tpl("Statement", backdrop="ocean", kicker2="The people who saw them", line1="A few sharks", line2="are a hopeful sign"))
S(1, sea(gw(0.6, 0.5, 0.6, to=[0.9, 0.46]), depth=0.3, callout="Too early to call it a return", calloutAt="early"))
S(1, sea(port(0.24, 0.42, 1.5, view="three_quarter", to=[0.32, 0.42], label={"text": "Port", "at": "Port"}),
         star(0.66, 0.68, 1.5, view="three_quarter", to=[0.74, 0.68], label={"text": "Starboard", "at": "Starboard"}), depth=0.35,
         heading="Still on this coast"))
S(1, aerial(port(0.4, 0.4, 1.1, view="top", to=[0.1, 0.2]), star(0.6, 0.6, 1.1, view="top", to=[0.92, 0.82]),
            kicker="EARLY 2026", heading="Around the Cape", callout="Sometimes swimming apart", calloutAt="apart"))
S(1, sea(port(0.3, 0.42, 1.5, to=[0.36, 0.42]), star(0.66, 0.66, 1.5, to=[0.72, 0.66]), gw(1.2, 0.84, 0.6, to=[0.9, 0.86], opacity=0.8),
         depth=0.45, title="Did two orcas empty a great white shark coast?", titleAt=0.3))
S(1, tpl("MapScene", bbox=SOUTH_COAST, countryLabels=[{"name": "South Africa", "lon": 21.0, "lat": -33.35}],
         pulses=[{"lon": 19.35, "lat": -34.58, "label": "Gansbaai: yes", "at": "Gansbaai"}, {"lon": 22.13, "lat": -34.18, "label": "Mossel Bay: yes", "at": "Mossel"}],
         title="They did", subtitle="More than once, on camera"))
S(2, sea(gw(0.76, 0.6, 0.9, to=[0.66, 0.6]), depth=0.3, surface=True, net={"x0": 0.05, "x1": 0.5, "top": 0.05, "bottom": 0.82},
         longline={"y": 0.12, "hooks": 8, "at": "lines"}, heading="Across the wider coast", callout="Nets and lines came long before the orcas", calloutAt="long"))
S(3, sea(gw(0.3, 0.56, 0.55, to=[0.44, 0.54], label={"text": "Born knowing, or learned?", "at": "born"}),
         orca(0.95, 0.4, 1.6, silhouette="#050b10", opacity=0.5, blur=4, to=[0.86, 0.4]), depth=0.45, zoom=[1.0, 1.1],
         title="One question is still open", titleAt=0.3))
S(3, sea(port(0.1, 0.4, 1.3, to=[0.42, 0.4]), star(0.0, 0.64, 1.3, to=[0.32, 0.64]), gw(0.9, 0.8, 0.7, to=[0.66, 0.8]), depth=0.35, rays=True,
         title="What do you think?", titleAt=0.2, callout="Tell us in the comments · Subscribe for more", calloutAt="comments"))

assert _pos == len(SENT), f"{len(SENT) - _pos} sentence(s) of the script have no shot yet"


# ====================================================================================== real b-roll
# The script's own cues ask for footage of the actual events, which no free library holds. So that the video still
# carries real pictures, these lines get real photos or clips of the animal or the place the sentence is about
# (never of a different event). Every library is searched (iNaturalist, Unsplash, Pexels, Pixabay, Openverse,
# Wikimedia Commons, NASA); only licences that allow commercial use pass; each find is checked against `shows`.
# A line whose search finds nothing keeps its 3D shot (the list of finds is pruned after the collection run).
import copy  # noqa: E402


def real(words, shows, fallback, first="video", **look):
    """look: how the photo is framed (focus: [x, y] = the part to keep in view, zoom: [from, to], parallax: False)."""
    ph = {"remotion": "PhotoStory", "props": {"layout": "full", "photos": [{"photo": "stock:" + words, "parallax": True, "verify": shows, **look}]},
          "fallback_visual": fallback}
    return ph if first == "photo" else {"stock": words, "verify": shows, "fallback_visual": ph}


def add_real(starts, words, shows, first="video", place="before", **look):
    sc = next(s for s in scenes if s["text"].startswith(starts))
    vs = sc.pop("visuals", None) or [sc.pop("visual")]
    r = real(words, shows, copy.deepcopy(vs[0] if place == "before" else vs[-1]), first, **look)
    sc["visuals"] = [r] + vs if place == "before" else vs + [r]


def widen(starts, more_words, photo_words=None, photo_shows=None):
    """One of the script's own cues: more search words after the script's, and a photo when no clip is found."""
    sc = next(s for s in scenes if s["text"].startswith(starts))
    for v in sc.get("visuals") or [sc["visual"]]:
        if "stock" in v:
            v["stock"] += "|" + more_words
            if photo_words:
                v["fallback_visual"] = real(photo_words, photo_shows or v["verify"], v["fallback_visual"], first="photo")
        elif v.get("remotion") == "PhotoStory":
            v["props"]["photos"][0]["photo"] += "|" + more_words


# Looked at on the review sheet of collection run #9 (27 November 2026). Kept: the eight below. Turned down and
# removed: a cliff coast with no seals (for the seal colony), a snorkeller (for cage diving), Cape Town harbour (for
# Mossel Bay), a drone photo of a swimming shark (for the breach), a swim-zone buoy line (for the shark nets), a Shark Spotters flag that is mostly a clothing brand's logo; nothing
# was found for Gansbaai town or for a great white swimming.
add_real("Sevengills are smaller sharks", "broadnose sevengill shark|sevengill shark|Notorynchus cepedianus",
         "a sevengill shark swimming underwater", first="photo")
add_real("Orcas learn from one another", "orca pod|killer whales swimming|orcas swimming", "a pod of orcas swimming together")
add_real("In years when orcas visited", "northern elephant seal|elephant seals beach California|elephant seal",
         "elephant seals lying on a beach", first="photo", parallax=False, focus=[0.6, 0.45], zoom=[1.0, 1.05])
add_real("At Gansbaai, a smaller shark called the bronze whaler", "bronze whaler shark|copper shark|Carcharhinus brachyurus",
         "a bronze whaler shark swimming underwater", first="photo", place="after")
add_real("In False Bay the change went further.", "Seal Island False Bay|False Bay Cape Town|False Bay aerial",
         "False Bay near Cape Town: the sea with its coast or an island", first="photo", place="after")
add_real("Reported sightings of Cape fur seals", "Cape fur seals swimming|Cape fur seal|fur seals swimming underwater",
         "Cape fur seals in the water or on rocks")
add_real("Fishing boats that target smaller sharks", "longline fishing boat|commercial fishing boat at sea|fishing trawler",
         "a commercial fishing boat at sea")
add_real("Orcas in other oceans have learned the same hunt.", "killer whales ocean|orca pod aerial|orcas",
         "orcas swimming in the open sea", place="after")
# Only these reviewed items may be used: a render can never bring in a picture or clip that was not looked at.
APPROVED = [
    "inaturalist-599687346",                              # sevengill shark underwater · Luca Davenport-Thomas · CC BY 4.0
    "inaturalist-245792457",                              # northern elephant seal · Nicole · CC BY 4.0
    "unsplash-iyVSCp0ZUj0",                               # wild orca pod at the surface · Mike Doherty · Unsplash
    "inaturalist-592508768",                              # bronze whaler from a drone · Bryce Watts-Parker · CC BY 4.0
    "pixabay-p7015038",                                   # fishing harbour in False Bay · jeanvdmeulen · Pixabay
    "pixabay-v261267",                                    # Cape fur seals in the surf · MountainDweller · Pixabay
    "pixabay-v6412",                                      # a fishing boat · Life-Of-Vids · Pixabay
    "unsplash-qM9tSt_5orU",                               # two wild orcas · Vidar Nordli-Mathisen · Unsplash
]


# ------------------------------------------------------------------------------------------ checks + write
def _cue_words(node, text, where):
    if isinstance(node, dict):
        for k, v in node.items():
            if (k == "at" or k.endswith("At")) and k != "lookAt" and isinstance(v, str):
                phrase = re.sub(r"(#\d+)?([+-]\d+(\.\d+)?)?$", "", v)
                norm = lambda w: re.sub(r"[^\w]", "", w.lower())                 # noqa: E731
                toks, want = [norm(w) for w in text.split()], [norm(w) for w in phrase.split()]
                ok = any(all(toks[i + j] == want[j] or (j == len(want) - 1 and toks[i + j].startswith(want[j])) for j in range(len(want)))
                         for i in range(len(toks) - len(want) + 1))
                if not ok:
                    raise SystemExit(f"{where}: cue word {v!r} is not in the line: {text}")
            else:
                _cue_words(v, text, where)
    elif isinstance(node, list):
        for v in node:
            _cue_words(v, text, where)


for i, sc in enumerate(scenes):
    _cue_words({k: v for k, v in sc.items() if k != "text"}, sc["text"], f"scene {i + 1}")

doc = {
    "preset": "ocean",
    "title": script.title,
    "description": ("In May 2017 a great white shark almost five metres long washed up on a South African beach with its liver "
                    "missing. This is the story of Port and Starboard, the two orcas that learned to hunt great whites, the bay "
                    "they emptied, and the argument among scientists over how much of the blame is theirs.\n\n"
                    "The animals and events in this video are shown as 3D reconstructions, except where real photos or footage are credited below."),
    "tags": ["orca", "great white shark", "Port and Starboard", "Gansbaai", "False Bay", "Mossel Bay", "South Africa",
             "killer whale", "shark liver", "ocean documentary", "wildlife documentary", "animals"],
    "sources": script.sources,
    "thumbnail": {"text": "TWO ORCAS EMPTIED THIS COAST"},
    "youtube": {"privacy": "private", "category_id": 15, "synthetic_media": True},
    # max_pause: no gap inside the voice longer than this. padding: the gap after each scene (about 0.2 s between
    # sentences with the voice trimmed tight). Both can be changed without recording anything again.
    # tempo: 0.9 = the narrator reads 10 % slower (calmer), pitch unchanged.
    "settings": {"stock_approved": APPROVED, "padding": 0.12, "voice": {"max_pause": 0.12, "tempo": 0.9}},
    "scenes": scenes,
}
head = ('# The Two Orcas That Emptied a Great White Shark Coast — first video for the channel.\n'
        '# Written by direct.py from script.txt (the narration is the script, sentence for sentence). Change the shots in\n'
        '# direct.py and run it again; this file is what gets rendered.\n')
(HERE / "script.yaml").write_text(head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=130), encoding="utf-8")
print(f"{len(scenes)} scenes, {sum(len(s['text'].split()) for s in scenes)} words → {HERE / 'script.yaml'}")
