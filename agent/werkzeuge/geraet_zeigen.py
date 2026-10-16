#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Was liegt auf dem Brett, wieviel Platz ist da, welche Fassung laeuft — eine Auskunft, kein Urteil.

Warum es dieses Werkzeug gibt
-----------------------------
Vor dem Uebertragen und danach muss man wissen, womit man es zu tun hat: Liegt dort schon eine
main.py, und wie gross ist sie? Ist ueberhaupt Platz? Welche MicroPython-Fassung? Bis zum
09.10.2026 gab es dafuer nur den Umweg ueber esp32_uebertragen, das dabei gleich schreibt — man
musste also etwas aendern, um etwas zu sehen.

Diese Auskunft aendert nichts. Sie liest. Was sie liefert, ist nachpruefbar: jede Zahl kommt vom
Geraet, keine vom Rechner.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, lauf, python_exe, Leitung
import re

AUF_DEM_BRETT = """
import os, sys, gc, time
try:
    import machine
    takt = machine.freq()
except Exception:
    takt = 0
print('FASSUNG', sys.version.replace(' ', '_'))
print('PLATTFORM', sys.platform)
print('TAKT', takt)
print('RAMFREI', gc.mem_free())
print('RAMBELEGT', gc.mem_alloc())
try:
    s = os.statvfs('/')
    print('FLASHFREI', s[0] * s[3])
    print('FLASHGANZ', s[0] * s[2])
except Exception as e:
    print('FLASHFEHLER', repr(e))
print('LAUFZEIT_MS', time.ticks_ms())
for n in os.listdir('/'):
    try:
        print('DATEI', n, os.stat('/' + n)[6])
    except Exception:
        print('DATEI', n, -1)
"""


def tun(e):
    port = str(e["port"]).strip()
    if not re.fullmatch(r"(COM\d+|/dev/[A-Za-z0-9._/-]+)", port):
        raise Abbruch(f"'{port}' sieht nicht wie ein Anschluss aus. "
                      f"Welche es gibt, sagt WERKZEUG: ports_zeigen {{}}")
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")
    with Leitung(port=port):
        r = lauf([str(python_exe()), "-m", "mpremote", "connect", port, "exec", AUF_DEM_BRETT], 120)
    text = (r.stdout or "") + (r.stderr or "")
    if "ModuleNotFoundError" in text or "No module named mpremote" in text:
        raise Abbruch("mpremote fehlt. Rufe WERKZEUG: paket_installieren {\"paket\": \"mpremote\"} auf.")
    if "FASSUNG" not in text:
        raise Abbruch(f"Das Brett an {port} antwortet nicht wie MicroPython: {text[-400:]}\n"
                      f"Laeuft MicroPython darauf? Das spielt WERKZEUG: esp32_firmware auf. "
                      f"Haelt ein anderes Programm den Anschluss?")

    w = {}
    dateien = []
    for z in text.splitlines():
        t = z.split()
        if not t:
            continue
        if t[0] == "DATEI" and len(t) >= 3:
            dateien.append((t[1], int(t[2])))
        elif len(t) >= 2:
            w[t[0]] = " ".join(t[1:])

    z = [f"Das Brett an {port}:"]
    if "FASSUNG" in w:
        z.append(f"  MicroPython: {w['FASSUNG'].replace('_', ' ')}  auf {w.get('PLATTFORM', '?')}")
    if w.get("TAKT", "0") != "0":
        z.append(f"  Taktfrequenz: {int(w['TAKT'])/1e6:.0f} MHz")
    if "RAMFREI" in w:
        frei, belegt = int(w["RAMFREI"]), int(w.get("RAMBELEGT", 0))
        z.append(f"  Arbeitsspeicher: {frei/1024:.0f} kB frei von {(frei+belegt)/1024:.0f} kB")
    if "FLASHFREI" in w:
        z.append(f"  Dateispeicher: {int(w['FLASHFREI'])/1024:.0f} kB frei von "
                 f"{int(w.get('FLASHGANZ', 0))/1024:.0f} kB")
    if "LAUFZEIT_MS" in w:
        s = int(w["LAUFZEIT_MS"]) / 1000
        z.append(f"  Laeuft seit {s:.0f} s (seit dem letzten Neustart)")
    z.append("")
    if dateien:
        z.append(f"  Dateien auf dem Brett ({len(dateien)}):")
        for n, g in sorted(dateien):
            z.append(f"    {n:<24} {g if g >= 0 else '?':>8} Byte")
        hat_main = any(n == "main.py" for n, _ in dateien)
        z.append("")
        if hat_main:
            g = next(g for n, g in dateien if n == "main.py")
            z.append(f"  main.py liegt dort ({g} Byte) und wird nach jedem Einschalten "
                     f"selbsttaetig ausgefuehrt.")
            z.append(f"  Ob es dieselbe Datei ist wie in der Werkstatt, sagt "
                     f"WERKZEUG: esp32_pruefsumme {{\"port\": \"{port}\", \"datei\": \"<name>.py\"}}")
        else:
            z.append("  Es liegt keine main.py auf dem Brett — nach dem Einschalten laeuft "
                     "dort nichts von selbst.")
    else:
        z.append("  Auf dem Brett liegt keine Datei.")
    z.append("")
    z.append("Dies ist eine Auskunft, kein Urteil: Was hier steht, hat das Geraet selbst gemeldet.")
    return "\n".join(z)


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "geraet_zeigen",
        "Fragt den ESP32, was auf ihm liegt: MicroPython-Fassung, Takt, freier Arbeits- und "
        "Dateispeicher, Laufzeit seit dem Neustart und alle Dateien mit Groesse. Aendert nichts. "
        "Rufe es vor und nach dem Uebertragen auf, um zu sehen, was sich getan hat.",
        {"port": {"type": "string", "description": "der Anschluss, zum Beispiel COM3"}},
        ["port"], {"port": "COM3"}, tun))
