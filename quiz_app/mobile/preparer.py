#!/usr/bin/env python3
"""Prépare le paquet à importer dans l'app Android : questions + extraits pré-calculés (+ ta progression).

    python quiz_app/mobile/preparer.py "<fichier, dossier ou jokers>" [--sans-progression]

Le téléphone n'a ni Python ni la recherche par le sens : on calcule ici, une fois pour toutes, le passage
de fiche et l'extrait vidéo de chaque question (comme /api/locate), et on range tout dans un seul fichier.
Ta progression et ton historique du PC (fichiers .progress.json et .sessions.json) sont joints, sauf option.
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.stdout.reconfigure(errors="replace")      # console Windows (cp1252) : pas de plantage sur un symbole
sys.path.insert(0, str(HERE.parent))
import app  # noqa: E402

OUT_DIR = HERE / "paquet"


def main():
    ap = argparse.ArgumentParser(description="Paquet de questions pour l'app Android DOP-C02")
    ap.add_argument("questions", nargs="+", help="fichier(s) JSON de questions, ou dossier (comme app.py)")
    ap.add_argument("--sans-progression", action="store_true", help="ne pas joindre la progression et l'historique du PC")
    ap.add_argument("--sortie", help=f"fichier de sortie (défaut : {OUT_DIR.name}/dop-c02-paquet.json)")
    args = ap.parse_args()

    bank_path, payload = app.load_bank(args.questions)
    payload["erreurs_note"] = False           # Obsidian n'est pas modifiable depuis le téléphone
    qs = payload["questions"]
    print(f"{len(qs)} questions chargées depuis {payload['source']}")

    locate = {}
    if app.LOCATOR:
        print("Index des extraits par le sens… (≈ 30 s la première fois)")
        app.LOCATOR._refresh()
        for _ in range(240):
            if app.SEMANTIC.ready:
                break
            time.sleep(1)
        if not app.SEMANTIC.ready:
            print("  recherche par le sens indisponible : extraits calculés avec les mots-clés seuls")
        t0 = time.time()
        for n, q in enumerate(qs, 1):
            locate[q["id"]] = app.LOCATOR.find(q)
            if n % 50 == 0 or n == len(qs):
                print(f"  extraits : {n}/{len(qs)}", flush=True)
        found = sum(1 for r in locate.values() if r.get("clips"))
        print(f"  {found}/{len(qs)} questions avec un extrait vidéo ({time.time() - t0:.0f} s)")
    else:
        print("Coffre Obsidian introuvable : pas d'extraits pour les questions")

    pack = {"format": "dop-c02-mobile", "version": 1, "cree_le": int(time.time() * 1000), "bank": payload, "locate": locate}
    if not args.sans_progression:
        prog = bank_path.with_name(bank_path.stem + ".progress.json")
        sess = bank_path.with_name(bank_path.stem + ".sessions.json")
        if prog.exists():
            pack["progress"] = json.loads(prog.read_text(encoding="utf-8"))
        if sess.exists():
            pack["sessions"] = json.loads(sess.read_text(encoding="utf-8")).get("sessions", [])
        print(f"Progression jointe : {'oui' if 'progress' in pack else 'aucune'} · "
              f"historique : {len(pack.get('sessions', []))} session(s)")

    out = Path(args.sortie) if args.sortie else OUT_DIR / "dop-c02-paquet.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\nPaquet prêt : {out}  ({out.stat().st_size / 1e6:.1f} Mo)")
    print("Copie-le sur le téléphone (câble USB → dossier Download, ou Google Drive),")
    print("puis dans l'app : 📱 → Importer un paquet.")


if __name__ == "__main__":
    main()
