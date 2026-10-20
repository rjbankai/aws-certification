"use strict";
// Couche mobile de l'app Android : remplace le serveur Python (app.py) par le stockage du téléphone.
// La page (index.html) est la même que sur le PC ; ce script intercepte ses appels /api/* et adapte
// ce qui n'existe pas dans une app : médias, téléchargements, impression, bouton retour.
(() => {
  // erreurs visibles dans « adb logcat » (Capacitor/Console)
  window.addEventListener("error", e => console.error(`[mobile] ${e.message} @${e.filename}:${e.lineno}`));
  window.addEventListener("unhandledrejection", e => console.error(`[mobile] promesse rejetée : ${e.reason?.message || e.reason}`));
  // ---------- stockage : IndexedDB, une simple table clé → valeur ----------
  const db = new Promise((ok, ko) => {
    const r = indexedDB.open("dop-c02", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("kv");
    r.onsuccess = () => ok(r.result);
    r.onerror = () => ko(r.error);
  });
  const tx = (mode, f) => db.then(d => new Promise((ok, ko) => {
    const t = d.transaction("kv", mode), req = f(t.objectStore("kv"));
    t.oncomplete = () => ok(req?.result);
    t.onerror = () => ko(t.error);
  }));
  const get = k => tx("readonly", s => s.get(k));
  const set = (k, v) => tx("readwrite", s => s.put(v, k));
  // les écritures passent l'une après l'autre (deux sessions enregistrées coup sur coup ne s'écrasent pas)
  let chain = Promise.resolve();
  const serial = f => (chain = chain.then(f, f));
  navigator.storage?.persist?.().catch(() => {});

  // ---------- natif (Capacitor) ----------
  const native = (plugin, method, opts) => {
    const C = window.Capacitor, p = C?.Plugins?.[plugin];
    if (p?.[method]) return p[method](opts);
    if (C?.nativePromise) return C.nativePromise(plugin, method, opts);
    return Promise.reject(new Error("fonction native indisponible"));
  };
  // un fichier texte → feuille de partage Android (Drive, Gmail, Fichiers…)
  async function shareText(name, text) {
    try {
      const { uri } = await native("Filesystem", "writeFile", { path: name, data: text, directory: "CACHE", encoding: "utf8" });
      await native("Share", "share", { title: name, files: [uri], dialogTitle: "Enregistrer ou envoyer" });
    } catch (e) {
      if (!/cancel/i.test(String(e?.message || e))) alert(`Partage impossible : ${e?.message || e}`);
    }
  }

  // ---------- l'API du serveur, rejouée localement ----------
  let PACK;
  const pack = async () => {
    if (PACK === undefined) {
      const bank = await get("bank");
      PACK = bank ? { bank, locate: (await get("locate")) || {} } : null;
    }
    return PACK;
  };
  const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const u = new URL(typeof input === "string" ? input : input.url, location.href);
    if (u.origin !== location.origin || !u.pathname.startsWith("/api/")) return realFetch(input, init);
    const method = (init.method || "GET").toUpperCase(), path = u.pathname;
    const body =() => { try { return JSON.parse(init.body || "{}"); } catch { return {}; } };
    if (method === "GET") {
      if (path === "/api/bank") {
        const p = await pack();
        if (!p) { importScreen(); return new Promise(() => {}); }    // la page attend l'import
        return json(p.bank);
      }
      if (path === "/api/progress") return json((await get("progress")) || {});
      if (path === "/api/sessions") return json({ sessions: (await get("sessions")) || [] });
      if (path === "/api/training") return realFetch("training.json");
      if (path === "/api/locate") {
        const r = (await pack())?.locate?.[u.searchParams.get("id")];
        return r ? json(r) : json({ error: "introuvable" }, 404);
      }
    } else {
      const data = body();
      if (path === "/api/progress") { await serial(() => set("progress", data)); return json({ ok: true }); }
      if (path === "/api/sessions") {
        await serial(async () => {
          const all = ((await get("sessions")) || []).filter(s => s.id !== data.id);
          all.push(data); await set("sessions", all);
        });
        return json({ ok: true });
      }
      if (path === "/api/sessions/clear") { await serial(() => set("sessions", [])); return json({ ok: true }); }
      if (path === "/api/reset") {
        if (data.confirm !== "RÉINITIALISER") return json({ error: "confirmation manquante" }, 400);
        await serial(async () => {
          const prog = (await get("progress")) || {}, sess = (await get("sessions")) || [];
          await set("sauvegarde-avant-reinit", { le: Date.now(), progress: prog, sessions: sess });
          if (data.progress) Object.assign(prog, { questions: {}, history: [], training: {} });
          if (data.notes) prog.notes = {};
          if (data.badClips) prog.badClips = {};
          await set("progress", prog);
          if (data.sessions) await set("sessions", []);
        });
        return json({ ok: true, sauvegardes: ["sauvegarde interne du téléphone"] });
      }
    }
    return json({ error: "indisponible sur mobile" }, 404);
  };
  // fermeture : la page envoie la session abandonnée par sendBeacon
  navigator.sendBeacon = (url, data) => {
    (data instanceof Blob ? data.text() : Promise.resolve(String(data))).then(t => window.fetch(url, { method: "POST", body: t }));
    return true;
  };

  // ---------- médias : chargés en mémoire (blob), pour une avance rapide fiable ----------
  const blobs = new Map();      // chemin → Promise<URL blob>, les 4 derniers
  const blobUrl = path => {
    if (!blobs.has(path)) {
      blobs.set(path, realFetch(path).then(r => { if (!r.ok) throw new Error(r.status); return r.blob(); }).then(b => URL.createObjectURL(b)));
      while (blobs.size > 4) {
        const [old, p] = blobs.entries().next().value;
        blobs.delete(old);
        p.then(url => setTimeout(() => { if (!document.querySelector(`[src="${url}"]`)) URL.revokeObjectURL(url); }, 2000)).catch(() => {});
      }
    }
    return blobs.get(path);
  };
  function fixMedia(el) {
    const src = el.getAttribute("src");
    if (!src || !src.startsWith("/media/")) return;
    const [path, frag] = src.split("#"), t = /t=([\d.]+)/.exec(frag || ""), play = el.autoplay;
    el.removeAttribute("src");
    el.autoplay = false;
    blobUrl(path).then(url => {
      if (t) el.addEventListener("loadedmetadata", () => { el.currentTime = +t[1]; }, { once: true });
      el.src = url;
      if (play) el.play().catch(() => {});
    }).catch(() => el.insertAdjacentHTML("afterend", '<div class="small muted">Média absent de l\'app.</div>'));
  }
  new MutationObserver(muts => {
    for (const m of muts) for (const n of m.addedNodes) {
      if (n.nodeType !== 1) continue;
      if (n.matches("audio, video")) fixMedia(n);
      n.querySelectorAll?.("audio, video").forEach(fixMedia);
    }
  }).observe(document.documentElement, { childList: true, subtree: true });

  // lien « 🎬 Vidéo » (nouvel onglet sur le PC) → lecteur dans l'app
  document.addEventListener("click", e => {
    const a = e.target.closest?.('a[href^="/media/"]');
    if (!a) return;
    e.preventDefault();
    const kind = a.getAttribute("href").startsWith("/media/video/") ? "video" : "audio";
    modal(`<${kind} controls autoplay style="width:100%;border-radius:10px;background:#000" src="${a.getAttribute("href")}"></${kind}>`);
  }, true);

  // téléchargement (export Markdown) → partage ; impression → indisponible
  const click = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    if (this.download && this.href.startsWith("blob:")) {
      realFetch(this.href).then(r => r.text()).then(t => shareText(this.download, t));
      return;
    }
    return click.call(this);
  };
  window.print = () => alert("L'impression n'existe pas dans l'app : utilise « Exporter (Markdown) », puis partage le fichier.");

  // ---------- fenêtres ----------
  function modal(inner) {
    const box = document.createElement("div");
    box.className = "modal";
    box.innerHTML = `<div class="card" role="dialog" aria-modal="true">
      <div class="row spread" style="margin-bottom:10px"><span></span><button class="btn sm" data-close>Fermer</button></div>${inner}</div>`;
    document.body.appendChild(box);
    box.querySelector("[data-close]").onclick = () => { box.querySelectorAll("audio, video").forEach(m => m.pause()); box.remove(); };
    return box;
  }
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const fmtD = ts => ts ? new Date(ts).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" }) : "?";

  // ---------- import d'un paquet préparé sur le PC (preparer.py) ----------
  function pickFile() {
    return new Promise(ok => {
      const inp = document.createElement("input");
      inp.type = "file"; inp.accept = ".json,application/json,text/plain,*/*";
      inp.onchange = () => ok(inp.files[0] || null);
      inp.click();
    });
  }
  async function importPack(status) {
    const f = await pickFile();
    if (!f) return;
    status.textContent = `Lecture de ${f.name}…`;
    let p;
    try { p = JSON.parse(await f.text()); } catch { status.textContent = "Ce fichier n'est pas un JSON valide."; return; }
    if (p?.format !== "dop-c02-mobile" || !Array.isArray(p.bank?.questions)) {
      status.textContent = "Ce n'est pas un paquet de l'app : prépare-le sur le PC avec quiz_app/mobile/preparer.py.";
      return;
    }
    const phoneProg = (await get("progress")) || {}, hasPhone = Object.keys(phoneProg.questions || {}).length > 0;
    let takePc = !!(p.progress || p.sessions);
    if (takePc && hasPhone) {
      takePc = confirm(`Le paquet contient ta progression du PC (${Object.keys(p.progress?.questions || {}).length} questions travaillées, `
        + `${(p.sessions || []).length} sessions).\n\nOK : la reprendre (remplace celle du téléphone)\nAnnuler : garder celle du téléphone`);
    }
    await serial(async () => {
      await set("bank", p.bank);
      await set("locate", p.locate || {});
      await set("paquet", { nom: f.name, cree_le: p.cree_le, importe_le: Date.now(), n: p.bank.questions.length });
      if (takePc) {
        if (p.progress) await set("progress", p.progress);
        if (p.sessions) await set("sessions", p.sessions);
      }
    });
    status.textContent = `${p.bank.questions.length} questions importées ✓`;
    setTimeout(() => location.reload(), 600);
  }
  function importScreen() {
    const app = document.getElementById("app");
    app.innerHTML = `<div class="card"><h2 style="margin-top:0">Bienvenue 👋</h2>
      <p>Les vidéos et les podcasts sont déjà dans l'app. Il reste à importer <b>tes questions</b> :</p>
      <ol class="small"><li>Sur le PC : <code>python quiz_app/mobile/preparer.py "&lt;tes questions&gt;"</code></li>
        <li>Copie <code>dop-c02-paquet.json</code> sur le téléphone (câble USB → Download, ou Google Drive).</li>
        <li>Choisis-le ici.</li></ol>
      <div class="row"><button class="btn primary" id="mImport">Importer un paquet…</button><span class="small muted" id="mStatus"></span></div></div>`;
    app.querySelector("#mImport").onclick = () => importPack(app.querySelector("#mStatus"));
  }

  // ---------- menu 📱 : paquet, import, export de la progression ----------
  async function menu() {
    const info = await get("paquet"), prog = (await get("progress")) || {}, sess = (await get("sessions")) || [];
    const box = modal(`<h2 style="margin-top:0">📱 Données de l'app</h2>
      <p class="small">${info ? `Paquet : <b>${esc(info.nom)}</b> · ${info.n} questions · préparé le ${fmtD(info.cree_le)} · importé le ${fmtD(info.importe_le)}` : "Aucun paquet importé."}</p>
      <p class="small muted">Progression : ${Object.keys(prog.questions || {}).length} questions travaillées · ${sess.length} session(s).</p>
      <div class="grid" style="gap:10px">
        <button class="btn" id="mImport2">Importer un nouveau paquet… <span class="muted small">(questions mises à jour)</span></button>
        <button class="btn primary" id="mExport">Exporter ma progression → PC</button>
        <span class="small muted" id="mStatus2"></span>
        <p class="small muted" style="margin:0">Sur le PC : <code>python quiz_app/mobile/fusionner_progression.py &lt;fichier exporté&gt; "&lt;tes questions&gt;"</code> fusionne les deux progressions.</p>
      </div>`);
    box.querySelector("#mImport2").onclick = () => importPack(box.querySelector("#mStatus2"));
    box.querySelector("#mExport").onclick = async () => {
      const out = { format: "dop-c02-progression", exporte_le: Date.now(), progress: (await get("progress")) || {}, sessions: (await get("sessions")) || [] };
      const d = new Date(), stamp = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}-${String(d.getHours()).padStart(2, "0")}${String(d.getMinutes()).padStart(2, "0")}`;
      shareText(`progression-telephone-${stamp}.json`, JSON.stringify(out));
    };
  }

  // ---------- session : pause automatique quand l'app passe en arrière-plan ----------
  // brouillon « abandonnée » enregistré sans clore la session : si Android ferme l'app, elle reste reprenable
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden || typeof S === "undefined" || !S || S.saved) return;
    if (!S.pausedAt && document.getElementById("stem")) pause();
    const rec = saveSession("abandonnee");
    if (rec) { S.saved = false; SESSIONS.splice(SESSIONS.indexOf(rec), 1); }
  });

  // ---------- bouton retour d'Android (plugin App de Capacitor) ----------
  // fenêtre ouverte → la fermer ; question affichée → pause ; autre écran → accueil ;
  // accueil → deux appuis rapprochés pour sortir (l'app passe en arrière-plan, rien n'est perdu)
  let exitArmed = false;
  function back() {
    const m = document.querySelector(".modal");
    const inSession = typeof S !== "undefined" && S && !S.saved;
    const atHome = document.getElementById("homeBtn")?.hidden;
    if (m) { const c = m.querySelector("[data-close]"); c ? c.click() : m.remove(); }
    else if (inSession && !S.pausedAt && document.getElementById("stem")) pause();
    else if (!atHome) document.getElementById("homeBtn").click();
    else if (exitArmed) native("App", "minimizeApp").catch(() => native("App", "exitApp"));
    else { exitArmed = true; toast("Appuie encore sur retour pour quitter"); setTimeout(() => { exitArmed = false; }, 2500); }
  }
  const App = window.Capacitor?.Plugins?.App;
  if (App?.addListener) App.addListener("backButton", back);
  else console.error("[mobile] plugin App absent : le bouton retour fermera l'app");
  function toast(t) {
    const d = document.createElement("div");
    d.textContent = t;
    d.style.cssText = "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);background:#222;color:#fff;padding:10px 16px;border-radius:20px;font-size:14px;z-index:99;opacity:.92";
    document.body.appendChild(d); setTimeout(() => d.remove(), 2300);
  }

  // ---------- en-tête : bouton 📱, marges des barres système ----------
  document.addEventListener("DOMContentLoaded", () => {
    const row = document.querySelector("header.top .row");
    if (row) {
      const b = document.createElement("button");
      b.className = "btn"; b.textContent = "📱"; b.title = "Paquet, import, export de la progression";
      b.onclick = menu; row.prepend(b);
    }
    const st = document.createElement("style");
    st.textContent = `.wrap { padding-top: max(16px, env(safe-area-inset-top), var(--safe-area-inset-top, 0px));
        padding-bottom: max(64px, calc(env(safe-area-inset-bottom) + 48px)); }
      #pdfExp { display: none; }
      .hint, .kbdhint { display: none; }`;
    document.head.appendChild(st);
  });
})();
