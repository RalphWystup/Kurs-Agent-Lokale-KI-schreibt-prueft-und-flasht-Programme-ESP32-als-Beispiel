#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Richtet ein eigenes Python in der Ablage ein — ohne Installation.

Was hier „installieren" heisst, ist genau genommen **entpacken**. Das eingebettete
Python von python.org ist ein ZIP-Archiv: ausgepackt laeuft es, geloescht ist es weg.
Es traegt sich nicht in die Registrierung ein, aendert kein PATH, braucht keine
Adminrechte und beruehrt ein bereits vorhandenes Python nicht.

Der eine Stolperstein: In ``python3xx._pth`` ist die Zeile ``import site``
auskommentiert. Solange das so bleibt, findet das entpackte Python keine
installierten Pakete — pip laeuft dann zwar durch, aber nichts ist danach
importierbar. Die Zeile wird hier freigeschaltet.
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

from _muster import werkzeug, Abbruch, lauf, PAKET, PYTHON, ABLAGE, eine, python_exe
import zipfile, sys, urllib.request

PYTHON_URL  = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
GETPIP_URL  = "https://bootstrap.pypa.io/get-pip.py"


def _beschaffen(muster: str, url: str, name: str) -> "object":
    """Nimmt die mitgelieferte Datei. Laedt nichts.

    Bis zum 02.10.2026 lud diese Stelle nach, wenn nichts da war -- und legte das
    Geladene nach paket\\. Beides widerspricht dem, was das Paket verspricht: im Kurs
    wird nichts aus dem Netz geholt (A2), und paket\\ wird nur gelesen (C5). Der
    Hinweis auf die Adresse bleibt stehen, damit die Meldung sagt, was fehlt und
    woher es stammt -- geholt wird es dort nicht.
    """
    d = eine(muster)
    if d:
        return d, f"mitgeliefert ({d.name}, {d.stat().st_size} Byte)"
    raise Abbruch(f"{name} liegt nicht im Paket ({muster}). Es wird nichts aus dem Netz "
                  f"geholt. Naechster Schritt: START.bat auf dem Vorbereitungsrechner "
                  f"starten -- es fuellt das Paket nach; oder {name} von {url} "
                  f"herunterladen und nach {PAKET} legen.")


def _pip_da() -> str | None:
    """Antwortet pip? Gibt seine Fassung zurueck oder None."""
    r = lauf([str(python_exe()), "-m", "pip", "--version"], 120)
    return r.stdout.strip() if r.returncode == 0 else None


def tun(e):
    z = []

    # --- Schritt 1: Python, falls es fehlt -----------------------------------------
    # Nicht "falls e['neu']": das Startskript packt das Python bereits aus, damit der Agent
    # ueberhaupt laufen kann. Wer hier frueher ausstieg, weil "Python liegt schon da", liess
    # pip ungetan — und bemerkte es erst beim ersten paket_installieren.
    if not python_exe().exists():
        quelle, woher = _beschaffen("python-*-embed-*.zip", PYTHON_URL,
                                    "python-3.12.10-embed-amd64.zip")
        z.append(f"Python-Archiv: {woher}")
        PYTHON.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(quelle) as a:
            a.extractall(PYTHON)
        if not python_exe().exists():
            raise Abbruch(f"Nach dem Entpacken fehlt {python_exe()}. "
                          f"Ist das Archiv das eingebettete Paket fuer Windows?")
        z.append(f"entpackt nach {PYTHON}")
    else:
        z.append(f"Python liegt bereits in {PYTHON} — wird weiterverwendet.")
        if e.get("neu"):
            # Das laufende Python laesst sich nicht ueberschreiben; unter Windows haelt das
            # Betriebssystem die Datei. Darauf hinweisen statt daran scheitern.
            z.append("Hinweis: 'neu' wurde uebergangen. Dieses Python fuehrt gerade den "
                     "Agenten aus und kann sich nicht selbst ersetzen. Fuer eine frische "
                     "Einrichtung erst aufraeumen, dann neu starten.")

    # --- Schritt 2: import site freischalten ---------------------------------------
    pth = next(iter(sorted(PYTHON.glob("python3*._pth"))), None)
    if pth:
        text = pth.read_text(encoding="utf-8")
        if "#import site" in text:
            pth.write_text(text.replace("#import site", "import site"), encoding="utf-8")
            z.append(f"{pth.name}: 'import site' freigeschaltet")
        else:
            z.append(f"{pth.name}: 'import site' war bereits aktiv")
    else:
        z.append("kein ._pth gefunden — das ist bei diesem Archiv ungewoehnlich")

    # --- Schritt 2b: tkinter aus dem Paket, falls mitgeliefert ------------------------
    # Das eingebettete Python kommt ohne tkinter. Fuer Programme mit Fenster (Auftraggeber,
    # 04.10.2026: „Taschenrechner mit graphischer Ausgabe") liegt es unter paket\tkinter in
    # derselben Ordnung wie das Python selbst (_tkinter.pyd, tcl86t.dll, tk86t.dll, zlib1.dll,
    # tcl\tcl8.6, tcl\tk8.6, Lib\site-packages\tkinter) und wird hier darueberkopiert.
    tk_archiv = eine("tkinter-*-win-amd64.zip")
    if tk_archiv:
        if not (PYTHON / "_tkinter.pyd").exists():
            with zipfile.ZipFile(tk_archiv) as a:
                a.extractall(PYTHON)
                n = len(a.namelist())
            z.append(f"tkinter aus dem Paket dazugelegt ({tk_archiv.name}): {n} Dateien")
        else:
            z.append("tkinter liegt bereits im eigenen Python.")
        probe = lauf([str(python_exe()), "-c", "import tkinter, _tkinter; print(tkinter.TkVersion)"], 60)
        z.append(f"Gegenprobe tkinter: {'Tk ' + probe.stdout.strip() if probe.returncode == 0 else 'FEHLT — ' + (probe.stderr or '').strip().splitlines()[-1][:120]}")
    else:
        z.append("Kein tkinter im Paket (paket\\tkinter-*.zip fehlt) — Programme mit Fenster laufen hier nicht.")

    # --- Schritt 3: pip, falls es fehlt ---------------------------------------------
    fassung = _pip_da()
    if fassung:
        z.append(f"pip ist bereits eingerichtet: {fassung}")
    else:
        getpip, woher = _beschaffen("get-pip.py", GETPIP_URL, "get-pip.py")
        z.append(f"get-pip: {woher}")
        r = lauf([str(python_exe()), str(getpip), "--no-warn-script-location"], 900)
        if r.returncode != 0:
            raise Abbruch(f"pip liess sich nicht einrichten (Code {r.returncode}): "
                          f"{(r.stderr or r.stdout)[-400:]}")
        fassung = _pip_da()
        if not fassung:
            raise Abbruch("get-pip lief durch, aber pip meldet sich trotzdem nicht. "
                          "Haeufigste Ursache: 'import site' ist nicht freigeschaltet.")
        z.append(f"pip eingerichtet: {fassung}")

    # --- Schritt 4: Gegenproben -----------------------------------------------------
    v = lauf([str(python_exe()), "-c", "import sys;print(sys.version)"], 120)
    z.append(f"Gegenprobe: Python {v.stdout.strip()}")
    z.append(f"Alles liegt in {ABLAGE} und wird von aufraeumen restlos entfernt.")
    return "\n".join(z)


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "umgebung_anlegen",
        "Richtet ein eigenes, eingebettetes Python samt pip in der Ablage ein. Installiert "
        "nichts im System: es wird nur entpackt und spaeter wieder geloescht. Muss vor "
        "paket_installieren und esp32_flashen laufen.",
        {"neu": {"type": "boolean",
                 "description": "true, wenn eine vorhandene Einrichtung ueberschrieben werden soll"}},
        [], {}, tun))
