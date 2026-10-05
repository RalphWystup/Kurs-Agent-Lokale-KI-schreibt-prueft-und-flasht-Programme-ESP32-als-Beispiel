"""Prueft das Gespraech: mehrere Anweisungen, ein Zusammenhang (04.10.2026, Anweisung des
Auftraggebers: anderer Pin, andere Frequenz, erst pruefen dann laden, eigenes Programm).
Festes Modell mit festen Antworten; jede Pruefung hat eine Gegenprobe. Aufruf aus diesem Ordner.
"""
import sys, os, pathlib, tempfile, shutil, importlib.util
w = tempfile.mkdtemp(); os.environ["KURS_AGENT_WURZEL"] = w
A = pathlib.Path(__file__).resolve().parent.parent / "agent"; sys.path.insert(0, str(A))
def lade(name):
    sp = importlib.util.spec_from_file_location(name, A / f"{name}.py"); m = importlib.util.module_from_spec(sp); sys.modules[name] = m; sp.loader.exec_module(m); return m
modell = lade("modell"); agent = lade("agent")
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
f = []
def pr(b, ok, info=""): print(f"  {'OK  ' if ok else 'FEHL'} {b} {info}"); f.append(ok)

def prog(pin, pause):
    return (f"from machine import Pin\\nimport time\\nled = Pin({pin}, Pin.OUT)\\nwhile True:\\n"
            f"    led.value(1)\\n    time.sleep({pause})\\n    led.value(0)\\n    time.sleep({pause})\\n")
def schreib(name, pin, pause): return 'WERKZEUG: schreib_datei {"name": "' + name + '", "inhalt": "' + prog(pin, pause) + '"}'
def test(name, erw): return 'WERKZEUG: programm_testen {"datei": "' + name + '", "sekunden": 3, "oeffnen": false, "erwartet": ' + erw + '}'

starts = {"n": 0}
_start = modell.starten
class _Server:
    def poll(self): return None
def zaehl_start(laut=True): starts["n"] += 1; return _Server()
modell.starten = zaehl_start; modell.beenden = lambda p: None
antworten = []
def fragen(v, **k): return antworten.pop(0) if antworten else "FERTIG"
modell.fragen = fragen
ev = []
s = agent.Sitzung(agent.sammlung(), laut=False, melden=ev.append)

# 1. erste Anweisung: blink.py 1 Hz
antworten[:] = [schreib("blink.py", 2, 0.5), test("blink.py", '{"pins": [2], "takt_hz": 1.0}'), "FERTIG. blink.py blinkt mit 1 Hz."]
r1 = s.anweisung("Schreibe blink.py, LED an GPIO 2 einmal je Sekunde; pruefe gegen pins [2] und takt_hz 1.0.")
pr("Anweisung 1: FERTIG nach schreiben + bestandenem Test", r1.startswith("FERTIG") and "blink.py" in s.abgenommen)

# 2. anderer Pin: nur der Pin aendert sich, der Takt bleibt
antworten[:] = [schreib("blink.py", 4, 0.5), test("blink.py", '{"pins": [2], "takt_hz": 1.0}'), "FERTIG. Jetzt GPIO 4."]
r2 = s.anweisung("Verwende einen anderen Pin: GPIO 4.")
pr("Anweisung 2: Erwartung wird pins [4] bei gleichem Takt 1.0", s.feste_erwartung == {"pins": [4], "takt_hz": 1.0})
letzter_test = [e for e in ev if e["art"] == "ruft" and e["werkzeug"] == "programm_testen"][-1]
pr("Anweisung 2: geprueft wurde gegen pins [4], obwohl das Modell [2] schrieb", letzter_test["eingabe"]["erwartet"] == {"pins": [4], "takt_hz": 1.0} and r2.startswith("FERTIG"))

# 2b. neue Erwartung ohne neues Programm: FERTIG wird abgewiesen, bis neu geprueft ist
antworten[:] = ["FERTIG. Passt schon.", schreib("blink.py", 5, 0.5), test("blink.py", '{"pins": [5], "takt_hz": 1.0}'), "FERTIG. Geprueft gegen GPIO 5."]
r2b = s.anweisung("Nimm jetzt GPIO 5.")
pr("Anweisung 2b: neue Erwartung (GPIO 5) -> FERTIG abgewiesen, Programm neu, Test, FERTIG", r2b.startswith("FERTIG. Geprueft") and len(antworten) == 0 and s.feste_erwartung == {"pins": [5], "takt_hz": 1.0}, f"(r2b={r2b[:60]!r}, offen={antworten})")

# 3. andere Frequenz: 10 Hz, Modell schreibt erst falsch (0.5), Hinweis nennt 0.05
antworten[:] = [schreib("blink.py", 5, 0.5), test("blink.py", '{"pins": [5], "takt_hz": 10.0}'),
                schreib("blink.py", 5, 0.05), test("blink.py", '{"pins": [5], "takt_hz": 10.0}'), "FERTIG. 10 Hz."]
r3 = s.anweisung("Aendere die Blinkfrequenz auf 10 Hz.")
pr("Anweisung 3: Erwartung takt_hz 10.0, Pin bleibt 5", s.feste_erwartung == {"pins": [5], "takt_hz": 10.0})
durchgefallen = [e for e in ev if e["art"] == "ergibt" and e.get("abnahme") == "durchgefallen"]
pr("Anweisung 3: Hinweis rechnet die Pause fuer 10 Hz vor (0.05 s)", bool(durchgefallen) and "time.sleep(0.05)" in durchgefallen[-1]["text"])
pr("Anweisung 3: FERTIG erst nach bestandenem 10-Hz-Test", r3.startswith("FERTIG") and "blink.py" in s.abgenommen)

# 4. auf das Geraet: fremder Anschluss wird abgewiesen; ungeprueftes Programm wird abgewiesen
antworten[:] = ['WERKZEUG: esp32_uebertragen {"port": "COM9", "datei": "blink.py"}',
                schreib("blink.py", 5, 0.05),
                'WERKZEUG: esp32_uebertragen {"port": "COM3", "datei": "blink.py"}',
                test("blink.py", '{"pins": [5], "takt_hz": 10.0}'),
                "FERTIG. Geprueft; das Uebertragen an COM3 steht aus, der Test lief ohne Hardware."]
r4 = s.anweisung("Pruefe zuerst, bevor du das Programm auf den ESP32 an COM3 laedst.")
erg = [e for e in ev if e["art"] == "ergibt" and e["werkzeug"] == "esp32_uebertragen"]
pr("Anweisung 4: COM9 (vom Menschen nicht genannt) wird abgewiesen", len(erg) >= 1 and "nicht genannt" in erg[0]["text"])
pr("Anweisung 4: COM3 ist genannt, aber die Datei ist seit der Aenderung ungeprueft -> abgewiesen", len(erg) >= 2 and "nicht abgenommen" in erg[1]["text"] and "veraendert" in erg[1]["text"])
pr("Anweisung 4: endet mit FERTIG nach erneutem Test", r4.startswith("FERTIG"))

# 5. eigenes Programm des Menschen: der Agent schreibt es woertlich, das Modell prueft nur
antworten[:] = [test("mein.py", '{"pins": [4], "takt_hz": 10.0}'), "FERTIG. mein.py ist geprueft."]
eigen = "from machine import Pin\nimport time\nled = Pin(5, Pin.OUT)\nwhile True:\n    led.value(1)\n    time.sleep(0.25)\n    led.value(0)\n    time.sleep(0.25)\n"
r5 = s.anweisung("Pruefe mein Programm mein.py gegen pins [5] und takt_hz 2.0:\n```python\n" + eigen + "```")
geschrieben = [e for e in ev if e["art"] == "ruft" and e["werkzeug"] == "schreib_datei" and e.get("vom_menschen")]
pr("Anweisung 5: das eingegebene Programm wurde woertlich als mein.py geschrieben", bool(geschrieben) and geschrieben[-1]["eingabe"]["inhalt"] == eigen and geschrieben[-1]["eingabe"]["name"] == "mein.py")
pr("Anweisung 5: geprueft gegen pins [5] und 2 Hz aus der Eingabe, bestanden, FERTIG", s.feste_erwartung == {"pins": [5], "takt_hz": 2.0} and "mein.py" in s.abgenommen and r5.startswith("FERTIG"))

# 5b. Behauptung je Anweisung: frueher wurde uebertragen; jetzt verlangt die Anweisung Laden, das Modell behauptet es nur
antworten[:] = ["FERTIG. Auf den ESP32 geladen.", "FERTIG. Geladen.", "FERTIG. Wirklich.", "FERTIG. Ja."]
r5b = s.anweisung("Lade mein.py auf den ESP32 an COM3.")
pr("Anweisung 5b: Laden verlangt, nur behauptet -> Fokus, dreimal abgewiesen, dann NICHT ABGENOMMEN (erfunden)", r5b.startswith("Nicht abgenommen") and ("nicht gelaufen" in r5b or "erfunden" in r5b), repr(r5b[:70]))

# 5c. Gruss: das Modell antwortet in Worten, der Agent nimmt es als Antwort (kein Nachhaken, keine Vorgabe)
antworten[:] = ["Ja, ich bin bereit. Was soll ich tun?"]
vorher = len([e for e in ev if e["art"] == "ruft"])
r5c = s.anweisung("hallo bist du bereit?")
pr("Anweisung 5c: Gruss -> Antwort in Worten gilt, kein Werkzeug, Modell nur einmal gefragt", r5c.startswith("Ja, ich bin bereit") and len([e for e in ev if e["art"] == "ruft"]) == vorher and len(antworten) == 0)

# 5e. erfundene Arbeit: FERTIG mit „geschrieben und geprueft", nichts gelaufen -> Zurueckweisung nennt den ersten Schritt; dann tut es das Modell
antworten[:] = ["FERTIG. Ich habe das Programm geschrieben und geprueft, die LED blinkt.", schreib("l.py", 5, 0.5), test("l.py", '{"pins": [5], "takt_hz": 1.0}'), "FERTIG. l.py geschrieben und bestanden."]
r5e = s.anweisung("Lass die LED l.py mit 1 Hz an GPIO 5 blinken.")
zur = [m for m in s.verlauf if m["role"] == "user" and "Das ist nicht wahr" in m["content"]]
pr("Anweisung 5e: erfundene Arbeit wird als unwahr zurueckgewiesen mit Beispielaufruf, danach echter Lauf, FERTIG", bool(zur) and "schreib_datei" in zur[-1]["content"] and r5e.startswith("FERTIG. l.py"))
# 5g. Prosa-Schleife: das Modell erzaehlt im langen Gespraech erfundene Arbeit; ohne Vorgeschichte (Fokus, Verlauf mit 2 Nachrichten) liefert es den Aufruf
zustand = {"fokus": 0}
def prosa(v, **k):
    if len(v) == 2:
        zustand["fokus"] += 1
        return schreib("f.py", 5, 0.5) if zustand["fokus"] == 1 else test("f.py", '{"pins": [5], "takt_hz": 1.0}')
    return antworten.pop(0) if antworten else "FERTIG. f.py ist geschrieben und geprueft."
modell.fragen = prosa
antworten[:] = ["FERTIG. Ich habe f.py geschrieben und geprueft, LAUF BESTANDEN.", "FERTIG. Ich habe f.py geschrieben und geprueft."]
r5g = s.anweisung("Schreibe f.py, LED an GPIO 5 mit 1 Hz, und pruefe es.")
pr("5g: erfundene Arbeit -> Fokus ohne Vorgeschichte liefert schreib_datei, dann Test, FERTIG echt", zustand["fokus"] >= 1 and "f.py" in s.abgenommen and r5g.startswith("FERTIG. f.py"), f"(Fokus {zustand['fokus']}x, {r5g[:50]!r})")
modell.fragen = fragen
# 6. Zwischenruf: Modell fragt nach dem Anschluss, der Mensch ruft "COM7" dazwischen, naechster Aufruf darf COM7
def mit_zwischenruf(v, **k):
    a = antworten.pop(0) if antworten else "FERTIG"
    if a == "__ZWISCHENRUF__":
        s.zwischenruf("COM7"); return 'WERKZEUG: ports_zeigen {}'
    return a
modell.fragen = mit_zwischenruf
antworten[:] = ['WERKZEUG: esp32_nachlesen {"port": "COM7", "sekunden": 2}', "__ZWISCHENRUF__",
                'WERKZEUG: esp32_nachlesen {"port": "COM7", "sekunden": 2}', "FERTIG. Nachgelesen."]
r6 = s.anweisung("Lies am Geraet nach, ob die LED blinkt.")
erg = [e for e in ev if e["art"] == "ergibt" and e["werkzeug"] == "esp32_nachlesen"]
pr("Zwischenruf: COM7 zuerst abgewiesen (nicht genannt), nach dem Zwischenruf 'COM7' zugelassen", len(erg) >= 2 and "nicht genannt" in erg[-2]["text"] and "nicht genannt" not in erg[-1]["text"] and "COM7" in s.genannte_ports)
pr("Zwischenruf erscheint als Auftrag-Ereignis mit Marke", any(e["art"] == "auftrag" and e.get("zwischenruf") for e in ev))
modell.fragen = fragen
pr("Modellserver in der ersten Sitzung genau einmal gestartet", starts["n"] == 1, f"({starts[chr(110)]})")
pr("Sitzung haelt den Verlauf (mehr als 20 Nachrichten)", len(s.verlauf) > 20)
s.schliessen()
# 5d. ohne Erwartung des Menschen: die erste des Modells wird festgehalten, die zweite ueberschrieben
s3 = agent.Sitzung(agent.sammlung(), laut=False, melden=ev.append)
def wandernd(v, **k): return antworten.pop(0) if antworten else "FERTIG"
modell.fragen = wandernd
antworten[:] = [schreib("w.py", 2, 0.5), test("w.py", '{"pins": [2], "takt_hz": 10.0}'), schreib("w.py", 2, 0.5), test("w.py", '{"pins": [2], "takt_hz": 1.0}'), "FERTIG."]
s3.anweisung("Schreibe w.py, das die LED an GPIO 2 blinken laesst, und pruefe es.")
tests = [e for e in ev if e["art"] == "ruft" and e["werkzeug"] == "programm_testen" and e["eingabe"].get("datei") == "w.py"]
pr("Anweisung 5d: Pin vom Menschen, Takt vom ersten Modellaufruf (10 Hz) festgehalten, zweiter (1 Hz) ueberschrieben", len(tests) == 2 and tests[0]["eingabe"]["erwartet"] == {"pins": [2], "takt_hz": 10.0} and tests[1]["eingabe"]["erwartet"] == {"pins": [2], "takt_hz": 10.0} and s3.feste_erwartung == {"pins": [2], "takt_hz": 10.0}, str([x["eingabe"]["erwartet"] for x in tests]))
s3.schliessen()
# 5f. frische Sitzung, Modell behauptet in freier Rede: Anmerkung des Agenten sichtbar
ev5 = []; s5 = agent.Sitzung(agent.sammlung(), laut=False, melden=ev5.append)
modell.fragen = lambda v, **k: "Ja, alles ist ok. Die LED blinkt einmal pro Sekunde."
r5f = s5.anweisung("Ist nun alles ok?")
anm = [e for e in ev5 if e["art"] == "hinweis" and "Anmerkung des Agenten" in e.get("text", "")]
pr("5f: Behauptung ohne Werkzeuge bekommt eine sichtbare Anmerkung, Antwort bleibt", bool(anm) and "kein Programm geprueft" in anm[0]["text"] and r5f.startswith("Ja, alles"))
s5.schliessen(); modell.fragen = fragen
pr("je Sitzung ein Modellstart (drei Sitzungen)", starts["n"] == 3, f"({starts[chr(110)]})")

prot = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
pr("Protokoll: SITZUNG BEGINNT, AUFTRAG-Zeilen aller Sitzungen, ENDE", prot.count("AUFTRAG ") == 13 and "SITZUNG BEGINNT" in prot and prot.rstrip().endswith("ENDE"))
# Gegenproben zu erwartung_aus
pr("erwartung_aus: '5-mal pro Sekunde' -> 5 Hz", agent.erwartung_aus("blinke 5-mal pro Sekunde") == {"takt_hz": 5.0})
pr("erwartung_aus: 'GPIO 4 und GPIO 2' -> pins [2, 4]", agent.erwartung_aus("LED an GPIO 4 und GPIO 2") == {"pins": [2, 4]})
pr("erwartung_aus: '2,5 Hz' -> 2.5", agent.erwartung_aus("mit 2,5 Hz") == {"takt_hz": 2.5})
s2 = agent.Sitzung(agent.sammlung(), laut=False); s2._vom_menschen("nein es ist com 3 nicht com 5, oder Com7")
pr("Anschluss aus 'com 3', 'com 5', 'Com7' -> COM3, COM5, COM7", s2.genannte_ports == {"COM3", "COM5", "COM7"}, str(sorted(s2.genannte_ports)))
s2._vom_menschen("das Kommando lautet"); pr("'Kommando' nennt keinen Anschluss (Gegenprobe)", s2.genannte_ports == {"COM3", "COM5", "COM7"})
pr("erwartung_aus: ohne Zahl -> bisherige bleibt (Gegenprobe)", agent.erwartung_aus("mach weiter", {"pins": [2]}) == {"pins": [2]})
print(f"\n  {sum(f)} von {len(f)} Gegenproben bestanden"); shutil.rmtree(w, ignore_errors=True); sys.exit(0 if all(f) else 1)
