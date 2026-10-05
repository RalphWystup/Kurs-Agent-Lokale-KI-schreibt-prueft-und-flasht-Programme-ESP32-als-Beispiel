#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sammelt alles, was zur Ferndiagnose gebraucht wird, in **eine** Datei.

    python sammle_bericht.py

Erzeugt ``BERICHT_<Datum>_<Zeit>.txt`` im Kursordner. Diese eine Datei genuegt, um von
aussen zu beurteilen, was auf diesem Rechner geschehen ist — ohne dass jemand danebensitzt
und ohne dass er erklaeren muss, was er gesehen hat.

Gesammelt wird:

    1  der Rechner          Windows, Speicher, Kerne, Platz, Grafik, Python
    2  das Paket            was da ist, was fehlt, welches Modell gewaehlt wuerde
    3  die Selbstpruefung   pruefe_alles.py, alle Punkte mit Ergebnis
    4  die Werkzeugprobe    jedes Werkzeug einmal, ohne Modell
    5  das Protokoll        was der Agent zuletzt getan hat
    6  die Ablage           welche Dateien entstanden sind

**Was nicht hineinkommt:** Benutzernamen werden zu <BENUTZER>, der Rechnername zu
<RECHNER>. Ein Bericht wandert zu jemandem, der ihn liest — er soll sagen, was das Paket
tut, und nicht, wem der Rechner gehoert.
"""
from __future__ import annotations
import datetime, os, pathlib, platform, re, subprocess, sys

HIER = pathlib.Path(__file__).resolve().parent
PY = sys.executable
EIGEN = HIER / "ablage" / "python" / ("python.exe" if os.name == "nt" else "python.exe")


def _anonym(text: str) -> str:
    """Nimmt Benutzer- und Rechnernamen heraus. Der Bericht soll weitergegeben werden."""
    for name, marke in ((os.environ.get("USERNAME") or os.environ.get("USER"), "<BENUTZER>"),
                        (platform.node(), "<RECHNER>"),
                        (os.environ.get("USERDOMAIN"), "<NETZ>")):
        if name and len(name) > 2:
            text = re.sub(re.escape(name), marke, text, flags=re.I)
    return text


def _lauf(befehl, zeit=900) -> str:
    try:
        r = subprocess.run(befehl, capture_output=True, text=True, timeout=zeit,
                           encoding="utf-8", errors="replace", cwd=str(HIER))
        return ((r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr.strip() else "")).strip()
    except subprocess.TimeoutExpired:
        return f"(nach {zeit} s abgebrochen)"
    except Exception as e:
        return f"({type(e).__name__}: {e})"


def abschnitt(titel: str, inhalt: str) -> str:
    strich = "=" * 74
    return f"\n{strich}\n  {titel}\n{strich}\n{inhalt or '(nichts)'}\n"


def main():
    jetzt = datetime.datetime.now()
    ziel = HIER / f"BERICHT_{jetzt:%Y-%m-%d_%H%M}.txt"
    # Welches Python? Das eigene, falls es da ist **und laeuft** — dann beschreibt der
    # Bericht genau die Umgebung, in der der Agent arbeitet. Dass die Datei existiert,
    # genuegt nicht: sie kann aus einem Archiv stammen und auf diesem System nicht
    # ausfuehrbar sein. Also wird gefragt, nicht geglaubt.


    py, teile_hinweis = PY, None
    if EIGEN.exists():
        try:
            probe = subprocess.run([str(EIGEN), "-c", "print(1)"], capture_output=True,
                                   text=True, timeout=120)
            if probe.returncode == 0:
                py = str(EIGEN)
            else:
                teile_hinweis = (f"Das eigene Python unter {EIGEN} antwortet nicht "
                                 f"({(probe.stderr or '').strip()[:120]}).")
        except Exception as e:
            # Die Datei kann da sein und sich trotzdem nicht starten lassen — etwa weil
            # sie aus einem Archiv stammt und das System sie nicht ausfuehren darf. Das
            # ist kein Grund, den ganzen Bericht ausfallen zu lassen.
            teile_hinweis = (f"Das eigene Python unter {EIGEN} liess sich nicht starten "
                             f"({type(e).__name__}).")
    if teile_hinweis:
        teile_hinweis += f" Der Bericht wurde deshalb mit {PY} erstellt."

    teile = [f"Kurs-Agent — Bericht vom {jetzt:%d.%m.%Y %H:%M:%S}",
             f"Ordner: {HIER}",
             f"Python fuer diesen Bericht: {py}",
             f"(Dieser Bericht ist zum Weitergeben gedacht. Benutzer- und Rechnername "
             f"sind durch Platzhalter ersetzt.)"]
    if locals().get("teile_hinweis"):
        teile.append("\nHINWEIS: " + teile_hinweis)

    print("  [1/6] Rechner …", flush=True)
    teile.append(abschnitt("1 — Der Rechner", _lauf([py, str(HIER / "pruefe_rechner.py")], 300)))

    print("  [2/6] Paket …", flush=True)
    teile.append(abschnitt("2 — Das Paket", _lauf([py, str(HIER / "agent" / "pfade.py")], 120)))

    print("  [3/6] Selbstpruefung (dauert) …", flush=True)
    teile.append(abschnitt("3 — Selbstpruefung gegen die Anforderungen",
                           _lauf([py, str(HIER / "pruefe_alles.py")], 1800)))

    print("  [4/6] Werkzeugprobe …", flush=True)
    teile.append(abschnitt("4 — Jedes Werkzeug einmal, ohne Modell",
                           _lauf([py, str(HIER / "agent" / "agent.py"), "--probe"], 1800)))

    print("  [5/6] Protokoll …", flush=True)
    prot = HIER / "ablage" / "protokoll.txt"
    teile.append(abschnitt("5 — Protokoll des letzten Laufs",
                           prot.read_text(encoding="utf-8", errors="replace")[-12000:]
                           if prot.is_file() else "(noch kein Lauf)"))

    print("  [6/6] Ablage …", flush=True)
    ablage = HIER / "ablage"
    if ablage.is_dir():
        dateien = sorted(p for p in ablage.rglob("*") if p.is_file())
        liste = "\n".join(f"  {p.stat().st_size:10d}  {p.relative_to(ablage)}"
                          for p in dateien[:80])
        if len(dateien) > 80:
            liste += f"\n  … und {len(dateien)-80} weitere"
        liste += f"\n  zusammen {len(dateien)} Dateien, " \
                 f"{sum(p.stat().st_size for p in dateien)/1e6:.1f} MB"
    else:
        liste = "(keine Ablage — entweder noch nichts gelaufen oder schon aufgeraeumt)"
    teile.append(abschnitt("6 — Was in der Ablage liegt", liste))

    ziel.write_text(_anonym("\n".join(teile)), encoding="utf-8")
    print(f"\n  Bericht geschrieben: {ziel}")
    print(f"  {ziel.stat().st_size/1024:.0f} kB. Diese eine Datei genuegt zur Ferndiagnose.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
