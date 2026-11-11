@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Kurs-Agent - alles holen und starten (Fassung 1.0)
rem ================================================================================
rem  ALLES_GUT_START_1.0.bat  -  Fassung 1.0 vom 11.11.2026
rem  Die EINE Datei fuer einen frischen Windows-Rechner mit Internet.
rem  Sie holt das Kurspaket von GitHub, ein eigenes Python, pip, die Python-Raeder,
rem  llama.cpp, die MicroPython-Firmware, die USB-Treiber und das Sprachmodell -
rem  und startet danach START.bat. Nichts wird auf dem Rechner installiert: alles
rem  liegt in EINEM Ordner (Vorgabe C:\Kurs_Agent). Ordner loeschen = alles weg.
rem
rem  Aufruf:  Doppelklick                      -> Ordner C:\Kurs_Agent
rem           ALLES_GUT_START_1.0.bat D:\Kurs  -> anderer Ordner
rem           ... --ohne-start                 -> nur holen, START.bat nicht aufrufen (Pruefung)
rem
rem  Was schon da ist, wird nicht noch einmal geholt: Abbruch -> einfach erneut starten.
rem  Bordmittel von Windows 10 (ab 1803) und 11: curl.exe, tar.exe, robocopy.
rem  Fortschritt und Befunde stehen danach in <Ordner>\alles_gut_protokoll.txt.
rem ================================================================================
set "FASSUNG=1.0"
set "REPO=Kurs-Agent-Lokale-KI-schreibt-prueft-und-flasht-Programme-ESP32-als-Beispiel"
set "REPOZIP=https://github.com/RalphWystup/%REPO%/archive/refs/heads/main.zip"
set "PYZIP=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "ZIEL=C:\Kurs_Agent"
set "OHNE_START=0"
rem --- Argumente: ein Ordner und/oder --ohne-start, in beliebiger Reihenfolge ---
:argumente
if "%~1"=="" goto argumente_fertig
if /i "%~1"=="--ohne-start" ( set "OHNE_START=1" ) else ( set "ZIEL=%~1" )
shift
goto argumente
:argumente_fertig
rem --- liegt diese Datei schon im Kursordner (START.bat daneben), ist das der Ordner ---
if exist "%~dp0START.bat" set "ZIEL=%~dp0"
if "%ZIEL:~-1%"=="\" set "ZIEL=%ZIEL:~0,-1%"

echo ==============================================================================
echo  KURS-AGENT - alles holen und starten  (Fassung %FASSUNG%)
echo  Ordner: %ZIEL%
echo  Dieses Fenster offen lassen. Das Sprachmodell ist 4,7 GB gross - je nach
echo  Leitung dauert das Holen 5 bis 60 Minuten. Abbruch ist unschaedlich: beim
echo  naechsten Start geht es dort weiter, wo es aufgehoert hat.
echo ==============================================================================
echo.

rem --- 0. Bordmittel pruefen: ohne curl und tar geht hier nichts ---
where curl.exe >nul 2>&1 || ( echo FEHLT: curl.exe. Windows 10 ab Fassung 1803 oder Windows 11 noetig. & goto ende_fehler )
where tar.exe  >nul 2>&1 || ( echo FEHLT: tar.exe. Windows 10 ab Fassung 1803 oder Windows 11 noetig. & goto ende_fehler )
if not exist "%ZIEL%" mkdir "%ZIEL%" 2>nul
if not exist "%ZIEL%" ( echo Der Ordner %ZIEL% laesst sich nicht anlegen. & goto ende_fehler )
cd /d "%ZIEL%" || goto ende_fehler

rem --- 1. Das Kurspaket (Quelltexte, Seite, Werkzeuge) von GitHub - etwa 4 MB ---
if exist "START.bat" (
  echo Schritt 1 von 4: Kurspaket liegt schon da ^(START.bat vorhanden^).
) else (
  echo Schritt 1 von 4: Kurspaket von GitHub holen ...
  if not exist "kurs_agent_main.zip" (
    curl.exe -L --fail --retry 3 --retry-delay 5 -# -o "kurs_agent_main.zip" "%REPOZIP%" || ( echo Das Kurspaket liess sich nicht holen: %REPOZIP% & goto ende_fehler )
  ) else (
    echo    kurs_agent_main.zip liegt schon da - wird genommen.
  )
  tar.exe -xf "kurs_agent_main.zip" || ( echo kurs_agent_main.zip laesst sich nicht entpacken - Datei loeschen und erneut starten. & goto ende_fehler )
  if not exist "%REPO%-main\START.bat" ( echo Im Archiv fehlt %REPO%-main\START.bat. & goto ende_fehler )
  robocopy "%REPO%-main" "." /E /MOVE /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 ( echo Die Dateien liessen sich nicht in %ZIEL% verschieben. & goto ende_fehler )
  if exist "%REPO%-main" rmdir /s /q "%REPO%-main"
  del "kurs_agent_main.zip"
  echo    Kurspaket liegt in %ZIEL%.
)

rem --- 2. Ein eigenes Python (eingebettet, 11 MB) - der Rechner braucht keines ---
set "PY=paket\python_vorlage\python.exe"
if exist "%PY%" (
  echo Schritt 2 von 4: Python liegt schon da ^(paket\python_vorlage^).
) else (
  echo Schritt 2 von 4: Python 3.12 ^(eingebettet^) holen ...
  if not exist "paket" mkdir "paket"
  if not exist "paket\python-3.12.10-embed-amd64.zip" (
    curl.exe -L --fail --retry 3 --retry-delay 5 -# -o "paket\python-3.12.10-embed-amd64.zip" "%PYZIP%" || ( echo Python liess sich nicht holen: %PYZIP% & goto ende_fehler )
  )
  if not exist "paket\python_vorlage" mkdir "paket\python_vorlage"
  tar.exe -xf "paket\python-3.12.10-embed-amd64.zip" -C "paket\python_vorlage" || ( echo Das Python-Archiv laesst sich nicht entpacken. & goto ende_fehler )
  if not exist "%PY%" ( echo Nach dem Entpacken fehlt %PY%. & goto ende_fehler )
  echo    Python liegt in paket\python_vorlage.
)

rem --- 3. Alles Weitere holt das Helferprogramm mit diesem Python (pip, Raeder, llama.cpp, Firmware, Treiber, Modell) ---
echo Schritt 3 von 4: pip, Python-Raeder, llama.cpp, Firmware, Treiber und Sprachmodell holen ...
if not exist "alles_gut.py" ( echo Im Kurspaket fehlt alles_gut.py - das Paket auf GitHub ist aelter als diese Datei. & goto ende_fehler )
"%PY%" "alles_gut.py"
set "RC=%errorlevel%"
if not "%RC%"=="0" (
  echo.
  echo Das Holen ist nicht vollstaendig ^(Rueckgabe %RC%^) - siehe oben und alles_gut_protokoll.txt.
  echo Diese Datei einfach erneut starten: Vorhandenes wird nicht noch einmal geladen.
  goto ende_fehler
)

rem --- 4. START.bat: einrichten (12 Punkte), Diener, Modellserver, Browser ---
if "%OHNE_START%"=="1" (
  echo Schritt 4 von 4: uebersprungen ^(--ohne-start^). Alles liegt in %ZIEL%; START.bat startet den Kurs.
  exit /b 0
)
echo Schritt 4 von 4: START.bat ...
echo.
call "START.bat"
exit /b %errorlevel%

:ende_fehler
echo.
echo Abgebrochen. Was geholt wurde, bleibt in %ZIEL% und wird beim naechsten Start weiterverwendet.
if "%OHNE_START%"=="1" exit /b 1
pause
exit /b 1
