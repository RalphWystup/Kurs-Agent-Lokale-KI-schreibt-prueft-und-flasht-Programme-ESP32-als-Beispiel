#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Die Simulation im Fenster: die LED leuchtet mit, während das Programm im Nachbau läuft.

    python simulation_fenster.py <spurdatei> <programmname>

Anweisung des Auftraggebers vom 10.10.2026: „Es wird die Möglichkeit geschaffen, die erzeugten
Programme auch zu simulieren, indem ein Fenster dazu aufgeht."

Was hier zu sehen ist
---------------------
Das Programm läuft nicht auf einem Brett, sondern im **Nachbau**: `programm_testen` ersetzt
`machine` durch eine Nachbildung, die jeden Schaltvorgang und jeden PWM-Tastgrad mit Zeitstempel
aufschreibt. Diese Spur zeigt das Fenster ab — in Echtzeit, so wie es auf dem Brett aussähe.

  * **Blinken** — die LED geht an und aus, der Takt steht darunter.
  * **Atmen** — die LED wird gedimmt; die Helligkeit ist der gemessene Tastgrad.

Das Fenster bleibt offen, bis jemand es schließt, und spielt auf Wunsch noch einmal ab.
Es urteilt nicht: Ob der Takt stimmt, sagt die Abnahme in `programm_testen`.
"""
import json
import pathlib
import sys
import time


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    spur_datei = pathlib.Path(sys.argv[1])
    name = sys.argv[2] if len(sys.argv) > 2 else spur_datei.stem

    try:
        d = json.loads(spur_datei.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Spur nicht lesbar: {e}")
        return 1
    wechsel = d.get("wechsel") or []          # [[pin, wert, zeit], ...]
    pwm = d.get("pwm") or {}                  # {"2": [[zeit, tastgrad], ...]}
    dauer = float(d.get("dauer") or 6.0)
    takt = d.get("takt") or ""

    try:
        import tkinter as tk
    except ImportError:
        print("tkinter fehlt — die Simulation laeuft trotzdem, nur ohne Fenster.")
        print("Einrichten mit: python pruefe_bereit.py --einrichten")
        return 1

    w = tk.Tk()
    w.title(f"Simulation — {name}")
    w.geometry("560x560")
    w.configure(bg="#1a202c")

    tk.Label(w, text="Simulation ohne Hardware", bg="#1a202c", fg="#e2e8f0",
             font=("Segoe UI", 13, "bold")).pack(pady=(16, 2))
    tk.Label(w, text=f"{name} — {dauer:.1f} s im Nachbau aufgezeichnet",
             bg="#1a202c", fg="#a0aec0", font=("Segoe UI", 9)).pack()

    brett = tk.Frame(w, bg="#2d3748", highlightbackground="#4a5568", highlightthickness=1)
    brett.pack(pady=22, padx=40, fill="x")
    leinwand = tk.Canvas(brett, width=200, height=200, bg="#2d3748", highlightthickness=0)
    leinwand.pack(pady=18)
    #  Die LED: ein Kreis, dessen Farbe die Helligkeit zeigt.
    led = leinwand.create_oval(55, 55, 145, 145, fill="#4a5568", outline="#718096", width=3)
    pin_text = tk.Label(brett, text="Pin —", bg="#2d3748", fg="#a0aec0", font=("Consolas", 10))
    pin_text.pack()
    uhr = tk.Label(brett, text="0.000 s", bg="#2d3748", fg="#63b3ed", font=("Consolas", 12))
    uhr.pack(pady=(4, 18))

    tk.Label(w, text=takt or "", bg="#1a202c", fg="#90cdf4",
             font=("Consolas", 10)).pack()

    zustand = {"laeuft": False, "t0": 0.0}

    def farbe(h: float) -> str:
        """Von dunkelgrau (aus) nach rot (voll) — h zwischen 0 und 1."""
        h = max(0.0, min(1.0, h))
        r = int(0x4a + (0xf5 - 0x4a) * h)
        g = int(0x55 + (0x65 - 0x55) * h)
        b = int(0x68 + (0x65 - 0x68) * h)
        return f"#{r:02x}{g:02x}{b:02x}"

    pins = sorted(pwm) or sorted({str(x[0]) for x in wechsel})
    spur = pwm.get(pins[0]) if pins and pwm else None

    def schritt():
        if not zustand["laeuft"]:
            return
        t = time.time() - zustand["t0"]
        if t > dauer + 0.3:
            zustand["laeuft"] = False
            uhr.config(text=f"{dauer:.3f} s — zu Ende")
            return
        if spur:
            i = 0
            while i + 1 < len(spur) and spur[i + 1][0] <= t:
                i += 1
            h = float(spur[i][1])
            leinwand.itemconfig(led, fill=farbe(h))
            pin_text.config(text=f"Pin {pins[0]} (PWM)")
            uhr.config(text=f"{t:.3f} s    Tastgrad {h*100:.0f} %")
        else:
            an, pin = 0, "—"
            for p, wert, zeit in wechsel:
                if zeit <= t:
                    an, pin = wert, p
                else:
                    break
            leinwand.itemconfig(led, fill=farbe(1.0 if an else 0.0))
            pin_text.config(text=f"Pin {pin}")
            uhr.config(text=f"{t:.3f} s    {'an' if an else 'aus'}")
        w.after(16, schritt)

    def start():
        zustand["t0"] = time.time()
        zustand["laeuft"] = True
        schritt()

    tk.Button(w, text="noch einmal abspielen", command=start, bg="#2d3748", fg="#e2e8f0",
              activebackground="#4a5568", activeforeground="#e2e8f0", relief="flat",
              font=("Segoe UI", 10), padx=16, pady=7).pack(pady=14)
    tk.Label(w, text="Das Fenster bleibt offen, bis Sie es schliessen.\n"
                     "Ob der Takt stimmt, sagt die Abnahme — nicht das Bild.",
             bg="#1a202c", fg="#a0aec0", font=("Segoe UI", 9), justify="center").pack(pady=(0, 12))

    start()
    w.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
