"""Prueft programm_testen mit PWM-Programmen (05.10.2026): Dreieck-Atmen, Sinus-Atmen, fester Tastgrad.
Die Huellkurve muss gemessen, der Takt gegen die Erwartung gehalten und die Form erkannt werden."""
import os, sys, pathlib, subprocess, json, shutil
hier = pathlib.Path(__file__).resolve().parent
os.environ["KURS_AGENT_WURZEL"] = str(hier)
w = hier / "ablage" / "werkstatt"; w.mkdir(parents=True, exist_ok=True)
# 50 Stufen je Halbperiode, Pause 9,2 ms + 0,8 ms gedachte Rechenzeit = 10 ms -> 1,0 s je Periode
(w / "atmen_dreieck.py").write_text("from machine import Pin, PWM\nimport time\nled = PWM(Pin(2), freq=1000)\nwhile True:\n    for d in range(0, 1024, 21):\n        led.duty(d); time.sleep(0.0092)\n    for d in range(1023, -1, -21):\n        led.duty(d); time.sleep(0.0092)\n")
(w / "atmen_sinus.py").write_text("from machine import Pin, PWM\nimport time, math\nled = PWM(Pin(2), freq=1000)\ni = 0\nwhile True:\n    led.duty(int(1023 * (0.5 - 0.5 * math.cos(2 * math.pi * i / 100))))\n    i += 1\n    time.sleep(0.01)\n")
(w / "pwm_fest.py").write_text("from machine import Pin, PWM\nimport time\nled = PWM(Pin(2), freq=1000, duty=512)\nwhile True:\n    time.sleep(0.1)\n")
def lauf(datei, erw):
    r = subprocess.run([sys.executable, str(hier.parent / "agent/werkzeuge/programm_testen.py"), json.dumps({"datei": datei, "sekunden": 4, "oeffnen": False, "erwartet": erw})], capture_output=True, text=True, timeout=120)
    return r.stdout
f = []
def pr(b, ok, info=""): print(f"  {'OK  ' if ok else 'FEHL'} {b} {info}"); f.append(ok)
a = lauf("atmen_dreieck.py", {"pins": [2], "takt_hz": 1.0}); z = [l for l in a.splitlines() if "PWM an Pin" in l]
pr("Dreieck-Atmen 1 Hz: Huellkurve gemessen, ABNAHME BESTANDEN, Form dreieckig", "ABNAHME BESTANDEN" in a and z and "dreieckig" in z[0], z[0][:160] if z else a[:200])
b = lauf("atmen_sinus.py", {"pins": [2], "takt_hz": 1.0}); z = [l for l in b.splitlines() if "PWM an Pin" in l]
pr("Sinus-Atmen 1 Hz: BESTANDEN, Form sinusfoermig", "ABNAHME BESTANDEN" in b and z and "sinusfoermig" in z[0], z[0][:160] if z else b[:200])
c = lauf("atmen_sinus.py", {"pins": [2], "takt_hz": 3.0}); pr("Sinus-Atmen gegen 3 Hz: NICHT BESTANDEN (Gegenprobe)", "ABNAHME NICHT BESTANDEN" in c)
d = lauf("pwm_fest.py", {"pins": [2], "takt_hz": 1.0}); pr("fester Tastgrad: keine Huellkurve, Takt nicht pruefbar -> NICHT BESTANDEN", "keine Huellkurve" in d and "NICHT BESTANDEN" in d, [l for l in d.splitlines() if "PWM an Pin" in l][:1])
e = lauf("atmen_dreieck.py", {"pins": [2], "takt_hz": 1.0, "form": "sinusfoermig"}); pr("Dreieck gegen Erwartung sinusfoermig: NICHT BESTANDEN (Dreieck ist kein Sinus)", "ABNAHME NICHT BESTANDEN" in e and "Form: erwartet sinusfoermig, gemessen dreieckig  NICHT ERFUELLT" in e)
g = lauf("atmen_sinus.py", {"pins": [2], "takt_hz": 1.0, "form": "sinusfoermig"}); pr("Sinus gegen Erwartung sinusfoermig: BESTANDEN", "ABNAHME BESTANDEN" in g and "Form: erwartet sinusfoermig, gemessen sinusfoermig  erfuellt" in g)
h = lauf("atmen_sinus.py", {"pins": [2], "takt_hz": 1.0, "form": "sinusfoermig", "mindestens_wechsel": 6}); pr("Sinus mit mindestens 6 Wechseln: PWM-Durchgaenge zaehlen, BESTANDEN", "ABNAHME BESTANDEN" in h, [l for l in h.splitlines() if "Zustandswechsel" in l][:1])
print(f"\n  {sum(f)} von {len(f)}"); sys.exit(0 if all(f) else 1)
