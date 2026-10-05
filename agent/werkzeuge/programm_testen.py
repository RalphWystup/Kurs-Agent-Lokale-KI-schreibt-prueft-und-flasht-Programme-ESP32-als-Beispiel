#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fuehrt das erzeugte Programm aus, bevor es auf die Hardware geht.

Das ist der Pruefschritt zwischen Schreiben und Ueberspielen. Das Modell schreibt ein
Programm, laesst es **hier** laufen, sieht am Ergebnis ob es tut was es soll — und erst
dann wandert dieselbe Datei auf den ESP32. Ein Programm, das hier nicht laeuft, laeuft
auch dort nicht; nur merkt man es dort erst, wenn man an der Hardware steht.

Es ist **keine** Nachahmung. Es ist dieselbe Datei, die sonst auf den ESP32 wandert, nur
mit einem nachgebauten ``machine``-Modul davor: ``Pin`` schreibt seine Zustandswechsel in
die Ausgabe, statt eine Leitung zu schalten. Der Quelltext bleibt unveraendert — wer ihn
danach ueberspielt, bekommt genau dieses Verhalten, dann an echten Anschluessen.

Zwei Dinge fallen damit zusammen:

  * **Der Test vor dem Ueberspielen.** Tippfehler, Endlosschleifen ohne Pause, ein
    vergessenes ``Pin.OUT`` — all das zeigt sich hier in Sekunden statt am Steckbrett.
  * **Der Kurs ohne Hardware.** Ein Steckbrett fehlt, zwei Teilnehmer teilen sich eines,
    der Treiber ist nicht installiert: die ganze Kette laesst sich trotzdem zeigen, mit
    einer LED auf dem Bildschirm.

Das Blinkprogramm ist dabei nur das Beispiel. Protokolliert wird jeder Anschluss, nicht
eine bestimmte Leuchtdiode; ein Programm mit drei Pins und unterschiedlichen Takten wird
genauso aufgezeichnet.

**Hier wird Quelltext ausgefuehrt, den ein Sprachmodell geschrieben hat.** Das ist der
einzige Punkt im ganzen Bausatz, an dem das geschieht, und er ist entsprechend eng
gefasst:

  * nur Dateien aus der Werkstatt, kein Pfad von aussen
  * vorher wird der Syntaxbaum durchgesehen: erlaubt sind ``machine`` und ``time``,
    sonst nichts — kein ``os``, kein ``subprocess``, kein ``open``, kein ``eval``
  * Zeitgrenze, denn ``while True`` endet nie von selbst
  * das eigene Python in der abgeschirmten Umgebung

Die Pruefung des Syntaxbaums ist kein Schutz gegen einen Angreifer — gegen den hilft
kein Filter, sondern nur, Fremdcode gar nicht auszufuehren. Sie ist ein Schutz gegen ein
Modell, das sich vertut, und das ist der Fall, der hier wirklich eintritt.
"""
import ast, json, re, sys, time, webbrowser
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

from _muster import werkzeug, Abbruch, lauf, in_der_ablage, ABLAGE, WERKSTATT, python_exe

#  math, random, struct, sys, gc: reine Rechenbibliotheken, die es in MicroPython wie in CPython gibt.
#  Ohne math kein Sinus — am 05.10.2026 fiel ein korrektes Sinus-Atmen daran, dass math verboten war.
ERLAUBTE_MODULE = {"machine", "time", "utime", "math", "random", "struct", "ustruct", "sys", "gc"}
# Alles, was zur Laufzeit an Dinge herankommt, die der Syntaxbaum nicht mehr sieht.
# getattr gehoert dazu: getattr(x, "__class__") fuehrt ueber die Klassenhierarchie zurueck
# zu allem, was die Liste darueber gerade verbietet.
VERBOTEN = {"eval", "exec", "compile", "open", "__import__", "input", "breakpoint",
            "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir",
            "memoryview", "classmethod", "staticmethod", "super"}

# Das nachgebaute machine-Modul. Es wird neben das Programm gelegt, damit der Import
# dort und nicht im echten MicroPython landet.
MACHINE = '''# -*- coding: utf-8 -*-
"""Ersatz fuer das machine-Modul von MicroPython — fuer den Lauf ohne Hardware.

Nachgebildet wird nur, was ein Blinkprogramm braucht. Jeder Zustandswechsel wird mit
Zeitstempel ausgegeben; wer mehr braucht, erweitert diese Datei.
"""
import sys, time

_START = time.time()


class Pin:
    OUT = "out"
    IN = "in"

    def __init__(self, nummer, richtung=None, *args, **kw):
        self.nummer = nummer
        self._wert = 0
        self._melde()

    def _melde(self):
        print(f"PIN {self.nummer} {self._wert} {time.time() - _START:.3f}", flush=True)

    def value(self, wert=None):
        if wert is None:
            return self._wert
        neu = 1 if wert else 0
        if neu != self._wert:
            self._wert = neu
            self._melde()
        return None

    def on(self):  self.value(1)
    def off(self): self.value(0)
    def high(self): self.value(1)
    def low(self):  self.value(0)
    def toggle(self): self.value(0 if self._wert else 1)


class Signal(Pin):
    """In MicroPython ein Pin mit moeglicher Invertierung — hier genuegt der Pin."""


class PWM:
    """Pulsweitenmodulation. Aufgezeichnet werden Frequenz und Tastgrad."""

    def __init__(self, pin, freq=None, duty=None, duty_u16=None, **kw):
        self.pin = pin if isinstance(pin, int) else getattr(pin, "nummer", 0)
        self._f, self._d = freq or 0, 0
        if duty is not None:
            self.duty(duty)
        if duty_u16 is not None:
            self.duty_u16(duty_u16)
        self._melde()

    def _melde(self):
        print(f"PWM {self.pin} {self._f} {self._d:.4f} {time.time() - _START:.3f}", flush=True)

    def freq(self, f=None):
        if f is None:
            return self._f
        self._f = f; self._melde()

    def duty(self, d=None):
        if d is None:
            return int(self._d * 1023)
        self._d = max(0.0, min(1.0, d / 1023)); self._melde()

    def duty_u16(self, d=None):
        if d is None:
            return int(self._d * 65535)
        self._d = max(0.0, min(1.0, d / 65535)); self._melde()

    def deinit(self):
        self._d = 0.0; self._melde()


class ADC:
    """Analogeingang. Es ist keine Spannung angeschlossen, also wird das auch gesagt:
    gelesen wird ein fester Wert, und im Protokoll steht, dass er erfunden ist."""

    ATTN_11DB = 3

    def __init__(self, pin, **kw):
        self.pin = pin if isinstance(pin, int) else getattr(pin, "nummer", 0)

    def atten(self, *a): pass
    def width(self, *a): pass

    def read(self):
        print(f"ADC {self.pin} 2048 ERFUNDEN {time.time() - _START:.3f}", flush=True)
        return 2048

    def read_u16(self):
        print(f"ADC {self.pin} 32768 ERFUNDEN {time.time() - _START:.3f}", flush=True)
        return 32768


def reset():
    raise SystemExit(0)


def freq(*a):
    return 240_000_000


def unique_id():
    return b"PRUEFLAUF"


def __getattr__(was):
    """Alles, was hier nicht nachgebildet ist, sagt das deutlich.

    Stillschweigend ein Scheinobjekt zu liefern waere schlimmer als ein Fehler: das
    Programm liefe scheinbar durch und versagte erst auf der Hardware — genau das, was
    dieser Pruefschritt verhindern soll.
    """
    raise AttributeError(
        f"machine.{was} ist im Lauf ohne Hardware nicht nachgebildet. "
        f"Nachgebildet sind: Pin, Signal, PWM, ADC, reset, freq, unique_id. "
        f"Dieses Programm laesst sich nur auf dem Geraet selbst pruefen.")
'''


def _pruefen(quelltext: str, name: str):
    """Sieht den Syntaxbaum durch, bevor irgendetwas laeuft."""
    try:
        baum = ast.parse(quelltext, filename=name)
    except SyntaxError as e:
        # Die Zeile mitliefern: "unmatched '}'" allein sagt einem Modell zu wenig, es
        # schreibt dann denselben Text noch einmal. Mit der Zeile vor Augen nicht.
        zeilen = quelltext.splitlines()
        stelle = (f"\n  Zeile {e.lineno}: {zeilen[e.lineno-1]}"
                  if e.lineno and 0 < e.lineno <= len(zeilen) else "")
        raise Abbruch(f"{name} ist kein gueltiges Python: Zeile {e.lineno}: {e.msg}{stelle}\n"
                      f"Schreibe die Datei mit schreib_datei neu und berichtige genau diese "
                      f"Stelle. Achte darauf, dass der Quelltext keine ueberzaehligen "
                      f"Klammern enthaelt.")
    for k in ast.walk(baum):
        if isinstance(k, ast.Import):
            for n in k.names:
                if n.name.split(".")[0] not in ERLAUBTE_MODULE:
                    raise Abbruch(f"{name} importiert '{n.name}'. Erlaubt sind hier nur "
                                  f"{', '.join(sorted(ERLAUBTE_MODULE))} — der Lauf ohne "
                                  f"Hardware fuehrt nur Blinkprogramme aus.")
        elif isinstance(k, ast.ImportFrom):
            if (k.module or "").split(".")[0] not in ERLAUBTE_MODULE:
                raise Abbruch(f"{name} holt aus '{k.module}'. Erlaubt sind hier nur "
                              f"{', '.join(sorted(ERLAUBTE_MODULE))}.")
        elif isinstance(k, ast.Name) and (k.id in VERBOTEN or k.id.startswith("__")):
            # Namen mit doppeltem Unterstrich sind der Weg aussen herum: ueber
            # __builtins__ ist jede Sperre dieser Liste erreichbar, und __builtins__.open
            # faellt unter keinen der verbotenen Namen.
            raise Abbruch(f"{name} benutzt '{k.id}'. Das ist hier nicht zugelassen.")
        elif isinstance(k, ast.Attribute) and k.attr.startswith("__"):
            raise Abbruch(f"{name} greift auf '{k.attr}' zu. Das ist hier nicht zugelassen.")


def _html(name: str, wechsel: list, zeit: float) -> str:
    daten = json.dumps(wechsel)
    return f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<title>Virtuelle LED — {name}</title><style>
 body {{ font-family:-apple-system,Segoe UI,Roboto,sans-serif; background:#1a202c; color:#e2e8f0;
        display:flex; flex-direction:column; align-items:center; padding:40px 20px; margin:0; }}
 h1 {{ font-size:1.3rem; font-weight:600; margin:0 0 6px; }}
 .unter {{ color:#a0aec0; font-size:.9rem; margin-bottom:34px; }}
 .brett {{ background:#2d3748; border-radius:14px; padding:38px 54px; border:1px solid #4a5568;
           display:flex; flex-direction:column; align-items:center; gap:18px; }}
 .led {{ width:86px; height:86px; border-radius:50%; background:#4a5568;
         border:3px solid #718096; transition:all .06s; }}
 .led.an {{ background:#f56565; border-color:#fc8181; box-shadow:0 0 44px 10px rgba(245,101,101,.65); }}
 .pin {{ font-family:ui-monospace,Consolas,monospace; color:#a0aec0; font-size:.88rem; }}
 .uhr {{ font-family:ui-monospace,Consolas,monospace; color:#63b3ed; font-size:1.05rem; }}
 table {{ margin-top:30px; border-collapse:collapse; font-size:.85rem;
          font-family:ui-monospace,Consolas,monospace; }}
 td,th {{ border:1px solid #4a5568; padding:4px 12px; text-align:right; }}
 th {{ background:#2d3748; color:#a0aec0; font-weight:600; }}
 .hinweis {{ max-width:560px; margin-top:30px; color:#a0aec0; font-size:.86rem; line-height:1.6;
             text-align:center; }}
 button {{ margin-top:22px; padding:9px 20px; border-radius:6px; border:1px solid #4a5568;
           background:#2d3748; color:#e2e8f0; cursor:pointer; font-family:inherit; font-size:.92rem; }}
</style></head><body>
<h1>Virtuelle LED</h1>
<div class="unter">{name} — {zeit:.1f} s aufgezeichnet, {len(wechsel)} Zustandswechsel</div>
<div class="brett">
 <div class="led" id="led"></div>
 <div class="pin" id="pin">Pin —</div>
 <div class="uhr" id="uhr">0.000 s</div>
</div>
<button onclick="start()">noch einmal abspielen</button>
<table><tr><th>Zeit</th><th>Pin</th><th>Wert</th></tr>
{"".join(f"<tr><td>{w[2]:.3f} s</td><td>{w[0]}</td><td>{'an' if w[1] else 'aus'}</td></tr>"
         for w in wechsel[:14])}
{"<tr><td colspan=3>…</td></tr>" if len(wechsel) > 14 else ""}
</table>
<div class="hinweis">Dies ist keine Nachahmung: es ist derselbe Quelltext, der sonst auf den
ESP32 geht, ausgeführt mit einem nachgebauten <code>machine</code>-Modul. Wer die Datei
anschließend überspielt, bekommt genau dieses Verhalten — dann auf einer echten LED.</div>
<script>
const W = {daten};
let t0 = 0, lauf = null;
function start() {{
  clearInterval(lauf); t0 = performance.now();
  const led = document.getElementById('led');
  led.classList.remove('an');
  let i = 0;
  lauf = setInterval(() => {{
    const t = (performance.now() - t0) / 1000;
    document.getElementById('uhr').textContent = t.toFixed(3) + ' s';
    while (i < W.length && W[i][2] <= t) {{
      led.classList.toggle('an', W[i][1] === 1);
      document.getElementById('pin').textContent = 'Pin ' + W[i][0];
      i++;
    }}
    if (i >= W.length && t > {zeit:.1f}) clearInterval(lauf);
  }}, 16);
}}
start();
</script></body></html>"""


def tun(e):
    name = str(e.get("datei", "blink.py")).strip()
    if "/" in name or "\\" in name:
        raise Abbruch("Gib nur den Dateinamen an, zum Beispiel blink.py.")
    quelle = WERKSTATT / name
    if not quelle.is_file():
        da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*.py"))) or "(nichts)"
        # Ein fertiges Muster statt einer Beschreibung: kleine Modelle greifen eine
        # Anweisung oft nicht auf, eine vorformulierte Zeile dagegen schon.
        raise Abbruch(
            f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}.\n"
            f"Das Programm muss erst geschrieben werden. Rufe jetzt genau dies auf:\n"
            f'WERKZEUG: schreib_datei {{"name": "{name}", "inhalt": "<der Quelltext>"}}\n'
            f"und erst danach wieder programm_testen.")
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")

    dauer = float(e.get("sekunden", 6))
    if not 1 <= dauer <= 60:
        raise Abbruch("sekunden muss zwischen 1 und 60 liegen.")

    text = quelle.read_text(encoding="utf-8")
    _pruefen(text, name)
    (WERKSTATT / "machine.py").write_text(MACHINE, encoding="utf-8")

    t0 = time.time()
    # teilausgabe: ein Blinkprogramm endet nicht von selbst, die Zeitgrenze ist der
    # Normalfall — und das bis dahin Gesagte ist genau das Ergebnis.
    # Nicht "python.exe blink.py": das eingebettete Python nimmt weder das Arbeits-
    # verzeichnis noch PYTHONPATH in den Suchpfad auf — python3xx._pth legt ihn
    # abschliessend fest. Das nachgebaute machine.py liegt daneben und waere unauffindbar
    # ("No module named 'machine'"). Also ueber einen Starter, der den Pfad selbst setzt.
    # runpy statt exec, damit die Datei im Traceback mit ihrem richtigen Namen erscheint —
    # die Fehlermeldung ist hier das Erzeugnis, sie muss stimmen.
    #  Virtuelle Zeit (05.10.2026): time.sleep rueckt eine gedachte Uhr vor, statt zu warten.
    #  Dazu je sleep 0,8 ms gedachte Rechenzeit: MicroPython auf dem ESP32 braucht fuer eine
    #  Schleifenrunde mit Kosinus und PWM-Aufruf etwa so lang. Kalibriert am 05.10.2026: Ein
    #  Atmen mit 1024 Stufen zu je 1 ms Pause brauchte am Geraet 1,8 s je Atemzug (11 in 20 s,
    #  vom Menschen gezaehlt) — 1024 x (1 + 0,8) ms. Ohne diesen Zuschlag haette der Nachbau
    #  1 Hz bescheinigt, das Geraet lieferte 0,55 Hz.
    #  Grund: Windows haelt time.sleep(0.01) nicht ein — es werden bis zu 15,6 ms. Ein Atem-
    #  programm mit 100 Stufen je Sekunde lief dadurch mit 0,64 Hz statt 1 Hz und fiel durch,
    #  obwohl es auf dem ESP32 (dessen sleep auf Mikrosekunden genau ist) richtig gewesen waere.
    #  Der Nachbau soll das Geraet nachbilden, nicht die Uhr des PC. Die Zeitstempel der Pins
    #  und PWM-Werte kommen von derselben gedachten Uhr; die Zeitgrenze endet den Lauf, sobald
    #  die gedachte Zeit erreicht ist — der Lauf dauert dann nur Bruchteile einer Sekunde.
    starter = (f"import sys, runpy, time as _t\n"
               f"sys.path.insert(0, {str(WERKSTATT)!r})\n"
               f"_V = [0.0]; _ECHT = _t.time(); _GRENZE = {float(dauer)!r}\n"
               f"def _sleep(s):\n"
               f"    _V[0] += max(0.0, float(s))\n"
               f"    _V[0] += 0.0008  # gedachte Rechenzeit des ESP32 je Schleifenrunde (kalibriert 05.10.2026: 11 Atemzuege in 20 s bei 2048 Stufen x 1 ms)\n"
               f"    if _V[0] >= _GRENZE:\n"
               f"        sys.stdout.flush(); print('ZEITGRENZE', flush=True); raise SystemExit(0)\n"
               f"_t.sleep = _sleep\n"
               f"_t.sleep_ms = lambda ms: _sleep(ms / 1000)\n"
               f"_t.sleep_us = lambda us: _sleep(us / 1e6)\n"
               f"_t.time = lambda: _ECHT + _V[0]\n"
               f"_t.monotonic = lambda: _V[0]\n"
               f"_t.ticks_ms = lambda: int(_V[0] * 1000)\n"
               f"_t.ticks_us = lambda: int(_V[0] * 1e6)\n"
               f"_t.ticks_diff = lambda a, b: a - b\n"
               f"_t.ticks_add = lambda a, b: a + b\n"
               f"sys.modules['utime'] = _t\n"
               f"runpy.run_path({str(quelle)!r}, run_name='__main__')\n")
    #  Die echte Zeitgrenze bleibt als Netz fuer Programme ohne jedes sleep (sie wuerden sonst
    #  endlos rechnen); normal endet der Lauf durch die gedachte Uhr mit 'ZEITGRENZE'.
    r = lauf([str(python_exe()), "-c", starter], zeit=max(dauer, 10.0), teilausgabe=True)
    gelaufen = time.time() - t0
    durch_zeit = r.returncode == -1 or "ZEITGRENZE" in (r.stdout or "")
    if "ZEITGRENZE" in (r.stdout or ""):
        gelaufen = dauer                    # gedachte Zeit: so lange "lief" das Programm

    # Ein abgestuerztes Programm ist der wichtigste Fall ueberhaupt — dafuer gibt es diesen
    # Schritt. Es darf nicht als "gelaufen" durchgehen, nur weil vor dem Absturz schon ein
    # Pin geschaltet wurde (Pin() meldet sich bereits beim Anlegen).
    if r.returncode not in (0, -1):
        rest = "\n".join((r.stderr or "").strip().splitlines()[-8:]) or "(keine Meldung)"
        geschaltet = sum(1 for z in (r.stdout or "").splitlines() if z.startswith("PIN "))
        raise Abbruch(
            f"{name} ist nach {gelaufen:.1f} s abgebrochen (Rueckgabewert {r.returncode}).\n"
            f"Meldung des Programms:\n{rest}\n"
            f"Bis dahin: {geschaltet} Pin-Vorgang/Vorgaenge. "
            f"Das Programm darf so nicht auf den ESP32 — dort faende der Fehler genauso "
            f"statt, nur ohne diese Meldung. Erst den Quelltext berichtigen.")

    ausgabe = r.stdout or ""
    return _auswerten(name, ausgabe, gelaufen, durch_zeit, e)


def _abnehmen(erwartet, pins, einschaltzeiten, wechsel, form=None) -> str:
    """Vergleicht das Gemessene mit dem, was angekuendigt war.

    Ohne diesen Vergleich ist der Lauf nur eine Vorfuehrung: etwas blinkt, und niemand hat
    gesagt, was haette blinken sollen. Erst die vorher genannte Erwartung macht daraus eine
    Abnahme — und erst dann kann sie **nicht bestehen**, was der einzige Grund ist, eine
    Pruefung ueberhaupt durchzufuehren.

    Verglichen wird, was sich messen laesst: welche Anschluesse geschaltet wurden und wie
    schnell. Was das Programm sonst noch tun soll, steht hier nicht zur Debatte.
    """
    if not erwartet:
        return ("\nKeine Erwartung angegeben — damit ist dies eine Vorfuehrung, keine Abnahme. "
                "Mit \"erwartet\": {\"pins\": [2], \"takt_hz\": 1.0} wird daraus eine Pruefung, "
                "die auch durchfallen kann.")

    befunde, bestanden = [], True

    soll_pins = erwartet.get("pins")
    if soll_pins is not None:
        soll, ist = sorted(int(x) for x in soll_pins), sorted(pins)
        gut = soll == ist
        bestanden &= gut
        befunde.append(f"  Anschluesse: erwartet {soll}, gemessen {ist}  "
                       f"{'erfuellt' if gut else 'NICHT ERFUELLT'}")

    soll_hz = erwartet.get("takt_hz")
    if soll_hz is not None:
        if len(einschaltzeiten) < 2:
            bestanden = False
            befunde.append(f"  Takt: erwartet {float(soll_hz):.2f} Hz, aber es gab nur "
                           f"{len(einschaltzeiten)} Einschaltvorgang/Vorgaenge — "
                           f"NICHT PRUEFBAR, also nicht erfuellt")
        else:
            abst = [einschaltzeiten[i+1] - einschaltzeiten[i]
                    for i in range(len(einschaltzeiten)-1)]
            ist_hz = 1 / (sum(abst) / len(abst))
            # Zehn Prozent Spielraum: der Rechner ist kein Taktgeber, time.sleep haelt
            # seine Zeiten nur ungefaehr ein. Enger zu pruefen hiesse, Streuung als
            # Fehler zu melden.
            gut = abs(ist_hz - float(soll_hz)) <= 0.1 * float(soll_hz)
            bestanden &= gut
            befunde.append(f"  Takt: erwartet {float(soll_hz):.2f} Hz, gemessen {ist_hz:.2f} Hz "
                           f"(Spielraum 10 %)  {'erfuellt' if gut else 'NICHT ERFUELLT'}")

    #  „Dreieck ist kein Sinus" (05.10.2026): Verlangt der Mensch eine Form der Helligkeitskurve,
    #  wird sie gemessen und verglichen — sinusfoermig oder dreieckig, aus der PWM-Huellkurve.
    soll_form = erwartet.get("form")
    if soll_form:
        soll_form = "sinusfoermig" if "sin" in str(soll_form).lower() else "dreieckig" if "drei" in str(soll_form).lower() else str(soll_form)
        if form is None:
            bestanden = False
            befunde.append(f"  Form: erwartet {soll_form}, aber keine PWM-Huellkurve gemessen (Programm schaltet nur ein/aus) — NICHT ERFUELLT")
        else:
            gut = form == soll_form
            bestanden &= gut
            befunde.append(f"  Form: erwartet {soll_form}, gemessen {form}  {'erfuellt' if gut else 'NICHT ERFUELLT'}")

    soll_n = erwartet.get("mindestens_wechsel")
    if soll_n is not None:
        gut = len(wechsel) >= int(soll_n)
        bestanden &= gut
        befunde.append(f"  Zustandswechsel: erwartet mindestens {int(soll_n)}, "
                       f"gemessen {len(wechsel)}  {'erfuellt' if gut else 'NICHT ERFUELLT'}")

    if not befunde:
        return "\nDie Erwartung enthielt kein pruefbares Feld (pins, takt_hz, form, mindestens_wechsel)."

    kopf = "ABNAHME BESTANDEN" if bestanden else "ABNAHME NICHT BESTANDEN"
    schluss = ("" if bestanden else
               "\n  Das Programm darf so nicht auf den ESP32. Entweder stimmt der Quelltext "
               "nicht mit der Absicht ueberein, oder die Erwartung war falsch — beides gehoert "
               "geklaert, bevor es weitergeht.")
    return f"\n{kopf}\n" + "\n".join(befunde) + schluss


def _pwm_auswerten(ausgabe):
    """Huellkurve des Tastgrads je PWM-Pin: Periode (Takt), Tastgradbereich, Form.

    Gibt (Bericht, Pins, Einschaltzeiten = Perioden-Anfaenge, Wechsel fuer die Anzeige) zurueck.
    Die Periode wird an den aufsteigenden Durchgaengen durch die Mitte zwischen kleinstem und
    groesstem Tastgrad gemessen; die Form am Vergleich einer Periode mit Sinus-Halbwelle und
    Dreieck (mittlerer Fehler, 0 = deckungsgleich)."""
    import math
    proben = {}
    for z in ausgabe.splitlines():
        m = re.fullmatch(r"PWM (\d+) (\S+) ([\d.]+) ([\d.]+)", z.strip())
        if m:
            proben.setdefault(int(m.group(1)), []).append((float(m.group(4)), float(m.group(3)), m.group(2)))
    bericht, pins, an, wechsel = [], [], [], []
    form_gemessen = None
    for pin, liste in sorted(proben.items()):
        pins.append(pin)
        ts = [x[0] for x in liste]; ds = [x[1] for x in liste]
        lo, hi = min(ds), max(ds); traeger = liste[-1][2]
        if hi - lo < 0.1:
            bericht.append(f"\nPWM an Pin {pin}: Traeger {traeger} Hz, Tastgrad fest bei {hi*100:.0f} % — keine Huellkurve.")
            continue
        #  Durchgaenge mit Hysterese (30 %/70 % des Bereichs): Eine am Geraet gemessene Kurve rauscht,
        #  und ohne Hysterese zaehlte jedes Zittern um die Mitte als neue Periode (05.10.2026, 10:24:
        #  7,6 Hz statt 1 Hz am ESP32).
        unten, oben = lo + 0.3 * (hi - lo), lo + 0.7 * (hi - lo)
        mitte = (lo + hi) / 2
        auf, ab, zustand = [], [], (1 if ds[0] >= mitte else 0)
        for i in range(1, len(ds)):
            if zustand == 0 and ds[i] >= oben:
                zustand = 1; auf.append(ts[i])
            elif zustand == 1 and ds[i] <= unten:
                zustand = 0; ab.append(ts[i])
        an = auf if pin == pins[0] else an
        for t_ in auf: wechsel.append([pin, 1, t_])
        for t_ in ab: wechsel.append([pin, 0, t_])
        satz = f"\nPWM an Pin {pin}: Traeger {traeger} Hz, Tastgrad {lo*100:.0f} … {hi*100:.0f} % ({len(liste)} Proben)"
        if len(auf) >= 2:
            per = [auf[i+1] - auf[i] for i in range(len(auf)-1)]; T = sum(per) / len(per)
            satz += f", Huellkurve: Periode {T:.3f} s ({1/T:.2f} Hz), {len(auf)} Perioden"
            # Form: eine Periode ab dem ersten Minimum vor dem ersten Aufwaertsdurchgang
            #  Eine Periode ab dem tiefsten Punkt vor dem ersten Anstieg (gesucht in +-0,6 T um den
            #  Aufwaertsdurchgang; mit der 70-%-Schwelle liegt der Durchgang nicht in der Mitte).
            umfeld = [(x[0], x[1]) for x in liste if auf[0] - 0.6 * T <= x[0] <= auf[0] + 0.6 * T]
            tmin = min(umfeld, key=lambda x: x[1])[0] if umfeld else auf[0] - T / 4
            seg = [(x[0], x[1]) for x in liste if tmin <= x[0] < tmin + T]
            if len(seg) >= 8:
                f_sin = f_dreieck = 0.0
                for tt, dd in seg:
                    ph = ((tt - tmin) / T) % 1.0
                    norm = (dd - lo) / (hi - lo)
                    #  „sinusfoermig" fuer eine Helligkeit heisst: weich von 0 ueber 1 zurueck nach 0,
                    #  also (1 - cos(2 pi t/T)) / 2 — die positive Halbwelle ohne Knick an den Enden.
                    f_sin += abs(norm - (1 - math.cos(2 * math.pi * ph)) / 2)
                    f_dreieck += abs(norm - (2*ph if ph < 0.5 else 2 - 2*ph))
                f_sin /= len(seg); f_dreieck /= len(seg)
                form = "sinusfoermig" if f_sin < f_dreieck else "dreieckig"
                if form_gemessen is None:
                    form_gemessen = form
                satz += f"; Form: {form} (Abweichung Sinus {f_sin:.2f}, Dreieck {f_dreieck:.2f})"
        else:
            satz += ", Huellkurve: weniger als zwei Perioden in der Messzeit"
        bericht.append(satz + ".")
    wechsel.sort(key=lambda w: w[2])
    return "".join(bericht), pins, an, wechsel, form_gemessen


def _auswerten(name, ausgabe, gelaufen, durch_zeit, e):
    wechsel = []
    for z in ausgabe.splitlines():
        t = re.fullmatch(r"PIN (\d+) ([01]) ([\d.]+)", z.strip())
        if t:
            wechsel.append([int(t.group(1)), int(t.group(2)), float(t.group(3))])

    sonstiges = [z.strip() for z in ausgabe.splitlines()
                 if z.startswith(("PWM ", "ADC "))]
    #  PWM: nicht Ein/Aus, sondern Helligkeit. Am 05.10.2026 (9:44) fiel ein brauchbares Atem-
    #  programm (Tastgrad 0 → 100 % → 0 in einer Sekunde) durch, weil hier nur Pin-Schaltungen
    #  zaehlten. Jetzt wird die Huellkurve des Tastgrads gemessen: Periode, Takt, Form.
    pwm_bericht, pwm_pins, pwm_an, pwm_wechsel, pwm_form = _pwm_auswerten(ausgabe)
    if pwm_wechsel:
        #  PWM-Durchgaenge durch die Mitte zaehlen als Zustandswechsel — ein Atmen schaltet nicht,
        #  es schwillt; die Anzeige und die Zaehlung nehmen die Huellkurve.
        wechsel = sorted(wechsel + pwm_wechsel, key=lambda w: w[2])
    if not wechsel and not pwm_pins:
        if sonstiges:
            return (f"{name} lief {gelaufen:.1f} s ohne Hardware und hat keinen Pin geschaltet, "
                    f"aber {len(sonstiges)} andere Vorgaenge erzeugt:\n  "
                    + "\n  ".join(sonstiges[:10])
                    + "\nFuer eine Anzeige wird ein geschalteter Pin gebraucht.")
        rest = "\n".join(ausgabe.splitlines()[-6:])
        raise Abbruch(f"{name} hat keinen Pin geschaltet. Ausgabe des Programms:\n{rest}\n"
                      f"Erwartet wird ein Pin mit Pin.OUT und Aufrufen von value(), on() oder off().")

    pins = sorted({w[0] for w in wechsel} | set(pwm_pins))
    an = [w[2] for w in wechsel if w[1] == 1]
    if pwm_an and len(pwm_pins) == 1 and not [w for w in wechsel if w not in pwm_wechsel and w[1] == 1]:
        an = pwm_an                     # bei reinem PWM zaehlt die Huellkurve als Takt
    takt = pwm_bericht
    # Nur bei einem einzigen Pin ist ein "Takt" eine sinnvolle Zahl. Bei mehreren waere es
    # der Mittelwert ueber verschiedene Leitungen — eine Zahl, die nichts bedeutet.
    if len(pins) == 1 and len(an) >= 2 and not pwm_bericht:
        abstaende = [an[i+1] - an[i] for i in range(len(an)-1)]
        mittel = sum(abstaende) / len(abstaende)
        takt = f"\nTakt: {mittel:.3f} s zwischen zwei Einschaltvorgaengen ({1/mittel:.2f} Hz)."

    abnahme = _abnehmen(e.get("erwartet"), pins, an, wechsel, form=pwm_form)

    ziel = in_der_ablage("virtuelle_led.html")
    ziel.write_text(_html(name, wechsel, gelaufen), encoding="utf-8")
    geoeffnet = ""
    if e.get("oeffnen", True):
        try:
            webbrowser.open(ziel.as_uri())
            geoeffnet = " und im Browser geoeffnet"
        except Exception:
            geoeffnet = " (der Browser liess sich nicht oeffnen — Datei von Hand aufrufen)"

    kopf = "\n".join(
        f"  {w[2]:6.3f} s   Pin {w[0]:<3d} {'●  an ' if w[1] else '○  aus'}" for w in wechsel[:12])
    mehr = f"\n  … und {len(wechsel)-12} weitere Wechsel" if len(wechsel) > 12 else ""

    extra = (f"\nAusserdem: {len(sonstiges)} PWM-/ADC-Vorgang/Vorgaenge, zum Beispiel "
             f"{sonstiges[0]}" if sonstiges else "")
    return (f"{name} lief {gelaufen:.1f} s ohne Hardware"
            + (" (nach der Zeitgrenze beendet — ein Blinkprogramm endet nicht von selbst)"
               if durch_zeit else " (von selbst beendet)")
            + f".\nGeschaltet wurde Pin {', '.join(map(str, pins))}, "
              f"{len(wechsel)} Zustandswechsel.{takt}{extra}\n{kopf}{mehr}\n"
              f"{abnahme}\nAufzeichnung: {ziel}{geoeffnet}.\n"
              f"Es war derselbe Quelltext wie fuer den ESP32 — nur das machine-Modul war "
              f"nachgebaut. Zum echten Blinken: esp32_firmware, dann esp32_uebertragen.")


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "programm_testen",
        "Fuehrt ein Programm aus der Werkstatt ohne Hardware aus und zeichnet auf, was an den "
        "Anschluessen geschieht; eine LED auf dem Bildschirm zeigt es an. IMMER aufrufen, "
        "nachdem ein Programm geschrieben wurde und BEVOR es auf den ESP32 ueberspielt wird — "
        "ein Programm, das hier nicht laeuft, laeuft dort auch nicht. Ersetzt zugleich die "
        "Hardware, wenn keine da ist.",
        {"datei":    {"type": "string", "description": "Dateiname in der Werkstatt, Vorgabe blink.py"},
         "sekunden": {"type": "number", "description": "wie lange laufen lassen, 1 bis 60, Vorgabe 6"},
         "oeffnen":  {"type": "boolean", "description": "Seite im Browser oeffnen, Vorgabe true"},
         "erwartet": {"type": "object", "description":
                      "Was herauskommen soll — daran wird gemessen. Felder: pins (Liste der "
                      "Anschlussnummern), form (sinusfoermig oder dreieckig, fuer PWM-Atmen), takt_hz (Einschaltvorgaenge je Sekunde, 10 % "
                      "Spielraum), mindestens_wechsel (Anzahl). Immer angeben: ohne "
                      "Erwartung ist der Lauf nur eine Vorfuehrung und kann nicht durchfallen."}},
        [], {"datei": "blink.py", "sekunden": 4, "oeffnen": False,
             "erwartet": {"pins": [2], "takt_hz": 1.0}}, tun))
