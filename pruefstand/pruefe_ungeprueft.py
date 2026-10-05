"""Prueft: FERTIG gilt nicht nach einer Aenderung, die seit der letzten Pruefung nicht geprueft
wurde (Pruefstand 04.10.2026: dritte Fassung geschrieben, nie geprueft, FERTIG). Aufruf aus
diesem Ordner.
"""
import sys, os, pathlib, tempfile, shutil, importlib.util
w = tempfile.mkdtemp(); os.environ["KURS_AGENT_WURZEL"] = w
A = pathlib.Path(__file__).resolve().parent.parent / 'agent'; sys.path.insert(0, str(A))
def lade(name):
    sp = importlib.util.spec_from_file_location(name, A / f"{name}.py"); m = importlib.util.module_from_spec(sp); sys.modules[name] = m; sp.loader.exec_module(m); return m
modell = lade("modell"); agent = lade("agent")
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
R = "from machine import Pin\\nimport time\\nled = Pin(2, Pin.OUT)\\nwhile True:\\n    led.value(1)\\n    time.sleep(0.5)\\n    led.value(0)\\n    time.sleep(0.5)\\n"
R2 = R.replace("0.5", "0.25")
ANT = ['WERKZEUG: schreib_datei {"name": "blink.py", "inhalt": "' + R + '"}',
       'WERKZEUG: programm_testen {"datei": "blink.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [2], "takt_hz": 1.0}}',
       'WERKZEUG: schreib_datei {"name": "blink.py", "inhalt": "' + R2 + '"}',
       'FERTIG. Alles gut.',                      # muss zurueckgewiesen werden (ungeprueft)
       'WERKZEUG: programm_testen {"datei": "blink.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [2], "takt_hz": 1.0}}',   # 2 Hz -> NICHT BESTANDEN
       'FERTIG. Jetzt.',                          # muss zurueckgewiesen werden (durchgefallen)
       'WERKZEUG: schreib_datei {"name": "blink.py", "inhalt": "' + R + '"}',
       'WERKZEUG: programm_testen {"datei": "blink.py", "sekunden": 3, "oeffnen": false, "erwartet": {"pins": [2], "takt_hz": 1.0}}',
       'FERTIG. Geprueft.']                       # angenommen
i = [0]
def fragen(v, **k):
    a = ANT[i[0]] if i[0] < len(ANT) else "FERTIG"; i[0] += 1; return a
modell.starten = lambda laut=True: None; modell.beenden = lambda p: None; modell.fragen = fragen
ev = []
r = agent.schleife("Schreibe blink.py, pruefe gegen pins [2] und takt_hz 1.0", agent.sammlung(), laut=False, melden=ev.append)
prot = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
f = []
def pr(b, ok, info=""): print(f"  {'OK  ' if ok else 'FEHL'} {b} {info}"); f.append(ok)
pr("alle neun Antworten gebraucht", i[0] == 9)
pr("FERTIG genau einmal angenommen", prot.count("FERTIG\n") == 1 and r.startswith("FERTIG. Geprueft"))
pr("Protokoll traegt Urteile", "ABNAHME BESTANDEN" in prot and "ABNAHME NICHT BESTANDEN" in prot)
# dreimal FERTIG nach ungeprueftem Schreiben: Lauf endet als NICHT ABGENOMMEN, nicht als FERTIG
ANT2 = ['WERKZEUG: schreib_datei {"name": "blink.py", "inhalt": "' + R2 + '"}', 'FERTIG', 'FERTIG', 'FERTIG', 'FERTIG']
i[0] = 0; ANT[:] = ANT2
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
r2 = agent.schleife("Schreibe blink.py, pruefe gegen pins [2] und takt_hz 1.0", agent.sammlung(), laut=False)
prot2 = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
pr("FERTIG ohne Pruefung, 2-Hz-Programm -> Agent prueft selbst, faellt durch, Ende NICHT ABGENOMMEN", r2.startswith("Nicht abgenommen") and "AGENT PRUEFT SELBST" in prot2 and "NICHT ABGENOMMEN" in prot2 and "\nFERTIG" not in prot2.replace("ABGENOMMEN", ""))
pr("sieben Modellantworten bis zum Ende (2 Abweisungen, Selbstpruefung, 3 Abweisungen)", i[0] == 7, f"({i[0]})")
# Modell schreibt und sagt nur noch FERTIG: der Agent prueft selbst, dann gilt FERTIG (bei bestandener Pruefung)
ANT3 = ['WERKZEUG: schreib_datei {"name": "blink.py", "inhalt": "' + R + '"}', 'FERTIG', 'FERTIG', 'FERTIG. Dann eben jetzt.']
i[0] = 0; ANT[:] = ANT3; ev4 = []
shutil.rmtree(pathlib.Path(w) / "ablage", ignore_errors=True)
shutil.copytree(str(pathlib.Path(__file__).resolve().parent / "ablage" / "python"), pathlib.Path(w) / "ablage" / "python", symlinks=True)
r3 = agent.schleife("Schreibe blink.py, pruefe gegen pins [2] und takt_hz 1.0", agent.sammlung(), laut=False, melden=ev4.append)
prot3 = (pathlib.Path(w) / "ablage" / "protokoll.txt").read_text(encoding="utf-8")
selbst = [e for e in ev4 if e["art"] == "ruft" and e["werkzeug"] == "programm_testen"]
pr("FERTIG ohne Pruefung: Agent prueft selbst (programm_testen mit der Erwartung des Menschen), danach FERTIG", "AGENT PRUEFT SELBST" in prot3 and selbst and selbst[0]["eingabe"].get("erwartet") == {"pins": [2], "takt_hz": 1.0} and r3.startswith("FERTIG. Dann"))
print(f"  {sum(f)} von {len(f)}"); shutil.rmtree(w, ignore_errors=True); sys.exit(0 if all(f) else 1)
