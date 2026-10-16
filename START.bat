@echo off
setlocal
chcp 65001 >nul
title Kurs-Agent
cd /d %~dp0
set "PYTHONPATH="
set "PYTHONHOME="
set "PYTHONNOUSERSITE=1"
echo ==============================================================
echo  KURS-AGENT  -  dieses Fenster ist der Schalter.
echo  Es bleibt offen, solange Sie arbeiten. Der erste Start dauert 1 bis 3 Minuten.
echo  Fenster schliessen = Kurs beenden (Modell, Leitung, Diener aus).
echo ==============================================================
rem --- 1. Einrichten: nachsehen, was da ist; nur das Fehlende aus dem Paket (kein Internet) ---
set "PY=ablage\python\python.exe"
if not exist "%PY%" set "PY=paket\python_vorlage\python.exe"
if not exist "%PY%" ( echo Im Paket fehlt das Python ^(paket\python_vorlage^). & pause & exit /b 1 )
"%PY%" "agent\einrichten.py"
set "RC=%errorlevel%"
rem --- Treiber fehlt und Windows verlangt Rechte: nur fuer diesen einen Schritt Administratorrechte holen (UAC-Abfrage: Ja) ---
if "%RC%"=="3" (
  echo.
  echo Der USB-Treiber fehlt. Windows verlangt dafuer einmal Administratorrechte - bitte die Abfrage mit Ja beantworten.
  powershell -NoProfile -Command "Start-Process -FilePath '%PY%' -ArgumentList 'agent\einrichten.py --treiber' -WorkingDirectory '%~dp0' -Verb RunAs -Wait"
  "%PY%" "agent\einrichten.py" --pruefen
)
if "%RC%"=="1" ( echo. & echo Einrichtung unvollstaendig - siehe oben. Die Seite startet trotzdem. & timeout /t 8 >nul )
rem --- 2. Laeuft schon ein Kurs auf 8777 (anderes Startfenster offen), nur den Browser oeffnen ---
netstat -ano | findstr /r /c:":8777 .*LISTENING" /c:":8777 .*ABH" >nul
if %errorlevel%==0 ( echo Der Kurs laeuft schon - es gibt bereits ein Startfenster. & start "" http://127.0.0.1:8777 & timeout /t 5 >nul & exit /b 0 )
rem --- 3. Diener im Vordergrund: dieses Fenster = der Kurs. Schliessen stellt alles ab. ---
set "KURS_BROWSER=1"
"ablage\python\python.exe" "agent\oberflaeche.py"
echo.
echo Kurs beendet.
pause
