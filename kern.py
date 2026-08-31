# -*- coding: utf-8 -*-
"""
Schulhelfer - Kern
==================
Alles, was nichts mit der Oberflaeche zu tun hat: Einstellungen,
verschluesselte Schluesselablage, Screenshots, Anfragen an Gemini,
Woerterliste, Abfragelogik, Tastenkuerzel und Aktualisierung.

Diese Datei kennt keine Oberflaeche. Sie schiebt Meldungen in die
Warteschlange 'ui' - wer sie anzeigt, ist ihr egal. Dadurch liess sich
die Oberflaeche von Tkinter auf Flet umstellen, ohne hier etwas zu
aendern.
"""

import base64
import ctypes
import io
import json
import math
import os
import queue
import random
import threading
import time
from ctypes import wintypes
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageGrab
from google import genai

import aktualisierung


# ===========================================================================
#  Ablageort und Protokoll
# ===========================================================================

ORDNER = Path(os.environ.get("APPDATA", Path.home())) / "Schulhelfer"
ORDNER.mkdir(parents=True, exist_ok=True)
KONFIG_DATEI = ORDNER / "konfig.json"
PROTOKOLL = ORDNER / "protokoll.txt"
WOERTER_DATEI = ORDNER / "woerter.json"


def log(text):
    """Schreibt ins Protokoll. Als EXE gibt es keine Konsole, darum die Datei."""
    zeile = f"{time.strftime('%H:%M:%S')}  {text}"
    try:
        with open(PROTOKOLL, "a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:
        pass
    try:
        print(zeile)
    except Exception:
        pass


# ===========================================================================
#  Nur einmal gleichzeitig laufen lassen
# ===========================================================================

SPERRE_NAME = "Local\\Schulhelfer_Einzelinstanz"
WECKER_NAME = "Local\\Schulhelfer_Fenster_zeigen"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WARTE_OK = 0x0

sperre_griff = None
wecker_griff = None


def schon_gestartet():
    """
    Legt eine benannte Windows-Sperre an. Existiert sie schon, laeuft das
    Programm bereits - dann wecken wir das laufende Fenster und beenden uns.
    Gibt True zurueck, wenn dieser Start abgebrochen werden soll.
    """
    global sperre_griff, wecker_griff
    try:
        kernel32 = ctypes.windll.kernel32
        sperre_griff = kernel32.CreateMutexW(None, False, SPERRE_NAME)
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            # Laeuft schon: dem laufenden Programm sagen, es soll sich zeigen
            wecker = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, WECKER_NAME)
            if wecker:
                kernel32.SetEvent(wecker)
                kernel32.CloseHandle(wecker)
            log("Laeuft bereits - hole das vorhandene Fenster nach vorn")
            return True

        # Wir sind der erste: Wecker anlegen, auf den spaetere Starts klopfen
        wecker_griff = kernel32.CreateEventW(None, False, False, WECKER_NAME)
        return False
    except Exception as fehler:
        log(f"Einzelinstanz-Sperre nicht moeglich: {fehler}")
        return False


def auf_wecker_horchen():
    """Wartet darauf, dass ein zweiter Start das Fenster nach vorn holen will."""
    if not wecker_griff:
        return
    kernel32 = ctypes.windll.kernel32
    while not beenden.is_set():
        # 500 ms warten, damit die Schleife das Programmende mitbekommt
        if kernel32.WaitForSingleObject(wecker_griff, 500) == WARTE_OK:
            ui.put(("zeigen", None))


# ===========================================================================
#  Schluessel verschluesselt ablegen (Windows DPAPI)
# ===========================================================================

class DATENBLOCK(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blockinhalt(block):
    inhalt = ctypes.string_at(block.pbData, block.cbData)
    ctypes.windll.kernel32.LocalFree(block.pbData)
    return inhalt


def schluessel_schuetzen(klartext):
    """Verschluesselt mit dem Windows-Benutzerkonto. Gibt base64 zurueck."""
    try:
        roh = klartext.encode("utf-8")
        rein = DATENBLOCK(len(roh), ctypes.cast(
            ctypes.create_string_buffer(roh), ctypes.POINTER(ctypes.c_char)))
        raus = DATENBLOCK()
        erfolg = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(rein), "Schulhelfer", None, None, None, 0,
            ctypes.byref(raus))
        if not erfolg:
            raise OSError("CryptProtectData fehlgeschlagen")
        return base64.b64encode(_blockinhalt(raus)).decode("ascii")
    except Exception as fehler:
        log(f"Verschluesselung nicht moeglich ({fehler}) - Ablage unverschluesselt")
        return "KLARTEXT:" + klartext


def schluessel_lesen(gespeichert):
    """Gegenstueck zu schluessel_schuetzen."""
    if not gespeichert:
        return ""
    if gespeichert.startswith("KLARTEXT:"):
        return gespeichert[9:]
    try:
        roh = base64.b64decode(gespeichert)
        rein = DATENBLOCK(len(roh), ctypes.cast(
            ctypes.create_string_buffer(roh), ctypes.POINTER(ctypes.c_char)))
        raus = DATENBLOCK()
        erfolg = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(rein), None, None, None, None, 0, ctypes.byref(raus))
        if not erfolg:
            raise OSError("CryptUnprotectData fehlgeschlagen")
        return _blockinhalt(raus).decode("utf-8")
    except Exception as fehler:
        log(f"Schluessel konnte nicht entschluesselt werden: {fehler}")
        return ""


# ===========================================================================
#  Einstellungen
# ===========================================================================

STANDARD = {
    "schluessel": "",
    "sprache": "de",
    "antwortsprache": "Deutsch",
    "modelle": [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.7-flash",
    ],
    "hotkey_erklaeren": "ctrl+alt+q",
    "nur_aktiver_bildschirm": True,
    "schriftgroesse": 11,
    "farbschema": "grau",
    "sprache_gewaehlt": False,
    "hinweis_gelesen": False,
    "update_geprueft": "",
    "max_breite": 1600,
    "zaehler_datum": "",
    "zaehler_stand": 0,
}

konfig = dict(STANDARD)


def konfig_laden():
    global konfig
    konfig = dict(STANDARD)
    if KONFIG_DATEI.exists():
        try:
            konfig.update(json.loads(KONFIG_DATEI.read_text(encoding="utf-8")))
        except Exception as fehler:
            log(f"Konfiguration unlesbar, nehme Standardwerte: {fehler}")
    # Zaehler taeglich zuruecksetzen
    if konfig.get("zaehler_datum") != date.today().isoformat():
        konfig["zaehler_datum"] = date.today().isoformat()
        konfig["zaehler_stand"] = 0


def konfig_speichern():
    try:
        KONFIG_DATEI.write_text(
            json.dumps(konfig, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as fehler:
        log(f"Konfiguration konnte nicht gespeichert werden: {fehler}")


# ===========================================================================
#  Woerterliste
# ===========================================================================

WOERTER_MARKE = "###WOERTER###"


def woerter_laden():
    if not WOERTER_DATEI.exists():
        return []
    try:
        return json.loads(WOERTER_DATEI.read_text(encoding="utf-8"))
    except Exception as fehler:
        log(f"Woerterliste unlesbar: {fehler}")
        return []


def woerter_speichern(liste):
    try:
        WOERTER_DATEI.write_text(
            json.dumps(liste, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as fehler:
        log(f"Woerterliste nicht speicherbar: {fehler}")


def woerter_abtrennen(antwort):
    """
    Schneidet den Woerter-Block vom Ende der Antwort ab.
    Gibt (Antwort ohne Block, Liste aus (Wort, Erklaerung)) zurueck.
    """
    if WOERTER_MARKE not in antwort:
        return antwort, []

    text, _, block = antwort.partition(WOERTER_MARKE)
    gefunden = []
    for zeile in block.splitlines():
        zeile = zeile.strip().lstrip("-•* ").strip()
        if "|" not in zeile:
            continue
        wort, _, erklaerung = zeile.partition("|")
        wort, erklaerung = wort.strip(), erklaerung.strip()
        if wort and erklaerung and len(wort) < 60:
            gefunden.append((wort, erklaerung))
    return text.rstrip(), gefunden


def vereinfachen(text):
    """Macht zwei Antworten vergleichbar: klein, ohne Artikel, ohne Zeichen."""
    text = text.strip().lower()
    for zeichen in ".,;:!?()[]{}\"'":
        text = text.replace(zeichen, "")
    artikel = ("der ", "die ", "das ", "ein ", "eine ", "el ", "la ", "los ",
               "las ", "un ", "una ", "the ", "a ", "an ", "le ", "les ",
               "il ", "lo ")
    for wort in artikel:
        if text.startswith(wort):
            text = text[len(wort):]
            break
    return " ".join(text.split())


def abstand(a, b):
    """Wie viele Buchstaben muesste man aendern? (Levenshtein)"""
    if len(a) < len(b):
        a, b = b, a
    vorherige = list(range(len(b) + 1))
    for i, zeichen_a in enumerate(a, 1):
        aktuelle = [i]
        for j, zeichen_b in enumerate(b, 1):
            aktuelle.append(min(vorherige[j] + 1,
                                aktuelle[j - 1] + 1,
                                vorherige[j - 1] + (zeichen_a != zeichen_b)))
        vorherige = aktuelle
    return vorherige[-1]


def antwort_pruefen(eingabe, richtig):
    """Gibt 'richtig', 'fast' oder 'falsch' zurueck."""
    a, b = vereinfachen(eingabe), vereinfachen(richtig)
    if not a:
        return "falsch"
    if a == b:
        return "richtig"
    # Bei laengeren Woertern einen Tippfehler durchgehen lassen
    if len(b) >= 5 and abstand(a, b) <= 1:
        return "fast"
    return "falsch"


def abfrage_auswaehlen(liste, anzahl=10):
    """
    Waehlt Woerter fuer eine Abfragerunde. Woerter, bei denen man sich schon
    geirrt hat, kommen haeufiger dran - richtig beantwortete seltener.
    """
    if not liste:
        return []
    gewichtet = []
    for eintrag in liste:
        falsch = eintrag.get("falsch", 0)
        richtig = eintrag.get("richtig", 0)
        gewicht = 1 + falsch * 3
        if richtig >= 2 and falsch == 0:
            gewicht = 1          # gut gekonnt, aber nie ganz ausschliessen
        gewichtet += [eintrag] * max(1, gewicht)

    ausgewaehlt, gesehen = [], set()
    versuche = 0
    while len(ausgewaehlt) < min(anzahl, len(liste)) and versuche < 500:
        versuche += 1
        kandidat = random.choice(gewichtet)
        if kandidat["wort"] not in gesehen:
            gesehen.add(kandidat["wort"])
            ausgewaehlt.append(kandidat)
    random.shuffle(ausgewaehlt)
    return ausgewaehlt


def ergebnis_merken(wort, war_richtig):
    """Zaehlt mit, wie oft ein Wort gekonnt wurde."""
    liste = woerter_laden()
    for eintrag in liste:
        if eintrag["wort"] == wort:
            schluessel = "richtig" if war_richtig else "falsch"
            eintrag[schluessel] = eintrag.get(schluessel, 0) + 1
            break
    woerter_speichern(liste)


def woerter_ergaenzen(neue):
    """Haengt neue Woerter an die Liste an, ohne Doppelte. Gibt Anzahl zurueck."""
    if not neue:
        return 0
    liste = woerter_laden()
    vorhanden = {eintrag["wort"].lower() for eintrag in liste}
    heute = date.today().isoformat()
    dazu = 0
    for wort, erklaerung in neue:
        if wort.lower() in vorhanden:
            continue
        liste.append({"wort": wort, "erklaerung": erklaerung, "datum": heute})
        vorhanden.add(wort.lower())
        dazu += 1
    if dazu:
        woerter_speichern(liste)
        log(f"{dazu} neue Woerter gespeichert")
    return dazu


# ===========================================================================
#  Texte in drei Sprachen
# ===========================================================================

TEXTE = {
    "de": {
        "sprachname": "Deutsch",
        "titel": "Schulhelfer",
        "menue_fenster": "Fenster zeigen",
        "menue_einstellungen": "Einstellungen",
        "menue_beenden": "Beenden",
        "weg_titel": "Schulhelfer läuft weiter",
        "weg_text": "Das Fenster ist zu, das Programm wartet unten rechts im Infobereich. Zum Beenden dort Rechtsklick auf das Symbol.",
        "btn_erklaeren": "Erklären",
        "btn_einstellungen": "Einstellungen",
        "lade_erklaeren": "Bildschirm wird gelesen …",
        "platzhalter": "Etwas nicht verstanden? Hier nachfragen …",
        "btn_senden": "Fragen",
        "btn_einfacher": "Noch einfacher",
        "btn_beispiel": "Beispiel geben",
        "btn_wortfuerwort": "Wort für Wort",
        "btn_wastun": "Was soll ich tun?",
        "btn_woerter": "Wörter",
        "menue_woerter": "Meine Wörterliste",
        "woerter_titel": "Meine Wörterliste",
        "woerter_leer": "Noch keine Wörter gesammelt.\n\nJedes Mal, wenn du «Erklären» benutzt, kommen die schwierigen Wörter automatisch hierher.",
        "woerter_anzahl": "{anzahl} Wörter gesammelt",
        "woerter_speichern": "Als Textdatei speichern",
        "woerter_handy": "Für das Handy",
        "handy_fertig": "Datei erstellt: {pfad}\nSchick sie dir aufs Handy und öffne sie dort.",
        "woerter_leeren": "Liste leeren",
        "woerter_gespeichert": "Gespeichert: {pfad}",
        "woerter_sicher": "Wirklich alle {anzahl} Wörter löschen?",
        "woerter_ueberschrift": "Schwierige Wörter",
        "woerter_suche": "Suchen …",
        "woerter_spalte_wort": "Wort",
        "woerter_spalte_erklaerung": "Erklärung",
        "woerter_spalte_datum": "Datum",
        "woerter_treffer": "{anzahl} von {gesamt}",
        "abfrage_start": "Abfragen",
        "abfrage_titel": "Wörter üben",
        "abfrage_frage": "Welches Wort wird hier beschrieben?",
        "abfrage_fortschritt": "Frage {nummer} von {gesamt}",
        "abfrage_pruefen": "Prüfen",
        "abfrage_weiter": "Weiter",
        "abfrage_weissnicht": "Ich weiss es nicht",
        "abfrage_richtig": "Richtig!",
        "abfrage_fast": "Fast – richtig wäre: {wort}",
        "abfrage_falsch": "Richtig wäre: {wort}",
        "abfrage_ende": "Fertig!",
        "abfrage_ergebnis": "{richtig} von {gesamt} richtig",
        "abfrage_nochmal": "Nochmal üben",
        "abfrage_schliessen": "Schliessen",
        "abfrage_zuwenig": "Sammle zuerst ein paar Wörter, dann kannst du üben.",
        "abfrage_schwierig": "Diese Wörter solltest du dir nochmal ansehen:",
        "woerter_spalte_gekonnt": "Gekonnt",
        "woerter_neu": "{anzahl} neue Wörter in deiner Liste",
        "ein_schriftgroesse": "Schriftgrösse",
        "ein_farbschema": "Farben",
        "will_titel": "So geht es",
        "will_schritte": [
            ("1", "Du siehst einen Text. Du verstehst ihn nicht."),
            ("2", "Du drückst {taste}."),
            ("3", "Ich lese deinen Bildschirm und erkläre ihn dir."),
            ("4", "Schwere Wörter kommen in deine Liste. Die kannst du üben."),
        ],
        "will_los": "Los geht's",
        "will_taste": "Merk dir diese Tasten:",
        "ds_titel": "Bevor du anfängst",
        "ds_kurz": "Dieses Programm schickt ein Bild deines Bildschirms an Google.",
        "ds_punkte": [
            ("Was passiert",
             "Wenn du das Tastenkürzel drückst, wird der Bildschirm "
             "fotografiert und das Bild an Google geschickt. Von dort kommt "
             "die Erklärung zurück. Ohne Internet geht das nicht."),
            ("Es geht der ganze Bildschirm mit",
             "Nicht nur die Stelle, die du erklärt haben willst. Was sonst "
             "noch offen ist, geht mit: Nachrichten, E-Mails, Namen. Schliess "
             "vorher, was niemanden angeht."),
            ("Google lernt daraus",
             "Beim kostenlosen Zugang verwendet Google deine Bilder, um seine "
             "Programme zu verbessern. Menschen können sie dabei zu sehen "
             "bekommen. Nur beim bezahlten Zugang ist das nicht so."),
            ("Was auf deinem Rechner bleibt",
             "Dein Schlüssel und deine Wörterliste bleiben hier, verschlüsselt "
             "in deinem Benutzerkonto. Sie werden nirgends hochgeladen."),
            ("Die Antworten können falsch sein",
             "Das Programm hilft beim Verstehen. Bei Zahlen, Fristen und "
             "Regeln schau in der ursprünglichen Quelle nach."),
        ],
        "ds_regel": "Kurz gesagt: Nichts fotografieren, was privat ist oder anderen Leuten gehört.",
        "ds_verstanden": "Verstanden",
        "ds_abbrechen": "Abbrechen",
        "menue_hinweis": "Datenschutz-Hinweis",
        "menue_update": "Auf Updates prüfen",
        "update_da": "Neue Fassung {version} verfügbar",
        "update_holen": "Herunterladen",
        "update_spaeter": "Später",
        "update_aktuell": "Du hast die neueste Fassung ({version}).",
        "update_kein_netz": "Konnte nicht nachschauen. Kein Internet?",
        "farbe_grau": "Dunkelgrau",
        "farbe_dunkel": "Dunkel",
        "farbe_hell": "Hell",
        "status": "{modell}  ·  {sprache}  ·  {anzahl} Anfragen heute",
        "bereit": "Bereit. Drück {taste1}, dann erkläre ich dir, was auf dem Bildschirm steht.",
        "erst_screenshot": "Mach zuerst einen Screenshot.",
        "du": "Du",
        "ein_titel": "Einstellungen",
        "ein_schluessel": "Gemini API-Schlüssel",
        "ein_schluessel_hinweis": (
            "Der Schlüssel wird verschlüsselt in deinem Windows-Profil "
            "gespeichert und verlässt deinen Rechner nicht."),
        "ein_noch_keiner": "Noch keinen Schlüssel? So bekommst du einen — gratis, in 2 Minuten:",
        "ein_schritt1": "1.  Auf den Knopf unten klicken. Der Browser öffnet die Google-Seite.",
        "ein_schritt2": "2.  Mit einem Google-Konto anmelden und auf «API-Schlüssel erstellen» klicken.",
        "ein_schritt3": "3.  Den Schlüssel kopieren, hierher zurückkommen und «Einfügen» drücken.",
        "ein_seite_oeffnen": "Seite öffnen",
        "ein_einfuegen": "Einfügen",
        "ein_testen": "Schlüssel testen",
        "ein_test_laeuft": "Wird geprüft …",
        "ein_test_ok": "Funktioniert. Antwort kam von {modell}.",
        "ein_test_leer": "Erst einen Schlüssel eintragen.",
        "ein_test_fehler": "Klappt nicht: {grund}",
        "ein_format": "Sieht ungewöhnlich aus — Gemini-Schlüssel beginnen meist mit AIza.",
        "ein_zeigen": "Anzeigen",
        "ein_sprache": "Sprache des Programms",
        "ein_antwortsprache": "Sprache der Antworten",
        "ein_hotkey1": "Tastenkürzel Erklären",
        "ein_bildschirm": "Nur den Bildschirm mit dem Mauszeiger fotografieren",
        "ein_modelle": "Modelle (eines pro Zeile, wird der Reihe nach probiert)",
        "ein_speichern": "Speichern",
        "ein_abbrechen": "Abbrechen",
        "ein_fehlt": "Ohne API-Schlüssel funktioniert das Programm nicht.",
        "fehler_limit": ("Alle Modelle sind heute am Limit.\n\nBei PerMinute "
                         "reicht kurz warten, bei PerDay ist es bis morgen.\n\n"),
        "fehler_key": ("Der API-Schlüssel wird nicht akzeptiert. Trag ihn in "
                       "den Einstellungen neu ein."),
        "fehler_modell": "Ein Modellname stimmt nicht:\n\n",
        "fehler_allgemein": "Fehler:\n\n",
    },
    "es": {
        "sprachname": "Español",
        "titel": "Asistente",
        "menue_fenster": "Mostrar ventana",
        "menue_einstellungen": "Ajustes",
        "menue_beenden": "Salir",
        "weg_titel": "El asistente sigue activo",
        "weg_text": "La ventana está cerrada, el programa espera abajo a la derecha. Para salir, clic derecho en el icono.",
        "btn_erklaeren": "Explicar",
        "btn_einstellungen": "Ajustes",
        "lade_erklaeren": "Leyendo la pantalla …",
        "platzhalter": "¿Algo no queda claro? Pregunta aquí …",
        "btn_senden": "Preguntar",
        "btn_einfacher": "Aún más fácil",
        "btn_beispiel": "Dame un ejemplo",
        "btn_wortfuerwort": "Palabra por palabra",
        "btn_wastun": "¿Qué tengo que hacer?",
        "btn_woerter": "Palabras",
        "menue_woerter": "Mi lista de palabras",
        "woerter_titel": "Mi lista de palabras",
        "woerter_leer": "Todavía no hay palabras.\n\nCada vez que uses «Explicar», las palabras difíciles vendrán aquí automáticamente.",
        "woerter_anzahl": "{anzahl} palabras guardadas",
        "woerter_speichern": "Guardar como texto",
        "woerter_handy": "Para el móvil",
        "handy_fertig": "Archivo creado: {pfad}\nEnvíatelo al móvil y ábrelo allí.",
        "woerter_leeren": "Vaciar lista",
        "woerter_gespeichert": "Guardado: {pfad}",
        "woerter_sicher": "¿Borrar de verdad las {anzahl} palabras?",
        "woerter_ueberschrift": "Palabras difíciles",
        "woerter_suche": "Buscar …",
        "woerter_spalte_wort": "Palabra",
        "woerter_spalte_erklaerung": "Explicación",
        "woerter_spalte_datum": "Fecha",
        "woerter_treffer": "{anzahl} de {gesamt}",
        "abfrage_start": "Practicar",
        "abfrage_titel": "Practicar palabras",
        "abfrage_frage": "¿Qué palabra se describe aquí?",
        "abfrage_fortschritt": "Pregunta {nummer} de {gesamt}",
        "abfrage_pruefen": "Comprobar",
        "abfrage_weiter": "Siguiente",
        "abfrage_weissnicht": "No lo sé",
        "abfrage_richtig": "¡Correcto!",
        "abfrage_fast": "Casi – lo correcto sería: {wort}",
        "abfrage_falsch": "Lo correcto sería: {wort}",
        "abfrage_ende": "¡Listo!",
        "abfrage_ergebnis": "{richtig} de {gesamt} correctas",
        "abfrage_nochmal": "Practicar otra vez",
        "abfrage_schliessen": "Cerrar",
        "abfrage_zuwenig": "Primero reúne algunas palabras y luego podrás practicar.",
        "abfrage_schwierig": "Repasa estas palabras:",
        "woerter_spalte_gekonnt": "Aciertos",
        "woerter_neu": "{anzahl} palabras nuevas en tu lista",
        "ein_schriftgroesse": "Tamaño de letra",
        "ein_farbschema": "Colores",
        "will_titel": "Así funciona",
        "will_schritte": [
            ("1", "Ves un texto. No lo entiendes."),
            ("2", "Pulsas {taste}."),
            ("3", "Leo tu pantalla y te lo explico."),
            ("4", "Las palabras difíciles van a tu lista. Puedes practicarlas."),
        ],
        "will_los": "Empezar",
        "will_taste": "Recuerda estas teclas:",
        "ds_titel": "Antes de empezar",
        "ds_kurz": "Este programa envía una imagen de tu pantalla a Google.",
        "ds_punkte": [
            ("Qué ocurre",
             "Al pulsar el atajo se hace una captura de la pantalla y se "
             "envía a Google. Desde allí llega la explicación. Sin internet "
             "no funciona."),
            ("Se envía la pantalla entera",
             "No solo la parte que quieres entender. Todo lo que esté "
             "abierto va también: mensajes, correos, nombres. Cierra antes "
             "lo que no le importe a nadie."),
            ("Google aprende de ello",
             "Con el acceso gratuito, Google usa tus imágenes para mejorar "
             "sus programas, y personas pueden verlas. Solo el acceso de "
             "pago lo evita."),
            ("Qué se queda en tu ordenador",
             "Tu clave y tu lista de palabras se quedan aquí, cifradas en tu "
             "cuenta de usuario. No se suben a ningún sitio."),
            ("Las respuestas pueden estar mal",
             "El programa ayuda a entender. Para cifras, plazos y normas, "
             "comprueba la fuente original."),
        ],
        "ds_regel": "En resumen: no captures nada privado ni que pertenezca a otras personas.",
        "ds_verstanden": "Entendido",
        "ds_abbrechen": "Cancelar",
        "menue_hinweis": "Aviso de privacidad",
        "menue_update": "Buscar actualizaciones",
        "update_da": "Nueva versión {version} disponible",
        "update_holen": "Descargar",
        "update_spaeter": "Más tarde",
        "update_aktuell": "Tienes la última versión ({version}).",
        "update_kein_netz": "No se pudo comprobar. ¿Sin internet?",
        "farbe_grau": "Gris oscuro",
        "farbe_dunkel": "Oscuro",
        "farbe_hell": "Claro",
        "status": "{modell}  ·  {sprache}  ·  {anzahl} consultas hoy",
        "bereit": "Listo. Pulsa {taste1} y te explico lo que hay en la pantalla.",
        "erst_screenshot": "Primero haz una captura de pantalla.",
        "du": "Tú",
        "ein_titel": "Ajustes",
        "ein_schluessel": "Clave de API de Gemini",
        "ein_schluessel_hinweis": (
            "La clave se guarda cifrada en tu perfil de Windows y no sale "
            "de tu ordenador."),
        "ein_noch_keiner": "¿Aún no tienes clave? Consíguela gratis en 2 minutos:",
        "ein_schritt1": "1.  Pulsa el botón de abajo. Se abrirá la página de Google.",
        "ein_schritt2": "2.  Inicia sesión con tu cuenta de Google y pulsa «Crear clave de API».",
        "ein_schritt3": "3.  Copia la clave, vuelve aquí y pulsa «Pegar».",
        "ein_seite_oeffnen": "Abrir página",
        "ein_einfuegen": "Pegar",
        "ein_testen": "Probar clave",
        "ein_test_laeuft": "Comprobando …",
        "ein_test_ok": "Funciona. Respondió {modell}.",
        "ein_test_leer": "Introduce primero una clave.",
        "ein_test_fehler": "No funciona: {grund}",
        "ein_format": "Parece rara — las claves de Gemini suelen empezar por AIza.",
        "ein_zeigen": "Mostrar",
        "ein_sprache": "Idioma del programa",
        "ein_antwortsprache": "Idioma de las respuestas",
        "ein_hotkey1": "Atajo para explicar",
        "ein_bildschirm": "Capturar solo la pantalla donde está el ratón",
        "ein_modelle": "Modelos (uno por línea, se prueban en orden)",
        "ein_speichern": "Guardar",
        "ein_abbrechen": "Cancelar",
        "ein_fehlt": "Sin clave de API el programa no funciona.",
        "fehler_limit": ("Todos los modelos han alcanzado su límite hoy.\n\n"
                         "Si dice PerMinute, espera un poco; si dice PerDay, "
                         "hasta mañana.\n\n"),
        "fehler_key": ("La clave de API no se acepta. Vuelve a introducirla "
                       "en los ajustes."),
        "fehler_modell": "Un nombre de modelo no es correcto:\n\n",
        "fehler_allgemein": "Error:\n\n",
    },
    "en": {
        "sprachname": "English",
        "titel": "Study Helper",
        "menue_fenster": "Show window",
        "menue_einstellungen": "Settings",
        "menue_beenden": "Quit",
        "weg_titel": "Study Helper keeps running",
        "weg_text": "The window is closed, the program waits in the notification area. Right-click the icon there to quit.",
        "btn_erklaeren": "Explain",
        "btn_einstellungen": "Settings",
        "lade_erklaeren": "Reading the screen …",
        "platzhalter": "Something unclear? Ask here …",
        "btn_senden": "Ask",
        "btn_einfacher": "Even simpler",
        "btn_beispiel": "Give an example",
        "btn_wortfuerwort": "Word by word",
        "btn_wastun": "What should I do?",
        "btn_woerter": "Words",
        "menue_woerter": "My word list",
        "woerter_titel": "My word list",
        "woerter_leer": "No words collected yet.\n\nEvery time you use «Explain», the difficult words are added here automatically.",
        "woerter_anzahl": "{anzahl} words collected",
        "woerter_speichern": "Save as text file",
        "woerter_handy": "For your phone",
        "handy_fertig": "File created: {pfad}\nSend it to your phone and open it there.",
        "woerter_leeren": "Clear list",
        "woerter_gespeichert": "Saved: {pfad}",
        "woerter_sicher": "Really delete all {anzahl} words?",
        "woerter_ueberschrift": "Difficult words",
        "woerter_suche": "Search …",
        "woerter_spalte_wort": "Word",
        "woerter_spalte_erklaerung": "Meaning",
        "woerter_spalte_datum": "Date",
        "woerter_treffer": "{anzahl} of {gesamt}",
        "abfrage_start": "Practise",
        "abfrage_titel": "Practise words",
        "abfrage_frage": "Which word is described here?",
        "abfrage_fortschritt": "Question {nummer} of {gesamt}",
        "abfrage_pruefen": "Check",
        "abfrage_weiter": "Next",
        "abfrage_weissnicht": "I don't know",
        "abfrage_richtig": "Correct!",
        "abfrage_fast": "Almost – it would be: {wort}",
        "abfrage_falsch": "It would be: {wort}",
        "abfrage_ende": "Done!",
        "abfrage_ergebnis": "{richtig} of {gesamt} correct",
        "abfrage_nochmal": "Practise again",
        "abfrage_schliessen": "Close",
        "abfrage_zuwenig": "Collect a few words first, then you can practise.",
        "abfrage_schwierig": "Look at these words again:",
        "woerter_spalte_gekonnt": "Correct",
        "woerter_neu": "{anzahl} new words in your list",
        "ein_schriftgroesse": "Font size",
        "ein_farbschema": "Colours",
        "will_titel": "How it works",
        "will_schritte": [
            ("1", "You see a text. You do not understand it."),
            ("2", "You press {taste}."),
            ("3", "I read your screen and explain it to you."),
            ("4", "Hard words go to your list. You can practise them."),
        ],
        "will_los": "Start",
        "will_taste": "Remember these keys:",
        "ds_titel": "Before you start",
        "ds_kurz": "This program sends a picture of your screen to Google.",
        "ds_punkte": [
            ("What happens",
             "When you press the shortcut, your screen is captured and the "
             "picture is sent to Google. The explanation comes back from "
             "there. It does not work without internet."),
            ("The whole screen is sent",
             "Not just the part you want explained. Whatever else is open "
             "goes too: messages, emails, names. Close anything that is "
             "nobody else's business first."),
            ("Google learns from it",
             "On the free tier Google uses your pictures to improve its "
             "products, and people may see them. Only the paid tier avoids "
             "this."),
            ("What stays on your computer",
             "Your key and your word list stay here, encrypted in your user "
             "account. They are not uploaded anywhere."),
            ("Answers can be wrong",
             "The program helps you understand. For numbers, deadlines and "
             "rules, check the original source."),
        ],
        "ds_regel": "In short: do not capture anything private or belonging to other people.",
        "ds_verstanden": "Understood",
        "ds_abbrechen": "Cancel",
        "menue_hinweis": "Privacy notice",
        "menue_update": "Check for updates",
        "update_da": "New version {version} available",
        "update_holen": "Download",
        "update_spaeter": "Later",
        "update_aktuell": "You have the latest version ({version}).",
        "update_kein_netz": "Could not check. No internet?",
        "farbe_grau": "Dark grey",
        "farbe_dunkel": "Dark",
        "farbe_hell": "Light",
        "status": "{modell}  ·  {sprache}  ·  {anzahl} requests today",
        "bereit": "Ready. Press {taste1} and I will explain what is on your screen.",
        "erst_screenshot": "Take a screenshot first.",
        "du": "You",
        "ein_titel": "Settings",
        "ein_schluessel": "Gemini API key",
        "ein_schluessel_hinweis": (
            "The key is stored encrypted in your Windows profile and never "
            "leaves your computer."),
        "ein_noch_keiner": "No key yet? Here is how to get one — free, in 2 minutes:",
        "ein_schritt1": "1.  Click the button below. Your browser opens the Google page.",
        "ein_schritt2": "2.  Sign in with a Google account and click «Create API key».",
        "ein_schritt3": "3.  Copy the key, come back here and press «Paste».",
        "ein_seite_oeffnen": "Open page",
        "ein_einfuegen": "Paste",
        "ein_testen": "Test key",
        "ein_test_laeuft": "Checking …",
        "ein_test_ok": "Works. Answered by {modell}.",
        "ein_test_leer": "Enter a key first.",
        "ein_test_fehler": "Not working: {grund}",
        "ein_format": "Looks unusual — Gemini keys usually start with AIza.",
        "ein_zeigen": "Show",
        "ein_sprache": "Program language",
        "ein_antwortsprache": "Answer language",
        "ein_hotkey1": "Shortcut for explain",
        "ein_bildschirm": "Capture only the screen with the mouse pointer",
        "ein_modelle": "Models (one per line, tried in order)",
        "ein_speichern": "Save",
        "ein_abbrechen": "Cancel",
        "ein_fehlt": "The program needs an API key to work.",
        "fehler_limit": ("All models have hit their limit today.\n\nIf it says "
                         "PerMinute, wait a moment; PerDay means tomorrow.\n\n"),
        "fehler_key": "The API key was rejected. Enter it again in the settings.",
        "fehler_modell": "A model name is not correct:\n\n",
        "fehler_allgemein": "Error:\n\n",
    },
}

ANTWORTSPRACHEN = ["Deutsch", "Español", "English", "Français", "Italiano"]


def t(schluessel, **werte):
    """Holt einen Text in der eingestellten Programmsprache."""
    tabelle = TEXTE.get(konfig.get("sprache", "de"), TEXTE["de"])
    text = tabelle.get(schluessel, TEXTE["de"].get(schluessel, schluessel))
    if not isinstance(text, str):
        return text          # Listen (z.B. die Hinweispunkte) unveraendert
    return text.format(**werte) if werte else text


# ===========================================================================
#  Bildschirmaufnahme
# ===========================================================================

def aktiver_monitor():
    """Rechteck des Monitors, auf dem der Mauszeiger steht."""
    try:
        user32 = ctypes.windll.user32

        class PUNKT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class RECHTECK(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECHTECK),
                        ("rcWork", RECHTECK), ("dwFlags", ctypes.c_ulong)]

        zeiger = PUNKT()
        user32.GetCursorPos(ctypes.byref(zeiger))
        handle = user32.MonitorFromPoint(zeiger, 2)  # DEFAULTTONEAREST
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(handle, ctypes.byref(info))
        r = info.rcMonitor
        return (r.left, r.top, r.right, r.bottom)
    except Exception as fehler:
        log(f"Monitor nicht bestimmbar: {fehler}")
        return None


def screenshot_base64():
    bild = ImageGrab.grab(all_screens=True)

    if konfig.get("nur_aktiver_bildschirm", True):
        rechteck = aktiver_monitor()
        if rechteck:
            user32 = ctypes.windll.user32
            ux = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            uy = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            l, o, re, u = rechteck
            bild = bild.crop((l - ux, o - uy, re - ux, u - uy))

    breite = konfig.get("max_breite", 1600)
    if bild.width > breite:
        hoehe = int(bild.height * breite / bild.width)
        bild = bild.resize((breite, hoehe), Image.LANCZOS)

    log(f"Screenshot {bild.width}x{bild.height}")
    puffer = io.BytesIO()
    bild.convert("RGB").save(puffer, format="PNG")
    return base64.b64encode(puffer.getvalue()).decode("ascii")


# ===========================================================================
#  Anfragen an Gemini
# ===========================================================================

PROMPT_ERKLAEREN = """Du hilfst einer Person, die einen Text auf ihrem \
Bildschirm nicht ganz versteht. Sehr wahrscheinlich ist die Sprache dieses \
Textes nicht ihre Muttersprache. Du siehst einen Screenshot ihres Bildschirms.

Deine Aufgabe ist nicht Uebersetzen, sondern Verstehen-Helfen.

ZUERST: Finde den Hauptinhalt.

Auf einem Bildschirm steht viel, was mit der eigentlichen Sache nichts zu
tun hat. Suche das, weswegen die Person dich fragt:

- Meistens ist es die Aufgabe, der Text oder die Frage in der Mitte des
  Bildes, oder der groesste zusammenhaengende Textblock.
- Ist eine Aufgabe hervorgehoben, aufgeklappt oder als aktuelle markiert,
  ist das die gesuchte.
- Steht dort ein Formular oder eine Anweisung, ist das der Hauptinhalt.

Das folgende gehoert NICHT dazu und wird NICHT erklaert:
Menues, Navigationsleisten, Seitenleisten mit Aufgabenlisten, Reiter,
Schaltflaechen am Rand, Kopf- und Fusszeilen der Seite, Werbung,
Taskleiste, Browser-Adresszeile, Uhrzeit, Benachrichtigungen.

Sag auch NICHT, auf welcher Webseite oder in welchem Programm die Person
gerade ist. Das weiss sie selbst. Fang direkt beim Inhalt an.

Kannst du nicht entscheiden, was gemeint ist, weil mehrere Aufgaben
gleichwertig nebeneinander stehen: Nimm die oberste oder die in der Mitte,
und schreib in einem kurzen Satz dazu, welche du erklaert hast.

Aufbau deiner Antwort:

1. Ein Satz: Was ist hier zu tun, oder worum geht es in diesem Text?
   Falls der Text in einer anderen Sprache ist als deine Antwort, sag hier
   auch, in welcher.

2. Der Inhalt in einfachen Worten. Bei einer Aufgabe: was genau von der
   Person verlangt wird, Schritt fuer Schritt. Bei einem Text: was darin
   steht.

3. Falls schwierige Woerter vorkommen, der Woerter-Block am Ende.

Danach - und nur wenn schwierige Woerter vorkommen - haeng GANZ ANS ENDE
einen Block in genau diesem Format an:

###WOERTER###
Wort | kurze einfache Erklaerung
Wort | kurze einfache Erklaerung

Regeln fuer diesen Block:
- Links steht das Wort GENAU SO, wie es auf dem Bildschirm steht, in der
  Originalsprache. Nicht uebersetzt, nicht angepasst. Die Person muss es
  auf ihrem Bildschirm wiederfinden koennen.
- Rechts steht die Erklaerung in der Sprache, in der du antwortest.
- Nimm nur Woerter aus dem Hauptinhalt. Keine Woerter aus Menues,
  Schaltflaechen oder Seitenleisten.
- Keine Namen von Programmen, Webseiten oder Menuepunkten.
- Hoechstens 8 Woerter, die schwierigsten zuerst.
- Die Erklaerung in hoechstens 12 Woertern.
- Keine Aufzaehlungszeichen, keine Nummerierung, nur "Wort | Erklaerung".
- Nach diesem Block kommt nichts mehr.

Wenn der Text auf dem Screenshot nicht lesbar ist, sag das klar, statt zu
raten. Kein Vorgeplaenkel, keine Floskeln."""

klient = None
aktives_modell = ""


def klient_aufbauen():
    global klient
    schluessel = schluessel_lesen(konfig.get("schluessel", ""))
    klient = genai.Client(api_key=schluessel) if schluessel else None
    return klient is not None


def ist_limit_fehler(fehler):
    text = str(fehler)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


def sprachregeln():
    """
    Die Regeln, die dafuer sorgen, dass eine Erklaerung in einer anderen
    Sprache trotzdem zum Text auf dem Bildschirm passt. Ohne sie uebersetzt
    das Modell auch die Fachbegriffe - dann steht in der Erklaerung ein Wort,
    das auf dem Bildschirm gar nicht vorkommt.
    """
    sprache = konfig.get("antwortsprache", "Deutsch")
    return f"""SPRACHE - das ist die wichtigste Regel:

Du schreibst deine gesamte Antwort auf {sprache}. Jeden Satz, jede
Ueberschrift, jede Erklaerung. Auch dann, wenn der Text auf dem Bildschirm
in einer anderen Sprache ist.

Der Text auf dem Bildschirm wird NICHT uebersetzt, sondern erklaert. Das ist
ein Unterschied. Halte dich dabei an diese Regeln:

1. Wenn du ein Wort vom Bildschirm nennst, schreib es GENAU SO, wie es dort
   steht - in der Originalsprache, unveraendert. Direkt danach in Klammern,
   was es auf {sprache} bedeutet.
   Beispiel: Rechnung (die Aufstellung, was etwas kostet)
2. Uebersetz niemals ein Wort vom Bildschirm still und heimlich. Die Person
   muss jedes Wort, das du nennst, auf ihrem Bildschirm wiederfinden koennen.
3. Ueberschriften, Knopfbeschriftungen und Feldnamen vom Bildschirm bleiben
   ebenfalls im Original, mit der Bedeutung dahinter in Klammern.
4. Zahlen, Namen, Daten und Betraege uebernimmst du unveraendert.

Schreibweise auf {sprache}:
- Kurze Saetze. Ein Gedanke pro Satz. Keine Nebensatzketten.
- Alltagswoerter statt Fachsprache.
- Keine Redewendungen und keine Bilder, die man nur mit viel Sprachgefuehl
  versteht.
- Wenn der Bildschirmtext in einer anderen Sprache ist als {sprache}, sag im
  ersten Satz, in welcher Sprache er ist.

Bevor du antwortest, pruef zwei Dinge: Ist wirklich jeder Satz auf {sprache}?
Und steht hinter jedem Originalwort seine Bedeutung?"""


def teile_bauen(system_prompt, bild_b64, verlauf, frage=None):
    teile = [
        {"type": "text", "text": system_prompt},
        {"type": "text", "text": sprachregeln()},
        {"type": "image", "data": bild_b64, "mime_type": "image/png"},
    ]
    for rolle, inhalt in verlauf:
        teile.append({"type": "text", "text": f"{rolle}: {inhalt}"})
    if frage:
        teile.append({"type": "text", "text": f"Neue Frage des Schuelers: {frage}"})
    return teile


def frage_api(teile):
    """Probiert die Modelle der Reihe nach. Gibt (Text, Modell) zurueck."""
    global aktives_modell
    letzter = None
    for modell in konfig.get("modelle") or STANDARD["modelle"]:
        try:
            antwort = klient.interactions.create(model=modell, input=teile)
            aktives_modell = modell
            return antwort.output_text, modell
        except Exception as fehler:
            letzter = fehler
            if ist_limit_fehler(fehler):
                log(f"{modell}: Limit erreicht, naechstes Modell")
                continue
            raise
    raise letzter


SCHLUESSEL_SEITE = "https://aistudio.google.com/apikey"


def schluessel_pruefen(roher_schluessel):
    """
    Schickt eine winzige Testanfrage. Gibt (True, Modellname) zurueck oder
    (False, Begruendung). Kostet praktisch nichts, kein Bild dabei.
    """
    try:
        probe = genai.Client(api_key=roher_schluessel)
    except Exception as fehler:
        return False, str(fehler)

    letzter = "?"
    for modell in konfig.get("modelle") or STANDARD["modelle"]:
        try:
            probe.interactions.create(
                model=modell,
                input=[{"type": "text", "text": "Antworte nur mit: OK"}])
            return True, modell
        except Exception as fehler:
            letzter = str(fehler)
            if ist_limit_fehler(fehler):
                continue          # Modell am Limit, naechstes probieren
            break                 # echter Fehler, z.B. Schluessel ungueltig

    if "API key" in letzter or "API_KEY_INVALID" in letzter:
        return False, "API key invalid"
    return False, letzter[:200]


def fehlertext(fehler):
    meldung = str(fehler)
    if ist_limit_fehler(fehler):
        return t("fehler_limit") + meldung
    if "API key" in meldung or "PERMISSION_DENIED" in meldung:
        return t("fehler_key")
    if "NOT_FOUND" in meldung or "404" in meldung:
        return t("fehler_modell") + meldung
    return t("fehler_allgemein") + meldung


# ===========================================================================
#  Warteschlangen
# ===========================================================================

arbeit = queue.Queue()
ui = queue.Queue()
beenden = threading.Event()
sitzung = {"bild": None, "prompt": PROMPT_ERKLAEREN, "verlauf": []}


# ===========================================================================
#  Aktualisierung
# ===========================================================================

def update_pruefen(nur_einmal_am_tag=True):
    """
    Laeuft im Hintergrund. Meldet sich nur, wenn es wirklich etwas Neues
    gibt - eine Meldung "alles aktuell" bei jedem Start waere nur laestig.
    """
    if nur_einmal_am_tag:
        if konfig.get("update_geprueft") == date.today().isoformat():
            return
        konfig["update_geprueft"] = date.today().isoformat()
        konfig_speichern()

    ergebnis = aktualisierung.pruefen()
    if ergebnis is None:
        log("Update-Pruefung fehlgeschlagen (kein Netz?)")
        if not nur_einmal_am_tag:
            ui.put(("meldung", (t("update_kein_netz"), None)))
        return

    if ergebnis["neu"]:
        log(f"Neue Fassung verfuegbar: {ergebnis['version']}")
        ui.put(("update", ergebnis))
    else:
        log("Programm ist aktuell")
        if not nur_einmal_am_tag:
            ui.put(("meldung",
                    (t("update_aktuell", version=aktualisierung.VERSION),
                     None)))


def arbeiter():
    while not beenden.is_set():
        try:
            auftrag = arbeit.get(timeout=0.5)
        except queue.Empty:
            continue

        art = auftrag[0]
        try:
            if klient is None:
                ui.put(("antwort", (t("ein_fehlt"), True)))
                continue

            if art == "erklaeren":
                ui.put(("verstecken", None))
                time.sleep(0.35)
                sitzung["bild"] = screenshot_base64()
                sitzung["prompt"] = PROMPT_ERKLAEREN
                sitzung["verlauf"] = []
                ui.put(("laden", t("lade_erklaeren")))

                text, modell = frage_api(
                    teile_bauen(sitzung["prompt"], sitzung["bild"], []))
                log(f"Antwort von {modell}, {len(text)} Zeichen")
                sitzung["verlauf"].append(("Antwort", text))
                zaehler_hoch()

                text, woerter = woerter_abtrennen(text)
                neue = woerter_ergaenzen(woerter)
                ui.put(("antwort", (text, True)))
                if woerter:
                    ui.put(("woerter", (woerter, neue)))

            elif art == "nachfrage":
                if not sitzung["bild"]:
                    ui.put(("antwort", (t("erst_screenshot"), False)))
                    continue
                frage = auftrag[1]
                sitzung["verlauf"].append(("Schueler", frage))
                text, modell = frage_api(teile_bauen(
                    sitzung["prompt"], sitzung["bild"],
                    sitzung["verlauf"][:-1], frage))
                sitzung["verlauf"].append(("Antwort", text))
                zaehler_hoch()
                ui.put(("antwort", ("\n" + text, False)))

        except Exception as fehler:
            log(f"FEHLER: {fehler}")
            ui.put(("antwort", (fehlertext(fehler), True)))


def zaehler_hoch():
    if konfig.get("zaehler_datum") != date.today().isoformat():
        konfig["zaehler_datum"] = date.today().isoformat()
        konfig["zaehler_stand"] = 0
    konfig["zaehler_stand"] = konfig.get("zaehler_stand", 0) + 1
    konfig_speichern()


# Windows-Konstanten fuer RegisterHotKey
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x0001, 0x0002, 0x0004, 0x0008
MOD_NOREPEAT = 0x4000
PM_REMOVE = 0x0001

# Sondertasten, die man in den Einstellungen eintragen darf
SONDERTASTEN = {
    "space": 0x20, "leertaste": 0x20, "enter": 0x0D, "tab": 0x09,
    "insert": 0x2D, "einfg": 0x2D, "delete": 0x2E, "entf": 0x2E,
    "home": 0x24, "end": 0x23, "pos1": 0x24, "ende": 0x23,
}

neu_registrieren = threading.Event()


class NACHRICHT(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt_x", ctypes.c_long),
                ("pt_y", ctypes.c_long)]


def taste_zerlegen(text):
    """Macht aus 'ctrl+alt+q' die Werte, die Windows erwartet."""
    mods, taste = 0, None
    for teil in [x.strip().lower() for x in text.split("+") if x.strip()]:
        if teil in ("ctrl", "strg", "control"):
            mods |= MOD_CONTROL
        elif teil == "alt":
            mods |= MOD_ALT
        elif teil in ("shift", "umschalt"):
            mods |= MOD_SHIFT
        elif teil in ("win", "windows"):
            mods |= MOD_WIN
        elif teil in SONDERTASTEN:
            taste = SONDERTASTEN[teil]
        elif len(teil) > 1 and teil[0] == "f" and teil[1:].isdigit():
            nummer = int(teil[1:])
            if 1 <= nummer <= 24:
                taste = 0x70 + nummer - 1
        elif len(teil) == 1:
            taste = ord(teil.upper())
    return mods, taste


def hotkeys_setzen():
    """Stoesst das Neuanmelden der Tastenkuerzel an."""
    neu_registrieren.set()


def hotkey_schleife():
    """
    Meldet die Tastenkuerzel bei Windows an und wartet auf deren Meldungen.

    Wichtig: RegisterHotKey meldet NUR die angegebenen Kombinationen an.
    Alle uebrigen Tastendruecke bekommt dieses Programm nie zu sehen - anders
    als bei einem globalen Tastaturhaken, den Virenscanner zu Recht als
    Keylogger einstufen.
    """
    user32 = ctypes.windll.user32
    nachricht = NACHRICHT()
    angemeldet = {}          # Kennung -> Modus
    neu_registrieren.set()

    while not beenden.is_set():
        if neu_registrieren.is_set():
            for kennung in angemeldet:
                user32.UnregisterHotKey(None, kennung)
            angemeldet.clear()

            for kennung, (feld, modus) in enumerate(
                    [("hotkey_erklaeren", "erklaeren")], start=1):
                mods, taste = taste_zerlegen(konfig.get(feld, ""))
                if not taste:
                    log(f"Tastenkuerzel '{konfig.get(feld)}' nicht verstanden")
                    continue
                if user32.RegisterHotKey(None, kennung,
                                         mods | MOD_NOREPEAT, taste):
                    angemeldet[kennung] = modus
                    log(f"Tastenkuerzel angemeldet: {konfig.get(feld)}")
                else:
                    log(f"'{konfig.get(feld)}' ist schon von einem anderen "
                        f"Programm belegt")
            neu_registrieren.clear()

        while user32.PeekMessageW(ctypes.byref(nachricht), None, 0, 0,
                                  PM_REMOVE):
            if nachricht.message == WM_HOTKEY:
                modus = angemeldet.get(nachricht.wParam)
                if modus:
                    arbeit.put((modus,))

        time.sleep(0.03)

    for kennung in angemeldet:
        user32.UnregisterHotKey(None, kennung)


def symbol_bild(groesse=64, mit_hintergrund=True):
    """
    Zeichnet das Programmsymbol: ein aufgeschlagenes Buch mit einer
    Gluehbirne darueber - Lesen und Verstehen. Wird gross gezeichnet und
    verkleinert, damit die Kanten weich werden.
    """
    S = 512
    bild = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    z = ImageDraw.Draw(bild)

    weiss = (255, 255, 255)
    dunkel = (22, 22, 31)
    gelb = (240, 200, 90)

    if mit_hintergrund:
        z.rounded_rectangle((0, 0, S, S), radius=int(S * 0.22),
                            fill=(86, 124, 208))
        z.rounded_rectangle((0, 0, S, int(S * 0.94)), radius=int(S * 0.22),
                            fill=(122, 162, 247))
        seitenfarbe, bund = weiss, (86, 124, 208)
    else:
        seitenfarbe, bund = (122, 162, 247), (22, 22, 31)

    # Gluehbirne
    mx, my, r = int(S * 0.50), int(S * 0.285), int(S * 0.105)
    z.ellipse((mx - r, my - r, mx + r, my + r), fill=gelb)
    z.rounded_rectangle((mx - int(r * 0.42), my + int(r * 0.72),
                         mx + int(r * 0.42), my + int(r * 1.30)),
                        radius=int(r * 0.16), fill=seitenfarbe)
    for winkel in (-140, -110, -70, -40):
        bogen = math.radians(winkel)
        von, bis = r * 1.42, r * 1.95
        z.line([(mx + von * math.cos(bogen), my + von * math.sin(bogen)),
                (mx + bis * math.cos(bogen), my + bis * math.sin(bogen))],
               fill=seitenfarbe, width=max(1, int(S * 0.028)))

    # Aufgeschlagenes Buch
    oben, unten = int(S * 0.545), int(S * 0.775)
    links, rechts = int(S * 0.155), int(S * 0.845)
    mitte_x = S // 2
    bauch = int(S * 0.052)

    for x_aussen in (links, rechts):
        punkte = [(mitte_x, oben + bauch)]
        for i in range(15):
            anteil = i / 14
            punkte.append((mitte_x + (x_aussen - mitte_x) * anteil,
                           oben + bauch * (1 - math.sin(anteil * math.pi / 2))))
        punkte += [(x_aussen, unten - bauch), (mitte_x, unten)]
        z.polygon(punkte, fill=seitenfarbe)

    z.line([(mitte_x, oben + bauch), (mitte_x, unten)], fill=bund,
           width=max(1, int(S * 0.016)))

    dicke = int(S * 0.019)
    for i in range(3):
        y = oben + int(S * 0.055) + i * int(S * 0.045)
        for x1, x2 in ((int(S * 0.215), mitte_x - int(S * 0.035)),
                       (mitte_x + int(S * 0.035), int(S * 0.785))):
            z.rounded_rectangle((x1, y, x2, y + dicke), radius=dicke // 2,
                                fill=dunkel)

    return bild.resize((groesse, groesse), Image.LANCZOS)


def tray_bild():
    return symbol_bild(64)


# ===========================================================================
#  Start der Hintergrundfaeden
# ===========================================================================

def hintergrund_starten():
    """Startet Arbeiter, Tastenkuerzel, Wecker und Update-Pruefung."""
    threading.Thread(target=arbeiter, daemon=True).start()
    threading.Thread(target=hotkey_schleife, daemon=True).start()
    threading.Thread(target=auf_wecker_horchen, daemon=True).start()
    threading.Thread(target=update_pruefen, daemon=True).start()


def beenden_anfordern():
    """Sagt allen Hintergrundfaeden, dass Schluss ist."""
    beenden.set()
