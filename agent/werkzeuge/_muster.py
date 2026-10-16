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

# Kein leeres Konsolenfenster (10.10.2026). Jedes Werkzeug startet seinerseits Programme —
# pip, den Interpreter fuer das erzeugte Programm, esptool. Ohne dieses Kennzeichen blitzt
# fuer jedes davon ein schwarzes Fenster auf dem Bildschirm auf; bei einem Auftrag mit
# zehn Aufrufen zehnmal. Der Auftraggeber: „da blinkt dauernd ein Fenster bei mir auf,
# sehr aggressiv." Die Fenster, die man SEHEN soll — Simulation und Ladevorgang —, starten
# abgeloest mit DETACHED_PROCESS und sind davon nicht betroffen.
OHNE_FENSTER = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


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
                              env=umgebung(), **OHNE_FENSTER, **LESEN)
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


class Leitung:
    """Meldet die serielle Leitung an, damit das Mitlese-Fenster zuruecktritt.

    Warum es das gibt (10.10.2026, in seinem eigenen Lauf gefunden):

        15:43:43  esp32_laden      LADEN BESTANDEN      -> Mitlesefenster geht auf
        15:44:25  esp32_nachlesen  FEHLER: failed to access COM3
                                   (it may be in use by another program)

    Nach jedem erfolgreichen Laden oeffnet esp32_laden ein Fenster, das den Anschluss
    offenhaelt und mitliest — das ist gewollt, der Auftraggeber will sehen, was das Brett
    sagt („ich will den download sehen und die rueckmeldungen, live", 10.10.2026). Das
    Fenster tritt auch zurueck, sobald jemand „belegt" in eine Marke schreibt.

    Nur: Das tat genau EIN Werkzeug von sieben. esp32_nachlesen, esp32_uebertragen,
    esp32_pruefsumme, esp32_firmware, esp32_mitlesen und geraet_zeigen meldeten sich nicht
    an — und scheiterten deshalb an einem Fenster, das der Agent selbst geoeffnet hatte.
    Der Geraeteauftrag brach danach ab.

    Eine Loesung in sieben Dateien ist keine. Darum steht sie hier, einmal, und jedes
    Werkzeug, das die Leitung braucht, umschliesst seinen Zugriff damit:

        with Leitung():
            ... hier wird COM3 benutzt ...

    Die Marke wird beim Austritt wieder auf „frei" gesetzt, damit das Fenster weiterliest.
    """

    MARKE = "esp32_leitung.txt"
    WARTEN = 1.2        # dem Fenster Zeit lassen, die Leitung wirklich loszulassen

    #  Verschachtelbar: Ein Werkzeug ruft mpremote oft mehrmals hintereinander. Ohne
    #  Zaehler wuerde jeder Aufruf die 1,2 s erneut kosten und die Marke zwischendurch
    #  freigeben — das Fenster griffe in der Luecke wieder zu. Angemeldet wird einmal,
    #  freigegeben wird, wenn der aeusserste Block endet.
    _tiefe = 0

    def __init__(self, warten: float = None, port: str = ""):
        self.warten = self.WARTEN if warten is None else warten
        self.marke = in_der_ablage(self.MARKE)
        #  Mit Anschluss wird die Hardware geprueft, ohne nur die Marke gesetzt.
        self.port = port or ""

    def __enter__(self):
        import time as _t
        Leitung._tiefe += 1
        if Leitung._tiefe > 1:
            return self                       # schon angemeldet
        try:
            self.marke.write_text("belegt", encoding="utf-8")
        except OSError:
            return self          # ohne Marke geht es weiter wie frueher — kein Abbruch
        _t.sleep(self.warten)
        if self.port:
            self.pruefen(self.port)
        return self

    def pruefen(self, port: str) -> None:
        """Ist der Anschluss wirklich frei? Fragt die Hardware, bevor gearbeitet wird.

        Anweisung des Auftraggebers (10.10.2026): „Hardware muss man immer testen — das
        Downloadprogramm muss das doch aber selbst tun, wenn es aufgerufen wird."

        Genau darum steht die Pruefung hier und nicht in sieben Werkzeugen: Wer die
        Leitung anmeldet, prueft sie auch. Was dabei herauskommt, ist eine Meldung, die
        ein Mensch versteht — nicht „failed to access COM3 (it may be in use by another
        program)", sondern WER ihn haelt und was zu tun ist.
        """
        try:
            import serial                                           # noqa: F401
        except ImportError:
            return                      # ohne pyserial kann hier nicht geprueft werden
        import serial as _s
        try:
            _s.Serial(port, 115200, timeout=0.2).close()
            return                                                  # frei
        except Exception as ex:
            fenster = in_der_ablage("esp32_fenster.pid")
            wer = ""
            if fenster.is_file():
                wer = (" Ein Mitlese-Fenster des Agenten ist offen (es wurde nach dem "
                       "letzten Laden geoeffnet) — schliesse es, dann ist der Anschluss frei.")
            raise Abbruch(
                f"{port} ist belegt: {type(ex).__name__}: {str(ex)[:160]}\n"
                f"Der Anschluss existiert, aber ein anderes Programm haelt ihn.{wer}\n"
                f"Haeufige Ursachen: ein offenes Mitlese- oder Vorfuehrfenster, Thonny, "
                f"ein serieller Monitor, oder ein frueherer Lauf, der nicht beendet wurde.\n"
                f"Geprueft wurde, BEVOR gearbeitet wurde — am Geraet ist nichts veraendert.")

    def __exit__(self, *_):
        #  Immer freigeben, auch wenn der Zugriff scheiterte: Eine stehengebliebene
        #  Marke „belegt" wuerde das Fenster dauerhaft stumm schalten.
        Leitung._tiefe = max(0, Leitung._tiefe - 1)
        if Leitung._tiefe:
            return False                      # ein aeusserer Block haelt sie noch
        try:
            self.marke.write_text("frei", encoding="utf-8")
        except OSError:
            pass
        return False


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
