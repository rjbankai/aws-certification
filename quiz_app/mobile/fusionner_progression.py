#!/usr/bin/env python3
"""Fusionne la progression exportée du téléphone (📱 → Exporter ma progression) avec celle du PC.

    python quiz_app/mobile/fusionner_progression.py progression-telephone-….json "<tes questions>"

Par question, le passage le plus récent l'emporte (répétition espacée comprise) ; les sessions des deux
côtés sont gardées (une session reprise sur l'autre appareil : la plus récente). Les fichiers du PC
sont d'abord sauvegardés (.backup-<date>.json), comme pour la réinitialisation de l'app.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.stdout.reconfigure(errors="replace")      # console Windows (cp1252) : pas de plantage sur un symbole
sys.path.insert(0, str(HERE.parent))
import app  # noqa: E402


def merge_progress(pc, tel):
    out = dict(pc)
    qs = dict(pc.get("questions", {}))
    for qid, p in tel.get("questions", {}).items():
        if qid not in qs or (p.get("ts") or 0) > (qs[qid].get("ts") or 0):
            qs[qid] = p
    out["questions"] = qs
    notes = dict(pc.get("notes", {}))
    for qid, n in tel.get("notes", {}).items():
        mine = notes.get(qid)
        if not mine or mine in n:
            notes[qid] = n                       # nouvelle note, ou note complétée sur le téléphone
        elif n not in mine:
            notes[qid] = f"{mine} · {n}"         # deux notes différentes : on garde les deux
    out["notes"] = notes
    bad = {k: list(v) for k, v in pc.get("badClips", {}).items()}
    for k, v in tel.get("badClips", {}).items():
        bad[k] = sorted(set(bad.get(k, [])) | set(v))
    out["badClips"] = bad
    key = lambda v: (v.get("q"), v.get("ep"), v.get("slide"), v.get("ts"))
    seen, votes = set(), []
    for v in pc.get("clipVotes", []) + tel.get("clipVotes", []):
        if key(v) not in seen:
            seen.add(key(v)); votes.append(v)
    out["clipVotes"] = votes
    tr = dict(pc.get("training", {}))
    for k, ts in tel.get("training", {}).items():
        tr[k] = max(tr.get(k) or 0, ts or 0)
    out["training"] = tr
    out["settings"] = pc.get("settings", tel.get("settings", {}))        # les réglages du PC restent
    return out


def merge_sessions(pc, tel):
    by = {s["id"]: s for s in pc}
    for s in tel:
        if s["id"] not in by or (s.get("fin") or 0) > (by[s["id"]].get("fin") or 0):
            by[s["id"]] = s
    return sorted(by.values(), key=lambda s: s.get("debut") or 0)


def main():
    ap = argparse.ArgumentParser(description="Fusionner la progression du téléphone dans celle du PC")
    ap.add_argument("export", help="fichier exporté depuis l'app Android")
    ap.add_argument("questions", nargs="+", help="tes questions, comme pour app.py (fichier, dossier ou jokers)")
    args = ap.parse_args()

    tel = json.loads(Path(args.export).read_text(encoding="utf-8"))
    if tel.get("format") != "dop-c02-progression":
        sys.exit("Ce fichier n'est pas un export de progression de l'app Android.")
    bank_path, _ = app.load_bank(args.questions)
    prog_p = bank_path.with_name(bank_path.stem + ".progress.json")
    sess_p = bank_path.with_name(bank_path.stem + ".sessions.json")
    pc_prog = json.loads(prog_p.read_text(encoding="utf-8")) if prog_p.exists() else {}
    pc_sess = json.loads(sess_p.read_text(encoding="utf-8")).get("sessions", []) if sess_p.exists() else []

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for p in (prog_p, sess_p):
        if p.exists():
            p.with_name(p.name.replace(".json", f".backup-{stamp}.json")).write_bytes(p.read_bytes())

    prog = merge_progress(pc_prog, tel.get("progress", {}))
    sess = merge_sessions(pc_sess, tel.get("sessions", []))
    prog_p.write_text(json.dumps(prog, ensure_ascii=False, indent=1), encoding="utf-8")
    sess_p.write_text(json.dumps({"sessions": sess}, ensure_ascii=False, indent=1), encoding="utf-8")
    n_new = len(set(prog["questions"]) - set(pc_prog.get("questions", {})))
    print(f"Fusion faite (sauvegardes .backup-{stamp}.json) : {len(prog['questions'])} questions travaillées "
          f"(+{n_new} venues du téléphone) · {len(sess)} sessions (+{len(sess) - len(pc_sess)}).")
    print("Relance l'app sur le PC pour voir la progression fusionnée.")


if __name__ == "__main__":
    main()
