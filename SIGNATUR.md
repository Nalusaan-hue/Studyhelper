# Signatur-Richtlinie / Code signing policy

Diese Seite ist Bedingung für die kostenlose Signatur durch die
SignPath Foundation. Sie erklärt, wer am Programm arbeitet, wer eine
Signatur freigibt und was das Programm mit Daten macht.

*This page is required for free code signing by SignPath Foundation.*

---

## Signatur

Kostenlose Signatur durch [SignPath.io](https://signpath.io/),
Zertifikat von der [SignPath Foundation](https://signpath.org/).

*Free code signing provided by [SignPath.io](https://signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).*

> Solange die Bewerbung bei SignPath nicht bewilligt ist, sind die
> veröffentlichten Dateien **nicht signiert**. Windows zeigt dann die
> übliche Warnung «Der Computer wurde durch Windows geschützt».
> Das ist keine Virusmeldung.

## Wer was darf

| Rolle | Person | Aufgabe |
|---|---|---|
| Author | Miguel Angel Martinez | schreibt den Code |
| Reviewer | Miguel Angel Martinez | prüft Änderungen von aussen |
| Approver | Miguel Angel Martinez | gibt jede Signatur einzeln frei |

Das Projekt hat zurzeit einen einzigen Betreuer. Kommen weitere dazu,
wird diese Tabelle ergänzt, bevor sie Schreibrechte erhalten.

Zugang zu GitHub und zu SignPath ist mit Zwei-Faktor-Anmeldung geschützt.

## Wie gebaut wird

Die veröffentlichten Dateien entstehen ausschliesslich durch
`.github/workflows/bauen.yml` auf einem Rechner von GitHub, aus dem
Quellcode in diesem Verzeichnis. Es wird nichts von Hand gebaut und
nichts von einem privaten Rechner hochgeladen.

Die Versionsnummer steht an einer einzigen Stelle: `aktualisierung.py`,
`VERSION`. Bau und Installationspaket lesen sie von dort.

## Was das Programm mit Daten macht

Hier gilt **nicht** der Standardsatz «überträgt keine Daten». Das
Programm überträgt Daten, und zwar genau dann, wenn die Person die
Tastenkombination drückt:

- Ein Bild des Bildschirms geht an die Gemini-Schnittstelle von Google,
  damit der Inhalt erklärt werden kann. Ohne Tastendruck passiert das
  nicht. Es läuft keine Aufnahme im Hintergrund.
- Im kostenlosen Kontingent von Google werden diese Daten von Google zur
  Verbesserung seiner Modelle verwendet. Darum gehört nichts Privates oder
  Vertrauliches in eine Erklärung.
- Einmal am Tag wird die Release-Seite dieses Projekts auf GitHub
  abgefragt, um zu sehen, ob eine neuere Fassung vorliegt. Dabei gehen
  keine Daten über die Person mit, nur die Versionsnummer im
  User-Agent.
- Der Gemini-Schlüssel, die Wörterliste und die Einstellungen bleiben
  auf dem eigenen Rechner, unter `%APPDATA%\Schulhelfer`. Der Schlüssel
  ist mit der Windows-Funktion DPAPI verschlüsselt und nur für das
  eigene Windows-Konto lesbar. Es gibt keinen Server des Projekts.

Das Programm enthält keine Werbung, keine Nutzungsstatistik, keine
Schadsoftware und nimmt keine Änderungen am System vor. Deinstallieren
heisst: den Ordner löschen.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Alle Bestandteile sind Open Source.
