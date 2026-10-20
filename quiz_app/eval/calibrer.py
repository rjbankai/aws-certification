"""Calibre les seuils absolus (similarité de sens « cos », marge) sur le jeu de test labellisé.

Affiche, pour les extraits justes et faux, la répartition de cos et de la marge, puis l'effet de
différents seuils CLIP_MIN_COS. Option --sans-explication pour le test le plus dur.

Usage : python quiz_app/eval/calibrer.py [--sans-explication]
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import app  # noqa: E402
from eval_clips import slide_spans, slide_of  # noqa: E402

labels = {k: set(v) for k, v in json.loads((HERE / "labels.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
bank = json.loads((HERE.parent / "exemples" / "questions_originales.json").read_text(encoding="utf-8"))["questions"]
if "--sans-explication" in sys.argv:
    for q in bank:
        q["explication"] = ""
app.LOCATOR._refresh()
for _ in range(180):
    if app.SEMANTIC.ready:
        break
    time.sleep(1)
spans = slide_spans()
rows = []
for q in bank:
    for rang, c in enumerate(app.LOCATOR.find(q)["clips"]):
        ok = slide_of(spans, c["episode"], c["at"]) in labels[q["id"]]
        rows.append((ok, c["cos"], c.get("marge"), rang))
good = sorted(r[1] for r in rows if r[0])
bad = sorted(r[1] for r in rows if not r[0])
print(f"{len(rows)} extraits · justes {len(good)} · faux {len(bad)}")
print("cos des justes :", [round(x, 2) for x in good[:8]], "…", f"médiane {good[len(good) // 2]:.2f}" if good else "")
print("cos des faux   :", [round(x, 2) for x in bad])
for t in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55):
    kept = [r for r in rows if r[1] >= t]
    ok = sum(1 for r in kept if r[0])
    print(f"  CLIP_MIN_COS {t:.2f} : {len(kept)}/{len(rows)} gardés · {ok} justes · {len(kept) - ok} faux")
