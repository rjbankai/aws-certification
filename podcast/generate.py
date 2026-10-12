"""Génère les épisodes MP3 du podcast DOP-C02 à partir des scripts texte.

Format d'un script (podcast/scripts/*.txt) :
    # Titre de l'épisode          (1re ligne, ignorée à l'audio)
    L: réplique de Léa
    R: réplique de Rémy
    E: texte lu en anglais (questions d'examen)
    [pause 4]                      (silence de 4 secondes, ex. avant une réponse de quiz)
    Lignes vides et lignes commençant par // ignorées.

Usage :
    python podcast/generate.py            # tous les épisodes
    python podcast/generate.py 03 05      # seulement les épisodes dont le nom commence par 03 ou 05
"""
import asyncio
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

VOICES = {
    "L": "fr-FR-VivienneMultilingualNeural",
    "R": "fr-FR-RemyMultilingualNeural",
    "E": "en-US-AndrewNeural",      # lecteur des questions d'examen en anglais
}
RATE = "+0%"            # vitesse de lecture ; on peut aussi accélérer dans le lecteur
GAP_SECONDS = 0.35      # silence entre deux répliques

ROOT = Path(__file__).parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "audio"
CACHE = ROOT / ".cache"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def parse(path):
    items = []
    for raw in path.read_text(encoding="utf-8").splitlines()[1:]:
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        m = re.fullmatch(r"\[pause\s+([\d.]+)\]", line)
        if m:
            items.append(("pause", float(m.group(1))))
            continue
        m = re.fullmatch(r"([LRE]):\s*(.+)", line)
        if not m:
            raise ValueError(f"{path.name}: ligne non reconnue : {raw!r}")
        items.append(("say", m.group(1), m.group(2)))
    return items


async def tts(voice, text):
    key = hashlib.sha1(f"{voice}|{RATE}|{text}".encode()).hexdigest()[:16]
    target = CACHE / f"{key}.mp3"
    if not target.exists() or target.stat().st_size == 0:
        for attempt in range(4):
            try:
                await edge_tts.Communicate(text, voice, rate=RATE).save(str(target))
                break
            except Exception:
                if attempt == 3:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
    return target


def silence(seconds):
    target = CACHE / f"silence_{seconds:.2f}.mp3"
    if not target.exists():
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
             "anullsrc=r=24000:cl=mono", "-t", f"{seconds}", "-b:a", "48k", str(target)],
            check=True,
        )
    return target


async def build(path):
    items = parse(path)
    sem = asyncio.Semaphore(6)

    async def seg(item):
        if item[0] == "pause":
            return [silence(item[1])]
        async with sem:
            return [await tts(VOICES[item[1]], item[2]), silence(GAP_SECONDS)]

    parts = [p for group in await asyncio.gather(*(seg(i) for i in items)) for p in group]
    listing = CACHE / f"{path.stem}.list"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    title = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
    out = OUT / f"{path.stem}.mp3"
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-ac", "1", "-ar", "24000", "-b:a", "64k",
         "-metadata", f"title={title}", "-metadata", "album=DOP-C02 — Révisions audio",
         "-metadata", "artist=Léa & Rémy", str(out)],
        check=True,
    )
    print(f"OK  {out.name}")


async def main():
    OUT.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    wanted = sys.argv[1:]
    for path in sorted(SCRIPTS.glob("*.txt")):
        if wanted and not any(path.name.startswith(w) for w in wanted):
            continue
        await build(path)


if __name__ == "__main__":
    asyncio.run(main())
