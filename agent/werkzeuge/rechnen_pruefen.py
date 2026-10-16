#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Der Taschenrechner fuer den Schueler: haelt ein erzeugtes Rechenprogramm gegen Pythons Arithmetik.

Warum es dieses Werkzeug gibt
-----------------------------
Der Auftraggeber am 09.10.2026: „Ein dummer Schueler — hier kleines LLM — dem gibt man einen
Taschenrechner, um seine Ergebnisse zu pruefen." Genau das ist dieses Werkzeug. Es fragt das
erzeugte Programm nicht, ob es richtig rechnet; es stellt ihm Aufgaben, deren Antwort feststeht,
und vergleicht.

Der Unterschied zu ``fenster_bedienen``: Dort stehen vier Proben mit **eingetippter** Erwartung
im Werkzeug. Hier werden die Aufgaben erzeugt und die richtige Antwort von **Python selbst**
gerechnet — ich tippe sie nicht ein, also kann ich mich nicht vertippen. Das ist der
unabhaengige Weg (Grundsatz 39): Die Behauptung „dieser Rechner rechnet" wird gegen eine Quelle
geprueft, die nichts mit dem Programm zu tun hat.

Geprueft werden vier Dinge, die alle vier Taschenrechner vom 08.10.2026 zu Fall gebracht haetten:

  * jede der vier Grundrechenarten einzeln, mehrfach mit verschiedenen Zahlen
  * mehrstellige Zahlen (ein Rechner verarbeitete nur eine Ziffer)
  * die Loeschtaste (danach muss die Anzeige leer sein und die naechste Aufgabe stimmen)
  * Teilen durch null — es darf abstuerzen oder eine Meldung zeigen, aber nicht still falsch rechnen

Das nachgebaute tkinter kommt aus ``fenster_bedienen``; es steht nur an einer Stelle und wird
hier benutzt, nicht abgeschrieben.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, WERKSTATT
import fenster_bedienen as fb


#  Die Aufgaben. Die richtige Antwort rechnet Python, sie steht nirgends als Zahl.
def aufgaben() -> list:
    paare = [(12, 7), (9, 4), (6, 7), (8, 2), (45, 23), (100, 25), (3, 9), (81, 9),
             (7, 7), (56, 8)]
    liste = []
    for i, (a, b) in enumerate(paare):
        zeichen = "+-*/"[i % 4]
        liste.append((f"{a}{zeichen}{b}=", eval(f"{a}{zeichen}{b}")))   # noqa: S307 — eigene Zahlen
    #  Dazu jede Rechenart noch einmal mit anderen Zahlen, damit nicht eine davon
    #  zufaellig stimmt: zwanzig Aufgaben insgesamt.
    for a, b in [(15, 6), (20, 13), (4, 12), (36, 6), (2, 99), (77, 11), (5, 5), (144, 12),
                 (31, 19), (60, 4)]:
        zeichen = "+-*/"[(a + b) % 4]
        liste.append((f"{a}{zeichen}{b}=", eval(f"{a}{zeichen}{b}")))   # noqa: S307
    return liste


def _laden(name: str):
    """Das Programm mit dem nachgebauten tkinter laden; gibt (Anzeigefeld, Tasten) zurueck."""
    pfad = WERKSTATT / name
    if not pfad.is_file():
        da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*"))) or "(nichts)"
        raise Abbruch(f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}.\n"
                      f"Lege sie erst an: WERKZEUG: schreib_datei "
                      f'{{"name": "{name}", "inhalt": "<der vollstaendige Quelltext>"}}')
    tk = fb._nachbau()
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = tk.ttk
    sys.modules["tkinter.messagebox"] = tk.messagebox
    raum = {"__name__": "__main__", "__file__": str(pfad)}
    try:
        exec(compile(pfad.read_text(encoding="utf-8", errors="replace"), str(pfad), "exec"), raum)
    except Exception as ex:
        raise Abbruch(f"{name} bricht schon beim Aufbau ab: {type(ex).__name__}: {ex}\n"
                      f"Berichtige es mit WERKZEUG: schreib_datei und pruefe erneut.")
    f = tk._fenster
    tasten = {k.text.strip(): k for k in f.knoepfe}
    anzeige = next((w for w in raum.values()
                    if isinstance(w, fb.Feld) and not isinstance(w, (fb.Knopf, fb.Fenster))), None)
    if anzeige is None:
        raise Abbruch(f"In {name} ist kein Anzeigefeld zu finden. Ein Taschenrechner braucht ein "
                      f"Feld, in dem die Zahl steht. Schreibe das Programm so neu, dass es "
                      f"ein tkinter.Entry oder tkinter.Label als Anzeige anlegt, zum Beispiel "
                      f"anzeige = tk.Entry(fenster) — und rufe dieses Werkzeug danach erneut auf.")
    return anzeige, tasten, f


def _druecken(anzeige, tasten, folge: str):
    """Tasten der Reihe nach druecken; gibt (Anzeige, Absturz) zurueck."""
    if "C" in tasten and tasten["C"].befehl:
        try:
            tasten["C"].befehl()
        except Exception:
            pass
    anzeige.delete()
    for zeichen in folge:
        k = tasten.get(zeichen)
        if k is None:
            return anzeige.get().strip(), f"es gibt keine Taste {zeichen!r}"
        if not k.befehl:
            return anzeige.get().strip(), f"die Taste {zeichen!r} hat keinen Befehl"
        try:
            k.befehl()
        except Exception as ex:
            return anzeige.get().strip(), f"{type(ex).__name__} bei Taste {zeichen!r}: {ex}"
    return anzeige.get().strip(), None


def tun(e):
    name = str(e["datei"]).strip()
    if "/" in name or "\\" in name or not name.endswith(".py"):
        raise Abbruch("datei muss ein .py-Name aus der Werkstatt sein, ohne Pfad.")
    anzeige, tasten, f = _laden(name)

    z = [f"{name}: {len(f.knoepfe)} Tasten ({' '.join(sorted(tasten)) or 'keine'}).",
         "Zwanzig Aufgaben; die richtige Antwort rechnet Python, sie steht nirgends als Zahl.",
         ""]
    falsch, erste = 0, None
    for folge, soll in aufgaben():
        roh, absturz = _druecken(anzeige, tasten, folge)
        if absturz:
            falsch += 1
            erste = erste or f"{folge} — {absturz}"
            z.append(f"  FEHLER  {folge:12s} {absturz}")
            continue
        try:
            gut = abs(float(roh) - float(soll)) < 1e-9
        except ValueError:
            gut = False
        if not gut:
            falsch += 1
            erste = erste or f"{folge} ergibt {roh!r}, richtig waere {soll:g}"
        z.append(f"  {'ok     ' if gut else 'FEHLER '} {folge:12s} ergibt {roh!r:>12}, "
                 f"Python rechnet {soll:g}")

    #  Loeschtaste: danach muss die Anzeige leer sein und die naechste Aufgabe stimmen.
    if "C" in tasten and tasten["C"].befehl:
        _druecken(anzeige, tasten, "99")
        try:
            tasten["C"].befehl()
        except Exception as ex:
            falsch += 1
            z.append(f"  FEHLER  Loeschtaste stuerzt ab: {type(ex).__name__}: {ex}")
        else:
            leer = anzeige.get().strip()
            if leer not in ("", "0"):
                falsch += 1
                erste = erste or f"nach 'C' steht noch {leer!r} in der Anzeige"
                z.append(f"  FEHLER  nach 'C' steht noch {leer!r} in der Anzeige, erwartet leer oder '0'")
            else:
                z.append(f"  ok      Loeschtaste raeumt die Anzeige ({leer!r})")
    else:
        z.append("  FEHLER  es gibt keine Loeschtaste 'C' mit Befehl")
        falsch += 1
        erste = erste or "es gibt keine Loeschtaste 'C' mit Befehl"

    #  Teilen durch null: abstuerzen darf es, still falsch rechnen nicht.
    if "/" in tasten and "0" in tasten:
        roh, absturz = _druecken(anzeige, tasten, "8/0=")
        if absturz:
            z.append(f"  ok      8/0 wird abgefangen oder bricht sichtbar ab ({absturz[:50]})")
        elif roh.strip() in ("", "0"):
            falsch += 1
            erste = erste or f"8/0 ergibt still {roh!r} statt einer Meldung"
            z.append(f"  FEHLER  8/0 ergibt still {roh!r} — das ist eine falsche Zahl, keine Meldung")
        else:
            z.append(f"  ok      8/0 ergibt {roh!r} (eine Meldung, keine stille Zahl)")

    z.append("")
    if falsch:
        z.append("RECHNEN NICHT BESTANDEN")
        z.append(f"  {falsch} Proben falsch. Zuerst dies: {erste}")
        z.append(f"  Berichtige genau diese Stelle mit WERKZEUG: schreib_datei "
                 f"{{\"name\": \"{name}\", \"inhalt\": \"<der berichtigte Quelltext>\"}} und rufe "
                 f"dieses Werkzeug danach erneut auf.")
    else:
        z.append("RECHNEN BESTANDEN")
        z.append("  Alle zwanzig Aufgaben, die Loeschtaste und die Teilung durch null stimmen.")
    return "\n".join(z)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gegenprobe":
        import tempfile
        print("Gegenprobe von rechnen_pruefen — drei gebaute Rechner:\n")
        FAELLE = [
            ("nur Addition, Minus stuerzt ab", False, '''
import tkinter as tk
w = tk.Tk()
anzeige = tk.Entry(w)
def tippe(t):
    if t == "=":
        a = anzeige.get()
        if "+" in a:
            x, y = a.split("+"); anzeige.delete(); anzeige.insert(0, str(int(x)+int(y)))
        else:
            raise ValueError("kann nur plus")
    elif t == "C":
        anzeige.delete()
    else:
        anzeige.insert("end", t)
for t in list("0123456789+-*/=C"):
    tk.Button(w, text=t, command=lambda z=t: tippe(z))
'''),
            ("jede Taste schreibt nur ihr Zeichen", False, '''
import tkinter as tk
w = tk.Tk()
anzeige = tk.Entry(w)
def plus(a, b): return a + b
def minus(a, b): return a - b
def tippe(t):
    anzeige.insert("end", t)
for t in list("0123456789+-*/=C"):
    tk.Button(w, text=t, command=lambda z=t: tippe(z))
'''),
            ("rechnet richtig", True, '''
import tkinter as tk
w = tk.Tk()
anzeige = tk.Entry(w)
def tippe(t):
    if t == "C":
        anzeige.delete()
    elif t == "=":
        try:
            r = eval(anzeige.get())
        except ZeroDivisionError:
            anzeige.delete(); anzeige.insert(0, "Fehler"); return
        anzeige.delete(); anzeige.insert(0, str(r))
    else:
        anzeige.insert("end", t)
for t in list("0123456789+-*/=C"):
    tk.Button(w, text=t, command=lambda z=t: tippe(z))
'''),
        ]
        alle = True
        ordner = pathlib.Path(tempfile.mkdtemp())
        for titel, soll_bestehen, quelle in FAELLE:
            d = ordner / "pruefling.py"
            d.write_text(quelle, encoding="utf-8")
            import _muster
            _muster.WERKSTATT = ordner
            globals()["WERKSTATT"] = ordner
            try:
                erg = tun({"datei": "pruefling.py"})
            except Abbruch as a:
                erg = f"RECHNEN NICHT BESTANDEN\n{a}"
            besteht = "RECHNEN BESTANDEN" in erg
            richtig = besteht == soll_bestehen
            alle &= richtig
            print(f"  {titel}")
            print(f"    erwartet: {'besteht' if soll_bestehen else 'faellt durch'}  —  "
                  f"gemessen: {'besteht' if besteht else 'faellt durch'}  "
                  f"{'richtig' if richtig else 'FALSCH'}")
            kern = [l for l in erg.splitlines() if "Zuerst dies" in l or "Alle zwanzig" in l]
            if kern:
                print(f"    {kern[0].strip()[:120]}")
            print()
        print("GEGENPROBE BESTANDEN" if alle else "GEGENPROBE NICHT BESTANDEN")
        raise SystemExit(0 if alle else 1)
    raise SystemExit(werkzeug(
        "rechnen_pruefen",
        "Stellt einem erzeugten Taschenrechner zwanzig Aufgaben, deren richtige Antwort Python "
        "selbst rechnet, und prueft dazu Loeschtaste und Teilung durch null. Urteil RECHNEN "
        "BESTANDEN / NICHT BESTANDEN. Rufe es bei jedem Rechenprogramm auf — ein Fenster, das "
        "erscheint, sagt nichts darueber, ob hinter den Tasten etwas steht.",
        {"datei": {"type": "string", "description": "Dateiname in der Werkstatt, z. B. rechner.py"}},
        ["datei"], {"datei": "rechner.py"}, tun))
