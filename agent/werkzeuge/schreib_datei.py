#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schreibt eine Datei in die Werkstatt — und nur dorthin.

Dies ist das Werkzeug, mit dem das Modell seinen Quelltext ablegt. Es ist damit das
gefaehrlichste im Bausatz: ein Modell, das einen Pfad erfindet, wuerde sonst irgendwo
schreiben. Der Pfad wird deshalb aufgeloest und gegen die Ablage geprueft, bevor eine
Datei entsteht — siehe in_der_ablage() im Muster.

Zurueck kommen Zeilenzahl und die ersten Zeilen. Das Modell soll sehen, was wirklich in
der Datei steht, nicht was es zu schreiben glaubte.
"""
import re
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

from _muster import werkzeug, Abbruch, in_der_ablage, WERKSTATT, ABLAGE


def tun(e):
    name = str(e["name"]).strip()
    inhalt = e["inhalt"]
    if not name:
        raise Abbruch("Es fehlt ein Dateiname.")
    # Ein absoluter Pfad wird nicht heimlich relativ gemacht: sonst meldet das Werkzeug
    # "C:\\irgendwo geschrieben", obwohl die Datei ganz woanders liegt. Lieber absagen
    # und sagen, was stattdessen zu tun ist.
    if name[0] in "/\\" or re.match(r"^[A-Za-z]:", name):
        raise Abbruch(f"'{name}' ist ein absoluter Pfad. Hier wird nur in die Werkstatt "
                      f"geschrieben; gib einen blossen Dateinamen an, zum Beispiel blink.py.")
    # Eine Python-Datei, die sich nicht uebersetzen laesst, ist keine Lieferung. Sie hier
    # abzuweisen hat zwei Gruende: der Fehler faellt sofort auf statt erst im Pruefschritt,
    # und eine bereits vorhandene, laufende Fassung bleibt erhalten statt ueberschrieben zu
    # werden. Modelle wiederholen ihre Tippfehler sonst hartnaeckig.
    if name.endswith(".py"):
        try:
            compile(inhalt, name, "exec")
        except SyntaxError as e:
            zeilen = inhalt.splitlines()
            stelle = (f"\n  Zeile {e.lineno}: {zeilen[e.lineno-1]}"
                      if e.lineno and 0 < e.lineno <= len(zeilen) else "")
            raise Abbruch(
                f"{name} wurde NICHT geschrieben: der Quelltext ist kein gueltiges Python.\n"
                f"  Zeile {e.lineno}: {e.msg}{stelle}\n"
                f"Schreibe den Text neu und berichtige genau diese Stelle. Haeufigste "
                f"Ursache ist eine ueberzaehlige Klammer am Zeilenende.")

    ziel = in_der_ablage(WERKSTATT.relative_to(ABLAGE) / name)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt, encoding="utf-8")

    zeilen = inhalt.splitlines()
    kopf = "\n".join(f"  {i+1:3d} | {z}" for i, z in enumerate(zeilen[:12]))
    rest = f"\n  ... und {len(zeilen)-12} weitere Zeilen" if len(zeilen) > 12 else ""
    return (f"{ziel} geschrieben: {len(zeilen)} Zeilen, {ziel.stat().st_size} Byte.\n"
            f"So steht es jetzt in der Datei:\n{kopf}{rest}")


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "schreib_datei",
        "Schreibt eine Textdatei in die Werkstatt, zum Beispiel den Quelltext fuer den ESP32. "
        "Vorhandene Dateien werden ersetzt. Ausserhalb der Ablage kann nicht geschrieben werden.",
        {"name":   {"type": "string", "description": "Dateiname, zum Beispiel blink.py"},
         "inhalt": {"type": "string", "description": "der vollstaendige Inhalt der Datei"}},
        ["name", "inhalt"],
        {"name": "probe.txt", "inhalt": "Dies ist eine Probe.\nZweite Zeile.\n"}, tun))
