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
# seit 05.10.2026: Anschluss genannt, mein.py abgenommen -> der Agent uebertraegt selbst; ohne Geraet schlaegt das fehl
# und ein fehlgeschlagener Schritt gibt kein FERTIG frei
rufe5b = [e for e in ev if e["art"] == "ruft" and e["werkzeug"] == "esp32_uebertragen" and e["eingabe"].get("datei") == "mein.py"]
fert5b = [e for e in ev if e["art"] == "fertig"]
pr("Anweisung 5b: Laden verlangt, nur behauptet -> Agent uebertraegt mein.py an COM3 selbst (einmal); ohne Geraet steht unter FERTIG 'esp32_uebertragen: fehlgeschlagen'",
   len(rufe5b) == 1 and r5b.startswith("FERTIG") and "esp32_uebertragen: fehlgeschlagen" in fert5b[-1].get("gemessen", ""), repr(fert5b[-1].get("gemessen", "")[:80]))

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
# 5h. leeres FERTIG auf eine Aufgabe (kein Werkzeug, keine Behauptung): Fokus liefert den Aufruf
zustand["fokus"] = 0
def leer(v, **k):
    if len(v) == 2:
        zustand["fokus"] += 1
        return schreib("leer.py", 5, 0.5) if zustand["fokus"] == 1 else test("leer.py", '{"pins": [5], "takt_hz": 1.0}')
    return antworten.pop(0) if antworten else "FERTIG. leer.py geschrieben und geprueft."
modell.fragen = leer
antworten[:] = ["FERTIG\n\nBereit fuer die naechste Anweisung."]
r5h = s.anweisung("Schreibe leer.py, LED an GPIO 5 mit 1 Hz, und pruefe es.")
pr("5h: leeres FERTIG -> Fokus sofort, Datei geschrieben und bestanden, FERTIG echt", zustand["fokus"] >= 1 and "leer.py" in s.abgenommen and r5h.startswith("FERTIG. leer.py"), f"(Fokus {zustand['fokus']}x)")
# 5i. eine fruehere, nie geschriebene Datei blockiert eine andere Anweisung nicht
modell.fragen = lambda v, **k: "FERTIG. Ich habe nachgesehen: keine Anschluesse."
s.verlangt.append("nie.py")
r5i = s.anweisung("Wie viele Anschluesse gibt es? Antworte kurz.")
pr("5i: 'nie.py' aus frueherer Anweisung blockiert eine Frage nicht", r5i.startswith("FERTIG. Ich habe nachgesehen"))
modell.fragen = fragen

# 5j. Zaehler „dritter gleicher Fehlschlag": zaehlt nur Fehlschlaege, nie eine bestandene Abnahme
modell.fragen = fragen
antworten[:] = [schreib("z.py", 6, 0.5), test("z.py", '{"pins": [6], "takt_hz": 2.0}'),
                schreib("z.py", 6, 0.5), test("z.py", '{"pins": [6], "takt_hz": 2.0}'),
                schreib("z.py", 6, 0.25), test("z.py", '{"pins": [6], "takt_hz": 2.0}'), "FERTIG. z.py blinkt mit einer Periode von 2 Sekunden."]
ab = len(ev)
r5j = s.anweisung("Schreibe z.py, LED an GPIO 6 mit 2 Hz (pins [6], takt_hz 2.0), und pruefe es.")
erg = [e for e in ev[ab:] if e["art"] == "ergibt" and e["werkzeug"] == "programm_testen"]
pr("5j: bestandene Abnahme traegt keinen Hinweis 'dritter gleicher Fehlschlag'", len(erg) == 3 and erg[-1]["abnahme"] == "bestanden" and "dritte gleiche" not in erg[-1]["text"], f"({len(erg)} Pruefungen)")
# 5k. FERTIG mit falscher Zahl: der Agent haengt die Messung an und merkt den Widerspruch an
fert = [e for e in ev[ab:] if e["art"] == "fertig"]
anm = [e for e in ev[ab:] if e["art"] == "hinweis" and "Anmerkung des Agenten" in e.get("text", "")]
pr("5k: unter FERTIG steht, was das Werkzeug gemessen hat (Takt, bestanden)", bool(fert) and "Takt" in fert[-1].get("gemessen", "") and "bestanden" in fert[-1].get("gemessen", ""), (fert[-1].get("gemessen", "")[:90] if fert else ""))
pr("5k: 'Periode von 2 Sekunden' bei 2 Hz bekommt eine sichtbare Anmerkung", bool(anm) and "Periode" in anm[-1]["text"] and "0.50 s" in anm[-1]["text"], (anm[-1]["text"][:100] if anm else ""))

# 5l. Nach NICHT BESTANDEN behauptet das Modell „wurde korrigiert" (kein Werkzeug): Berichtigungsfokus
#     liefert die Datei neu, der Agent haengt die Pruefung an, am Ende echtes FERTIG
antworten[:] = [schreib("k.py", 7, 0.5), test("k.py", '{"pins": [7], "takt_hz": 2.0}'),
                "FERTIG\n\nDie Zeile time.sleep(0.5) wurde korrigiert auf time.sleep(0.25).",
                schreib("k.py", 7, 0.25),                     # Antwort auf den Fokus (ohne Vorgeschichte)
                "FERTIG. k.py blinkt mit 2 Hz."]
ab = len(ev)
r5l = s.anweisung("Schreibe k.py, LED an GPIO 7 mit 2 Hz (pins [7], takt_hz 2.0), und pruefe es.")
rufe = [(e["werkzeug"], e["eingabe"].get("name") or e["eingabe"].get("datei")) for e in ev[ab:] if e["art"] == "ruft"]
fok = [e for e in ev[ab:] if e["art"] == "hinweis" and "Berichtigung" in e.get("text", "") or "berichtigte Datei" in e.get("text", "")]
pr("5l: behauptete Korrektur -> Fokus mit Datei und Befund, schreib_datei + Pruefung vom Agenten, FERTIG echt",
   bool(fok) and rufe[-2:] == [("schreib_datei", "k.py"), ("programm_testen", "k.py")] and "k.py" in s.abgenommen and r5l.startswith("FERTIG. k.py"), str(rufe))

# 5l-b. der Fokus-Prompt rechnet die Ersetzung vor
gesehen = {"prompts": []}
_fragen_alt = modell.fragen
def mitlesen(v, **k):
    gesehen["prompts"].append(v[-1]["content"]); return _fragen_alt(v, **k)
modell.fragen = mitlesen
antworten[:] = [schreib("kb.py", 9, 0.5), test("kb.py", '{"pins": [9], "takt_hz": 0.5}'),
                "FERTIG\n\nDie Taktperiode sollte 2 s sein.", schreib("kb.py", 9, 1.0), "FERTIG. kb.py blinkt mit 0.5 Hz."]
r5lb = s.anweisung("Schreibe kb.py, LED an GPIO 9 genau 1 s an und 1 s aus (pins [9], takt_hz 0.5), und pruefe es.")
fokusprompt = [p_ for p_ in gesehen["prompts"] if "Rechnung des Agenten" in p_]
pr("5l-b: der Berichtigungsfokus rechnet vor: Ersetze time.sleep(0.5) durch time.sleep(1)", bool(fokusprompt) and "Ersetze time.sleep(0.5) durch time.sleep(1)" in fokusprompt[0] and r5lb.startswith("FERTIG. kb.py"), (fokusprompt[0][fokusprompt[0].find("Rechnung"):][:120] if fokusprompt else r5lb[:80]))
modell.fragen = _fragen_alt
# 5l-c. „Es ist nun moeglich, das Programm auf den ESP32 zu uebertragen" ist keine Behauptung
antworten[:] = [schreib("kc.py", 10, 0.5), test("kc.py", '{"pins": [10], "takt_hz": 1.0}'),
                "FERTIG\n\nDie Pruefung war erfolgreich. Es ist nun moeglich, das Programm auf den ESP32 zu uebertragen und dort zu testen."]
r5lc = s.anweisung("Schreibe kc.py, LED an GPIO 10 mit 1 Hz (pins [10], takt_hz 1.0), und pruefe es.")
pr("5l-c: Moeglichkeitsform 'auf den ESP32 zu uebertragen' wird nicht als Behauptung zurueckgewiesen", r5lc.startswith("FERTIG") and "moeglich" in r5lc, r5lc[:80])

# 5l-d. das Modell bringt „form: sinusfoermig" in ein Ein/Aus-Programm ohne Wort des Menschen zur Form -> gestrichen
antworten[:] = [schreib("zw.py", 11, 0.25), test("zw.py", '{"pins": [11], "takt_hz": 2.0, "form": "sinusfoermig"}'), "FERTIG. zw.py blinkt."]
ab = len(ev)
r5ld = s.anweisung("Schreibe zw.py: LED an GPIO 11 zweimal je Sekunde. Pruefe gegen pins [11].")
t5ld = [e for e in ev[ab:] if e["art"] == "ruft" and e["werkzeug"] == "programm_testen"]
pr("5l-d: 'form' vom Modell ohne Wort des Menschen wird gestrichen; Erwartung pins [11], 2 Hz; FERTIG", bool(t5ld) and "form" not in t5ld[0]["eingabe"]["erwartet"] and s.feste_erwartung == {"pins": [11], "takt_hz": 2.0} and r5ld.startswith("FERTIG"), str(s.feste_erwartung))

# 5l-e. allgemeines Programm nach ESP32-Anweisungen: der Pruefweg richtet sich nach der Datei (programm_ausfuehren), nicht nach der alten Erwartung
antworten[:] = ['WERKZEUG: schreib_datei {"name": "rech.py", "inhalt": "print(1/0)"}', 'WERKZEUG: programm_ausfuehren {"datei": "rech.py", "sekunden": 5}',
                "FERTIG. Der Rechner steht.", 'WERKZEUG: schreib_datei {"name": "rech.py", "inhalt": "print(2+3)"}', "FERTIG. rech.py rechnet 2+3."]
ab = len(ev)
r5le = s.anweisung("Programmiere rech.py, das 2+3 ausgibt, und fuehre es mit programm_ausfuehren aus.")
rufe5le = [(e["werkzeug"], e["eingabe"].get("datei")) for e in ev[ab:] if e["art"] == "ruft" and e["werkzeug"] in ("programm_testen", "programm_ausfuehren")]
pr("5l-e: nach ESP32-Anweisungen prueft der Agent ein gewoehnliches Programm mit programm_ausfuehren, nie mit programm_testen gegen Pins",
   rufe5le and all(w == "programm_ausfuehren" for w, _ in rufe5le) and r5le.startswith("FERTIG. rech.py"), str(rufe5le))

# 5o. Musterprogramm als letzte Stufe: das Modell liefert zweimal dieselbe falsche Datei -> der Agent legt ein Muster vor,
#     das Modell schreibt es, das Werkzeug prueft es; unter FERTIG steht, dass das Muster vom Agenten stammt
falsch = "import machine, time\\npwm = machine.PWM(machine.Pin(12), freq=1000)\\nwhile True:\\n    pwm.duty(512); time.sleep(0.5)\\n"
antworten[:] = ['WERKZEUG: schreib_datei {"name": "at.py", "inhalt": "' + falsch + '"}',
                'WERKZEUG: programm_testen {"datei": "at.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [12], "takt_hz": 1.0, "form": "sinusfoermig"}}',
                "FERTIG. at.py atmet.", 'WERKZEUG: schreib_datei {"name": "at.py", "inhalt": "' + falsch + '"}',   # Fokus 1: unveraendert
                "FERTIG. at.py atmet.", "__MUSTER__",                                                                 # Fokus 2: Muster abschreiben
                "FERTIG. at.py atmet sinusfoermig."]
gesehen["prompts"] = []
def muster_abschreiben(v, **k):
    a = antworten.pop(0) if antworten else "FERTIG"
    if a == "__MUSTER__":
        p_ = v[-1]["content"]; gesehen["prompts"].append(p_)
        code = p_.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
        return 'WERKZEUG: schreib_datei {"name": "at.py", "inhalt": ' + json.dumps(code) + '}'
    return a
import json
modell.fragen = muster_abschreiben
ab = len(ev)
r5o = s.anweisung("Schreibe at.py, das die LED an GPIO 12 per PWM sinusfoermig atmen laesst, eine Periode pro Sekunde. Pruefe es.")
fert5o = [e for e in ev[ab:] if e["art"] == "fertig"]
pr("5o: Muster erst nach unveraenderter Fassung; Fokus-Prompt traegt das Musterprogramm; danach bestanden und FERTIG",
   bool(gesehen["prompts"]) and "Musterprogramm" in gesehen["prompts"][0] and "math.cos" in gesehen["prompts"][0] and "at.py" in s.abgenommen and r5o.startswith("FERTIG"), r5o[:60])
pr("5o: unter FERTIG steht, dass das Muster vom Agenten stammt", bool(fert5o) and "Musterprogramm vom Agenten" in fert5o[-1].get("gemessen", "") and "Form: erwartet sinusfoermig, gemessen sinusfoermig" in fert5o[-1].get("gemessen", ""), fert5o[-1].get("gemessen", "")[:120] if fert5o else "")
pr("5o: sichtbarer Hinweis, dass ein Muster vorgelegt wurde", any(e["art"] == "hinweis" and "Musterprogramm" in e.get("text", "") for e in ev[ab:]))
modell.fragen = fragen

# 5m. Abschlusstext aus Agentensaetzen („Die letzte Pruefung war erfolgreich (die Abnahme ist durchgefallen) …")
antworten[:] = [schreib("m.py", 8, 0.5), test("m.py", '{"pins": [8], "takt_hz": 1.0}'),
                "FERTIG\n\nDie letzte Pruefung war erfolgreich (die Abnahme ist durchgefallen). Ein Programm, das die Pruefung nicht besteht, gilt nicht als geliefert."]
ab = len(ev)
r5m = s.anweisung("Schreibe m.py, LED an GPIO 8 mit 1 Hz (pins [8], takt_hz 1.0), und pruefe es.")
fert = [e for e in ev[ab:] if e["art"] == "fertig"]
pr("5m: nachgeplapperter Abschlusstext wird durch den eigenen Abschluss des Agenten ersetzt",
   bool(fert) and "gilt nicht als geliefert" not in fert[-1]["text"] and "m.py wurde geschrieben" in fert[-1]["text"] and "bestanden" in fert[-1]["text"]
   and any(e["art"] == "hinweis" and "Abschlusstext" in e.get("text", "") for e in ev[ab:]), fert[-1]["text"][:120] if fert else "")

# 5n. „Lade k.py auf den ESP32 an COM9 und lies nach": Modell erzaehlt, Fokus liefert das Falsche (schreib_datei)
#     -> der Agent fuehrt esp32_uebertragen mit Datei, Anschluss und Erwartung selbst aus (k.py ist abgenommen)
antworten[:] = ["FERTIG. k.py wurde auf den ESP32 geladen und die LED blinkt.",
                schreib("k.py", 7, 0.25),                      # falsche Antwort auf den Fokus
                "FERTIG", "FERTIG", "FERTIG", "FERTIG"]
ab = len(ev)
r5n = s.anweisung("Lade k.py auf den ESP32 an COM9 und lies am Geraet nach, ob die LED so blinkt.")
rufe5n = [e for e in ev[ab:] if e["art"] == "ruft"]
pr("5n: Geraeteschritt verlangt, Modell liefert ihn nicht -> Agent ruft esp32_uebertragen k.py COM9 mit Erwartung selbst, genau einmal",
   len(rufe5n) == 1 and rufe5n[0]["werkzeug"] == "esp32_uebertragen" and rufe5n[0]["eingabe"].get("datei") == "k.py"
   and rufe5n[0]["eingabe"].get("port") == "COM9" and rufe5n[0]["eingabe"].get("erwartet") == s.feste_erwartung, str([(r["werkzeug"], r["eingabe"].get("datei")) for r in rufe5n]))
pr("5n: ohne Geraet endet die Anweisung ehrlich: Nachlesen verlangt, nicht gelungen -> Nicht abgenommen (oder FERTIG mit 'fehlgeschlagen')",
   (r5n.startswith("Nicht abgenommen") and "nicht gelungen" in r5n) or ("fehlgeschlagen" in r5n), r5n[:120])

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
com7 = [e for e in erg if e["eingabe"].get("port") == "COM7"] if all("eingabe" in e for e in erg) else []
rufe7 = [e for e in ev if e["art"] == "ruft" and e["werkzeug"] == "esp32_nachlesen" and e["eingabe"].get("port") == "COM7"]
pr("Zwischenruf: COM7 zuerst abgewiesen (nicht genannt), nach dem Zwischenruf 'COM7' zugelassen", len(rufe7) >= 2 and any("nicht genannt" in e["text"] for e in erg) and "nicht genannt" not in erg[-1]["text"] and "COM7" in s.genannte_ports and s.letzter_port == "COM7", str(len(rufe7)))
pr("Zwischenruf erscheint als Auftrag-Ereignis mit Marke", any(e["art"] == "auftrag" and e.get("zwischenruf") for e in ev))
modell.fragen = fragen
pr("Modellserver in der ersten Sitzung genau einmal gestartet", starts["n"] == 1, f"({starts[chr(110)]})")
# seit 05.10.2026 wird der Verlauf zu Beginn jeder Anweisung verdichtet: Anweisung des Agenten, ein Absatz Tatsachen,
# die letzte Anweisung im Wortlaut — der Zusammenhang bleibt ueber den Zustand des Agenten, nicht ueber den Wortlaut
zus = [m for m in s.verlauf if m["role"] == "user" and m["content"].startswith("Bisheriger Verlauf")]
pr("Sitzung haelt den Zusammenhang verdichtet: Zusammenfassung nennt Dateien, Erwartung und Anschluesse", bool(zus) and "blink.py" in zus[-1]["content"] and "COM3" in zus[-1]["content"] and "Erwartung" in zus[-1]["content"] and len(s.verlauf) < 40, f"({len(s.verlauf)} Nachrichten)")
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
pr("Protokoll: SITZUNG BEGINNT, AUFTRAG-Zeilen aller Sitzungen, ENDE", prot.count("AUFTRAG ") == 24 and "SITZUNG BEGINNT" in prot and prot.rstrip().endswith("ENDE"))
# Gegenproben zu erwartung_aus
pr("erwartung_aus: '5-mal pro Sekunde' -> 5 Hz", agent.erwartung_aus("blinke 5-mal pro Sekunde") == {"takt_hz": 5.0})
pr("erwartung_aus: 'GPIO 4 und GPIO 2' -> pins [2, 4]", agent.erwartung_aus("LED an GPIO 4 und GPIO 2") == {"pins": [2, 4]})
pr("erwartung_aus: '2,5 Hz' -> 2.5", agent.erwartung_aus("mit 2,5 Hz") == {"takt_hz": 2.5})
s2 = agent.Sitzung(agent.sammlung(), laut=False); s2._vom_menschen("nein es ist com 3 nicht com 5, oder Com7")
pr("Anschluss aus 'com 3', 'com 5', 'Com7' -> COM3, COM5, COM7", s2.genannte_ports == {"COM3", "COM5", "COM7"}, str(sorted(s2.genannte_ports)))
s2._vom_menschen("das Kommando lautet"); pr("'Kommando' nennt keinen Anschluss (Gegenprobe)", s2.genannte_ports == {"COM3", "COM5", "COM7"})
pr("erwartung_aus: ohne Zahl -> bisherige bleibt (Gegenprobe)", agent.erwartung_aus("mach weiter", {"pins": [2]}) == {"pins": [2]})
print(f"\n  {sum(f)} von {len(f)} Gegenproben bestanden"); shutil.rmtree(w, ignore_errors=True); sys.exit(0 if all(f) else 1)
