#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Der gemeinsame Rahmen aller Werkzeuge.

Ein Werkzeug ist ein eigenständiges Programm mit genau zwei Betriebsarten:

    werkzeug.py --beschreibung     sagt als JSON, was es kann und was es braucht
    werkzeug.py '<json>'           tut es und schreibt das Ergebnis als Text

Das Modell liest die Beschreibungen und entscheidet. Mehr Verbindung zwischen Modell und
Werkzeug gibt es nicht — deshalb lässt sich jedes Werkzeug ohne Modell von Hand prüfen.

Zwei Regeln, die hier und nicht in den einzelnen Werkzeugen stehen, damit sie überall
gleich gelten:

  * Ein Fehler wird **Text**, nie eine Ausnahme. Sonst stürzt der Agent beim ersten
    Tippfehler des Modells ab, statt ihn dem Modell zurückzugeben, das ihn beheben kann.
  * Jedes Schreiben geht in die Ablage. Der Weg dorthin wird geprüft, nicht geglaubt.
"""
from __future__ import annotations
import sys, pathlib
# Der eigene Ordner und der des Agenten muessen in den Suchpfad, bevor etwas daraus geholt
# wird. Unter einem gewoehnlichen Python stehen sie von selbst darin — beim eingebetteten
# Python nicht: dort legt python3xx._pth den Suchpfad abschliessend fest, und sys.path hat
# genau zwei Eintraege. Ohne diese Zeilen scheitert jedes Werkzeug auf dem Kursrechner mit
# "No module named _muster", waehrend es auf dem Entwicklungsrechner tadellos laeuft.
_hier = pathlib.Path(__file__).resolve().parent

# Die Windows-Konsole gibt sonst Fragezeichen statt Umlauten und Gedankenstrichen aus — der
# Standard dort ist keine UTF-8-Codepage. Das Startskript setzt zwar chcp 65001, aber ein
# Werkzeug, das jemand einzeln aufruft, laeuft ohne dieses Startskript.
for _strom in (sys.stdout, sys.stderr):
    try:
        _strom.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json, subprocess, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from pfade import (ABLAGE, PAKET, PIP_CACHE, PYTHON, WERKSTATT, WURZEL,   # noqa: E402
                   python_exe, eine, umgebung)
import sauber
sauber.sicherstellen()   # vor allem anderen: saubere Umgebung

import waechter                                                            # noqa: E402

waechter.anmelden(ABLAGE, PAKET)


# Wie die Ausgabe eines Unterprozesses gelesen wird. Ohne diese Angabe nimmt Windows
# cp1252 — die Werkzeuge schreiben aber UTF-8 (sonst kaeme statt eines Gedankenstrichs ein
# Fragezeichen). Trifft dann ein Zeichen ausserhalb von cp1252 ein, wirft der Leser einen
# UnicodeDecodeError in einem Nebenlauf, und subprocess liefert eine **leere** Ausgabe bei
# Rueckgabewert 0: das Werkzeug lief, und niemand erfaehrt, was es sagte.
LESEN = {"encoding": "utf-8", "errors": "replace"}


def lauf(befehl, zeit=300, teilausgabe=False):
    """Startet ein Programm — die **einzige** Stelle im Bausatz, die das tut.

    Dass sie die einzige ist, hat einen Grund: jeder Unterprozess muss in der
    abgeschirmten Umgebung laufen (siehe umgebung() in pfade.py). Stuende der Aufruf an
    sieben Stellen, wuerde das achte Werkzeug es vergessen, und zwar unbemerkt — denn auf
    dem Rechner des Erbauers ist PYTHONPATH nicht gesetzt und der pip-Zwischenspeicher
    schon warm. Der Fehler zeigte sich erst im Kurs, auf einem fremden Rechner.
    """
    try:
        return subprocess.run(befehl, capture_output=True, text=True, timeout=zeit,
                              env=umgebung(), **LESEN)
    except subprocess.TimeoutExpired as e:
        if not teilausgabe:
            raise
        # Bei einer Zeitgrenze verwirft subprocess.run das bis dahin Gesagte — und genau
        # darauf kommt es an, wenn ein Programm absichtlich nicht endet (eine Blinkschleife
        # etwa). Mit teilausgabe=True wird das Gesammelte zurueckgegeben, so als waere das
        # Programm regulaer beendet worden; der Aufrufer erkennt es am Rueckgabewert -1.
        def _text(x):
            return x.decode("utf-8", "replace") if isinstance(x, bytes) else (x or "")
        return subprocess.CompletedProcess(befehl, -1, _text(e.stdout), _text(e.stderr))


class Abbruch(Exception):
    """Ein erwarteter Fehlschlag mit einer Erklärung, die das Modell lesen soll."""


def in_der_ablage(p) -> pathlib.Path:
    """Gibt den Pfad zurück — aber nur, wenn er wirklich in der Ablage liegt.

    Ohne diese Prüfung genügt ein ``..\\..\\Windows`` im Dateinamen, den das Modell
    vorschlägt, um ausserhalb zu schreiben. Geprüft wird der **aufgeloeste** Pfad, denn
    erst nach dem Aufloesen steht fest, wo er endet.
    """
    ziel = (ABLAGE / p).resolve() if not pathlib.Path(p).is_absolute() else pathlib.Path(p).resolve()
    if ABLAGE.resolve() not in ziel.parents and ziel != ABLAGE.resolve():
        raise Abbruch(f"{ziel} liegt nicht in der Ablage ({ABLAGE}). "
                      f"Nur dort darf geschrieben werden, denn nur sie wird am Ende geloescht.")
    return ziel


def werkzeug(name: str, zweck: str, felder: dict, pflicht: list, probe: dict, tun) -> int:
    if len(sys.argv) < 2:
        print(f"Aufruf: {pathlib.Path(sys.argv[0]).name} --beschreibung | --probe | '<json>'")
        return 2
    if sys.argv[1] == "--beschreibung":
        print(json.dumps({"name": name, "description": zweck,
                          "input_schema": {"type": "object", "properties": felder,
                                           "required": pflicht}}, ensure_ascii=False))
        return 0
    eingabe = probe if sys.argv[1] == "--probe" else None
    if eingabe is None:
        try:
            eingabe = json.loads(sys.argv[1])
        except json.JSONDecodeError as e:
            print(f"FEHLER: die Eingabe ist kein gueltiges JSON: {e}")
            return 0
    try:
        print(tun(eingabe))
        if waechter.verstoesse():
            print(waechter.bericht())
    except Abbruch as e:
        print(f"FEHLER: {e}")
    except Exception as e:                      # noqa: BLE001 — Absicht, siehe oben
        print(f"FEHLER: {type(e).__name__}: {e}")
    return 0
