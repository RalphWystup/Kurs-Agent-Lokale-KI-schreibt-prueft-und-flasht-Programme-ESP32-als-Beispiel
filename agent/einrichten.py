#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Einrichten vor dem Start — nachsehen, was da ist; nur das Fehlende aus dem Paket (Gebot 8, 9).

Sein Wort (15.10.2026): „Bevor etwas auf diesem Rechner installiert wird, wie Treiber, ist
nachzusehen, ob es dieses schon gibt. Ansonsten ist alles mitzuführen — wir haben ja kein
Internet!" — und: „eine bat, die ich aufrufe, um alles zu installieren, was noch nicht
installiert ist, dann geht die HTML auf."

Dieses Programm wird von START.bat mit dem Python aus paket\\python_vorlage (oder, wenn schon
eingerichtet, aus ablage\\python) aufgerufen. Jeder Schritt: MESSEN -> fehlt? -> aus dem Paket
nehmen -> MESSEN. Nichts kommt aus dem Netz. Was das Paket nicht hat, wird gesagt.

    python einrichten.py            einrichten, Bericht
    python einrichten.py --pruefen  nur messen, nichts aendern
"""
import os
import pathlib
import shutil
import subprocess
import sys
import zipfile

HIER = pathlib.Path(__file__).resolve().parent
WURZEL = HIER.parent
PAKET = WURZEL / "paket"
ABLAGE = WURZEL / "ablage"
PY = ABLAGE / "python" / "python.exe"
VORLAGE = PAKET / "python_vorlage"
PAKETE = PAKET / "pakete"
BEFUNDE = []
NUR_PRUEFEN = "--pruefen" in sys.argv
NUR_TREIBER = "--treiber" in sys.argv      # von START.bat mit Administratorrechten aufgerufen: nur E5
TREIBER_RECHTE = 3                          # Rueckgabewert: Treiber fehlt, Windows verlangt Rechte -> START.bat holt sie fuer diesen Schritt


def sag(nr, was, zustand, beleg):
    BEFUNDE.append((nr, was, zustand, beleg))
    print(f"  {nr}  {zustand:<14} {was}\n       {beleg}", flush=True)


def lauf(befehl, zeit=600):
    return subprocess.run(befehl, capture_output=True, text=True, timeout=zeit,
                          encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def python_laeuft(exe: pathlib.Path) -> str:
    if not exe.is_file():
        return ""
    try:
        r = lauf([str(exe), "-c", "import sys; print(sys.version.split()[0])"], 30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:                                             # noqa: BLE001
        return ""


RECHTE_NOETIG = False


def nur_treiber() -> int:
    """START.bat ruft das mit Administratorrechten auf, wenn der Treiber fehlt und pnputil ohne Rechte scheitert."""
    # E5 — der CH340-Treiber (USB-seriell): nachsehen, nicht blind installieren
    try:
        r = lauf(["pnputil", "/enum-drivers"], 60)
        da = "ch341" in (r.stdout or "").lower() or "ch340" in (r.stdout or "").lower()
    except Exception:                                             # noqa: BLE001
        da = False
    treiber = sorted((PAKET / "treiber").glob("*")) if (PAKET / "treiber").is_dir() else []
    #  Sein Wort (16.10.2026, 14:35): „Beim User muss alles automatisch installiert werden, wenn es nicht schon
    #  vorhanden ist — und es muss ohne Internet gehen!"  Also: nachsehen; fehlt der Treiber, aus dem Paket
    #  installieren (pnputil, Windows-Bordmittel, kein Netz). Verweigert Windows das mangels Rechten, wird gesagt,
    #  dass START.bat einmal „Als Administrator" zu starten ist — nur dann, nur dafuer.
    inf = sorted((PAKET / "treiber").rglob("*.inf")) if (PAKET / "treiber").is_dir() else []
    if da:
        sag("E5", "CH340-Treiber", "VORHANDEN", "im Treiberspeicher von Windows (pnputil)")
    elif not treiber:
        sag("E5", "CH340-Treiber", "FEHLT", "nicht im Treiberspeicher von Windows, und im Paket liegt kein Treiber (paket\\treiber ist leer).")
    elif NUR_PRUEFEN:
        sag("E5", "CH340-Treiber", "FEHLT", "nicht im Treiberspeicher; im Paket: " + ", ".join(t.name for t in treiber) + " (nur geprueft)")
    elif not inf:
        sag("E5", "CH340-Treiber", "FEHLT", "im Paket liegt nur ein Archiv (" + ", ".join(t.name for t in treiber)
            + ") ohne entpackte .inf — Archiv in paket\\treiber entpacken, dann START.bat erneut; oder das Installationsprogramm darin starten.")
    else:
        r = lauf(["pnputil", "/add-driver", str(inf[0]), "/install"], 300)
        try:
            r2 = lauf(["pnputil", "/enum-drivers"], 60)
            ok = "ch341" in (r2.stdout or "").lower() or "ch340" in (r2.stdout or "").lower()
        except Exception:                                         # noqa: BLE001
            ok = False
        sag("E5", "CH340-Treiber", "EINGERICHTET" if ok else "NICHT MOEGLICH",
            f"aus dem Paket installiert ({inf[0].name}), nachgemessen im Treiberspeicher" if ok
            else "pnputil hat den Treiber aus dem Paket nicht aufgenommen (Rueckgabe " + str(r.returncode) + "): "
                 + (r.stdout or r.stderr)[-160:].strip().replace("\n", " ")
                 + " — Windows verlangt dafuer Administratorrechte; START.bat holt sie fuer diesen einen Schritt (Abfrage mit Ja beantworten).")
        if not ok:
            global RECHTE_NOETIG
            RECHTE_NOETIG = True

    return 0 if not RECHTE_NOETIG else 1


def main() -> int:
    print("EINRICHTEN — nachsehen, dann nur das Fehlende aus dem Paket" + (" (nur Treiber, mit Rechten)" if NUR_TREIBER else ""), flush=True)
    if NUR_TREIBER:
        return nur_treiber()

    # E1 — das Python des Kurses
    v = python_laeuft(PY)
    if v:
        sag("E1", "Python des Kurses (ablage\\python)", "VORHANDEN", f"laeuft, {v}")
    else:
        vv = python_laeuft(VORLAGE / "python.exe")
        if not vv:
            sag("E1", "Python des Kurses", "FEHLT", "weder ablage\\python noch paket\\python_vorlage laeuft — "
                "das Paket ist unvollstaendig; nichts wird aus dem Netz geholt.")
            return 1
        if NUR_PRUEFEN:
            sag("E1", "Python des Kurses", "FEHLT", f"Vorlage da ({vv}); wuerde nach ablage\\python kopiert")
        else:
            ABLAGE.mkdir(exist_ok=True)
            shutil.copytree(VORLAGE, ABLAGE / "python", dirs_exist_ok=True)
            v = python_laeuft(PY)
            sag("E1", "Python des Kurses", "EINGERICHTET" if v else "FEHLT",
                f"aus paket\\python_vorlage kopiert; laeuft: {v or 'nein'}")
            if not v:
                return 1

    # E2 — pip im Python des Kurses (fuer die Pakete)
    r = lauf([str(PY), "-m", "pip", "--version"], 60)
    if r.returncode == 0:
        sag("E2", "pip", "VORHANDEN", r.stdout.strip()[:80])
    elif (PAKET / "get-pip.py").is_file() and not NUR_PRUEFEN:
        r = lauf([str(PY), str(PAKET / "get-pip.py"), "--no-index", "--find-links", str(PAKETE)], 600)
        ok = lauf([str(PY), "-m", "pip", "--version"], 60).returncode == 0
        sag("E2", "pip", "EINGERICHTET" if ok else "FEHLT", "aus paket\\get-pip.py" if ok else (r.stderr or r.stdout)[-300:])
    else:
        sag("E2", "pip", "FEHLT", "paket\\get-pip.py " + ("fehlt" if not (PAKET / "get-pip.py").is_file() else "da (nur geprueft)"))

    # E3 — die Pakete pyserial, mpremote, esptool
    for modul, paketname in (("serial", "pyserial"), ("mpremote", "mpremote"), ("esptool", "esptool")):
        r = lauf([str(PY), "-c", f"import {modul}; print(getattr({modul}, '__version__', 'da'))"], 60)
        if r.returncode == 0:
            sag("E3", f"Paket {paketname}", "VORHANDEN", r.stdout.strip()[:60])
            continue
        #  Rad (.whl) oder Quellarchiv (.tar.gz — so liefert hole_paket esptool; pip baut es offline, setuptools und
        #  wheel liegen als Raeder bei). 16.10.2026, 15:10 gemessen: esptool lag nur als .tar.gz da -> „kein Rad".
        raeder = sorted(p for p in PAKETE.glob(f"{paketname}*") if p.suffix in (".whl", ".gz", ".zip")) if PAKETE.is_dir() else []
        if not raeder:
            sag("E3", f"Paket {paketname}", "FEHLT", f"kein Rad und kein Quellarchiv in paket\\pakete — nichts wird aus dem Netz geholt")
            continue
        if NUR_PRUEFEN:
            sag("E3", f"Paket {paketname}", "FEHLT", f"Rad da: {raeder[-1].name} (nur geprueft)")
            continue
        r = lauf([str(PY), "-m", "pip", "install", "--no-index", "--find-links", str(PAKETE), paketname], 600)
        ok = lauf([str(PY), "-c", f"import {modul}"], 60).returncode == 0
        sag("E3", f"Paket {paketname}", "EINGERICHTET" if ok else "FEHLT",
            f"aus {raeder[-1].name}" if ok else (r.stderr or r.stdout)[-300:])

    # E4 — tkinter (Fenster der Werkzeuge)
    r = lauf([str(PY), "-c", "import tkinter; print(tkinter.TkVersion)"], 60)
    if r.returncode == 0:
        sag("E4", "tkinter", "VORHANDEN", f"Tk {r.stdout.strip()}")
    else:
        z = sorted(PAKET.glob("tkinter-*.zip"))
        if z and not NUR_PRUEFEN:
            with zipfile.ZipFile(z[-1]) as zf:
                zf.extractall(ABLAGE / "python")
            ok = lauf([str(PY), "-c", "import tkinter"], 60).returncode == 0
            sag("E4", "tkinter", "EINGERICHTET" if ok else "FEHLT", f"aus {z[-1].name}")
        else:
            sag("E4", "tkinter", "FEHLT", "kein tkinter-Zip im Paket" if not z else "Zip da (nur geprueft)")

    # E5 — der CH340-Treiber (USB-seriell): nachsehen, nicht blind installieren
    try:
        r = lauf(["pnputil", "/enum-drivers"], 60)
        da = "ch341" in (r.stdout or "").lower() or "ch340" in (r.stdout or "").lower()
    except Exception:                                             # noqa: BLE001
        da = False
    treiber = sorted((PAKET / "treiber").glob("*")) if (PAKET / "treiber").is_dir() else []
    #  Sein Wort (16.10.2026, 14:35): „Beim User muss alles automatisch installiert werden, wenn es nicht schon
    #  vorhanden ist — und es muss ohne Internet gehen!"  Also: nachsehen; fehlt der Treiber, aus dem Paket
    #  installieren (pnputil, Windows-Bordmittel, kein Netz). Verweigert Windows das mangels Rechten, wird gesagt,
    #  dass START.bat einmal „Als Administrator" zu starten ist — nur dann, nur dafuer.
    inf = sorted((PAKET / "treiber").rglob("*.inf")) if (PAKET / "treiber").is_dir() else []
    if da:
        sag("E5", "CH340-Treiber", "VORHANDEN", "im Treiberspeicher von Windows (pnputil)")
    elif not treiber:
        sag("E5", "CH340-Treiber", "FEHLT", "nicht im Treiberspeicher von Windows, und im Paket liegt kein Treiber (paket\\treiber ist leer).")
    elif NUR_PRUEFEN:
        sag("E5", "CH340-Treiber", "FEHLT", "nicht im Treiberspeicher; im Paket: " + ", ".join(t.name for t in treiber) + " (nur geprueft)")
    elif not inf:
        sag("E5", "CH340-Treiber", "FEHLT", "im Paket liegt nur ein Archiv (" + ", ".join(t.name for t in treiber)
            + ") ohne entpackte .inf — Archiv in paket\\treiber entpacken, dann START.bat erneut; oder das Installationsprogramm darin starten.")
    else:
        r = lauf(["pnputil", "/add-driver", str(inf[0]), "/install"], 300)
        try:
            r2 = lauf(["pnputil", "/enum-drivers"], 60)
            ok = "ch341" in (r2.stdout or "").lower() or "ch340" in (r2.stdout or "").lower()
        except Exception:                                         # noqa: BLE001
            ok = False
        sag("E5", "CH340-Treiber", "EINGERICHTET" if ok else "NICHT MOEGLICH",
            f"aus dem Paket installiert ({inf[0].name}), nachgemessen im Treiberspeicher" if ok
            else "pnputil hat den Treiber aus dem Paket nicht aufgenommen (Rueckgabe " + str(r.returncode) + "): "
                 + (r.stdout or r.stderr)[-160:].strip().replace("\n", " ")
                 + " — Windows verlangt dafuer Administratorrechte; START.bat holt sie fuer diesen einen Schritt (Abfrage mit Ja beantworten).")
        if not ok:
            global RECHTE_NOETIG
            RECHTE_NOETIG = True

    # E6 — Modell und Modellserver
    gguf = sorted((PAKET / "modell").glob("*.gguf")) if (PAKET / "modell").is_dir() else []
    srv = [p for p in PAKET.rglob("llama-server.exe")]
    sag("E6", "Sprachmodell", "VORHANDEN" if gguf else "FEHLT",
        ", ".join(f"{g.name} ({g.stat().st_size / 1e9:.1f} GB)" for g in gguf) or "keine .gguf in paket\\modell")
    sag("E7", "Modellserver llama-server", "VORHANDEN" if srv else "FEHLT", str(srv[0].relative_to(WURZEL)) if srv else "nicht im Paket")

    # E8 — Firmware und Werkzeuge
    fw = sorted((PAKET / "firmware").glob("*.bin")) if (PAKET / "firmware").is_dir() else []
    sag("E8", "MicroPython-Firmware", "VORHANDEN" if fw else "FEHLT", ", ".join(f.name for f in fw) or "keine .bin")
    wz = sorted((HIER / "werkzeuge").glob("*.py"))
    sag("E9", "Werkzeuge", "VORHANDEN" if len(wz) >= 10 else "FEHLT", f"{len(wz)} Programme in agent\\werkzeuge")
    sag("E10", "Seite", "VORHANDEN" if (WURZEL / "Frage.html").is_file() else "FEHLT", "Frage.html")

    fehlt = [b for b in BEFUNDE if b[2] in ("FEHLT", "NICHT MOEGLICH")]
    print("-" * 78)
    print(f"{len(BEFUNDE) - len(fehlt)} von {len(BEFUNDE)} vorhanden oder eingerichtet"
          + (f"; FEHLT: " + ", ".join(b[1] for b in fehlt) if fehlt else ""))
    print("EINRICHTUNG " + ("VOLLSTAENDIG" if not fehlt else "UNVOLLSTAENDIG — siehe oben"))
    if RECHTE_NOETIG:
        return TREIBER_RECHTE
    return 0 if not fehlt else 1


if __name__ == "__main__":
    sys.exit(main())
