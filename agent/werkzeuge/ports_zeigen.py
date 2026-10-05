#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zaehlt die seriellen Anschluesse auf und sagt, welcher nach einem ESP32 aussieht.

Ein ESP32-Steckbrett haengt am Rechner an einem USB-Seriell-Wandler. Dessen Hersteller-
und Geraetenummer steht im Geraetebaum; daran laesst sich ein Vorschlag ablesen. Ein
Vorschlag — mehr nicht: angeschlossen sein koennen auch ein Messgeraet, eine Steuerung
oder ein zweites Steckbrett. Darum **waehlt dieses Werkzeug nicht aus**, es zeigt nur,
und das Flashen verlangt den Anschluss ausdruecklich.

Bekannte Wandler:
    10C4:EA60  Silicon Labs CP2102     die haeufigste Variante
    1A86:7523  QinHeng CH340           verbreitet auf guenstigen Steckbrettern
    1A86:55D4  QinHeng CH9102
    0403:6001  FTDI FT232R
    303A:*     Espressif selbst        ESP32-S2/S3 mit eingebautem USB
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

from _muster import werkzeug, Abbruch, lauf, python_exe
import json

WANDLER = {"10C4:EA60": "Silicon Labs CP2102", "1A86:7523": "QinHeng CH340",
           "1A86:55D4": "QinHeng CH9102", "0403:6001": "FTDI FT232R",
           "0403:6015": "FTDI FT231X", "303A:1001": "Espressif USB (S2/S3)",
           "303A:0002": "Espressif USB (S2/S3)"}

ABFRAGE = r"""
import json, serial.tools.list_ports as lp
print(json.dumps([{"port": p.device, "name": p.description or "",
                   "hersteller": p.manufacturer or "",
                   "vid": p.vid, "pid": p.pid} for p in lp.comports()]))
"""


def tun(e):
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")
    r = lauf([str(python_exe()), "-c", ABFRAGE], 120)
    if r.returncode != 0:
        if "ModuleNotFoundError" in (r.stderr or ""):
            raise Abbruch("pyserial fehlt. Erst paket_installieren mit esptool aufrufen "
                          "(pyserial kommt dabei mit).")
        raise Abbruch(f"Die Anschluesse liessen sich nicht auflisten: {(r.stderr or '')[-300:]}")

    liste = json.loads(r.stdout)
    if not liste:
        return ("Es ist kein serieller Anschluss sichtbar.\n"
                "Zu pruefen: Steckbrett eingesteckt? USB-Kabel mit Datenadern (nicht nur Ladekabel)? "
                "Treiber fuer CP2102 oder CH340 vorhanden?")

    z, vorschlag = [], None
    for p in liste:
        kennung = f"{p['vid']:04X}:{p['pid']:04X}" if p["vid"] else "—"
        bekannt = WANDLER.get(kennung)
        z.append(f"  {p['port']:8s} {kennung:9s} {p['name']}"
                 + (f"   <- {bekannt}" if bekannt else ""))
        if bekannt and vorschlag is None:
            vorschlag = p["port"]

    s = f"{len(liste)} serielle(r) Anschluss/Anschluesse:\n" + "\n".join(z)
    s += (f"\n\nNach dem Wandler zu urteilen koennte der ESP32 an {vorschlag} haengen."
          if vorschlag else
          "\n\nKeiner traegt die Kennung eines bekannten USB-Seriell-Wandlers.")
    s += ("\nDas ist ein Vorschlag, keine Feststellung: an einem solchen Anschluss kann auch "
          "ein anderes Geraet haengen. Der Anschluss ist beim Flashen ausdruecklich anzugeben.")
    return s


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "ports_zeigen",
        "Zeigt alle seriellen Anschluesse (COM-Ports) des Rechners und markiert, welcher nach "
        "einem USB-Seriell-Wandler eines ESP32 aussieht. Vor dem Flashen aufrufen.",
        {}, [], {}, tun))
