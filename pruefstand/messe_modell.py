"""Misst ein Modell am Pruefstand: ein festes Gespraech mit dem echten Agenten (Sitzung, Werkzeuge,
Regeln), je Anweisung Ergebnis, Werkzeugaufrufe, erfundene Arbeit (Zurueckweisungen), Dauer.

    python3 messe_modell.py <wurzel>          z. B. ../pruefstand_coder3b
Die Wurzel braucht paket/llama (Linux-Server), paket/modell/<ein gguf>, ablage/python.
"""
import sys, os, pathlib, time, json, importlib.util
wurzel = pathlib.Path(sys.argv[1]).resolve()
os.environ["KURS_AGENT_WURZEL"] = str(wurzel)
A = pathlib.Path(__file__).resolve().parent.parent / "agent"; sys.path.insert(0, str(A))
def lade(name):
    sp = importlib.util.spec_from_file_location(name, A / f"{name}.py"); m = importlib.util.module_from_spec(sp); sys.modules[name] = m; sp.loader.exec_module(m); return m
modell = lade("modell"); agent = lade("agent")
GESPRAECH = [
    "hallo bist du bereit?",
    "Wie können wir testen, ob ein Blinkprogramm stimmt? Gibt es zum Beispiel eine LED?",
    "Schreibe blink.py, das die LED an GPIO 2 einmal je Sekunde blinken laesst, und pruefe es.",
    "Aendere die Blinkfrequenz auf 3 Hz.",
    "Schreibe ein Programm atmen.py, das die LED an GPIO 2 per PWM sinusfoermig atmen laesst, eine Periode pro Sekunde. Pruefe es.",
    "Schreibe zwei.py: LED an GPIO 2 zweimal je Sekunde und LED an GPIO 4 einmal je Sekunde, gleichzeitig. Pruefe gegen pins [2, 4].",
    "Programmiere einen einfachen Taschenrechner rechner.py mit tkinter: Anzeige, Ziffern, + - * / = C. Fuehre ihn mit programm_ausfuehren aus (fenster true).",
    "Ist nun alles ok?",
]
ev = []
s = agent.Sitzung(agent.sammlung(), laut=False, melden=ev.append)
zeilen = []; t_ges = time.time()
for i, text in enumerate(GESPRAECH, 1):
    n0 = len(ev); t0 = time.time()
    try:
        r = s.anweisung(text)
    except Exception as e:
        r = f"AUSNAHME {type(e).__name__}: {e}"
    neu = ev[n0:]
    rufe = [e["werkzeug"] for e in neu if e["art"] == "ruft"]
    best = sum(1 for e in neu if e["art"] == "ergibt" and e.get("abnahme") == "bestanden")
    durch = sum(1 for e in neu if e["art"] == "ergibt" and e.get("abnahme") == "durchgefallen")
    fehler = sum(1 for e in neu if e["art"] == "ergibt" and e.get("fehler"))
    zurueck = sum(1 for m in s.verlauf if m["role"] == "user" and (m["content"].startswith("Das ist nicht wahr") or m["content"].startswith("Noch nicht fertig")))
    fokus = sum(1 for e in neu if e["art"] == "hinweis" and "ohne Vorgeschichte" in e.get("text", ""))
    selbst = sum(1 for e in neu if e["art"] == "hinweis" and "prueft" in e.get("text", "") and "selbst" in e.get("text", ""))
    anm = sum(1 for e in neu if e["art"] == "hinweis" and "Anmerkung des Agenten" in e.get("text", ""))
    ende = "FERTIG" if r.startswith("FERTIG") else ("Nicht abgenommen" if r.startswith("Nicht abgenommen") else ("Abbruch" if r.startswith("Abbruch") else "Antwort"))
    zeilen.append({"nr": i, "anweisung": text[:70], "ende": ende, "antwort": r.strip().splitlines()[0][:110], "aufrufe": len(rufe), "werkzeuge": rufe,
                   "bestanden": best, "durchgefallen": durch, "fehler": fehler, "fokus": fokus, "selbst": selbst, "anmerkung": anm, "sekunden": round(time.time() - t0)})
    print(f"[{i}] {ende:16s} {len(rufe):2d} Aufrufe  ✓{best} ✗{durch} F{fehler}  Fokus {fokus} Selbst {selbst} Anm {anm}  {round(time.time()-t0):4d} s  | {r.strip().splitlines()[0][:90]}", flush=True)
    #  nach jeder Anweisung schreiben: am 05.10.2026 ging eine 50-Minuten-Reihe am Ende an einem Namensfehler verloren
    name = (sys.modules["pfade"].eine("modell/*.gguf") or pathlib.Path("?")).name
    ergebnis = {"modell": name, "wurzel": str(wurzel), "agent_stand": time.strftime("%Y-%m-%d %H:%M", time.localtime(A.joinpath("agent.py").stat().st_mtime)),
                "dauer_s": round(time.time() - t_ges), "anweisungen": zeilen, "vollstaendig": i == len(GESPRAECH)}
    (wurzel / "messung.json").write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1), encoding="utf-8")
s.schliessen()
print(f"\n{name}: {ergebnis['dauer_s']} s gesamt; FERTIG {sum(1 for z in zeilen if z['ende']=='FERTIG')}/{len(zeilen)}, Antwort {sum(1 for z in zeilen if z['ende']=='Antwort')}, nicht abgenommen {sum(1 for z in zeilen if z['ende']=='Nicht abgenommen')}; Aufrufe {sum(z['aufrufe'] for z in zeilen)}, bestanden {sum(z['bestanden'] for z in zeilen)}, durchgefallen {sum(z['durchgefallen'] for z in zeilen)}")
