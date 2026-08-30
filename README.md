# Schulhelfer

**Erklärt auf Tastendruck in einfacher Sprache, was auf dem Bildschirm steht.**

Für alle, die einen Text nicht auf Anhieb verstehen — weil er in einer
Fremdsprache ist, weil er voller Fachbegriffe steckt, oder weil er einfach
kompliziert geschrieben wurde.

*Explains what's on your screen in plain language · Explica en lenguaje
sencillo lo que hay en tu pantalla*

---

## Was es macht

Du liest etwas und verstehst es nicht. Du drückst `Strg + Alt + Q`. Das
Programm liest deinen Bildschirm und erklärt ihn dir — in kurzen Sätzen und
mit Alltagswörtern.

Dabei bleiben Fachbegriffe **im Original stehen**, mit der Bedeutung in
Klammern dahinter. Wer eine deutsche Aufgabe auf Spanisch erklärt bekommt,
findet jedes erklärte Wort auf seinem Bildschirm wieder. Das ist der
Unterschied zu einer Übersetzung.

### Nachfragen ohne Formulieren

Vier Knöpfe für die Fälle, in denen einem die Worte fehlen:

**Noch einfacher** · **Beispiel geben** · **Wort für Wort** ·
**Was soll ich tun?**

Wer lieber tippt, kann daneben frei fragen. Der Bildschirm bleibt dabei im
Gespräch — man kann mehrfach nachhaken.

### Aus Nichtverstehen wird Vokabular

Jede Erklärung sammelt die schwierigen Wörter automatisch in einer Liste.
Die lässt sich durchsuchen, sortieren und **abfragen**: Die Erklärung
erscheint, du tippst das Wort. Tippfehler zählen als richtig — ein
Buchstabendreher ist kein Nichtwissen. Wörter, bei denen du dich oft geirrt
hast, kommen häufiger dran.

Mit einem Klick wird daraus eine Datei fürs Handy: eine einzelne HTML-Seite
mit allen Wörtern und der kompletten Abfrage. Läuft offline im Browser, ohne
Installation und ohne Schlüssel. Der PC sammelt, das Handy übt.

---

## Sprachen

Programmsprache **Deutsch · English · Español**, Antwortsprache getrennt
einstellbar, zusätzlich Français und Italiano.

Der Bildschirm darf also deutsch sein und die Erklärung spanisch.

Beim ersten Start fragt das Programm nach der Sprache, bevor es irgendetwas
anderes anzeigt — wer die Sprache noch nicht gewählt hat, versteht ja
womöglich keine der drei.

---

## Installieren

1. Neueste Fassung unter **[Releases](../../releases/latest)** herunterladen
   und entpacken.
2. `Schulhelfer.exe` starten.
3. Beim ersten Start durch die Einrichtung klicken. Du brauchst einen
   eigenen Gemini-Schlüssel — kostenlos, ein Google-Konto genügt, keine
   Kreditkarte. Das Programm führt dich hin.

Windows 10 oder 11, 64 Bit. Python muss nicht installiert sein.

Beim ersten Start warnt Windows vor unbekannter Software. Das ist keine
Virusmeldung, sondern die übliche Warnung bei Programmen ohne gekauftes
Zertifikat: „Weitere Informationen" → „Trotzdem ausführen".

---

## Warum jeder seinen eigenen Schlüssel braucht

Ein Schlüssel lässt sich in einem Programm nicht verstecken — alles, was in
der Datei steckt, kann man wieder herausholen. Und alle würden über dasselbe
Kontingent laufen.

Dein Schlüssel wird verschlüsselt in deinem Windows-Benutzerprofil abgelegt
und verlässt deinen Rechner nicht. Das kostenlose Kontingent reicht für rund
500 Erklärungen pro Tag.

---

## Was du wissen solltest

Das Programm schickt ein Bild deines Bildschirms an Google. Im kostenlosen
Kontingent verwendet Google diese Daten zur Verbesserung seiner Modelle.
Also nichts erklären lassen, was privat oder vertraulich ist — keine
Nachrichten, keine Passwörter, keine Daten anderer Leute.

Und: Die Antworten können falsch sein. Das Programm ist eine
Verständnishilfe, kein Nachschlagewerk. Bei Zahlen, Fristen und Regeln
gehört die Angabe in der Originalquelle nachgeprüft.

---

## Selbst bauen

Anleitung zum Bauen, zum MSI-Paket und zum Veröffentlichen:
siehe [LIESMICH.md](LIESMICH.md).

```
pip install flet google-genai pillow pystray
python schulhelfer_flet.py
```

Geschrieben in Python mit [Flet](https://flet.dev). Die gesamte Logik steckt
in `kern.py` und kennt keine Oberfläche — deshalb liess sich die Oberfläche
von Tkinter auf Flet umstellen, ohne den Kern anzufassen.

---

Entstanden als privates Projekt für Mitschülerinnen und Mitschüler, die im
Unterricht mehr mit der Sprache kämpfen als mit dem Stoff.
