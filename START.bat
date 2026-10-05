@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title Kurs-Agent

rem ===================================================================================
rem  Kurs-Agent - Startskript
rem
rem  Ein Doppelklick, eine Frage: installieren und starten - oder deinstallieren.
rem  Alles Weitere erledigt dieses Skript selbst: Es legt das eigene Python bereit, holt,
rem  was im Paket noch fehlt, prueft, ob alles da ist, und oeffnet den Agenten im Browser.
rem
rem  Anlass fuer diese Form (03.10.2026): "Geht das nicht einfacher, dass die START.bat
rem  alles selbst macht und fragt: installieren oder deinstallieren? Was kuemmert mich der
rem  Rest, es muss halt alles funktionieren." - Recht hat er. Die Betriebsarten, das
rem  Werkzeugmenue und die Einzelpruefungen gibt es weiter, aber nur fuer den, der sie
rem  sucht:   START.bat --menue
rem
rem  Alles ist relativ zu diesem Skript (%~dp0). Es gibt im ganzen Paket keinen festen
rem  Pfad; der Stick darf jeden Laufwerksbuchstaben haben.
rem ===================================================================================

rem --- Die Umgebung saeubern, bevor irgendetwas laeuft ------------------------------
rem  PYTHONPATH laedt fremde Module in UNSER Python, PYTHONHOME verbiegt die Standard-
rem  bibliothek. Geleert wird nur in diesem Fenster (setlocal steht oben) - am Rechner
rem  aendert sich nichts.
set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONSTARTUP="
set "PYTHONUSERBASE="
set "PYTHONEXECUTABLE="
set "PIP_TARGET="
set "PIP_PREFIX="
set "PIP_USER="
set "PIP_CONFIG_FILE="
set "PIP_INDEX_URL="
set "PIP_EXTRA_INDEX_URL="
set "PYTHONNOUSERSITE=1"

set "HIER=%~dp0"
if "%HIER:~-1%"=="\" set "HIER=%HIER:~0,-1%"

rem --- Laufprotokoll ----------------------------------------------------------------
rem  Jeder Lauf schreibt mit, was er tut (letzter_lauf.txt im Paketordner; der vorige
rem  Lauf bleibt als vorletzter_lauf.txt). Anlass: Am 03.10.2026 war nach einem Lauf das
rem  Fenster fort und nichts geschrieben - aus der Ferne war nicht zu sagen, was geschah.
set "PROT=%HIER%\letzter_lauf.txt"
if exist "%PROT%" move /y "%PROT%" "%HIER%\vorletzter_lauf.txt" >nul 2>&1
echo ==== Kurs-Agent, Lauf vom %DATE% %TIME% ====>"%PROT%" 2>nul
call :prot "Ordner: %HIER%"
call :prot "Aufrufart: [%~1]  KURS_AGENT_KOPIE=[%KURS_AGENT_KOPIE%]"

if /i "%~1"=="--menue"    goto menue_vorbereiten
if /i "%~1"=="--hier"     goto installieren
if /i "%~1"=="--kopieren" goto kopieren
if defined KURS_AGENT_KOPIE goto installieren

:hauptfrage
echo.
echo   ===============================================================
echo    Kurs-Agent - ein KI-Agent, der einen ESP32 zum Blinken bringt
echo   ===============================================================
echo.
echo    Paket liegt in: %HIER%
echo.
echo    [1]  Installieren und starten    holt, was fehlt, und oeffnet den Agenten
echo    [2]  Deinstallieren              entfernt alles, was der Agent angelegt hat
echo    [3]  Abbrechen
echo.
set "WAHL="
set /p WAHL="   Ihre Wahl [1]: "
if "%WAHL%"=="" set "WAHL=1"
call :prot "Hauptfrage beantwortet: [%WAHL%]"
if "%WAHL%"=="2" goto deinstallieren
if "%WAHL%"=="3" exit /b 0
if not "%WAHL%"=="1" goto hauptfrage

rem ===================================================================================
rem  [1]  Installieren und starten
rem ===================================================================================
:installieren
call :python_bereit
call :fehlt_etwas
if "!FEHLT!"=="1" (
  call :prot "Paket unvollstaendig - wird geholt"
  echo.
  echo    Das Paket ist noch nicht vollstaendig. Was fehlt, wird jetzt geholt - einmalig,
  echo    mit Netz, bis zu 6,8 GB. Alles landet in diesem Ordner, am Rechner aendert sich
  echo    nichts. Was unterwegs abbricht, wird beim naechsten Start weitergeladen.
  echo.
  call :suchepython
  if not defined FREMD (
    call :prot "kein Python mit pip zum Holen gefunden"
    echo    Zum Holen wird einmalig ein Python mit pip gebraucht - auf diesem Rechner ist
    echo    keines. Zwei Wege:
    echo      1. Den gefuellten Ordner von einem anderen Rechner kopieren. Das ist der
    echo         gedachte Weg: fuellen einmal, weitergeben beliebig oft.
    echo      2. Python von python.org installieren, "Add python.exe to PATH" ankreuzen,
    echo         dann START.bat erneut starten.
    echo    Was geprueft wurde, steht in %PROT%
    echo.
    pause
    goto hauptfrage
  )
  call :prot "hole_paket.py laeuft mit !FREMD!"
  set "PIP_CACHE_DIR=%HIER%\ablage\pip_zwischenspeicher"
  "!FREMD!" "%HIER%\hole_paket.py"
  set "RC=!ERRORLEVEL!"
  call :prot "hole_paket.py beendet, Rueckgabe [!RC!]"
  echo.
  echo    Was dabei geschah, steht Zeile fuer Zeile in: %HIER%\fuellen_protokoll.txt
  echo.
  call :python_bereit
  call :fehlt_etwas
  if "!FEHLT!"=="1" (
    set /a ANLAEUFE+=1
    call :prot "nach dem Holen fehlt noch etwas (Anlauf !ANLAEUFE!)"
    echo.
    echo    Es fehlt noch etwas - siehe oben.
    rem  Hoechstens zwei Anlaeufe. Am 04.10.2026 um 0:55 drehte sich START.bat fuenfmal im
    rem  Kreis "unvollstaendig - holen - unvollstaendig", weil hole_paket.py alles vorfand
    rem  und die Pruefung trotzdem etwas vermisste - ein Widerspruch im Programm, den kein
    rem  weiterer Anlauf aufloest. Nach dem zweiten geht es weiter, und das Protokoll sagt,
    rem  was fehlte.
    if !ANLAEUFE! GEQ 2 (
      call :prot "zweiter Anlauf vergeblich - es geht mit Luecken weiter"
      echo    Auch der zweite Anlauf hat es nicht behoben. Es geht weiter, mit Luecken;
      echo    was fehlt, steht in %PROT%
      echo.
    ) else (
      echo    Meist war es ein Netzaussetzer; ein zweiter Anlauf holt genau das Fehlende
      echo    nach, Vorhandenes nicht noch einmal.
      set "NOCHMAL=j"
      set /p "NOCHMAL=   Noch einmal versuchen? [J/n] "
      if /i not "!NOCHMAL!"=="n" goto installieren
      call :prot "weiter trotz Luecken"
      echo    Gut - es geht weiter, mit Luecken.
    )
  )
)
if not defined PY (
  call :prot "kein eigenes Python - Start nicht moeglich"
  echo    Ohne das eigene Python kann nichts starten. Erwartet wurde:
  echo       %HIER%\paket\python_vorlage\python.exe
  pause
  goto hauptfrage
)
call :vorbereiten
call :prot "Agent startet"
echo.
echo    Der Agent startet; es oeffnet sich ein Browserfenster.
echo    Dieses Fenster bitte offen lassen. Strg+C beendet den Agenten.
echo.
"!PY!" "%HIER%\agent\oberflaeche.py"
call :prot "Agent beendet"
goto hauptfrage

rem ===================================================================================
rem  [2]  Deinstallieren: erst der Nachweis, dann das Loeschen
rem ===================================================================================
:deinstallieren
call :python_bereit
if defined PY (
  set "KURS_AGENT_WURZEL=%HIER%"
  echo.
  echo    Erst der Nachweis, dann das Loeschen:
  "!PY!" "%HIER%\agent\werkzeuge\nachweis_autark.py" "{\"wann\": \"nachher\"}"
  echo.
  "!PY!" "%HIER%\agent\werkzeuge\aufraeumen.py" "{\"nur_zeigen\": false}"
)
rem  Der Rest des eigenen Pythons laesst sich erst entfernen, wenn Python beendet ist -
rem  bis dahin haelt Windows python.exe und seine DLL fest. Jetzt ist es beendet.
if exist "%HIER%\ablage" rmdir /s /q "%HIER%\ablage" 2>nul
if exist "%HIER%\ablage" (
  call :prot "ablage liess sich nicht ganz entfernen"
  echo    Der Ordner ablage liess sich nicht ganz entfernen - ist er in einem
  echo    Explorer-Fenster geoeffnet? Schliessen und [2] wiederholen.
) else (
  call :prot "deinstalliert - ablage ist fort"
  echo    Alles, was der Agent angelegt hat, ist entfernt. Das Paket selbst bleibt.
)
echo.
pause
goto hauptfrage

rem ===================================================================================
rem  Unterroutinen
rem ===================================================================================

rem --- Das eigene Python bereitlegen. Setzt PY, oder laesst es leer, wenn es nicht geht.
rem     PY wird hier jedes Mal neu bestimmt, nicht einmal am Anfang: Am 03.10.2026 war PY
rem     an einer Stelle leer, ohne dass eine Zeile es geleert haette - "Der Befehl """"
rem     ist entweder falsch geschrieben ...". Was neu bestimmt wird, kann nicht veralten.
:python_bereit
set "PY=%HIER%\ablage\python\python.exe"
rem  Ein halbes Python ist keins. Am 04.10.2026 um 0:36 lief das Aufraeumen, waehrend das
rem  Python noch lief: Es nahm alles bis auf python.exe und die DLL (die hielt Windows
rem  fest) und hinterliess die Marke _rest_entfernen. Diese Fassung prueft nur "gibt es
rem  python.exe?" - und hielt den Rest fuer ein Python. Jeder Aufruf starb dann mit
rem  "No module named encodings", und START.bat drehte sich im Kreis.
rem  Darum drei Fragen, bevor PY gilt: Liegt die Marke? Fehlt die Bibliothek? Startet es?
if exist "%HIER%\ablage\_rest_entfernen" (
  call :prot "Rest eines frueheren Aufraeumens gefunden - ablage\python wird erneuert"
  rmdir /s /q "%HIER%\ablage\python" 2>nul
  del /q "%HIER%\ablage\_rest_entfernen" 2>nul
)
if exist "!PY!" if not exist "%HIER%\ablage\python\python3*.zip" (
  call :prot "ablage\python ohne Bibliothek (python3*.zip fehlt) - wird erneuert"
  rmdir /s /q "%HIER%\ablage\python" 2>nul
)
if exist "!PY!" (
  "!PY!" -c "import encodings, json" >nul 2>&1
  if errorlevel 1 (
    call :prot "ablage\python startet nicht - wird erneuert"
    rmdir /s /q "%HIER%\ablage\python" 2>nul
  )
)
if exist "!PY!" exit /b 0
if exist "%HIER%\paket\python_vorlage\python.exe" (
  echo    Das mitgelieferte Python wird bereitgelegt - nur kopiert, nicht installiert.
  echo    Ein vorhandenes Python auf diesem Rechner wird weder benutzt noch veraendert.
  xcopy "%HIER%\paket\python_vorlage" "%HIER%\ablage\python" /E /I /Q /Y >nul
)
if exist "!PY!" ( call :prot "eigenes Python bereit: !PY!" & exit /b 0 )
set "PY="
call :prot "eigenes Python noch nicht da (paket\python_vorlage fehlt)"
exit /b 0

rem --- Fehlt etwas im Paket? Setzt FEHLT auf 1 oder 0. Die Liste der Bestandteile steht
rem     an einer Stelle, in agent\pfade.py - dort, wo auch der Agent sie liest.
rem     Anlass: Nach einem abgebrochenen Fuellen lag Python im Paket, sonst nichts - und
rem     daran allein erkannte das Skript bis zum 03.10.2026 "fertig". Ein halb gefuelltes
rem     Paket ist der gefaehrlichste Zustand: Es sieht fertig aus.
:fehlt_etwas
set "FEHLT=1"
if not defined PY exit /b 0
echo    Paket:
rem  Die Ausgabe der Pruefung geht auf den Schirm UND ins Laufprotokoll - samt Fehlertext,
rem  falls das Programm selbst scheitert. Am 04.10.2026 um 0:55 lief START.bat in einer
rem  Schleife "unvollstaendig - holen - unvollstaendig", und aus der Ferne war nicht zu
rem  sehen, welchen Teil die Pruefung vermisste: Das stand nur im Fenster.
if not exist "%HIER%\ablage" mkdir "%HIER%\ablage" 2>nul
"!PY!" "%HIER%\agent\pfade.py" --fehlt > "%HIER%\ablage\_vollstaendigkeit.txt" 2>&1
set "RC=!ERRORLEVEL!"
type "%HIER%\ablage\_vollstaendigkeit.txt"
type "%HIER%\ablage\_vollstaendigkeit.txt" >> "%PROT%" 2>nul
if "!RC!"=="0" set "FEHLT=0"
call :prot "Vollstaendigkeit geprueft: Rueckgabe [!RC!], FEHLT=[!FEHLT!]"
exit /b 0

rem --- Vor dem Start: Rechner ansehen, Vorher-Bild aufnehmen. Ohne das Vorher-Bild liesse
rem     sich am Ende nicht belegen, dass nichts zurueckbleibt.
:vorbereiten
set "KURS_AGENT_WURZEL=%HIER%"
"!PY!" "%HIER%\pruefe_rechner.py" --kurz
"!PY!" "%HIER%\agent\werkzeuge\nachweis_autark.py" "{\"wann\": \"vorher\"}" >nul 2>&1
exit /b 0

rem --- Ein Python mit pip finden - nur zum Holen des Pakets, sonst fuer nichts.
rem     JEDER Fundort wird geprueft, nicht nur der erste: "where python" nennt zuerst den
rem     Platzhalter des Windows-Stores, der nur den Laden oeffnet und kein pip hat. Am
rem     03.10.2026 brach das Skript daran ab, obwohl zwei Zeilen weiter ein brauchbares
rem     Python (Thonny) stand. Grundsatz 21: Wer denkt, es geht nicht, hat nicht gut genug
rem     gesucht. Die Schleifenvariable heisst Q, nicht P - PY soll nicht einmal in die
rem     Naehe einer Verwechslung kommen.
:suchepython
set "FREMD="
for /f "delims=" %%Q in ('where python 2^>nul') do call :pruefepython "%%Q"
if exist "%LOCALAPPDATA%\Programs\Thonny\python.exe" call :pruefepython "%LOCALAPPDATA%\Programs\Thonny\python.exe"
for /f "delims=" %%Q in ('dir /b /s "%LOCALAPPDATA%\Programs\Python\python.exe" 2^>nul') do call :pruefepython "%%Q"
for /f "delims=" %%Q in ('where py 2^>nul') do call :pruefepython "%%Q"
for /f "delims=" %%Q in ('dir /b /s "%PROGRAMFILES%\Python*\python.exe" 2^>nul') do call :pruefepython "%%Q"
for /f "delims=" %%Q in ('dir /b /s "%PROGRAMFILES(X86)%\Python*\python.exe" 2^>nul') do call :pruefepython "%%Q"
exit /b 0

rem --- Taugt dieser Kandidat? Nimmt den ersten, in dem pip wirklich laeuft, und vermerkt
rem     jeden uebergangenen samt Grund - sonst sucht beim naechsten Mal wieder jemand an
rem     der falschen Stelle. Der Store-Platzhalter wird am Namen erkannt (reine
rem     cmd-Ersetzung, kein "find": das ist ein eigenes Programm und antwortet unter Wine
rem     mit Rueckgabe 2) und gar nicht erst gestartet - sonst ginge der Laden auf.
:pruefepython
if defined FREMD exit /b 0
set "KAND=%~1"
if not exist "%KAND%" exit /b 0
if not "!KAND:\WindowsApps\=!"=="!KAND!" (
  call :prot "uebergangen, Platzhalter des Windows-Stores: %KAND%"
  exit /b 0
)
"%KAND%" -m pip --version >nul 2>&1
if errorlevel 1 (
  call :prot "uebergangen, kein pip darin: %KAND%"
  exit /b 0
)
set "FREMD=%KAND%"
call :prot "brauchbares Python mit pip: %KAND%"
exit /b 0

rem --- Eine Zeile ins Laufprotokoll. Faellt stumm aus, wenn nicht geschrieben werden kann.
rem     Die Umleitung steht VORN: Endet der Text auf eine Ziffer, liest cmd bei
rem     "...FEHLT=1>>datei" die 1 als Dateinummer der Umleitung und verschluckt sie - im
rem     Protokoll stand dann "FEHLT=" ohne Wert und "Rueckgabe " ohne Zahl (04.10.2026).
rem     Nachtrag 1:10 Uhr: Die Umleitung VORN liess Aufrufe aus Klammerbloecken stumm
rem     verschwinden (die Erneuerung des Pythons lief, stand aber nicht im Protokoll).
rem     Darum wieder hinten - mit einem Leerzeichen vor >>, damit keine Ziffer als
rem     Dateinummer gelesen wird.
:prot
echo [%TIME%] %~1 >>"%PROT%" 2>nul
exit /b 0

rem ===================================================================================
rem  --kopieren : auf die Platte kopieren und dort arbeiten (schneller als vom Stick);
rem  der kopierte Ordner wird am Ende wieder geloescht.
rem ===================================================================================
:kopieren
set "ZIEL=%TEMP%\Kurs_Agent_Lauf"
echo.
echo    Das Paket wird kopiert nach:
echo       %ZIEL%
echo    Es wird nach dem Beenden wieder geloescht.
echo.
if exist "%ZIEL%" rmdir /s /q "%ZIEL%"
robocopy "%HIER%" "%ZIEL%" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 ( echo    Das Kopieren schlug fehl. & pause & exit /b 1 )
echo    Kopiert. Der Stick kann jetzt abgezogen werden.
set KURS_AGENT_KOPIE=1
call :prot "kopiert nach %ZIEL% - dort geht es weiter"
call "%ZIEL%\START.bat" --hier
exit /b 0

rem ===================================================================================
rem  --menue : das Werkzeugmenue fuer den, der es sucht. Hier laesst sich jedes Teil
rem  einzeln pruefen, der Agent ohne Browser oder ohne Modell fahren, ein Bericht sammeln.
rem ===================================================================================
:menue_vorbereiten
call :python_bereit
if not defined PY (
  echo    Ohne das eigene Python gibt es kein Menue. Erst START.bat ohne Zusatz starten.
  pause & exit /b 1
)
call :vorbereiten
call :prot "Menue erreicht"
:menue
echo   ---------------------------------------------------------------
echo    [1]  Agent starten                 Oberflaeche im Browser  ^<-- hier anfangen
echo    [2]  Werkzeuge einzeln pruefen     jedes einmal, ohne Modell
echo    [3]  Aufraeumen                    Nachweis zeigen, dann alles loeschen
echo.
echo    [4]  Paket fuellen                 einmalig, braucht Netz
echo    [5]  Werkzeuge anzeigen            was der Agent kann
echo    [6]  Agent in der Konsole          ohne Browser
echo    [7]  Ohne Modell durchlaufen       Rueckfallweg
echo    [8]  Bericht sammeln               eine Datei zum Weitergeben
echo    [9]  Beenden
echo   ---------------------------------------------------------------
set "M="
set /p M="   Ihre Wahl [1]: "
if "%M%"=="" set "M=1"
call :prot "Menuewahl: [%M%]"
if "%M%"=="1" (
  echo.
  echo    Die Oberflaeche wird gestartet, es oeffnet sich ein Browserfenster.
  echo    Dieses Fenster bitte offen lassen; mit Strg+C wird die Oberflaeche beendet.
  echo.
  "!PY!" "%HIER%\agent\oberflaeche.py"
  goto menue
)
if "%M%"=="2" ( "!PY!" "%HIER%\agent\agent.py" --probe     & goto menue )
if "%M%"=="3" goto deinstallieren
if "%M%"=="4" (
  call :suchepython
  if defined FREMD ( "!FREMD!" "%HIER%\hole_paket.py" ) else ( echo    Kein Python mit pip gefunden. )
  goto menue
)
if "%M%"=="5" ( "!PY!" "%HIER%\agent\agent.py" --werkzeuge & goto menue )
if "%M%"=="7" ( "!PY!" "%HIER%\agent\agent.py" --drehbuch  & goto menue )
if "%M%"=="8" (
  echo.
  echo    Es wird ein Bericht gesammelt: Rechner, Paket, Selbstpruefung,
  echo    Werkzeugprobe, Protokoll. Das dauert einige Minuten.
  echo.
  "!PY!" "%HIER%\sammle_bericht.py"
  goto menue
)
if "%M%"=="9" goto ende
if "%M%"=="6" (
  echo.
  set "A="
  set /p A="   Auftrag [Vorgabe: LED blinken, nur geprueft]: "
  if "!A!"=="" set "A=Schreibe ein MicroPython-Programm blink.py, das die LED an GPIO 2 einmal je Sekunde blinken laesst. Pruefe es danach mit programm_testen gegen die Erwartung pins [2] und takt_hz 1.0."
  "!PY!" "%HIER%\agent\agent.py" "!A!"
  goto menue
)
goto menue

:ende
call :prot "Beendet ueber Punkt 9"
echo.
echo    Fertig. Es wurde nichts installiert; der Stick kann abgezogen werden.
pause
exit /b 0
