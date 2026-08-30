# -*- coding: utf-8 -*-
"""
Erzeugt eine eigenstaendige HTML-Datei mit den gesammelten Woertern und der
kompletten Abfrage. Die Datei laeuft ohne Internet, ohne Installation und
ohne API-Schluessel in jedem Handy-Browser.

Wird von schulhelfer.py aufgerufen.
"""

import json


TEXTE_APP = {
    "de": {
        "titel": "Meine Wörter",
        "frage": "Welches Wort wird hier beschrieben?",
        "fortschritt": "Frage {n} von {g}",
        "pruefen": "Prüfen",
        "weiter": "Weiter",
        "weissnicht": "Ich weiss es nicht",
        "richtig": "Richtig!",
        "fast": "Fast – richtig wäre:",
        "falsch": "Richtig wäre:",
        "fertig": "Fertig!",
        "ergebnis": "{r} von {g} richtig",
        "nochmal": "Nochmal üben",
        "schwierig": "Diese Wörter solltest du dir nochmal ansehen:",
        "leer": "Es sind noch keine Wörter da.",
        "tab_ueben": "Üben",
        "tab_liste": "Alle Wörter",
        "suchen": "Suchen …",
        "anzahl": "{n} Wörter",
        "gekonnt": "gekonnt",
    },
    "es": {
        "titel": "Mis palabras",
        "frage": "¿Qué palabra se describe aquí?",
        "fortschritt": "Pregunta {n} de {g}",
        "pruefen": "Comprobar",
        "weiter": "Siguiente",
        "weissnicht": "No lo sé",
        "richtig": "¡Correcto!",
        "fast": "Casi – lo correcto sería:",
        "falsch": "Lo correcto sería:",
        "fertig": "¡Listo!",
        "ergebnis": "{r} de {g} correctas",
        "nochmal": "Practicar otra vez",
        "schwierig": "Repasa estas palabras:",
        "leer": "Todavía no hay palabras.",
        "tab_ueben": "Practicar",
        "tab_liste": "Todas",
        "suchen": "Buscar …",
        "anzahl": "{n} palabras",
        "gekonnt": "aciertos",
    },
    "en": {
        "titel": "My words",
        "frage": "Which word is described here?",
        "fortschritt": "Question {n} of {g}",
        "pruefen": "Check",
        "weiter": "Next",
        "weissnicht": "I don't know",
        "richtig": "Correct!",
        "fast": "Almost – it would be:",
        "falsch": "It would be:",
        "fertig": "Done!",
        "ergebnis": "{r} of {g} correct",
        "nochmal": "Practise again",
        "schwierig": "Look at these words again:",
        "leer": "No words yet.",
        "tab_ueben": "Practise",
        "tab_liste": "All words",
        "suchen": "Search …",
        "anzahl": "{n} words",
        "gekonnt": "correct",
    },
}


VORLAGE = """<!DOCTYPE html>
<html lang="__SPRACHE__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1,
      viewport-fit=cover">
<meta name="theme-color" content="#2b2d33">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>__TITEL__</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0; background: #2b2d33; color: #e9eaee;
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; min-height: 100vh;
    min-height: 100dvh;
  }
  header {
    background: #35373f; padding: 14px 18px;
    padding-top: calc(14px + env(safe-area-inset-top));
    display: flex; align-items: center; gap: 12px;
  }
  header h1 { font-size: 17px; margin: 0; flex: 1; }
  #stand { font-size: 12px; color: #a2a6b0; }
  nav { display: flex; background: #35373f; }
  nav button {
    flex: 1; background: none; border: none; color: #a2a6b0;
    font-size: 14px; padding: 12px; font-family: inherit;
    border-bottom: 2px solid transparent;
  }
  nav button.aktiv { color: #e9eaee; border-bottom-color: #7aa2f7; }
  main { flex: 1; padding: 20px; display: flex; flex-direction: column; }
  .frage { font-size: 13px; color: #a2a6b0; margin-bottom: 10px; }
  .erklaerung {
    font-size: 25px; font-weight: 700; line-height: 1.3;
    margin-bottom: 22px;
  }
  input[type=text] {
    width: 100%; background: #41444e; border: 2px solid #41444e;
    border-radius: 10px; color: #e9eaee; font-size: 19px;
    padding: 14px; text-align: center; font-family: inherit;
  }
  input[type=text]:focus { outline: none; border-color: #7aa2f7; }
  #rueckmeldung {
    margin-top: 18px; font-size: 17px; font-weight: 700; min-height: 26px;
  }
  .gut { color: #9ece6a; }
  .fast { color: #e0af68; }
  .schlecht { color: #f7768e; }
  footer {
    padding: 16px 20px; padding-bottom: calc(16px + env(safe-area-inset-bottom));
    display: flex; gap: 10px; align-items: center;
  }
  button.haupt {
    flex: 1; background: #7aa2f7; color: #1b1e26; border: none;
    border-radius: 10px; padding: 16px; font-size: 17px; font-weight: 700;
    font-family: inherit;
  }
  button.neben {
    background: #41444e; color: #e9eaee; border: none; border-radius: 10px;
    padding: 16px; font-size: 14px; font-family: inherit;
  }
  button:active { opacity: .75; }
  #suchfeld {
    width: 100%; background: #41444e; border: none; border-radius: 10px;
    color: #e9eaee; font-size: 16px; padding: 12px; font-family: inherit;
    margin-bottom: 14px;
  }
  .eintrag {
    padding: 12px 0; border-bottom: 1px solid #41444e;
    display: flex; gap: 12px; align-items: baseline;
  }
  .eintrag b { color: #7aa2f7; font-size: 17px; }
  .eintrag span { flex: 1; font-size: 15px; }
  .eintrag em { font-style: normal; color: #a2a6b0; font-size: 12px; }
  .verborgen { display: none !important; }
</style>
</head>
<body>

<header>
  <h1>__TITEL__</h1>
  <div id="stand"></div>
</header>

<nav>
  <button id="tabUeben" class="aktiv">__TAB_UEBEN__</button>
  <button id="tabListe">__TAB_LISTE__</button>
</nav>

<main id="ueben">
  <div class="frage" id="frageText">__FRAGE__</div>
  <div class="erklaerung" id="erklaerung"></div>
  <input type="text" id="eingabe" autocomplete="off" autocapitalize="off"
         autocorrect="off" spellcheck="false">
  <div id="rueckmeldung"></div>
</main>

<main id="liste" class="verborgen">
  <input type="text" id="suchfeld" placeholder="__SUCHEN__">
  <div id="eintraege"></div>
</main>

<footer id="fussUeben">
  <button class="neben" id="weissnicht">__WEISSNICHT__</button>
  <button class="haupt" id="hauptknopf">__PRUEFEN__</button>
</footer>

<script>
const WOERTER = __DATEN__;
const T = __TEXTE__;

// Statistik im Browser merken, damit schwierige Woerter oefter drankommen
let stat = {};
try { stat = JSON.parse(localStorage.getItem("schulhelfer_stat") || "{}"); }
catch (e) { stat = {}; }
function statSichern() {
  try { localStorage.setItem("schulhelfer_stat", JSON.stringify(stat)); }
  catch (e) {}
}
function werte(wort) {
  return stat[wort] || { richtig: 0, falsch: 0 };
}

function vereinfachen(text) {
  text = (text || "").toLowerCase().trim();
  text = text.replace(/[.,;:!?()\\[\\]{}"']/g, "");
  const artikel = ["der ", "die ", "das ", "ein ", "eine ", "el ", "la ",
                   "los ", "las ", "un ", "una ", "the ", "a ", "an ",
                   "le ", "les ", "il ", "lo "];
  for (const w of artikel) {
    if (text.startsWith(w)) { text = text.slice(w.length); break; }
  }
  return text.replace(/\\s+/g, " ").trim();
}

function abstand(a, b) {
  if (a.length < b.length) { const h = a; a = b; b = h; }
  let vorher = Array.from({length: b.length + 1}, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const jetzt = [i];
    for (let j = 1; j <= b.length; j++) {
      jetzt.push(Math.min(vorher[j] + 1, jetzt[j - 1] + 1,
                          vorher[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)));
    }
    vorher = jetzt;
  }
  return vorher[b.length];
}

function pruefen(eingabe, richtig) {
  const a = vereinfachen(eingabe), b = vereinfachen(richtig);
  if (!a) return "falsch";
  if (a === b) return "richtig";
  if (b.length >= 5 && abstand(a, b) <= 1) return "fast";
  return "falsch";
}

function auswaehlen(anzahl) {
  if (!WOERTER.length) return [];
  const topf = [];
  for (const e of WOERTER) {
    const w = werte(e.wort);
    let gewicht = 1 + w.falsch * 3;
    if (w.richtig >= 2 && w.falsch === 0) gewicht = 1;
    for (let i = 0; i < gewicht; i++) topf.push(e);
  }
  const raus = [], gesehen = new Set();
  let versuche = 0;
  while (raus.length < Math.min(anzahl, WOERTER.length) && versuche < 500) {
    versuche++;
    const k = topf[Math.floor(Math.random() * topf.length)];
    if (!gesehen.has(k.wort)) { gesehen.add(k.wort); raus.push(k); }
  }
  return raus.sort(() => Math.random() - 0.5);
}

let runde = [], nummer = 0, punkte = 0, schwierige = [], beantwortet = false;

const $ = id => document.getElementById(id);

function starten() {
  runde = auswaehlen(10);
  nummer = 0; punkte = 0; schwierige = []; beantwortet = false;
  $("frageText").classList.remove("verborgen");
  $("eingabe").classList.remove("verborgen");
  $("weissnicht").classList.remove("verborgen");
  $("weissnicht").textContent = T.weissnicht;
  $("hauptknopf").textContent = T.pruefen;
  if (!runde.length) {
    $("erklaerung").textContent = T.leer;
    $("erklaerung").style.fontSize = "17px";
    $("frageText").classList.add("verborgen");
    $("eingabe").classList.add("verborgen");
    $("weissnicht").classList.add("verborgen");
    $("hauptknopf").classList.add("verborgen");
    $("stand").textContent = "";
    return;
  }
  frageZeigen();
}

function frageZeigen() {
  const e = runde[nummer];
  beantwortet = false;
  $("stand").textContent = T.fortschritt.replace("{n}", nummer + 1)
                                        .replace("{g}", runde.length);
  $("erklaerung").textContent = e.erklaerung;
  $("erklaerung").style.fontSize = "25px";
  $("eingabe").value = "";
  $("eingabe").disabled = false;
  $("rueckmeldung").textContent = "";
  $("hauptknopf").textContent = T.pruefen;
  $("weissnicht").disabled = false;
  $("eingabe").focus();
}

function antworten(eingabe) {
  const e = runde[nummer];
  const urteil = pruefen(eingabe, e.wort);
  const r = $("rueckmeldung");
  const w = werte(e.wort);

  if (urteil === "richtig") {
    r.textContent = T.richtig; r.className = "gut";
    punkte++; w.richtig++;
  } else if (urteil === "fast") {
    r.textContent = T.fast + " " + e.wort; r.className = "fast";
    punkte++; w.richtig++;
  } else {
    r.textContent = T.falsch + " " + e.wort; r.className = "schlecht";
    schwierige.push(e.wort); w.falsch++;
  }
  stat[e.wort] = w;
  statSichern();

  beantwortet = true;
  $("eingabe").disabled = true;
  $("weissnicht").disabled = true;
  $("hauptknopf").textContent = T.weiter;
}

function weiter() {
  if (!runde.length) return;
  if (!beantwortet) { antworten($("eingabe").value); return; }
  nummer++;
  if (nummer >= runde.length) abschluss(); else frageZeigen();
}

function abschluss() {
  $("stand").textContent = T.fertig;
  let text = T.ergebnis.replace("{r}", punkte).replace("{g}", runde.length);
  if (schwierige.length) {
    text += "\\n\\n" + T.schwierig + "\\n" + schwierige.join(", ");
  }
  $("erklaerung").textContent = text;
  $("erklaerung").style.fontSize = "17px";
  $("erklaerung").style.whiteSpace = "pre-line";
  $("frageText").classList.add("verborgen");
  $("eingabe").classList.add("verborgen");
  $("weissnicht").classList.add("verborgen");
  $("rueckmeldung").textContent = "";
  $("hauptknopf").textContent = T.nochmal;
}

function listeZeichnen() {
  const suche = vereinfachen($("suchfeld").value);
  const ziel = $("eintraege");
  ziel.innerHTML = "";
  const sichtbar = WOERTER.filter(e =>
    !suche || vereinfachen(e.wort).includes(suche)
           || vereinfachen(e.erklaerung).includes(suche));
  for (const e of sichtbar) {
    const w = werte(e.wort);
    const zeile = document.createElement("div");
    zeile.className = "eintrag";
    const gesamt = w.richtig + w.falsch;
    zeile.innerHTML =
      "<b></b><span></span><em></em>";
    zeile.querySelector("b").textContent = e.wort;
    zeile.querySelector("span").textContent = e.erklaerung;
    zeile.querySelector("em").textContent =
      gesamt ? w.richtig + "/" + gesamt : "";
    ziel.appendChild(zeile);
  }
  $("stand").textContent = T.anzahl.replace("{n}", sichtbar.length);
}

$("hauptknopf").addEventListener("click", () => {
  if ($("hauptknopf").textContent === T.nochmal) starten(); else weiter();
});
$("weissnicht").addEventListener("click", () => {
  if (!beantwortet) antworten("");
});
$("eingabe").addEventListener("keydown", ev => {
  if (ev.key === "Enter") { ev.preventDefault(); weiter(); }
});
$("suchfeld").addEventListener("input", listeZeichnen);

$("tabUeben").addEventListener("click", () => {
  $("tabUeben").classList.add("aktiv");
  $("tabListe").classList.remove("aktiv");
  $("ueben").classList.remove("verborgen");
  $("liste").classList.add("verborgen");
  $("fussUeben").classList.remove("verborgen");
  starten();
});
$("tabListe").addEventListener("click", () => {
  $("tabListe").classList.add("aktiv");
  $("tabUeben").classList.remove("aktiv");
  $("liste").classList.remove("verborgen");
  $("ueben").classList.add("verborgen");
  $("fussUeben").classList.add("verborgen");
  listeZeichnen();
});

starten();
</script>
</body>
</html>
"""


def lern_app_bauen(woerter, sprache="de"):
    """Baut die fertige HTML-Seite als Text."""
    texte = TEXTE_APP.get(sprache, TEXTE_APP["de"])
    schlank = [{"wort": e["wort"], "erklaerung": e["erklaerung"]}
               for e in woerter]

    seite = VORLAGE
    for platzhalter, wert in [
        ("__SPRACHE__", sprache),
        ("__TITEL__", texte["titel"]),
        ("__FRAGE__", texte["frage"]),
        ("__PRUEFEN__", texte["pruefen"]),
        ("__WEISSNICHT__", texte["weissnicht"]),
        ("__TAB_UEBEN__", texte["tab_ueben"]),
        ("__TAB_LISTE__", texte["tab_liste"]),
        ("__SUCHEN__", texte["suchen"]),
    ]:
        seite = seite.replace(platzhalter, wert)

    seite = seite.replace("__DATEN__",
                          json.dumps(schlank, ensure_ascii=False))
    seite = seite.replace("__TEXTE__", json.dumps(texte, ensure_ascii=False))
    return seite
