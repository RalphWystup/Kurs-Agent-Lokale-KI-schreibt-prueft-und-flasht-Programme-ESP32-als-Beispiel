# Quellen — worauf jeder Baustein fußt (Gebot 7)

| Datei | Grundlage |
|:--|:--|
| `Frage.html` | Seite: OpenAI-kompatible Schnittstelle des llama-server (`/v1/chat/completions`, Server-Sent Events), Dokumentation llama.cpp; Textfeld/Fetch nach MDN; eigener Ansatz nach Lesen von LLM-Self-Repair-Arbeiten (arXiv 2604.10508, 2606.17514, ICLR 2024 Self-Debug) für die Agent-Knöpfe |
| `agent/oberflaeche.py` | Python `http.server`, `subprocess`, pyserial (Raw-REPL-Steuerzeichen Strg+A/B/C/D nach MicroPython-Doku) |
| `agent/einrichten.py` | Python Embeddable Package + `get-pip.py` (python.org), `pip install --no-index --find-links`, `pnputil /enum-drivers` (Microsoft) |
| `START.bat` | Windows-Batch; `netstat -ano`, `findstr` (Microsoft) |
| `einspielen.py` | Baugate-Prinzip wie bei der Analoganzeige (eigenes Projekt, 16.09.2026); Gebote 1–10 vom 15./16.10.2026 |
| `agent/werkzeuge/esp32_firmware.py` | esptool (`erase_flash`, `write_flash`), MicroPython-Banner nach weichem Neustart (Strg+C/Strg+D, MicroPython-Doku REPL) |
| `agent/werkzeuge/esp32_laden.py` | Raw-REPL-Protokoll (MicroPython-Doku), SHA-256 auf dem Gerät mit `uhashlib` |
| `agent/werkzeuge/programm_testen.py` | Nachbau von `machine.Pin/PWM/ADC` nach MicroPython-ESP32-Doku; `duty` 0..1023, `duty_u16` 0..65535 mit ValueError wie auf dem Gerät |
| `pruefe_simulator.py` | Prüfprogramme mit mathematisch feststehendem Ergebnis (angehobener Kosinus, Dreieck); eigener Ansatz |

- `pruefe_diener.py` | Prüfmittel des Dieners: spielt die Seite (Lebenszeichen 300 ms) und löst Übersetzen/Simulator aus; eigener Ansatz nach Lesen von Python-Doku `http.server`/`urllib.request`; Anlass: Wächter-Fehlalarm 16.10.2026 01:56:01
- `pruefe_start.py` | Prüfmittel des Schalters: startet START.bat im eigenen Fenster, schließt es per WM_CLOSE (Win32-Doku: EnumWindows/PostMessage), misst Diener/Modell vorher und nachher; Diener-Sicherungen nach Microsoft-Doku SetConsoleCtrlHandler (CTRL_CLOSE_EVENT) und Job Objects (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
