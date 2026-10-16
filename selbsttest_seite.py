#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Selbsttest der Seite — ich spiele den User, auf seinem Rechner, ueber die Bruecke.

Jeder Knopf des Reiters Testen wird so gedrueckt, wie die Seite es tut (dieselben Wege des
Dieners), mit dem Brett an COM3. Jeder Schritt hat ein Soll und eine Messung (Gebot 1, 2, 6).

    python3 selbsttest_seite.py            laeuft vom Arbeitsbereich aus
"""
import json
import re
import subprocess
import sys
import time

BEFEHL = ["python3", "/workspace/Bruecke/befehl.py", "-p", "Kurs_Agent"]
DIENER = "127.0.0.1:8777"
LLM = "127.0.0.1:8099"
BEFUNDE = []


def bruecke(*arg, zeit=300) -> str:
    r = subprocess.run([*BEFEHL, *arg], capture_output=True, text=True, timeout=zeit)
    return (r.stdout or "") + (r.stderr or "")


def hole(adresse, pfad) -> str:
    t = bruecke("hole", f"{adresse} {pfad}")
    m = re.search(r"(\{.*\}|\[.*\])", t, re.S)
    return m.group(1) if m else t.strip()


def sende(adresse, pfad, daten: dict) -> str:
    t = bruecke("sende", f"{adresse} {pfad} {json.dumps(daten, ensure_ascii=False)}")
    m = re.search(r"(\{.*\})", t, re.S)
    return m.group(1) if m else t.strip()


def werkzeug(name, eingabe, zeit=240) -> str:
    """Wie der Knopf: starten, dann /ausgabe abfragen, bis fertig."""
    a = json.loads(sende(DIENER, "/werkzeug", {"name": name, "eingabe": eingabe}))
    if "id" not in a:
        return "FEHLER " + json.dumps(a)
    ende = time.time() + zeit
    while time.time() < ende:
        time.sleep(3)
        d = json.loads(hole(DIENER, f"/ausgabe?id={a['id']}"))
        if d.get("fertig"):
            return "\n".join(d["zeilen"])
    return "FEHLER: Zeitgrenze"


def pruefe(nr, was, ok, beleg):
    BEFUNDE.append((nr, was, bool(ok), beleg))
    sende(DIENER, "/notiz", {"art": "SELBSTTEST", "text": f"{nr} {'ERFUELLT' if ok else 'NICHT ERFUELLT'} {was} | {beleg[:150]}"})
    print(f"  {nr:4s} {'ERFUELLT      ' if ok else 'NICHT ERFUELLT'}  {was}\n        {beleg[:220]}", flush=True)


def main() -> int:
    print("SELBSTTEST DER SEITE — ich spiele den User, Brett an COM3", flush=True)
    z = hole(DIENER, "/zustand")
    pruefe("S1", "Diener antwortet (/zustand)", '"laeuft"' in z, z[:120])

    d = json.loads(hole(DIENER, "/dateien"))
    pruefe("S2", "vorgefertigte Programme waehlbar (nur seine, laut VON_IHM.txt)", len(d.get("dateien", [])) >= 2 and set(d.get("dateien", [])) <= set(open("/workspace/Kurs_Agent/testprogramme/VON_IHM.txt").read().split()), ", ".join(d.get("dateien", [])))

    t1 = json.loads(hole(DIENER, "/datei?name=test1_blink_1hz.py"))
    code = t1.get("inhalt", "")
    pruefe("S3", "Programm kommt in den Editor (Inhalt lesbar, aenderbar)", "machine.Pin(2" in code, f"{len(code)} Zeichen")

    kaputt = code.replace("led.value(0)", "led.value(0")
    u = json.loads(sende(DIENER, "/uebersetzen", {"name": "test1_blink_1hz.py", "inhalt": kaputt}))
    text = "\n".join(u.get("zeilen", []))
    pruefe("S4", "Interpreter meldet einen eingebauten Fehler wortgetreu im Ausgabefenster",
           (not u.get("ok")) and "SyntaxError" in text and "line 11" in text, text.replace("\n", " | "))

    u = json.loads(sende(DIENER, "/uebersetzen", {"name": "test1_blink_1hz.py", "inhalt": code}))
    pruefe("S5", "berichtigtes Programm: Interpreter Rueckgabewert 0, keine Ausgabe", u.get("ok") and "(keine Ausgabe" in "\n".join(u["zeilen"]), u["zeilen"][-1])

    s = werkzeug("programm_testen", {"datei": "test1_blink_1hz.py", "sekunden": 6, "oeffnen": False})
    m = re.search(r"Takt an Pin 2: ([\d.]+) s[^(]*\(([\d.]+) Hz\)", s) or re.search(r"Takt: ([\d.]+) s[^(]*\(([\d.]+) Hz\)", s)
    pruefe("S6", "Simulator misst 1 Hz am Pin 2 (ohne Brett)", m and abs(float(m.group(2)) - 1.0) < 0.1, m.group(0) if m else s[-200:])

    s = werkzeug("ports_zeigen", {})
    pruefe("S7", "Anschluesse zeigen findet COM3 mit CH340", "COM3" in s and "CH340" in s, s.replace("\n", " | ")[:200])

    s = werkzeug("esp32_firmware", {"port": "COM3", "nur_pruefen": True}, 120)
    pruefe("S8", "Firmware-Pruefung misst das Banner (nur nachsehen)", "gemessen: MicroPython v" in s, s.replace("\n", " | ")[:200])

    s = werkzeug("esp32_firmware", {"port": "COM3"}, 400)
    pruefe("S9", "Betriebssystem aufspielen: geschrieben UND Banner danach gemessen", "FIRMWARE BESTANDEN" in s and "MicroPython v" in s,
           " | ".join(z for z in s.splitlines() if "BESTANDEN" in z or "meldet sich" in z)[:220])

    s = werkzeug("esp32_laden", {"datei": "test1_blink_1hz.py", "port": "COM3", "fenster": False, "sekunden": 3}, 300)
    pruefe("S10", "Laden: Pruefsumme vom Brett gleich, Neustart", "LADEN BESTANDEN" in s and "gleich der Werkstattdatei" in s,
           " | ".join(z.strip() for z in s.splitlines() if z.strip().startswith(("3.", "6.", "LADEN")))[:220])

    s = werkzeug("esp32_nachlesen", {"port": "COM3", "datei": "main.py", "sekunden": 6, "erwartet": {"pins": [2], "takt_hz": 1.0}}, 300)
    m = re.search(r"\(([\d.]+) Hz\) - Flanken", s)
    pruefe("S11", "Nachlesen am Geraet: 1 Hz an Pin 2, ABNAHME BESTANDEN", "ABNAHME BESTANDEN" in s and m and abs(float(m.group(1)) - 1.0) < 0.1,
           (m.group(0) if m else "") + " | " + ("ABNAHME BESTANDEN" if "ABNAHME BESTANDEN" in s else s[-150:]))

    o = sende(DIENER, "/seriell/oeffnen", {"port": "COM3"})
    time.sleep(2)
    sende(DIENER, "/seriell/senden", {"art": "strg_c"}); time.sleep(0.5)
    sende(DIENER, "/seriell/senden", {"text": "print(7*6)"}); time.sleep(1.5)
    g = json.loads(hole(DIENER, "/seriell/lesen?ab=0"))
    pruefe("S12", "Terminal: verbinden, Strg+C, Befehl print(7*6) -> 42 vom Brett", '"ok": true' in o and "42" in g.get("text", "") and ">>>" in g.get("text", ""),
           g.get("text", "")[-160:].replace("\n", " | "))
    sende(DIENER, "/seriell/senden", {"art": "strg_d"}); time.sleep(3)
    g2 = json.loads(hole(DIENER, f"/seriell/lesen?ab={g.get('ab', 0)}"))
    pruefe("S13", "Terminal: Strg+D -> weicher Neustart mit Banner", "MicroPython v" in g2.get("text", "") or "soft reboot" in g2.get("text", ""),
           g2.get("text", "")[:160].replace("\n", " | "))
    sende(DIENER, "/seriell/schliessen", {})

    a = sende(LLM, "/v1/chat/completions", {"messages": [{"role": "user", "content": "Wie viele Beine hat eine Spinne? Antworte mit einer Zahl."}],
                                             "max_tokens": 30, "temperature": 0.2})
    try:
        inhalt = json.loads(a)["choices"][0]["message"]["content"]
    except Exception:                                             # noqa: BLE001
        inhalt = a[:200]
    pruefe("S14", "Sprachmodell antwortet auf eine Eingabe", "8" in inhalt or "acht" in inhalt.lower(), inhalt.strip()[:120])

    s = werkzeug("esp32_laden", {"datei": "test1_blink_1hz.py", "port": "COM3", "fenster": False, "sekunden": 3}, 300)
    pruefe("S15", "Laden nach dem Terminal (Leitung wieder frei) besteht erneut", "LADEN BESTANDEN" in s, s.splitlines()[-1][:160] if s else s)

    bruecke("hochladen", r"C:\Kurs_Agent\ablage\protokoll_testen.txt")
    import glob, os
    pfade = sorted(glob.glob("/workspace/Kurs_Agent/Bilder/*protokoll_testen.txt"), key=os.path.getmtime)
    p = open(pfade[-1], encoding="utf-8").read() if pfade else ""
    noetig = ["WAHL", "EDITOR", "NICHT_UEBERS", "UEBERSETZT", "WERKZEUG     programm_testen", "WERKZEUG     esp32_firmware",
              "WERKZEUG     esp32_laden", "SERIELL", "REPL"]
    fehlt = [n for n in noetig if n not in p]
    pruefe("S16", "Protokoll enthaelt jeden Schritt dieses Tests", not fehlt, "fehlt: " + ", ".join(fehlt) if fehlt else f"{len(p.splitlines())} Zeilen, alle Arten vorhanden")

    print("-" * 78)
    gut = sum(1 for b in BEFUNDE if b[2])
    print(f"{gut} von {len(BEFUNDE)} erfuellt")
    print("SELBSTTEST BESTANDEN" if gut == len(BEFUNDE) else "SELBSTTEST NICHT BESTANDEN")
    return 0 if gut == len(BEFUNDE) else 1


if __name__ == "__main__":
    sys.exit(main())
