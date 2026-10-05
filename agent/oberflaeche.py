#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Die Bedienoberflaeche im Browser — damit niemand eine Kommandozeile braucht.

Ein kleiner Webserver auf ``127.0.0.1``, der eine Seite ausliefert und den Agenten in
einem Nebenlauf startet. Die Seite fragt alle halbe Sekunde nach neuen Ereignissen und
zeigt sie an: welcher Schritt laeuft, welches Werkzeug gerufen wurde, was es geantwortet
hat, ob die Abnahme bestanden ist.

Warum ein Webserver und kein Fenster: das eingebettete Python bringt **kein tkinter** mit.
Ein Fenster haette also eine Installation verlangt — genau das, was dieses Paket nicht tut.
Der Browser ist auf jedem Windows-Rechner da.

Warum Nachfragen und keine dauerhafte Verbindung: beides geht, aber Nachfragen geht immer.
Ein halbsekuendliches GET ueberlebt Virenscanner, Zwischenspeicher und einen Browser, der
die Verbindung schliesst, weil der Reiter in den Hintergrund rutscht.

``127.0.0.1`` ist ausdruecklich gemeint: der Server ist von aussen nicht erreichbar, auch
nicht aus dem Hoersaal-WLAN. Wer die Seite sehen will, sitzt an diesem Rechner.
"""
from __future__ import annotations
import http.server, json, socketserver, threading, time, webbrowser, subprocess, sys, pathlib, os

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pfade import ABLAGE, WURZEL, eine                      # noqa: E402
import agent as agentmodul                                   # noqa: E402

ADRESSE, PORT = "127.0.0.1", 8777
PORTE = range(8777, 8787)      # zehn Versuche, falls einer schon belegt ist

# Fertige Auftraege. Ein Anfaenger soll klicken koennen, nicht formulieren muessen — und
# wer formulieren will, hat daneben das freie Feld.
AUFTRAEGE = [
    ("LED blinken lassen, nur geprüft",
     "Schreibe ein MicroPython-Programm blink.py, das die LED an GPIO 2 einmal je Sekunde "
     "blinken laesst. Pruefe es danach mit programm_testen gegen die Erwartung pins [2] und "
     "takt_hz 1.0. Es ist keine Hardware angeschlossen.",
     "ohne Hardware — das Programm entsteht, läuft und wird abgenommen"),
    ("LED blinken lassen und auf den ESP32",
     "Richte die Umgebung ein und installiere esptool und mpremote. Schreibe dann ein "
     "MicroPython-Programm blink.py, das die LED an GPIO 2 einmal je Sekunde blinken laesst, "
     "und pruefe es mit programm_testen gegen pins [2] und takt_hz 1.0. Sieh danach nach, "
     "welche seriellen Anschluesse es gibt, und melde mir, welchen ich bestaetigen soll.",
     "mit Hardware — bis zum Anschluss, das Flashen bestätigen Sie"),
    ("Zweimal blinken, verschiedene Takte",
     "Schreibe ein MicroPython-Programm zwei.py, in dem die LED an GPIO 2 zweimal je Sekunde "
     "und die LED an GPIO 4 einmal je Sekunde blinkt. Pruefe es mit programm_testen gegen "
     "pins [2, 4]. Es ist keine Hardware angeschlossen.",
     "zeigt, dass jeder Anschluss einzeln aufgezeichnet wird"),
    ("Was ist an diesem Rechner angeschlossen?",
     "Richte die Umgebung ein, installiere esptool und sieh dann nach, welche seriellen "
     "Anschluesse es an diesem Rechner gibt.",
     "kurzer Lauf — gut als erster Versuch"),
]

def auftraege_lesen() -> list:
    """Die festen Anfragen (Knoepfe ueber dem Eingabefeld) aus agent/auftraege.json — je Aufruf
    gelesen, damit der Dozent sie aendern kann, ohne den Agenten neu zu starten (05.10.2026:
    „feste Anfragen ueber Buttons hinterlegen, aber auch freie Eingabe ermoeglichen")."""
    d = pathlib.Path(__file__).with_name("auftraege.json")
    try:
        liste = json.loads(d.read_text(encoding="utf-8"))
        return [{"titel": a["titel"], "text": a["text"], "hinweis": a.get("hinweis", "")} for a in liste]
    except Exception:
        return [{"titel": a, "text": b, "hinweis": c} for a, b, c in AUFTRAEGE]


_ereignisse: list = []
_sperre = threading.Lock()
_laeuft = False

_geraete = {"zeit": 0.0, "liste": None}
def geraete() -> list | None:
    """Welche seriellen Anschluesse gerade da sind — fuer die Kopfzeile („sehe nie, ob der ESP32 ueberhaupt
    verbunden ist", 05.10.2026). Hoechstens alle 5 s, und nie waehrend ein Werkzeug laeuft: Ein Flashen oder
    Uebertragen darf keine zweite Abfrage am selben Anschluss bekommen. None heisst: nicht feststellbar
    (noch kein eigenes Python oder kein pyserial)."""
    if _laeuft or time.time() - _geraete["zeit"] < 5:
        return _geraete["liste"]
    _geraete["zeit"] = time.time()
    try:
        from pfade import python_exe
        w = str(pathlib.Path(__file__).resolve().parent / "werkzeuge")
        if w not in sys.path:
            sys.path.insert(0, w)
        from ports_zeigen import ABFRAGE, WANDLER
        if not python_exe().exists():
            return None
        from pfade import umgebung
        r = subprocess.run([str(python_exe()), "-c", ABFRAGE], capture_output=True, text=True, timeout=10,
                           env=umgebung(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return None
        liste = []
        for p in json.loads(r.stdout):
            kennung = f"{p['vid']:04X}:{p['pid']:04X}" if p.get("vid") else ""
            liste.append({"port": p["port"], "name": p.get("name", ""), "wandler": WANDLER.get(kennung)})
        _geraete["liste"] = liste
    except Exception:
        return _geraete["liste"]
    return _geraete["liste"]
_sitzung = None          # das Gespraech: bleibt ueber Anweisungen hinweg offen (04.10.2026)


def _melden(e: dict):
    with _sperre:
        e["zeit"] = time.strftime("%H:%M:%S")
        _ereignisse.append(e)


def _starten(auftrag: str):
    """Eine Anweisung in der offenen Sitzung — die erste eroeffnet sie.

    Bis zum 04.10.2026 war jeder Auftrag ein eigener Lauf mit leerem Gedaechtnis und neu
    geladenem Modell. Jetzt bleibt beides stehen: „anderer Pin", „andere Frequenz", „erst
    pruefen, dann laden" beziehen sich auf das, was vorher war."""
    global _laeuft, _sitzung
    _laeuft = True
    try:
        if _sitzung is None:
            _sitzung = agentmodul.Sitzung(agentmodul.sammlung(), laut=False, melden=_melden)
        _sitzung.anweisung(auftrag)
    except Exception as e:
        _melden({"art": "fehler", "text": f"{type(e).__name__}: {e}"})
        _sitzung = None                      # die Sitzung hat sich im Fehlerfall selbst geschlossen
    finally:
        _laeuft = False
        _melden({"art": "ende"})


def _sitzung_schliessen(grund: str):
    global _sitzung
    if _sitzung is not None:
        try:
            _sitzung.schliessen()
        except Exception:
            pass
        _sitzung = None
        _melden({"art": "neu", "text": grund})


def _werkzeug(name: str, eingabe: dict):
    """Ein einzelnes Werkzeug ohne Modell — fuer die Knoepfe 'Prüfen' und 'Aufräumen'."""
    w = agentmodul.sammlung()
    _melden({"art": "ruft", "werkzeug": name, "eingabe": eingabe, "schritt": 0})
    #  Auch Einzelaufrufe stehen im Protokoll — bis zum 04.10.2026 taten sie das nicht, und
    #  ein Aufraeumen aus dem Browser, das das laufende Python halb loeschte, war darin
    #  unsichtbar. Was ein Knopf tut, muss hinterher nachlesbar sein.
    agentmodul.notieren(f"KNOPF {name} {json.dumps(eingabe, ensure_ascii=False)[:160]}")
    t = agentmodul.ausfuehren(name, eingabe, w)
    #  Die ersten drei Zeilen, nicht nur die erste: Bei esp32_firmware steht in Zeile 1 nur
    #  "ESP32 erkannt", ob geflasht wurde erst in Zeile 3 (04.10.2026, 1:22 Uhr).
    agentmodul.notieren("ERGIBT " + " | ".join(z.strip() for z in (t or "").splitlines()[:3])[:300])
    _melden({"art": "ergibt", "werkzeug": name, "text": t, "schritt": 0,
             **agentmodul.beurteilen(t)})
    _melden({"art": "ende"})


class Griff(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass                                  # kein Gekritzel in der Konsole

    def _senden(self, art, inhalt: bytes, code=200):
        self.send_response(code)
        self.send_header("Content-Type", art)
        self.send_header("Content-Length", str(len(inhalt)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(inhalt)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            return self._senden("text/html; charset=utf-8", seite().encode("utf-8"))
        if self.path.startswith("/ereignisse"):
            ab = 0
            if "ab=" in self.path:
                try:
                    ab = int(self.path.split("ab=")[1].split("&")[0])
                except ValueError:
                    ab = 0
            with _sperre:
                neu = _ereignisse[ab:]
                stand = len(_ereignisse)
            return self._senden("application/json",
                                json.dumps({"ab": stand, "neu": neu, "laeuft": _laeuft}).encode())
        if self.path.startswith("/zustand"):
            with _sperre:
                stand = len(_ereignisse)
            s = _sitzung
            return self._senden("application/json", json.dumps({
                "laeuft": _laeuft, "stand": stand, "wurzel": str(WURZEL),
                "modell": (eine("modell/*.gguf") or pathlib.Path("—")).name,
                "sitzung": None if s is None else {
                    "anweisungen": s.anweisungen,
                    "modell_geladen": bool(s.server is not None and s.server.poll() is None),
                    "ohne_modell": s.ohne_modell,
                    "erwartung": s.feste_erwartung, "ports": sorted(s.genannte_ports),
                    "abgenommen": sorted(s.abgenommen), "ungeprueft": sorted(s.ungeprueft)},
                "auftraege": auftraege_lesen(),
                "geraete": geraete(),
            }).encode())
        if self.path.startswith("/led"):
            # startswith, nicht ==: die Seite haengt ein ?t=<Zeit> an, um den
            # Zwischenspeicher des Browsers zu umgehen. Mit == trifft die Route nie.
            d = ABLAGE / "virtuelle_led.html"
            if d.is_file():
                return self._senden("text/html; charset=utf-8", d.read_bytes())
            return self._senden("text/plain; charset=utf-8",
                                "Noch keine Aufzeichnung.".encode(), 404)
        self._senden("text/plain", b"nicht gefunden", 404)

    def do_POST(self):
        laenge = int(self.headers.get("Content-Length") or 0)
        daten = json.loads(self.rfile.read(laenge) or b"{}")
        if self.path == "/start":
            auftrag = (daten.get("auftrag") or "").strip()
            if not auftrag:
                return self._senden("application/json", b'{"fehler": "kein Auftrag"}', 400)
            if _laeuft:
                #  Quereingabe (04.10.2026): waehrend der Agent arbeitet, wird die Eingabe als
                #  Zwischenruf eingereiht und beim naechsten Schritt aufgenommen — statt 409.
                if _sitzung is not None:
                    _sitzung.zwischenruf(auftrag)
                    return self._senden("application/json", b'{"zwischenruf": true}')
                return self._senden("application/json", b'{"fehler": "laeuft schon"}', 409)
            threading.Thread(target=_starten, args=(auftrag,), daemon=True).start()
            return self._senden("application/json", b'{"gestartet": true}')
        if self.path == "/neu":
            #  Neues Gespraech: Sitzung schliessen (Modellserver beenden, Sperre loesen); die
            #  Werkstatt bleibt, damit nichts verloren geht. Nur im Stillstand.
            if _laeuft:
                return self._senden("application/json", b'{"fehler": "laeuft schon"}', 409)
            _sitzung_schliessen("Neues Gespraech begonnen.")
            return self._senden("application/json", b'{"neu": true}')
        if self.path == "/neuladen":
            #  Agent und Modellanbindung neu einlesen, ohne das Fenster zu schliessen. Fuer den
            #  Dozenten, der Korrekturen ueber die Bruecke einspielt (04.10.2026: drei Neustarts
            #  an einem Nachmittag). Nur im Stillstand; Werkzeuge sind ohnehin Unterprozesse.
            if _laeuft:
                return self._senden("application/json", b'{"fehler": "laeuft schon"}', 409)
            import importlib
            _sitzung_schliessen("Agent neu geladen — das Gespraech beginnt von vorn.")
            neu = []
            for modulname in ("modell", "waechter", "sauber", "pfade"):
                if modulname in sys.modules:
                    importlib.reload(sys.modules[modulname]); neu.append(modulname)
            importlib.reload(agentmodul); neu.append("agent")
            stand = {n: time.strftime("%H:%M:%S", time.localtime(pathlib.Path(sys.modules[n].__file__).stat().st_mtime))
                     for n in neu if n in sys.modules}
            agentmodul.notieren("NEU GELADEN " + ", ".join(f"{k} ({v})" for k, v in stand.items()))
            return self._senden("application/json", json.dumps({"neu_geladen": stand}).encode())
        if self.path == "/werkzeug":
            if _laeuft:
                return self._senden("application/json", b'{"fehler": "laeuft schon"}', 409)
            name = daten.get("name", "")
            threading.Thread(target=_werkzeug,
                             args=(name, daten.get("eingabe") or {}), daemon=True).start()
            return self._senden("application/json", b'{"gestartet": true}')
        self._senden("text/plain", b"nicht gefunden", 404)


class Server(socketserver.ThreadingTCPServer):
    # Absichtlich NICHT allow_reuse_address: ein belegter Port gehoert jemand anderem.
    # Wir weichen aus, statt uns dazwischenzudraengen (siehe _freier_port).
    allow_reuse_address = False
    daemon_threads = True


def seite() -> str:
    """Die Seite wird bei jedem Aufruf gelesen: eine Aenderung an oberflaeche.html braucht so
    keinen Neustart — der Dozent spielt sie ein und laedt den Browser neu."""
    d = pathlib.Path(__file__).with_name("oberflaeche.html")
    return d.read_text(encoding="utf-8") if d.is_file() else "<h1>oberflaeche.html fehlt</h1>"


def _freier_port():
    """Nimmt den ersten freien Port — statt den belegten einem anderen Programm wegzunehmen.

    Auf dem Kursrechner kann 8777 schon jemandem gehoeren. Mit allow_reuse_address wuerde
    der Start hier zwar gelingen, aber die Anfragen landeten dann teils beim anderen
    Programm. Lieber ausweichen: wir sind Gast auf diesem Rechner.
    """
    import socket
    for p in PORTE:
        with socket.socket() as s:
            try:
                s.bind((ADRESSE, p))
                return p
            except OSError:
                continue
    raise SystemExit(f"Die Ports {PORTE.start} bis {PORTE.stop-1} sind alle belegt. "
                     f"Schliesse ein Programm, das einen davon benutzt.")


def _sperre_aufraeumen():
    """Eine Sperrdatei ohne lebenden Prozess wird beim Start entfernt.

    Wird das Agentenfenster hart geschlossen (Kreuz statt Strg+C), bleibt ablage\\laeuft.pid
    liegen, und die naechste Anweisung endet mit „Belegt: In diesem Ordner laeuft bereits ein
    Agent" (Pruefstand 04.10.2026, 12:52, nach einem abgeschossenen Server). Lebt der Prozess
    nicht mehr, ist die Sperre gegenstandslos; lebt er, bleibt sie — und wird gemeldet."""
    d = agentmodul.ABLAGE / "laeuft.pid"
    if not d.is_file():
        return
    alt = d.read_text(encoding="utf-8", errors="replace").strip()
    if alt.isdigit() and agentmodul._lebt(alt) and alt != str(os.getpid()):
        print(f"  Achtung: ablage\\laeuft.pid nennt Prozess {alt}, und der laeuft noch — ein zweiter Agent? "
              f"Erst den beenden, sonst meldet jede Anweisung 'Belegt'.")
        return
    try:
        d.unlink()
        print("  Alte Sperrdatei ohne lebenden Prozess entfernt (ablage\\laeuft.pid).")
    except OSError:
        pass


def main():
    _sperre_aufraeumen()
    port = _freier_port()
    if port != PORT:
        print(f"  Port {PORT} ist belegt — die Oberflaeche laeuft auf {port}.")
    with Server((ADRESSE, port), Griff) as s:
        adresse = f"http://{ADRESSE}:{port}/"
        print(f"  Die Oberflaeche laeuft: {adresse}")
        print(f"  Dieses Fenster offen lassen. Beenden mit Strg+C.")
        # Den Browser in einem eigenen Nebenlauf starten und jeden Fehler schlucken:
        # webbrowser.open ruft ein fremdes Programm auf, und dessen Scheitern darf den
        # Server nicht mitreissen. Auf einem Rechner ohne eingetragenen Standardbrowser
        # endete das sonst mit einer Ausnahme, und die Oberflaeche war weg, bevor sie
        # jemand sehen konnte.
        def _browser():
            try:
                webbrowser.open(adresse)
            except Exception as e:
                print(f"  (Der Browser liess sich nicht oeffnen: {type(e).__name__}. "
                      f"Adresse von Hand aufrufen: {adresse})")
        threading.Thread(target=_browser, daemon=True).start()
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            print("\n  Beendet.")
        finally:
            _sitzung_schliessen("Oberflaeche beendet.")      # Modellserver nicht verwaist lassen


if __name__ == "__main__":
    raise SystemExit(main())
