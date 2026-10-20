"""Fabrique les vidéos (diapositives animées + voix + sous-titres) des épisodes du podcast.

Prérequis : avoir lancé `python podcast/generate.py <ep>` (audio + chronologie dans .cache).

Directives dans les scripts (ignorées à l'audio) :
    @slide <type> <titre>      début d'une diapositive ; lignes suivantes = contenu ; fin par @end
        types : title (lignes : sur-titre, sous-titre), bullets, flow, cards ("Titre :: texte"),
                table ("a | b | c", 1re ligne = en-têtes), quiz (question ; "> réponse")
        flow : "Étape :: détail", suffixe " *" = étape grisée, préfixe "!" = étape mise en avant,
               ligne "> texte" = légende affichée quand tout est révélé
        **texte** = surligné
    @+  /  @+3  /  @all         révèle l'élément suivant / 3 éléments / tout (puces, étapes, cartes, lignes)
    @answer                     affiche la réponse d'un quiz

Schémas (@slide diagram <titre>) — positions en % de la zone de dessin, champs séparés par « | » :
    group ID x y w h | Libellé | couleur          conteneur (Organization, OU, VPC…)
    node  ID x y w h | Libellé | sous-titre | icône | couleur
    arrow ID DE VERS | légende | dashed           flèche tracée automatiquement entre deux boîtes
    couleurs : org, ou, account, service, prev, detect, proactive, user, data (ou une couleur CSS)
  Directives : @show ID… (ou @show all) · @hide ID… · @focus ID… (le reste s'estompe) · @unfocus
               @flow ARROW… : un point lumineux parcourt la ou les flèches au début de la réplique suivante
Pendant un [pause N] sur une diapositive quiz, un compte à rebours s'affiche.

Usage :
    python podcast/video/make_video.py 01 02
"""
import json
import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
PODCAST = HERE.parent
CACHE = PODCAST / ".cache"
OUT = HERE / "out"
FPS = 25
FADE = 0.25
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def run(args):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True)


FLOW_S, FLOW_FRAMES = 1.6, 16     # animation d'un flux le long d'une flèche


def diagram_ids(spec):
    """Identifiants des éléments d'un schéma (2e mot de chaque ligne : group/node/arrow ID …)."""
    return [line.split()[1] for line in spec["body"] if len(line.split()) > 1]


def build_states(timeline, tag, ep):
    """Transforme la chronologie en une suite d'états d'écran (start, dur, contenu)."""
    total = sum(e["dur"] for e in timeline if e["type"] in ("say", "pause"))
    slide, shown, answer = None, 0, False
    vis, focus, flows = [], [], []        # schémas : éléments visibles, mis en avant, flux à animer
    states = []

    def emit(start, dur, **kw):
        st = {"tag": tag, "ep": ep, "slide": slide, "shown": shown, "answer": answer,
              "vis": list(vis), "focus": list(focus), "progress": start / total, **kw}
        states.append({"start": start, "dur": dur, "state": st})

    for e in timeline:
        if e["type"] == "slide":
            slide, shown, answer, vis, focus, flows = e["spec"], 0, False, [], [], []
        elif e["type"] == "directive":
            v = e["value"]
            cmd, _, rest = v.partition(" ")
            ids = rest.split()
            if v == "answer":
                answer = True
            elif v == "all":
                shown = 999
            elif v.startswith("+"):
                shown += int(v[1:] or 1)
            elif cmd == "show":
                vis += [i for i in (diagram_ids(slide) if ids == ["all"] else ids) if i not in vis]
            elif cmd == "hide":
                vis = [i for i in vis if i not in ids]
            elif cmd == "focus":
                focus = ids
            elif cmd == "unfocus":
                focus = []
            elif cmd == "flow":
                flows += ids
            else:
                raise ValueError(f"directive inconnue : @{v}")
        elif e["type"] == "say":
            if flows:
                # un point lumineux parcourt les flèches au début de la réplique, sans fondu entre les images
                n, step = FLOW_FRAMES, min(FLOW_S, e["dur"] * 0.8) / FLOW_FRAMES
                for k in range(n):
                    emit(e["start"] + k * step, step, speaker=e["speaker"], text=e["text"],
                         flow={"arrows": flows, "t": (k + 1) / n}, nofade=k > 0)
                emit(e["start"] + n * step, e["dur"] - n * step, speaker=e["speaker"], text=e["text"], nofade=True)
                flows = []
                continue
            emit(e["start"], e["dur"], speaker=e["speaker"], text=e["text"])
        elif e["type"] == "pause":
            if slide and slide["type"] == "quiz" and not answer:
                secs = max(1, math.ceil(e["dur"]))
                step = e["dur"] / secs
                for k in range(secs):
                    emit(e["start"] + k * step, step, timer={"left": secs - k, "total": secs})
            else:
                emit(e["start"], e["dur"])
    return states


def render_pngs(states, folder):
    folder.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto((HERE / "template.html").as_uri())
        page.wait_for_load_state("load")
        for n, s in enumerate(states):
            page.evaluate("s => window.render(s)", s["state"])
            s["png"] = folder / f"{n:04d}.png"
            page.screenshot(path=str(s["png"]))
        browser.close()


def make_clip(n, s, prev, folder):
    frames = round((s["start"] + s["dur"]) * FPS) - round(s["start"] * FPS)
    clip = folder / f"{n:04d}.mp4"
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-pix_fmt", "yuv420p",
           "-r", str(FPS), "-frames:v", str(frames), str(clip)]
    if frames <= 0:
        return None
    if prev is not None and not s["state"].get("nofade") and frames > FADE * FPS + 2:
        d = frames / FPS + 1
        run(["-loop", "1", "-framerate", str(FPS), "-t", f"{d}", "-i", str(prev),
             "-loop", "1", "-framerate", str(FPS), "-t", f"{d}", "-i", str(s["png"]),
             "-filter_complex", f"[0][1]xfade=transition=fade:duration={FADE}:offset=0", *enc])
    else:
        run(["-loop", "1", "-framerate", str(FPS), "-i", str(s["png"]), *enc])
    return clip


def build(stem):
    timeline = json.loads((CACHE / f"{stem}.timeline.json").read_text(encoding="utf-8"))
    title = (PODCAST / "scripts" / f"{stem}.txt").read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
    ep, _, topic = title.partition(" — ")
    states = build_states(timeline, f"DOP-C02 · {topic}", ep)
    work = CACHE / "video" / stem
    render_pngs(states, work)
    prevs = [None] + [s["png"] for s in states[:-1]]
    with ThreadPoolExecutor(4) as pool:
        clips = list(pool.map(lambda a: make_clip(*a, work), zip(range(len(states)), states, prevs)))
    listing = work / "clips.list"
    listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips if c), encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    out = OUT / f"{stem}.mp4"
    run(["-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(PODCAST / "audio" / f"{stem}.mp3"),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart",
         "-metadata", f"title={title}", str(out)])
    print(f"OK  {out.name}  ({len(states)} écrans)", flush=True)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        for script in sorted((PODCAST / "scripts").glob(f"{arg}*.txt")):
            build(script.stem)
