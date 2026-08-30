@echo off
setlocal enabledelayedexpansion
REM ===================================================================
REM  Schulhelfer (Flet) bauen
REM
REM  Beim ersten Mal laedt Flet das Flutter-SDK herunter und braucht
REM  die Visual Studio Build Tools mit "Desktopentwicklung mit C++".
REM  Das dauert. Danach geht es schnell.
REM ===================================================================

pushd "%~dp0"
if errorlevel 1 goto unc_fehler

echo.
echo   Schulhelfer wird gebaut
echo   Ordner: %CD%
echo.

REM ---- Python suchen -----------------------------------------------
set PY=

call :versuche python
if defined PY goto python_da
call :versuche py -3
if defined PY goto python_da
call :versuche python3
if defined PY goto python_da

REM  Feste Orte absuchen
for %%p in (
  "%LOCALAPPDATA%\Python\bin\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%ProgramFiles%\Python314\python.exe"
  "%ProgramFiles%\Python313\python.exe"
  "%ProgramFiles%\Python312\python.exe"
) do (
  if exist %%p (
    set PY=%%p
    goto python_da
  )
)

REM  Der Python-Installationsverwalter legt Ordner wie
REM  "pythoncore-3.14-64" an - deren Namen kennen wir nicht im Voraus,
REM  darum hier mit Platzhalter suchen.
for /d %%d in ("%LOCALAPPDATA%\Python\pythoncore-*") do (
  if exist "%%d\python.exe" (
    set PY="%%d\python.exe"
    goto python_da
  )
)
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
  if exist "%%d\python.exe" (
    set PY="%%d\python.exe"
    goto python_da
  )
)

goto kein_python

:versuche
%* --version >nul 2>&1
if not errorlevel 1 set PY=%*
exit /b

:python_da
for /f "tokens=*" %%v in ('%PY% --version 2^>^&1') do echo   Python: %%v
echo   Pfad:   %PY%
echo.

REM ---- Dateien vollstaendig? ---------------------------------------
if not exist "schulhelfer_flet.py" goto fehlt_datei
if not exist "kern.py"             goto fehlt_datei
if not exist "lernapp.py"          goto fehlt_datei
if not exist "aktualisierung.py"   goto fehlt_datei
if not exist "assets\icon.png" (
  echo   Hinweis: assets\icon.png fehlt - es wird ohne eigenes Symbol gebaut.
  echo.
)

echo [1/2] Abhaengigkeiten installieren
%PY% -m pip install --upgrade flet google-genai pillow pystray
if errorlevel 1 goto fehler

echo.
echo [2/2] Windows-Programm bauen

REM  "python -m flet" geht nicht, das Paket hat keinen Modul-Einstieg.
REM  Also flet.exe suchen. Achtung: Die Pakete koennen in einem anderen
REM  Ordner liegen als der python-Befehl selbst - beim Python-
REM  Installationsverwalter ist genau das der Fall.
set FLET=

where flet.exe >nul 2>&1
if not errorlevel 1 (
  set FLET=flet.exe
  goto flet_da
)

for %%p in (
  "%LOCALAPPDATA%\Python\bin\flet.exe"
  "%LOCALAPPDATA%\Python\Scripts\flet.exe"
) do (
  if exist %%p (
    set FLET=%%p
    goto flet_da
  )
)

for /d %%d in ("%LOCALAPPDATA%\Python\pythoncore-*") do (
  if exist "%%d\Scripts\flet.exe" (
    set FLET="%%d\Scripts\flet.exe"
    goto flet_da
  )
)

for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
  if exist "%%d\Scripts\flet.exe" (
    set FLET="%%d\Scripts\flet.exe"
    goto flet_da
  )
)

for /d %%d in ("%ProgramFiles%\Python3*") do (
  if exist "%%d\Scripts\flet.exe" (
    set FLET="%%d\Scripts\flet.exe"
    goto flet_da
  )
)

REM  Zuletzt Python selbst fragen. usebackq ist noetig, damit die
REM  Anfuehrungszeichen im Befehl nicht zerlegt werden.
for /f "usebackq delims=" %%s in (`%PY% -c "import sysconfig,os;print(os.path.join(sysconfig.get_path('scripts'),'flet.exe'))"`) do (
  if exist "%%s" (
    set FLET="%%s"
    goto flet_da
  )
)

if not defined FLET goto kein_flet

:flet_da
echo   Flet:   %FLET%

REM ---- PowerShell 7 sicherstellen ----------------------------------
REM  Flutter ruft beim Bauen "pwsh" auf. Ist der Ordner nicht im PATH
REM  dieser Eingabeaufforderung, bricht der Bau mit
REM  "Unable to determine engine version" ab - obwohl pwsh installiert
REM  ist und in PowerShell funktioniert.
where pwsh.exe >nul 2>&1
if not errorlevel 1 goto pwsh_da

for %%p in (
  "%ProgramFiles%\PowerShell\7\pwsh.exe"
  "%ProgramFiles(x86)%\PowerShell\7\pwsh.exe"
  "%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe"
) do (
  if exist %%p (
    for %%d in (%%p) do set "PATH=%%~dpd;!PATH!"
    echo   PowerShell 7 ergaenzt: %%p
    goto pwsh_da
  )
)

for /d %%d in ("%ProgramFiles%\PowerShell\*") do (
  if exist "%%d\pwsh.exe" (
    set "PATH=%%d;!PATH!"
    echo   PowerShell 7 ergaenzt: %%d
    goto pwsh_da
  )
)

echo.
echo   ACHTUNG: pwsh wurde nicht gefunden.
echo   Flutter braucht PowerShell 7 zum Bauen. Falls der Bau gleich
echo   mit "Unable to determine engine version" abbricht, installier
echo   es mit:  winget install Microsoft.PowerShell
echo.

:pwsh_da
echo.

%FLET% build windows ^
  --module-name schulhelfer_flet ^
  --product "Schulhelfer" ^
  --company "Schulprojekt" ^
  --copyright "Freies Schulprojekt" ^
  --build-version 1.0.0
if errorlevel 1 goto fehler

if not exist "build\windows" goto nichts_gebaut

echo.
echo   ============================================================
echo    Fertig. Das Programm liegt in:
echo    %CD%\build\windows\
echo.
echo    Zum Weitergeben zippen:
echo    Compress-Archive -Path build\windows\* -DestinationPath Schulhelfer.zip -Force
echo   ============================================================
echo.
popd
pause
exit /b 0

:kein_python
echo.
echo   Python wurde nicht gefunden.
echo.
echo   Falls es in PowerShell funktioniert, fehlt nur der PATH-Eintrag.
echo   Dann diesen Befehl in PowerShell in diesem Ordner ausfuehren:
echo.
echo     python -c "import sys; print(sys.executable)"
echo.
echo   Schick mir den ausgegebenen Pfad, dann trage ich ihn ein.
echo.
popd
pause
exit /b 1

:kein_flet
echo.
echo   flet.exe wurde nicht gefunden.
echo   Installier es mit:  %PY% -m pip install flet
echo.
popd
pause
exit /b 1

:fehlt_datei
echo.
echo   Es fehlen Dateien in diesem Ordner. Noetig sind:
echo     schulhelfer_flet.py
echo     kern.py
echo     lernapp.py
echo     aktualisierung.py
echo     assets\icon.png
echo.
popd
pause
exit /b 1

:nichts_gebaut
echo.
echo   Flet meldete keinen Fehler, aber build\windows fehlt.
echo   Schau in der Ausgabe oben nach der Ursache.
echo.
popd
pause
exit /b 1

:unc_fehler
echo.
echo   Der Ordner liegt auf einem Netzlaufwerk. Kopier ihn nach
echo   C:\Schulhelfer und starte build_flet.bat dort noch einmal.
echo.
pause
exit /b 1

:fehler
echo.
echo   Fehler beim Bauen. Die Meldung steht oben.
echo.
echo   Beim ersten Mal fehlen meist Flutter oder die Visual Studio
echo   Build Tools. Flet sagt in der Ausgabe, was gebraucht wird.
echo.
popd
pause
exit /b 1