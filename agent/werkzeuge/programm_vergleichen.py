#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vergleicht die jetzige Fassung einer Datei mit der vorigen — hat sich ueberhaupt etwas geaendert?

Warum es dieses Werkzeug gibt
-----------------------------
Am 08.10.2026 schrieb das 7B-Modell dreimal hintereinander denselben Inhalt in dieselbe Datei und
hielt den Auftrag fuer erledigt. Am selben Tag ueberschrieb es einen fertigen Taschenrechner
(52 Zeilen) mit einem Blinkprogramm (7 Zeilen) und merkte es nicht. Beides faellt sofort auf,
wenn jemand nachsieht — nur sah niemand nach, weil es dafuer kein Werkzeug gab.

Dieses Werkzeug sieht nach. Es liest die vorige Fassung aus ``ablage/fassungen/<name>/`` und
meldet eines von dreien:

  * **Byte fuer Byte dieselbe Datei** — dann hat der letzte Schreibvorgang nichts bewirkt, und
    ein weiterer Versuch mit demselben Text ist sinnlos.
  * **geaendert** — mit Zeilen dazu, Zeilen weg und den ersten Unterschieden im Wortlaut.
  * **ganz anderes Programm** — wenn weniger als ein Fuenftel der Zeilen gleich geblieben ist.
    Das ist kein Mangel an sich; es ist eine Warnung, wenn der Auftrag nur eine Aenderung
    verlangte.

Dieses Werkzeug urteilt nicht ueber den Inhalt. Es sagt, was sich geaendert hat, und laesst das
Urteil den Messwerkzeugen.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, WERKSTATT, ABLAGE
import difflib

FASSUNGEN = ABLAGE / "fassungen"


def vorige(name: str):
    """Die zuletzt gesicherte Fassung dieser Datei, oder None."""
    ordner = FASSUNGEN / name
    if not ordner.is_dir():
        return None
    alle = sorted(ordner.glob("*"))
    return alle[-1] if alle else None


def vergleich(alt_text: str, neu_text: str, alt_name: str, neu_name: str) -> str:
    """Der Bericht ueber den Unterschied — nachrechenbar, mit Zeilennummern."""
    a = alt_text.splitlines()
    b = neu_text.splitlines()
    if alt_text == neu_text:
        return ("BYTE FUER BYTE DIESELBE DATEI.\n"
                f"  Die neue Fassung ({len(b)} Zeilen) ist mit der vorigen identisch. Der letzte "
                f"Schreibvorgang hat nichts geaendert.\n"
                f"  Denselben Text noch einmal zu schreiben hilft nicht. Lies den Befund der "
                f"letzten Messung und aendere genau die Stelle, die er nennt.")

    unterschied = list(difflib.unified_diff(a, b, alt_name, neu_name, lineterm="", n=1))
    dazu = sum(1 for z in unterschied if z.startswith("+") and not z.startswith("+++"))
    weg = sum(1 for z in unterschied if z.startswith("-") and not z.startswith("---"))
    gleich = difflib.SequenceMatcher(None, a, b).ratio()

    z = [f"GEAENDERT: {dazu} Zeilen dazu, {weg} Zeilen weg "
         f"(vorher {len(a)} Zeilen, jetzt {len(b)} Zeilen).",
         f"  Uebereinstimmung mit der vorigen Fassung: {gleich*100:.0f} %."]
    if gleich < 0.20:
        z.append("  ACHTUNG: Weniger als ein Fuenftel ist gleich geblieben. Das ist kein "
                 "geaendertes Programm mehr, sondern ein anderes. Wenn der Auftrag nur eine "
                 "Aenderung verlangte, ist hier etwas verlorengegangen — sieh nach, ob die "
                 "Datei zum Auftrag gehoert, den du gerade bearbeitest.")
    z.append("")
    z.append("Die Unterschiede im Wortlaut:")
    gezeigt = [u for u in unterschied if not u.startswith(("+++", "---"))][:24]
    z.extend("  " + u for u in gezeigt)
    übrig = len([u for u in unterschied if not u.startswith(("+++", "---"))]) - len(gezeigt)
    if übrig > 0:
        z.append(f"  … und {übrig} weitere Unterschiedszeilen")
    return "\n".join(z)


def tun(e):
    name = str(e["datei"]).strip()
    if "/" in name or "\\" in name:
        raise Abbruch("datei muss ein Name aus der Werkstatt sein, ohne Pfad.")
    jetzt = WERKSTATT / name
    if not jetzt.is_file():
        da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*"))) or "(nichts)"
        raise Abbruch(f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}.\n"
                      f"Lege sie erst an: WERKZEUG: schreib_datei "
                      f'{{"name": "{name}", "inhalt": "<der vollstaendige Quelltext>"}}')
    neu_text = jetzt.read_text(encoding="utf-8", errors="replace")

    alt = vorige(name)
    if alt is None:
        return (f"{name} ist neu — es gibt noch keine vorige Fassung zum Vergleichen.\n"
                f"  {len(neu_text.splitlines())} Zeilen, {jetzt.stat().st_size} Byte.\n"
                f"  Ab dem naechsten Schreiben zeigt dieses Werkzeug, was sich geaendert hat.")
    alt_text = alt.read_text(encoding="utf-8", errors="replace")
    return (f"{name}: jetzige Fassung gegen die vorige ({alt.name}).\n\n"
            + vergleich(alt_text, neu_text, f"vorher ({alt.name})", "jetzt"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gegenprobe":
        print("Gegenprobe von programm_vergleichen — vier Faelle:\n")
        faelle = [
            ("gleicher Text zweimal", "a = 1\nb = 2\n", "a = 1\nb = 2\n", "BYTE FUER BYTE"),
            ("eine Zeile geaendert", "a = 1\nb = 2\n", "a = 1\nb = 3\n", "GEAENDERT"),
            ("Taschenrechner durch Blinkprogramm ersetzt",
             "\n".join(f"zeile_{i} = {i}" for i in range(52)),
             "import machine\nimport time\nled = machine.Pin(2)\nwhile True:\n    pass\n",
             "ACHTUNG"),
            ("leere Datei gegen Inhalt", "", "a = 1\n", "GEAENDERT"),
        ]
        alle = True
        for titel, alt, neu, muss in faelle:
            erg = vergleich(alt, neu, "vorher", "jetzt")
            gut = muss in erg
            alle &= gut
            print(f"  {titel}")
            print(f"    erwartet '{muss}' -> {'richtig' if gut else 'FALSCH'}")
            print(f"    {erg.splitlines()[0][:100]}")
            print()
        print("GEGENPROBE BESTANDEN" if alle else "GEGENPROBE NICHT BESTANDEN")
        raise SystemExit(0 if alle else 1)
    raise SystemExit(werkzeug(
        "programm_vergleichen",
        "Vergleicht die jetzige Fassung einer Datei in der Werkstatt mit der vorigen und sagt, "
        "was sich geaendert hat: Byte fuer Byte dieselbe Datei, geaendert mit Zeilen dazu und "
        "weg, oder ein ganz anderes Programm. Zeigt die Unterschiede im Wortlaut. Rufe es nach "
        "jedem schreib_datei auf, um zu sehen, ob deine Aenderung angekommen ist.",
        {"datei": {"type": "string", "description": "Dateiname in der Werkstatt, z. B. blink.py"}},
        ["datei"], {"datei": "blink.py"}, tun))
