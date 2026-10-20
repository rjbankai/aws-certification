"""Génère les épisodes MP3 du podcast DOP-C02 à partir des scripts texte.

Format d'un script (podcast/scripts/*.txt) :
    # Titre de l'épisode          (1re ligne, ignorée à l'audio)
    L: réplique de Léa
    R: réplique de Rémy
    E: texte lu en anglais (questions d'examen)
    [pause 4]                      (silence de 4 secondes, ex. avant une réponse de quiz)
    Lignes vides et lignes commençant par // ignorées.

Dans une réplique L/R, un terme entre accolades est prononcé en anglais natif,
avec la même voix : « le hook {After Allow Test Traffic} sur {ECS} ».

Les lignes qui commencent par @ pilotent les vidéos (diapositives) et sont
ignorées à l'audio ; voir make_video.py.

Usage :
    python podcast/generate.py            # tous les épisodes
    python podcast/generate.py 03 05      # seulement les épisodes dont le nom commence par 03 ou 05
"""
import asyncio
import hashlib
import json
import re
import subprocess
import sys
import wave
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
SAMPLE_RATE = 24000

ROOT = Path(__file__).parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "audio"
CACHE = ROOT / ".cache"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def clean(text):
    """Texte d'une réplique sans les accolades de prononciation (pour les sous-titres)."""
    return text.replace("{", "").replace("}", "")


def parse(path):
    """Renvoie la liste des éléments d'un script : say, pause, et directives vidéo (@...)."""
    items = []
    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line or line.startswith("//"):
            continue
        if line.startswith("@slide"):
            head = line[len("@slide"):].strip()
            kind, _, title = head.partition(" ")
            body = []
            while i < len(lines) and lines[i].strip() != "@end":
                if lines[i].strip():
                    body.append(lines[i].strip())
                i += 1
            i += 1  # saute @end
            items.append(("slide", {"type": kind, "title": title.strip(), "body": body}))
            continue
        if line.startswith("@"):
            items.append(("directive", line[1:].strip()))
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


def chunks(text):
    """Découpe une réplique en morceaux (langue, texte) : 'fr' hors accolades, 'en' dedans."""
    out = []
    for n, part in enumerate(re.split(r"\{([^}]*)\}", text)):
        part = part.strip()
        if not part:
            continue
        if not re.search(r"\w", part) and out:
            # ponctuation seule (« , ») : rattachée au morceau précédent, jamais synthétisée seule
            out[-1] = (out[-1][0], out[-1][1] + part)
            continue
        out.append(("en" if n % 2 else "fr", part))
    return out


def run(args):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True)


def duration(wav_path):
    with wave.open(str(wav_path)) as w:
        return w.getnframes() / w.getframerate()


async def tts_mp3(voice, text):
    key = hashlib.sha1(f"{voice}|{RATE}|{text}".encode()).hexdigest()[:16]
    target = CACHE / f"{key}.mp3"
    if not target.exists() or target.stat().st_size == 0:
        for attempt in range(5):
            try:
                await edge_tts.Communicate(text, voice, rate=RATE).save(str(target))
                break
            except Exception:
                if attempt == 4:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
    return target


# Amorces qui fixent la langue détectée par la voix multilingue ; elles sont coupées ensuite.
# Sans elles, un morceau court (« puis », « Pour ») est souvent lu dans la mauvaise langue.
PREFIX = {"fr": "Bon, alors je dis : ", "en": "Okay, the term is: "}
# Les morceaux français très courts (« sur », « avec des ») reçoivent aussi une suite, coupée
# elle aussi : prononcés au milieu d'une phrase, ils restent bien français.
SUFFIX_FR = ", voilà."
SHORT_WORDS = 3


async def tts_chunk(voice, lang, text):
    """Synthétise un morceau précédé d'une amorce ; renvoie (mp3, instant où commence le morceau)."""
    suffix = SUFFIX_FR if lang == "fr" and len(re.findall(r"[\w']+", text)) <= SHORT_WORDS else ""
    key = hashlib.sha1(f"{voice}|{RATE}|{lang}|{PREFIX[lang]}|{text}|{suffix}".encode()).hexdigest()[:16]
    mp3, meta = CACHE / f"chunk_{key}.mp3", CACHE / f"chunk_{key}.json"
    if not meta.exists():
        n_prefix = len(re.findall(r"[\w']+", PREFIX[lang]))
        for attempt in range(5):
            try:
                audio, bounds = bytearray(), []
                comm = edge_tts.Communicate(PREFIX[lang] + text + suffix, voice, rate=RATE, boundary="WordBoundary")
                async for ch in comm.stream():
                    if ch["type"] == "audio":
                        audio += ch["data"]
                    elif ch["type"] == "WordBoundary":
                        bounds.append((ch["offset"] / 1e7, ch["duration"] / 1e7))
                break
            except Exception:
                if attempt == 4:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
        # Le 1er mot du morceau est le mot n° n_prefix (0-indexé). On coupe au milieu du
        # silence qui suit le « : » de l'amorce, pour ne rogner ni l'amorce ni le morceau.
        idx = min(n_prefix, len(bounds) - 1)
        end_prefix = bounds[idx - 1][0] + bounds[idx - 1][1]
        start = (end_prefix + bounds[idx][0]) / 2
        end = None
        if suffix and len(bounds) >= idx + 2:
            last, first_suffix = bounds[-2], bounds[-1]   # dernier mot du morceau, « voilà »
            end = (last[0] + last[1] + first_suffix[0]) / 2
        mp3.write_bytes(bytes(audio))
        meta.write_text(json.dumps({"start": start, "end": end, "bounds": bounds}), encoding="utf-8")
    m = json.loads(meta.read_text(encoding="utf-8"))
    return mp3, m["start"], m.get("end")


def to_wav(mp3, trim, start=0.0, end=None):
    """Décode en WAV mono 24 kHz à partir de `start` ; si trim, retire les silences de début et de fin."""
    target = mp3.with_name(mp3.stem + ("_t" if trim else "") + ".wav")
    if not target.exists():
        # garde 40 ms de marge pour ne pas rogner les attaques et les fins de mots faibles
        flt = ["-af", "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse,"
                      "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse"] if trim else []
        cut = ["-t", f"{end - start:.3f}"] if end else []
        run(["-i", str(mp3), "-ss", f"{start:.3f}", *cut, *flt, "-ac", "1", "-ar", str(SAMPLE_RATE), str(target)])
    return target


def silence(seconds):
    target = CACHE / f"silence_{seconds:.3f}.wav"
    if not target.exists():
        run(["-f", "lavfi", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono", "-t", f"{seconds}", str(target)])
    return target


def concat_wav(parts, target):
    listing = target.with_suffix(".list")
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(target)])
    return target


def joint_gap(left, right):
    """Petit blanc entre deux morceaux d'une même phrase ; plus long après une ponctuation."""
    if re.search(r"[,;:.!?]$", left) or re.match(r"^[,;:.!?]", right):
        return 0.22
    return 0.05


async def line_wav(speaker, text, sem):
    parts = chunks(text) if speaker != "E" else [("en", text)]
    # « blue/green » serait lu « blue slash green »
    parts = [(lang, t.replace("/", " ") if lang == "en" else t) for lang, t in parts]
    if len(parts) == 1 and (speaker == "E" or parts[0][0] == "fr"):
        async with sem:
            return to_wav(await tts_mp3(VOICES[speaker], parts[0][1]), trim=False)
    key = hashlib.sha1(f"{VOICES[speaker]}|{RATE}|{text}|{PREFIX}|{SUFFIX_FR}|chunked".encode()).hexdigest()[:16]
    target = CACHE / f"line_{key}.wav"
    if target.exists():
        return target
    async with sem:
        synth = [await tts_chunk(VOICES[speaker], lang, t) for lang, t in parts]
    seq = []
    for n, (mp3, start, end) in enumerate(synth):
        if n:
            seq.append(silence(joint_gap(parts[n - 1][1], parts[n][1])))
        seq.append(to_wav(mp3, trim=True, start=start, end=end))
    return concat_wav(seq, target)


async def build(path):
    items = parse(path)
    sem = asyncio.Semaphore(6)
    spoken = [it for it in items if it[0] in ("say", "pause")]

    async def seg(item):
        if item[0] == "pause":
            return silence(item[1])
        return await line_wav(item[1], item[2], sem)

    wavs = dict(zip(map(id, spoken), await asyncio.gather(*(seg(i) for i in spoken))))

    # Chronologie (utilisée par make_video.py) et liste des morceaux audio
    timeline, parts, t = [], [], 0.0
    gap = silence(GAP_SECONDS)
    for it in items:
        if it[0] == "slide":
            timeline.append({"type": "slide", "spec": it[1]})
        elif it[0] == "directive":
            timeline.append({"type": "directive", "value": it[1]})
        elif it[0] == "pause":
            d = duration(wavs[id(it)])
            timeline.append({"type": "pause", "start": t, "dur": d})
            parts.append(wavs[id(it)])
            t += d
        else:
            d = duration(wavs[id(it)])
            timeline.append({"type": "say", "speaker": it[1], "text": clean(it[2]),
                             "start": t, "dur": d + GAP_SECONDS})
            parts += [wavs[id(it)], gap]
            t += d + GAP_SECONDS
    (CACHE / f"{path.stem}.timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=1), encoding="utf-8")

    full = concat_wav(parts, CACHE / f"{path.stem}.full.wav")
    title = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
    out = OUT / f"{path.stem}.mp3"
    run(["-i", str(full), "-ac", "1", "-ar", str(SAMPLE_RATE), "-b:a", "64k",
         "-metadata", f"title={title}", "-metadata", "album=DOP-C02 — Révisions audio",
         "-metadata", "artist=Léa & Rémy", str(out)])
    print(f"OK  {out.name}  ({t / 60:.1f} min)", flush=True)


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
