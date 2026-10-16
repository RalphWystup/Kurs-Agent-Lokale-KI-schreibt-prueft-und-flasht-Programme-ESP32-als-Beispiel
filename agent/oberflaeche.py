#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Der Diener hinter Frage.html — startet auf Knopfdruck die Werkzeuge, sonst nichts.

Neuanfang 15.10.2026. Sein Wort: „Im Reiter Testen geschieht zuerst alles per Hand": zwei
vorgefertigte Python-Dateien, waehlbar und aenderbar, durch den Interpreter uebersetzen, dann
Simulator oder Laden auf den ESP32, davor das Betriebssystem (MicroPython) aufspielen.

Kein Agent, kein Modellaufruf hier (die Seite spricht mit dem 7B selbst). Jeder Knopf ruft genau
ein Werkzeug als eigenen Prozess, und die Ausgabe laeuft Zeile fuer Zeile in die Seite.

Wege (nur 127.0.0.1:8777):
    GET  /                      die Seite (Frage.html, bei jedem Aufruf gelesen)
    GET  /zustand               {"laeuft": ...}  — damit die Bruecke start/status kann
    GET  /dateien               die vorgefertigten Programme in testprogramme\\
    GET  /datei?name=x.py       Inhalt einer davon
    POST /uebersetzen           {name, inhalt}: in die Werkstatt schreiben, mit dem Interpreter
                                des Kurses uebersetzen (py_compile) — Fehler im Wortlaut
    POST /werkzeug              {name, eingabe}: Werkzeug starten, gibt {"id": n}
    GET  /ausgabe?id=n          {"zeilen": [...], "fertig": bool}
    GET  /ports                 Ausgabe von ports_zeigen

Die Bruecke startet diese Datei mit „kursagent start" (Python des Kurses, abgeloest).
"""
from __future__ import annotations

import http.server
import json
import os
import signal
import pathlib
import subprocess
import sys
import threading
import time
import webbrowser

HIER = pathlib.Path(__file__).resolve().parent
WURZEL = HIER.parent
for _p in (str(HIER), str(WURZEL)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from pfade import ABLAGE, WERKSTATT, python_exe, umgebung   # noqa: E402

WERKZEUGE = HIER / "werkzeuge"
PROGRAMME = WURZEL / "testprogramme"
SEITE = WURZEL / "Frage.html"
OHNE_FENSTER = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
LESEN = {"encoding": "utf-8", "errors": "replace"}

_jobs: dict = {}
_sperre = threading.Lock()
_naechste = [0]


def fenster_ist_der_schalter():
    """Sein Wort (16.10.2026, 02:35): „ich will doch eine start bat zum starten! das muss alles
    ausloesen und wenn ich diese schliesse — sie bleibt offen solange ich arbeite — wird wieder
    alles abgestellt."  Zwei Sicherungen nach Windows-Dokumentation (kein Raten):
      1. SetConsoleCtrlHandler: beim Schliessen des Fensters (CTRL_CLOSE_EVENT, auch Abmelden/
         Herunterfahren) laeuft aufraeumen() — Python selbst faengt nur Strg+C/Strg+Untbr ab.
      2. Job-Objekt mit KILL_ON_JOB_CLOSE: stirbt dieser Prozess, wie auch immer, beendet Windows
         alle Kindprozesse (Modellserver, Werkzeuge) mit — nichts bleibt stehen."""
    if os.name != "nt":
        return "kein Windows"
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    befund = []
    try:
        HANDLER = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def _handler(art):
            if art in (2, 5, 6):                       # CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT
                aufraeumen("Fenster geschlossen")
                return True
            return False
        global _ctrl_handler
        _ctrl_handler = HANDLER(_handler)                # Referenz halten, sonst raeumt Python sie weg
        befund.append("Ctrl-Handler " + ("gesetzt" if k.SetConsoleCtrlHandler(_ctrl_handler, True) else "NICHT gesetzt"))
    except Exception as e:                                        # noqa: BLE001
        befund.append(f"Ctrl-Handler Fehler: {e}")
    try:
        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]
        k.CreateJobObjectW.restype = wintypes.HANDLE                # 64-Bit-Handles: ohne restype kuerzt ctypes auf 32 Bit (Fehler 6, gemessen 02:32)
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        job = k.CreateJobObjectW(None, None)
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x2000          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok1 = k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))   # JobObjectExtendedLimitInformation
        ok2 = k.AssignProcessToJobObject(job, k.GetCurrentProcess())
        global _job
        _job = job                                              # Handle halten: sein Schliessen = alles beenden
        befund.append("Job-Objekt " + ("gesetzt" if ok1 and ok2 else f"NICHT gesetzt (Fehler {k.GetLastError()})"))
    except Exception as e:                                        # noqa: BLE001
        befund.append(f"Job-Objekt Fehler: {e}")
    return ", ".join(befund)


def aufraeumen(grund: str):
    """Ausgangszustand (sein Wort 16.10.2026: „Wenn die HTML oder die bat geschlossen wird, muss
    alles wieder auf den Ausgangszustand gesetzt werden — nichts ausser der Bruecke darf mehr
    laufen"): Leitung zu, Modellserver aus, Diener aus."""
    try:
        protokoll("ENDE", grund + " — Leitung geschlossen, Modellserver beendet, Diener beendet")
    except Exception:                                             # noqa: BLE001
        pass
    try:
        SERIELL.schliessen()
    except Exception:                                             # noqa: BLE001
        pass
    try:
        subprocess.run(["taskkill", "/IM", "llama-server.exe", "/F"], capture_output=True, timeout=20,
                       **OHNE_FENSTER)
    except Exception:                                             # noqa: BLE001
        pass
    os._exit(0)


PROTOKOLL = ABLAGE / "protokoll_testen.txt"


def protokoll(art: str, text: str):
    """Jeder Schritt des Menschen im Testmodus, mit Uhrzeit — daraus wird spaeter der Agent
    abgeleitet (sein Wort 15.10.2026: „du analysierst mein Verhalten, indem du mir zusiehst")."""
    try:
        ABLAGE.mkdir(parents=True, exist_ok=True)
        with open(PROTOKOLL, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {art:<12} {text}\n")
    except OSError:
        pass


class Seriell:
    """Die direkte Leitung zum Brett (REPL): offen halten, mitlesen, Befehle senden.
    Sein Wort (15.10.2026): „Normalerweise meldet der ESP32 sich nach dem Aufspielen des
    Betriebssystems zurueck und ermoeglicht eine direkte Eingabe von Befehlen — das moechte
    ich hier auch drin haben." Vor jedem Werkzeug wird die Leitung freigegeben."""

    def __init__(self):
        self.v = None
        self.port = ""
        self.puffer: list = []
        self.sperre = threading.Lock()

    def oeffnen(self, port: str) -> str:
        import serial
        self.schliessen()
        self.v = serial.Serial(port, 115200, timeout=0.2)
        self.port = port
        with self.sperre:
            self.puffer = [f"[verbunden mit {port}, 115200 Baud — Strg+C unterbricht, Strg+D startet neu]"]
        threading.Thread(target=self._lesen, daemon=True).start()
        try:                       # ein Zeilenumbruch holt die Eingabeaufforderung hervor
            self.v.write(b"\r\n")
        except Exception:          # noqa: BLE001
            pass
        return port

    def _lesen(self):
        v = self.v
        rest = b""
        while v is not None and v is self.v:
            try:
                b = v.read(256)
            except Exception as ex:                                # noqa: BLE001
                with self.sperre:
                    self.puffer.append(f"[Leitung weg: {ex}]")
                self.v = None
                return
            if not b:
                continue
            rest += b
            text = rest.decode("utf-8", "replace")
            rest = b""
            with self.sperre:
                self.puffer.append(text)
                if len(self.puffer) > 4000:
                    del self.puffer[:1000]

    def senden(self, text: str, roh: bytes = b""):
        if self.v is None:
            raise RuntimeError("keine Verbindung")
        self.v.write(roh if roh else (text.encode("utf-8") + b"\r\n"))

    def lesen(self, ab: int):
        with self.sperre:
            return "".join(self.puffer[ab:]), len(self.puffer)

    def schliessen(self):
        v, self.v = self.v, None
        if v is not None:
            try:
                v.close()
            except Exception:      # noqa: BLE001
                pass
            with self.sperre:
                self.puffer.append(f"[getrennt von {self.port}]")
            time.sleep(0.3)


SERIELL = Seriell()


def _py() -> str:
    p = pathlib.Path(python_exe())
    return str(p) if p.is_file() else sys.executable


def job_starten(befehl: list, titel: str) -> int:
    """Ein Programm abgeloest starten; seine Zeilen landen in _jobs[id]."""
    with _sperre:
        _naechste[0] += 1
        nr = _naechste[0]
        _jobs[nr] = {"zeilen": [], "fertig": False, "rc": None, "start": time.time()}

    def laufen():
        try:
            p = subprocess.Popen(befehl, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1, env=umgebung(), cwd=str(WURZEL),
                                 **OHNE_FENSTER, **LESEN)
            for zeile in p.stdout:
                with _sperre:
                    _jobs[nr]["zeilen"].append(zeile.rstrip("\n"))
            p.wait()
            rc = p.returncode
        except Exception as ex:                                   # noqa: BLE001
            with _sperre:
                _jobs[nr]["zeilen"].append(f"FEHLER: {type(ex).__name__}: {ex}")
            rc = -1
        with _sperre:
            d = _jobs[nr]
            d["rc"] = rc
            d["dauer_s"] = round(time.time() - d["start"], 1)   # fuer die Standzeile — keine eigene Zeile im Fenster (sein Wort 16.10.2026)
            d["fertig"] = True
            protokoll("ERGEBNIS", titel.split(" ")[0] + f" rc={rc} {d['dauer_s']} s | "
                      + " | ".join(z for z in d["zeilen"] if z.strip())[:600])
    threading.Thread(target=laufen, daemon=True).start()
    protokoll("WERKZEUG", titel[:400])
    return nr


def werkzeug_befehl(name: str, eingabe: dict) -> list:
    datei = WERKZEUGE / f"{name}.py"
    if not datei.is_file():
        raise FileNotFoundError(f"Werkzeug {name} fehlt")
    return [_py(), str(datei), json.dumps(eingabe, ensure_ascii=False)]


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _senden(self, typ: str, daten: bytes, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(daten)

    def _json(self, d, code: int = 200):
        self._senden("application/json; charset=utf-8", json.dumps(d, ensure_ascii=False).encode("utf-8"), code)

    def do_GET(self):
        pfad, _, abfrage = self.path.partition("?")
        felder = dict(x.split("=", 1) for x in abfrage.split("&") if "=" in x)
        if pfad == "/":
            if SEITE.is_file():
                return self._senden("text/html; charset=utf-8", SEITE.read_bytes())
            return self._senden("text/plain; charset=utf-8", b"Frage.html fehlt", 404)
        if pfad == "/zustand":
            with _sperre:
                laeuft = any(not j["fertig"] for j in _jobs.values())
            return self._json({"laeuft": laeuft, "wurzel": str(WURZEL), "werkstatt": str(WERKSTATT)})
        if pfad == "/dateien":
            PROGRAMME.mkdir(exist_ok=True)
            return self._json({"dateien": sorted(p.name for p in PROGRAMME.glob("*.py"))})
        if pfad == "/datei":
            name = pathlib.Path(felder.get("name", "")).name
            protokoll("WAHL", name)
            p = PROGRAMME / name
            if not name or not p.is_file():
                return self._json({"fehler": f"{name} gibt es nicht"}, 404)
            return self._json({"name": name, "inhalt": p.read_text(encoding="utf-8", errors="replace")})
        if pfad == "/ausgabe":
            try:
                nr = int(felder.get("id", "0"))
            except ValueError:
                nr = 0
            with _sperre:
                j = _jobs.get(nr)
                if not j:
                    return self._json({"fehler": "unbekannter Lauf"}, 404)
                return self._json({"zeilen": list(j["zeilen"]), "fertig": j["fertig"], "rc": j["rc"], "dauer_s": j.get("dauer_s")})
        if pfad == "/seriell/lesen":
            try:
                ab = int(felder.get("ab", "0"))
            except ValueError:
                ab = 0
            text, stand = SERIELL.lesen(ab)
            return self._json({"text": text, "ab": stand, "verbunden": SERIELL.v is not None, "port": SERIELL.port})
        if pfad == "/protokoll":
            try:
                n = int(felder.get("n", "120"))
            except ValueError:
                n = 120
            try:
                zeilen = PROTOKOLL.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
            except OSError:
                zeilen = []
            return self._json({"zeilen": zeilen})
        if pfad == "/ports":
            r = subprocess.run(werkzeug_befehl("ports_zeigen", {}), capture_output=True, text=True,
                               timeout=60, env=umgebung(), **OHNE_FENSTER, **LESEN)
            return self._json({"text": (r.stdout or r.stderr or "").strip()})
        return self._senden("text/plain", b"nicht gefunden", 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            daten = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"fehler": "kein JSON"}, 400)
        if self.path == "/uebersetzen":
            name = pathlib.Path(str(daten.get("name") or "programm.py")).name
            if not name.endswith(".py"):
                name += ".py"
            inhalt = str(daten.get("inhalt") or "")
            #  Beim Kopieren aus einer Antwort kommt oft eine gemeinsame Einrueckung mit (16.10.2026,
            #  in seinem Test: jede Zeile zwei Leerzeichen -> IndentationError in Zeile 1). Eine
            #  Einrueckung, die ALLE nicht-leeren Zeilen gemeinsam haben, traegt keine Bedeutung und
            #  wird entfernt — und gesagt. Der Interpreter urteilt danach wie immer selbst.
            import textwrap
            bereinigt = textwrap.dedent(inhalt.replace("\r\n", "\n"))
            hinweis = ""
            if bereinigt != inhalt.replace("\r\n", "\n"):
                erste = next((z for z in inhalt.replace("\r\n", "\n").splitlines() if z.strip()), "")
                n = len(erste) - len(erste.lstrip())
                hinweis = (f"alle Zeilen hatten {n} Zeichen Einrueckung am Anfang (beim Kopieren "
                           f"mitgekommen) — entfernt; die Eingabe zeigt jetzt den bereinigten Text")
                inhalt = bereinigt
            protokoll("EDITOR", name + "\n" + inhalt)
            # 1. in die Werkstatt — unveraendert, wie er in der Eingabe steht.
            WERKSTATT.mkdir(parents=True, exist_ok=True)
            ziel = WERKSTATT / name
            ziel.write_text(inhalt, encoding="utf-8")
            # 2. uebersetzen mit dem Interpreter des Kurses. Sein Wort (16.10.2026, 02:50): „der
            #    Interpreter-Ausgang gibt nur die Meldung vom Interpreter aus, so wie er es macht, und
            #    nicht wie du es willst!" — zeilen = wortgetreu stdout+stderr des Interpreters, sonst
            #    nichts; py_compile schreibt bei Erfolg nichts, dann ist zeilen leer. Rueckgabewert und
            #    Hinweis gehen getrennt mit (fuer die Standzeile, nicht fuer das Fenster).
            r2 = subprocess.run([_py(), "-m", "py_compile", str(ziel)], capture_output=True,
                                text=True, timeout=60, env=umgebung(), **OHNE_FENSTER, **LESEN)
            roh = ((r2.stdout or "") + (r2.stderr or "")).rstrip()
            zeilen = roh.splitlines()
            protokoll("UEBERSETZT" if r2.returncode == 0 else "NICHT_UEBERS",
                      f"{name} | Rueckgabewert {r2.returncode} | " + (" | ".join(zeilen)[:600] or "(keine Ausgabe)"))
            return self._json({"zeilen": zeilen, "ok": r2.returncode == 0, "rc": r2.returncode, "name": name,
                               "hinweis": hinweis, "inhalt": inhalt if hinweis else None})
        if self.path == "/notiz":
            protokoll(str(daten.get("art") or "NOTIZ")[:12], str(daten.get("text") or "")[:4000])
            return self._json({"ok": True})
        if self.path == "/seriell/oeffnen":
            with _sperre:
                laeuft = any(not j["fertig"] for j in _jobs.values())
            if laeuft:
                return self._json({"fehler": "Ein Werkzeug benutzt die Leitung gerade."}, 409)
            try:
                port = SERIELL.oeffnen(str(daten.get("port") or "COM3").strip())
                protokoll("SERIELL", "verbunden " + port)
                return self._json({"ok": True, "port": port})
            except Exception as ex:                                 # noqa: BLE001
                return self._json({"fehler": f"{type(ex).__name__}: {ex}"}, 500)
        if self.path == "/seriell/senden":
            try:
                art = str(daten.get("art") or "")
                roh = {"strg_c": b"\x03", "strg_d": b"\x04"}.get(art, b"")
                text = str(daten.get("text") or "")
                SERIELL.senden(text, roh)
                protokoll("REPL", art or text)
                return self._json({"ok": True})
            except Exception as ex:                                 # noqa: BLE001
                return self._json({"fehler": f"{type(ex).__name__}: {ex}"}, 500)
        if self.path == "/seriell/schliessen":
            SERIELL.schliessen()
            protokoll("SERIELL", "getrennt")
            return self._json({"ok": True})
        if self.path == "/werkzeug":
            name = str(daten.get("name") or "")
            eingabe = daten.get("eingabe") or {}
            if name not in ("programm_testen", "esp32_firmware", "esp32_laden", "esp32_nachlesen",
                            "ports_zeigen", "geraet_zeigen", "quelltext_pruefen"):
                return self._json({"fehler": f"{name} ist hier nicht vorgesehen"}, 400)
            if SERIELL.v is not None:
                SERIELL.schliessen()           # die Leitung gehoert jetzt dem Werkzeug
                protokoll("SERIELL", "getrennt, weil " + name + " die Leitung braucht")
            try:
                nr = job_starten(werkzeug_befehl(name, eingabe),
                                 f"{name} {json.dumps(eingabe, ensure_ascii=False)}")
            except FileNotFoundError as ex:
                return self._json({"fehler": str(ex)}, 404)
            return self._json({"id": nr})
        return self._json({"fehler": "nicht gefunden"}, 404)


def modell_sicherstellen():
    """Alles in einem (sein Wort 15.10.2026): laeuft kein Modellserver, wird das 7B gestartet."""
    try:
        import modell as _m
        if not _m.laeuft_schon(2.0):
            print("Modellserver wird gestartet …", flush=True)
            _m.starten(laut=False)
            print("Modellserver laeuft:", _m.geladenes() or "127.0.0.1:8099", flush=True)
    except Exception as ex:                                       # noqa: BLE001
        print(f"Modellserver nicht gestartet: {type(ex).__name__}: {ex}", flush=True)


def main() -> int:
    PROGRAMME.mkdir(exist_ok=True)
    WERKSTATT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=modell_sicherstellen, daemon=True).start()
    protokoll("START", "Diener gestartet; Schalter: " + fenster_ist_der_schalter())
    for sig in ("SIGBREAK", "SIGINT", "SIGTERM"):       # Strg+Untbr, Strg+C, kursagent stop
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), lambda *_: aufraeumen("Fenster geschlossen"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8777), H)
    print("Seite: http://127.0.0.1:8777", flush=True)
    import os
    if os.environ.get("KURS_BROWSER") == "1":      # START.bat setzt das; ueber die Bruecke kein neues Fenster
        threading.Thread(target=lambda: (time.sleep(0.8), webbrowser.open("http://127.0.0.1:8777")),
                         daemon=True).start()
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
