#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Der Agent: Auftrag — Modell — Werkzeug — Ergebnis — und wieder von vorn.

Ein Agent ist kein Programm, das etwas weiss. Er ist eine Schleife:

    1  Verlauf und Werkzeugliste an das Modell geben
    2  aus der Antwort einen Werkzeugaufruf herauslesen
    3  das Werkzeug als eigenes Programm starten
    4  dessen Ausgabe — Erfolg **oder** Fehler — in den Verlauf schreiben
    5  zurueck zu 1, bis das Modell FERTIG meldet

Mehr ist es nicht. Alles Koennen steckt in den Werkzeugen, alles Urteilsvermoegen im
Modell, und dieses Programm haelt beides auseinander. Genau deshalb kann man die
Werkzeuge ohne Modell pruefen und das Modell ohne Hardware wechseln.

Entscheidend fuer Punkt 4: Ein Fehler ist kein Abbruch, sondern eine Nachricht. Ein
Modell, das erfaehrt „pyserial fehlt", installiert pyserial. Ein Modell, dessen Agent
abstuerzt, erfaehrt gar nichts.

Zwei Betriebsarten:

    agent.py "<Auftrag>"     mit Modell — das Modell entscheidet
    agent.py --drehbuch      ohne Modell — feste Reihenfolge, damit der Kurs auch dann
                             laeuft, wenn das Modell im Raum klemmt
"""
from __future__ import annotations
import json, re, subprocess, sys, datetime, pathlib
import os

# Der eigene Ordner muss in den Suchpfad, bevor etwas daraus geholt wird. Unter einem
# gewoehnlichen Python steht er von selbst darin — beim eingebetteten Python nicht: dort
# legt die Datei python3xx._pth den Suchpfad abschliessend fest. Ein Import, der auf dem
# Entwicklungsrechner selbstverstaendlich gelingt, scheitert dann auf dem Kursrechner.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# Die Windows-Konsole gibt sonst Fragezeichen statt Umlauten und Gedankenstrichen aus — der
# Standard dort ist keine UTF-8-Codepage. Das Startskript setzt zwar chcp 65001, aber ein
# Werkzeug, das jemand einzeln aufruft, laeuft ohne dieses Startskript.
for _strom in (sys.stdout, sys.stderr):
    try:
        _strom.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import sauber
sauber.sicherstellen()   # vor allem anderen: saubere Umgebung

import waechter
from pfade import ABLAGE, PAKET, PROTOKOLL, WERKSTATT, WURZEL, umgebung

WERKZEUGE = pathlib.Path(__file__).resolve().parent / "werkzeuge"
# Siehe LESEN in _muster.py: ohne diese Angabe liest Windows cp1252 und verliert die
# gesamte Ausgabe, sobald ein Zeichen darin nicht vorkommt.
LESEN = {"encoding": "utf-8", "errors": "replace"}
MAX_SCHRITTE = 25

ANWEISUNG = """Du bist ein Agent an einem Windows-Rechner. Du steuerst ihn ausschliesslich
ueber die unten aufgefuehrten Werkzeuge; etwas anderes kannst du nicht tun.

So rufst du ein Werkzeug auf — eine Zeile, sonst nichts in dieser Zeile:

WERKZEUG: <name> {"feld": "wert"}

Erlaubt sind genau diese Namen: {namen}
Erfinde keinen anderen Namen. Rufe hoechstens ein Werkzeug je Antwort auf.
Du bekommst darauf das Ergebnis und entscheidest dann weiter.

Der uebliche Ablauf, wenn ein Programm fuer den ESP32 verlangt ist:

    1  schreib_datei      das Programm anlegen
    2  programm_testen    SOFORT danach, mit "erwartet" — ohne Hardware pruefen
    3  bei NICHT BESTANDEN zurueck zu 1, sonst weiter
    4  ports_zeigen       welcher Anschluss
    5  esp32_firmware     MicroPython aufspielen
    6  esp32_uebertragen  die geprueffte Datei auf das Geraet
    7  esp32_nachlesen    am Geraet messen, ob es wirklich blinkt — erst dann FERTIG

Schritt 2 folgt immer unmittelbar auf Schritt 1.

Ist KEIN ESP32-Programm verlangt — ein Rechner, ein Skript, ein Programm mit Fenster —, dann:

    1  schreib_datei          das Programm anlegen
    2  programm_ausfuehren    SOFORT danach: laeuft es, stimmt die Ausgabe? Fuer ein Programm mit
                              grafischer Oberflaeche (tkinter) mit "fenster": true
    3  bei LAUF NICHT BESTANDEN zurueck zu 1 (die letzte Zeile der Fehlerausgabe nennt die Ursache)
    4  bei LAUF BESTANDEN: fuer ein Fensterprogramm zuletzt programm_ausfuehren mit
       "offen_lassen": true, damit der Mensch es benutzen kann — dann erst das Wort FERTIG

Fuer die grafische Oberflaeche nimm tkinter (import tkinter as tk); es liegt im Paket.

Du antwortest frei. Stellt der Mensch eine Aufgabe, loese sie mit den Werkzeugen, ein Aufruf
je Antwort. Gruesst er, fragt er oder bemerkt er etwas, antworte ihm in Worten — kurz, ehrlich,
ohne Werkzeug. Erfinde keine Aufgabe, die niemand gestellt hat. Bist du mit einer Anweisung
fertig, schreibe FERTIG und darunter in wenigen Saetzen, was geschehen ist.

Fragt der Mensch, was du kannst oder wie etwas geprueft wird, erklaere es konkret mit den
Werkzeugen, nicht allgemein: Ein Programm fuer den ESP32 schreibst du mit schreib_datei und
pruefst es ohne Hardware mit programm_testen gegen eine Erwartung (welche Anschluesse, welcher
Takt); eine LED am Brett misst esp32_nachlesen direkt am Geraet, nachdem esp32_uebertragen das
Programm hinueberkopiert hat; welcher Anschluss da ist, zeigt ports_zeigen. Nenne, was du
dafuer vom Menschen brauchst (Anschluss, gewuenschter Takt), statt es zu raten.

Achtung: Wenn der Auftrag ein Programm verlangt, ist der erste Aufruf IMMER schreib_datei.
Dass im Auftrag auch programm_testen steht, heisst nicht, dass es zuerst kommt — es kann
nichts pruefen, was noch nicht geschrieben ist.

Was du ueber das Brett weisst (ESP32-DevKit, MicroPython):
- Die eingebaute blaue LED haengt an GPIO 2: machine.Pin(2, machine.Pin.OUT). Weitere LEDs
  schliesst man extern an freie Anschluesse an (z. B. GPIO 4, 5, 16-19, 21-23, 25-27, 32, 33),
  mit Vorwiderstand gegen Masse.
- Helligkeit regelt man mit PWM: machine.PWM(machine.Pin(2), freq=1000) und duty(0 bis 1023)
  oder duty_u16(0 bis 65535). Ein weiches Atmen ist eine Folge von duty-Werten, z. B. einer
  Sinus-Halbwelle, im Takt der gewuenschten Periode.
- Tasten, Sensoren und Anzeigen gibt es nur, wenn der Mensch sie angeschlossen hat; frage nach,
  statt sie anzunehmen.

Die Werkzeuge im Einzelnen:
{liste}

Regeln:
- Ein Fehler ist kein Grund aufzuhoeren. Lies ihn, behebe die Ursache, versuche es erneut.
- Nachdem du ein Programm geschrieben hast, pruefe es IMMER zuerst mit programm_testen.
  Erst wenn es dort tut was es soll, darf es auf den ESP32. Ein Programm, das im Test
  abbricht, bricht auf der Hardware genauso ab — nur siehst du es dort nicht.
- Gib beim Testen immer "erwartet" an: welche Anschluesse geschaltet werden sollen und mit
  welchem Takt. Steht die Erwartung im Auftrag (pins, takt_hz), gilt genau sie — aendere nie
  die Erwartung, damit das Programm besteht; aendere das Programm. Ohne Erwartung ist der Lauf nur eine Vorfuehrung und kann nicht durchfallen;
  erst der Vergleich mit dem, was du angekuendigt hast, ist eine Pruefung.
- Bricht programm_testen ab oder meldet NICHT BESTANDEN, lies die Befunde, berichtige den
  Quelltext mit schreib_datei und pruefe erneut. Erst nach BESTANDEN geht es weiter.
- Pruefe vor dem Flashen mit ports_zeigen, welcher Anschluss da ist. Rate keinen.
- Ist keine Hardware da oder antwortet kein ESP32, ist der Auftrag mit einem bestandenen
  programm_testen trotzdem erfuellt. Sage dann, dass das Ueberspielen aussteht.
- Schreibe FERTIG erst, wenn das Ziel der Anweisung wirklich erreicht ist — bei einem Programm
  also, wenn es geschrieben UND geprueft wurde. Darunter in zwei bis fuenf Saetzen, was geschehen
  ist. Behaupte nichts, was kein Werkzeug getan hat.
"""


def sammlung() -> dict:
    """Fragt jedes Werkzeugprogramm, was es kann. Die Liste entsteht nicht hier,
    sondern in den Werkzeugen selbst — ein neues Werkzeug ist eine neue Datei."""
    w = {}
    for d in sorted(WERKZEUGE.glob("*.py")):
        if d.name.startswith("_"):
            continue
        r = subprocess.run([sys.executable, str(d), "--beschreibung"],
                           capture_output=True, text=True, timeout=60, env=umgebung(), **LESEN)
        if r.returncode == 0 and r.stdout.strip():
            try:
                b = json.loads(r.stdout)
                b["datei"] = d
                w[b["name"]] = b
            except json.JSONDecodeError:
                print(f"  (uebergangen: {d.name} liefert kein gueltiges JSON)")
    return w


def ausfuehren(name: str, eingabe: dict, werkzeuge: dict) -> str:
    if name not in werkzeuge:
        return (f"FEHLER: '{name}' gibt es nicht. Waehlbar sind: {', '.join(sorted(werkzeuge))}.")
    r = subprocess.run([sys.executable, str(werkzeuge[name]["datei"]),
                        json.dumps(eingabe, ensure_ascii=False)],
                       capture_output=True, text=True, timeout=1800, env=umgebung(), **LESEN)
    return (r.stdout or r.stderr or "(keine Ausgabe)").strip()


# Werkzeuge, die das Modell nicht aufrufen darf (siehe schleife): sie beenden den Lauf selbst.
NICHT_FUERS_MODELL = {"aufraeumen"}

# Das JSON ist freiwillig: "WERKZEUG: ports_zeigen" ohne Klammern gilt als leere Eingabe. Am
# 04.10.2026 (14:07) hing ein solcher Aufruf hinter programm_testen und ging verloren.
AUFRUF = re.compile(r"WERKZEUG:\s*([A-Za-z_][A-Za-z0-9_]*)[ \t]*(\{.*|$)", re.M | re.S)


def heraus(text: str, namen=()):
    """Liest einen Werkzeugaufruf aus der Antwort — auch wenn ein Codeblock drumherum steht.

    Kleine Modelle verpacken ihre Antwort gern in ```…```. Das ist kein Fehler des Modells,
    sondern eine Eigenheit, auf die der Parser vorbereitet sein muss.

    Seit 04.10.2026 auch ohne das Wort WERKZEUG: Das 3B-Modell schrieb auf dem Laptop dreimal
    hintereinander nur 'schreib_datei {...}'. Der Name eines bekannten Werkzeugs am
    Zeilenanfang, gefolgt von JSON, ist eindeutig genug — die Datei blieb sonst ungeschrieben,
    und die Pruefung lief gegen eine alte aus der Nacht davor."""
    sauber = re.sub(r"```[a-zA-Z]*\n?|```", "", text)
    t = AUFRUF.search(sauber)
    if not t and namen:
        t = re.search(r"(?m)^[ \t]*(" + "|".join(re.escape(n) for n in sorted(namen)) + r")[ \t]*(\{.*|$)",
                      sauber, re.S)
    if not t:
        return None, None
    name, rest = t.group(1), t.group(2)
    if not rest.strip():
        return name, {}
    # Wo das JSON endet, entscheidet der JSON-Leser selbst. Klammern von Hand zu zaehlen
    # scheitert, sobald eine } **innerhalb** einer Zeichenkette steht — und genau das ist
    # der Normalfall, wenn das Modell Quelltext uebergibt.
    try:
        wert, _ = json.JSONDecoder().raw_decode(rest)
        return name, wert if isinstance(wert, dict) else {"__fehler": "erwartet wird ein JSON-Objekt"}
    except json.JSONDecodeError as e:
        return name, {"__fehler": f"kein gueltiges JSON: {e}"}


def zerlegen(text: str, namen=()) -> list:
    """Teilt eine Antwort mit mehreren Werkzeugaufrufen in einzelne Antworten.

    Qwen2.5-Coder-3B schrieb am 04.10.2026 (14:02) vier Aufrufe in eine Antwort. Der Agent
    nahm nur den ersten, das Modell bekam dreimal dasselbe Ergebnis und gab auf. Hier wird
    an jedem Zeilenanfang getrennt, an dem ein neuer Aufruf beginnt; der erste Teil wird sofort
    ausgefuehrt, die uebrigen folgen der Reihe nach, ohne das Modell erneut zu fragen."""
    sauber = re.sub(r"```[a-zA-Z]*\n?|```", "", text)
    muster = (r"(?m)^[ \t]*(?:WERKZEUG:\s*[A-Za-z_][A-Za-z0-9_]*|(?:" + "|".join(re.escape(n) for n in sorted(namen)) + r"))[ \t]*(?:\{|$)"
              if namen else r"(?m)^[ \t]*WERKZEUG:\s*[A-Za-z_][A-Za-z0-9_]*[ \t]*(?:\{|$)")
    anfaenge = [m.start() for m in re.finditer(muster, sauber)]
    if len(anfaenge) <= 1:
        return [text]
    teile = [sauber[a:b].strip() for a, b in zip(anfaenge, anfaenge[1:] + [len(sauber)])]
    return [x for x in teile if x]


def beurteilen(ergebnis: str) -> dict:
    """Wie ein Werkzeugergebnis zu lesen ist: Fehler? Abnahme bestanden oder nicht?

    Diese Beurteilung steht hier und sonst nirgends. Als die Oberflaeche sie ein zweites
    Mal — und dabei unvollstaendig — vornahm, zeigte sie bei bestandener Abnahme keine
    Marke an: derselbe Lauf, zwei Urteile.
    """
    return {"fehler": ergebnis.startswith("FEHLER"),
            "abnahme": ("bestanden" if ("ABNAHME BESTANDEN" in ergebnis or "LAUF BESTANDEN" in ergebnis)
                        else "durchgefallen" if ("ABNAHME NICHT BESTANDEN" in ergebnis or "LAUF NICHT BESTANDEN" in ergebnis)
                        else None)}



def kuerzen(ergebnis: str, kopf=20, fuss=8, hoechstens=2500) -> str:
    """Was ins Gedaechtnis des Modells geht: Anfang und Ende, nicht jeden Zustandswechsel.

    programm_testen liefert je Lauf ueber hundert Zeilen Zeitachse. Nach 23 Schritten war
    das Kontextfenster (8192) am 04.10.2026 voll — HTTP 400, Lauf zu Ende. Die Oberflaeche
    und das Protokoll bekommen weiterhin alles; nur das Modell liest die Kurzfassung."""
    zeilen = ergebnis.splitlines()
    if len(zeilen) > kopf + fuss + 2:
        zeilen = zeilen[:kopf] + [f"    … ({len(zeilen) - kopf - fuss} Zeilen ausgelassen) …"] + zeilen[-fuss:]
    kurz = "\n".join(zeilen)
    return kurz if len(kurz) <= hoechstens else kurz[:hoechstens - 20] + "\n    … (gekuerzt)"


def zusammenfassen(verlauf: list, getan: list, letzter_befund) -> list:
    """Wenn das Kontextfenster trotzdem voll ist: Anweisung und Auftrag bleiben, die
    letzten sechs Nachrichten bleiben, alles dazwischen wird ein Satz."""
    if len(verlauf) <= 8:
        return verlauf
    satz = (f"Zusammenfassung der bisherigen Schritte (aeltere Nachrichten gekuerzt): "
            f"gelaufene Werkzeuge: {', '.join(getan) or 'keine'}. "
            f"Stand der letzten Pruefung: {letzter_befund or 'bestanden oder noch keine'}. "
            f"Mach mit dem naechsten noetigen Schritt weiter.")
    return verlauf[:2] + [{"role": "user", "content": satz}] + verlauf[-6:]


def fehlerbericht(fehler: BaseException, auftrag: str) -> pathlib.Path:
    """Eine Datei, die ohne den Erbauer weiterhilft: Was lief, was brach, womit.

    Der Kurs laeuft auf fremden Rechnern ohne Netz. Bricht dort etwas, gibt es keinen, der
    zusieht — nur diese Datei. Anweisung vom 04.10.2026: „nur ein Fehlerprotokoll waere dann
    hilfreich." Das Protokoll selbst endete an dem Tag 35 Sekunden vor dem Abbruch."""
    import platform, traceback
    ABLAGE.mkdir(parents=True, exist_ok=True)
    ziel = ABLAGE / "fehlerbericht.txt"
    try:
        import modell as _m
        modellname = (_m.eine("modell/*.gguf") or pathlib.Path("keins")).name
        sac = _m.signaturpflicht()[0] if os.name == "nt" else "nicht Windows"
    except Exception as e:                       # der Bericht darf nicht selbst scheitern
        modellname, sac = f"unbekannt ({e})", "unbekannt"
    try:
        letzte = PROTOKOLL.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
    except OSError:
        letzte = ["(kein Protokoll)"]
    text = "\n".join([
        f"FEHLERBERICHT Kurs-Agent — {datetime.datetime.now():%d.%m.%Y %H:%M:%S}",
        f"Auftrag:  {auftrag}",
        f"Fehler:   {type(fehler).__name__}: {fehler}",
        f"Rechner:  {platform.platform()}  Python {platform.python_version()}",
        f"Wurzel:   {WURZEL}",
        f"Modell:   {modellname}",
        f"Signaturpflicht (Smart App Control): {sac}",
        "",
        "Rueckverfolgung:",
        traceback.format_exc(),
        "Die letzten 40 Protokollzeilen:",
        *letzte,
        "",
        "Was jetzt hilft: diese Datei und ablage\\protokoll.txt dem Dozenten geben; START.bat",
        "erneut starten — der Agent beginnt von vorn, nichts ist verloren.",
    ])
    ziel.write_text(text, encoding="utf-8")
    return ziel


def notieren(zeile: str):
    ABLAGE.mkdir(parents=True, exist_ok=True)
    with PROTOKOLL.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%H:%M:%S}  {zeile}\n")


class Belegt(Exception):
    """Ein zweiter Lauf im selben Ordner — das geht schief, und zwar unbemerkt."""


class Sperre:
    """Sorgt dafuer, dass nur ein Lauf je Ordner arbeitet.

    Zwei gleichzeitige Laeufe teilen sich eine Werkstatt: der eine schreibt blink.py,
    waehrend der andere es prueft. Das Ergebnis sieht dann richtig aus und gehoert zu
    einem anderen Programm — ein Fehler, der niemandem auffaellt, weil nichts abstuerzt.
    Im Kurs passiert das, sobald jemand zwei Fenster oeffnet.
    """

    def __init__(self):
        self.datei = ABLAGE / "laeuft.pid"

    def __enter__(self):
        ABLAGE.mkdir(parents=True, exist_ok=True)
        if self.datei.is_file():
            alt = self.datei.read_text(encoding="utf-8").strip()
            if _lebt(alt):
                raise Belegt(f"In diesem Ordner laeuft bereits ein Agent (Prozess {alt}). "
                             f"Zwei Laeufe teilen sich die Werkstatt und verfaelschen sich "
                             f"gegenseitig die Ergebnisse. Warte, bis der erste fertig ist — "
                             f"oder loesche {self.datei}, wenn kein Agent mehr laeuft.")
        self.datei.write_text(str(os.getpid()), encoding="utf-8")
        return self

    def __exit__(self, *a):
        try:
            if self.datei.is_file() and self.datei.read_text(encoding="utf-8").strip() == str(os.getpid()):
                self.datei.unlink()
        except OSError:
            pass


def _lebt(pid: str) -> bool:
    """Laeuft dieser Prozess noch? Unter Windows ueber die Prozessliste, nicht ueber
    os.kill — dort wuerde jedes Signal den Prozess beenden statt ihn zu befragen."""
    if not pid.isdigit():
        return False
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True)
        return pid in (r.stdout or "")
    #  Ein Zombie (Zustand Z) hat zwar noch einen Eintrag, lebt aber nicht — er hielt am
    #  04.10.2026 auf dem Pruefstand eine Sperre fest, die niemandem mehr gehoerte.
    stat = pathlib.Path(f"/proc/{pid}/stat")
    if not stat.exists():
        return False
    try:
        return stat.read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def erwartung_aus(text: str, bisher=None):
    """Liest die Erwartung aus den Worten des Menschen — und fuehrt sie ueber Anweisungen fort.

    Formen: 'pins [2, 4]' und 'takt_hz 1.0' (die technische Schreibweise), 'GPIO 4' oder 'Pin 4',
    '10 Hz', 'zehnmal je Sekunde' als '10 mal je Sekunde'. Sagt der Mensch spaeter nur „anderer
    Pin: GPIO 4", bleibt der Takt von vorher — die Erwartung setzt der Mensch, Stueck fuer Stueck.
    Am 04.10.2026 schrieb das 3B-Modell die Erwartung von 1,0 auf 0,5 Hz um, damit sein Programm
    besteht — eine Pruefung, deren Massstab der Gepruefte selbst setzt, ist keine."""
    e = dict(bisher or {})
    p = re.search(r"pins?\s*\[([\d,\s]*)\]", text)
    if p:
        e["pins"] = [int(x) for x in p.group(1).split(",") if x.strip()]
    else:
        g = re.findall(r"\b(?:GPIO|Pin|Anschluss)\s*(\d{1,2})\b", text)
        if g:
            e["pins"] = sorted({int(x) for x in g})
    tk = (re.search(r"takt_hz\s*(\d+(?:[.,]\d+)?)", text)
          or re.search(r"(\d+(?:[.,]\d+)?)\s*Hz\b", text)
          or re.search(r"(\d+(?:[.,]\d+)?)\s*-?\s*(?:mal|Perioden?)? ?(?:je|pro|in der) Sekunde", text))
    if tk:
        e["takt_hz"] = float(tk.group(1).replace(",", "."))
    else:
        #  „eine Periode pro Sekunde", „einmal je Sekunde", „zweimal pro Sekunde" (05.10.2026, 9:44:
        #  das Zahlwort wurde ueberlesen, und das Modell setzte 1000 Hz).
        ZAHLWORT = {"ein": 1, "eine": 1, "einer": 1, "einmal": 1, "zwei": 2, "zweimal": 2, "drei": 3, "dreimal": 3,
                    "vier": 4, "viermal": 4, "fuenf": 5, "fünf": 5, "fuenfmal": 5, "fünfmal": 5, "zehn": 10, "zehnmal": 10}
        zw = re.search(r"\b(" + "|".join(ZAHLWORT) + r")\b\s*(?:mal|Perioden?|Blink\w*)?\s*(?:je|pro|in der) Sekunde", text, re.I)
        if zw:
            e["takt_hz"] = float(ZAHLWORT[zw.group(1).lower()])
    if re.search(r"sinus", text, re.I):
        e["form"] = "sinusfoermig"
    elif re.search(r"dreieck", text, re.I):
        e["form"] = "dreieckig"
    return e or None


class Sitzung:
    """Ein Gespraech mit dem Agenten: mehrere Anweisungen, ein Zusammenhang.

    Bis zum 04.10.2026 war jeder Auftrag ein eigener Lauf mit leerem Gedaechtnis. Der
    Auftraggeber: „Am Ende muss wie auch hier immer die Moeglichkeit zur Eingabe der naechsten
    Anweisung bestehen … verwende einen anderen Pin, aendere die Blinkfrequenz, pruefe zuerst,
    bevor du das Programm runterlaedst, oder ich gebe selbst ein Programm ein." Dafuer bleibt
    hier alles stehen: der Verlauf fuer das Modell, was geschrieben, geprueft und abgenommen
    ist, welche Anschluesse der Mensch genannt hat, und der Modellserver — er wird nicht fuer
    jede Anweisung neu geladen.

    Was der Mensch sagt, gilt ueber das Modell hinweg: die Erwartung (Pins, Takt), die
    Dateinamen, der Anschluss. Was das Modell behauptet, muss ein Werkzeug getan haben.
    """

    def __init__(self, werkzeuge: dict, laut=True, melden=None):
        import modell
        self.modell, self.werkzeuge, self.laut, self.melden = modell, werkzeuge, laut, melden
        #  aufraeumen gehoert nicht in die Hand des Modells: Es beendet den Modellserver und loescht
        #  die Ablage samt Protokoll — mitten im Auftrag (Pruefstand 04.10.2026, 11:21).
        fuers_modell = {n: w for n, w in werkzeuge.items() if n not in NICHT_FUERS_MODELL}
        self.namen = ", ".join(sorted(fuers_modell))
        liste = "\n".join(f"- {n}: {w['description']}\n  Felder: "
                          f"{json.dumps(w['input_schema']['properties'], ensure_ascii=False)}"
                          for n, w in sorted(fuers_modell.items()))
        # Nicht .format(): die Anweisung enthaelt JSON-Beispiele mit geschweiften Klammern.
        anweisung = ANWEISUNG.replace("{namen}", self.namen).replace("{liste}", liste)
        self.verlauf = [{"role": "system", "content": anweisung}]
        self.gesehen, self.getan = {}, []
        self.letzter_befund = None
        self.feste_erwartung = None                 # der Mensch setzt den Massstab
        self.geschrieben: set = set()               # in dieser Sitzung geschrieben
        self.ungeprueft: set = set()                # geschrieben, seitdem nicht geprueft
        self.abgenommen: set = set()                # zuletzt geprueft und bestanden, seitdem unveraendert
        self.verlangt: list = []                    # Dateien, die der Mensch nannte
        self.genannte_ports: set = set()            # Anschluesse, die der Mensch nannte
        self.anweisungen = 0
        self.zwischenrufe: list = []                # Eingaben waehrend eines Laufs (Quereingabe)
        self._schloss = __import__("threading").Lock()
        self.sperre = None
        self.server = None
        self.ohne_modell = False
        self.offen = False

    # ------------------------------------------------------------------ Hilfen
    def sagen(self, art, **d):
        if self.melden:
            try:
                self.melden(dict(art=art, **d))
            except Exception:
                pass          # eine Oberflaeche darf den Lauf nie zum Scheitern bringen

    def oeffnen(self):
        self.sperre = Sperre().__enter__()
        self.offen = True
        notieren("SITZUNG BEGINNT")

    def schliessen(self):
        if not self.offen:
            return
        if waechter.verstoesse():
            print("\n" + waechter.bericht())
        self.modell.beenden(self.server)
        self.server = None
        self.sperre.__exit__()
        self.offen = False
        notieren("ENDE")
        self.sagen("modell_beendet")

    def _modell_bereit(self) -> bool:
        if self.ohne_modell:
            return False
        if self.server is not None and self.server.poll() is None:
            return True
        self.sagen("modell_laedt")
        try:
            self.server = self.modell.starten(laut=self.laut)
        except self.modell.KeinModell as e:
            #  Kein Modell ist kein Ende (Anforderung A6): Grund in Worten, dann Drehbuch.
            grund = str(e)
            notieren(f"KEIN MODELL {grund.splitlines()[0][:160]}")
            self.sagen("kein_modell", text=grund)
            if self.laut:
                print(f"\nKein Modell: {grund}\n\nWeiter ohne Modell — mit dem Drehbuch:")
            self.ohne_modell = True
            return False
        self.sagen("modell_bereit")
        return True

    def zwischenruf(self, text: str):
        """Eine Eingabe, waehrend der Agent arbeitet — „eine Quereingabe muss moeglich sein"
        (04.10.2026). Sie wird eingereiht und beim naechsten Schritt aufgenommen: der Mensch
        nennt den Anschluss, aendert die Erwartung oder korrigiert, ohne auf das Ende zu warten."""
        with self._schloss:
            self.zwischenrufe.append(text.strip())

    def _zwischenrufe_aufnehmen(self):
        with self._schloss:
            neu, self.zwischenrufe = self.zwischenrufe[:], []
        for text in neu:
            if not text:
                continue
            notieren(f"ZWISCHENRUF {text}")
            self.sagen("auftrag", text=text, zwischenruf=True)
            self._vom_menschen(text)
            self.verlauf.append({"role": "user", "content": f"Zwischenruf des Menschen: {text}"})
        return bool(neu)

    def _vom_menschen(self, text: str):
        """Was der Mensch sagt, wird festgehalten, bevor das Modell es zu sehen bekommt."""
        vorher = self.feste_erwartung
        self.feste_erwartung = erwartung_aus(text, self.feste_erwartung)
        if vorher is not None and self.feste_erwartung != vorher:
            #  Neue Erwartung, alte Abnahme: „Verwende GPIO 4" — und das Modell sagte FERTIG, weil
            #  blink.py gegen GPIO 2 bestanden hatte (Pruefstand 04.10.2026, 12:28). Was gegen den
            #  alten Massstab bestand, ist gegen den neuen ungeprueft.
            #  Betroffen ist die Datei, von der gerade die Rede ist — die genannte, sonst die zuletzt
            #  verlangte. Ein neues Programm mit eigener Erwartung macht die alten nicht ungeprueft.
            genannt = set(re.findall(r"\b([\w-]+\.py)\b", text)) or ({self.verlangt[-1]} if self.verlangt else set())
            betroffen = genannt & (self.abgenommen | self.geschrieben)
            self.ungeprueft |= betroffen
            self.abgenommen -= betroffen
            self.letzter_befund = None
        for n in re.findall(r"\b([\w-]+\.py)\b", text):
            if n not in self.verlangt:
                self.verlangt.append(n)
        #  „nein es ist com 3 nicht com 5" (04.10.2026, 19:57): mit Leerzeichen, klein geschrieben —
        #  der Mensch schreibt, wie er spricht. Alles davon heisst COM3.
        self.genannte_ports |= {"COM" + z for z in re.findall(r"\bCOM\s*(\d{1,3})\b", text, re.I)}
        self.genannte_ports |= set(re.findall(r"(/dev/tty[A-Za-z0-9]+)", text))

    def _eigenes_programm(self, text: str, schritt=0):
        """Gibt der Mensch selbst ein Programm ein (```…```), schreibt der Agent es — woertlich.

        „… oder ich gebe selbst ein Programm ein zum Ueberpruefen" (04.10.2026). Ein kleines
        Modell wuerde den Quelltext beim Abschreiben veraendern; deshalb geht er hier ohne Umweg
        in die Werkstatt, und das Modell bekommt gesagt, dass die Datei schon liegt."""
        block = re.search(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S)
        if not block:
            return None
        name = next(iter(re.findall(r"\b([\w-]+\.py)\b", text)), "eingabe.py")
        eingabe = {"name": name, "inhalt": block.group(1)}
        self.sagen("ruft", schritt=schritt, werkzeug="schreib_datei", eingabe=eingabe, vom_menschen=True)
        notieren(f"RUFT schreib_datei (vom Menschen eingegeben) {json.dumps({'name': name}, ensure_ascii=False)}")
        ergebnis = ausfuehren("schreib_datei", eingabe, self.werkzeuge)
        notieren(f"ERGIBT {ergebnis.splitlines()[0] if ergebnis else ''}")
        self.sagen("ergibt", schritt=schritt, werkzeug="schreib_datei", text=ergebnis, **beurteilen(ergebnis))
        if not ergebnis.startswith("FEHLER"):
            self.geschrieben.add(name); self.ungeprueft.add(name); self.abgenommen.discard(name)
            self.getan.append("schreib_datei")
        return name, ergebnis

    def _pruefaufruf(self, datei: str) -> str:
        """Der passende Pruefaufruf fuer eine Datei: ESP32-Programme (machine) mit programm_testen
        gegen die Erwartung des Menschen, alles andere mit programm_ausfuehren (Fenster erkannt
        an tkinter)."""
        try:
            quelle = (WERKSTATT / datei).read_text(encoding="utf-8", errors="replace")
        except OSError:
            quelle = ""
        if "machine" in quelle or self.feste_erwartung:
            e = {"datei": datei, "sekunden": 6, "oeffnen": False}
            if self.feste_erwartung:
                e["erwartet"] = self.feste_erwartung
            return "WERKZEUG: programm_testen " + json.dumps(e, ensure_ascii=False)
        e = {"datei": datei, "sekunden": 8}
        if "tkinter" in quelle:
            e["fenster"] = True
        return "WERKZEUG: programm_ausfuehren " + json.dumps(e, ensure_ascii=False)

    def _fokus(self, text: str, hinweis: str) -> str:
        """Dasselbe Modell, aber ohne die lange Vorgeschichte: Anweisung, Aufgabe, eine Aufforderung.

        Am 05.10.2026 (9:35) erzaehlte das 3B-Modell viermal hintereinander, es habe geschrieben,
        geprueft und uebertragen — kein Werkzeug lief, und die Zurueckweisungen im Gespraech
        aenderten nichts: Das lange Gespraech hielt es in der Prosa. Mit kurzem Verlauf liefert es
        den Werkzeugaufruf. Das ist die Methode, die der Agent dem Modell je nach Faehigkeit
        bereitstellt (Anforderung J15): erzeugt, geprueft, ueberprueft — nichts angenommen."""
        mini = [self.verlauf[0],
                {"role": "user", "content": f"Aufgabe des Menschen: {text}\n\n{hinweis}\n"
                                            "Antworte AUSSCHLIESSLICH mit genau einer Zeile 'WERKZEUG: <name> {...}' — "
                                            "kein Satz davor, keiner danach, kein FERTIG."}]
        notieren("FOKUS Modell ohne Vorgeschichte nach dem Werkzeugaufruf gefragt")
        self.sagen("hinweis", text="Das Modell erzaehlt Arbeit, die kein Werkzeug getan hat. Der Agent fragt es ohne Vorgeschichte noch einmal nur nach dem naechsten Werkzeugaufruf.")
        return self.modell.fragen(mini)

    def _anmerkung_zu(self, antwort: str):
        """Behauptet eine Antwort in freier Rede etwas, das kein Werkzeug der Sitzung belegt, sagt der
        Agent es dazu — sichtbar, ohne die Antwort zu unterdruecken. „Ja, alles ist ok. Die LED blinkt
        einmal pro Sekunde" (05.10.2026, 9:27) — und nichts war je geprueft oder uebertragen worden."""
        saetze = []
        if re.search(r"blinkt|l[aä]e?uft", antwort, re.I) and not any(n in self.getan for n in ("programm_testen", "esp32_nachlesen")):
            saetze.append("In diesem Gespraech wurde kein Programm geprueft (programm_testen) und nichts am Geraet gemessen (esp32_nachlesen).")
        if re.search(r"[uü]e?bertragen|geladen|geflasht|auf den ESP32", antwort, re.I) and "esp32_uebertragen" not in self.getan:
            saetze.append("Es wurde nichts auf den ESP32 uebertragen (esp32_uebertragen lief nicht).")
        if re.search(r"geschrieben", antwort, re.I) and not self.geschrieben:
            saetze.append("Es wurde keine Datei geschrieben.")
        return " ".join(saetze) if saetze else None

    def _takt_hinweis(self, pwm=False) -> str:
        f = (self.feste_erwartung or {}).get("takt_hz")
        if f and pwm:
            return (f"Bei {float(f):g} Hz Atmen dauert eine Periode {1/float(f):g} s. Mit N Stufen je Periode ist "
                    f"jede Pause time.sleep({1/float(f):g}/N) — zum Beispiel 100 Stufen: time.sleep({1/float(f)/100:g}). "
                    f"Sinusfoermig heisst: duty = 1023 * (1 - cos(2*pi*i/N)) / 2.")
        if f:
            pause = 1 / (2 * float(f))
            return (f"Bei {float(f):g} Hz besteht eine Blinkperiode aus zwei Pausen von je "
                    f"{pause:g} s: nach dem Einschalten time.sleep({pause:g}), nach dem Ausschalten "
                    f"time.sleep({pause:g}).")
        return ("Bei einem Takt: eine Blinkperiode besteht aus zwei Pausen, also ergibt "
                "time.sleep(0.5) + time.sleep(0.5) genau 1 Hz.")

    # ------------------------------------------------------------------ eine Anweisung
    def anweisung(self, text: str) -> str:
        """Fuehrt eine Anweisung des Menschen aus, bis FERTIG, Abbruch oder Nicht abgenommen.
        Danach kann die naechste kommen — der Zusammenhang bleibt."""
        if not self.offen:
            self.oeffnen()
        self.anweisungen += 1
        text = text.strip()
        notieren(f"AUFTRAG {text}")
        self.sagen("auftrag", text=text, nummer=self.anweisungen)
        self._vom_menschen(text)
        try:
            return self._durchlaufen(text)
        except Exception as e:
            #  Auf einem fremden Rechner ohne Netz sieht niemand zu. Was bleibt, ist diese Datei.
            notieren(f"ABBRUCH {type(e).__name__}: {str(e).splitlines()[0][:200] if str(e) else ''}")
            try:
                bericht = fehlerbericht(e, text)
                notieren(f"FEHLERBERICHT {bericht}")
                self.sagen("fehler", text=f"{type(e).__name__}: {e}\nFehlerbericht: {bericht}")
            except Exception:
                pass
            self.schliessen()
            raise

    def _durchlaufen(self, text: str) -> str:
        modell, werkzeuge, namen, laut = self.modell, self.werkzeuge, self.namen, self.laut
        sagen, verlauf = self.sagen, self.verlauf
        eigenes = self._eigenes_programm(text)
        verlauf.append({"role": "user", "content": text})
        if eigenes:
            verlauf.append({"role": "user", "content":
                f"Hinweis des Agenten: {eigenes[0]} wurde soeben woertlich aus der Eingabe des Menschen "
                f"in die Werkstatt geschrieben. Schreibe sie nicht neu; pruefe sie mit programm_testen."})
        if not self._modell_bereit():
            return drehbuch(werkzeuge, laut=laut, melden=self.melden)

        getan_hier: list = []
        getan_dateien: list = []                   # in dieser Anweisung geschriebene Dateien, in Reihenfolge
        abweisungen, selbst_geprueft = 0, False
        warteschlange: list = []
        for schritt in range(1, MAX_SCHRITTE + 1):
            if self._zwischenrufe_aufnehmen():
                #  Ein Zwischenruf geht vor: Was das Modell schon vorhatte, wird mit dem neuen
                #  Wissen neu entschieden — die Warteschlange verfaellt.
                warteschlange = []
            if warteschlange:
                #  Das Modell hat schon entschieden — der naechste Aufruf aus derselben Antwort.
                antwort = warteschlange.pop(0)
                sagen("denkt", schritt=schritt, aus_warteschlange=True)
                verlauf.append({"role": "assistant", "content": antwort})
                sagen("antwort", schritt=schritt, text=antwort.strip()[:1200])
                name, eingabe = heraus(antwort, werkzeuge)
                if name is None:
                    continue
            else:
                sagen("denkt", schritt=schritt)
                try:
                    antwort = modell.fragen(verlauf)
                except modell.KontextVoll:
                    #  Voll ist kein Ende: Anweisung und Auftrag bleiben, die Mitte wird ein Satz.
                    notieren("KONTEXT VOLL - aeltere Schritte zusammengefasst")
                    sagen("hinweis", text="Das Gedaechtnis des Modells war voll; aeltere Schritte wurden zusammengefasst.")
                    self.verlauf = verlauf = zusammenfassen(verlauf, self.getan, self.letzter_befund)
                    antwort = modell.fragen(verlauf)
                teile = zerlegen(antwort, werkzeuge)
                if len(teile) > 1:
                    notieren(f"MEHRERE AUFRUFE in einer Antwort: {len(teile)} — der Reihe nach")
                    sagen("hinweis", text=f"Die Antwort enthielt {len(teile)} Werkzeugaufrufe; sie werden der Reihe nach ausgefuehrt.")
                    antwort, warteschlange = teile[0], teile[1:]
                verlauf.append({"role": "assistant", "content": antwort})
                sagen("antwort", schritt=schritt, text=antwort.strip()[:1200])
                name, eingabe = heraus(antwort, werkzeuge)

            if name is None:
                if "FERTIG" in antwort.upper():
                    #  Ein FERTIG gilt nur, wenn es stimmt. Es wird bis zu dreimal zurueckgewiesen;
                    #  dann endet die Anweisung als NICHT ABGENOMMEN, nie als FERTIG (04.10.2026:
                    #  beide 3B-Modelle kamen mit dem zweiten FERTIG durch).
                    #  Zweites FERTIG, und die Datei ist immer noch ungeprueft — gleich, welche Regel das
                    #  erste zurueckwies (am 04.10.2026, 13:04, war es die Behauptung „auf den ESP32"): Der
                    #  Agent prueft jetzt selbst, einmal je Anweisung, sichtbar als eigener Aufruf.
                    if self.ungeprueft and abweisungen >= 1 and not selbst_geprueft:
                        selbst_geprueft = True
                        abweisungen += 1
                        datei = sorted(self.ungeprueft)[0]
                        aufruf = self._pruefaufruf(datei)
                        notieren(f"AGENT PRUEFT SELBST {datei} — FERTIG ohne Pruefung")
                        sagen("hinweis", text=f"FERTIG ohne Pruefung: der Agent prueft {datei} jetzt selbst.")
                        verlauf.append({"role": "user", "content":
                            f"Du hast FERTIG gesagt, ohne {datei} zu pruefen. Der Agent prueft jetzt selbst; "
                            f"hier der Aufruf und gleich darauf das Ergebnis."})
                        warteschlange.insert(0, aufruf)
                        continue
                    #  Je ANWEISUNG, nicht je Sitzung: Am 04.10.2026 (20:10) sagte das Modell „auf dem ESP32
                    #  geladen", weil frueher im Gespraech einmal uebertragen worden war — in dieser Anweisung
                    #  lief nichts. Was die Anweisung verlangt (laden, nachlesen), muss in ihr gelaufen sein.
                    behauptet_geraet = re.search(r"ueberspielt|überspielt|geflasht|geladen|auf den ESP32|auf das Ger", antwort, re.I)
                    verlangt_laden = re.search(r"\b(lade|laden|laedt|lädt|uebertrag|übertrag|flash|auf den ESP32|auf das Ger)", text, re.I)
                    verlangt_lesen = re.search(r"\b(nachles|nachlies|lies .{0,30}nach|zurueckles|zurücklies|zurueck ?lesen|rücklesen)", text, re.I)
                    fehlt_geraet = []
                    if (verlangt_laden or behauptet_geraet) and "esp32_uebertragen" not in getan_hier:
                        fehlt_geraet.append("esp32_uebertragen")
                    if verlangt_lesen and "esp32_nachlesen" not in getan_hier:
                        fehlt_geraet.append("esp32_nachlesen")
                    behauptet_arbeit = re.search(r"geschrieben|gepr[uü]e?ft|getestet|blinkt|l[aä]e?uft ohne Fehler", antwort, re.I)
                    if behauptet_arbeit and not getan_hier and abweisungen < 3:
                        #  „Ich habe das Programm geschrieben und geprueft … die LED blinkt" — und kein einziges
                        #  Werkzeug lief (05.10.2026, 9:26, Qwen2.5-Coder-3B). Das ist keine Antwort, das ist
                        #  erfunden. Der Agent sagt, was wahr ist, und nennt den ersten Schritt mit Beispiel.
                        abweisungen += 1
                        erw = json.dumps(self.feste_erwartung) if self.feste_erwartung else '{"pins": [2], "takt_hz": 1.0}'
                        hinweis = ("Es ist noch kein Werkzeug gelaufen. Der erste Schritt fuer ein Programm ist "
                                   'WERKZEUG: schreib_datei {"name": "<datei>.py", "inhalt": "<der vollstaendige Quelltext>"}; '
                                   f"danach WERKZEUG: programm_testen {{\"datei\": \"<datei>.py\", \"sekunden\": 6, \"erwartet\": {erw}}}.")
                        verlauf.append({"role": "user", "content":
                            "Das ist nicht wahr: In dieser Anweisung ist kein einziges Werkzeug gelaufen — nichts wurde "
                            "geschrieben, geprueft oder uebertragen. Behaupte nur, was ein Werkzeug getan hat. " + hinweis})
                        #  Nicht nur sagen, sondern die Methode bereitstellen: ohne Vorgeschichte fragen.
                        fokus = self._fokus(text, hinweis)
                        teile = zerlegen(fokus, werkzeuge)
                        if teile and heraus(teile[0], werkzeuge)[0] is not None:
                            warteschlange = teile[:5] + warteschlange
                            continue
                        continue
                    if fehlt_geraet and not getan_hier and self.genannte_ports and abweisungen < 3:
                        #  Verlangt ist ein Geraeteschritt, nichts lief, der Anschluss ist bekannt: ohne
                        #  Vorgeschichte nach genau diesem Aufruf fragen.
                        abweisungen += 1
                        port = sorted(self.genannte_ports)[0]
                        datei = (self.verlangt[-1] if self.verlangt else "blink.py")
                        hinweis = (f"Der naechste Schritt ist WERKZEUG: {fehlt_geraet[0]} " +
                                   (json.dumps({"port": port, "datei": datei}) if fehlt_geraet[0] == "esp32_uebertragen"
                                    else json.dumps({"port": port, "sekunden": 6})) + ".")
                        fokus = self._fokus(text, hinweis)
                        teile = zerlegen(fokus, werkzeuge)
                        if teile and heraus(teile[0], werkzeuge)[0] is not None:
                            warteschlange = teile[:5] + warteschlange
                        continue
                    if fehlt_geraet and abweisungen < 3:
                        abweisungen += 1
                        port_satz = (f"Anschluss, den der Mensch genannt hat: {', '.join(sorted(self.genannte_ports))}"
                                     if self.genannte_ports else
                                     "Der Mensch hat noch keinen Anschluss genannt — frage ihn danach (FERTIG mit der Frage), statt zu behaupten")
                        verlauf.append({"role": "user", "content":
                            f"Noch nicht fertig: {' und '.join(fehlt_geraet)} ist in dieser Anweisung nicht gelaufen — "
                            f"gelaufen sind {', '.join(getan_hier) or 'keine Werkzeuge'}. {port_satz}. "
                            f"Fuehre den fehlenden Schritt aus oder sage ehrlich, dass er noch aussteht."})
                        continue
                    if fehlt_geraet and abweisungen >= 3:
                        grund = (f"{' und '.join(fehlt_geraet)} nicht gelaufen" if getan_hier
                                 else "kein einziges Werkzeug gelaufen — die Arbeit war erfunden")
                        notieren(f"NICHT ABGENOMMEN {grund} — FERTIG dreimal zurueckgewiesen")
                        sagen("abbruch", text=f"Nicht abgenommen: {grund}. Das Modell hat dreimal FERTIG gesagt, ohne den verlangten Schritt zu tun.")
                        return f"Nicht abgenommen: {grund}."
                    fehlend = [n for n in self.verlangt if n not in self.geschrieben]
                    if (self.ungeprueft or self.letzter_befund or fehlend) and abweisungen >= 3:
                        grund = (f"{', '.join(sorted(self.ungeprueft))} ungeprueft" if self.ungeprueft
                                 else f"letzte Pruefung: {self.letzter_befund}" if self.letzter_befund
                                 else f"{', '.join(fehlend)} nie geschrieben")
                        notieren(f"NICHT ABGENOMMEN {grund} — FERTIG dreimal zurueckgewiesen")
                        sagen("abbruch", text=f"Nicht abgenommen: {grund}. Das Modell hat dreimal FERTIG "
                                              f"gesagt, ohne die aktuelle Fassung bestanden zu haben.")
                        return f"Nicht abgenommen: {grund}."
                    if fehlend and not self.ungeprueft and abweisungen < 3:
                        abweisungen += 1
                        verlauf.append({"role": "user", "content":
                            f"Noch nicht fertig: der Auftrag verlangt {', '.join(fehlend)}, und diese Datei "
                            f"wurde noch nicht geschrieben. Rufe schreib_datei mit dem vollstaendigen "
                            f"Programm auf, danach programm_testen."})
                        continue
                    if self.ungeprueft and abweisungen < 3:
                        abweisungen += 1
                        verlauf.append({"role": "user", "content":
                            f"Noch nicht fertig: {', '.join(sorted(self.ungeprueft))} ist gegen die aktuelle "
                            f"Erwartung {json.dumps(self.feste_erwartung) if self.feste_erwartung else ''} noch nicht "
                            f"geprueft (veraendert oder neue Erwartung). Passe das Programm an und rufe "
                            f"programm_testen auf; erst ein bestandener Test der aktuellen Fassung zaehlt."})
                        continue
                    if self.letzter_befund and abweisungen < 3:
                        abweisungen += 1
                        verlauf.append({"role": "user", "content":
                            f"Noch nicht fertig: die letzte Pruefung war nicht erfolgreich "
                            f"({self.letzter_befund}). Ein Programm, das die Pruefung nicht besteht, "
                            f"gilt nicht als geliefert. Berichtige den Quelltext mit "
                            f"schreib_datei — aendere wirklich etwas, derselbe Text fuehrt zum "
                            f"selben Ergebnis — und pruefe danach erneut mit programm_testen. "
                            + self._takt_hinweis()})
                        continue
                    if laut:
                        print(f"\n=== fertig nach {len(getan_hier)} Werkzeugaufrufen ===\n{antwort.strip()}")
                    notieren("FERTIG")
                    sagen("fertig", text=antwort.strip(), aufrufe=len(getan_hier))
                    return antwort
                #  Eine Antwort in Worten ist eine Antwort — an den Menschen, nicht an den Agenten.
                #  Bis zum 05.10.2026 wurde sie mit „Das war kein Werkzeugaufruf" zurueckgewiesen; der
                #  Auftraggeber: „keine ergebnisoffene Eingabe, sondern alles vorgegeben — das war nicht
                #  der Sinn der Uebung." Der Mensch liest sie und sagt, wie es weitergeht.
                notieren("ANTWORT " + antwort.strip().splitlines()[0][:160])
                anmerkung = self._anmerkung_zu(antwort)
                if anmerkung:
                    notieren("ANMERKUNG " + anmerkung[:160])
                    sagen("hinweis", text="Anmerkung des Agenten: " + anmerkung)
                sagen("fertig", text=antwort.strip(), aufrufe=len(getan_hier))
                return antwort

            if "__fehler" in (eingabe or {}):
                verlauf.append({"role": "user", "content":
                                f"FEHLER: {eingabe['__fehler']}. Schicke den Aufruf noch einmal "
                                f"mit gueltigem JSON."})
                continue

            self.getan.append(name); getan_hier.append(name)
            nachsatz, vorab = "", None
            if name == "schreib_datei" and isinstance(eingabe.get("inhalt"), str):
                inhalt = eingabe["inhalt"]
                if "\\n" in inhalt and "\n" not in inhalt.strip():
                    #  Qwen2.5-Coder-7B maskiert Zeilenumbrueche im JSON doppelt (\\n statt \n), die
                    #  Datei waere eine einzige Zeile mit Backslashes — kein gueltiges Python (05.10.2026,
                    #  Pruefstand 8:46: viermal „nicht geschrieben"). Die Absicht ist eindeutig; der Agent
                    #  loest die Maskierung auf und sagt es dem Modell.
                    eingabe["inhalt"] = inhalt.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "    ")
                    nachsatz += "\n\nHINWEIS: Die Zeilenumbrueche waren doppelt maskiert (\\\\n); der Agent hat sie aufgeloest. Schreibe im JSON \\n fuer einen Zeilenumbruch."
            if name in NICHT_FUERS_MODELL:
                vorab = (f"FEHLER: {name} ist kein Schritt eines Auftrags. Es beendet den Agenten und "
                         f"loescht alles, was er angelegt hat — das geschieht am Kursende ueber den Knopf "
                         f"'Aufraeumen', nicht mitten im Auftrag. Mach mit dem Auftrag weiter.")
            #  Der Anschluss wird nie geraten (H3): Nur ein Anschluss, den der Mensch genannt hat.
            if name in ("esp32_firmware", "esp32_uebertragen", "esp32_nachlesen"):
                port = str(eingabe.get("port", "")).strip()
                if port.upper() not in {p.upper() for p in self.genannte_ports}:
                    vorab = (f"FEHLER: Der Anschluss {port or '(leer)'} wurde vom Menschen nicht genannt — "
                             f"geraten wird nicht. Rufe ports_zeigen auf und frage in deiner Antwort mit "
                             f"FERTIG, welcher Anschluss gelten soll; der Mensch nennt ihn dann.")
            #  Nur Abgenommenes geht auf das Geraet (G1, G6): zuletzt geprueft, bestanden, unveraendert.
            if name == "esp32_uebertragen" and not vorab:
                datei = str(eingabe.get("datei", "")).strip()
                if datei not in self.abgenommen:
                    grund = ("nach der letzten Pruefung veraendert" if datei in self.ungeprueft
                             else "noch nie mit programm_testen bestanden")
                    vorab = (f"FEHLER: {datei} ist nicht abgenommen ({grund}). Erst programm_testen "
                             f"bestehen, dann uebertragen — ein Programm, das im Test nicht tut, was "
                             f"es soll, tut es auf dem Geraet auch nicht.")
            if name in ("esp32_nachlesen", "esp32_uebertragen") and self.feste_erwartung is not None:
                eingabe["erwartet"] = self.feste_erwartung      # dieselbe Erwartung auch am Geraet
            if name == "programm_ausfuehren":
                datei = eingabe.get("datei", "")
                if datei and datei not in self.geschrieben:
                    vorab = (f"FEHLER: {datei} wurde in dieser Sitzung noch nicht geschrieben. Ausgefuehrt "
                             "wird nur, was du selbst geschrieben hast — erst schreib_datei, dann programm_ausfuehren.")
            if name in ("programm_testen", "programm_ausfuehren") and not str(eingabe.get("datei", "")).strip():
                #  Das Modell vergass die Datei (05.10.2026, 9:55) — das Werkzeug nahm stillschweigend
                #  blink.py und pruefte ein altes Programm. Gemeint ist die zuletzt geschriebene Datei.
                letzte = next((n for n in reversed(getan_dateien) if n.endswith(".py")), None)
                if letzte:
                    eingabe["datei"] = letzte
                    nachsatz += f"\n\nHINWEIS: Im Aufruf fehlte \"datei\"; geprueft wurde die zuletzt geschriebene Datei {letzte}."
                else:
                    vorab = "FEHLER: Im Aufruf fehlt \"datei\", und in dieser Anweisung wurde noch keine Datei geschrieben."
            if name == "programm_testen":
                if isinstance(eingabe.get("erwartet"), dict):
                    #  Was der Mensch nicht festgelegt hat, legt der erste Aufruf des Modells fest — und
                    #  es bleibt. Am 05.10.2026 (9:09) wanderte die Erwartung sonst von 10 Hz zu 1 Hz.
                    neu = {k: v for k, v in eingabe["erwartet"].items()
                           if k in ("pins", "takt_hz", "form") and k not in (self.feste_erwartung or {})}   # mindestens_wechsel legt das Modell nicht fest (05.10.2026: 10 Wechsel bei PWM-Atmen)
                    if "takt_hz" in neu and float(neu["takt_hz"]) > 50:
                        #  1000 Hz „Takt" war die PWM-Traegerfrequenz (05.10.2026, 9:44). Ein Takt ueber
                        #  50 Hz ist fuer ein Auge unsichtbar und wird nicht als Erwartung festgehalten.
                        nachsatz += (f"\n\nHINWEIS: takt_hz {neu['takt_hz']} ist kein sichtbares Blinken oder Atmen, "
                                     "sondern eine Traegerfrequenz. Die Erwartung meint, wie oft je Sekunde die LED sichtbar "
                                     "an- und abschwillt oder blinkt (zum Beispiel 1.0). Frage den Menschen, wenn es unklar ist.")
                        del eingabe["erwartet"]["takt_hz"]; del neu["takt_hz"]
                    if neu:
                        self.feste_erwartung = {**(self.feste_erwartung or {}), **neu}
                        notieren(f"ERWARTUNG ERGAENZT (vom Modell genannt) {json.dumps(neu)}")
                        sagen("hinweis", text=f"Erwartung festgehalten: {json.dumps(self.feste_erwartung)} — aendern kann sie ab jetzt nur der Mensch.")
                if self.feste_erwartung is not None:
                    if isinstance(eingabe.get("erwartet"), dict) and "mindestens_wechsel" in eingabe["erwartet"]:
                        nachsatz += "\n\nHINWEIS: mindestens_wechsel wurde gestrichen — es zaehlt nur, was der Mensch erwartet (pins, takt_hz, form)."
                    if eingabe.get("erwartet") != self.feste_erwartung:
                        nachsatz = ("\n\nHINWEIS: Die Erwartung steht im Auftrag und wurde darauf "
                                    f"gesetzt: {json.dumps(self.feste_erwartung)}. Nicht die Erwartung an "
                                    "das Programm anpassen, sondern das Programm an die Erwartung.")
                    eingabe["erwartet"] = self.feste_erwartung
                if self.melden is not None:
                    eingabe["oeffnen"] = False         # die Oberflaeche zeigt die LED selbst
                datei = eingabe.get("datei", "")
                if datei and datei not in self.geschrieben:
                    vorab = (f"FEHLER: {datei} wurde in dieser Sitzung noch nicht geschrieben. Gepruefft "
                             "wird nur, was du selbst geschrieben hast — rufe zuerst schreib_datei "
                             "mit dem vollstaendigen Programm auf, dann programm_testen.")
            sagen("ruft", schritt=schritt, werkzeug=name, eingabe=eingabe)
            if laut:
                print(f"\n[{schritt}] {name} {json.dumps(eingabe, ensure_ascii=False)[:120]}")
            notieren(f"RUFT {name} {json.dumps(eingabe, ensure_ascii=False)}")
            ergebnis = vorab if vorab else ausfuehren(name, eingabe, werkzeuge)
            if nachsatz:
                ergebnis += nachsatz
            if name == "esp32_uebertragen" and "RUECKLESEN NACH DEM NEUSTART" in ergebnis:
                #  Die Uebertragung hat selbst am Geraet nachgelesen — das zaehlt als esp32_nachlesen
                #  (05.10.2026, 10:25: „esp32_nachlesen nicht gelaufen", obwohl gemessen worden war).
                self.getan.append("esp32_nachlesen"); getan_hier.append("esp32_nachlesen")
            if name == "schreib_datei" and not ergebnis.startswith("FEHLER") and eingabe.get("name"):
                self.geschrieben.add(eingabe["name"]); self.abgenommen.discard(eingabe["name"])
                getan_dateien.append(eingabe["name"])
                selbst_geprueft = False           # jede neue Fassung darf der Agent wieder selbst pruefen
                #  Beide 3B-Modelle nannten die Datei "two.py", der Auftrag sagte "zwei.py" (04.10.2026).
                #  Der Name gehoert dem Menschen wie die Erwartung — hier als Hinweis, nicht als Sperre.
                if self.verlangt and eingabe["name"].endswith(".py") and eingabe["name"] not in self.verlangt:
                    ergebnis += (f"\n\nHINWEIS: Der Auftrag nennt die Datei {self.verlangt[-1]}, geschrieben wurde "
                                 f"{eingabe['name']}. Verwende den Namen aus dem Auftrag.")
                if eingabe["name"].endswith(".py"):
                    self.ungeprueft.add(eingabe["name"])
            if name in ("programm_testen", "programm_ausfuehren") and not vorab:
                self.ungeprueft.discard(eingabe.get("datei", ""))
                abweisungen = 0                   # eine neue Pruefung eroeffnet drei neue Versuche
                if "ABNAHME BESTANDEN" in ergebnis or "LAUF BESTANDEN" in ergebnis:
                    self.abgenommen.add(eingabe.get("datei", ""))
                else:
                    self.abgenommen.discard(eingabe.get("datei", ""))

            #  Eine durchgefallene Abnahme aendert sich nicht durch Wiederholung — also steht hier,
            #  was zu tun ist, mit der Zahl, die zur Erwartung passt (04.10.2026, 14:12: der feste
            #  Satz „0,5 + 0,5 = 1 Hz" zog das Modell bei 10 Hz immer wieder zu 0,5 s).
            if "ABNAHME NICHT BESTANDEN" in ergebnis:
                ergebnis += ("\n\nNAECHSTER SCHRITT: Rufe schreib_datei mit berichtigtem "
                             "Quelltext auf. Dasselbe Programm noch einmal zu pruefen "
                             "aendert nichts am Ergebnis. Achte auf die Zeile, die oben "
                             "NICHT ERFUELLT heisst — dort steht, welche Zahl nicht stimmt. "
                             + self._takt_hinweis(pwm="PWM an Pin" in ergebnis))

            # Den Stand der letzten Pruefung merken — daran haengt, ob FERTIG gilt.
            if name in ("programm_testen", "programm_ausfuehren"):
                self.letzter_befund = (None if ("ABNAHME BESTANDEN" in ergebnis or "LAUF BESTANDEN" in ergebnis)
                                       else "die Abnahme ist durchgefallen"
                                       if "ABNAHME NICHT BESTANDEN" in ergebnis
                                       else "das Programm endete mit einem Fehler"
                                       if "LAUF NICHT BESTANDEN" in ergebnis
                                       else ergebnis.splitlines()[0][:120] if ergebnis.startswith("FEHLER")
                                       else None)

            schluessel = (name, ergebnis[:80])
            self.gesehen[schluessel] = self.gesehen.get(schluessel, 0) + 1
            if self.gesehen[schluessel] >= 3:
                ergebnis += ("\n\nHINWEIS: Das ist der dritte gleiche Fehlschlag mit "
                             f"{name}. Rufe dieses Werkzeug nicht noch einmal so auf. "
                             "Entweder behebst du zuerst die genannte Ursache mit einem "
                             "anderen Werkzeug, oder dieser Teil des Auftrags ist hier "
                             "nicht erfuellbar — dann schreibe FERTIG und sage, was fehlt.")
            if laut:
                print("    " + ergebnis.replace("\n", "\n    ")[:1500])
            urteil = ("  | ABNAHME BESTANDEN" if "ABNAHME BESTANDEN" in ergebnis
                      else "  | ABNAHME NICHT BESTANDEN" if "ABNAHME NICHT BESTANDEN" in ergebnis else "")
            notieren(f"ERGIBT {ergebnis.splitlines()[0] if ergebnis else ''}{urteil}")
            sagen("ergibt", schritt=schritt, werkzeug=name, text=ergebnis, **beurteilen(ergebnis))
            verlauf.append({"role": "user", "content": f"Ergebnis von {name}:\n{kuerzen(ergebnis)}"})

        notieren(f"ABBRUCH {MAX_SCHRITTE} Schritte erreicht, ohne dass FERTIG kam")
        sagen("abbruch", text=f"{MAX_SCHRITTE} Schritte erreicht, ohne dass FERTIG kam.")
        return f"Abbruch: {MAX_SCHRITTE} Schritte erreicht, ohne dass FERTIG kam."


def schleife(auftrag: str, werkzeuge: dict, laut=True, melden=None):
    """Ein einzelner Auftrag als Sitzung mit genau einer Anweisung — fuer die Befehlszeile und
    die Pruefprogramme. Die Oberflaeche haelt die Sitzung offen und reicht Anweisungen nach."""
    s = Sitzung(werkzeuge, laut=laut, melden=melden)
    try:
        return s.anweisung(auftrag)
    finally:
        s.schliessen()


DREHBUCH = [
    ("nachweis_autark", {"wann": "vorher"}),
    ("umgebung_anlegen", {}),
    ("paket_installieren", {"paket": "esptool"}),
    ("paket_installieren", {"paket": "mpremote"}),
    ("ports_zeigen", {}),
    ("schreib_datei", {"name": "blink.py", "inhalt":
        "from machine import Pin\nimport time\n\nled = Pin(2, Pin.OUT)\nwhile True:\n"
        "    led.value(1)\n    time.sleep(0.5)\n    led.value(0)\n    time.sleep(0.5)\n"}),
    ("programm_testen", {"datei": "blink.py", "sekunden": 5,
                         "erwartet": {"pins": [2], "takt_hz": 1.0}}),
]


def drehbuch(werkzeuge, laut=True, melden=None):
    """Dieselben Werkzeuge, nur ohne Modell — fuer den Fall, dass das Modell nicht laeuft.
    Das Flashen fehlt mit Absicht: dafuer muss der Anschluss bekannt sein.

    Meldet jeden Schritt ueber `melden` genauso wie die Schleife mit Modell — die
    Oberflaeche zeigt beide Wege mit denselben Zeilen, Marken und der virtuellen LED.
    """
    def sagen(art, **d):
        if melden:
            try:
                melden(dict(art=art, **d))
            except Exception:
                pass

    notieren("DREHBUCH ohne Modell")
    letztes = ""
    for i, (name, eingabe) in enumerate(DREHBUCH, 1):
        if laut:
            print(f"\n[{i}] {name} {json.dumps(eingabe, ensure_ascii=False)[:100]}")
        sagen("ruft", schritt=i, werkzeug=name, eingabe=eingabe)
        notieren(f"RUFT {name} {json.dumps(eingabe, ensure_ascii=False)}")
        ergebnis = ausfuehren(name, eingabe, werkzeuge)
        letztes = ergebnis
        if laut:
            print("    " + ergebnis.replace("\n", "\n    "))
        notieren(f"ERGIBT {ergebnis.splitlines()[0] if ergebnis else ''}")
        sagen("ergibt", schritt=i, werkzeug=name, text=ergebnis, **beurteilen(ergebnis))
    nachweis = ausfuehren("nachweis_autark", {"wann": "nachher"}, werkzeuge)
    if laut:
        print("\n[Nachweis] " + nachweis)
    sagen("ruft", schritt=len(DREHBUCH) + 1, werkzeug="nachweis_autark", eingabe={"wann": "nachher"})
    sagen("ergibt", schritt=len(DREHBUCH) + 1, werkzeug="nachweis_autark", text=nachweis,
          **beurteilen(nachweis))
    schluss = ("Ohne Modell endet das Drehbuch hier: Das Programm wurde geschrieben und "
               + ("mit bestandener Abnahme" if "ABNAHME BESTANDEN" in letztes else "geprueft")
               + " — dieselben Werkzeuge, dieselbe Pruefung, nur die Reihenfolge stand fest. "
               "Zum Flashen muss der Anschluss bekannt sein:\n"
               "  python agent\\werkzeuge\\esp32_firmware.py '{\"port\": \"COM5\"}'\n"
               "  python agent\\werkzeuge\\esp32_uebertragen.py '{\"port\": \"COM5\", \"datei\": \"blink.py\"}'")
    if laut:
        print("\n" + schluss)
    notieren("FERTIG (Drehbuch)")
    sagen("fertig", text=schluss, aufrufe=len(DREHBUCH) + 1)
    return schluss


def main():
    waechter.anmelden(ABLAGE, PAKET, laut=True)
    werkzeuge = sammlung()
    a = sys.argv[1] if len(sys.argv) > 1 else "--hilfe"

    if a == "--werkzeuge":
        for n, w in sorted(werkzeuge.items()):
            print(f"{n:22s} {w['description'].splitlines()[0][:100]}")
        return 0
    if a == "--probe":
        for n, w in sorted(werkzeuge.items()):
            r = subprocess.run([sys.executable, str(w["datei"]), "--probe"],
                               capture_output=True, text=True, timeout=600, env=umgebung(), **LESEN)
            kopf = (r.stdout or r.stderr).strip().splitlines()
            print(f"{n:22s} {'OK  ' if r.returncode == 0 else 'FEHL'} {kopf[0][:110] if kopf else ''}")
        return 0
    if a == "--drehbuch":
        drehbuch(werkzeuge)
        return 0
    if a.startswith("--"):
        print(__doc__)
        print(f"\n{len(werkzeuge)} Werkzeuge: {', '.join(sorted(werkzeuge))}")
        return 0

    schleife(" ".join(sys.argv[1:]), werkzeuge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
