#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruefstand des Dieners — laeuft AUF seinem Rechner (Bruecke: python pruefe_diener.py), spielt die Seite.

Anlass 16.10.2026, 01:56:01 und 02:16:42: der Diener beendete sich mit „Seite geschlossen", obwohl
die Seite offen war. Sein Wort: „test das doch zuvor … auf dem Server … bevor ich den ungeprueften
Mist bekomme." Hier wird der Diener so abgefragt, wie die Seite es tut (Lebenszeichen alle 300 ms),
und dabei werden Uebersetzen und Simulator ausgeloest. Soll: der Diener lebt die ganze Zeit.
Danach wird das Ende der Seite gemeldet (/ende) — Soll: Diener und Modellserver sind weg.

    python pruefe_diener.py            (Diener muss laufen: kursagent start)
"""
import json
import subprocess
import sys
import threading
import time
import urllib.request

D = "http://127.0.0.1:8777"
BEFUNDE = []
lebt = {"an": True, "fehler": 0, "zaehler": 0}


def hole(pfad, zeit=5):
    with urllib.request.urlopen(D + pfad, timeout=zeit) as r:
        return json.loads(r.read().decode("utf-8"))


def sende(pfad, daten, zeit=30):
    req = urllib.request.Request(D + pfad, data=json.dumps(daten).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=zeit) as r:
        return json.loads(r.read().decode("utf-8"))


def puls():
    while lebt["an"]:
        try:
            hole("/seriell/lesen?ab=0", 3)
            lebt["zaehler"] += 1
        except Exception:                                         # noqa: BLE001
            lebt["fehler"] += 1
        time.sleep(0.3)


def prozesse():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe"], capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return "llama-server.exe" in (r.stdout or "")


def pruefe(nr, was, ok, beleg):
    BEFUNDE.append((nr, was, bool(ok), beleg))
    print(f"  {nr:4s} {'ERFUELLT      ' if ok else 'NICHT ERFUELLT'}  {was}\n        {beleg[:200]}", flush=True)


def main() -> int:
    print("PRUEFSTAND DIENER — ich spiele die Seite (Lebenszeichen alle 300 ms)", flush=True)
    try:
        z = hole("/zustand")
    except Exception as e:                                        # noqa: BLE001
        print("Diener antwortet nicht:", e)
        return 1
    pruefe("D1", "Diener antwortet (/zustand)", True, json.dumps(z)[:120])
    t = threading.Thread(target=puls, daemon=True); t.start()
    time.sleep(12)
    try:
        hole("/zustand"); lebt12 = True
    except Exception:                                             # noqa: BLE001
        lebt12 = False
    pruefe("D2", "Diener lebt nach 12 s Lebenszeichen (Waechterschwelle 8 s)", lebt12, f"{lebt['zaehler']} Pulse, {lebt['fehler']} Fehler")
    u = sende("/uebersetzen", {"name": "pruef_diener.py", "inhalt": "import time\nprint(1)\n"})
    pruefe("D3", "Uebersetzen antwortet", u.get("ok") is True, " | ".join(u.get("zeilen", []))[:150])
    a = sende("/werkzeug", {"name": "programm_testen", "eingabe": {"datei": "pruef_diener.py", "sekunden": 6, "oeffnen": False, "fenster": False}})
    fertig, ende, d = False, time.time() + 90, {}
    while time.time() < ende and not fertig:
        time.sleep(1)
        try:
            d = hole(f"/ausgabe?id={a.get('id', 0)}"); fertig = d.get("fertig", False)
        except Exception as e:                                    # noqa: BLE001
            pruefe("D4", "Simulator-Lauf: Diener lebt waehrend des Laufs", False, f"Diener weg: {e}")
            lebt["an"] = False
            return 1
    pruefe("D4", "Simulator-Lauf beendet, Diener lebt", fertig, (d.get("zeilen") or ["?"])[-1][:150])
    time.sleep(10)
    try:
        hole("/zustand"); lebt_danach = True
    except Exception:                                             # noqa: BLE001
        lebt_danach = False
    pruefe("D5", "Diener lebt 10 s nach dem Lauf", lebt_danach, f"{lebt['zaehler']} Pulse, {lebt['fehler']} Fehler")
    lebt["an"] = False
    time.sleep(1)
    # Ende der Seite melden — Soll: alles weg
    try:
        sende("/ende", {}, 5)
        gemeldet = True
    except Exception as e:                                        # noqa: BLE001
        gemeldet = False
        print("  /ende:", str(e)[:100])
    time.sleep(6)
    try:
        hole("/zustand", 3); weg = False
    except Exception:                                             # noqa: BLE001
        weg = True
    pruefe("D6", "nach /ende: Diener weg", weg, "gemeldet" if gemeldet else "/ende nicht angenommen")
    pruefe("D7", "nach /ende: Modellserver weg", not prozesse(), "tasklist llama-server.exe")
    print("-" * 78)
    gut = sum(1 for b in BEFUNDE if b[2])
    print(f"{gut} von {len(BEFUNDE)} erfuellt")
    print("DIENER BESTANDEN" if gut == len(BEFUNDE) else "DIENER NICHT BESTANDEN")
    return 0 if gut == len(BEFUNDE) else 1


if __name__ == "__main__":
    sys.exit(main())
