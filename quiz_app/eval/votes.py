"""Mesure la justesse réelle des extraits vidéo sur TA banque, à partir de tes votes 👍 / 👎 dans l'app.

Lit uniquement les votes enregistrés dans le fichier de progression (identifiants et scores numériques,
jamais le texte des questions) et affiche :
  - le taux d'extraits jugés pertinents, au total et par rang (1er extrait, 2e extrait) ;
  - le taux selon le score de confiance, pour choisir le bon seuil d'affichage ;
  - l'effet du domaine (extrait du même domaine ou non).

Usage :
    python quiz_app/eval/votes.py "<dossier ou fichier de la banque>"
    (le fichier lu est questions.progress.json pour un dossier, <fichier>.progress.json pour un fichier)

Tu peux coller la sortie telle quelle : elle ne contient aucune question.
"""
import json
import sys
from pathlib import Path


def progress_file(arg):
    p = Path(arg).expanduser()
    if p.is_dir():
        return p / "questions.progress.json"
    if p.name.endswith(".progress.json"):
        return p
    return p.with_name(p.stem + ".progress.json")


def rate(votes):
    good = sum(1 for v in votes if v["vote"] > 0)
    return f"{good}/{len(votes)} pertinents ({100 * good // len(votes)} %)" if votes else "—"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = progress_file(sys.argv[1])
    if not path.exists():
        sys.exit(f"Fichier introuvable : {path}")
    votes = [v for v in json.loads(path.read_text(encoding="utf-8")).get("clipVotes", []) if v.get("conf") is not None]
    print(f"{len(votes)} vote(s) dans {path.name}")
    if len(votes) < 10:
        print("Pas encore assez de votes : vise au moins 30 pour une mesure utile.")
        if not votes:
            return
    print(f"\nTous les extraits      : {rate(votes)}")
    for r, nom in ((0, "1er extrait"), (1, "2e extrait")):
        print(f"{nom:22} : {rate([v for v in votes if v.get('rang') == r])}")
    print(f"Même domaine           : {rate([v for v in votes if v.get('domaine_ok')])}")
    print(f"Autre domaine          : {rate([v for v in votes if not v.get('domaine_ok')])}")
    print("\nSelon le score de confiance (conf) :")
    for lo, hi in ((0, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 2)):
        sel = [v for v in votes if lo <= v["conf"] < hi]
        if sel:
            print(f"  conf {lo:.1f}–{min(hi, 1):.1f} : {rate(sel)}")
    # seuil conseillé : le plus bas qui garde au moins 80 % d'extraits pertinents
    print("\nSi on n'affichait que les extraits au-dessus d'un seuil :")
    best = None
    for t in (0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9):
        sel = [v for v in votes if v["conf"] >= t]
        if not sel:
            continue
        ok = sum(1 for v in sel if v["vote"] > 0) / len(sel)
        print(f"  seuil {t:.2f} : {len(sel)}/{len(votes)} gardés · {100 * ok:.0f} % pertinents")
        if best is None and ok >= 0.8:
            best = t
    print(f"\nSeuil conseillé (≥ 80 % pertinents) : {best if best is not None else 'aucun — il faut plus de votes ou une autre approche'}")


if __name__ == "__main__":
    main()
