# Kurs-Agent — eine lokale KI schreibt, prüft und flasht Programme

<img src="Foto_Ralph_Wystup.jpg" align="right" width="140" alt="Prof. Dr.-Ing. Ralph Wystup">

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)

**Seite öffnen:** https://ralphwystup.github.io/Kurs-Agent-Lokale-KI-schreibt-prueft-und-flasht-Programme-ESP32-als-Beispiel/ — das Lehrbeispiel mit zwölf Reitern: Wofür das Ganze, Was im Paket ist, Schritt für Schritt,
Zwei Beispiele, Hardware und Treiber, **Das Sprachmodell, Der Agent, Die Werkzeuge, Prüfen und Messen, Stand und Grenzen**,
Was der Rechner merkt, Wenn es klemmt. Mit Funktionsskizze. Läuft offline.

Ein KI-Agent mit eigenem Sprachmodell (Qwen2.5-Coder, 3B oder 7B, als GGUF über llama.cpp) läuft aus **einem Ordner** auf
einem Windows-Rechner: ohne Installation, ohne Netz, mit eigenem Python. Im Gespräch schreibt er auf Anforderung
Python-Programme, prüft sie selbst gegen eine vorher genannte Erwartung, berichtigt sie, überspielt sie auf einen ESP32 und
liest am Gerät zurück, ob die LED wirklich tut, was verlangt war. Allgemeine Programme (ein Taschenrechner mit tkinter) laufen
mit dem Paket-Python. Am Ende entfernt er sich restlos; der Rechner bleibt, wie er war.

Dieses Paket vertieft am realen System, was die Seite
[„KI steuert lokale Hardware über eine Brücke“](https://ralphwystup.github.io/KI-steuert-lokale-Hardware-ueber-eine-Bruecke/)
exemplarisch zeigt.

## Vermerk der Unvollständigkeit

Dies ist ein **Lehrbeispiel, kein fertiges Produkt** — bewusst so veröffentlicht. Es zeigt, wie eine kleine lokale KI mit einem
strengen Agenten und messenden Werkzeugen brauchbare Ergebnisse liefert, und es zeigt ebenso ehrlich, woran ein 3-Milliarden-Modell
scheitert: schnelle Takte, zwei LEDs mit zwei Takten gleichzeitig, erfundene Arbeit in langen Gesprächen, falsche Hardwareauskünfte.
Alles, was als „funktioniert“ steht, wurde am 04./05.10.2026 auf einem Windows-Laptop (8 GB frei, Smart App Control EIN) mit einem
ESP32 an COM3 gemessen; alles andere steht im Reiter **Stand und Grenzen** als offen. Die Richtigkeit trägt die Messung, nicht das Modell.

## Was drin ist

| Datei / Ordner | Inhalt |
|:--|:--|
| [`Kurs_Agent_3.0.html`](Kurs_Agent_3.0.html) | die Kurs-Seite: Inbetriebnahme, Komponenten in getrennten Reitern, Funktionsskizze, Messungen, Stand und Grenzen |
| [`AUFGABE.md`](AUFGABE.md) / [`.pdf`](AUFGABE.pdf) | die Aufgabe des Auftraggebers, wörtlich, und was daraus folgt |
| [`ANFORDERUNGEN.md`](ANFORDERUNGEN.md) / [`.pdf`](ANFORDERUNGEN.pdf) | 96 Anforderungen in elf Gruppen, jede so gefasst, dass sie scheitern kann |
| [`PRUEFPROTOKOLL.md`](PRUEFPROTOKOLL.md) / [`.pdf`](PRUEFPROTOKOLL.pdf) | was geprüft ist, womit, mit welchem Ergebnis — einschließlich der Fehlschläge |
| [`LIESMICH_Paket.md`](LIESMICH_Paket.md) | Anfangen: Doppelklick auf `START.bat` |
| `START.bat` | der einzige Einstieg: [1] installieren und starten, [2] deinstallieren |
| `hole_paket.py` | füllt das Paket einmal mit Netz aus den Originalquellen (Python, pip, Räder, llama.cpp, MicroPython, Treiber, Modell); im Kurs nie |
| `agent/` | der Agent (`agent.py`, Klasse `Sitzung`), die Modellanbindung, die Oberfläche (Gespräch im Browser), die festen Anfragen (`auftraege.json`) |
| `agent/werkzeuge/` | elf Werkzeuge, jedes ein eigenes Programm mit `--beschreibung`: schreib_datei, programm_testen (Nachbau mit gedachter Uhr, PWM-Hüllkurve), programm_ausfuehren, ports_zeigen, esp32_firmware, esp32_uebertragen, esp32_nachlesen (misst am Gerät), umgebung_anlegen, paket_installieren, nachweis_autark, aufraeumen |
| `pruefstand/` | die Gegenproben: `pruefe_schleife.py`, `pruefe_regeln.py`, `pruefe_gespraech.py`, `pruefe_ungeprueft.py`, `pruefe_pwm.py`, dazu `messe_modell.py` für Modellvergleiche |
| `pruefe_alles.py`, `pruefe_unversehrtheit.py`, `pruefe_rechner.py`, `sammle_bericht.py` | Prüfung gegen das Anforderungsblatt, Unversehrtheit des Rechners, Eignung des Rechners, Ferndiagnose in einer Datei |
| `paket/tkinter-8.6.13-py3.12-win-amd64.zip` | tkinter für das eingebettete Python (aus conda-forge, Lizenzen im Archiv) — alles andere im Paket wird geholt, nicht mitgeliefert |
| `erstelle_anleitung.py`, `bilder/` | erzeugt die Seite; die Werkzeugtabelle wird aus den Programmen gelesen |
| [`LIZENZEN.md`](LIZENZEN.md) | die fremden Bestandteile, woher sie kommen, unter welcher Lizenz |
| `index.html` | leitet auf die Seite weiter, damit GitHub Pages sie unter der Adresse oben zeigt |

## Anfangen

    git clone https://github.com/RalphWystup/Kurs-Agent-Lokale-KI-schreibt-prueft-und-flasht-Programme-ESP32-als-Beispiel.git C:\Kurs_Agent
    C:\Kurs_Agent\START.bat        →  [1]

Beim ersten Start ist das Paket leer; `START.bat` sagt das und holt alles selbst (rund 7 GB, Python, Räder, llama.cpp,
MicroPython, Treiber, Modell). Dafür wird einmal ein vorhandenes Python mit pip und Netz gebraucht — der Vorbereitungsschritt
des Dozenten. Danach läuft der Kurs ohne Netz mit dem Python aus dem Paket; der gefüllte Ordner wird kopiert und weitergegeben.
Liegt ein gefülltes Paket nebenan (ein Stick, `C:\Kurs_Agent\paket`), füllt sich eine frische Kopie daraus ohne Netz.

Im Browser öffnet sich das Gespräch: feste Anfragen als Knöpfe über dem Eingabefeld, darunter die freie Eingabe. Etwa:
„Schreibe blink.py, LED an GPIO 2 einmal je Sekunde, prüfe es.“ — „Ändere auf 2 Hz.“ — „Lade es an COM3 auf den ESP32 und lies
nach, ob die LED blinkt.“ — „Programmiere einen Taschenrechner mit grafischer Oberfläche.“

## Nachrechnen

    cd pruefstand
    python3 pruefe_schleife.py      # die Schleife ohne Modell: FERTIG gilt erst nach bestandener Abnahme (8 Punkte)
    python3 pruefe_regeln.py        # die Regeln des Agenten mit Gegenproben (28)
    python3 pruefe_gespraech.py     # das Gespräch: anderer Pin, andere Frequenz, erst prüfen dann laden, Zwischenruf (30)
    python3 pruefe_pwm.py           # PWM-Hüllkurve: Periode, Takt, Form (7)
    cd .. && python3 pruefe_alles.py

Der Prüfstand braucht in `pruefstand/ablage/python/` ein Python (unter Linux ein Verweis `python.exe -> /usr/bin/python3`);
für `messe_modell.py` zusätzlich `paket/llama/llama-server` und ein Modell unter `paket/modell/`.

## Grundsätze dahinter

Nichts gilt, bevor es gemessen ist. Jede Prüfung hat eine Gegenprobe, die durchfallen muss. Zwei unabhängige Wege: der Nachbau
auf dem PC und das Gerät selbst. Die Erwartung setzt der Mensch; das Modell kann sie nicht verschieben. Was das Modell behauptet,
muss ein Werkzeug getan haben. Der Agent steuert nicht, er wacht.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Fremde Bestandteile: siehe [LIZENZEN.md](LIZENZEN.md).
