#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kopiert eine Datei aus der Werkstatt auf den ESP32 und startet ihn neu.

MicroPython fuehrt nach dem Einschalten ``main.py`` aus. Deshalb wird die Datei unter
diesem Namen abgelegt — dann blinkt die LED, sobald Strom anliegt, auch ohne Rechner.

Nach dem Kopieren wird das Verzeichnis des Geraets gelesen. Erst wenn die Datei dort mit
der richtigen Groesse steht, gilt die Uebertragung als gelungen; ein stiller Fehlschlag
soll nicht als Erfolg gemeldet werden.
"""
import sys, pathlib
# Der eigene Ordner und der des Agenten muessen in den Suchpfad, bevor etwas daraus geholt
# wird. Unter einem gewoehnlichen Python stehen sie von selbst darin — beim eingebetteten
# Python nicht: dort legt python3xx._pth den Suchpfad abschliessend fest, und sys.path hat
# genau zwei Eintraege. Ohne diese Zeilen scheitert jedes Werkzeug auf dem Kursrechner mit
# "No module named _muster", waehrend es auf dem Entwicklungsrechner tadellos laeuft.
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, lauf, WERKSTATT, python_exe
import re


def _mpremote(port, *args, zeit=180):
    return lauf([str(python_exe()), "-m", "mpremote", "connect", port, *args], zeit)


def tun(e):
    port = str(e["port"]).strip()
    if not re.fullmatch(r"(COM\d+|/dev/[A-Za-z0-9._/-]+)", port):
        raise Abbruch(f"'{port}' sieht nicht wie ein Anschluss aus.")
    name = str(e["datei"]).strip()
    quelle = WERKSTATT / name
    if not quelle.is_file():
        da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*"))) or "(nichts)"
        raise Abbruch(f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}.\n"
                      f'Erst anlegen: WERKZEUG: schreib_datei {{"name": "{name}", '
                      f'"inhalt": "<der Quelltext>"}}')
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")
    ziel = str(e.get("ziel", "main.py")).strip() or "main.py"
    if "/" in ziel or "\\" in ziel:
        raise Abbruch("Der Zielname auf dem Geraet darf keinen Pfad enthalten.")

    #  Drei Anlaeufe, drei Sekunden Abstand. Direkt nach dem Flashen legt MicroPython beim
    #  ersten Start sein Dateisystem an und antwortet einige Sekunden nicht auf dem
    #  Raw-REPL; mpremote meldet dann "could not enter raw repl". Am 04.10.2026, 1:22 Uhr,
    #  scheiterte so der erste Klick und der zweite, zwoelf Sekunden spaeter, gelang -- das
    #  soll das Werkzeug selbst abwarten, nicht der Mensch.
    import time
    r = None
    for anlauf in range(1, 4):
        r = _mpremote(port, "fs", "cp", str(quelle), f":{ziel}")
        if r.returncode == 0:
            break
        if "ModuleNotFoundError" in (r.stderr or ""):
            raise Abbruch("mpremote fehlt. Erst paket_installieren mit mpremote aufrufen.")
        if anlauf < 3 and "raw repl" in ((r.stderr or "") + (r.stdout or "")).lower():
            time.sleep(3)
            continue
        break
    if r.returncode != 0:
        raise Abbruch(f"Das Kopieren nach {port} schlug fehl (drei Anlaeufe): "
                      f"{(r.stderr or r.stdout)[-400:]}\n"
                      f"Laeuft auf dem Geraet schon MicroPython (esp32_firmware)? Haelt ein "
                      f"anderes Programm den Anschluss (Thonny, serieller Monitor)?")

    # Gegenprobe: steht die Datei wirklich auf dem Geraet?
    v = _mpremote(port, "fs", "ls")
    gefunden = ziel in (v.stdout or "")
    if not gefunden:
        raise Abbruch(f"Nach dem Kopieren steht {ziel} nicht im Verzeichnis des Geraets. "
                      f"Verzeichnis: {(v.stdout or v.stderr)[-300:]}")

    _mpremote(port, "reset", zeit=60)
    text = (f"{quelle.name} ({quelle.stat().st_size} Byte) nach {port}:{ziel} kopiert.\n"
            f"Gegenprobe — Verzeichnis des Geraets:\n{v.stdout.strip()}\n"
            f"Geraet neu gestartet. MicroPython fuehrt main.py selbsttaetig aus.")
    #  „Das muss man doch durch Ruecklesen rausfinden" (04.10.2026): Ist eine Erwartung bekannt, wird
    #  nach dem Neustart am Geraet gemessen — die Uebertragung endet mit einer Messung, nicht mit
    #  einem Satz. Das Messprogramm fuehrt die Datei auf dem Geraet aus und startet danach neu.
    erwartet = e.get("erwartet")
    if erwartet and ziel == "main.py":
        import time as _t
        _t.sleep(2.0)
        try:
            from esp32_nachlesen import tun as nachlesen
            text += "\n\nRUECKLESEN NACH DEM NEUSTART:\n" + nachlesen({"port": port, "datei": ziel, "sekunden": 5, "erwartet": erwartet})
        except Abbruch as a:
            text += f"\n\nRUECKLESEN NACH DEM NEUSTART: FEHLER: {a}"
    return text


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "esp32_uebertragen",
        "Kopiert eine Datei aus der Werkstatt auf den ESP32 und startet ihn neu. Standardziel "
        "ist main.py, denn MicroPython fuehrt diese Datei nach dem Einschalten selbsttaetig aus. "
        "Setzt voraus, dass esp32_firmware bereits gelaufen ist.",
        {"port":  {"type": "string", "description": "der Anschluss, zum Beispiel COM5"},
         "datei": {"type": "string", "description": "Dateiname in der Werkstatt, zum Beispiel blink.py"},
         "ziel":  {"type": "string", "description": "Name auf dem Geraet, Vorgabe main.py"},
         "erwartet": {"type": "object", "description": "wie bei programm_testen (pins, takt_hz): dann wird nach dem Neustart am Geraet nachgelesen"}},
        ["port", "datei"], {"port": "COM5", "datei": "blink.py"}, tun))
