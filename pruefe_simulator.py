#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruefstand des Simulators (programm_testen) — durch die Tuer, mit Programmen feststehenden Ergebnisses.

Der Simulator wird nicht importiert und nicht ausgeschnitten: Er bekommt wie im Betrieb eine
Datei in der Werkstatt und eine Erwartung, und sein Text wird gelesen. Die Programme sind so
gebaut, dass ihr Ergebnis mathematisch feststeht — trifft der Simulator es nicht, irrt er.

Anlass 16.10.2026 (in seinem Test gefunden): duty_u16(33554880) wurde gekappt statt wie auf dem
Brett ValueError zu werfen — der Simulator liess ein Programm durch, das auf dem ESP32 starb.
Dieser Fall steht hier als K5.8. Gebot 1: messen, nicht annehmen.

    python pruefe_simulator.py
"""
import json
import pathlib
import re
import subprocess
import sys

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER / "agent"))
from pfade import python_exe, umgebung, WERKSTATT   # noqa: E402

WERKZEUGE = HIER / "agent" / "werkzeuge"
KOPF = "import machine\nimport time\nimport math\n"
BEFUNDE = []

PROGRAMME = {
    #  Name: (Quelltext, erwartet, was im Text stehen muss, was nicht)
    "k5_sinus_mitte.py": (
        KOPF + "led = machine.PWM(machine.Pin(2), freq=1000)\n"
        "t0 = time.time()\nwhile True:\n    t = (time.time() - t0) % 2\n"
        "    led.duty(int(511 * (1 + math.sin(2 * math.pi * t / 2))))\n    time.sleep(0.01)\n",
        {"pins": [2], "takt_hz": 0.5, "form": "sinusfoermig"}, "ABNAHME BESTANDEN", "dreieckig"),
    "k5_kosinus.py": (
        KOPF + "led = machine.PWM(machine.Pin(2), freq=1000)\n"
        "t0 = time.time()\nwhile True:\n    t = (time.time() - t0) % 2\n"
        "    led.duty(int(511 * (1 - math.cos(2 * math.pi * t / 2))))\n    time.sleep(0.01)\n",
        {"pins": [2], "takt_hz": 0.5, "form": "sinusfoermig"}, "ABNAHME BESTANDEN", "dreieckig"),
    "k5_dreieck.py": (
        KOPF + "led = machine.PWM(machine.Pin(2), freq=1000)\n"
        "while True:\n    for d in range(0, 1024, 11):\n        led.duty(d)\n        time.sleep(0.01)\n"
        "    for d in range(1023, -1, -11):\n        led.duty(d)\n        time.sleep(0.01)\n",
        {"pins": [2], "takt_hz": 0.5, "form": "sinusfoermig"},
        "Form: erwartet sinusfoermig, gemessen dreieckig", "ABNAHME BESTANDEN"),
    "k5_dreieck_erwartet.py": (
        KOPF + "led = machine.PWM(machine.Pin(2), freq=1000)\n"
        "while True:\n    for d in range(0, 1024, 11):\n        led.duty(d)\n        time.sleep(0.01)\n"
        "    for d in range(1023, -1, -11):\n        led.duty(d)\n        time.sleep(0.01)\n",
        {"pins": [2], "takt_hz": 0.5, "form": "dreieckig"}, "ABNAHME BESTANDEN", "NICHT ERFUELLT"),
    "k5_zwei_1hz.py": (
        KOPF + "a = machine.Pin(2, machine.Pin.OUT)\nb = machine.Pin(4, machine.Pin.OUT)\n"
        "while True:\n    a.value(1); b.value(0); time.sleep(0.5)\n    a.value(0); b.value(1); time.sleep(0.5)\n",
        {"pins": [2, 4], "takt_hz": 2.0}, "Takt: erwartet 2.00 Hz, gemessen 1.00 Hz", "ABNAHME BESTANDEN"),
    "k5_zwei_1hz_richtig.py": (
        KOPF + "a = machine.Pin(2, machine.Pin.OUT)\nb = machine.Pin(4, machine.Pin.OUT)\n"
        "while True:\n    a.value(1); b.value(0); time.sleep(0.5)\n    a.value(0); b.value(1); time.sleep(0.5)\n",
        {"pins": [2, 4], "takt_hz": 1.0}, "ABNAHME BESTANDEN", "NICHT ERFUELLT"),
    "k5_blink_halb.py": (
        KOPF + "led = machine.Pin(2, machine.Pin.OUT)\nwhile True:\n"
        "    led.value(1); time.sleep(1)\n    led.value(0); time.sleep(1)\n",
        {"pins": [2], "takt_hz": 1.0}, "Takt: erwartet 1.00 Hz, gemessen 0.50 Hz", "ABNAHME BESTANDEN"),
    "k5_an1_aus2.py": (
        KOPF + "led = machine.Pin(2, machine.Pin.OUT)\nwhile True:\n"
        "    led.value(1); time.sleep(1)\n    led.value(0); time.sleep(2)\n",
        {"pins": [2], "an_s": 1.0, "aus_s": 2.0}, "Aus-Dauer an Pin 2: erwartet 2.00 s, gemessen 2.00 s", "NICHT ERFUELLT"),
    "k5_an1_aus1_falsch.py": (
        KOPF + "led = machine.Pin(2, machine.Pin.OUT)\nwhile True:\n"
        "    led.value(1); time.sleep(1)\n    led.value(0); time.sleep(1)\n",
        {"pins": [2], "an_s": 1.0, "aus_s": 2.0}, "Aus-Dauer an Pin 2: erwartet 2.00 s, gemessen 1.00 s", "ABNAHME BESTANDEN"),
    "k5_duty_zu_gross.py": (
        KOPF + "pwm = machine.PWM(machine.Pin(2), freq=1000)\n"
        "def hell(b):\n    pwm.duty_u16(int(b * 65535))\n"
        "while True:\n    for b in range(0, 65535, 512):\n        hell(b)\n        time.sleep_ms(10)\n",
        {"pins": [2], "takt_hz": 0.5, "form": "dreieckig"},
        "ValueError: duty_u16 must be between 0 and 65535", "ABNAHME BESTANDEN"),
}


def werkzeug(name, eingabe, zeit=120):
    r = subprocess.run([str(python_exe()), str(WERKZEUGE / f"{name}.py"), json.dumps(eingabe, ensure_ascii=False)],
                       capture_output=True, text=True, timeout=zeit, env=umgebung(),
                       encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    WERKSTATT.mkdir(parents=True, exist_ok=True)
    for i, (name, (quelle, erwartet, muss, darf_nicht)) in enumerate(PROGRAMME.items(), 1):
        (WERKSTATT / name).write_text(quelle, encoding="utf-8")
        aus = werkzeug("programm_testen", {"datei": name, "erwartet": erwartet, "oeffnen": False, "fenster": False, "sekunden": 6})   # Pruefmittel oeffnet kein Fenster
        ok = (muss in aus) and (darf_nicht not in aus)
        form = re.search(r"Form: \w+ \(Abweichung Sinus [\d.]+, Dreieck [\d.]+\)", aus)
        takt = re.search(r"Takt: erwartet [^\n]*", aus)
        fehler = re.search(r"ValueError[^\n]*", aus)
        beleg = " ".join(x.group(0) for x in (form, takt, fehler) if x)
        BEFUNDE.append((f"K5.{i}", f"{name}: muss '{muss[:50]}'", ok, beleg[:150] or aus.strip().splitlines()[-1][:150]))
        try:
            (WERKSTATT / name).unlink()
        except OSError:
            pass
    print("=" * 78)
    print("PRUEFSTAND SIMULATOR — Programme mit feststehendem Ergebnis")
    print("=" * 78)
    gut = 0
    for nr, was, ok, beleg in BEFUNDE:
        print(f"  {nr:5s} {'ERFUELLT      ' if ok else 'NICHT ERFUELLT'}  {was}\n        {beleg}")
        gut += ok
    print("-" * 78)
    print(f"{gut} von {len(BEFUNDE)} erfuellt")
    print("SIMULATOR BESTANDEN" if gut == len(BEFUNDE) else "SIMULATOR NICHT BESTANDEN")
    return 0 if gut == len(BEFUNDE) else 1


if __name__ == "__main__":
    sys.exit(main())
