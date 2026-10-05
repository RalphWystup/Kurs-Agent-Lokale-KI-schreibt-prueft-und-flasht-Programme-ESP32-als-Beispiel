#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Liest vom ESP32 zurueck, ob die LED wirklich blinkt — gemessen auf dem Geraet selbst.

Bis zum 04.10.2026 endete die Kette mit „Geraet neu gestartet. MicroPython fuehrt main.py
aus." Ob danach etwas blinkte, wusste nur, wer danebenstand. Anweisung des Auftraggebers:
„lies einfach zurueck, ob die LED blinkt." Das tut dieses Werkzeug: Es laesst das Programm
auf dem Geraet in einem Nebenlauf starten und zeichnet im Hauptlauf die Pegel der genannten
Anschluesse auf - per Flankeninterrupt mit Mikrosekunden-Zeitstempel vom Zaehler des Geraets
(Auftraggeber 04.10.2026: die Quarzfrequenz ist doch bekannt) -, einige Sekunden lang. Daraus werden Takt und
Zustandswechsel bestimmt und wie bei programm_testen gegen die Erwartung gehalten.

Das ist der zweite, unabhaengige Weg (Grundsatz 1): programm_testen misst den Nachbau auf dem
Rechner, dieses Werkzeug misst das Geraet. Stimmen beide, ist das Programm abgenommen.

Danach wird das Geraet neu gestartet, damit main.py wieder wie gewohnt laeuft.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, lauf, python_exe
from programm_testen import _abnehmen
import re

# Laeuft auf dem Geraet. {DATEI}, {PINS}, {MS} werden eingesetzt. Kein f-String, damit die
# geschweiften Klammern von MicroPython-Code nicht mit Platzhaltern verwechselt werden.
MESSPROGRAMM = """
import machine, time, _thread
_src = open('{DATEI}').read()
def _lauf():
    try:
        exec(_src, {})
    except Exception as e:
        print('PROGRAMMFEHLER', repr(e))
_thread.start_new_thread(_lauf, ())
time.sleep_ms(200)
_pins = {PINS}
_w = []
_t0 = time.ticks_us()
def _mach(n):
    def _h(p):
        if len(_w) < 2000:
            _w.append((time.ticks_diff(time.ticks_us(), _t0), n, p.value()))
    return _h
_p = {}
for n in _pins:
    _p[n] = machine.Pin(n)
    _w.append((0, n, _p[n].value()))
    _p[n].irq(handler=_mach(n), trigger=machine.Pin.IRQ_RISING | machine.Pin.IRQ_FALLING)
time.sleep_ms({MS})
for n in _pins:
    _p[n].irq(handler=None)
for t, n, v in _w:
    print('W', t, n, v)
print('ENDE', time.ticks_diff(time.ticks_us(), _t0))
"""


# PWM: Flanken kommen tausendmal je Sekunde, sie sagen nichts ueber das Atmen. Gemessen wird
# der Tastgrad direkt aus dem PWM-Kanal des Pins (machine.PWM(pin).duty_u16() findet den
# vorhandenen Kanal) alle 10 ms aus einem Zeitgeber-Interrupt; der Hauptlauf schlaeft derweil.
# Eine Messschleife im Hauptlauf bremste das Programm um das Vierfache (05.10.2026, 10:30:
# 7 s je Atemzug gemessen, 1,8 s vom Menschen gezaehlt — 11 in 20 s); Pulsdauern noch mehr. Die Zeilen
# heissen wie dort ("PWM <pin> <f> <duty> <t>"), damit dieselbe Auswertung Periode und Form liefert.
MESSPROGRAMM_PWM = """
import machine, time, _thread
_src = open('{DATEI}').read()
def _lauf():
    try:
        exec(_src, {})
    except Exception as e:
        print('PROGRAMMFEHLER', repr(e))
_thread.start_new_thread(_lauf, ())
time.sleep_ms(300)
_pins = {PINS}
_q = {}
for n in _pins:
    try:
        _q[n] = machine.PWM(machine.Pin(n))
    except Exception as e:
        print('KEINPWM', n, repr(e))
_t0 = time.ticks_us()
_z = []
def _probe(tm):
    t = time.ticks_diff(time.ticks_us(), _t0)
    for n in _q:
        _z.append((n, _q[n].freq(), _q[n].duty_u16(), t))
_tm = machine.Timer(-1)
_tm.init(period=10, mode=machine.Timer.PERIODIC, callback=_probe)
time.sleep_ms({MS})
_tm.deinit()
for n, f, d, t in _z:
    print('PWM', n, int(f), '%.4f' % (d / 65535), '%.3f' % (t / 1e6))
print('ENDE')
"""


def _mpremote(port, *args, zeit=180):
    return lauf([str(python_exe()), "-m", "mpremote", "connect", port, *args], zeit)


def tun(e):
    port = str(e["port"]).strip()
    if not re.fullmatch(r"(COM\d+|/dev/[A-Za-z0-9._/-]+)", port):
        raise Abbruch(f"'{port}' sieht nicht wie ein Anschluss aus.")
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")
    datei = str(e.get("datei", "main.py")).strip() or "main.py"
    if "/" in datei or "\\" in datei or "'" in datei:
        raise Abbruch("Der Dateiname auf dem Geraet darf keinen Pfad enthalten.")
    sekunden = float(e.get("sekunden", 6))
    if not 1 <= sekunden <= 60:
        raise Abbruch("sekunden muss zwischen 1 und 60 liegen.")
    erwartet = e.get("erwartet") or None
    pins = e.get("pins") or (erwartet or {}).get("pins") or [2]
    pins = sorted({int(p) for p in pins})
    if any(not 0 <= p <= 48 for p in pins):
        raise Abbruch("Anschlussnummern muessen zwischen 0 und 48 liegen.")

    pwm = bool(e.get("pwm")) or bool((erwartet or {}).get("form"))
    vorlage = MESSPROGRAMM_PWM if pwm else MESSPROGRAMM
    programm = (vorlage.replace("{DATEI}", datei).replace("{PINS}", repr(pins))
                .replace("{MS}", str(int(sekunden * 1000))))
    r = _mpremote(port, "exec", programm, zeit=int(sekunden) + 90)
    text = (r.stdout or "") + (r.stderr or "")
    if "ModuleNotFoundError" in text or "No module named" in text:
        raise Abbruch("mpremote fehlt. Erst paket_installieren mit mpremote aufrufen.")
    if r.returncode != 0 and "ENDE" not in text:
        raise Abbruch(f"Das Messprogramm lief nicht auf {port}: {text[-500:]}\n"
                      f"Laeuft MicroPython auf dem Geraet (esp32_firmware)? Haelt ein anderes "
                      f"Programm den Anschluss?")
    if "PROGRAMMFEHLER" in text:
        z = [l for l in text.splitlines() if "PROGRAMMFEHLER" in l][0]
        raise Abbruch(f"{datei} bricht auf dem Geraet ab: {z.split('PROGRAMMFEHLER', 1)[1].strip()}")
    if "ENOENT" in text or "OSError" in text and "ENDE" not in text:
        raise Abbruch(f"{datei} liegt nicht auf dem Geraet: {text[-300:]}")

    if pwm:
        from programm_testen import _pwm_auswerten
        bericht, pwm_pins, pwm_an, pwm_wechsel, form = _pwm_auswerten(text)
        zeilen = [f"Gemessen auf dem Geraet an {port}, {sekunden:.0f} s, Anschluesse {pins}, Programm {datei} — "
                  f"Tastgrad aus dem PWM-Kanal (alle 10 ms):"]
        zeilen.append(bericht.strip() if bericht.strip() else "  Kein PWM-Signal gemessen.")
        zeilen.append(_abnehmen(erwartet, pwm_pins or pins, pwm_an, pwm_wechsel, form=form))
        if e.get("roh"):
            roh = [z for z in text.splitlines() if z.startswith("PWM ")]
            schritt = max(1, len(roh) // 60)
            zeilen.append("Rohwerte (jede %d. Probe: Pin Traeger Tastgrad Zeit):" % schritt)
            zeilen += ["  " + z for z in roh[::schritt][:60]]
        _mpremote(port, "reset", zeit=60)
        zeilen.append("Geraet neu gestartet; main.py laeuft wieder von selbst.")
        return "\n".join(zeilen)
    wechsel, einschalt = [], {}
    for m in re.finditer(r"^W (\d+) (\d+) (\d)$", text, re.M):
        t_us, pin, v = int(m.group(1)), int(m.group(2)), int(m.group(3))
        wechsel.append([pin, v, t_us / 1e6])
        if v == 1 and t_us > 0:
            einschalt.setdefault(pin, []).append(t_us / 1e6)
    # Der erste Eintrag je Anschluss ist der Anfangspegel, kein Wechsel.
    geschaltet = sorted({w[0] for w in wechsel if sum(1 for x in wechsel if x[0] == w[0]) > 1})
    # Fuer die Abnahme zaehlt der Takt des ersten erwarteten Anschlusses (wie bei programm_testen).
    leitpin = (sorted(int(p) for p in (erwartet or {}).get("pins", [])) or geschaltet or pins)[0]
    an = einschalt.get(leitpin, [])

    zeilen = [f"Gemessen auf dem Geraet an {port}, {sekunden:.0f} s, Anschluesse {pins}, Programm {datei}:"]
    if not geschaltet:
        zeilen.append("  Kein Anschluss hat den Pegel gewechselt — nichts blinkt.")
    else:
        zeilen.append(f"  Geschaltet wurde: {geschaltet}, {len(wechsel) - len(pins)} Zustandswechsel.")
        if len(an) >= 2:
            abst = [an[i + 1] - an[i] for i in range(len(an) - 1)]
            zeilen.append(f"  Takt an Pin {leitpin}: {sum(abst) / len(abst):.4f} s zwischen zwei "
                          f"Einschaltvorgaengen ({1 / (sum(abst) / len(abst)):.3f} Hz) - Flanken per Interrupt, "
                          f"Zeit vom Mikrosekundenzaehler des Geraets.")
    for pin, v, t in wechsel[:40]:
        zeilen.append(f"  {t:9.4f} s   Pin {pin}   {'●  an ' if v else '○  aus'}")
    if len(wechsel) > 40:
        zeilen.append(f"  … {len(wechsel) - 40} weitere")
    zeilen.append(_abnehmen(erwartet, geschaltet, an, wechsel))

    _mpremote(port, "reset", zeit=60)
    zeilen.append("Geraet neu gestartet; main.py laeuft wieder von selbst.")
    return "\n".join(zeilen)


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "esp32_nachlesen",
        "Liest vom ESP32 zurueck, ob die LED wirklich blinkt: startet das Programm auf dem Geraet "
        "und zeichnet dort die Pegel der Anschluesse auf. Takt und Wechsel werden gegen die Erwartung "
        "gehalten (ABNAHME) — die Messung am Geraet, unabhaengig von programm_testen. Setzt voraus, "
        "dass esp32_uebertragen gelaufen ist.",
        {"port":     {"type": "string", "description": "der Anschluss, zum Beispiel COM3"},
         "datei":    {"type": "string", "description": "Programm auf dem Geraet, Vorgabe main.py"},
         "sekunden": {"type": "number", "description": "Messdauer, Vorgabe 6"},
         "pwm":      {"type": "boolean", "description": "true fuer PWM-Programme (Atmen): misst den Tastgrad statt der Flanken; mit erwartet.form automatisch"},
         "roh":      {"type": "boolean", "description": "Rohwerte der Tastgradmessung mit ausgeben (zur Fehlersuche)"},
         "erwartet": {"type": "object", "description": "wie bei programm_testen: pins, takt_hz, form"}},
        ["port"], {"port": "COM3", "sekunden": 4, "erwartet": {"pins": [2], "takt_hz": 1.0}}, tun))
