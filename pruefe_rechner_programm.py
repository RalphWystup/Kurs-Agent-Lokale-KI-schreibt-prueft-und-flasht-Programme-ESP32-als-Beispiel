#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prüft einen erzeugten Taschenrechner, ohne dass jemand Tasten drückt.

    python pruefe_rechner_programm.py [pfad\\rechner.py]

Warum
-----
Beide bisher erzeugten Taschenrechner sahen fertig aus: Fenster, sechzehn Tasten, vier
Rechenarten. Beim ersten funktionierte nur die Addition, die anderen drei Tasten schrieben ihr
Zeichen bloß in die Anzeige. Gesehen hat das niemand, weil ein Blick auf das Fenster nicht
zeigt, was hinter einer Taste steht — und weil `programm_testen` tkinter nicht zulässt und
`programm_ausfuehren` das Programm nur startet.

Dieses Programm macht daraus eine Messung. Es lädt die Datei mit einem **nachgebauten tkinter**,
in dem jedes Bedienelement nur mitschreibt, statt etwas anzuzeigen. Dadurch läuft derselbe
Quelltext ohne Bildschirm, und danach lässt sich drücken, was sonst ein Mensch drücken müsste:
Die Tastenbefehle werden aufgerufen und das Ergebnis im Anzeigefeld gelesen.

Geprüft wird, was der Auftrag verlangt: Anzeige, Ziffern 0-9, die vier Rechenarten, Gleich und
Löschen. Jede Rechnung wird gegen das richtige Ergebnis gehalten, nicht gegen „es kam etwas".
"""
from __future__ import annotations
import pathlib
import sys
import types

fehler = 0


def sage(gut: bool, text: str) -> None:
    global fehler
    if not gut:
        fehler += 1
    print(f"  {'ok    ' if gut else 'FEHLER'}  {text}")


# ----------------------------------------------------------------- nachgebautes tkinter
class Feld:
    """Ein Eingabefeld, das sich merkt, was darin steht — mehr braucht ein Taschenrechner nicht."""

    def __init__(self, **kw):
        self.inhalt = ""

    def get(self):
        return self.inhalt

    def insert(self, wo, was):
        if wo in (0, "0", "end", "insert"):
            self.inhalt = (str(was) + self.inhalt) if wo in (0, "0") else (self.inhalt + str(was))
        else:
            self.inhalt += str(was)

    def delete(self, von, bis=None):
        self.inhalt = ""

    def config(self, **kw):
        if "text" in kw:
            self.inhalt = str(kw["text"])

    configure = config

    def __setitem__(self, k, v):
        self.config(**{k: v})

    def grid(self, **kw):
        return self

    def pack(self, **kw):
        return self

    def place(self, **kw):
        return self

    def bind(self, *a, **kw):
        return None

    def focus_set(self):
        return None


class Knopf(Feld):
    def __init__(self, master=None, **kw):
        super().__init__()
        self.text = str(kw.get("text", ""))
        self.befehl = kw.get("command")
        if master is not None and hasattr(master, "knoepfe"):
            master.knoepfe.append(self)


class Fenster(Feld):
    def __init__(self, *a, **kw):
        super().__init__()
        self.knoepfe = []
        self.titel = ""

    def title(self, t=None):
        if t is not None:
            self.titel = str(t)
        return self.titel

    def mainloop(self, *a, **kw):
        return None

    def geometry(self, *a, **kw):
        return None

    def resizable(self, *a, **kw):
        return None

    def destroy(self):
        return None

    def columnconfigure(self, *a, **kw):
        return None

    rowconfigure = columnconfigure

    def quit(self):
        return None


def nachbau() -> types.ModuleType:
    """Ein Modul, das sich wie tkinter verhält, aber nur mitschreibt."""
    m = types.ModuleType("tkinter")
    fenster = Fenster()

    def Tk(*a, **kw):
        return fenster

    class StringVar:
        def __init__(self, *a, **kw):
            self.wert = kw.get("value", "")

        def get(self):
            return self.wert

        def set(self, w):
            self.wert = str(w)

    def macher(klasse):
        def bauen(master=None, **kw):
            return klasse(master if master is not None else fenster, **kw) if klasse is Knopf else klasse(**kw)
        return bauen

    m.Tk = Tk
    m.Frame = macher(Feld)
    m.Entry = macher(Feld)
    m.Label = macher(Feld)
    m.Button = macher(Knopf)
    m.StringVar = StringVar
    m.END = "end"
    m.INSERT = "insert"
    m.LEFT = "left"
    m.RIGHT = "right"
    m.TOP = "top"
    m.BOTTOM = "bottom"
    m.BOTH = "both"
    m.X = "x"
    m.Y = "y"
    m.W = "w"
    m.E = "e"
    m.N = "n"
    m.S = "s"
    m.NSEW = "nsew"
    m.DISABLED = "disabled"
    m.NORMAL = "normal"
    m.ttk = types.SimpleNamespace(Button=macher(Knopf), Entry=macher(Feld), Label=macher(Feld),
                                  Frame=macher(Feld), Style=lambda *a, **kw: types.SimpleNamespace(configure=lambda *x, **y: None))
    m.messagebox = types.SimpleNamespace(showerror=lambda *a, **kw: None, showinfo=lambda *a, **kw: None)
    m._fenster = fenster
    return m


# ----------------------------------------------------------------- die Prüfung
def druecke(knoepfe: dict, folge: str) -> str | None:
    """Eine Tastenfolge drücken, zum Beispiel '12+7='. Gibt den Absturz zurück, falls einer kommt.

    Ein Taschenrechner, der bei einer Taste abstürzt, ist ein Befund und kein Grund, die Prüfung
    abzubrechen: Beim ersten erzeugten Programm warf „9-4=" einen Fehler, weil das Minus nur in
    die Anzeige geschrieben und danach als Zahl gelesen wurde.
    """
    for z in folge:
        k = knoepfe.get(z)
        if k and k.befehl:
            try:
                k.befehl()
            except Exception as e:
                return f"{type(e).__name__} bei Taste {z!r}: {e}"
    return None


def main() -> int:
    pfad = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
        pathlib.Path(__file__).resolve().parent / "ablage" / "werkstatt" / "rechner.py"
    print(f"Geprüft wird: {pfad}\n")
    if not pfad.is_file():
        print(f"FEHLER: {pfad} gibt es nicht")
        return 2

    tk = nachbau()
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = tk.ttk
    sys.modules["tkinter.messagebox"] = tk.messagebox

    raum: dict = {"__name__": "__main__", "__file__": str(pfad)}
    try:
        exec(compile(pfad.read_text(encoding="utf-8", errors="replace"), str(pfad), "exec"), raum)
    except Exception as e:
        print(f"FEHLER beim Laden: {type(e).__name__}: {e}")
        return 1

    f = tk._fenster
    knoepfe = {k.text.strip(): k for k in f.knoepfe}
    print(f"  Fenstertitel: {f.title() or '(keiner)'}")
    print(f"  Tasten gefunden: {len(f.knoepfe)} — {' '.join(sorted(knoepfe))}\n")

    for z in "0123456789":
        if z not in knoepfe:
            sage(False, f"Taste {z} fehlt")
            break
    else:
        sage(True, "alle zehn Ziffern sind da")
    for z in "+-*/=C":
        sage(z in knoepfe, f"Taste {z} ist da")

    # Das Anzeigefeld finden: das Feld, in das die Ziffern schreiben.
    anzeige = None
    for name, wert in raum.items():
        if isinstance(wert, Feld) and not isinstance(wert, (Knopf, Fenster)):
            anzeige = wert
            break
    if anzeige is None:
        sage(False, "kein Anzeigefeld gefunden — der Rest ist nicht prüfbar")
        return 1

    rechnungen = [("12+7=", 19), ("9-4=", 5), ("6*7=", 42), ("8/2=", 4)]
    for folge, soll in rechnungen:
        if "C" in knoepfe and knoepfe["C"].befehl:
            knoepfe["C"].befehl()
        anzeige.delete(0)
        absturz = druecke(knoepfe, folge)
        roh = anzeige.get().strip()
        if absturz:
            sage(False, f"{folge:7s} stuerzt ab — {absturz}")
            continue
        try:
            ist = float(roh)
            gut = abs(ist - soll) < 1e-9
        except ValueError:
            gut = False
        sage(gut, f"{folge:7s} ergibt {roh!r}, erwartet {soll}")

    if "C" in knoepfe and knoepfe["C"].befehl:
        druecke(knoepfe, "123")
        try:
            knoepfe["C"].befehl()
        except Exception as e:
            sage(False, f"C stuerzt ab: {type(e).__name__}: {e}")
            print(); return 1
        sage(anzeige.get().strip() == "", f"C leert die Anzeige (danach steht {anzeige.get()!r})")

    print()
    print("alles in Ordnung" if not fehler else f"{fehler} Befund(e) — das Programm ist nicht fertig")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
