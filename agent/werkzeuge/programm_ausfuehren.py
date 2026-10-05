#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fuehrt ein beliebiges Python-Programm aus der Werkstatt mit dem Paket-Python aus.

programm_testen ist fuer den ESP32 gebaut: Es ersetzt ``machine`` und misst Pins. Fuer alles
andere — einen Taschenrechner, ein Programm mit Fenster, ein Skript, das rechnet und etwas
ausgibt — gibt es dieses Werkzeug (Anweisung des Auftraggebers, 04.10.2026: „programmier mir
mal einen einfachen Taschenrechner mit graphischer Ausgabe").

Zwei Betriebsarten:

  * **laufen lassen** (Vorgabe): Das Programm laeuft bis zum Ende oder bis zur Zeitgrenze;
    Ausgabe, Fehlerausgabe und Rueckgabewert werden berichtet. Mit ``eingabe`` laesst sich
    Text auf die Standardeingabe geben, so dass auch ein Programm mit input() pruefbar ist.
  * **fenster**: Fuer Programme mit grafischer Oberflaeche (tkinter). Das Programm wird
    gestartet und einige Sekunden beobachtet: Lebt es noch? Hat es ein Fenster geoeffnet
    (Windows: Fenstertitel ueber die Prozessnummer)? Danach wird es beendet — oder mit
    ``offen_lassen`` fuer den Menschen offen gelassen, der es dann selbst bedient.

Ein Programm, das sofort mit einer Fehlermeldung endet, hat nicht bestanden; das Urteil
steht als LAUF BESTANDEN / LAUF NICHT BESTANDEN im Ergebnis, damit der Agent es wie bei
programm_testen lesen kann.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, WERKSTATT, python_exe
from pfade import umgebung
import subprocess, time, os, re


def _fenster_von(pid: int) -> list:
    """Titel der sichtbaren Fenster dieses Prozesses (nur Windows; sonst leer)."""
    if os.name != "nt":
        return []
    try:
        import ctypes, ctypes.wintypes as wt
        u = ctypes.windll.user32
        titel = []
        @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        def schau(h, _):
            if u.IsWindowVisible(h):
                p = wt.DWORD()
                u.GetWindowThreadProcessId(h, ctypes.byref(p))
                if p.value == pid:
                    n = u.GetWindowTextLengthW(h)
                    puffer = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(h, puffer, n + 1)
                    titel.append(puffer.value or "(ohne Titel)")
            return True
        u.EnumWindows(schau, 0)
        return titel
    except Exception:
        return []


def tun(e):
    name = str(e["datei"]).strip()
    if "/" in name or "\\" in name or not name.endswith(".py"):
        raise Abbruch("datei muss ein .py-Name aus der Werkstatt sein, ohne Pfad.")
    quelle = WERKSTATT / name
    if not quelle.is_file():
        da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*"))) or "(nichts)"
        raise Abbruch(f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}. Erst schreib_datei.")
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")
    sekunden = float(e.get("sekunden", 10))
    if not 1 <= sekunden <= 120:
        raise Abbruch("sekunden muss zwischen 1 und 120 liegen.")
    fenster = bool(e.get("fenster", False))
    offen_lassen = bool(e.get("offen_lassen", False))
    eingabe = e.get("eingabe")
    befehl = [str(python_exe()), "-X", "utf8", str(quelle)]
    u = umgebung()
    #  tkinter aus dem Paket (paket\tkinter -> ablage\python), falls umgebung_anlegen es gelegt hat:
    #  TCL_LIBRARY/TK_LIBRARY zeigen dann auf den mitgelieferten tcl-Ordner.
    tcl = python_exe().parent / "tcl"
    if tcl.is_dir():
        for d in tcl.iterdir():
            if d.is_dir() and d.name.lower().startswith("tcl8"):
                u["TCL_LIBRARY"] = str(d)
            if d.is_dir() and d.name.lower().startswith("tk8"):
                u["TK_LIBRARY"] = str(d)

    if not fenster:
        t0 = time.time()
        try:
            r = subprocess.run(befehl, cwd=str(WERKSTATT), env=u, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=sekunden,
                               input=(str(eingabe) if eingabe is not None else None))
            dauer = time.time() - t0
            aus, fehl, rc = (r.stdout or ""), (r.stderr or ""), r.returncode
            lief_ab = False
        except subprocess.TimeoutExpired as te:
            dauer = time.time() - t0
            aus = (te.stdout.decode("utf-8", "replace") if isinstance(te.stdout, bytes) else (te.stdout or ""))
            fehl = (te.stderr.decode("utf-8", "replace") if isinstance(te.stderr, bytes) else (te.stderr or ""))
            rc, lief_ab = None, True
        zeilen = [f"{name} lief {dauer:.1f} s" + (" und wurde an der Zeitgrenze beendet (es endet nicht von selbst)." if lief_ab else f", Rueckgabewert {rc}.")]
        if aus.strip():
            zeilen += ["Ausgabe:", *("    " + z for z in aus.rstrip().splitlines()[-40:])]
        else:
            zeilen.append("Ausgabe: (keine)")
        if fehl.strip():
            zeilen += ["Fehlerausgabe:", *("    " + z for z in fehl.rstrip().splitlines()[-25:])]
        bestanden = (rc == 0) or (lief_ab and "Traceback" not in fehl)
        zeilen.append("")
        zeilen.append("LAUF BESTANDEN" if bestanden else "LAUF NICHT BESTANDEN")
        if not bestanden:
            zeilen.append("  Das Programm endete mit einem Fehler. Lies die Fehlerausgabe (die letzte Zeile nennt "
                          "die Ursache), berichtige den Quelltext mit schreib_datei und fuehre es erneut aus.")
        return "\n".join(zeilen)

    #  Fenster: starten, beobachten, (beenden)
    kennung = {}
    if os.name == "nt":
        kennung["creationflags"] = 0x00000008 | 0x00000200       # DETACHED_PROCESS | NEW_PROCESS_GROUP
    p = subprocess.Popen(befehl, cwd=str(WERKSTATT), env=u, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace", **kennung)
    t0 = time.time(); titel = []
    while time.time() - t0 < sekunden:
        time.sleep(0.5)
        if p.poll() is not None:
            break
        titel = _fenster_von(p.pid) or titel
        if titel and time.time() - t0 >= min(3.0, sekunden):
            break
    lebt = p.poll() is None
    zeilen = [f"{name} als Fensterprogramm gestartet (Prozess {p.pid})."]
    if lebt:
        zeilen.append(f"  Nach {time.time() - t0:.1f} s laeuft es noch"
                      + (f"; Fenster: {', '.join(repr(t) for t in titel)}" if titel
                         else "; ein Fenster wurde " + ("nicht erkannt (auf diesem System nicht ermittelbar)" if os.name != "nt" else "NICHT gefunden")) + ".")
        if offen_lassen:
            zeilen.append("  Es bleibt fuer den Menschen offen; er schliesst es selbst.")
            aus, fehl = "", ""
        else:
            p.terminate()
            try:
                aus, fehl = p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill(); aus, fehl = p.communicate()
            zeilen.append("  Danach beendet (zum Weiterbenutzen: offen_lassen true).")
    else:
        aus, fehl = p.communicate()
        zeilen.append(f"  Es hat sich nach {time.time() - t0:.1f} s von selbst beendet, Rueckgabewert {p.returncode}.")
    if (aus or "").strip():
        zeilen += ["Ausgabe:", *("    " + z for z in aus.rstrip().splitlines()[-20:])]
    if (fehl or "").strip():
        zeilen += ["Fehlerausgabe:", *("    " + z for z in fehl.rstrip().splitlines()[-25:])]
    bestanden = lebt and (os.name != "nt" or bool(titel))
    zeilen.append("")
    zeilen.append("LAUF BESTANDEN" if bestanden else "LAUF NICHT BESTANDEN")
    if not bestanden:
        zeilen.append("  Ein Fensterprogramm muss laufen und ein Fenster zeigen. Lies die Fehlerausgabe, "
                      "berichtige mit schreib_datei und fuehre es erneut aus. Fehlt tkinter, sagt die "
                      "Fehlerausgabe 'No module named _tkinter' — dann liegt es nicht im Paket.")
    return "\n".join(zeilen)


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "programm_ausfuehren",
        "Fuehrt ein beliebiges Python-Programm aus der Werkstatt mit dem Paket-Python aus — fuer alles, "
        "was kein ESP32-Programm ist (Rechner, Skripte, Programme mit Fenster). Berichtet Ausgabe, Fehler "
        "und Rueckgabewert; Urteil LAUF BESTANDEN / NICHT BESTANDEN. Mit fenster true wird ein Programm mit "
        "grafischer Oberflaeche (tkinter) gestartet und beobachtet, ob es laeuft und ein Fenster zeigt.",
        {"datei":    {"type": "string",  "description": "Dateiname in der Werkstatt, zum Beispiel rechner.py"},
         "sekunden": {"type": "number",  "description": "Zeitgrenze bzw. Beobachtungsdauer, Vorgabe 10"},
         "fenster":  {"type": "boolean", "description": "true fuer ein Programm mit grafischer Oberflaeche"},
         "offen_lassen": {"type": "boolean", "description": "Fensterprogramm fuer den Menschen offen lassen"},
         "eingabe":  {"type": "string",  "description": "Text fuer die Standardeingabe (input()), optional"}},
        ["datei"], {"datei": "probe.py", "sekunden": 5}, tun))
