#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: ein Programm mit Fenster bedienen und messen, was dabei herauskommt.

Die Luecke, die dieses Werkzeug schliesst
-----------------------------------------
Bis zum 09.10.2026 konnte der Agent ein Fensterprogramm nur **starten** (programm_ausfuehren)
und sehen, ob ein Fenster erscheint. Was hinter den Tasten steht, prueft das nicht. Vier
erzeugte Taschenrechner liefen damit durch:

  * einer, bei dem jede Taste nur ihr Zeichen in die Anzeige schrieb -- die vier fertigen
    Rechenfunktionen darueber wurden nie aufgerufen,
  * einer, der nur addieren konnte und bei Minus mit ValueError abstuerzte,
  * einer, der bei Gleich mit NameError abstuerzte,
  * und einer, der wirklich rechnete.

Von aussen sahen alle vier gleich aus: Fenster da, sechzehn Tasten, alles ordentlich. Der Agent
sagte dreimal FERTIG zu einem Programm, das beim ersten Rechnen scheitert.

Wie gemessen wird
-----------------
Das Programm wird mit einem **nachgebauten tkinter** geladen: Jedes Bedienelement merkt sich nur,
was in ihm steht, statt etwas anzuzeigen. Derselbe Quelltext laeuft damit ohne Bildschirm. Danach
werden die Tastenbefehle aufgerufen -- auch die, die mit ``bind`` statt ``command`` angehaengt
sind -- und das Ergebnis im Anzeigefeld gelesen und gegen den richtigen Wert gehalten.

Das ersetzt programm_ausfuehren nicht, es ergaenzt es: dort laeuft das Programm wirklich und
zeigt sein Fenster, hier wird gerechnet und nachgemessen.
"""
import sys
import pathlib

_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, WERKSTATT                                   # noqa: E402
import types                                                              # noqa: E402


# ----------------------------------------------------------------- nachgebautes tkinter
class Feld:
    def __init__(self, **kw):
        self.inhalt = ""
        self.befehl = None

    def get(self):
        return self.inhalt

    def insert(self, wo, was):
        self.inhalt = (str(was) + self.inhalt) if wo in (0, "0") else (self.inhalt + str(was))

    def delete(self, von=0, bis=None):
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
        #  Tasten werden oft mit bind('<Button-1>', …) angehaengt statt mit command=.
        #  Wer nur command kennt, sieht einen Knopf ohne Funktion und meldet einen Fehler,
        #  den es nicht gibt (am 09.10.2026 vier solcher Fehlmeldungen).
        if len(a) > 1 and callable(a[1]) and not self.befehl:
            h = a[1]
            self.befehl = lambda: h(None)
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

    resizable = geometry

    def destroy(self):
        return None

    def columnconfigure(self, *a, **kw):
        return None

    rowconfigure = columnconfigure

    def quit(self):
        return None


def _nachbau():
    m = types.ModuleType("tkinter")
    fenster = Fenster()

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

    m.Tk = lambda *a, **kw: fenster
    m.Frame = m.Entry = m.Label = macher(Feld)
    m.Button = macher(Knopf)
    m.StringVar = StringVar
    for n, w in (("END", "end"), ("INSERT", "insert"), ("LEFT", "left"), ("RIGHT", "right"),
                 ("TOP", "top"), ("BOTTOM", "bottom"), ("BOTH", "both"), ("X", "x"), ("Y", "y"),
                 ("W", "w"), ("E", "e"), ("N", "n"), ("S", "s"), ("NSEW", "nsew"),
                 ("DISABLED", "disabled"), ("NORMAL", "normal")):
        setattr(m, n, w)
    m.ttk = types.SimpleNamespace(Button=macher(Knopf), Entry=macher(Feld), Label=macher(Feld),
                                  Frame=macher(Feld),
                                  Style=lambda *a, **kw: types.SimpleNamespace(configure=lambda *x, **y: None))
    m.messagebox = types.SimpleNamespace(showerror=lambda *a, **kw: None, showinfo=lambda *a, **kw: None)
    m._fenster = fenster
    return m


def tun(e):
    name = e["datei"]
    pfad = WERKSTATT / name
    if not pfad.is_file():
        return f"FEHLER: {name} liegt nicht in der Werkstatt ({WERKSTATT})."

    tk = _nachbau()
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = tk.ttk
    sys.modules["tkinter.messagebox"] = tk.messagebox
    raum = {"__name__": "__main__", "__file__": str(pfad)}
    try:
        exec(compile(pfad.read_text(encoding="utf-8", errors="replace"), str(pfad), "exec"), raum)
    except Exception as ex:
        return (f"{name} laesst sich nicht laden: {type(ex).__name__}: {ex}\n\n"
                f"BEDIENUNG NICHT BESTANDEN\n  Das Programm bricht schon beim Aufbau ab. "
                f"Berichtige es mit schreib_datei.")

    f = tk._fenster
    knoepfe = {k.text.strip(): k for k in f.knoepfe}
    z = [f"{name}: Fenstertitel {f.title() or '(keiner)'}, {len(f.knoepfe)} Tasten "
         f"({' '.join(sorted(knoepfe)) or 'keine'})"]

    anzeige = next((w for w in raum.values() if isinstance(w, Feld) and not isinstance(w, (Knopf, Fenster))), None)
    if anzeige is None:
        return "\n".join(z) + "\n\nBEDIENUNG NICHT BESTANDEN\n  Kein Anzeigefeld gefunden."

    proben = e.get("proben") or [{"druecke": "12+7=", "erwartet": "19"},
                                 {"druecke": "9-4=", "erwartet": "5"},
                                 {"druecke": "6*7=", "erwartet": "42"},
                                 {"druecke": "8/2=", "erwartet": "4"}]
    fehler = 0
    for p in proben:
        folge, soll = str(p.get("druecke", "")), str(p.get("erwartet", ""))
        if "C" in knoepfe and knoepfe["C"].befehl:
            try:
                knoepfe["C"].befehl()
            except Exception:
                pass
        anzeige.delete()
        absturz = None
        for zeichen in folge:
            k = knoepfe.get(zeichen)
            if k and k.befehl:
                try:
                    k.befehl()
                except Exception as ex:
                    absturz = f"{type(ex).__name__} bei Taste {zeichen!r}: {ex}"
                    break
        roh = anzeige.get().strip()
        if absturz:
            fehler += 1
            z.append(f"  FEHLER  {folge:8s} stuerzt ab: {absturz}")
            continue
        try:
            gut = abs(float(roh) - float(soll)) < 1e-9
        except ValueError:
            gut = roh == soll
        fehler += not gut
        z.append(f"  {'ok     ' if gut else 'FEHLER '} {folge:8s} ergibt {roh!r}, erwartet {soll!r}")

    z.append("")
    if fehler:
        z.append("BEDIENUNG NICHT BESTANDEN")
        z.append(f"  {fehler} von {len(proben)} Proben falsch. Das Fenster allein sagt nichts darueber, "
                 f"ob hinter einer Taste etwas steht. Berichtige das Programm mit schreib_datei und "
                 f"pruefe erneut.")
    else:
        z.append("BEDIENUNG BESTANDEN")
        z.append(f"  Alle {len(proben)} Proben treffen.")
    return "\n".join(z)


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "fenster_bedienen",
        "Prueft ein Programm mit grafischer Oberflaeche, indem es die Tasten wirklich drueckt und das "
        "Ergebnis in der Anzeige misst — ohne Bildschirm. Fuer einen Taschenrechner ohne Angaben: "
        "12+7, 9-4, 6*7, 8/2. Urteil BEDIENUNG BESTANDEN / NICHT BESTANDEN. Ergaenzt programm_ausfuehren: "
        "dort laeuft das Fenster, hier wird nachgerechnet.",
        {"datei":  {"type": "string", "description": "Dateiname in der Werkstatt, zum Beispiel rechner.py"},
         "proben": {"type": "array", "description": "eigene Proben, je {\"druecke\": \"12+7=\", \"erwartet\": \"19\"}",
                    "items": {"type": "object"}}},
        ["datei"], {"datei": "rechner.py"}, tun))
