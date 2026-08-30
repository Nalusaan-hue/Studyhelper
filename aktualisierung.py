# -*- coding: utf-8 -*-
"""
Prueft, ob es eine neuere Fassung gibt.

Fragt dazu die Release-Seite des GitHub-Projekts ab. Das kostet nichts,
braucht kein Konto und keine eigene Serverinfrastruktur.

Bewusst NICHT eingebaut: automatisches Herunterladen und Ausfuehren des
Installers. Ein Programm, das sich selbst Dateien aus dem Netz holt und
startet, ist genau das Muster, das Virenscanner zu Recht anspringen -
und ein Einfallstor, falls das Konto je uebernommen wird. Das Programm
sagt Bescheid und oeffnet die Seite; installieren tut der Mensch.
"""

import json
import re
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
#  Hier dein Projekt eintragen
# ---------------------------------------------------------------------------

BENUTZER = "Nalusaan-hue"
PROJEKT = "Studyhelper"

VERSION = "1.0.0"          # die Fassung, die gerade laeuft

ABFRAGE = f"https://api.github.com/repos/{BENUTZER}/{PROJEKT}/releases/latest"
SEITE = f"https://github.com/{BENUTZER}/{PROJEKT}/releases/latest"

ZEITLIMIT = 6              # Sekunden. Lieber aufgeben als das Programm bremsen


def zahlenfolge(text):
    """Macht aus 'v1.2.10' die Zahlenfolge (1, 2, 10) zum Vergleichen."""
    zahlen = re.findall(r"\d+", text or "")
    return tuple(int(z) for z in zahlen[:4]) or (0,)


def ist_neuer(dort, hier):
    """Ist die Fassung 'dort' neuer als 'hier'?"""
    a, b = zahlenfolge(dort), zahlenfolge(hier)
    # Auf gleiche Laenge bringen, damit 1.2 und 1.2.0 gleich sind
    laenge = max(len(a), len(b))
    a = a + (0,) * (laenge - len(a))
    b = b + (0,) * (laenge - len(b))
    return a > b


def pruefen(zeitlimit=ZEITLIMIT):
    """
    Fragt GitHub nach der neuesten Fassung.

    Gibt zurueck:
      {"neu": True/False, "version": "1.1.0", "seite": "https://...",
       "hinweise": "was sich geaendert hat"}
    oder None, wenn die Abfrage nicht geklappt hat. Kein Netz, kein
    Problem - dann passiert einfach nichts.
    """
    anfrage = urllib.request.Request(
        ABFRAGE,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": f"Schulhelfer/{VERSION}"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=zeitlimit) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, OSError):
        return None

    marke = daten.get("tag_name") or daten.get("name") or ""
    if not marke:
        return None

    return {
        "neu": ist_neuer(marke, VERSION),
        "version": marke.lstrip("vV"),
        "seite": daten.get("html_url") or SEITE,
        "hinweise": (daten.get("body") or "").strip()[:400],
    }


if __name__ == "__main__":
    print("Laufende Fassung:", VERSION)
    ergebnis = pruefen()
    if ergebnis is None:
        print("Keine Verbindung oder Projekt nicht gefunden.")
    elif ergebnis["neu"]:
        print("Neuere Fassung:", ergebnis["version"])
        print(ergebnis["seite"])
    else:
        print("Alles aktuell.")
