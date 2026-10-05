#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wo liegt was — die einzige Stelle, die Pfade kennt.

Alles ist **relativ zum Paket**. Kein Werkzeug darf einen festen Pfad enthalten; sonst
läuft das Paket nur auf dem Rechner, auf dem es gebaut wurde. Der Stick bekommt morgen
einen anderen Laufwerksbuchstaben, und der Kursraum hat einen anderen Benutzernamen.

Zwei Betriebsarten:

  vom Stick      WURZEL ist der Ordner, in dem START.bat liegt
  auf Platte     WURZEL ist die Kopie unter %TEMP%, die sich am Ende selbst löscht

Beides unterscheidet sich hier um genau eine Zeile — und sonst nirgends im Paket.
"""
from __future__ import annotations
import os, pathlib

# Der Ordner, in dem dieses Paket liegt. Von hier aus wird alles abgeleitet.
WURZEL = pathlib.Path(os.environ.get("KURS_AGENT_WURZEL",
                                     pathlib.Path(__file__).resolve().parent.parent))

PAKET    = WURZEL / "paket"        # was mitgeliefert wird: Python, pip, Pakete, Modell
ABLAGE   = WURZEL / "ablage"       # was der Agent anlegt — und was am Ende gelöscht wird
PYTHON   = ABLAGE / "python"       # hierhin wird Python entpackt
WERKSTATT= ABLAGE / "werkstatt"    # hier entsteht das Programm für den ESP32
PROTOKOLL= ABLAGE / "protokoll.txt"

# Die mitgelieferten Dateien, jeweils über ein Muster gesucht statt fest benannt:
# die Fassungsnummer soll sich ändern duerfen, ohne dass hier etwas anzufassen ist.
def eine(muster: str) -> pathlib.Path | None:
    t = sorted(PAKET.glob(muster))
    return t[-1] if t else None


def python_exe() -> pathlib.Path:
    return PYTHON / "python.exe"


PIP_CACHE = ABLAGE / "pip-zwischenlager"   # damit nichts im Benutzerprofil landet


def umgebung() -> dict:
    """Die Umgebung, in der jeder Unterprozess laeuft — abgeschirmt gegen den Rechner.

    Drei Wege fuehren sonst aus dem Ordner heraus, und alle drei sind leicht zu uebersehen:

      1  **Der pip-Zwischenspeicher.** pip legt heruntergeladene Pakete in
         ``%LOCALAPPDATA%\\pip\\Cache`` ab. Das sind schnell einige hundert Megabyte, sie
         liegen ausserhalb der Ablage, und kein Aufraeumen der Welt findet sie dort.

      2  **Das Benutzer-Paketverzeichnis** ``%APPDATA%\\Python\\Python3xx\\site-packages``.
         Python liest es mit, pip schreibt im Zweifel hinein. Damit koennte unser Python
         Pakete des Nutzers sehen — oder, schlimmer, seine ueberschreiben.

      3  **Die Umgebungsvariablen** PYTHONPATH, PYTHONHOME, PIP_*. Wer sie gesetzt hat,
         bekaeme ein Python, das halb aus unserem Ordner und halb von anderswo stammt.
         Fehler daraus sind kaum zu finden, weil sie auf dem Rechner des Erbauers nicht
         auftreten.

    Hier wird alles drei abgestellt. Die Variablen werden nicht geaendert, sondern nur fuer
    die Unterprozesse gesetzt — die Einstellungen des Rechners bleiben, wie sie sind.
    """
    import os as _os
    u = dict(_os.environ)
    for weg in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE",
                "PIP_TARGET", "PIP_PREFIX", "PIP_USER", "PIP_CONFIG_FILE",
                "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_FIND_LINKS"):
        u.pop(weg, None)
    u["PYTHONNOUSERSITE"] = "1"          # kein Benutzer-Paketverzeichnis, weder lesen noch schreiben
    u["PIP_CACHE_DIR"] = str(PIP_CACHE)  # der Zwischenspeicher liegt in der Ablage
    u["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    u["PYTHONDONTWRITEBYTECODE"] = "0"   # .pyc duerfen entstehen — sie liegen in der Ablage
    return u


#  Was vollstaendig vorliegen muss, damit der Kurs laufen kann. Gesucht wird ueber Muster,
#  nicht ueber feste Namen: Fassungsnummern duerfen sich aendern, ohne dass hier etwas
#  anzufassen ist.
BESTANDTEILE = (
    ("Python",    "python_vorlage/python.exe", "das eigene Python, ausgepackt"),
    ("get-pip",   "get-pip.py",                "pip fuer das eigene Python"),
    ("Pakete",    "pakete/*.whl",              "mpremote, esptool und ihre Abhaengigkeiten"),
    ("llama.cpp", "llama/*.dll",               "der Rechenkern fuer das Sprachmodell"),
    ("Firmware",  "firmware/*.bin",            "MicroPython fuer den ESP32"),
    ("Treiber",   "treiber/*.ZIP",             "USB-Seriell, falls Windows den ESP32 nicht erkennt"),
    ("Modell",    "modell/*.gguf",             "das Sprachmodell"),
)


def fehlendes() -> list:
    """Was im Paket fehlt. Leere Liste heisst: der Kurs kann laufen.

    Anlass (03.10.2026): Beim ersten Fuellen auf dem Kursrechner brach hole_paket.py nach
    dem ersten Schritt ab. Dadurch lag Python im Paket -- und genau daran, und nur daran,
    hatte START.bat bis dahin erkannt, ob noch zu fuellen ist. Beim naechsten Start ging
    es deshalb ohne Nachfrage ins Hauptmenue, mit einem Paket, in dem drei Viertel fehlten.
    Ein halb gefuelltes Paket ist der gefaehrlichste Zustand: Es sieht fertig aus.
    """
    return [(n, m, w) for n, m, w in BESTANDTEILE if not sorted(PAKET.glob(m))]


def bericht() -> str:
    z = [f"Wurzel     {WURZEL}", f"Paket      {PAKET}", f"Ablage     {ABLAGE}"]
    for name, m in (("Python-ZIP", "python-*-embed-*.zip"), ("get-pip", "get-pip.py"),
                    ("Pakete", "pakete/*.whl"), ("Modell", "modell/*.gguf")):
        d = eine(m)
        z.append(f"  {name:12s} {'gefunden: ' + d.name if d else 'FEHLT (' + m + ')'}")
    return "\n".join(z)


if __name__ == "__main__":
    import sys
    if "--fehlt" in sys.argv:
        f = fehlendes()
        for name, muster, wofuer in f:
            print(f"      FEHLT  {name:10s} {wofuer}")
        if not f:
            print("      Das Paket ist vollstaendig.")
        #  Rueckgabe 1 heisst "es fehlt etwas" -- START.bat fragt danach.
        raise SystemExit(1 if f else 0)
    print(bericht())
