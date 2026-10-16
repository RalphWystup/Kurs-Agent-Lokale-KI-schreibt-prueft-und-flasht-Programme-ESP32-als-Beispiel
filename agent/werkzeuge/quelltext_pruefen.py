#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Liest das erzeugte Programm als Syntaxbaum und berichtet, was wirklich darin steht.

Warum es dieses Werkzeug gibt
-----------------------------
Ein Sprachmodell kann einen Quelltext schreiben. Es kann nicht zuverlaessig sagen, was dieser
Quelltext tut — es sagt, was es gemeint hat. Am 08.10.2026 entstanden vier Taschenrechner; alle
vier sahen im Fenster vollstaendig aus, und alle vier waren mangelhaft: bei einem rechnete keine
Taste, bei einem nur die Addition, bei einem stuerzte ``=`` mit einem NameError ab. Keiner waere
ohne Messung aufgefallen.

Hier wird gemessen, bevor irgendetwas laeuft. Berichtet werden nur Tatsachen aus dem Syntaxbaum:

  * welche Anschluesse angelegt werden, als Ein- oder Ausgang, ob PWM im Spiel ist
  * alle Wartezeiten und der **daraus gerechnete Soll-Takt** je Anschluss
  * ob es eine Endlosschleife gibt
  * alle Importe, gehalten gegen die MicroPython-Liste
  * Namen, die benutzt, aber nirgends festgelegt werden — die Ursache jedes NameError
  * Funktionen, die festgelegt, aber nie gerufen werden — toter Code
  * Knoepfe ohne Befehl: ``Button(...)`` ohne ``command`` und ohne ``bind`` — der Fehler,
    an dem der erste Taschenrechner scheiterte

Was dieses Werkzeug sagt, ist nachrechenbar: Jeder Befund nennt die Zeile, in der er steht.
Es urteilt nicht ueber den Sinn des Programms, sondern ueber das, was dasteht.

Grundsatz 39 (09.10.2026): Jede Behauptung wird unabhaengig geprueft. Dieses Werkzeug ist eine
der Stellen, an denen die Behauptung des Modells „ich habe einen Taschenrechner geschrieben"
gegen den Quelltext gehalten wird — nicht gegen die Erinnerung daran.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, WERKSTATT
import ast
import builtins

ERLAUBTE_MODULE_ESP32 = {"machine", "time", "utime", "math", "random", "struct", "ustruct",
                         "sys", "gc"}


# ------------------------------------------------------------------ Hilfen am Syntaxbaum
def _name_von(knoten) -> str:
    """'machine.Pin' aus einem Attribut- oder Namensknoten, so weit es geht."""
    if isinstance(knoten, ast.Name):
        return knoten.id
    if isinstance(knoten, ast.Attribute):
        return f"{_name_von(knoten.value)}.{knoten.attr}"
    return ""


def _zahl(knoten):
    """Ein konstanter Zahlenwert, sonst None. Keine Auswertung von Ausdruecken: geraten wird nicht."""
    if isinstance(knoten, ast.Constant) and isinstance(knoten.value, (int, float)):
        return float(knoten.value)
    if isinstance(knoten, ast.UnaryOp) and isinstance(knoten.op, ast.USub):
        z = _zahl(knoten.operand)
        return -z if z is not None else None
    return None


class Untersuchung(ast.NodeVisitor):
    def __init__(self):
        self.pins = {}           # Nummer -> Art ('OUT', 'IN', 'PWM', 'unbekannt')
        self.wartezeiten = []    # (Sekunden, Zeile, Quelle)
        self.importe = []        # (Modul, Zeile)
        self.endlos = []         # Zeilen mit while True
        self.festgelegt = set()  # Funktions- und Klassennamen
        self.gerufen = set()     # gerufene Namen
        self.benutzt = set()     # alle gelesenen Namen
        self.zugewiesen = set()  # alle zugewiesenen Namen
        self.knoepfe = []        # (Zeile, hat_command)
        self.bindungen = 0
        self.tk = False

    # -- Importe
    def visit_Import(self, k):
        for n in k.names:
            self.importe.append((n.name.split(".")[0], k.lineno))
            if n.name.split(".")[0] in ("tkinter", "Tkinter"):
                self.tk = True
            self.zugewiesen.add((n.asname or n.name).split(".")[0])
        self.generic_visit(k)

    def visit_ImportFrom(self, k):
        modul = (k.module or "").split(".")[0]
        self.importe.append((modul, k.lineno))
        if modul in ("tkinter", "Tkinter"):
            self.tk = True
        for n in k.names:
            self.zugewiesen.add(n.asname or n.name)
        self.generic_visit(k)

    # -- Namen
    def visit_Name(self, k):
        if isinstance(k.ctx, ast.Store):
            self.zugewiesen.add(k.id)
        else:
            self.benutzt.add(k.id)
        self.generic_visit(k)

    def _argumente(self, args):
        for a in list(args.args) + list(args.posonlyargs) + list(args.kwonlyargs):
            self.zugewiesen.add(a.arg)
        if args.vararg:
            self.zugewiesen.add(args.vararg.arg)
        if args.kwarg:
            self.zugewiesen.add(args.kwarg.arg)

    def visit_FunctionDef(self, k):
        self.festgelegt.add(k.name)
        self.zugewiesen.add(k.name)
        self._argumente(k.args)
        self.generic_visit(k)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, k):
        #  Am 09.10.2026 meldete dieses Werkzeug beim ersten Lauf gegen einen echten
        #  Taschenrechner den Namen 't' als „nirgends festgelegt". In Wahrheit stand dort
        #  command=lambda t=text: button_click(t) — t ist das Argument des Lambda. Ein
        #  Pruefmittel, das einen Fehler erfindet, schadet so viel wie eines, das keinen
        #  findet: Das Modell berichtigt dann etwas, das richtig war (Grundsatz 39, die
        #  Behauptung dieses Werkzeugs wurde selbst geprueft und hielt nicht).
        self._argumente(k.args)
        self.generic_visit(k)

    def visit_ClassDef(self, k):
        self.festgelegt.add(k.name)
        self.zugewiesen.add(k.name)
        self.generic_visit(k)

    def visit_ExceptHandler(self, k):
        if k.name:
            self.zugewiesen.add(k.name)
        self.generic_visit(k)

    def visit_comprehension(self, k):
        self.generic_visit(k)

    def visit_While(self, k):
        if isinstance(k.test, ast.Constant) and k.test.value is True:
            self.endlos.append(k.lineno)
        self.generic_visit(k)

    # -- Aufrufe
    def visit_Call(self, k):
        name = _name_von(k.func)
        kurz = name.split(".")[-1]
        if name:
            self.gerufen.add(name)
            self.gerufen.add(kurz)

        #  Pin(n, Pin.OUT) / machine.Pin(n) — die Nummer ist das erste Argument
        if kurz == "Pin" and k.args:
            nr = _zahl(k.args[0])
            if nr is not None:
                art = "unbekannt"
                for a in list(k.args[1:]) + [w.value for w in k.keywords]:
                    t = _name_von(a).split(".")[-1]
                    if t in ("OUT", "IN"):
                        art = t
                self.pins.setdefault(int(nr), art)
                if art != "unbekannt":
                    self.pins[int(nr)] = art

        #  PWM(Pin(n)) oder PWM(n)
        if kurz == "PWM" and k.args:
            nr = _zahl(k.args[0])
            if nr is None and isinstance(k.args[0], ast.Call):
                innen = k.args[0]
                if innen.args:
                    nr = _zahl(innen.args[0])
            if nr is not None:
                self.pins[int(nr)] = "PWM"

        #  sleep(x), sleep_ms(x), sleep_us(x)
        if kurz in ("sleep", "sleep_ms", "sleep_us") and k.args:
            z = _zahl(k.args[0])
            if z is not None:
                teiler = {"sleep": 1.0, "sleep_ms": 1e3, "sleep_us": 1e6}[kurz]
                self.wartezeiten.append((z / teiler, k.lineno, f"{kurz}({z:g})"))

        #  tkinter: Button ohne command
        if kurz == "Button":
            hat = any(w.arg == "command" for w in k.keywords)
            self.knoepfe.append((k.lineno, hat))
            self.tk = True
        if kurz == "bind":
            self.bindungen += 1
        self.generic_visit(k)


# ------------------------------------------------------------------ Befunde
def _befunde(u: Untersuchung, baum, fuer: str, erwartet: dict) -> tuple[list, list]:
    """(erfuellt, maengel) — erfuellt zuerst, damit der Schueler nicht alles wegwirft (L6)."""
    erfuellt, maengel = [], []

    # 1. Importe
    if fuer == "esp32":
        schlecht = [(m, z) for m, z in u.importe if m not in ERLAUBTE_MODULE_ESP32]
        if schlecht:
            for m, z in schlecht:
                maengel.append((10, f"Zeile {z}: '{m}' gibt es auf dem ESP32 nicht. "
                                    f"MicroPython kennt nur: {', '.join(sorted(ERLAUBTE_MODULE_ESP32))}."))
        elif u.importe:
            erfuellt.append(f"alle {len(u.importe)} Importe gibt es auf dem ESP32")

    # 2. Namen, die benutzt, aber nie festgelegt werden -> NameError beim Laufen
    eingebaut = set(dir(builtins))
    offen = sorted(n for n in (u.benutzt - u.zugewiesen - eingebaut) if not n.startswith("_"))
    if offen:
        maengel.append((0, f"Diese Namen werden benutzt, aber nirgends festgelegt: "
                           f"{', '.join(offen[:8])}. Beim Laufen gibt das einen NameError. "
                           f"(Am 08.10.2026 stuerzte genau so die Taste '=' eines Taschenrechners ab.)"))
    else:
        erfuellt.append("jeder benutzte Name ist auch festgelegt")

    # 3. Funktionen, die nie gerufen werden
    tot = sorted(n for n in (u.festgelegt - u.gerufen) if not n.startswith("_"))
    #  Der Einstiegspunkt main() darf ungerufen sein, wenn er unter if __name__ steht.
    tot = [n for n in tot if n not in ("main",)]
    if tot:
        maengel.append((20, f"Diese Funktionen stehen da, werden aber nie gerufen: "
                            f"{', '.join(tot[:8])}. Entweder fehlt der Aufruf, oder sie sind "
                            f"ueberfluessig. (So war der erste Taschenrechner gebaut: vier "
                            f"fertige Rechenfunktionen, und keine wurde je benutzt.)"))
    elif u.festgelegt:
        erfuellt.append(f"alle {len(u.festgelegt)} Funktionen werden auch gerufen")

    # 4. Knoepfe ohne Befehl
    if u.knoepfe:
        ohne = [z for z, hat in u.knoepfe if not hat]
        if ohne and u.bindungen == 0:
            maengel.append((5, f"{len(ohne)} von {len(u.knoepfe)} Button-Aufrufstellen haben weder "
                               f"'command' noch eine Bindung mit bind(): Zeilen "
                               f"{', '.join(str(z) for z in ohne[:10])}. Diese Knoepfe tun nichts, "
                               f"wenn man sie drueckt."))
        else:
            erfuellt.append(f"alle {len(u.knoepfe)} Button-Aufrufstellen haben einen Befehl"
                            + (f" oder eine der {u.bindungen} Bindungen" if u.bindungen else ""))

    # 5. Endlosschleife — beim ESP32 noetig, beim Rechnerprogramm meist falsch
    if fuer == "esp32":
        if u.endlos:
            erfuellt.append(f"Endlosschleife in Zeile {u.endlos[0]} — das Programm laeuft dauerhaft")
        else:
            maengel.append((30, "Es gibt keine Endlosschleife. Ein Programm auf dem Brett soll "
                                "laufen, solange Strom anliegt; ohne 'while True' ist es nach "
                                "einem Durchgang zu Ende."))

    # 6. Anschluesse gegen die Erwartung
    soll = (erwartet or {}).get("pins")
    if soll is not None:
        ist = sorted(u.pins)
        if sorted(int(x) for x in soll) == ist:
            erfuellt.append(f"die Anschluesse stimmen: {ist}")
        else:
            maengel.append((1, f"Der Auftrag nennt die Anschluesse {sorted(int(x) for x in soll)}, "
                               f"im Quelltext stehen {ist or '(keine)'}."))

    return erfuellt, maengel


def _takt(u: Untersuchung) -> list:
    """Aus den Wartezeiten den Soll-Takt rechnen — nachrechenbar, nicht geraten."""
    zeilen = []
    if not u.wartezeiten:
        return zeilen
    for s, z, q in u.wartezeiten:
        zeilen.append(f"  Zeile {z}: {q}  = {s:g} s")
    #  Zwei gleiche Wartezeiten je Durchgang: eine Periode sind beide zusammen.
    summe = sum(s for s, _, _ in u.wartezeiten)
    if summe > 0:
        zeilen.append(f"  Summe je Durchgang: {summe:g} s  ->  Takt = 1 / {summe:g} s "
                      f"= {1 / summe:.3f} Hz, wenn die Schleife genau einmal durchlaeuft")
    return zeilen


def tun(e):
    name = str(e["datei"]).strip()
    if "/" in name or "\\" in name or not name.endswith(".py"):
        raise Abbruch("datei muss ein .py-Name aus der Werkstatt sein, ohne Pfad.")
    quelle = WERKSTATT / name
    if not quelle.is_file():
        da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*"))) or "(nichts)"
        raise Abbruch(f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}. "
                      f"Erst WERKZEUG: schreib_datei aufrufen.")
    text = quelle.read_text(encoding="utf-8", errors="replace")
    try:
        baum = ast.parse(text, filename=name)
    except SyntaxError as s:
        raise Abbruch(f"{name} ist kein gueltiges Python: Zeile {s.lineno}: {s.msg}\n"
                      f"Berichtige die Zeile mit WERKZEUG: schreib_datei und pruefe erneut.")

    u = Untersuchung()
    u.visit(baum)
    fuer = str(e.get("fuer", "")).strip().lower()
    if not fuer:
        fuer = "esp32" if any(m == "machine" for m, _ in u.importe) else \
               ("fenster" if u.tk else "rechner")
    erwartet = e.get("erwartet") or {}

    z = [f"{name}: {len(text.splitlines())} Zeilen, untersucht als Programm fuer "
         f"{'den ESP32' if fuer == 'esp32' else 'ein Fenster' if fuer == 'fenster' else 'den Rechner'}.",
         ""]

    z.append("Was darin steht:")
    if u.pins:
        for nr in sorted(u.pins):
            z.append(f"  Anschluss {nr}: {u.pins[nr]}")
    else:
        z.append("  Anschluesse: (keine)")
    if u.importe:
        z.append("  Importe: " + ", ".join(sorted({m for m, _ in u.importe})))
    if u.knoepfe:
        #  Gezaehlt werden Aufrufstellen, nicht Knoepfe: eine Stelle in einer Schleife
        #  erzeugt so viele Knoepfe, wie die Schleife Durchgaenge hat. Wer hier „1 Knopf"
        #  schriebe, behauptete etwas Falsches ueber einen Rechner mit sechzehn Tasten.
        z.append(f"  Button-Aufrufstellen: {len(u.knoepfe)}, davon "
                 f"{sum(1 for _, h in u.knoepfe if h)} mit command"
                 + (f", dazu {u.bindungen} Bindungen mit bind()" if u.bindungen else "")
                 + " (eine Stelle in einer Schleife erzeugt mehrere Knoepfe)")
    if u.festgelegt:
        z.append(f"  Funktionen: {', '.join(sorted(u.festgelegt)[:10])}")
    takt = _takt(u)
    if takt:
        z.append("  Wartezeiten und der Takt, der sich daraus rechnet:")
        z.extend("  " + t for t in takt)

    erfuellt, maengel = _befunde(u, baum, fuer, erwartet)
    z.append("")
    if erfuellt:
        z.append("Das stimmt:")
        z.extend(f"  + {s}" for s in erfuellt)
    if maengel:
        maengel.sort(key=lambda x: x[0])
        z.append("")
        z.append(f"Zuerst dies: {maengel[0][1]}")
        if len(maengel) > 1:
            z.append("Danach noch:")
            z.extend(f"  - {s}" for _, s in maengel[1:])
        z.append("")
        z.append("QUELLTEXT NICHT BESTANDEN")
        z.append(f"  Berichtige den ersten Punkt mit WERKZEUG: schreib_datei "
                 f"{{\"name\": \"{name}\", \"inhalt\": \"<der berichtigte Quelltext>\"}} und rufe "
                 f"dieses Werkzeug danach erneut auf.")
    else:
        z.append("")
        z.append("QUELLTEXT BESTANDEN")
        z.append("  Im Quelltext ist nichts zu beanstanden. Das sagt noch nicht, dass das "
                 "Programm das Richtige tut — das sagt erst die Messung "
                 "(programm_testen, fenster_bedienen oder esp32_nachlesen).")
    return "\n".join(z)


#  Vier gebaute Faelle fuer die Gegenprobe. Drei muessen durchfallen, einer muss bestehen —
#  ein Pruefmittel, das immer anschlaegt, ist so wertlos wie eines, das nie anschlaegt (B4).
GEGENPROBE = [
    ("NameError: ein Name wird benutzt, aber nie festgelegt",
     "import tkinter as tk\n"
     "w = tk.Tk()\n"
     "def gleich():\n"
     "    return math_operation(1, 2)\n"
     "tk.Button(w, text='=', command=gleich).pack()\n", "fenster", False),

    ("tote Funktion: vier Rechenwege, keiner wird gerufen",
     "import tkinter as tk\n"
     "def plus(a, b): return a + b\n"
     "def minus(a, b): return a - b\n"
     "def mal(a, b): return a * b\n"
     "def geteilt(a, b): return a / b\n"
     "w = tk.Tk()\n"
     "tk.Button(w, text='+', command=w.quit).pack()\n", "fenster", False),

    ("Knopf ohne Befehl: Button ohne command und ohne bind",
     "import tkinter as tk\n"
     "w = tk.Tk()\n"
     "tk.Button(w, text='7').pack()\n"
     "tk.Button(w, text='8').pack()\n"
     "w.mainloop()\n", "fenster", False),

    #  15.10.2026, sein Wort: „ich will keine Versuchungen!" — der saubere Fall ist kein
    #  Blinkprogramm mehr. Nirgends im Paket darf eine Loesung der Kursaufgaben stehen.
    ("sauber: ein Tasterprogramm, an dem nichts auszusetzen ist",
     "import machine\n"
     "import time\n"
     "taster = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)\n"
     "while True:\n"
     "    if taster.value() == 0:\n"
     "        print('gedrueckt')\n"
     "        time.sleep(0.5)\n"
     "    time.sleep(0.5)\n", "esp32", True),
]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gegenprobe":
        print("Gegenprobe von quelltext_pruefen — drei Faelle muessen durchfallen, einer bestehen:\n")
        alle_richtig = True
        for titel, quelle, fuer, soll_bestehen in GEGENPROBE:
            u = Untersuchung()
            u.visit(ast.parse(quelle))
            erf, man = _befunde(u, None, fuer, {})
            besteht = not man
            richtig = besteht == soll_bestehen
            alle_richtig &= richtig
            print(f"  {titel}")
            print(f"    erwartet: {'besteht' if soll_bestehen else 'faellt durch'}  —  "
                  f"gemessen: {'besteht' if besteht else 'faellt durch'}  "
                  f"{'richtig' if richtig else 'FALSCH'}")
            if man:
                print(f"    Befund: {sorted(man)[0][1][:110]}")
            if soll_bestehen and erf:
                print(f"    erfuellt: {'; '.join(erf)[:110]}")
            print()
        #  Takt aus Wartezeiten: Handrechnung 0,5 s + 0,5 s = 1 s -> 1,000 Hz (Kriterium T5)
        u = Untersuchung(); u.visit(ast.parse(GEGENPROBE[3][1]))
        summe = sum(s for s, _, _ in u.wartezeiten)
        takt = 1 / summe if summe else 0
        takt_richtig = abs(takt - 1.0) < 1e-9
        alle_richtig &= takt_richtig
        print(f"  T5 Takt aus den Wartezeiten: {summe:g} s je Durchgang -> {takt:.3f} Hz "
              f"(von Hand: 0,5 + 0,5 = 1 s -> 1,000 Hz)  "
              f"{'richtig' if takt_richtig else 'FALSCH'}")
        print()
        print("GEGENPROBE BESTANDEN" if alle_richtig else "GEGENPROBE NICHT BESTANDEN")
        raise SystemExit(0 if alle_richtig else 1)
    if len(sys.argv) > 2 and sys.argv[1] == "--text":
        #  Fuer die Gegenprobe: Quelltext unmittelbar pruefen, ohne Werkstatt.
        t = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
        u = Untersuchung(); u.visit(ast.parse(t))
        erf, man = _befunde(u, None, sys.argv[3] if len(sys.argv) > 3 else "rechner", {})
        print("erfuellt:", erf)
        for g, s in sorted(man):
            print(f"  [{g}] {s}")
        raise SystemExit(0)
    raise SystemExit(werkzeug(
        "quelltext_pruefen",
        "Liest ein Programm aus der Werkstatt als Syntaxbaum und berichtet, was wirklich darin "
        "steht: Anschluesse, Wartezeiten und der daraus gerechnete Takt, Importe, Namen ohne "
        "Festlegung (NameError), Funktionen die nie gerufen werden, Knoepfe ohne Befehl. "
        "Urteil QUELLTEXT BESTANDEN / NICHT BESTANDEN. Das ist der Schritt VOR dem Laufenlassen.",
        {"datei":    {"type": "string", "description": "Dateiname in der Werkstatt, z. B. blink.py"},
         "fuer":     {"type": "string", "description": "esp32, fenster oder rechner; sonst selbst erkannt"},
         "erwartet": {"type": "object", "description": "wie bei programm_testen, z. B. {\"pins\": [2]}"}},
        ["datei"], {"datei": "blink.py"}, tun))
