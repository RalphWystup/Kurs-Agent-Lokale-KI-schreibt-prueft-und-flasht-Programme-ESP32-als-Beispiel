#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Installiert ein Python-Paket — in die Ablage, nicht ins System.

Das eingebettete Python hat seine eigenen site-packages innerhalb der Ablage. Was hier
installiert wird, liegt dort und sonst nirgends. Ein vorhandenes Python des Rechners
bleibt unberuehrt, auch wenn dasselbe Paket dort in anderer Fassung liegt.

Liegen Paketdateien (.whl) im Paketordner, werden **nur** diese benutzt und das Netz gar
nicht erst gefragt. Damit laeuft der Kurs auch im Raum ohne Zugang.
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

from _muster import werkzeug, Abbruch, lauf, PAKET, PYTHON, python_exe
import re

# Nur was im Vorrat liegt, darf angefordert werden. Bis zum 02.10.2026 stand hier auch
# "adafruit-ampy" -- erlaubt, aber nicht mitgeliefert. Das Modell liest diese Liste und
# haette es anfordern koennen; im Kurs ohne Netz waere das gescheitert, und zwar erst
# dann, wenn zwanzig Leute davorsitzen. Was erlaubt ist, muss auch dasein (E5).
ERLAUBT = {"esptool", "pyserial", "mpremote", "setuptools", "wheel"}


def tun(e):
    name = str(e["paket"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise Abbruch(f"'{name}' ist kein zulaessiger Paketname. Ein Paketname besteht aus "
                      f"Buchstaben, Ziffern, Punkt, Strich und Unterstrich, zum Beispiel "
                      f"esptool oder pyserial.")
    if name.lower() not in ERLAUBT:
        #  Eine Abweisung, die einen gangbaren Weg verschweigt, schickt das Modell in die Schleife.
        #  Am 08.10.2026 verlangte es viermal hintereinander tkinter und bekam viermal dasselbe Nein,
        #  obwohl tkinter im Paket lag und 'umgebung_anlegen' es auspackt. Wer Nein sagt, sagt wohin.
        WEG = {"tkinter": "tkinter kommt nicht ueber pip. Es liegt als Archiv im Paket und wird von "
                          "umgebung_anlegen in das eigene Python gelegt. Rufe WERKZEUG: umgebung_anlegen {} auf.",
               "tk": "Siehe tkinter: Rufe WERKZEUG: umgebung_anlegen {} auf.",
               "machine": "'machine' gibt es nur auf dem Mikrocontroller, nicht auf diesem Rechner. "
                          "Programme dafuer prueft programm_testen; es baut 'machine' nach.",
               "micropython": "MicroPython laeuft auf dem Brett, nicht hier. Die Firmware spielt "
                              "esp32_firmware auf; Programme dafuer prueft programm_testen."}
        rat = WEG.get(name.lower(), "Dieses Paket wird hier nicht gebraucht. Wenn der Auftrag ohne "
                                    "es nicht geht, sage mit FERTIG, was fehlt und wofuer.")
        raise Abbruch(f"'{name}' steht nicht auf der Liste der erlaubten Pakete "
                      f"({', '.join(sorted(ERLAUBT))}). Der Kurs installiert nur, was er braucht.\n"
                      f"{rat}")
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")

    vorrat = PAKET / "pakete"
    offline = vorrat.is_dir() and any(vorrat.iterdir())
    befehl = [str(python_exe()), "-m", "pip", "install", "--no-warn-script-location", name]
    if offline:
        # --no-build-isolation ist hier Pflicht, nicht Geschmack: esptool wird nur als
        # Quelltext veroeffentlicht, und pip baut Quelltextpakete sonst in einer
        # abgeschotteten Umgebung, in die es sich setuptools **aus dem Netz** holt. Ohne
        # Netz endet das mit "Cannot import 'setuptools.build_meta'". Mit dem Schalter
        # nimmt pip das setuptools, das hier schon liegt.
        befehl[5:5] = ["--no-index", "--find-links", str(vorrat), "--no-build-isolation"]
        woher = f"aus mitgelieferten Dateien in {vorrat}"
    else:
        woher = "aus dem Netz (im Paket lagen keine Paketdateien)"

    # Das Werkzeug zum Bauen muss vorher stehen — sonst scheitert der erste Quelltextbau,
    # und zwar mit einer Meldung, die nach einem Fehler des Pakets aussieht.
    vorbereitung = []
    if offline and name.lower() not in ("setuptools", "wheel"):
        for grundlage in ("setuptools", "wheel"):
            p = lauf([str(python_exe()), "-c", f"import {grundlage}"], 120)
            if p.returncode != 0:
                g = lauf([str(python_exe()), "-m", "pip", "install", "--no-index",
                          "--find-links", str(vorrat), "--no-warn-script-location",
                          grundlage], 600)
                vorbereitung.append(f"{grundlage} "
                                    + ("nachinstalliert" if g.returncode == 0
                                       else f"liess sich nicht einrichten: {(g.stderr or '')[-150:]}"))

    r = lauf(befehl, 1800)
    if r.returncode != 0:
        raise Abbruch(f"Installation von {name} fehlgeschlagen ({woher}): "
                      f"{(r.stderr or r.stdout)[-500:]}\n"
                      f"Was jetzt hilft: Liegt die Paketdatei im Paketordner? Ist zuvor "
                      f"umgebung_anlegen gelaufen? Sage mit FERTIG, was fehlt, wenn der "
                      f"Auftrag ohne dieses Paket nicht geht.")

    # Gegenprobe: das Paket muss sich jetzt auch importieren lassen.
    modul = {"pyserial": "serial"}.get(name.lower(), name.replace("-", "_"))
    p = lauf([str(python_exe()), "-c",
              f"import {modul};print(getattr({modul},'__version__','?'))"], 120)
    if p.returncode != 0:
        #  Eine fehlgeschlagene Gegenprobe ist kein Erfolg (10.10.2026, gemessen). Bis dahin
        #  stand sie als Fussnote unter der Meldung „installiert" — das Modell las die erste
        #  Zeile, rief das naechste Werkzeug, bekam wieder „pyserial fehlt", installierte
        #  wieder, und so fort. Der Auftrag „blink.py auf das Brett laden" scheiterte daran
        #  in jedem der drei Durchgaenge. Wer „installiert" meldet, muss es nachweisen
        #  koennen (Grundsatz 39).
        raise Abbruch(
            f"{name} wurde zwar von pip eingerichtet ({woher}), laesst sich aber nicht "
            f"importieren:\n  import {modul} -> {(p.stderr or '').strip()[-220:]}\n"
            f"Damit ist es NICHT benutzbar. Haeufigste Ursache: 'import site' ist im "
            f"eingebetteten Python nicht freigeschaltet. Was jetzt hilft: "
            f"WERKZEUG: umgebung_anlegen {{}} aufrufen und danach hier noch einmal.")
    gegen = f"Gegenprobe: import {modul} -> Fassung {p.stdout.strip()}"
    vorab = ("Vorbereitung: " + ", ".join(vorbereitung) + "\n") if vorbereitung else ""
    return (f"{vorab}{name} installiert {woher}.\n"
            f"Ziel: {PYTHON} (nicht das Python des Rechners)\n{gegen}")


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "paket_installieren",
        "Installiert ein Python-Paket in die eigene Umgebung in der Ablage. Erlaubt sind nur: "
        + ", ".join(sorted(ERLAUBT)) + ". Fuer den ESP32 wird esptool gebraucht.",
        {"paket": {"type": "string", "description": "Name des Pakets, zum Beispiel esptool"}},
        ["paket"], {"paket": "esptool"}, tun))
