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
        raise Abbruch('Es fehlt ein Dateiname. Der Aufruf braucht beide Felder: '
                      'WERKZEUG: schreib_datei {"name": "<datei>.py", '
                      '"inhalt": "<der vollstaendige Quelltext>"}')
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
    #  Die Vorlage bleibt eine Vorlage (Anweisung vom 10.10.2026): „das Template bleibt ein
    #  Template, um zu verhindern, dass die KI nicht arbeiten muss". Wer die Platzhalter
    #  stehen laesst, hat nicht gearbeitet, sondern abgeschrieben. Das faellt hier auf und
    #  nicht erst in der Messung.
    if "<<<" in inhalt or ">>>" in inhalt:
        stellen = [i + 1 for i, z in enumerate(inhalt.splitlines()) if "<<<" in z or ">>>" in z]
        raise Abbruch(
            f"{name} wurde NICHT geschrieben: Darin stehen noch Platzhalter der Vorlage "
            f"(Zeile {', '.join(str(s) for s in stellen[:6])}).\n"
            f"Die Vorlage zeigt, WIE ein ESP32-Programm aufgebaut ist — was es tun soll, "
            f"steht im Auftrag und muss von dir kommen. Ersetze jedes <<< ... >>> durch "
            f"deinen eigenen Code und schreibe die Datei neu.")

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

    #  Kein stilles Ueberschreiben (09.10.2026). Am 08.10. ersetzte das Modell einen fertigen
    #  Taschenrechner mit 52 Zeilen durch ein Blinkprogramm mit 7 Zeilen und merkte es nicht;
    #  an einem anderen Tag schrieb es dreimal denselben Text und hielt den Auftrag fuer
    #  erledigt. Beides faellt auf, sobald die vorige Fassung aufgehoben und der Unterschied
    #  gemeldet wird. Gesichert wird nur, was sich wirklich aendert.
    vermerk = ""
    if ziel.is_file():
        vorher = ziel.read_text(encoding="utf-8", errors="replace")
        if vorher == inhalt:
            vermerk = ("\nACHTUNG: Diese Datei ist Byte fuer Byte dieselbe wie vorher. Der "
                       "Schreibvorgang hat nichts geaendert. Denselben Text noch einmal zu "
                       "schreiben hilft nicht — lies den Befund der letzten Messung und "
                       "aendere genau die Stelle, die er nennt.")
        else:
            import time as _t
            ordner = ABLAGE / "fassungen" / name
            ordner.mkdir(parents=True, exist_ok=True)
            (ordner / _t.strftime("%Y-%m-%d_%H%M%S")).write_text(vorher, encoding="utf-8")
            a, b = len(vorher.splitlines()), len(inhalt.splitlines())
            vermerk = (f"\nEs gab diese Datei schon ({a} Zeilen); die vorige Fassung liegt in "
                       f"ablage/fassungen/{name}/. Jetzt sind es {b} Zeilen.")
            if a >= 20 and b < a / 3:
                vermerk += ("\nACHTUNG: Die Datei ist auf weniger als ein Drittel geschrumpft. "
                            "Gehoert der neue Inhalt wirklich zu dem Auftrag, den du gerade "
                            "bearbeitest? Was sich genau geaendert hat, sagt "
                            "WERKZEUG: programm_vergleichen {\"datei\": \"" + name + "\"}")

    ziel.write_text(inhalt, encoding="utf-8")

    zeilen = inhalt.splitlines()
    kopf = "\n".join(f"  {i+1:3d} | {z}" for i, z in enumerate(zeilen[:12]))
    rest = f"\n  ... und {len(zeilen)-12} weitere Zeilen" if len(zeilen) > 12 else ""
    return (f"{ziel} geschrieben: {len(zeilen)} Zeilen, {ziel.stat().st_size} Byte.{vermerk}\n"
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
