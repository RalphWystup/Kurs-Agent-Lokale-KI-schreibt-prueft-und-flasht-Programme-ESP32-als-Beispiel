#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entfernt alles, was der Agent angelegt hat — und weist nach, dass nichts blieb.

Das ist das Versprechen des ganzen Pakets: hinterher ist der Rechner so, wie er vorher
war. Einhalten laesst es sich nur, weil **alles Angelegte in einem einzigen Ordner
liegt**. Haette der Agent irgendwo sonst schreiben duerfen, waere dieses Werkzeug eine
Behauptung statt eines Beweises.

Darum gehoeren drei Dinge zusammen und stehen und fallen miteinander:

    in_der_ablage()   kein Schreiben ausserhalb        (im Muster)
    ABLAGE            ein einziger Ort                 (in pfade.py)
    aufraeumen        loeschen und nachzaehlen         (hier)

Berichtet wird, was vorher da war und was nachher noch da ist. Die zweite Zahl muss
null sein; steht sie nicht auf null, sagt das Werkzeug das und nennt die Reste.
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

from _muster import werkzeug, Abbruch, ABLAGE, PAKET, PYTHON, WURZEL
import os, shutil, signal, time


def _modell_beenden() -> str:
    """Beendet einen noch laufenden Modellserver — aber nur den eigenen.

    Eine Datei, die ein Programm offen haelt, laesst sich unter Windows nicht loeschen.
    Bricht jemand den Agenten mit Strg+C ab, laeuft llama-server weiter und haelt die
    Modelldatei fest; das Aufraeumen scheitert dann, und der Ordner bleibt liegen.

    Beendet wird die Prozessnummer, die modell.py beim Starten hinterlegt hat — nicht
    "alles, was llama-server heisst". Der Unterschied zaehlt: auf einem fremden Rechner
    koennte ein zweiter laufen, der uns nichts angeht.

    Nachgefragt, ob der Prozess nun wirklich tot ist, wird **nicht**. Der uebliche Griff
    dafuer, ``os.kill(pid, 0)``, ist unter Windows eine Falle: Python reicht dort jedes
    Signal an TerminateProcess weiter, die vermeintliche Abfrage beendet den Prozess also
    selbst — und bei einer inzwischen neu vergebenen Nummer einen wildfremden. Gebraucht
    wird die Antwort ohnehin nicht: ob das Loeschen gelang, sagt die Nachzaehlung
    unten, und die zaehlt Dateien statt Prozesse.
    """
    pid_datei = ABLAGE / "llama.pid"
    if not pid_datei.is_file():
        return ""
    try:
        pid = int(pid_datei.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return ""
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError) as e:
        return f"Der Modellserver (Prozess {pid}) lief nicht mehr ({type(e).__name__}).\n"
    time.sleep(2)                 # dem Prozess Zeit lassen, die Modelldatei freizugeben
    return f"Dem Modellserver (Prozess {pid}) wurde das Ende angesagt.\n"


def _zaehlen(ordner):
    n, b = 0, 0
    if ordner.is_dir():
        for p in ordner.rglob("*"):
            if p.is_file():
                n += 1
                try:
                    b += p.stat().st_size
                except OSError:
                    pass
    return n, b


def tun(e):
    if not ABLAGE.is_dir():
        return f"Es gibt nichts aufzuraeumen: {ABLAGE} besteht nicht."

    n, b = _zaehlen(ABLAGE)
    teile = sorted(p.name for p in ABLAGE.iterdir())
    if e.get("nur_zeigen"):
        return (f"In {ABLAGE} liegen {n} Dateien ({b/1e6:.1f} MB) in: {', '.join(teile)}.\n"
                f"Mit \"nur_zeigen\": false wird alles davon geloescht.")

    hinweis = _modell_beenden()
    shutil.rmtree(ABLAGE, ignore_errors=True)

    # Nachzaehlen statt annehmen.
    rest_n, rest_b = _zaehlen(ABLAGE)
    if ABLAGE.exists() or rest_n:
        reste = [p for p in ABLAGE.rglob("*") if p.is_file()]
        namen = [str(p.relative_to(ABLAGE)) for p in reste][:10]

        # Das eigene Python kann sich nicht selbst loeschen: Windows haelt die laufende
        # python.exe und ihre DLL fest. Das ist kein Fehler, sondern unvermeidlich — der
        # Agent laeuft ja mit genau diesem Python. Das Startskript raeumt den Rest ab,
        # nachdem Python beendet ist; dafuer wird hier eine Marke hinterlassen.
        eigenes = [p for p in reste if PYTHON in p.parents or p.parent == PYTHON]
        if len(eigenes) == len(reste):
            try:
                (ABLAGE / "_rest_entfernen").write_text(
                    "Diese Marke sagt dem Startskript, dass der Ordner ablage nach dem "
                    "Ende von Python noch zu entfernen ist.\n", encoding="utf-8")
            except OSError:
                pass
            return (hinweis + f"Geloescht: {n - rest_n} von {n} Dateien, "
                    f"{(b - rest_b)/1e6:.1f} MB.\n"
                    f"Zurueck blieben {rest_n} Dateien des Pythons, mit dem dieser Vorgang "
                    f"gerade laeuft — es kann sich nicht selbst loeschen:\n  "
                    + ", ".join(namen) + "\n"
                    f"Das Startskript entfernt sie, sobald Python beendet ist. Von Hand "
                    f"geht es auch: den Ordner {ABLAGE} loeschen.\n"
                    f"Am System wurde nichts geaendert: keine Installation, keine "
                    f"Registrierung, kein PATH, keine Adminrechte.")

        raise Abbruch(f"Es blieben {rest_n} Dateien zurueck: {', '.join(namen)}. "
                      f"Haeufigster Grund: eine Datei ist noch von einem Programm geoeffnet "
                      f"(Editor, serieller Monitor). Schliessen und wiederholen.")

    return (hinweis + f"Geloescht: {n} Dateien, {b/1e6:.1f} MB — der gesamte Ordner {ABLAGE}.\n"
            f"Nachgezaehlt: {ABLAGE} besteht nicht mehr, 0 Dateien zurueck.\n"
            f"Unberuehrt bleiben das mitgelieferte Paket ({PAKET.name}) und der Agent selbst; "
            f"sie wurden nie veraendert.\n"
            f"Am System wurde nichts geaendert: keine Installation, keine Registrierung, "
            f"kein PATH, keine Adminrechte. Was der ESP32 gelernt hat, bleibt auf dem ESP32.")


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "aufraeumen",
        "Loescht alles, was im Lauf angelegt wurde: das eigene Python, die installierten Pakete "
        "und die erzeugten Dateien. Zaehlt danach nach, dass nichts zurueckblieb. Am Ende der "
        "Arbeit aufrufen.",
        {"nur_zeigen": {"type": "boolean",
                        "description": "true: nur auflisten, was geloescht wuerde, und nichts loeschen"}},
        [], {"nur_zeigen": True}, tun))
