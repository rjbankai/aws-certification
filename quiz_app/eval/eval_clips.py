"""Mesure la qualité des extraits vidéo proposés après une question.

Pour chaque question de exemples/questions_originales.json, compare les extraits renvoyés par
app.LOCATOR.find() aux diapositives attendues (labels.json) :
  - premier extrait juste   : le premier extrait affiché tombe sur une bonne diapositive
  - au moins un juste       : un des extraits affichés est bon
  - faux affichés           : extraits affichés qui ne sont pas sur une bonne diapositive
  - rien affiché            : aucune proposition (préférable à une fausse)

Usage : python quiz_app/eval/eval_clips.py [-v]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import app  # noqa: E402

CACHE = app.VAULT / "podcast" / ".cache"


def slide_spans():
    """(épisode à 2 chiffres) → liste des (début, fin, indice) de chaque diapositive."""
    spans = {}
    for tl in sorted(CACHE.glob("[0-9][0-9]-*.timeline.json")):
        items, idx, cur = [], -1, None
        for e in json.loads(tl.read_text(encoding="utf-8")):
            if e["type"] == "slide":
                idx += 1
                cur = [None, None, idx]
                items.append(cur)
            elif e["type"] in ("say", "pause") and cur is not None:
                cur[0] = e["start"] if cur[0] is None else cur[0]
                cur[1] = e["start"] + e["dur"]
        spans[tl.name[:2]] = [tuple(x) for x in items if x[0] is not None]
    return spans


def slide_of(spans, ep, t):
    for a, b, i in spans.get(ep[:2], []):
        if a - 0.01 <= t < b - 0.01:
            return f"{ep[:2]}:{i}"
    return None


def main(verbose=False):
    labels = {k: set(v) for k, v in json.loads((HERE / "labels.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
    bank = json.loads((HERE.parent / "exemples" / "questions_originales.json").read_text(encoding="utf-8"))
    if "--sans-explication" in sys.argv:
        # test plus dur, plus proche d'une banque externe : énoncé anglais + bonne réponse, sans mon explication
        for q in bank["questions"]:
            q["explication"] = ""
    spans = slide_spans()
    # attendre l'index par le sens (construit en arrière-plan), sinon on mesurerait les mots-clés seuls
    import time
    app.LOCATOR._refresh()
    for _ in range(180):
        if app.SEMANTIC.ready:
            break
        time.sleep(1)
    print("recherche par le sens :", "active" if app.SEMANTIC.ready else "indisponible (mots-clés seuls)")
    first_ok = any_ok = wrong = none = shown = 0
    for q in bank["questions"]:
        clips = app.LOCATOR.find(q).get("clips", [])
        got = [slide_of(spans, c["episode"], c.get("at", c["start"])) for c in clips]
        ok = [g in labels[q["id"]] for g in got]
        shown += len(got)
        if not got:
            none += 1
        else:
            first_ok += ok[0]
            any_ok += any(ok)
            wrong += ok.count(False)
        if verbose:
            mark = "—" if not got else ("✓" if ok[0] else ("~" if any(ok) else "✗"))
            print(f"{mark} {q['id']} attendu {sorted(labels[q['id']])} · proposé {got}")
    n = len(bank["questions"])
    print(f"premier extrait juste : {first_ok}/{n} ({100 * first_ok // n} %) · au moins un juste : {any_ok}/{n} · "
          f"faux affichés : {wrong}/{shown} · rien affiché : {none}")
    return first_ok, any_ok, wrong, none


if __name__ == "__main__":
    main("-v" in sys.argv)
