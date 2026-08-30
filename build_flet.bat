@echo off
REM ===================================================================
REM  Schulhelfer (Flet) bauen
REM
REM  Anders als bei Tkinter kommt hier NICHT PyInstaller zum Einsatz,
REM  sondern Flets eigener Befehl. Der braucht beim ersten Mal das
REM  Flutter-SDK und die Visual-Studio-Buildtools - mehrere Gigabyte,
REM  und der erste Durchlauf dauert entsprechend lang.
REM ===================================================================

pushd "%~dp0"

set PY=
call :versuche python
if defined PY goto weiter
call :versuche py -3
if defined PY goto weiter
call :versuche python3
if defined PY goto weiter
echo   Python wurde nicht gefunden.
pause & exit /b 1

:versuche
%* --version >nul 2>&1
if not errorlevel 1 set PY=%*
exit /b

:weiter
echo.
echo [1/2] Abhaengigkeiten installieren
%PY% -m pip install --upgrade flet google-genai pillow pystray
if errorlevel 1 goto fehler

echo.
echo [2/2] Windows-Programm bauen

REM  "python -m flet" geht nicht - das Paket hat keinen Modul-Einstieg.
REM  Darum flet.exe suchen. Die liegt im Scripts-Ordner der jeweiligen
REM  Python-Installation, der oft nicht im PATH steht.
set FLET=
where flet.exe >nul 2>&1
if not errorlevel 1 set FLET=flet.exe

if not defined FLET (
  for /f "delims=" %%s in ('%PY% -c "import sysconfig,os;print(os.path.join(sysconfig.get_path('scripts'),'flet.exe'))"') do (
    if exist "%%s" set FLET=%%s
  )
)

if not defined FLET (
  for /f "delims=" %%s in ('%PY% -c "import sysconfig,os;print(os.path.join(sysconfig.get_path('scripts','nt_user'),'flet.exe'))"') do (
    if exist "%%s" set FLET=%%s
  )
)

if not defined FLET goto kein_flet
echo   Benutze: %FLET%
echo.

"%FLET%" build windows ^
  --module-name schulhelfer_flet ^
  --product "Schulhelfer" ^
  --company "Schulprojekt" ^
  --copyright "Freies Schulprojekt" ^
  --build-version 1.0.0
if errorlevel 1 goto fehler

echo.
echo   Fertig. Das Programm liegt unter:
echo   %CD%\build\windows\
echo.
popd
pause
exit /b 0

:kein_flet
echo.
echo   flet.exe wurde nicht gefunden.
echo.
echo   Installier es mit:  %PY% -m pip install flet
echo   Falls es installiert ist, liegt es im Scripts-Ordner
echo   deiner Python-Installation - den kannst du dem PATH
echo   hinzufuegen.
echo.
popd
pause
exit /b 1

:fehler
echo.
echo   Fehler beim Bauen. Meldung siehe oben.
echo.
echo   Beim ersten Mal fehlen meist Flutter oder die
echo   Visual-Studio-Buildtools. Flet sagt in der Ausgabe,
echo   was genau gebraucht wird.
echo.
popd
pause
exit /b 1
