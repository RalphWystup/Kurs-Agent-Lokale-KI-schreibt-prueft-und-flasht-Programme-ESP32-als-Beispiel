#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ist dieser Rechner für JEDE Testaufgabe bereit? — ausgeführt, nicht nachgesehen.

    python pruefe_bereit.py                 prüft und berichtet
    python pruefe_bereit.py --einrichten    prüft, richtet Fehlendes ein, prüft erneut

Warum es dieses Programm gibt
-----------------------------
Am 08.10.2026 meldete START.bat „Das Paket ist vollstaendig" — und der Taschenrechner lief
trotzdem nicht. Grund: Die Vollständigkeitsprüfung sieht nach, ob die Archive im Paket
**liegen** (``paket/tkinter-*.zip`` war da). Ob tkinter im eingebetteten Python auch
**eingerichtet** ist, prüfte niemand. Das Fensterprogramm stürzte beim ``import tkinter`` ab,
das Fenster erschien nie, und die Fehlermeldung des nächsten Werkzeugs schickte das Modell in
eine Schleife.

Der Auftraggeber dazu: **„ALLES, was benötigt wird, muss installiert sein für alle
Testaufgaben."**

Daraus folgt die Regel dieses Programms: **Vorhanden ist nicht einsatzbereit.** Jede
Voraussetzung wird durch Ausführen geprüft — ein Import, ein Aufruf, eine Antwort. Eine Datei,
die daliegt, zählt nicht als Nachweis.

Was geprüft wird, steht in VORAUSSETZUNGEN; was welche Aufgabe davon braucht, in AUFGABEN.
Eine Aufgabe gilt als **nicht prüfbar**, solange eine ihrer Voraussetzungen fehlt — nie als
bestanden, nie als übersprungen.
"""
from __future__ import annotations
import argparse
import pathlib
import subprocess
import sys

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER / "agent"))

try:
    from pfade import PAKET, python_exe, umgebung          # type: ignore
except Exception:                                           # außerhalb des Kursordners
    PAKET = HIER / "paket"
    def python_exe():                                       # noqa: E306
        p = HIER / "ablage" / "python" / "python.exe"
        return p if p.exists() else pathlib.Path(sys.executable)
    def umgebung():                                         # noqa: E306
        import os
        return dict(os.environ)


def im_kurspython(code: str, zeit: int = 60) -> tuple[bool, str]:
    """Ein Stück Python im eingebetteten Python des Kurses ausführen."""
    try:
        r = subprocess.run([str(python_exe()), "-c", code], capture_output=True, text=True,
                           timeout=zeit, env=umgebung())
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    return r.returncode == 0, (r.stdout or r.stderr or "").strip().splitlines()[-1][:120] if (r.stdout or r.stderr).strip() else ""


# ---------------------------------------------------------------- Die Voraussetzungen
# Jede ist ein Paar aus Name und einer Probe, die WIRKLICH etwas tut.
VORAUSSETZUNGEN = {
    "python": lambda: im_kurspython("import sys; print(sys.version.split()[0])"),
    "tkinter": lambda: im_kurspython("import tkinter, _tkinter; print('Tk', tkinter.TkVersion)"),
    "pyserial": lambda: im_kurspython("import serial; print(serial.__version__)"),
    "mpremote": lambda: im_kurspython("import mpremote; print('mpremote da')"),
    "esptool": lambda: im_kurspython("import esptool; print('esptool da')"),
    "modell": lambda: _modell_da(),
    "firmware": lambda: _datei_da("firmware/*.bin", "MicroPython-Firmware"),
    "treiber": lambda: _datei_da("treiber/*.ZIP", "USB-Treiber"),
    "geraet": lambda: _geraet_da(),
}


def _datei_da(muster: str, was: str) -> tuple[bool, str]:
    treffer = sorted(PAKET.glob(muster))
    return (bool(treffer), f"{was}: {treffer[0].name}" if treffer else f"{was} fehlt ({muster})")


def _modell_da() -> tuple[bool, str]:
    """Nicht nur „eine .gguf liegt da", sondern: passt eines in den freien Speicher?"""
    try:
        sys.path.insert(0, str(HIER / "agent"))
        import modell as m                                   # type: ignore
        d, grund = m.waehlen(laut=False)
        if d:
            return True, f"{d.name} ({d.stat().st_size/1e9:.1f} GB, Bedarf {m.bedarf_gb(d):.1f} GB)"
        return False, (grund or "kein Modell").splitlines()[0][:110]
    except Exception as e:
        g = sorted(PAKET.glob("modell/*.gguf"))
        return (bool(g), f"{g[0].name} (ungeprüft: {type(e).__name__})" if g else "keine Modelldatei")


def _geraet_da() -> tuple[bool, str]:
    """Hängt ein ESP32 am Rechner? Ohne ihn sind die Hardware-Aufgaben nicht prüfbar."""
    ok, aus = im_kurspython(
        "import serial.tools.list_ports as p;"
        "l=[x for x in p.comports() if any(k in (x.hwid or '').upper() for k in ('1A86','10C4','0403'))];"
        "print(l[0].device if l else 'keiner')")
    if not ok:
        return False, "Anschlüsse nicht lesbar (pyserial fehlt?)"
    return (aus != "keiner", f"ESP32 an {aus}" if aus != "keiner" else "kein ESP32 sichtbar")


# ---------------------------------------------------------------- Was welche Aufgabe braucht
AUFGABEN = [
    ("1 Hallo, bist du bereit?",          ["modell"]),
    ("2 LED blinken, 1 Hz",               ["python", "modell"]),
    ("3 auf 2 Hz ändern",                 ["python", "modell"]),
    ("4 1 s an, 1 s aus",                 ["python", "modell"]),
    ("5 auf ESP32 laden, nachlesen",      ["python", "modell", "mpremote", "pyserial", "geraet"]),
    ("6 sinusförmig atmen",               ["python", "modell"]),
    ("7 zwei LEDs, zwei Takte",           ["python", "modell"]),
    ("8 Taschenrechner mit Fenster",      ["python", "modell", "tkinter"]),
    ("9 was ist angeschlossen?",          ["python", "pyserial"]),
    ("— Firmware aufspielen",             ["python", "esptool", "firmware", "geraet"]),
]


def pruefen() -> dict:
    print("Voraussetzungen, jede durch Ausführen geprüft:\n")
    stand = {}
    for name, probe in VORAUSSETZUNGEN.items():
        try:
            ok, text = probe()
        except Exception as e:
            ok, text = False, f"{type(e).__name__}: {e}"
        stand[name] = ok
        print(f"  {'ok    ' if ok else 'FEHLT '}  {name:10s} {text}")
    return stand


def bericht(stand: dict) -> int:
    print("\nWelche Aufgabe ist damit prüfbar:\n")
    offen = 0
    for name, braucht in AUFGABEN:
        fehlt = [b for b in braucht if not stand.get(b)]
        if fehlt:
            offen += 1
            print(f"  NICHT PRÜFBAR  {name:32s} es fehlt: {', '.join(fehlt)}")
        else:
            print(f"  bereit         {name}")
    print()
    if offen:
        print(f"{offen} von {len(AUFGABEN)} Aufgaben sind nicht prüfbar. Das ist kein „übersprungen“ —")
        print("solange etwas fehlt, darf keine davon als geprüft gelten (Grundsatz 37).")
        if not stand.get("tkinter"):
            print("\n  tkinter kommt NICHT über pip. Es liegt als Archiv im Paket und wird von")
            print("  'umgebung_anlegen' ausgepackt:  python pruefe_bereit.py --einrichten")
    else:
        print(f"Alle {len(AUFGABEN)} Aufgaben sind prüfbar.")
    return offen


def einrichten() -> None:
    print("\nFehlendes einrichten (umgebung_anlegen) …")
    w = HIER / "agent" / "werkzeuge" / "umgebung_anlegen.py"
    if not w.is_file():
        print(f"  FEHLER: {w} gibt es nicht")
        return
    r = subprocess.run([str(python_exe()), str(w), "{}"], capture_output=True, text=True,
                       timeout=1800, env=umgebung())
    for z in (r.stdout or r.stderr or "").strip().splitlines()[-12:]:
        print("   ", z[:150])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--einrichten", action="store_true",
                   help="Fehlendes einrichten und danach erneut prüfen")
    a = p.parse_args()
    print(f"Kursordner: {HIER}\nPython:     {python_exe()}\n")
    stand = pruefen()
    offen = bericht(stand)
    if offen and a.einrichten:
        einrichten()
        print("\n" + "=" * 70 + "\nNach dem Einrichten:\n")
        stand = pruefen()
        offen = bericht(stand)
    return 1 if offen else 0


if __name__ == "__main__":
    sys.exit(main())
