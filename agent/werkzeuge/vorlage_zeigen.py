#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zeigt das Grundgeruest eines ESP32-Programms — Handwerkszeug, keine Loesung.

Anweisung des Auftraggebers vom 10.10.2026: „Leg ein fertiges Template fuer die
Grundeinstellungen eines Python-ESP32-Programms an, damit das LLM weiss, wie sowas geht."
Und unmittelbar danach die Grenze: „ein Template! nicht den fertigen Code, das waere Betrug!"

Genau so ist es gebaut. Die Vorlage nennt:

  * welche Module es auf dem Brett gibt und welche nicht
  * wie ein Anschluss als Ausgang angelegt wird
  * wie PWM geht, und dass duty_u16 bis 65535 reicht, nicht bis 1023
  * dass ein Programm fuer das Brett eine Endlosschleife braucht
  * wie aus einem verlangten Takt eine Wartezeit wird

Sie nennt NICHT, was das Programm tun soll. An diesen Stellen stehen Platzhalter der Form
``<<< ... >>>``, und die Vorlage laesst sich deshalb nicht uebersetzen: Wer sie unveraendert
abschickt, bekommt von schreib_datei einen Syntaxfehler. Das ist Absicht.

Warum es die Vorlage ueberhaupt gibt: Ein kleines Modell kennt MicroPython nur ungefaehr. Am
05.10.2026 schrieb es ``from machine import Pin, time`` (time gibt es dort nicht), am
05.10.2026 ``duty_u16(1023 * x)`` (die LED blieb bei 1,6 Prozent), am 09.10.2026 ``import
tkinter`` in einem Programm fuer das Brett. Das sind keine Denkfehler, sondern Wissensluecken
— und die schliesst man mit einem Nachschlagewerk, nicht mit einer Abweisung.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, PAKET

VORLAGEN = {
    #  Als .txt, nicht als .py: Die Vorlage ist absichtlich kein gueltiges Python
    #  (sie hat Platzhalter). Die Bruecke prueft jede .py beim Uebertragen und wies
    #  sie deshalb ab — zu Recht. Ein Nachschlagewerk ist kein Programm.
    "esp32": "esp32_grundgeruest.txt",
    "pruefbar": "pruefbar_schreiben.txt",
}


def tun(e):
    was = str(e.get("wofuer", "esp32")).strip().lower()
    if was not in VORLAGEN:
        raise Abbruch(f"Fuer '{was}' gibt es keine Vorlage. Da ist: "
                      f"{', '.join(sorted(VORLAGEN))}. Rufe das Werkzeug mit "
                      f'WERKZEUG: vorlage_zeigen {{"wofuer": "esp32"}} auf.')
    d = PAKET / "vorlagen" / VORLAGEN[was]
    if not d.is_file():
        raise Abbruch(f"Die Vorlage {d} liegt nicht im Paket. "
                      f"Was jetzt hilft: ohne sie weiterarbeiten — sie ist eine Hilfe, "
                      f"keine Voraussetzung. Schreibe das Programm mit schreib_datei und "
                      f"pruefe es mit quelltext_pruefen.")
    text = d.read_text(encoding="utf-8", errors="replace")
    return (f"Grundgeruest eines MicroPython-Programms fuer den ESP32.\n"
            f"Die Stellen mit <<< ... >>> musst DU fuellen — dort steht, was der Auftrag "
            f"verlangt. Unveraendert laesst sich das hier nicht uebersetzen.\n"
            f"{'-' * 72}\n{text}\n{'-' * 72}\n"
            f"Schreibe jetzt dein eigenes Programm mit schreib_datei und pruefe es mit "
            f"quelltext_pruefen.")


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "vorlage_zeigen",
        "Zeigt das Grundgeruest eines MicroPython-Programms fuer den ESP32: welche Module es "
        "gibt, wie ein Anschluss angelegt wird, wie PWM geht, wie aus einem Takt eine "
        "Wartezeit wird. Es ist ein Nachschlagewerk, keine Loesung — die Stellen, an denen "
        "steht was zu tun ist, sind leer. Rufe es auf, wenn du unsicher bist, wie MicroPython "
        "etwas nennt.",
        {"wofuer": {"type": "string", "description": "esp32 (Grundgeruest) oder pruefbar (wie ein Programm aussieht, das sich messen laesst)"}},
        [], {"wofuer": "esp32"}, tun))
