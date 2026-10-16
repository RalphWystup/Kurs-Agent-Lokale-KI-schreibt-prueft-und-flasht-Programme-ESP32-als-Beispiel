#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruefstand des Schalters — laeuft AUF seinem Rechner (Bruecke: python pruefe_start.py).

Sein Wort (16.10.2026, 02:35): „ich will doch eine start bat zum starten! das muss alles ausloesen
und wenn ich diese schliesse — sie bleibt offen solange ich arbeite — wird wieder alles abgestellt."
Hier wird START.bat in einem eigenen Fenster gestartet, gemessen, ob Diener und Modell kommen,
dann das Fenster geschlossen wie mit der Maus (WM_CLOSE) und gemessen, ob alles weg ist.

    python pruefe_start.py            (vorher darf nichts auf 8777 laufen)
"""
import ctypes
import json
import pathlib
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes

HIER = pathlib.Path(__file__).resolve().parent
PROTOKOLL = HIER / "ablage" / "protokoll_testen.txt"
BEFUNDE = []
OHNE = dict(creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def hole(url, zeit=3):
    with urllib.request.urlopen(url, timeout=zeit) as r:
        return r.read().decode("utf-8", "replace")


def diener_da():
    try:
        return '"wurzel"' in hole("http://127.0.0.1:8777/zustand")
    except Exception:                                             # noqa: BLE001
        return False


def modell_da():
    try:
        req = urllib.request.Request("http://127.0.0.1:8099/v1/chat/completions",
                                     data=json.dumps({"messages": [{"role": "user", "content": "Sag nur: ja"}], "max_tokens": 5}).encode(),
                                     headers={"Content-Type": "application/json"})
        return "choices" in urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    except Exception:                                             # noqa: BLE001
        return False


def llama_laeuft():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq llama-server.exe"], capture_output=True, text=True, encoding="cp850", errors="replace", **OHNE)
    return "llama-server.exe" in (r.stdout or "")


def diener_prozesse():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*oberflaeche.py*' }).Count"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, **OHNE)
    return (r.stdout or "0").strip()


def fenster_schliessen(titel="Kurs-Agent"):
    """Das Konsolenfenster mit diesem Titel schliessen wie mit der Maus (WM_CLOSE) — nur Konsolen,
    nie den Browser (Klassen ConsoleWindowClass / Windows Terminal)."""
    u = ctypes.windll.user32
    gefunden = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def jedes(hwnd, _):
        n = u.GetWindowTextLengthW(hwnd)
        if n:
            puf = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(hwnd, puf, n + 1)
            kl = ctypes.create_unicode_buffer(256); u.GetClassNameW(hwnd, kl, 256)
            if titel in puf.value and kl.value in ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"):
                gefunden.append((hwnd, puf.value, kl.value))
        return True
    u.EnumWindows(PROC(jedes), 0)
    for hwnd, _, _ in gefunden:
        u.PostMessageW(hwnd, 0x0010, 0, 0)                      # WM_CLOSE
    return gefunden


def pruefe(nr, was, ok, beleg):
    BEFUNDE.append((nr, was, bool(ok), beleg))
    print(f"  {nr:4s} {'ERFUELLT      ' if ok else 'NICHT ERFUELLT'}  {was}\n        {beleg[:200]}", flush=True)


def main() -> int:
    print("PRUEFSTAND SCHALTER — START.bat starten, Fenster schliessen, nachmessen", flush=True)
    pruefe("F1", "vorher: nichts auf 8777, kein llama-server", not diener_da() and not llama_laeuft(),
           f"Diener {diener_da()}, llama {llama_laeuft()}, Diener-Prozesse {diener_prozesse()}")
    zeilen_vorher = len(PROTOKOLL.read_text(encoding="utf-8", errors="replace").splitlines()) if PROTOKOLL.is_file() else 0
    t0 = time.time()
    p = subprocess.Popen(["cmd", "/c", str(HIER / "START.bat")], cwd=str(HIER), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    pruefe("F2", "START.bat in eigenem Fenster gestartet", p.pid > 0, f"PID {p.pid}")
    while time.time() - t0 < 150 and not diener_da():
        time.sleep(1)
    pruefe("F3", "Diener antwortet nach dem Start", diener_da(), f"nach {time.time() - t0:.0f} s")
    while time.time() - t0 < 300 and not modell_da():
        time.sleep(2)
    pruefe("F4", "Modell antwortet (8099) — die bat hat alles ausgeloest", modell_da(), f"nach {time.time() - t0:.0f} s")
    proto = PROTOKOLL.read_text(encoding="utf-8", errors="replace").splitlines()[zeilen_vorher:]
    start = [z for z in proto if "  START " in z]
    pruefe("F5", "Diener meldet beide Sicherungen (Ctrl-Handler, Job-Objekt) gesetzt",
           start and "Ctrl-Handler gesetzt" in start[-1] and "Job-Objekt gesetzt" in start[-1], start[-1][20:] if start else "keine START-Zeile")
    f = fenster_schliessen()
    pruefe("F6", "Fenster der bat gefunden und WM_CLOSE geschickt (wie Klick auf X)", len(f) == 1, "; ".join(f"{t} [{k}]" for _, t, k in f) or "kein Konsolenfenster 'Kurs-Agent'")
    t1 = time.time()
    while time.time() - t1 < 15 and (diener_da() or llama_laeuft()):
        time.sleep(1)
    pruefe("F7", "nach dem Schliessen: Diener weg (8777 antwortet nicht)", not diener_da(), f"nach {time.time() - t1:.0f} s; Diener-Prozesse {diener_prozesse()}")
    pruefe("F8", "nach dem Schliessen: Modellserver weg", not llama_laeuft(), "tasklist llama-server.exe")
    proto = PROTOKOLL.read_text(encoding="utf-8", errors="replace").splitlines()[zeilen_vorher:]
    ende = [z for z in proto if "  ENDE " in z]
    pruefe("F9", "Protokoll: ENDE 'Fenster geschlossen' (sauber aufgeraeumt, nicht hart beendet)", ende and "Fenster geschlossen" in ende[-1], ende[-1][:120] if ende else "keine ENDE-Zeile — hart beendet (Job-Objekt hat gekillt?)")
    print("-" * 78)
    gut = sum(1 for b in BEFUNDE if b[2])
    print(f"{gut} von {len(BEFUNDE)} erfuellt")
    print("SCHALTER BESTANDEN" if gut == len(BEFUNDE) else "SCHALTER NICHT BESTANDEN")
    return 0 if gut == len(BEFUNDE) else 1


if __name__ == "__main__":
    sys.exit(main())
