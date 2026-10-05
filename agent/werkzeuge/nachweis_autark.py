#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sieht nach, ob ausserhalb des eigenen Ordners etwas angefasst wurde.

Die Zusage lautet: dieses Paket laeuft autark und laesst den Rechner, wie er war. Eine
Zusage ist aber nur so viel wert wie ihre Pruefung — darum dieses Werkzeug. Es nimmt die
Stellen auf, an denen ein Python-Programm ueblicherweise Spuren hinterlaesst, und
vergleicht sie vor und nach der Arbeit.

    nachweis_autark.py '{"wann": "vorher"}'    Zustand aufnehmen
    ... der Agent arbeitet ...
    nachweis_autark.py '{"wann": "nachher"}'   vergleichen

Geprueft werden:

  das Python des Rechners      sein Ordner und seine site-packages
  das Benutzer-Paketverzeichnis %APPDATA%\\Python   (dorthin schreibt pip mit --user)
  der pip-Zwischenspeicher      %LOCALAPPDATA%\\pip  (wird sonst still mehrere hundert MB gross)
  PATH und die PYTHON-Variablen des Benutzers

Was es **nicht** prueft, und das gehoert dazugesagt: die Windows-Registrierung und
Dienste. Beide werden von diesem Paket auch nicht angefasst — nichts darin ruft ein
Installationsprogramm auf, und alles, was laeuft, laeuft aus einem Ordner. Aber geprueft
ist das hier nicht, sondern nur begruendet.
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

from _muster import werkzeug, Abbruch, in_der_ablage, ABLAGE, WURZEL
import os, json, pathlib, sys

AUFNAHME = ABLAGE / "nachweis_vorher.json"


def _orte() -> dict:
    """Die Stellen, an denen ein Python-Programm ueblicherweise Spuren hinterlaesst.

    Ausdruecklich **nicht** ueber ``sys.executable``: das ist beim Lauf unser eigenes
    Python in der Ablage. Wer danach fragt, beobachtet den Ordner, der ohnehin geloescht
    wird — und bekommt jedes Mal ein beruhigendes Ergebnis, das nichts bedeutet. Beobachtet
    werden deshalb feste Orte des Rechners, die mit diesem Paket nichts zu tun haben.
    """
    o = {}
    if os.name == "nt":
        um = os.path.expandvars
        o["Benutzer-Pakete"] = um(r"%APPDATA%\Python")
        o["pip-Zwischenspeicher"] = um(r"%LOCALAPPDATA%\pip")
        o["Python des Benutzers"] = um(r"%LOCALAPPDATA%\Programs\Python")
        for basis in (um("%ProgramFiles%"), "C:" + os.sep):
            for name in ("Python312", "Python313", "Python311"):
                d = os.path.join(basis, name)
                if os.path.isdir(d):
                    o[f"Python in {name}"] = d
        o["Thonny"] = um(r"%LOCALAPPDATA%\Programs\Thonny")
    else:
        o["Benutzer-Pakete"] = os.path.expanduser("~/.local/lib")
        o["pip-Zwischenspeicher"] = os.path.expanduser("~/.cache/pip")
        o["Python des Systems"] = "/usr/lib/python3"
        o["site-packages des Systems"] = "/usr/local/lib"
    # Nur Orte, die es wirklich gibt, und keiner darf in unserem eigenen Baum liegen.
    from pfade import WURZEL
    wurzel = str(WURZEL).lower()
    return {n: p for n, p in o.items() if p and not str(p).lower().startswith(wurzel)}


def _stand(pfad: str) -> dict:
    p = pathlib.Path(pfad)
    if not p.exists():
        return {"da": False}
    n, b, jung = 0, 0, 0.0
    try:
        for d in p.rglob("*"):
            if d.is_file():
                n += 1
                try:
                    s = d.stat(); b += s.st_size; jung = max(jung, s.st_mtime)
                except OSError:
                    pass
    except OSError as e:
        return {"da": True, "fehler": str(e)}
    return {"da": True, "dateien": n, "byte": b, "juengste": jung}


def _aufnehmen() -> dict:
    return {"orte": {name: _stand(pfad) for name, pfad in _orte().items()},
            "pfade": _orte(),
            "PATH": os.environ.get("PATH", ""),
            "python_variablen": {k: v for k, v in os.environ.items() if k.startswith("PYTHON")}}


def tun(e):
    wann = str(e.get("wann", "vorher")).lower()

    if wann == "vorher":
        in_der_ablage("nachweis_vorher.json")
        ABLAGE.mkdir(parents=True, exist_ok=True)
        a = _aufnehmen()
        AUFNAHME.write_text(json.dumps(a, indent=1), encoding="utf-8")
        z = [f"Zustand aufgenommen. Beobachtet werden {len(a['orte'])} Stellen ausserhalb von {WURZEL}:"]
        for name, pfad in a["pfade"].items():
            s = a["orte"][name]
            inhalt = ("nicht vorhanden" if not s["da"]
                      else f"{s.get('dateien', 0)} Dateien, {s.get('byte', 0)/1e6:.1f} MB")
            z.append(f"  {name:24s} {pfad}")
            z.append(f"  {'':24s} {inhalt}")
        return "\n".join(z)

    if wann != "nachher":
        raise Abbruch("wann muss 'vorher' oder 'nachher' sein.")
    if not AUFNAHME.is_file():
        raise Abbruch(f"Es gibt keine Aufnahme ({AUFNAHME}). Vor der Arbeit einmal mit "
                      f'"wann": "vorher" aufrufen — ohne Vorher-Bild ist ein Vergleich nicht moeglich.')

    alt = json.loads(AUFNAHME.read_text(encoding="utf-8"))
    neu = _aufnehmen()
    z, abweichung = [], 0

    for name, pfad in alt["pfade"].items():
        a, b = alt["orte"][name], neu["orte"].get(name, {"da": False})
        if a == b:
            z.append(f"  unveraendert   {name:24s} {pfad}")
            continue
        abweichung += 1
        if not a["da"] and b["da"]:
            z.append(f"  NEU ENTSTANDEN {name:24s} {pfad}  "
                     f"({b.get('dateien', 0)} Dateien, {b.get('byte', 0)/1e6:.1f} MB)")
        else:
            dn = b.get("dateien", 0) - a.get("dateien", 0)
            db = b.get("byte", 0) - a.get("byte", 0)
            z.append(f"  VERAENDERT     {name:24s} {pfad}  "
                     f"({dn:+d} Dateien, {db/1e6:+.1f} MB)")

    if alt["PATH"] != neu["PATH"]:
        abweichung += 1
        z.append("  VERAENDERT     PATH")
    if alt["python_variablen"] != neu["python_variablen"]:
        abweichung += 1
        z.append(f"  VERAENDERT     PYTHON-Variablen: {neu['python_variablen']}")

    kopf = ("Nichts ausserhalb des Paketordners hat sich veraendert."
            if abweichung == 0 else
            f"ACHTUNG: {abweichung} Stelle(n) ausserhalb des Paketordners haben sich veraendert.")
    schluss = ("\nNicht geprueft: Windows-Registrierung und Dienste. Sie werden nicht angefasst, "
               "weil nichts in diesem Paket ein Installationsprogramm aufruft — das ist begruendet, "
               "nicht gemessen.")
    return f"{kopf}\n" + "\n".join(z) + schluss


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "nachweis_autark",
        "Nimmt den Zustand der Stellen ausserhalb des Paketordners auf ('vorher') und vergleicht "
        "ihn spaeter ('nachher'). Damit laesst sich belegen statt behaupten, dass der Rechner "
        "unveraendert bleibt. Vor der Arbeit und vor dem Aufraeumen aufrufen.",
        {"wann": {"type": "string", "description": "'vorher' oder 'nachher'"}},
        [], {"wann": "vorher"}, tun))
