# -*- coding: utf-8 -*-
"""
Baut aus dist\\Schulhelfer ein MSI-Paket.

Warum ein eigenes Skript? Der Ordner _internal enthaelt hunderte Dateien,
und WiX braucht fuer jede einzelne einen Eintrag. Von Hand ist das nicht
zu pflegen - dieses Skript liest den Ordner und schreibt die Quelldatei
jedes Mal neu.

Voraussetzungen:
  1. build.bat wurde ausgefuehrt, dist\\Schulhelfer existiert
  2. WiX ist installiert:  dotnet tool install --global wix

Aufruf:
    python msi_bauen.py

Ergebnis: Schulhelfer.msi

Das Paket installiert OHNE Administratorrechte ins Benutzerprofil. Das ist
Absicht: So laesst es sich auch dort verteilen, wo Schueler keine
Adminrechte haben.
"""

import subprocess
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

# ---------------------------------------------------------------------------
#  Einstellungen
# ---------------------------------------------------------------------------

NAME = "Schulhelfer"
VERSION = "1.0.0.0"
HERSTELLER = "Schulprojekt"
EXE = "Schulhelfer.exe"

# Diese Kennung darf sich NIE aendern. Windows erkennt daran, dass eine
# neue Fassung die alte ersetzt statt zusaetzlich installiert zu werden.
UPGRADE_CODE = "6B2E9D14-7A83-4C05-9F61-3D8A24E7B0C9"

# Woher kommen die gebauten Dateien?
#   Flet:       build\\windows
#   PyInstaller: dist\\Schulhelfer
# Als Argument uebergeben:  python msi_bauen.py build\\windows
QUELLE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build") / "windows"
WXS_DATEI = Path(f"{NAME}.wxs")
MSI_DATEI = Path(f"{NAME}.msi")


# ---------------------------------------------------------------------------
#  Kennungen erzeugen
# ---------------------------------------------------------------------------

def kennung(pfad):
    """
    Macht aus einem Pfad eine gueltige WiX-Kennung. Die darf nur Buchstaben,
    Ziffern, Punkt und Unterstrich enthalten und muss eindeutig sein.
    """
    sauber = "".join(c if c.isalnum() else "_" for c in str(pfad))
    # Kurzer Hash haengt hinten dran, damit lange Pfade nicht kollidieren
    kurz = uuid.uuid5(uuid.NAMESPACE_URL, str(pfad)).hex[:8]
    return f"f{sauber[-60:]}_{kurz}"


# ---------------------------------------------------------------------------
#  Verzeichnisbaum und Dateien aufbauen
# ---------------------------------------------------------------------------

def baum_aufbauen(wurzel):
    """
    Geht den Ordner durch und liefert zwei Textstuecke zurueck:
    die Verzeichnisstruktur und die Liste der Bestandteile.
    """
    verzeichnisse = []
    bestandteile = []

    def durchgehen(ordner, eltern_kennung, tiefe):
        einzug = "  " * (tiefe + 4)

        # Erst die Dateien in diesem Ordner
        for datei in sorted(p for p in ordner.iterdir() if p.is_file()):
            relativ = datei.relative_to(wurzel)
            k = kennung(relativ)
            bestandteile.append(
                f'      <Component Id="c{k}" Directory="{eltern_kennung}">\n'
                f'        <File Id="{k}" Source="{escape(str(datei))}" '
                f'KeyPath="yes" />\n'
                f'      </Component>'
            )

        # Dann die Unterordner
        for unter in sorted(p for p in ordner.iterdir() if p.is_dir()):
            relativ = unter.relative_to(wurzel)
            k = "d" + kennung(relativ)
            verzeichnisse.append(
                f'{einzug}<Directory Id="{k}" Name="{escape(unter.name)}">')
            durchgehen(unter, k, tiefe + 1)
            verzeichnisse.append(f'{einzug}</Directory>')

    durchgehen(wurzel, "INSTALLFOLDER", 0)
    return "\n".join(verzeichnisse), "\n".join(bestandteile)


# ---------------------------------------------------------------------------
#  Quelldatei schreiben
# ---------------------------------------------------------------------------

VORLAGE = """<?xml version="1.0" encoding="utf-8"?>
<!-- Diese Datei wird von msi_bauen.py erzeugt. Nicht von Hand aendern. -->
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">

  <Package Name="{name}"
           Manufacturer="{hersteller}"
           Version="{version}"
           UpgradeCode="{upgrade}"
           Scope="perUser"
           Compressed="yes">

    <!-- Sorgt dafuer, dass eine neue Fassung die alte ersetzt -->
    <MajorUpgrade AllowSameVersionUpgrades="yes"
        DowngradeErrorMessage="Es ist bereits eine neuere Fassung von {name} installiert." />

    <MediaTemplate EmbedCab="yes" />

    <Icon Id="Programmsymbol" SourceFile="symbol.ico" />
    <Property Id="ARPPRODUCTICON" Value="Programmsymbol" />
    <Property Id="ARPNOREPAIR" Value="1" />

    <!-- Ins Benutzerprofil, damit keine Adminrechte noetig sind -->
    <StandardDirectory Id="LocalAppDataFolder">
      <Directory Id="HERSTELLERORDNER" Name="{hersteller}">
        <Directory Id="INSTALLFOLDER" Name="{name}">
{verzeichnisse}
        </Directory>
      </Directory>
    </StandardDirectory>

    <StandardDirectory Id="ProgramMenuFolder">
      <Directory Id="MENUEORDNER" Name="{name}" />
    </StandardDirectory>

    <Feature Id="Hauptteil" Title="{name}" Level="1">
      <ComponentGroupRef Id="Programmdateien" />
      <ComponentRef Id="Startmenue" />
    </Feature>

    <ComponentGroup Id="Programmdateien">
{bestandteile}
    </ComponentGroup>

    <!-- Verknuepfung im Startmenue. Der Registrierungseintrag ist noetig,
         weil eine Verknuepfung allein kein gueltiger Ankerpunkt ist. -->
    <Component Id="Startmenue" Directory="MENUEORDNER" Guid="*">
      <Shortcut Id="StartmenueVerknuepfung"
                Name="{name}"
                Description="Erklärt den Bildschirm in einfacher Sprache"
                Target="[INSTALLFOLDER]{exe}"
                WorkingDirectory="INSTALLFOLDER"
                Icon="Programmsymbol" />
      <RemoveFolder Id="MenueordnerEntfernen" Directory="MENUEORDNER"
                    On="uninstall" />
      <RegistryValue Root="HKCU"
                     Key="Software\\{hersteller}\\{name}"
                     Name="installiert" Type="integer" Value="1"
                     KeyPath="yes" />
    </Component>

  </Package>
</Wix>
"""


def main():
    if not QUELLE.exists():
        print(f"FEHLER: {QUELLE} gibt es nicht.")
        print("Lass zuerst build_flet.bat laufen.")
        print("Oder gib den Ordner an:  python msi_bauen.py dist\\Schulhelfer")
        return 1

    dateien = sum(1 for _ in QUELLE.rglob("*") if _.is_file())
    print(f"[1/3] {QUELLE} eingelesen: {dateien} Dateien")

    verzeichnisse, bestandteile = baum_aufbauen(QUELLE)

    WXS_DATEI.write_text(VORLAGE.format(
        name=NAME, hersteller=HERSTELLER, version=VERSION,
        upgrade=UPGRADE_CODE, exe=EXE,
        verzeichnisse=verzeichnisse, bestandteile=bestandteile,
    ), encoding="utf-8")
    print(f"[2/3] {WXS_DATEI} geschrieben")

    print("[3/3] WiX wird aufgerufen ...")
    try:
        ergebnis = subprocess.run(
            ["wix", "build", str(WXS_DATEI), "-o", str(MSI_DATEI)],
            capture_output=True, text=True)
    except FileNotFoundError:
        print()
        print("WiX wurde nicht gefunden. Einmalig installieren mit:")
        print("    dotnet tool install --global wix")
        print()
        print(f"Die Quelldatei {WXS_DATEI} ist trotzdem fertig.")
        return 1

    if ergebnis.returncode != 0:
        print("WiX meldet einen Fehler:")
        print(ergebnis.stdout[-2000:])
        print(ergebnis.stderr[-2000:])
        return 1

    groesse = MSI_DATEI.stat().st_size / 1024 / 1024
    print()
    print(f"Fertig: {MSI_DATEI}  ({groesse:.1f} MB)")
    print()
    print("Zum Ausrollen über Intune oder Gruppenrichtlinie geeignet.")
    print("Stille Installation:  msiexec /i Schulhelfer.msi /qn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
