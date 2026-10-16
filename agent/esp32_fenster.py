#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Das Fenster zum Laden: zeigt jeden Schritt und danach die serielle Leitung — bis es zugeht.

    python esp32_fenster.py <mitschnittdatei> <port>

Anweisung des Auftraggebers vom 10.10.2026: „Das Werkzeug wird dann mit Fenster aufgerufen und
der Download und das Debuggen über seriell angezeigt, bis der User das Fenster schließt."

Wie die Arbeit geteilt ist
--------------------------
Zwei Programme können nicht gleichzeitig dieselbe serielle Leitung halten. Deshalb:

  * `esp32_laden` lädt und schreibt dabei jede Zeile in die Mitschnittdatei.
  * Dieses Fenster zeigt die Datei laufend an — so ist das Herunterladen zu sehen, während
    es geschieht.
  * Wenn `esp32_laden` fertig ist und die Leitung freigibt (erkennbar an der Schlusszeile
    in der Datei), übernimmt das Fenster und liest selbst weiter mit. Dann sieht man, was
    das Programm auf dem Brett ausgibt — so lange, bis jemand das Fenster schließt.

Das Fenster urteilt nicht. Es zeigt.
"""
import pathlib
import sys
import threading
import time

ENDE = "### LEITUNG FREI ###"
#  Wer die Leitung gerade braucht, schreibt "belegt" in diese Datei. Das Fenster sieht es
#  im Lesetakt und gibt die Leitung frei — sonst kann nach einem Laden nie wieder geladen
#  werden, solange das Fenster offen ist (10.10.2026 gemessen: PermissionError auf COM3).
MARKE = "esp32_leitung.txt"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    datei = pathlib.Path(sys.argv[1])
    port = sys.argv[2]

    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except ImportError:
        print("tkinter fehlt. Ohne Fenster laeuft das Laden trotzdem; der Mitschnitt steht in")
        print(f"  {datei}")
        return 1

    w = tk.Tk()
    w.title(f"ESP32 an {port} — Laden und Mitlesen")
    w.geometry("900x620")
    w.configure(bg="#1a202c")

    kopf = tk.Label(w, text=f"ESP32 an {port}", bg="#1a202c", fg="#e2e8f0",
                    font=("Segoe UI", 13, "bold"))
    kopf.pack(pady=(12, 2))
    stand = tk.Label(w, text="warte auf den ersten Schritt …", bg="#1a202c", fg="#63b3ed",
                     font=("Segoe UI", 10))
    stand.pack(pady=(0, 8))

    feld = scrolledtext.ScrolledText(w, bg="#2d3748", fg="#e2e8f0", insertbackground="#e2e8f0",
                                     font=("Consolas", 9), wrap="none", borderwidth=0)
    feld.pack(fill="both", expand=True, padx=12, pady=(0, 8))
    feld.tag_config("ok", foreground="#68d391")
    feld.tag_config("fehl", foreground="#fc8181")
    feld.tag_config("hin", foreground="#90cdf4")
    feld.tag_config("her", foreground="#f6ad55")

    fuss = tk.Label(w, text="Das Fenster bleibt offen und liest mit. Schliessen beendet nur "
                            "das Mitlesen, nicht das Programm auf dem Brett.",
                    bg="#1a202c", fg="#a0aec0", font=("Segoe UI", 9))
    fuss.pack(pady=(0, 10))

    laeuft = {"an": True, "leitung_frei": False}

    def zeile(text, art=None):
        feld.insert("end", text + "\n", art or ())
        feld.see("end")

    def datei_lesen():
        """Die Mitschnittdatei laufend anzeigen, solange esp32_laden schreibt."""
        gelesen = 0
        while laeuft["an"] and not laeuft["leitung_frei"]:
            try:
                if datei.is_file():
                    t = datei.read_text(encoding="utf-8", errors="replace")
                    if len(t) > gelesen:
                        for z in t[gelesen:].splitlines():
                            if ENDE in z:
                                laeuft["leitung_frei"] = True
                                w.after(0, lambda: stand.config(
                                    text="Laden beendet — das Fenster liest jetzt selbst mit",
                                    fg="#68d391"))
                                break
                            art = ("ok" if " ok " in z else "fehl" if "FEHL" in z
                                   else "hin" if z.strip().startswith("->")
                                   else "her" if z.strip().startswith("<-") else None)
                            w.after(0, lambda z=z, a=art: zeile(z, a))
                            if z.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.")):
                                w.after(0, lambda z=z: stand.config(text=z.strip()[:90]))
                        gelesen = len(t)
            except OSError:
                pass
            time.sleep(0.25)

    def seriell_lesen():
        """Nach dem Laden selbst mitlesen — bis das Fenster zugeht."""
        while laeuft["an"] and not laeuft["leitung_frei"]:
            time.sleep(0.3)
        if not laeuft["an"]:
            return
        w.after(0, lambda: zeile("", None))
        w.after(0, lambda: zeile("--- ab hier liest das Fenster selbst mit ---", "hin"))
        try:
            import serial
        except ImportError:
            w.after(0, lambda: zeile("pyserial fehlt — kein Mitlesen moeglich.", "fehl"))
            return
        v = None
        for _ in range(20):                       # auf die Freigabe der Leitung warten
            if not laeuft["an"]:
                return
            try:
                v = serial.Serial(port, 115200, timeout=0.3)
                break
            except Exception:
                time.sleep(0.5)
        if v is None:
            w.after(0, lambda: zeile(f"{port} bleibt belegt — kein Mitlesen.", "fehl"))
            return
        marke = datei.parent / MARKE
        rest = b""
        try:
            while laeuft["an"]:
                #  Braucht jemand anders die Leitung? Dann zur Seite treten.
                try:
                    if marke.is_file() and "belegt" in marke.read_text(encoding="utf-8"):
                        w.after(0, lambda: zeile("--- Leitung wird gebraucht, Fenster tritt "
                                                 "zurueck und wartet ---", "hin"))
                        v.close()
                        while laeuft["an"] and marke.is_file() and \
                                "belegt" in marke.read_text(encoding="utf-8"):
                            time.sleep(0.4)
                        if not laeuft["an"]:
                            return
                        for _ in range(20):
                            try:
                                v = serial.Serial(port, 115200, timeout=0.3)
                                break
                            except Exception:
                                time.sleep(0.4)
                        w.after(0, lambda: zeile("--- Leitung wieder frei, Fenster liest "
                                                 "weiter mit ---", "hin"))
                except OSError:
                    pass
                teil = v.read(256)
                if not teil:
                    continue
                rest += teil
                while b"\n" in rest:
                    z, rest = rest.split(b"\n", 1)
                    s = z.decode("utf-8", "replace").rstrip()
                    if s:
                        w.after(0, lambda s=s: zeile("  " + s, "her"))
        except Exception as ex:
            w.after(0, lambda: zeile(f"Leitung abgebrochen: {type(ex).__name__}", "fehl"))
        finally:
            try:
                v.close()
            except Exception:
                pass

    def zu():
        laeuft["an"] = False
        w.after(200, w.destroy)

    w.protocol("WM_DELETE_WINDOW", zu)
    threading.Thread(target=datei_lesen, daemon=True).start()
    threading.Thread(target=seriell_lesen, daemon=True).start()
    w.mainloop()
    laeuft["an"] = False
    return 0


if __name__ == "__main__":
    sys.exit(main())
