"""Vérifie que le thème (domaine) de chaque question d'une banque JSON est cohérent avec son contenu.

Principe : les 6 fiches de domaine du coffre (DOP-C02-SDLC-Automation.md, …) servent de vocabulaire de
référence. Chaque question (énoncé + bonne réponse + explication) est comparée aux lignes de chaque fiche
(BM25, le même moteur que les passages de l'app). Le domaine qui ressort le plus nettement est le domaine
probable. Seuls les désaccords NETS sont signalés : une question peut légitimement toucher deux domaines.

Usage :
    python quiz_app/check_themes.py <fichier.json | dossier | joker> [--fix] [--seuil 1.6]

Produit, à côté de la banque :
    themes-rapport.md                     la liste des questions suspectes, avec les mots-clés qui ont décidé
    <fichier>.themes-corriges.json        (avec --fix) une COPIE corrigée ; l'original n'est jamais modifié
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import app  # noqa: E402  (réutilise le découpage en termes et l'index des fiches)

FICHES = {
    "DOP-C02-SDLC-Automation": "sdlc_automation",
    "DOP-C02-Configuration-Management-IaC": "config_management_iac",
    "DOP-C02-Resilient-Cloud-Solutions": "resilient_cloud_solutions",
    "DOP-C02-Monitoring-and-Logging": "monitoring_logging",
    "DOP-C02-Incident-and-Event-Response": "incident_event_response",
    "DOP-C02-Security-and-Compliance": "security_compliance",
}
LIBELLES = {
    "sdlc_automation": "SDLC Automation", "config_management_iac": "Configuration Management & IaC",
    "resilient_cloud_solutions": "Resilient Cloud Solutions", "monitoring_logging": "Monitoring & Logging",
    "incident_event_response": "Incident & Event Response", "security_compliance": "Security & Compliance",
}
TOP_LINES = 6        # lignes de fiche retenues par domaine pour le score
# Ce que la question demande d'ACCOMPLIR (verbes et objectifs) : c'est ce qui décide du domaine,
# plus que les services cités dans le contexte. Cherché dans l'énoncé, surtout sa dernière phrase.
INTENT = {
    "sdlc_automation": r"deploy|deployment|pipeline|build|release|rollback|blue/green|canary|artifact|test(s|ing)? (before|the new)|commit",
    "config_management_iac": r"provision|template|stack|infrastructure as code|standardi[sz]e|new accounts?|organizations?|patch|configuration drift|golden ami|fleet",
    "resilient_cloud_solutions": r"\bRTO\b|\bRPO\b|disaster|highly available|high availability|failover|fail over|recover|resilien|scal(e|ing) (to|automatically)|outage",
    "monitoring_logging": r"visuali[sz]e|dashboard|metric|monitor|logs?\b|trace|observab|alarm|insight|analy[sz]e",
    "incident_event_response": r"troubleshoot|root cause|remediat|respond|notif|automatically (fix|stop|disable|restart)|investigat|fail(s|ed|ing)\b|error",
    "security_compliance": r"encrypt|least privilege|complian|audit|unauthori[sz]ed|credential|permission|access to|secret|vulnerab|threat|attack",
}
INTENT_BONUS = 0.18  # +18 % du meilleur score par objectif reconnu (2 au maximum par domaine)


def index():
    if not app.LOCATOR:
        sys.exit("Les fiches du coffre sont introuvables (l'outil doit être dans le dossier quiz_app du coffre).")
    app.LOCATOR._refresh()
    docs = [d for d in app.LOCATOR.docs if d["kind"] == "fiche" and d["file"] in FICHES]
    if not docs:
        sys.exit("Aucune fiche de domaine trouvée.")
    return docs, app.LOCATOR.idf, app.LOCATOR.avglen


def whole_terms(text):
    """Termes sans les morceaux de noms composés : « EventBridge » ne doit pas compter aussi « event » et « bridge »."""
    full = app._terms(text)
    keep = {app._stem(app._norm(w).strip("-_")) for w in re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9_\-]*", text or "")}
    keep |= {app.EN_FR.get(k, k) for k in keep}
    return {t: w for t, w in full.items() if t in keep}


def domain_scores(q, docs, idf, avglen):
    good = [o["texte"] for o in (q.get("options") or []) if o.get("lettre") in q.get("reponses", [])]
    good += [o["texte"] for o in q.get("options_correctes") or []]
    query = whole_terms(" ".join(filter(None, [q.get("enonce") or q.get("titre"), q.get("explication")])))
    for t, w in whole_terms(" ".join(filter(None, [*good, q.get("solution")]))).items():
        query[t] = max(query.get(t, 0), w) * 2
    k1, b = 1.2, 0.5
    per = {th: [] for th in FICHES.values()}
    for d in docs:
        s, hits = 0.0, []
        for t, wq in query.items():
            if t in d["terms"]:
                tf = d["terms"][t]
                c = idf.get(t, 0) * wq * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d["terms"]) / avglen))
                s += c
                hits.append((c, t))
        if s > 0:
            per[FICHES[d["file"]]].append((s, hits))
    scores, keys = {}, {}
    for th, lst in per.items():
        lst.sort(key=lambda x: -x[0])
        top = lst[:TOP_LINES]
        scores[th] = sum(s for s, _ in top)
        contrib = {}
        for _, hits in top:
            for c, t in hits:
                contrib[t] = contrib.get(t, 0) + c
        keys[th] = [t for t, _ in sorted(contrib.items(), key=lambda x: -x[1])[:6]]
    # bonus d'objectif : ce que demande la question (la dernière phrase compte double)
    stem = q.get("enonce") or q.get("titre") or ""
    sentences = re.split(r"(?<=[.?!])\s+", stem.strip())
    ask = sentences[-1] if sentences else ""
    ref = max(scores.values()) if scores else 0
    for th, pattern in INTENT.items():
        n = len(re.findall(pattern, stem, re.I)) + len(re.findall(pattern, ask, re.I))
        if n:
            scores[th] += ref * INTENT_BONUS * min(n, 2)
            hit = re.search(pattern, ask, re.I) or re.search(pattern, stem, re.I)
            keys[th] = [f"objectif : {hit.group(0)}"] + keys[th][:5]
    return scores, keys


def load(paths):
    files = []
    for arg in paths:
        p = Path(arg).expanduser()
        if any(c in arg for c in "*?["):
            files += sorted(p.parent.glob(p.name))
        elif p.is_dir():
            files += sorted(f for f in p.glob("*.json") if not f.name.endswith((".progress.json", ".sessions.json", ".themes-corriges.json")))
        elif p.is_file():
            files.append(p)
    banks = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("questions"), list):
            banks.append((f, data))
    if not banks:
        sys.exit("Aucune banque de questions trouvée.")
    return banks


def main():
    ap = argparse.ArgumentParser(description="Vérifie la cohérence des thèmes d'une banque de questions DOP-C02")
    ap.add_argument("questions", nargs="+")
    ap.add_argument("--fix", action="store_true", help="écrire une copie corrigée de chaque fichier")
    ap.add_argument("--seuil", type=float, default=1.6,
                    help="écart minimal entre le domaine probable et le thème actuel (défaut 1.6 = 60 %% de plus)")
    args = ap.parse_args()

    docs, idf, avglen = index()
    banks = load(args.questions)
    rows, total, fixed = [], 0, {}
    for f, data in banks:
        for q in data["questions"]:
            if not isinstance(q, dict) or q.get("statut") == "non_traitable" or not q.get("theme"):
                continue
            total += 1
            scores, keys = domain_scores(q, docs, idf, avglen)
            best = max(scores, key=scores.get)
            cur = q["theme"]
            cur_s, best_s = scores.get(cur, 0), scores[best]
            if best != cur and best_s > 0 and (cur_s == 0 or best_s / cur_s >= args.seuil):
                ratio = best_s / cur_s if cur_s else float("inf")
                rows.append((f.name, q.get("id", "?"), cur, best, ratio, keys[best], (q.get("titre") or "")[:90]))
                fixed.setdefault(f, set()).add(q.get("id"))

    out_dir = banks[0][0].parent
    rows.sort(key=lambda r: -r[4])
    lines = [f"# Vérification des thèmes — {total} questions analysées", "",
             f"**{len(rows)} question(s) suspecte(s)** (domaine probable au moins {args.seuil:g} fois plus net que le thème actuel).",
             "Une question peut toucher deux domaines : relis chaque cas avant de corriger.", "",
             "| Fichier | ID | Thème actuel | Domaine probable | Netteté | Mots-clés décisifs | Titre |", "|---|---|---|---|---|---|---|"]
    for name, qid, cur, best, ratio, kw, titre in rows:
        r = "∞" if ratio == float("inf") else f"×{ratio:.1f}"
        lines.append(f"| {name} | {qid} | {LIBELLES.get(cur, cur)} | **{LIBELLES[best]}** | {r} | {', '.join(kw)} | {titre.replace('|', '/')} |")
    report = out_dir / "themes-rapport.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    by = {}
    for r in rows:
        by[(r[2], r[3])] = by.get((r[2], r[3]), 0) + 1
    print(f"{total} questions analysées · {len(rows)} suspecte(s)")
    for (cur, best), n in sorted(by.items(), key=lambda x: -x[1]):
        print(f"  {n:3d} × {LIBELLES.get(cur, cur)}  →  {LIBELLES[best]}")
    print(f"Rapport : {report}")

    if args.fix and rows:
        best_of = {(r[0], r[1]): r[3] for r in rows}
        for f, data in banks:
            if f not in fixed:
                continue
            copy = json.loads(json.dumps(data))
            for q in copy["questions"]:
                new = best_of.get((f.name, q.get("id")))
                if new:
                    q["theme"], q["theme_libelle"] = new, LIBELLES[new]
            if isinstance(copy.get("themes"), list):
                for t in copy["themes"]:
                    t["nb_questions"] = sum(1 for q in copy["questions"] if q.get("theme") == t.get("id"))
            target = f.with_name(f.stem + ".themes-corriges.json")
            target.write_text(json.dumps(copy, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Copie corrigée : {target}")


if __name__ == "__main__":
    main()
