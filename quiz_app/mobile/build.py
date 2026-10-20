#!/usr/bin/env python3
"""Fabrique l'APK Android hors ligne : la page du simulateur + couche mobile + vidéos et podcasts.

    python quiz_app/mobile/build.py            # → quiz_app/mobile/DOP-C02.apk

Les questions n'y sont PAS : elles s'importent dans l'app (paquet fait par preparer.py), ce qui permet
de les mettre à jour sans refaire l'APK. Prérequis : Node 22+, Android Studio (JDK + SDK Android).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
QUIZ = HERE.parent
sys.stdout.reconfigure(errors="replace")      # console Windows (cp1252) : pas de plantage sur un symbole
sys.path.insert(0, str(QUIZ))
import app  # noqa: E402

WWW = HERE / "www"
SDK = Path(os.environ.get("ANDROID_HOME") or Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk")
JDK = Path(os.environ.get("DOPC02_JAVA_HOME") or r"C:\Program Files\Android\Android Studio\jbr")
APK = HERE / "DOP-C02.apk"


def run(cmd, cwd, env=None):
    print("→", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True, shell=(os.name == "nt"))


def build_www():
    if WWW.exists():
        shutil.rmtree(WWW)
    (WWW / "media").mkdir(parents=True)
    # la même page que sur le PC, avec la couche mobile chargée avant son script
    html = (QUIZ / "static" / "index.html").read_text(encoding="utf-8")
    marker = '<script>\n"use strict";'
    assert html.count(marker) == 1, "script principal introuvable dans index.html"
    html = html.replace(marker, '<script src="mobile.js"></script>\n' + marker)
    html = html.replace('content="width=device-width, initial-scale=1"', 'content="width=device-width, initial-scale=1, viewport-fit=cover"')
    (WWW / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(HERE / "mobile.js", WWW / "mobile.js")
    # parcours de formation (titres, durées) et médias
    (WWW / "training.json").write_text(json.dumps(app.training() or {"domains": [], "final": []}, ensure_ascii=False), encoding="utf-8")
    total = 0
    for kind, (folder, ext, _) in app.MEDIA.items():
        dest = WWW / "media" / kind
        dest.mkdir()
        for f in sorted((app.VAULT / folder).glob(f"*{ext}")):
            shutil.copy2(f, dest / f.name)
            total += f.stat().st_size
    print(f"www prêt : {total / 1e6:.0f} Mo de médias")


def main():
    if not app.VAULT:
        sys.exit("Coffre Obsidian introuvable (dossier parent de quiz_app).")
    if not (JDK / "bin" / "java.exe").exists() or not SDK.exists():
        sys.exit(f"JDK ({JDK}) ou SDK Android ({SDK}) introuvable : installe Android Studio, ou règle DOPC02_JAVA_HOME / ANDROID_HOME.")
    build_www()
    if not (HERE / "node_modules").exists():
        run(["npm", "install", "--no-fund", "--no-audit"], HERE)
    if not (HERE / "android").exists():
        run(["npx", "cap", "add", "android"], HERE)
    run(["npx", "cap", "sync", "android"], HERE)
    env = dict(os.environ, JAVA_HOME=str(JDK), ANDROID_HOME=str(SDK), ANDROID_SDK_ROOT=str(SDK))
    (HERE / "android" / "local.properties").write_text(f"sdk.dir={SDK.as_posix()}\n", encoding="utf-8")
    run([str(HERE / "android" / ("gradlew.bat" if os.name == "nt" else "gradlew")), "assembleDebug", "--console=plain", "-q"], HERE / "android", env)
    out = HERE / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    shutil.copy2(out, APK)
    print(f"\nAPK prêt : {APK}  ({APK.stat().st_size / 1e6:.0f} Mo)")


if __name__ == "__main__":
    main()
