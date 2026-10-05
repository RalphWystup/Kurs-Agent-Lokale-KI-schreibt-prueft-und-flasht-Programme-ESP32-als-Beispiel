"""Prueft die Schleife ohne Sprachmodell: feste Antworten, feste Erwartung.

Geprueft wird der Teil, den ein echtes Modell nur zufaellig ausloest — und der deshalb
sonst unbemerkt kaputtginge: Wird FERTIG zurueckgewiesen, solange die letzte Pruefung
fehlschlug? Und wird es danach angenommen?
"""
import os, sys, pathlib, json
hier = pathlib.Path(".").resolve()
os.environ["KURS_AGENT_WURZEL"] = str(hier)
sys.path.insert(0, str((hier / "../agent").resolve()))
import agent, modell

KAPUTT = ('from machine import Pin\\nimport time\\nled = Pin(2, Pin.OUT)\\n'
          'while True:\\n    led.value(1)\\n    time.sleep(0.5)}')
RICHTIG = ('from machine import Pin\\nimport time\\nled = Pin(2, Pin.OUT)\\nwhile True:\\n'
           '    led.value(1)\\n    time.sleep(0.5)\\n    led.value(0)\\n    time.sleep(0.5)\\n')
LANGSAM = ('from machine import Pin\\nimport time\\nled = Pin(2, Pin.OUT)\\nwhile True:\\n'
           '    led.value(1)\\n    time.sleep(1)\\n    led.value(0)\\n    time.sleep(1)\\n')
PRUEFEN = 'WERKZEUG: programm_testen {"datei": "blink.py", "sekunden": 4, "oeffnen": false, "erwartet": {"pins": [2], "takt_hz": 1.0}}'

ANTWORTEN = [
    f'WERKZEUG: schreib_datei {{"name": "blink.py", "inhalt": "{KAPUTT}"}}',
    PRUEFEN,                                   # -> FEHLER (Syntax)
    'FERTIG\nAlles erledigt.',                 # muss zurueckgewiesen werden
    f'WERKZEUG: schreib_datei {{"name": "blink.py", "inhalt": "{LANGSAM}"}}',
    PRUEFEN,                                   # -> ABNAHME NICHT BESTANDEN (0,5 Hz)
    'FERTIG\nJetzt aber.',                     # muss ebenfalls zurueckgewiesen werden
    f'WERKZEUG: schreib_datei {{"name": "blink.py", "inhalt": "{RICHTIG}"}}',
    PRUEFEN,                                   # -> ABNAHME BESTANDEN
    'FERTIG\nDas Programm blinkt mit 1 Hz und ist geprueft.',   # muss angenommen werden
]
_i = [0]
def fragen(verlauf, **kw):
    a = ANTWORTEN[_i[0]] if _i[0] < len(ANTWORTEN) else "FERTIG"
    _i[0] += 1
    return a

modell.starten = lambda laut=True: None
modell.fragen = fragen
modell.beenden = lambda p: None

erwartet_zurueckgewiesen = 2
ereignisse = []
ergebnis = agent.schleife("Prueflauf", agent.sammlung(), laut=False,
                          melden=lambda e: ereignisse.append(e))

arten = [e["art"] for e in ereignisse]
rufe = [e["werkzeug"] for e in ereignisse if e["art"] == "ruft"]
abn = [e.get("abnahme") for e in ereignisse if e["art"] == "ergibt"]
fertig = [e for e in ereignisse if e["art"] == "fertig"]

print("Antworten verbraucht:", _i[0], "von", len(ANTWORTEN))
print("Werkzeugaufrufe:     ", rufe)
print("Abnahmen:            ", abn)
print("FERTIG angenommen:   ", len(fertig), "mal")
print()
gut = True
def pruefen(was, bedingung):
    global gut
    print(f"  {'OK  ' if bedingung else 'FEHL'}  {was}")
    gut &= bool(bedingung)

pruefen("alle neun Antworten wurden gebraucht (FERTIG wurde zweimal zurueckgewiesen)",
        _i[0] == len(ANTWORTEN))
# seit 05.10.2026: auf jedes FERTIG nach einem Fehlschlag holt der Berichtigungsfokus die neue Datei und der
# Agent prueft sie sofort selbst; der eigene Pruefaufruf des Modells folgt danach noch einmal — acht Aufrufe
pruefen("genau acht Werkzeugaufrufe (3 x schreiben, 5 x pruefen)", len(rufe) == 8)
pruefen("die Reihenfolge stimmt",
        rufe == ["schreib_datei", "programm_testen", "schreib_datei", "programm_testen", "programm_testen",
                 "schreib_datei", "programm_testen", "programm_testen"])
pruefen("erste Pruefung: Fehler (kein Abnahmeurteil)", len(abn) > 1 and abn[1] is None)
pruefen("zweite Pruefung (vom Agenten angehaengt): durchgefallen", len(abn) > 3 and abn[3] == "durchgefallen")
pruefen("letzte Pruefungen: bestanden", len(abn) == 8 and abn[6] == "bestanden" and abn[7] == "bestanden")
pruefen("FERTIG wurde genau einmal angenommen", len(fertig) == 1)
pruefen("und erst nach der bestandenen Abnahme",
        fertig and "1 Hz" in fertig[0]["text"])
print("\n" + ("ALLE PUNKTE ERFUELLT" if gut else "ES GIBT ABWEICHUNGEN"))
raise SystemExit(0 if gut else 1)
