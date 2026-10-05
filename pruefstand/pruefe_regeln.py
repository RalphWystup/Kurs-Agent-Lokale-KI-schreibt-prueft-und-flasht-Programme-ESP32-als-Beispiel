"""Prueft die Regeln der Schleife, die am 04.10.2026 aus dem ersten echten Windows-Lauf kamen:
Werkzeugaufruf ohne das Wort WERKZEUG, Erwartung aus dem Auftrag, Kuerzen des Verlaufs,
Zusammenfassen bei vollem Kontext, Fehlerbericht, keine Pruefung ungeschriebener Dateien.
Jede Pruefung hat eine Gegenprobe, die durchfallen muss. Aufruf aus diesem Ordner.
"""
import sys, os, pathlib, tempfile, shutil, importlib.util
w = tempfile.mkdtemp(); os.environ["KURS_AGENT_WURZEL"] = w
A = pathlib.Path(__file__).resolve().parent.parent / 'agent'; sys.path.insert(0, str(A))
def lade(name):
    sp = importlib.util.spec_from_file_location(name, A / f"{name}.py"); m = importlib.util.module_from_spec(sp); sys.modules[name] = m; sp.loader.exec_module(m); return m
modell = lade("modell"); agent = lade("agent")
namen = {"schreib_datei", "programm_testen", "ports_zeigen"}
f = []
def pr(bez, ok, info=""): print(f"  {'OK  ' if ok else 'FEHL'} {bez} {info}", flush=True); f.append(ok)
n, e = agent.heraus('schreib_datei {"name": "a.py", "inhalt": "x"}', namen); pr("ohne WERKZEUG erkannt", n == "schreib_datei" and e == {"name": "a.py", "inhalt": "x"})
n, e = agent.heraus('WERKZEUG: ports_zeigen {}', namen); pr("mit WERKZEUG weiterhin", n == "ports_zeigen")
n, e = agent.heraus('Ich wuerde jetzt schreib_datei aufrufen {"x": 1}', namen); pr("Name mitten im Satz NICHT erkannt (Gegenprobe)", n is None)
n, e = agent.heraus('unbekannt {"x": 1}', namen); pr("unbekannter Name NICHT erkannt (Gegenprobe)", n is None)
pr("Erwartung aus Auftrag", agent.erwartung_aus("gegen pins [2] und takt_hz 1.0.") == {"pins": [2], "takt_hz": 1.0})
pr("Erwartung mehrere Pins ohne Takt", agent.erwartung_aus("gegen pins [2, 4].") == {"pins": [2, 4]})
pr("keine Erwartung -> None (Gegenprobe)", agent.erwartung_aus("sieh nach, welche Anschluesse es gibt") is None)
lang = "\n".join(f"Zeile {i}" for i in range(200)); k = agent.kuerzen(lang)
pr("kuerzen: Kopf und Fuss bleiben", k.startswith("Zeile 0") and k.rstrip().endswith("Zeile 199") and "ausgelassen" in k and len(k) < 2600, f"({len(k)} Zeichen)")
pr("kuerzen: Kurzes bleibt ganz (Gegenprobe)", agent.kuerzen("a\nb") == "a\nb")
v = [{"role":"system","content":"S"},{"role":"user","content":"A"}] + [{"role":"user","content":f"m{i}"} for i in range(20)]
z = agent.zusammenfassen(v, ["schreib_datei"], None); pr("zusammenfassen: 2 + 1 + 6", len(z) == 9 and z[0]["content"] == "S" and "schreib_datei" in z[2]["content"] and z[-1]["content"] == "m19")
modell.starten = lambda laut=True: None; modell.beenden = lambda p: None
def kaputt(verlauf, **kw): raise RuntimeError("Testabbruch 4711")
modell.fragen = kaputt
werk = agent.sammlung()
try:
    agent.schleife("Schreibe blink.py, pruefe gegen pins [2] und takt_hz 1.0", werk, laut=False); pr("Ausnahme wird weitergereicht", False)
except RuntimeError:
    b = pathlib.Path(w) / "ablage" / "fehlerbericht.txt"; p = pathlib.Path(w) / "ablage" / "protokoll.txt"
    inhalt = b.read_text(encoding="utf-8") if b.is_file() else ""; prot = p.read_text(encoding="utf-8") if p.is_file() else ""
    pr("fehlerbericht.txt geschrieben", b.is_file() and "Testabbruch 4711" in inhalt and "Rueckverfolgung" in inhalt and "Auftrag:" in inhalt)
    pr("Protokoll traegt ABBRUCH, FEHLERBERICHT und ENDE", "ABBRUCH RuntimeError" in prot and "FEHLERBERICHT" in prot and prot.rstrip().endswith("ENDE"))
RICHTIG = "from machine import Pin\\nimport time\\nled = Pin(2, Pin.OUT)\\nwhile True:\\n    led.value(1)\\n    time.sleep(0.5)\\n    led.value(0)\\n    time.sleep(0.5)\\n"
zustand = {"n": 0}
def voll(verlauf, **kw):
    zustand["n"] += 1
    if zustand["n"] == 1: raise modell.KontextVoll("voll")
    if zustand["n"] == 2: return 'WERKZEUG: schreib_datei {"name": "blink.py", "inhalt": "' + RICHTIG + '"}'
    if zustand["n"] == 3: return 'WERKZEUG: programm_testen {"datei": "blink.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [2], "takt_hz": 0.5}}'
    return "FERTIG"
modell.fragen = voll
letzte = {}
_aus = agent.ausfuehren
def merk(name, eingabe, werkzeuge):
    r = _aus(name, eingabe, werkzeuge)
    if name == "programm_testen": letzte["eingabe"] = dict(eingabe); letzte["ergebnis"] = r
    return r
agent.ausfuehren = merk
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
ereignisse = []
r = agent.schleife("Schreibe blink.py, pruefe gegen pins [2] und takt_hz 1.0", werk, laut=False, melden=ereignisse.append)
prot = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
pr("KontextVoll ueberlebt, Lauf endet mit FERTIG", "KONTEXT VOLL" in prot and "FERTIG" in prot)
ruf = [z for z in prot.splitlines() if "RUFT programm_testen" in z]
pr("Erwartung des Modells (0.5) durch die des Auftrags (1.0) ersetzt", letzte.get("eingabe", {}).get("erwartet") == {"pins": [2], "takt_hz": 1.0} and bool(ruf) and '"takt_hz": 1.0' in ruf[0])
pr("Abnahme danach bestanden", "ABNAHME BESTANDEN" in letzte.get("ergebnis", ""), "\n      ERGEBNIS: " + letzte.get("ergebnis", "")[:600].replace("\n", " | "))
pr("Hinweis an das Modell, dass die Erwartung aus dem Auftrag kommt", any("HINWEIS: Die Erwartung steht im Auftrag" in e.get("text", "") for e in ereignisse if e.get("art") == "ergibt"))
zustand["n"] = 0
def fremd(verlauf, **kw):
    zustand["n"] += 1
    return 'WERKZEUG: programm_testen {"datei": "fremd.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [2]}}' if zustand["n"] == 1 else "FERTIG"
modell.fragen = fremd
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
agent.schleife("Pruefe fremd.py gegen pins [2]", werk, laut=False)
prot = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
pr("Pruefung einer nicht geschriebenen Datei wird abgewiesen", "noch nicht geschrieben" in prot)
# aufraeumen mitten im Auftrag: wird abgewiesen, der Lauf geht weiter, die Ablage bleibt
zustand["n"] = 0
def raeumer(verlauf, **kw):
    zustand["n"] += 1
    return 'WERKZEUG: aufraeumen {}' if zustand["n"] == 1 else "FERTIG"
modell.fragen = raeumer
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
agent.schleife("Sieh nach, welche Anschluesse es gibt", werk, laut=False)
prot = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
pr("aufraeumen vom Modell wird abgewiesen, Ablage und Protokoll bleiben", "kein Schritt eines Auftrags" in prot and (pathlib.Path(w) / "ablage" / "python").exists() and prot.rstrip().endswith("ENDE"))
pr("aufraeumen fehlt in der Werkzeugliste fuers Modell", "aufraeumen" in werk and "aufraeumen" in agent.NICHT_FUERS_MODELL)
# mehrere Aufrufe in einer Antwort: alle der Reihe nach, dann FERTIG
zustand["n"] = 0
def buendel(verlauf, **kw):
    zustand["n"] += 1
    if zustand["n"] == 1:
        return ('WERKZEUG: schreib_datei {"name": "blink.py", "inhalt": "' + RICHTIG + '"}\n'
                'WERKZEUG: programm_testen {"datei": "blink.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [2], "takt_hz": 1.0}}\n'
                'WERKZEUG: ports_zeigen {}')
    return "FERTIG"
modell.fragen = buendel
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
r = agent.schleife("Schreibe blink.py, pruefe gegen pins [2] und takt_hz 1.0", werk, laut=False)
prot = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
reihe = [z.split()[2] for z in prot.splitlines() if "  RUFT " in z]
pr("drei Aufrufe aus einer Antwort der Reihe nach ausgefuehrt", reihe == ["schreib_datei", "programm_testen", "ports_zeigen"] and "MEHRERE AUFRUFE" in prot, str(reihe))
pr("Modell wurde dafuer nur zweimal gefragt", zustand["n"] == 2)
pr("danach FERTIG angenommen (Datei geschrieben und bestanden)", r.startswith("FERTIG"))
# FERTIG ohne die verlangte Datei: dreimal abgewiesen, dann NICHT ABGENOMMEN
zustand["n"] = 0
def drueckeberger(verlauf, **kw):
    zustand["n"] += 1
    return 'WERKZEUG: ports_zeigen {}' if zustand["n"] == 1 else "FERTIG: alles gut."
modell.fragen = drueckeberger
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
r = agent.schleife("Schreibe blink.py, pruefe gegen pins [2] und takt_hz 1.0", werk, laut=False)
prot = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
pr("FERTIG ohne die verlangte blink.py -> NICHT ABGENOMMEN nach drei Abweisungen", r.startswith("Nicht abgenommen") and "nie geschrieben" in prot and zustand["n"] == 5, f"(Modell {zustand['n']}x gefragt)")
# Aufruf ohne JSON, und FERTIG mit falscher Behauptung
n, e = agent.heraus('WERKZEUG: ports_zeigen', namen); pr("Aufruf ohne JSON gilt als leere Eingabe", n == "ports_zeigen" and e == {})
pr("zerlegen trennt auch vor einem Aufruf ohne JSON", len(agent.zerlegen('WERKZEUG: programm_testen {"datei": "a.py"}\nWERKZEUG: ports_zeigen', namen)) == 2)
# 05.10.2026, 13:33: ein neues Blinkprogramm erbt nicht die Kurvenform des Atmens davor
e_form = agent.erwartung_aus("Schreibe zwei.py: LED an GPIO 2 zweimal je Sekunde und LED an GPIO 4 einmal je Sekunde, gleichzeitig. Pruefe gegen pins [2, 4].", {"pins": [2], "takt_hz": 1.0, "form": "sinusfoermig"})
pr("Erwartung: neues Programm ohne Wort zur Form setzt 'form' zurueck, Pins und Takt neu", e_form == {"pins": [2, 4], "takt_hz": 2.0}, str(e_form))
e_form2 = agent.erwartung_aus("Aendere die Blinkfrequenz auf 2 Hz.", {"pins": [2], "takt_hz": 1.0, "form": "sinusfoermig"})
pr("Erwartung: nur neue Frequenz, kein neues Programm -> Form bleibt (Gegenprobe)", e_form2 == {"pins": [2], "takt_hz": 2.0, "form": "sinusfoermig"}, str(e_form2))
zustand["n"] = 0
def luegner(verlauf, **kw):
    zustand["n"] += 1
    if zustand["n"] == 1: return 'WERKZEUG: schreib_datei {"name": "blink.py", "inhalt": "' + RICHTIG + '"}'
    if zustand["n"] == 2: return 'WERKZEUG: programm_testen {"datei": "blink.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [2], "takt_hz": 1.0}}'
    if zustand["n"] == 3: return 'FERTIG: geschrieben, geprueft und auf den ESP32 ueberspielt.'
    return 'FERTIG: geschrieben und geprueft; das Ueberspielen steht aus.'
modell.fragen = luegner
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
r = agent.schleife("Schreibe blink.py, pruefe gegen pins [2] und takt_hz 1.0", werk, laut=False)
pr("FERTIG mit 'ueberspielt' ohne esp32_uebertragen wird einmal zurueckgewiesen, ehrliches FERTIG angenommen", zustand["n"] == 4 and "steht aus" in r)
# allgemeines Programm: programm_ausfuehren zaehlt als Pruefung — kaputt sperrt FERTIG, gut gibt frei
zustand["n"] = 0
def rechner(verlauf, **kw):
    zustand["n"] += 1
    if zustand["n"] == 1: return 'WERKZEUG: schreib_datei {"name": "rechner.py", "inhalt": "print(1/0)"}'
    if zustand["n"] == 2: return 'WERKZEUG: programm_ausfuehren {"datei": "rechner.py", "sekunden": 5}'
    if zustand["n"] == 3: return 'FERTIG. Der Rechner steht.'
    if zustand["n"] == 4: return 'WERKZEUG: schreib_datei {"name": "rechner.py", "inhalt": "print(2+3)"}'
    if zustand["n"] == 5: return 'WERKZEUG: programm_ausfuehren {"datei": "rechner.py", "sekunden": 5}'
    return 'FERTIG. Der Rechner rechnet 2+3.'
modell.fragen = rechner
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
ev3 = []
r = agent.schleife("Schreibe rechner.py, das 2+3 ausgibt.", werk, laut=False, melden=ev3.append)
urteile = [e.get("abnahme") for e in ev3 if e["art"] == "ergibt" and e["werkzeug"] == "programm_ausfuehren"]
# seit 05.10.2026: auf das FERTIG nach dem kaputten Lauf holt der Berichtigungsfokus die neue Datei und der Agent
# haengt programm_ausfuehren selbst an; der eigene Lauf des Modells kommt danach noch einmal — drei Urteile
pr("allgemeines Programm: kaputter Lauf sperrt FERTIG, Berichtigungsfokus + eigener Lauf, guter Lauf gibt frei", zustand["n"] == 6 and r.startswith("FERTIG. Der Rechner rechnet") and urteile == ["durchgefallen", "bestanden", "bestanden"], str(urteile))
# doppelt maskierte Zeilenumbrueche (7B-Marotte): Agent loest sie auf, Datei ist gueltiges Python, Pruefung laeuft
zustand["n"] = 0
def maskiert(verlauf, **kw):
    zustand["n"] += 1
    if zustand["n"] == 1:
        return 'WERKZEUG: schreib_datei {"name": "m.py", "inhalt": "from machine import Pin\\\\nimport time\\\\nled = Pin(2, Pin.OUT)\\\\nwhile True:\\\\n    led.value(1)\\\\n    time.sleep(0.5)\\\\n    led.value(0)\\\\n    time.sleep(0.5)\\\\n"}'
    if zustand["n"] == 2:
        return 'WERKZEUG: programm_testen {"datei": "m.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [2], "takt_hz": 1.0}}'
    return "FERTIG. m.py bestanden."
modell.fragen = maskiert
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
ev6 = []
r = agent.schleife("Schreibe m.py, LED an GPIO 2 mit 1 Hz, pruefe es.", werk, laut=False, melden=ev6.append)
erg = [e for e in ev6 if e["art"] == "ergibt" and e["werkzeug"] == "schreib_datei"]
pr("doppelt maskierte Zeilenumbrueche werden aufgeloest, Datei geschrieben, Test bestanden, FERTIG", bool(erg) and "doppelt maskiert" in erg[0]["text"] and "geschrieben" in erg[0]["text"] and r.startswith("FERTIG. m.py"), (erg[0]["text"][:80] if erg else ""))
print(f"\n  {sum(f)} von {len(f)} Gegenproben bestanden", flush=True)
shutil.rmtree(w, ignore_errors=True)
sys.exit(0 if all(f) else 1)
