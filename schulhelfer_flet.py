# -*- coding: utf-8 -*-
"""
Schulhelfer - Oberflaeche in Flet
==================================
Erklaert auf Tastendruck in einfacher Sprache, was auf dem Bildschirm steht,
sammelt die schwierigen Woerter und fragt sie ab.

Die ganze Logik steckt in kern.py. Diese Datei zeigt sie nur an.

Starten:   flet run schulhelfer_flet.py
Bauen:     flet build windows
"""

import os
import queue
import threading
import time
import webbrowser

import flet as ft
import pystray

import kern
import lernapp


# ---------------------------------------------------------------------------
#  Hilfe
# ---------------------------------------------------------------------------

def t(schluessel, **werte):
    return kern.t(schluessel, **werte)


SCHNELLFRAGEN = [
    ("btn_einfacher",
     "Erklaere das bitte noch einfacher. Kuerzere Saetze, noch leichtere "
     "Woerter, so wie fuer jemanden, der die Sprache gerade erst lernt. "
     "Es gelten weiterhin alle Sprachregeln von oben."),
    ("btn_beispiel",
     "Gib mir ein konkretes Beispiel aus dem Alltag, das zeigt, worum es "
     "hier geht. Es gelten weiterhin alle Sprachregeln von oben."),
    ("btn_wortfuerwort",
     "Geh den Text auf dem Bildschirm Satz fuer Satz durch. Schreib jeden "
     "Satz zuerst genau so hin, wie er auf dem Bildschirm steht, und "
     "erklaere ihn direkt darunter in einfachen Worten. Es gelten weiterhin "
     "alle Sprachregeln von oben."),
    ("btn_wastun",
     "Was genau soll ich jetzt konkret tun? Sag es mir in einfachen "
     "Schritten. Es gelten weiterhin alle Sprachregeln von oben."),
]

SCHRIFTGROESSEN = ["9", "10", "11", "12", "14", "16", "18", "20"]


def hauptfarbe():
    """Grundfarbe des Farbschemas. Flet leitet daraus alles Weitere ab."""
    return {"grau": ft.Colors.BLUE_GREY,
            "dunkel": ft.Colors.INDIGO,
            "hell": ft.Colors.BLUE}.get(
        kern.konfig.get("farbschema", "grau"), ft.Colors.BLUE_GREY)


def hell_oder_dunkel():
    return (ft.ThemeMode.LIGHT
            if kern.konfig.get("farbschema") == "hell"
            else ft.ThemeMode.DARK)


# ===========================================================================
#  Oberflaeche
# ===========================================================================

def main(seite: ft.Page):
    seite.title = t("titel")
    seite.window.width = 640
    seite.window.height = 780
    seite.window.min_width = 420
    seite.window.min_height = 520
    seite.padding = 0

    def thema_setzen():
        """
        Farben UND Schriftgroessen. Die Groesse muss ins Thema, sonst
        aendert sich nur, was man einzeln angefasst hat - Knopfbeschriftungen
        und Listen blieben sonst gleich gross.
        """
        g = int(kern.konfig.get("schriftgroesse", 11))
        schriften = ft.TextTheme(
            body_large=ft.TextStyle(size=g + 2),
            body_medium=ft.TextStyle(size=g),
            body_small=ft.TextStyle(size=max(9, g - 2)),
            title_large=ft.TextStyle(size=g + 7, weight=ft.FontWeight.BOLD),
            title_medium=ft.TextStyle(size=g + 3, weight=ft.FontWeight.W_500),
            title_small=ft.TextStyle(size=g + 1),
            label_large=ft.TextStyle(size=g),
            label_medium=ft.TextStyle(size=max(9, g - 1)),
            label_small=ft.TextStyle(size=max(8, g - 2)),
        )
        seite.theme = ft.Theme(color_scheme_seed=hauptfarbe(),
                               text_theme=schriften)
        seite.dark_theme = ft.Theme(color_scheme_seed=hauptfarbe(),
                                    text_theme=schriften)
        seite.theme_mode = hell_oder_dunkel()

    def markdown_stil():
        """Schriftgroesse fuer den Antworttext."""
        g = int(kern.konfig.get("schriftgroesse", 11))
        return ft.MarkdownStyleSheet(
            p_text_style=ft.TextStyle(size=g + 1),
            strong_text_style=ft.TextStyle(size=g + 1,
                                           weight=ft.FontWeight.BOLD),
            h1_text_style=ft.TextStyle(size=g + 8,
                                       weight=ft.FontWeight.BOLD),
            h2_text_style=ft.TextStyle(size=g + 5,
                                       weight=ft.FontWeight.BOLD),
            h3_text_style=ft.TextStyle(size=g + 3,
                                       weight=ft.FontWeight.BOLD),
        )

    thema_setzen()

    def gr(zusatz=0):
        return int(kern.konfig.get("schriftgroesse", 11)) + zusatz

    # Jedes dauerhafte Steuerelement wird hier mit seinem Textschluessel
    # eingetragen. Beim Sprachwechsel geht die Liste einmal durch - so
    # kann kein Element vergessen werden.
    beschriftungen = []

    def beschriftungsfeld(steuer):
        """
        In welchem Feld steckt die Beschriftung?

        Wichtig: Knoepfe speichern ihren Text in 'content', nicht in 'text'.
        Setzt man 'text', legt Python still ein neues Attribut an, das Flet
        nie ansieht - der Knopf bleibt dann in der alten Sprache stehen.
        """
        felder = getattr(type(steuer), "__dataclass_fields__", {})
        for kandidat in ("content", "value", "label"):
            if kandidat in felder:
                return kandidat
        return "tooltip"

    def merken(steuer, schluessel, feld=None):
        beschriftungen.append((steuer, schluessel,
                               feld or beschriftungsfeld(steuer)))
        return steuer

    def beschriftungen_auffrischen():
        for steuer, schluessel, feld in beschriftungen:
            try:
                setattr(steuer, feld, t(schluessel))
            except Exception as fehler:
                kern.log(f"Beschriftung {schluessel} nicht setzbar: {fehler}")

    # -----------------------------------------------------------------------
    #  Ansicht 1: Erklaeren
    # -----------------------------------------------------------------------

    ladebalken = ft.ProgressBar(visible=False)
    antwort = ft.Markdown("", selectable=True,
                          extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                          md_style_sheet=markdown_stil())
    wortkarten = ft.Column(spacing=8)
    verlaufsspalte = ft.Column([antwort, wortkarten], spacing=16,
                               scroll=ft.ScrollMode.AUTO, expand=True)

    eingabe = ft.TextField(hint_text=t("platzhalter"), border_radius=12,
                           filled=True, expand=True, multiline=False,
                           on_submit=lambda e: nachfragen(eingabe.value))

    def bereit_anzeigen():
        antwort.value = t("bereit",
                          taste1=kern.konfig["hotkey_erklaeren"].upper())
        wortkarten.controls.clear()

    def nachfragen(text, beschriftung=None):
        if not (text or "").strip():
            return
        if not kern.sitzung.get("bild"):
            melden(t("erst_screenshot"))
            return
        antwort.value += f"\n\n**{t('du')}:** {beschriftung or text}\n"
        eingabe.value = ""
        ladebalken.visible = True
        seite.update()
        kern.arbeit.put(("nachfrage", text))

    erklaerknopf = merken(ft.FilledButton(
        t("btn_erklaeren"), icon=ft.Icons.AUTO_AWESOME, height=52,
        expand=True, on_click=lambda e: kern.arbeit.put(("erklaeren",))),
        "btn_erklaeren")

    erklaeren_ansicht = ft.Column([
        ft.Container(
            content=ft.Row([erklaerknopf], spacing=8),
            padding=ft.Padding.only(left=16, right=16, top=12)),
        ft.Container(content=verlaufsspalte, expand=True,
                     padding=ft.Padding.symmetric(horizontal=16, vertical=8)),
        ft.Container(
            content=ft.Row(
                [merken(ft.OutlinedButton(
                    t(schluessel),
                    on_click=lambda e, a=auftrag, s=schluessel:
                        nachfragen(a, t(s))), schluessel)
                 for schluessel, auftrag in SCHNELLFRAGEN],
                wrap=True, spacing=8, run_spacing=8),
            padding=ft.Padding.symmetric(horizontal=16)),
        ft.Container(
            content=ft.Row([
                eingabe,
                merken(ft.FilledButton(
                    t("btn_senden"), icon=ft.Icons.SEND, height=48,
                    on_click=lambda e: nachfragen(eingabe.value)),
                    "btn_senden"),
            ], spacing=8),
            padding=ft.Padding.only(left=16, right=16, top=8, bottom=12)),
    ], expand=True, spacing=10)

    # -----------------------------------------------------------------------
    #  Ansicht 2: Woerterliste
    # -----------------------------------------------------------------------

    suche = ft.TextField(hint_text=t("woerter_suche"),
                         prefix_icon=ft.Icons.SEARCH, border_radius=12,
                         filled=True, dense=True,
                         on_change=lambda e: liste_fuellen())
    liste = ft.ListView(expand=True, spacing=2)
    listenzaehler = ft.Text("", size=12, opacity=0.7)
    listenmeldung = ft.Text("", size=12)

    def liste_fuellen():
        alle = kern.woerter_laden()
        begriff = (suche.value or "").lower()
        sichtbar = [e for e in alle
                    if not begriff
                    or begriff in e["wort"].lower()
                    or begriff in e["erklaerung"].lower()]
        liste.controls.clear()
        for eintrag in reversed(sichtbar):
            richtig = eintrag.get("richtig", 0)
            falsch = eintrag.get("falsch", 0)
            gesamt = richtig + falsch
            gekonnt = gesamt and richtig / gesamt >= 0.6
            liste.controls.append(ft.ListTile(
                leading=ft.Icon(
                    ft.Icons.CHECK_CIRCLE if gekonnt
                    else ft.Icons.RADIO_BUTTON_UNCHECKED,
                    color=ft.Colors.GREEN if gekonnt else None, size=20),
                title=ft.Text(eintrag["wort"], weight=ft.FontWeight.BOLD,
                              size=gr()),
                subtitle=ft.Text(eintrag["erklaerung"], size=gr(-2)),
                trailing=ft.Text(f"{richtig}/{gesamt}" if gesamt else "–",
                                 size=gr(-3), opacity=0.6),
                dense=True,
            ))
        listenzaehler.value = (t("woerter_treffer", anzahl=len(sichtbar),
                                 gesamt=len(alle)) if begriff
                               else t("woerter_anzahl", anzahl=len(alle)))
        seite.update()

    def fuers_handy(e=None):
        eintraege = kern.woerter_laden()
        if not eintraege:
            return
        ziel = kern.Path.home() / "Desktop" / "Meine_Woerter.html"
        if not ziel.parent.exists():
            ziel = kern.ORDNER / "Meine_Woerter.html"
        try:
            ziel.write_text(
                lernapp.lern_app_bauen(eintraege,
                                       kern.konfig.get("sprache", "de")),
                encoding="utf-8")
            melden(t("handy_fertig", pfad=ziel.name))
        except Exception as fehler:
            melden(str(fehler)[:100])

    def als_text(e=None):
        eintraege = kern.woerter_laden()
        if not eintraege:
            return
        ziel = kern.Path.home() / "Desktop" / "Meine_Woerterliste.txt"
        if not ziel.parent.exists():
            ziel = kern.ORDNER / "Meine_Woerterliste.txt"
        try:
            breite = max(len(e["wort"]) for e in eintraege) + 2
            zeilen = [f"{e['wort']:<{breite}}{e['erklaerung']}"
                      for e in sorted(eintraege,
                                      key=lambda e: e["wort"].lower())]
            ziel.write_text(t("woerter_titel") + "\n" + "=" * 40 + "\n\n"
                            + "\n".join(zeilen) + "\n", encoding="utf-8")
            melden(t("woerter_gespeichert", pfad=ziel.name))
        except Exception as fehler:
            melden(str(fehler)[:100])

    def liste_leeren(e=None):
        anzahl = len(kern.woerter_laden())
        if not anzahl:
            return

        def ja(e):
            kern.woerter_speichern([])
            seite.pop_dialog()
            liste_fuellen()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(t("woerter_titel")),
            content=ft.Text(t("woerter_sicher", anzahl=anzahl)),
            actions=[
                ft.TextButton(t("ds_abbrechen"),
                              on_click=lambda e: seite.pop_dialog()),
                ft.FilledButton(t("woerter_leeren"), on_click=ja),
            ],
        )
        seite.show_dialog(dialog)

    woerter_ansicht = ft.Column([
        ft.Container(content=ft.Column([
            suche,
            ft.Row([listenzaehler, listenmeldung], spacing=12),
        ], spacing=8), padding=ft.Padding.only(left=16, right=16, top=12)),
        ft.Container(content=liste, expand=True,
                     padding=ft.Padding.symmetric(horizontal=8)),
        ft.Container(content=ft.Row([
            merken(ft.FilledButton(t("abfrage_start"), icon=ft.Icons.SCHOOL,
                                   on_click=lambda e: ansicht_wechseln(2)),
                   "abfrage_start"),
            merken(ft.OutlinedButton(t("woerter_handy"),
                                     icon=ft.Icons.PHONE_ANDROID,
                                     on_click=fuers_handy), "woerter_handy"),
            merken(ft.OutlinedButton(t("woerter_speichern"),
                                     icon=ft.Icons.DOWNLOAD,
                                     on_click=als_text), "woerter_speichern"),
            merken(ft.OutlinedButton(t("woerter_leeren"),
                                     icon=ft.Icons.DELETE_OUTLINE,
                                     on_click=liste_leeren), "woerter_leeren"),
        ], wrap=True, spacing=8, run_spacing=8),
            padding=ft.Padding.only(left=16, right=16, bottom=12, top=4)),
    ], expand=True, spacing=8)

    # -----------------------------------------------------------------------
    #  Ansicht 3: Abfrage
    # -----------------------------------------------------------------------

    runde = {"woerter": [], "nummer": 0, "punkte": 0, "schwierige": [],
             "beantwortet": False, "fertig": False}

    fortschritt = ft.ProgressBar(value=0)
    fortschritt_text = ft.Text("", size=12, opacity=0.7)
    frage_ueberschrift = merken(
        ft.Text(t("abfrage_frage"), size=13, opacity=0.7), "abfrage_frage",
        "value")
    gefragt = ft.Text("", size=gr(11), weight=ft.FontWeight.BOLD)
    antwortfeld = ft.TextField(text_align=ft.TextAlign.CENTER,
                               border_radius=12, filled=True, text_size=gr(6),
                               on_submit=lambda e: abfrage_weiter())
    abfrage_rueckmeldung = ft.Text("", size=gr(4), weight=ft.FontWeight.BOLD)
    abfrage_knopf = ft.FilledButton(t("abfrage_pruefen"), height=48,
                                    expand=True,
                                    on_click=lambda e: abfrage_weiter())
    weissnicht_knopf = merken(ft.OutlinedButton(
        t("abfrage_weissnicht"), height=48,
        on_click=lambda e: abfrage_antworten("")), "abfrage_weissnicht")

    def runde_starten():
        runde["woerter"] = kern.abfrage_auswaehlen(kern.woerter_laden(), 10)
        runde.update({"nummer": 0, "punkte": 0, "schwierige": [],
                      "fertig": False})
        if not runde["woerter"]:
            gefragt.value = t("abfrage_zuwenig")
            gefragt.size = gr(4)
            frage_ueberschrift.visible = False
            antwortfeld.visible = False
            weissnicht_knopf.visible = False
            abfrage_knopf.visible = False
            fortschritt_text.value = ""
            seite.update()
            return
        frage_ueberschrift.visible = True
        antwortfeld.visible = True
        weissnicht_knopf.visible = True
        abfrage_knopf.visible = True
        frage_zeigen()

    def frage_zeigen():
        eintrag = runde["woerter"][runde["nummer"]]
        runde["beantwortet"] = False
        gefragt.value = eintrag["erklaerung"]
        gefragt.size = gr(11)
        antwortfeld.value = ""
        antwortfeld.disabled = False
        abfrage_rueckmeldung.value = ""
        abfrage_knopf.content = t("abfrage_pruefen")
        weissnicht_knopf.disabled = False
        fortschritt.value = runde["nummer"] / len(runde["woerter"])
        fortschritt_text.value = t("abfrage_fortschritt",
                                   nummer=runde["nummer"] + 1,
                                   gesamt=len(runde["woerter"]))
        seite.update()
        # focus() ist in Flet eine Coroutine - ohne run_task passiert nichts
        seite.run_task(antwortfeld.focus)

    def abfrage_antworten(eingegeben):
        if runde["beantwortet"] or not runde["woerter"]:
            return
        eintrag = runde["woerter"][runde["nummer"]]
        wort = eintrag["wort"]
        urteil = kern.antwort_pruefen(eingegeben, wort)

        if urteil == "richtig":
            abfrage_rueckmeldung.value = t("abfrage_richtig")
            abfrage_rueckmeldung.color = ft.Colors.GREEN
            runde["punkte"] += 1
            kern.ergebnis_merken(wort, True)
        elif urteil == "fast":
            abfrage_rueckmeldung.value = t("abfrage_fast", wort=wort)
            abfrage_rueckmeldung.color = ft.Colors.ORANGE
            runde["punkte"] += 1
            kern.ergebnis_merken(wort, True)
        else:
            abfrage_rueckmeldung.value = t("abfrage_falsch", wort=wort)
            abfrage_rueckmeldung.color = ft.Colors.RED
            runde["schwierige"].append(wort)
            kern.ergebnis_merken(wort, False)

        runde["beantwortet"] = True
        antwortfeld.disabled = True
        weissnicht_knopf.disabled = True
        abfrage_knopf.content = t("abfrage_weiter")
        seite.update()

    def abfrage_weiter():
        if runde["fertig"]:
            runde_starten()
            return
        if not runde["beantwortet"]:
            abfrage_antworten(antwortfeld.value or "")
            return
        runde["nummer"] += 1
        if runde["nummer"] >= len(runde["woerter"]):
            abfrage_abschluss()
        else:
            frage_zeigen()

    def abfrage_abschluss():
        runde["fertig"] = True
        text = t("abfrage_ergebnis", richtig=runde["punkte"],
                 gesamt=len(runde["woerter"]))
        if runde["schwierige"]:
            text += ("\n\n" + t("abfrage_schwierig") + "\n"
                     + ", ".join(runde["schwierige"]))
        gefragt.value = text
        gefragt.size = gr(4)
        frage_ueberschrift.visible = False
        antwortfeld.visible = False
        abfrage_rueckmeldung.value = ""
        weissnicht_knopf.disabled = True
        fortschritt.value = 1
        fortschritt_text.value = t("abfrage_ende")
        abfrage_knopf.content = t("abfrage_nochmal")
        seite.update()
        liste_fuellen()

    abfrage_ansicht = ft.Column([
        fortschritt,
        ft.Container(content=ft.Column([
            fortschritt_text,
            frage_ueberschrift,
            gefragt,
            antwortfeld,
            abfrage_rueckmeldung,
        ], spacing=14), expand=True,
            padding=ft.Padding.symmetric(horizontal=20, vertical=16)),
        ft.Container(content=ft.Row([weissnicht_knopf, abfrage_knopf],
                                    spacing=8),
                     padding=ft.Padding.only(left=20, right=20, bottom=16)),
    ], expand=True, spacing=4)

    # -----------------------------------------------------------------------
    #  Einstellungen
    # -----------------------------------------------------------------------

    def einstellungen_oeffnen(e=None):
        schluesselfeld = ft.TextField(
            label=t("ein_schluessel"), password=True,
            can_reveal_password=True, border_radius=10,
            value=kern.schluessel_lesen(kern.konfig.get("schluessel", "")))
        pruefmeldung = ft.Text("", size=12)

        def seite_oeffnen(e):
            webbrowser.open(kern.SCHLUESSEL_SEITE)

        def einfuegen(e):
            inhalt = (seite.clipboard or "").strip()
            if not inhalt:
                return
            schluesselfeld.value = inhalt
            if not inhalt.startswith("AIza"):
                pruefmeldung.value = t("ein_format")
                pruefmeldung.color = ft.Colors.ORANGE
            else:
                pruefmeldung.value = ""
            seite.update()

        def testen(e):
            pruefmeldung.value = t("ein_test_laeuft")
            pruefmeldung.color = None
            seite.update()

            def im_hintergrund():
                klappt, angabe = kern.schluessel_pruefen(
                    (schluesselfeld.value or "").strip())
                kern.ui.put(("pruefergebnis", (klappt, angabe)))

            if not (schluesselfeld.value or "").strip():
                pruefmeldung.value = t("ein_test_leer")
                pruefmeldung.color = ft.Colors.ORANGE
                seite.update()
                return
            nonlocal pruefanzeige
            pruefanzeige = pruefmeldung
            threading.Thread(target=im_hintergrund, daemon=True).start()

        sprachauswahl = ft.Dropdown(
            label=t("ein_sprache"), border_radius=10,
            value=kern.konfig.get("sprache", "de"),
            options=[ft.dropdown.Option(k, kern.TEXTE[k]["sprachname"])
                     for k in kern.TEXTE])
        antwortsprache = ft.Dropdown(
            label=t("ein_antwortsprache"), border_radius=10,
            value=kern.konfig.get("antwortsprache", "Deutsch"),
            options=[ft.dropdown.Option(s) for s in kern.ANTWORTSPRACHEN])
        farbauswahl = ft.Dropdown(
            label=t("ein_farbschema"), border_radius=10,
            value=kern.konfig.get("farbschema", "grau"),
            options=[ft.dropdown.Option("grau", t("farbe_grau")),
                     ft.dropdown.Option("dunkel", t("farbe_dunkel")),
                     ft.dropdown.Option("hell", t("farbe_hell"))])
        schriftauswahl = ft.Dropdown(
            label=t("ein_schriftgroesse"), border_radius=10,
            value=str(kern.konfig.get("schriftgroesse", 11)),
            options=[ft.dropdown.Option(s) for s in SCHRIFTGROESSEN])
        tastenfeld = ft.TextField(label=t("ein_hotkey1"), border_radius=10,
                                  value=kern.konfig["hotkey_erklaeren"])
        nur_aktiv = ft.Switch(label=t("ein_bildschirm"),
                              value=kern.konfig.get("nur_aktiver_bildschirm",
                                                    True))
        modellfeld = ft.TextField(
            label=t("ein_modelle"), multiline=True, min_lines=4, max_lines=6,
            border_radius=10, value="\n".join(kern.konfig.get("modelle", [])))

        def speichern(e):
            roh = (schluesselfeld.value or "").strip()
            if not roh:
                pruefmeldung.value = t("ein_fehlt")
                pruefmeldung.color = ft.Colors.ORANGE
                seite.update()
                return

            kern.konfig["schluessel"] = kern.schluessel_schuetzen(roh)
            kern.konfig["sprache"] = sprachauswahl.value
            kern.konfig["antwortsprache"] = antwortsprache.value
            kern.konfig["farbschema"] = farbauswahl.value
            kern.konfig["schriftgroesse"] = int(schriftauswahl.value)
            kern.konfig["hotkey_erklaeren"] = (
                tastenfeld.value or "ctrl+alt+q").strip().lower()
            kern.konfig["nur_aktiver_bildschirm"] = bool(nur_aktiv.value)
            kern.konfig["modelle"] = [z.strip() for z in
                                      (modellfeld.value or "").splitlines()
                                      if z.strip()] or kern.STANDARD["modelle"]
            kern.konfig_speichern()
            kern.klient_aufbauen()
            kern.hotkeys_setzen()

            seite.pop_dialog()
            neu_aufbauen()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(t("ein_titel")),
            content=ft.Container(width=520, height=520, content=ft.Column([
                schluesselfeld,
                ft.Row([
                    ft.FilledTonalButton(t("ein_seite_oeffnen"),
                                         icon=ft.Icons.OPEN_IN_NEW,
                                         on_click=seite_oeffnen),
                    ft.OutlinedButton(t("ein_einfuegen"),
                                      icon=ft.Icons.CONTENT_PASTE,
                                      on_click=einfuegen),
                    ft.OutlinedButton(t("ein_testen"),
                                      icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                                      on_click=testen),
                ], wrap=True, spacing=8, run_spacing=8),
                pruefmeldung,
                ft.Text(t("ein_schluessel_hinweis"), size=11, opacity=0.7),
                ft.Divider(),
                sprachauswahl, antwortsprache, farbauswahl, schriftauswahl,
                tastenfeld, nur_aktiv, modellfeld,
            ], spacing=14, scroll=ft.ScrollMode.AUTO)),
            actions=[
                ft.TextButton(t("ein_abbrechen"),
                              on_click=lambda e: seite.pop_dialog()),
                ft.FilledButton(t("ein_speichern"), on_click=speichern),
            ],
        )
        seite.show_dialog(dialog)

    pruefanzeige = None

    # -----------------------------------------------------------------------
    #  Datenschutz-Hinweis
    # -----------------------------------------------------------------------

    def sprachwahl_zeigen(danach=None):
        """
        Allererster Schritt. Enthaelt absichtlich fast keinen Text - wer die
        Sprache noch nicht gewaehlt hat, versteht ja moeglicherweise keine
        der drei. Die Sprachnamen stehen jeweils in ihrer eigenen Sprache.
        """
        def waehlen(kuerzel):
            kern.konfig["sprache"] = kuerzel
            kern.konfig["antwortsprache"] = {
                "de": "Deutsch", "es": "Español", "en": "English"}[kuerzel]
            kern.konfig["sprache_gewaehlt"] = True
            kern.konfig_speichern()
            seite.pop_dialog()
            neu_aufbauen()
            if danach:
                danach()

        knoepfe = [
            ft.FilledTonalButton(
                kern.TEXTE[k]["sprachname"], height=64, width=380,
                on_click=lambda e, kk=k: waehlen(kk))
            for k in ("de", "en", "es")
        ]

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.LANGUAGE, size=28),
                          ft.Text("Sprache · Language · Idioma", size=20,
                                  weight=ft.FontWeight.BOLD)], spacing=12),
            content=ft.Container(width=400, height=240, content=ft.Column(
                knoepfe, spacing=14,
                alignment=ft.MainAxisAlignment.CENTER)),
        )
        seite.show_dialog(dialog)

    def willkommen_zeigen(danach=None):
        """Vier kurze Saetze. Was das Programm tut, ohne Fachwoerter."""
        taste = kern.konfig["hotkey_erklaeren"].upper()

        zeilen = []
        for nummer, text in t("will_schritte"):
            zeilen.append(ft.Row([
                ft.Container(
                    width=34, height=34, border_radius=17,
                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(nummer, weight=ft.FontWeight.BOLD)),
                ft.Text(text.format(taste=taste), size=gr(3), expand=True),
            ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER))

        def weiter(e):
            seite.pop_dialog()
            if danach:
                danach()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.MENU_BOOK, size=28),
                          ft.Text(t("will_titel"), size=gr(9),
                                  weight=ft.FontWeight.BOLD)], spacing=12),
            content=ft.Container(width=460, height=330, content=ft.Column(
                zeilen + [
                    ft.Container(
                        margin=ft.Margin.only(top=10), padding=16,
                        border_radius=12,
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                        content=ft.Column([
                            ft.Text(t("will_taste"), size=gr(-1), opacity=0.8),
                            ft.Text(taste, size=gr(6),
                                    weight=ft.FontWeight.BOLD),
                        ], spacing=2, tight=True)),
                ], spacing=18, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.FilledButton(t("will_los"), height=48,
                                     on_click=weiter)],
        )
        seite.show_dialog(dialog)

    def hinweis_zeigen(beim_ersten_mal=False, danach=None):
        punkte = []
        for ueberschrift, inhalt in t("ds_punkte"):
            punkte.append(ft.Column([
                ft.Text(ueberschrift, weight=ft.FontWeight.BOLD, size=gr()),
                ft.Text(inhalt, size=gr(-2), opacity=0.8),
            ], spacing=2))

        def verstanden(e):
            kern.konfig["hinweis_gelesen"] = True
            kern.konfig_speichern()
            seite.pop_dialog()
            if danach:
                danach()

        def abbrechen(e):
            seite.pop_dialog()
            programm_beenden()

        aktionen = [ft.FilledButton(t("ds_verstanden"), on_click=verstanden)]
        if beim_ersten_mal:
            aktionen.insert(0, ft.TextButton(t("ds_abbrechen"),
                                             on_click=abbrechen))

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Column([
                ft.Text(t("ds_titel"), size=gr(6),
                        weight=ft.FontWeight.BOLD),
                ft.Text(t("ds_kurz"), size=gr(-1),
                        color=ft.Colors.PRIMARY),
            ], spacing=4, tight=True),
            content=ft.Container(width=520, height=420, content=ft.Column(
                punkte + [
                    ft.Container(
                        content=ft.Text(t("ds_regel"),
                                        weight=ft.FontWeight.BOLD, size=gr(-1)),
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                        padding=14, border_radius=10, margin=ft.Margin.only(top=8)),
                ], spacing=14, scroll=ft.ScrollMode.AUTO)),
            actions=aktionen,
        )
        seite.show_dialog(dialog)

    # -----------------------------------------------------------------------
    #  Rahmen
    # -----------------------------------------------------------------------

    inhalt = ft.Container(content=erklaeren_ansicht, expand=True)

    def ansicht_wechseln(nummer):
        navigation.selected_index = nummer
        if nummer == 0:
            inhalt.content = erklaeren_ansicht
        elif nummer == 1:
            inhalt.content = woerter_ansicht
            liste_fuellen()
        else:
            inhalt.content = abfrage_ansicht
            runde_starten()
        seite.update()

    navigation = ft.NavigationBar(
        selected_index=0,
        on_change=lambda e: ansicht_wechseln(e.control.selected_index),
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.AUTO_AWESOME,
                                        label=t("btn_erklaeren")),
            ft.NavigationBarDestination(icon=ft.Icons.LIST_ALT,
                                        label=t("btn_woerter")),
            ft.NavigationBarDestination(icon=ft.Icons.SCHOOL,
                                        label=t("abfrage_start")),
        ],
    )

    statuszeile = ft.Text("", size=11, opacity=0.6)

    def status_aktualisieren():
        statuszeile.value = t("status",
                              modell=kern.aktives_modell or "—",
                              sprache=kern.konfig.get("antwortsprache",
                                                      "Deutsch"),
                              anzahl=kern.konfig.get("zaehler_stand", 0))

    def melden(text):
        seite.show_dialog(ft.SnackBar(ft.Text(text)))

    seite.appbar = ft.AppBar(
        leading=ft.Icon(ft.Icons.MENU_BOOK),
        leading_width=44,
        title=ft.Text(t("titel")),
        actions=[
            statuszeile,
            merken(ft.IconButton(ft.Icons.SETTINGS,
                                 tooltip=t("menue_einstellungen"),
                                 on_click=einstellungen_oeffnen),
                   "menue_einstellungen", "tooltip"),
            # Dieses Menue ist der Rueckweg, falls das Tray-Symbol fehlt.
            # Ohne es kaeme man nicht mehr aus dem Programm heraus.
            ft.PopupMenuButton(items=[
                merken(ft.PopupMenuItem(
                    content=t("menue_woerter"),
                    on_click=lambda e: ansicht_wechseln(1)),
                    "menue_woerter", "content"),
                merken(ft.PopupMenuItem(
                    content=t("menue_hinweis"),
                    on_click=lambda e: hinweis_zeigen()),
                    "menue_hinweis", "content"),
                merken(ft.PopupMenuItem(
                    content=t("menue_update"),
                    on_click=lambda e: threading.Thread(
                        target=kern.update_pruefen, args=(False,),
                        daemon=True).start()),
                    "menue_update", "content"),
                ft.PopupMenuItem(),
                merken(ft.PopupMenuItem(
                    content=t("menue_beenden"),
                    on_click=lambda e: programm_beenden()),
                    "menue_beenden", "content"),
            ]),
            ft.Container(width=8),
        ],
    )
    seite.navigation_bar = navigation
    seite.add(ft.Column([ladebalken, inhalt], expand=True, spacing=0))

    def neu_aufbauen():
        """
        Nach geaenderten Einstellungen: Beschriftungen, Farben, Schriften.

        Die Reihenfolge ist entscheidend. Zuerst wird alles im Fenster
        geaendert und mit seite.update() abgeschickt, ERST DANACH das
        Tray-Symbol angefasst. Andersherum kann ein Fehler beim Tray dazu
        fuehren, dass seite.update() nie erreicht wird - die Beschriftungen
        sind dann zwar im Speicher geaendert, kommen aber nie am Bildschirm
        an. Genau das war der Grund, warum der Sprachwechsel unter Windows
        nicht griff, im Test mit Attrappe aber schon.
        """
        try:
            thema_setzen()
            seite.title = t("titel")
            if seite.appbar is not None and seite.appbar.title is not None:
                seite.appbar.title.value = t("titel")

            for ziel, schluessel in zip(navigation.destinations,
                                        ("btn_erklaeren", "btn_woerter",
                                         "abfrage_start")):
                ziel.label = t(schluessel)

            beschriftungen_auffrischen()

            antwort.md_style_sheet = markdown_stil()
            eingabe.hint_text = t("platzhalter")
            eingabe.text_size = gr()
            suche.hint_text = t("woerter_suche")
            suche.text_size = gr()

            # Eine vorhandene Antwort NICHT wegwerfen, nur weil jemand die
            # Schriftgroesse geaendert hat
            if not kern.sitzung.get("bild"):
                bereit_anzeigen()

            gefragt.size = gr(11)
            antwortfeld.text_size = gr(6)
            abfrage_rueckmeldung.size = gr(4)

            # Der Abfrageknopf heisst je nach Zustand anders
            abfrage_knopf.content = (t("abfrage_nochmal") if runde["fertig"]
                                     else t("abfrage_weiter")
                                     if runde["beantwortet"]
                                     else t("abfrage_pruefen"))

            liste_fuellen()
            status_aktualisieren()
        except Exception as fehler:
            kern.log(f"Neuaufbau der Oberflaeche: {fehler}")

        # Fenster abschicken, bevor irgendetwas anderes schiefgehen kann
        try:
            seite.update()
        except Exception as fehler:
            kern.log(f"seite.update im Neuaufbau: {fehler}")

        # Tray zuletzt und im Hintergrund. Klemmt es dort, ist das Fenster
        # trotzdem schon richtig beschriftet.
        threading.Thread(target=tray_neu_aufbauen, daemon=True).start()

    # -----------------------------------------------------------------------
    #  Meldungen aus dem Kern abholen
    # -----------------------------------------------------------------------

    async def meldungen_abholen():
        import asyncio
        while not kern.beenden.is_set():
            try:
                while True:
                    befehl, daten = kern.ui.get_nowait()

                    if befehl == "laden":
                        ladebalken.visible = True
                        antwort.value = daten
                        wortkarten.controls.clear()
                        seite.window.visible = True
                        seite.update()

                    elif befehl == "verstecken":
                        seite.window.visible = False
                        seite.update()

                    elif befehl == "zeigen":
                        seite.window.visible = True
                        seite.window.to_front()
                        seite.update()

                    elif befehl == "antwort":
                        text, neu = daten
                        ladebalken.visible = False
                        if neu:
                            antwort.value = text
                            wortkarten.controls.clear()
                        else:
                            antwort.value += "\n\n" + text
                        kern.konfig["zaehler_stand"] = kern.konfig.get(
                            "zaehler_stand", 0)
                        status_aktualisieren()
                        seite.window.visible = True
                        ansicht_wechseln(0)

                    elif befehl == "woerter":
                        gefundene, neue = daten
                        wortkarten.controls.clear()
                        for wort, erklaerung in gefundene:
                            wortkarten.controls.append(ft.Card(
                                content=ft.Container(padding=12, content=ft.Row([
                                    ft.Icon(ft.Icons.BOOKMARK_BORDER, size=18),
                                    ft.Column([
                                        ft.Text(wort,
                                                weight=ft.FontWeight.BOLD,
                                                size=gr()),
                                        ft.Text(erklaerung, size=gr(-2),
                                                opacity=0.8),
                                    ], spacing=2, expand=True),
                                ], spacing=12))))
                        if neue:
                            melden(t("woerter_neu", anzahl=neue))
                        liste_fuellen()
                        seite.update()

                    elif befehl == "neu":
                        neu_aufbauen()

                    elif befehl == "einstellungen":
                        einstellungen_oeffnen()

                    elif befehl == "woerter_fenster":
                        seite.window.visible = True
                        ansicht_wechseln(1)

                    elif befehl == "abfrage":
                        seite.window.visible = True
                        ansicht_wechseln(2)

                    elif befehl == "hinweis":
                        hinweis_zeigen()

                    elif befehl == "update":
                        update_balken_zeigen(daten)

                    elif befehl == "meldung":
                        melden(daten[0] if isinstance(daten, tuple) else daten)

                    elif befehl == "pruefergebnis":
                        klappt, angabe = daten
                        if pruefanzeige is not None:
                            pruefanzeige.value = (
                                t("ein_test_ok", modell=angabe) if klappt
                                else t("ein_test_fehler", grund=angabe))
                            pruefanzeige.color = (ft.Colors.GREEN if klappt
                                                  else ft.Colors.RED)
                            seite.update()

                    elif befehl == "ende":
                        seite.window.destroy()
                        return

            except queue.Empty:
                pass
            await asyncio.sleep(0.1)

    def update_balken_zeigen(angaben):
        balken = ft.Container(
            bgcolor=ft.Colors.PRIMARY_CONTAINER, padding=10,
            content=ft.Row([
                ft.Icon(ft.Icons.SYSTEM_UPDATE, size=18),
                ft.Text(t("update_da", version=angaben["version"]),
                        expand=True, size=12),
                ft.TextButton(t("update_holen"),
                              on_click=lambda e: webbrowser.open(
                                  angaben["seite"])),
                ft.IconButton(ft.Icons.CLOSE, icon_size=16,
                              on_click=lambda e: (
                                  seite.controls[0].controls.remove(balken),
                                  seite.update())),
            ], spacing=8))
        seite.controls[0].controls.insert(0, balken)
        seite.update()

    # -----------------------------------------------------------------------
    #  Tray-Symbol
    # -----------------------------------------------------------------------

    def programm_beenden(icon=None, item=None):
        """
        Beendet das Programm. Absichtlich mit Holzhammer am Schluss:
        Wenn das Fenster nicht schliesst oder ein Faden haengt, muss der
        Benutzer trotzdem wieder herauskommen - sonst laeuft das Programm
        unsichtbar weiter und laesst sich nur ueber den Task-Manager
        beenden.
        """
        kern.beenden_anfordern()

        symbol = tray.get("symbol")
        if symbol is not None:
            try:
                symbol.stop()
            except Exception as fehler:
                kern.log(f"Tray liess sich nicht beenden: {fehler}")
        tray["symbol"] = None
        tray["laeuft"] = False

        try:
            seite.window.destroy()
        except Exception as fehler:
            kern.log(f"Fenster liess sich nicht schliessen: {fehler}")

        # Notausgang: laeuft der Prozess nach zwei Sekunden noch, hart raus
        def nachfassen():
            time.sleep(2)
            kern.log("Beenden erzwungen")
            os._exit(0)

        threading.Thread(target=nachfassen, daemon=True).start()

    tray = {"symbol": None, "laeuft": False}

    def tray_neu_aufbauen():
        """
        Das Tray-Menue wird beim Anlegen beschriftet und laesst sich
        nachtraeglich nicht umbenennen. Beim Sprachwechsel also altes
        Symbol beenden und ein neues anlegen.
        """
        altes = tray.get("symbol")
        if altes is None:
            return
        try:
            altes.stop()
            tray["symbol"] = None
            time.sleep(0.3)          # dem alten Symbol Zeit zum Verschwinden
            tray_starten()
        except Exception as fehler:
            kern.log(f"Tray-Menue nicht erneuerbar: {fehler}")

    def tray_starten():
        symbol = pystray.Icon(
            "schulhelfer", kern.tray_bild(), t("titel"),
            menu=pystray.Menu(
                pystray.MenuItem(t("menue_fenster"),
                                 lambda: kern.ui.put(("zeigen", None)),
                                 default=True),
                pystray.MenuItem(t("menue_woerter"),
                                 lambda: kern.ui.put(("woerter_fenster", None))),
                pystray.MenuItem(t("abfrage_start"),
                                 lambda: kern.ui.put(("abfrage", None))),
                pystray.MenuItem(t("menue_einstellungen"),
                                 lambda: kern.ui.put(("einstellungen", None))),
                pystray.MenuItem(t("menue_hinweis"),
                                 lambda: kern.ui.put(("hinweis", None))),
                pystray.MenuItem(t("menue_update"), lambda: threading.Thread(
                    target=kern.update_pruefen, args=(False,),
                    daemon=True).start()),
                pystray.MenuItem(t("menue_beenden"), programm_beenden),
            ))
        tray["symbol"] = symbol

        def starten():
            try:
                symbol.run()
            except Exception as fehler:
                # Im gepackten Programm kann das Tray fehlschlagen. Dann
                # soll nur das Symbol fehlen, nicht das ganze Programm.
                tray["laeuft"] = False
                kern.log(f"Tray-Symbol nicht verfuegbar: {fehler}")

        threading.Thread(target=starten, daemon=True).start()
        tray["laeuft"] = True

    # Beim Schliessen nur verstecken - das Programm wartet weiter auf
    # das Tastenkuerzel
    def fenster_ereignis(e):
        """
        Flet meldet die Ereignisart in e.type als Aufzaehlungswert, nicht
        als Text in e.data. Ein Vergleich mit "close" ist nie wahr - dann
        reagiert das X gar nicht und das Fenster laesst sich nicht mehr
        schliessen. Darum hier beide Wege pruefen.
        """
        art = getattr(getattr(e, "type", None), "value", None) \
            or getattr(e, "data", None)
        if art != "close":
            return
        if tray.get("laeuft"):
            # Es gibt ein Tray-Symbol - also nur verstecken und Bescheid
            # sagen, wo das Programm hin ist.
            seite.window.visible = False
            seite.update()
            melden(t("weg_text"))
        else:
            # Kein Tray, kein Rueckweg - dann muss das X wirklich beenden
            programm_beenden()

    seite.window.prevent_close = True
    seite.window.on_event = fenster_ereignis

    # -----------------------------------------------------------------------
    #  Los
    # -----------------------------------------------------------------------

    bereit_anzeigen()
    status_aktualisieren()
    seite.update()

    seite.run_task(meldungen_abholen)
    tray_starten()
    kern.hintergrund_starten()

    hat_schluessel = kern.klient_aufbauen()

    # Erststart in vier Schritten:
    #   Sprache waehlen -> was das Programm tut -> Datenschutz -> Schluessel
    def schritt_schluessel():
        if not hat_schluessel:
            einstellungen_oeffnen()

    def schritt_datenschutz():
        if kern.konfig.get("hinweis_gelesen"):
            schritt_schluessel()
        else:
            hinweis_zeigen(beim_ersten_mal=True, danach=schritt_schluessel)

    def schritt_willkommen():
        willkommen_zeigen(danach=schritt_datenschutz)

    if kern.konfig.get("sprache_gewaehlt"):
        schritt_datenschutz()
    else:
        sprachwahl_zeigen(danach=schritt_willkommen)


def start():
    kern.konfig_laden()
    if kern.schon_gestartet():
        return
    ft.run(main)


if __name__ == "__main__":
    start()