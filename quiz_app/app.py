"""Simulateur d'examen DOP-C02 : charge une banque de questions JSON et l'ouvre dans le navigateur.

Usage :
    python quiz_app/app.py chemin/vers/questions.json [--port 8765] [--no-browser]
    python quiz_app/app.py fichier1.json fichier2.json ...     # plusieurs fichiers fusionnés
    python quiz_app/app.py chemin/vers/dossier                  # tous les .json du dossier

Le fichier doit suivre le schéma dop-c02_questions.schema.json (1.0 ou 1.1).
  - Questions avec 'enonce' + 'options' (1.1) : QCM corrigé automatiquement.
  - Questions sans 'options' (1.0)             : mode auto-évaluation (réponse révélée, tu notes toi-même).
Les questions 'non_traitable' sont ignorées ; les 'reconstituee' sont exclues par défaut (option dans l'app).

À côté de la banque sont enregistrés :
  <fichier>.progress.json  progression par question et réglages
  <fichier>.sessions.json  historique complet de toutes les sessions (terminées, abandonnées, temps écoulé)
(pour plusieurs fichiers ou un dossier : questions.*.json dans le dossier du premier fichier).

Si l'app est dans le coffre Obsidian des révisions (dossier parent avec .obsidian), elle propose aussi :
  - des liens vers les fiches de chaque domaine (ouverture dans Obsidian) ;
  - les épisodes audio / vidéo du podcast (podcast/audio, podcast/video/out) ;
  - l'ajout d'une ligne dans la section « Erreurs récurrentes » de DOP-C02.md.
"""
import argparse
import datetime
import json
import math
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
SCHEMA = HERE / "dop-c02_questions.schema.json"
THEME_IDS = ["sdlc_automation", "config_management_iac", "resilient_cloud_solutions",
             "monitoring_logging", "incident_event_response", "security_compliance"]

VAULT = HERE.parent if (HERE.parent / ".obsidian").is_dir() else None
MEDIA = {"audio": ("podcast/audio", ".mp3", "audio/mpeg"), "video": ("podcast/video/out", ".mp4", "video/mp4")}
# fiche Obsidian et épisodes du podcast associés à chaque domaine
THEME_LINKS = {
    "sdlc_automation": ("DOP-C02-SDLC-Automation", ["01-sdlc-automation", "09-questions-en-sdlc"]),
    "config_management_iac": ("DOP-C02-Configuration-Management-IaC", ["02-configuration-management-iac", "10-questions-en-iac"]),
    "resilient_cloud_solutions": ("DOP-C02-Resilient-Cloud-Solutions", ["03-resilient-cloud-solutions", "11-questions-en-resilience"]),
    "monitoring_logging": ("DOP-C02-Monitoring-and-Logging", ["04-monitoring-logging", "12-questions-en-monitoring"]),
    "incident_event_response": ("DOP-C02-Incident-and-Event-Response", ["05-incident-event-response", "13-questions-en-incident"]),
    "security_compliance": ("DOP-C02-Security-and-Compliance", ["06-security-compliance", "14-questions-en-security"]),
}
# Parcours de formation : pour chaque domaine, les étapes dans un ordre logique
# (cours → schémas du plus simple au plus complexe → questions en anglais → entraînement)
TRAINING = [
    ("sdlc_automation", ["01-sdlc-automation", "45-principe-tests-pipeline", "46-principe-artefacts",
                         "21-principe-hooks-codedeploy", "22-principe-strategies-deploiement", "34-principe-beanstalk-blue-green",
                         "47-principe-eks-stockage", "23-principe-pipeline-cross-compte", "09-questions-en-sdlc"]),
    ("config_management_iac", ["02-configuration-management-iac", "35-principe-partage-valeurs-stacks", "24-principe-stacksets",
                               "20-principe-control-tower", "36-principe-systems-manager", "48-principe-appconfig-automatisation",
                               "37-principe-golden-ami", "10-questions-en-iac"]),
    ("resilient_cloud_solutions", ["03-resilient-cloud-solutions", "25-principe-strategies-dr", "26-principe-route53-global-accelerator",
                                   "38-principe-rds-aurora", "39-principe-sqs-visibility", "49-principe-scaling-cache",
                                   "11-questions-en-resilience"]),
    ("monitoring_logging", ["04-monitoring-logging", "40-principe-cloudtrail-config-cloudwatch", "27-principe-sorties-cloudwatch-logs",
                            "28-principe-centralisation-logs", "50-principe-logs-securises-observabilite", "12-questions-en-monitoring"]),
    ("incident_event_response", ["05-incident-event-response", "29-principe-auto-remediation", "30-principe-echecs-lambda",
                                 "41-principe-depannage-cloudformation", "42-principe-roles-ecs", "13-questions-en-incident"]),
    ("security_compliance", ["06-security-compliance", "31-principe-evaluation-iam", "32-principe-acces-cross-compte",
                             "51-principe-identites-federation", "43-principe-tri-securite", "33-principe-instance-compromise",
                             "44-principe-s3-depuis-vpc", "14-questions-en-security"]),
]
TRAINING_FINAL = ["00-intro-technique-examen", "08-duels-notions-confondues", "07-quiz-eclair-veille"]


def training():
    """Le parcours, avec ce qui existe réellement : titre, vidéo ou audio, durée."""
    if not VAULT:
        return None

    def step(ep):
        mp3, mp4 = VAULT / "podcast" / "audio" / f"{ep}.mp3", VAULT / "podcast" / "video" / "out" / f"{ep}.mp4"
        if not (mp3.exists() or mp4.exists()):
            return None
        script = VAULT / "podcast" / "scripts" / f"{ep}.txt"
        title = script.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip() if script.exists() else ep
        num = int(ep[:2])
        kind = "cours" if num <= 6 else "schema" if num >= 20 else "questions" if 9 <= num <= 14 else "final"
        dur = round(mp3.stat().st_size * 8 / 64000) if mp3.exists() else None      # MP3 à 64 kb/s
        return {"id": ep, "kind": kind, "title": title, "video": mp4.exists(), "audio": mp3.exists(), "duration": dur}

    domains = [{"theme": th, "steps": [s for s in map(step, eps) if s]} for th, eps in TRAINING]
    return {"domains": domains, "final": [s for s in map(step, TRAINING_FINAL) if s]}


ERREURS_NOTE = "DOP-C02.md"
ERREURS_TITRE = "## ❌ Erreurs récurrentes"


def theme_links():
    """Ce qui existe réellement dans le coffre : fiches, audios, vidéos."""
    if not VAULT:
        return {}
    out = {}
    for tid, (fiche, episodes) in THEME_LINKS.items():
        entry = {"fiche": fiche if (VAULT / f"{fiche}.md").exists() else None, "audio": [], "video": []}
        for kind, (folder, ext, _) in MEDIA.items():
            entry[kind] = [e for e in episodes if (VAULT / folder / f"{e}{ext}").exists()]
        out[tid] = entry
    return out


# ---------- recherche du passage de fiche (et du moment de podcast) qui correspond à une question ----------
STOP = set("""le la les un une des de du et ou en au aux a à est sont pas ne que qui quoi dans sur pour par avec sans ce cet cette ces se
son sa ses on il elle ils leur plus moins tout tous toute très bien même mais donc car si alors quand comme aussi être avoir fait faire
peut doit c'est d'un d'une l'on qu'il the and for with that this from into which what when will must should can are was were has have
not all any each its their them they then than there these those such use using used company solution requirements requirement meet
meets engineer devops aws amazon need needs needed wants want least most option options question réponse bonne mauvaise
one two three all same time new version web running run uses every each own minimal configuration application applications
create created creating ensure make makes way best data also""".split())
# quelques équivalents anglais → français, pour que « parallel » retrouve « parallèle » dans les fiches et le podcast
EN_FR = {"parallel": "parallele", "deployment": "deploiement", "deployments": "deploiement", "deploy": "deploiement",
         "deploys": "deploiement", "deployed": "deploiement", "rollback": "rollback", "encrypted": "chiffre",
         "encryption": "chiffrement", "backup": "sauvegarde", "backups": "sauvegarde", "failover": "bascule",
         "replication": "replication", "permissions": "permission", "alarm": "alarme", "alarms": "alarme"}


def _norm(word):
    import unicodedata
    return unicodedata.normalize("NFKD", word.lower()).encode("ascii", "ignore").decode()


def _stem(n):
    """Pluriel simple : « alarms » → « alarm », « policies » → « policie » (identique des deux côtés)."""
    return n[:-1] if len(n) > 4 and n.endswith("s") and not n.endswith("ss") else n


def _terms(text):
    """Mots utiles d'un texte, avec un poids plus fort pour les termes techniques (CodeDeploy, KMS, S3…).
    Les mots composés (ContinueUpdateRollback, UPDATE_ROLLBACK_FAILED, cfn-signal) comptent aussi par morceaux."""
    out = {}

    def add(n, w):
        n = _stem(n)
        if (len(n) >= 3 or w >= 3) and n not in STOP:
            out[n] = max(out.get(n, 0), w)

    for w in re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9_\-]*", text or ""):
        n = _norm(w).strip("-_")
        if len(n) < 3 and not re.fullmatch(r"[A-Z0-9]{2,}", w):
            continue
        # vrai terme technique : CamelCase, sigle, chiffre (CodeDeploy, KMS, S3, UPDATE_ROLLBACK_FAILED) ;
        # un simple mot en majuscule (Auto, Scaling, Load) compte moins
        tech = bool(re.search(r"[A-Z].*[A-Z]|\d|_", w))
        weight = 3.0 if tech else (1.5 if w[0].isupper() and len(w) > 3 else 1.0)
        add(EN_FR.get(n, n), weight)
        parts = [p for p in re.split(r"[_\-]|(?<=[a-z])(?=[A-Z])", w) if p]
        if len(parts) > 1:
            for p in parts:
                add(_norm(p), weight * 0.6)
    return out


# diapositives de quiz ou de récapitulatif : pertinentes mais moins explicatives que le schéma lui-même
RECAP = re.compile(r"QUESTION|RÉFLEXE|SCÉNARIO|À retenir|En une image|Choisir|résume", re.I)


# Choix des extraits vidéo (réglés sur le jeu de test quiz_app/eval, à affiner avec les votes 👍/👎)
HYBRID_ALPHA = 0.4         # part du sens (embeddings) face aux mots-clés (BM25) dans le score combiné
CLIP_OTHER_DOMAIN = 0.6    # pénalité d'un extrait d'un autre domaine que la question
CLIP_RECAP = 0.85          # pénalité d'une diapositive de quiz ou de récapitulatif
CLIP_MIN_CONF = 0.55       # en dessous : aucun extrait (mieux vaut rien qu'un extrait faux)
CLIP_REL_TOP = 0.8         # le second extrait doit être presque aussi sûr que le premier
CLIP_MIN_COS = 0.40        # similarité de sens minimale (absolue, 0 à 1) ; à régler avec eval/calibrer.py et les votes


class Semantic:
    """Recherche par le sens : un petit modèle multilingue local (fastembed) compare la question anglaise
    aux répliques françaises. Construit en arrière-plan ; tant qu'il n'est pas prêt, l'app reste en mots-clés."""
    MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self):
        self.ready, self.model, self.U, self.owner, self.n = False, None, None, None, 0
        self.lock = threading.Lock()

    def start(self, clips):
        threading.Thread(target=self._build, args=(clips,), daemon=True).start()

    def _units(self, clips):
        units, owner = [], []
        for i, d in enumerate(clips):
            units.append(f"{d['slide']}. {d['shown'][:300]}")
            owner.append(i)
            for _, _, t in d["lines"]:
                units.append(t)
                owner.append(i)
        return units, owner

    def _build(self, clips):
        try:
            import hashlib
            import numpy as np
            from fastembed import TextEmbedding
        except ImportError:
            print("Recherche par le sens indisponible (pip install fastembed) : extraits choisis par mots-clés seulement.")
            return
        with self.lock:
            units, owner = self._units(clips)
            key = hashlib.sha1((self.MODEL + "\n".join(units)).encode()).hexdigest()[:16]
            cache = VAULT / "podcast" / ".cache" / f"clip-embeddings-{key}.npy"
            self.model = TextEmbedding(self.MODEL)
            if cache.exists():
                U = np.load(cache)
            else:
                print(f"Index des extraits par le sens : {len(units)} passages, première fois ~30 s…")
                U = np.array(list(self.model.embed(units)), dtype="float32")
                U /= np.linalg.norm(U, axis=1, keepdims=True)
                np.save(cache, U)
            self.U, self.owner, self.n, self.np = U, np.array(owner), len(clips), np
            self.ready = True
            print("Recherche par le sens prête.")

    def scores(self, q, good, clips):
        """Similarité (0 à 1, normalisée) de la question avec chaque diapositive : max sur ses passages."""
        np = self.np
        if len(clips) != self.n:
            return None
        ask = re.split(r"(?<=[.?!])\s+", (q.get("enonce") or q.get("titre") or "").strip())[-1]
        text = " ".join(filter(None, [*good, q.get("solution"), q.get("explication"), ask]))
        with self.lock:
            v = np.array(list(self.model.embed([text])), dtype="float32")[0]
        v /= np.linalg.norm(v)
        sims = self.U @ v
        out = np.full(self.n, -1.0, dtype="float32")
        np.maximum.at(out, self.owner, sims)
        lo, hi = float(out.min()), float(out.max())
        raw = out.tolist()
        return [(x - lo) / ((hi - lo) or 1) for x in raw], raw


SEMANTIC = Semantic()


class Locator:
    """Petit moteur BM25 sur les lignes des fiches (avec le titre de leur section) et les répliques du podcast."""

    def __init__(self):
        self.stamp, self.docs, self.cache = None, [], {}

    def _sources(self):
        fiches = sorted(VAULT.glob("DOP-C02*.md"))
        tls = sorted((VAULT / "podcast" / ".cache").glob("[0-9][0-9]-*.timeline.json"))
        return fiches, tls

    @staticmethod
    def _slide_text(spec):
        """Texte affiché sur une diapositive : libellés des boîtes et flèches, puces, cartes, lignes de tableau."""
        out = []
        for line in spec.get("body", []):
            if spec.get("type") == "diagram":
                parts = [x.strip() for x in line.split("|")]
                out += [x for x in parts[1:3] if x]
            else:
                out.append(re.sub(r"\*\*|::|^> ", " ", line))
        return " ".join(out)

    @staticmethod
    def _clips(timeline):
        """Une unité par diapositive : [début, fin] de la diapositive, son titre, son texte affiché et ses répliques.
        Une diapositive = une explication complète, du moment où elle apparaît jusqu'à la suivante."""
        slides, cur = [], None
        for e in timeline:
            if e["type"] == "slide":
                cur = {"idx": len(slides), "type": e["spec"].get("type", ""), "title": e["spec"].get("title", ""),
                       "shown": Locator._slide_text(e["spec"]), "items": []}
                slides.append(cur)
            elif e["type"] in ("say", "pause") and cur is not None:
                cur["items"].append(e)
        for sl in slides:
            lines = [e for e in sl["items"] if e["type"] == "say" and e.get("speaker") in ("L", "R")]
            if sl["type"] == "title" or not lines:
                continue                     # diapositive de titre : une introduction, jamais une explication
            sl["start"] = sl["items"][0]["start"]
            sl["end"] = sl["items"][-1]["start"] + sl["items"][-1]["dur"]
            sl["lines"] = lines
            yield sl

    def _refresh(self):
        fiches, tls = self._sources()
        stamp = tuple((p.name, p.stat().st_mtime) for p in fiches + tls)
        if stamp == self.stamp:
            return
        docs = []
        for f in fiches:
            heads, in_front = [], False
            for n, raw in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                line = raw.strip()
                if n == 1 and line == "---":
                    in_front = True; continue
                if in_front:
                    in_front = line != "---"; continue
                m = re.match(r"^(#{1,6})\s+(.*)$", line)
                if m:
                    level = len(m.group(1))
                    heads = [h for h in heads if h[0] < level] + [(level, m.group(2).strip())]
                    continue
                text = re.sub(r"[*`>|]|\[\[|\]\]|\[!\w+\]", " ", line).strip(" -")
                if len(text) < 12 or set(text) <= set("-: "):
                    continue
                title = " ".join(h[1] for h in heads)
                terms = _terms(text)
                for t, w in _terms(title).items():
                    terms[t] = max(terms.get(t, 0), w * 0.6)
                docs.append({"kind": "fiche", "file": f.stem, "line": n, "heading": heads[-1][1] if heads else "",
                             "path": [h[1] for h in heads], "text": text, "terms": terms})
        for tl in tls:
            ep = tl.name.split(".")[0]
            if not (VAULT / "podcast" / "audio" / f"{ep}.mp3").exists():
                continue
            script = VAULT / "podcast" / "scripts" / f"{ep}.txt"
            head = script.read_text(encoding="utf-8").splitlines()[:8] if script.exists() else [ep]
            title = head[0].lstrip("# ").strip()
            # domaine de l'épisode : « Domaine N » sur la diapositive de titre, sinon déduit du numéro
            m = re.search(r"Domaine (\d)", " ".join(head))
            num = int(ep[:2]) if ep[:2].isdigit() else 0
            domain = int(m.group(1)) if m else (num if 1 <= num <= 6 else num - 8 if 9 <= num <= 14 else None)
            video = (VAULT / "podcast" / "video" / "out" / f"{ep}.mp4").exists()
            for sl in self._clips(json.loads(tl.read_text(encoding="utf-8"))):
                spoken = " ".join(e["text"] for e in sl["lines"])
                terms = _terms(spoken)
                for t, w in _terms(sl["shown"]).items():
                    terms[t] = max(terms.get(t, 0), w)
                for t, w in _terms(sl["title"]).items():
                    terms[t] = max(terms.get(t, 0), w * 0.8)
                docs.append({"kind": "clip", "episode": ep, "title": title, "slide": sl["title"], "slide_idx": sl["idx"],
                             "principle": ep[:2].isdigit() and int(ep[:2]) >= 20, "video": video,
                             "start": round(sl["start"], 1), "end": round(sl["end"], 1),
                             "lines": [(round(e["start"], 2), round(e["dur"], 2), e["text"]) for e in sl["lines"]],
                             "text": spoken, "terms": terms, "shown": sl["shown"],
                             "recap": bool(RECAP.search(sl["title"])), "domain": domain})
        n = len(docs) or 1
        df = {}
        for d in docs:
            for t in d["terms"]:
                df[t] = df.get(t, 0) + 1
        self.idf = {t: max(0.0, math.log((n - c + 0.5) / (c + 0.5) + 1)) for t, c in df.items()}
        self.avglen = sum(len(d["terms"]) for d in docs) / n
        self.docs, self.stamp, self.cache = docs, stamp, {}
        SEMANTIC.ready = False
        SEMANTIC.start([d for d in docs if d["kind"] == "clip"])

    def _pick_clips(self, q, query, good, qdom):
        """Classe les diapositives en combinant mots-clés (BM25) et sens (embeddings multilingues),
        puis ne garde que les extraits assez sûrs. Renvoie (extraits, index de sens utilisé ?)."""
        clips = [d for d in self.docs if d["kind"] == "clip"]
        if not clips:
            return [], False
        k1, b = 1.2, 0.5
        bm = []
        for d in clips:
            sc = 0.0
            for t, wq in query.items():
                if t in d["terms"]:
                    tf = d["terms"][t]
                    sc += self.idf.get(t, 0) * wq * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d["terms"]) / self.avglen))
            bm.append(sc)
        top_bm = max(bm) or 1.0
        bm_raw = bm
        bm = [x / top_bm for x in bm]
        sem, cos = SEMANTIC.scores(q, good, clips) if SEMANTIC.ready else (None, None)
        conf = []
        for i, d in enumerate(clips):
            c = HYBRID_ALPHA * sem[i] + (1 - HYBRID_ALPHA) * bm[i] if sem is not None else bm[i]
            if d.get("recap"):
                c *= CLIP_RECAP
            if qdom and d.get("domain") and d["domain"] != qdom:
                c *= CLIP_OTHER_DOMAIN
            conf.append(c)
        order = sorted(range(len(clips)), key=lambda i: -conf[i])
        top = conf[order[0]]
        second = conf[order[1]] if len(order) > 1 else 0
        best = {}
        for i in order:
            d = clips[i]
            if d["principle"] in best:
                continue
            if conf[i] < CLIP_MIN_CONF or conf[i] < top * CLIP_REL_TOP:
                break
            if cos is not None and cos[i] < CLIP_MIN_COS:
                continue        # sens trop éloigné de la question : on n'affiche pas cet extrait
            best[d["principle"]] = self._window(d, query) | {
                "conf": round(conf[i], 3), "bm25": round(bm[i], 3), "sem": round(sem[i], 3) if sem is not None else None,
                "domain_ok": not (qdom and d.get("domain") and d["domain"] != qdom), "slide_idx": d["slide_idx"],
                # scores absolus, comparables d'une question à l'autre (pour régler les seuils avec les votes)
                "cos": round(cos[i], 3) if cos is not None else None, "bm25_brut": round(bm_raw[i], 1),
                "marge": round(conf[i] - second, 3) if i == order[0] else None}
        return [best[k] for k in (True, False) if k in best], sem is not None

    @staticmethod
    def _window(d, query):
        """Extrait affiché : la diapositive entière, ou, si elle dure plus de 2 minutes, une fenêtre autour
        de la réplique la plus proche de la question. La réplique sert aussi de citation."""
        def overlap(text):
            return sum(w for t, w in _terms(text).items() if t in query)
        at, dur, text = max(d["lines"], key=lambda ln: overlap(ln[2]))
        start, end = d["start"], d["end"]
        if end - start > 120:
            start = max(d["start"], at - 15)
            end = min(d["end"], at + dur + 45)
        out = {k: d[k] for k in ("episode", "title", "slide", "video", "principle")}
        return out | {"start": round(start, 1), "end": round(end, 1), "at": at, "text": text}

    def find(self, q):
        self._refresh()
        hit = self.cache.get(q["id"])
        if hit and (hit.get("sem") or not SEMANTIC.ready):     # recalculer si l'index de sens est prêt entre-temps
            return hit
        good = [o["texte"] for o in (q.get("options") or []) if o.get("lettre") in q.get("reponses", [])]
        good += [o["texte"] for o in q.get("options_correctes") or []]
        # le concept à retrouver est surtout dans la bonne réponse : ses mots comptent double
        query = _terms(" ".join(filter(None, [q.get("enonce") or q.get("titre"), q.get("explication")])))
        for t, w in _terms(" ".join(filter(None, [*good, q.get("solution")]))).items():
            query[t] = max(query.get(t, 0), w) * 2
        k1, b = 1.2, 0.5
        qdom = THEME_IDS.index(q["theme"]) + 1 if q.get("theme") in THEME_IDS else None
        scored = []
        for d in self.docs:
            s = 0.0
            for t, wq in query.items():
                if t in d["terms"]:
                    tf = d["terms"][t]
                    s += self.idf.get(t, 0) * wq * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d["terms"]) / self.avglen))
            if s > 0:
                if d.get("recap"):
                    s *= 0.7
                if d["kind"] == "clip" and qdom and d.get("domain") and d["domain"] != qdom:
                    s *= CLIP_OTHER_DOMAIN       # un extrait d'un autre domaine n'explique presque jamais la question
                scored.append((s, d))
        scored.sort(key=lambda x: -x[0])
        top_f = next((s for s, d in scored if d["kind"] == "fiche"), 0)
        fiches, seen = [], set()
        for s, d in scored:
            if d["kind"] == "fiche":
                key = (d["file"], d["heading"])
                if s >= top_f * 0.55 and key not in seen and len(fiches) < 3:
                    seen.add(key)
                    fiches.append({k: d[k] for k in ("file", "line", "heading", "path", "text")} | {"score": round(s, 1)})
        clips, sem_used = self._pick_clips(q, query, good, qdom)
        self.cache[q["id"]] = {"fiches": fiches, "clips": clips, "sem": sem_used}
        return self.cache[q["id"]]


LOCATOR = Locator() if VAULT else None


def append_erreur(line):
    """Ajoute une ligne à la fin de la section « Erreurs récurrentes » de DOP-C02.md."""
    note = VAULT / ERREURS_NOTE
    text = note.read_text(encoding="utf-8")
    pos = text.find(ERREURS_TITRE)
    if pos < 0:
        text = text.rstrip("\n") + f"\n\n{ERREURS_TITRE}\n\n{line}\n"
    else:
        nxt = text.find("\n## ", pos + len(ERREURS_TITRE))
        if nxt < 0:
            text = text.rstrip("\n") + f"\n{line}\n"
        else:
            before = text[:nxt].rstrip("\n")
            text = f"{before}\n{line}\n{text[nxt:]}"
    note.write_text(text, encoding="utf-8")


def validate(bank):
    """Valide la banque. Renvoie (erreurs bloquantes, avertissements, questions utilisables)."""
    errors, warnings = [], []
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
        # la clé « $schema » en tête de fichier est une convention courante : on ne la signale pas
        body = {k: v for k, v in bank.items() if k != "$schema"} if isinstance(bank, dict) else bank
        for e in sorted(validator.iter_errors(body), key=lambda e: list(e.path))[:15]:
            where = "/".join(str(p) for p in e.path) or "(racine)"
            warnings.append(f"Schéma : {where} — {e.message[:160]}")
    except ImportError:
        warnings.append("Module 'jsonschema' absent : validation simplifiée (pip install jsonschema pour la complète).")

    if not isinstance(bank, dict) or not isinstance(bank.get("questions"), list):
        return ["Le fichier doit contenir un objet avec une liste 'questions'."], warnings, []

    usable, seen = [], set()
    for n, q in enumerate(bank["questions"]):
        qid = q.get("id", f"#{n}") if isinstance(q, dict) else f"#{n}"
        if not isinstance(q, dict):
            warnings.append(f"{qid} : pas un objet, ignorée."); continue
        if qid in seen:
            warnings.append(f"{qid} : identifiant en double, ignorée."); continue
        seen.add(qid)
        if q.get("statut") == "non_traitable" or not q.get("reponses"):
            continue
        if q.get("theme") not in THEME_IDS:
            warnings.append(f"{qid} : thème absent ou inconnu, ignorée."); continue
        opts = q.get("options") or []
        letters = {o.get("lettre") for o in opts if isinstance(o, dict)}
        if opts and not set(q["reponses"]) <= letters:
            warnings.append(f"{qid} : réponse(s) {q['reponses']} absente(s) des options ; passée en auto-évaluation.")
            q = {**q, "options": []}
        usable.append(q)
    return errors, warnings, usable


class Handler(BaseHTTPRequestHandler):
    bank_path: Path
    payload: dict

    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    lock = threading.Lock()

    @property
    def progress_path(self):
        return self.bank_path.with_name(self.bank_path.stem + ".progress.json")

    @property
    def sessions_path(self):
        return self.bank_path.with_name(self.bank_path.stem + ".sessions.json")

    def read_sessions(self):
        p = self.sessions_path
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"sessions": []}

    def write_json(self, path, data):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send(200, (HERE / "static" / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/bank":
            self.send(200, self.payload)
        elif self.path == "/api/progress":
            p = self.progress_path
            self.send(200, json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})
        elif self.path == "/api/training":
            self.send(200, training() or {"domains": [], "final": []})
        elif self.path == "/api/sessions":
            with self.lock:
                self.send(200, self.read_sessions())
        elif self.path.startswith("/media/"):
            self.send_media()
        elif self.path.startswith("/api/locate?id="):
            qid = self.path.split("=", 1)[1]
            q = next((x for x in self.payload["questions"] if x.get("id") == qid), None)
            if not (q and LOCATOR):
                return self.send(404, {"error": "introuvable"})
            with self.lock:
                self.send(200, LOCATOR.find(q))
        else:
            self.send(404, {"error": "introuvable"})

    def send_media(self):
        """Sert un épisode du podcast, avec prise en charge des requêtes partielles (avance rapide)."""
        m = re.fullmatch(r"/media/(audio|video)/([\w.-]+)", self.path)
        if not (m and VAULT):
            return self.send(404, {"error": "introuvable"})
        folder, ext, ctype = MEDIA[m.group(1)]
        path = (VAULT / folder / m.group(2)).resolve()
        if path.suffix != ext or not path.is_file() or (VAULT / folder).resolve() not in path.parents:
            return self.send(404, {"error": "introuvable"})
        size = path.stat().st_size
        start, end = 0, size - 1
        rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if rng and (rng.group(1) or rng.group(2)):
            if rng.group(1):
                start = int(rng.group(1))
                end = min(int(rng.group(2)), size - 1) if rng.group(2) else size - 1
            else:
                start = max(0, size - int(rng.group(2)))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (ConnectionResetError, BrokenPipeError):
            pass  # le navigateur a interrompu la lecture (avance rapide)

    def do_POST(self):
        if self.path == "/api/obsidian/erreur":
            return self.post_erreur()
        if self.path == "/api/reset":
            return self.post_reset()
        if self.path not in ("/api/progress", "/api/sessions", "/api/sessions/clear"):
            return self.send(404, {"error": "introuvable"})
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self.send(400, {"error": "JSON invalide"})
        with self.lock:
            if self.path == "/api/progress":
                self.write_json(self.progress_path, data)
            elif self.path == "/api/sessions/clear":
                self.write_json(self.sessions_path, {"sessions": []})
            else:
                # une session terminée ou abandonnée : ajoutée (ou remplacée si même id)
                store = self.read_sessions()
                store["sessions"] = [s for s in store["sessions"] if s.get("id") != data.get("id")] + [data]
                self.write_json(self.sessions_path, store)
        self.send(200, {"ok": True})

    def post_reset(self):
        """Réinitialisation choisie par l'utilisateur, après sauvegarde datée des fichiers actuels."""
        try:
            what = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self.send(400, {"error": "JSON invalide"})
        if what.get("confirm") != "RÉINITIALISER":
            return self.send(400, {"error": "confirmation manquante"})
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backups = []
        with self.lock:
            for path in (self.progress_path, self.sessions_path):
                if path.exists():
                    bak = path.with_name(path.name.replace(".json", f".backup-{stamp}.json"))
                    bak.write_bytes(path.read_bytes())
                    backups.append(bak.name)
            prog = json.loads(self.progress_path.read_text(encoding="utf-8")) if self.progress_path.exists() else {}
            if what.get("progress"):
                prog["questions"], prog["history"], prog["training"] = {}, [], {}
            if what.get("notes"):
                prog["notes"] = {}
            if what.get("badClips"):
                prog["badClips"] = {}
            self.write_json(self.progress_path, prog)       # les réglages sont conservés
            if what.get("sessions"):
                self.write_json(self.sessions_path, {"sessions": []})
        self.send(200, {"ok": True, "sauvegardes": backups})

    def post_erreur(self):
        if not (VAULT and (VAULT / ERREURS_NOTE).exists()):
            return self.send(404, {"error": f"{ERREURS_NOTE} introuvable dans le coffre"})
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self.send(400, {"error": "JSON invalide"})
        texte = " ".join(str(data.get("texte", "")).split())
        if not texte:
            return self.send(400, {"error": "texte vide"})
        line = f"- {datetime.date.today():%d/%m} · **{data.get('theme', '?')}** ({data.get('id', '?')}) : {texte}"
        with self.lock:
            append_erreur(line)
        self.send(200, {"ok": True, "ligne": line})


def load_bank(args_questions):
    """Fichiers, dossier ou jokers → (chemin de la progression, contenu servi par /api/bank). Quitte en cas d'erreur."""
    files, from_dir = [], set()
    for arg in args_questions:
        if any(c in arg for c in "*?["):
            # PowerShell et cmd ne développent pas les jokers : on le fait ici
            p = Path(arg).expanduser()
            matches = sorted(p.parent.glob(p.name))
            if not matches:
                sys.exit(f"Aucun fichier ne correspond à : {arg}")
            files += [m.resolve() for m in matches]
            continue
        p = Path(arg).expanduser().resolve()
        if p.is_dir():
            found = sorted(f for f in p.glob("*.json")
                           if not f.name.endswith((".progress.json", ".sessions.json")) and ".backup-" not in f.name)
            files += found
            from_dir.update(found)
        elif p.is_file():
            files.append(p)
        else:
            sys.exit(f"Fichier ou dossier introuvable : {p}")
    if not files:
        sys.exit("Aucun fichier .json trouvé.")
    # copie corrigée par check_themes.py présente à côté de l'original : on prend la copie, pas les deux
    corrected = {f.with_name(f.name.replace(".themes-corriges.json", ".json")) for f in files if f.name.endswith(".themes-corriges.json")}
    skipped = [f for f in files if f in corrected]
    files = [f for f in files if f not in corrected]
    if skipped:
        print(f"{len(skipped)} fichier(s) remplacé(s) par leur copie aux thèmes corrigés (.themes-corriges.json)")

    bank, kept = None, []
    for f in files:
        try:
            part = json.loads(f.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            if f in from_dir:
                print(f"Ignoré : {f.name} (JSON invalide)"); continue
            sys.exit(f"JSON invalide dans {f.name} : ligne {e.lineno}, colonne {e.colno} — {e.msg}")
        if not isinstance(part, dict) or not isinstance(part.get("questions"), list):
            if f in from_dir:
                print(f"Ignoré : {f.name} (pas une banque de questions)"); continue
            sys.exit(f"{f.name} : il faut un objet avec une liste 'questions'.")
        kept.append(f)
        if bank is None:
            bank = {k: v for k, v in part.items() if k != "questions"}
            bank["questions"] = []
        bank["questions"] += part["questions"]
    if not kept:
        sys.exit("Aucune banque de questions trouvée.")
    # une seule banque : progression à côté du fichier ; plusieurs : dans le dossier du premier
    path = kept[0] if len(kept) == 1 else kept[0].with_name("questions.json")
    source = kept[0].name if len(kept) == 1 else f"{len(kept)} fichiers ({kept[0].parent.name})"

    errors, warnings, usable = validate(bank)
    if errors:
        sys.exit("\n".join(errors))
    for w in warnings:
        print("Avertissement :", w)
    if not usable:
        sys.exit("Aucune question utilisable dans ce fichier.")
    payload = {"meta": bank.get("meta", {}), "themes": bank.get("themes", []),
               "questions": usable, "warnings": warnings, "source": source,
               "vault": VAULT.name if VAULT else None, "links": theme_links(),
               "erreurs_note": bool(VAULT and (VAULT / ERREURS_NOTE).exists())}
    return path, payload


def main():
    ap = argparse.ArgumentParser(description="Simulateur d'examen DOP-C02")
    ap.add_argument("questions", nargs="+", help="fichier(s) JSON de questions, ou dossier")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    args = ap.parse_args()

    Handler.bank_path, Handler.payload = load_bank(args.questions)
    usable, source = Handler.payload["questions"], Handler.payload["source"]
    url = f"http://127.0.0.1:{args.port}/"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    n_qcm = sum(1 for q in usable if q.get("options"))
    print(f"{len(usable)} questions chargées depuis {source} — {n_qcm} en QCM, {len(usable) - n_qcm} en auto-évaluation")
    if not n_qcm:
        print("  → Aucune question n'a de champs 'enonce' + 'options' : seul le titre sera affiché (schéma 1.1 requis pour le QCM).")
    print(f"Simulateur : {url}   (Ctrl+C pour arrêter)")
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")


if __name__ == "__main__":
    main()
