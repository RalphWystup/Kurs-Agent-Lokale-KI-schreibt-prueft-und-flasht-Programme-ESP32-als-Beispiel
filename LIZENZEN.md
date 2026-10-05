# Fremde Bestandteile — woher, wozu, unter welcher Lizenz

Stand 05.10.2026. Das Repositorium enthält **eigenen** Quelltext (MIT) und **ein** fremdes Archiv (tkinter). Alles Übrige im
Paket wird von `hole_paket.py` beim ersten Start **aus den Originalquellen geladen**, nicht hier verteilt:

| Bestandteil | Quelle | Lizenz | im Repositorium? |
|:--|:--|:--|:--|
| Python 3.12 (eingebettet, Windows) | python.org | PSF License | nein — wird geladen |
| pip (`get-pip.py`) | bootstrap.pypa.io | MIT | nein — wird geladen |
| esptool, mpremote, pyserial und Abhängigkeiten (Räder) | PyPI | GPL-2.0 (esptool), MIT (mpremote, pyserial), weitere je Paket | nein — werden geladen |
| llama.cpp (Rechenkern, Windows-Build) | github.com/ggml-org/llama.cpp | MIT | nein — wird geladen |
| llama-server, signiert (aus dem Ollama-Archiv `ollama-windows-amd64.zip`, `lib/ollama/`) | github.com/ollama/ollama | MIT (Ollama), MIT (llama.cpp), Lizenzen der Bibliotheken liegen im Archiv bei | nein — Anleitung im Prüfprotokoll; `hole_paket.py` lädt den unsignierten llama.cpp-Build, der signierte ist für Rechner mit Smart App Control von Hand zu ergänzen |
| MicroPython-Firmware ESP32_GENERIC | micropython.org | MIT | nein — wird geladen |
| USB-Treiber CH341SER, CH343SER | wch-ic.com | Herstellerlizenz (WCH), nur zur Verwendung mit WCH-Chips | nein — werden geladen; der Agent installiert keinen Treiber |
| USB-Treiber CP210x | silabs.com | Herstellerlizenz (Silicon Labs) | nein — Hinweis, von Hand zu holen |
| Qwen2.5-Coder-3B/7B-Instruct, Qwen2.5-3B/7B-Instruct (GGUF, Q4_K_M, Quantisierung bartowski) | huggingface.co/bartowski, huggingface.co/Qwen | Apache-2.0 (Qwen2.5) | nein — werden geladen |
| **tkinter für Python 3.12** (`_tkinter.pyd`, `tcl86t.dll`, `tk86t.dll`, `zlib1.dll`, `tcl/`, `Lib/site-packages/tkinter`) | conda-forge: `python-3.12.10-h3f84c4b_0_cpython`, `tk-8.6.13-h967ab96_4` | PSF License (Python/_tkinter), Tcl/Tk License (BSD-artig), zlib License | **ja** — `paket/tkinter-8.6.13-py3.12-win-amd64.zip`, Lizenztexte im Archiv unter `LIZENZEN/` |

Schriften: Systemschriften des Betrachters. Bilder: eigene Bildschirmfotos der Oberfläche auf dem Prüfstand. Keine Zugangsdaten,
keine Netzwerkadressen außer `127.0.0.1`, keine Benutzer- oder Rechnernamen.

Die Namen „Qwen“, „Ollama“, „ESP32“, „MicroPython“, „Windows“ sind Marken ihrer Inhaber und werden nur zur Bezeichnung verwendet.
