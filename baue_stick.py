#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stellt den gebrauchsfertigen Ordner zusammen — das, was auf den Stick kommt.

    python baue_stick.py E:\\Kurs_Agent      Ziel angeben
    python baue_stick.py                     legt .\\Kurs_Agent_Stick an

Mitgenommen wird, was zum Betrieb gehoert. Nicht mitgenommen wird, was beim Entwickeln
entsteht: die Ablage, Zwischenspeicher, Uebertragungsordner. Sonst landet der Zustand des
Erbauerrechners auf dem Stick — und mit ihm Dateien, die dort niemand erwartet.

Das mitgelieferte Paket (paket\\) wird uebernommen, wenn es gefuellt ist, sonst wird es
gemeldet: ein Stick ohne Modell startet im Kurs nicht.
"""
from __future__ import annotations
import pathlib, shutil, sys

HIER = pathlib.Path(__file__).resolve().parent
MIT  = ["START.bat", "hole_paket.py", "baue_stick.py", "erstelle_anleitung.py", "pruefe_rechner.py",
        "pruefe_alles.py", "pruefe_unversehrtheit.py", "sammle_bericht.py",
        "ANFORDERUNGEN.md", "PRUEFPROTOKOLL.md", "LIESMICH.md",
        "agent", "paket"]
# Die Anleitung traegt ihre Fassung im Namen; deshalb wird sie ueber ein Muster gesucht
# statt fest benannt — sonst faellt sie beim naechsten Fassungswechsel still weg.
#
# Am 02.10.2026 stand hier das Muster "Kurs_Agent_Bedienung_*.html". Eine Datei dieses
# Namens gibt es nicht; die Anleitung heisst "Kurs_Agent_Inbetriebnahme_*.html". Der Stick
# waere also **ohne Anleitung** gebaut worden, und niemand haette es gemerkt: ein Muster,
# das nichts findet, meldet nichts. Deshalb prueft pruefe() unten jetzt jedes Muster
# einzeln und schlaegt Alarm, wenn eines leer ausgeht.
MUSTER = ["Kurs_Agent_Inbetriebnahme_*.html"]
OHNE = {"ablage", "Arbeitsstand", "Bilder", "__pycache__", ".git", "Sicherung"}


def _ohne(ordner, namen):
    return [n for n in namen if n in OHNE or n.endswith(".pyc")]


def main():
    ziel = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HIER / "Kurs_Agent_Stick"
    if ziel == HIER:
        raise SystemExit("Das Ziel darf nicht der Quellordner selbst sein.")
    if ziel.exists() and any(ziel.iterdir()):
        antwort = input(f"{ziel} ist nicht leer. Inhalt ersetzen? [nein] ").strip().lower()
        if antwort not in ("j", "ja", "y", "yes"):
            raise SystemExit("Abgebrochen; es wurde nichts geaendert.")
    ziel.mkdir(parents=True, exist_ok=True)

    n, b = 0, 0
    fehlt = []                 # was nicht da war -- am Ende EINE deutliche Bilanz daraus
    for muster in MUSTER:
        treffer = sorted(HIER.glob(muster))
        if not treffer:
            print(f"  FEHLT: kein Treffer fuer {muster}")
            fehlt.append(muster)
        for d in treffer:
            shutil.copy2(d, ziel / d.name)
            n += 1; b += d.stat().st_size
            print(f"  {d.name}")
    for name in MIT:
        q = HIER / name
        if not q.exists():
            print(f"  FEHLT: {name}")
            fehlt.append(name)
            continue
        z = ziel / name
        if q.is_dir():
            if z.exists():
                shutil.rmtree(z)
            shutil.copytree(q, z, ignore=_ohne)
        else:
            shutil.copy2(q, z)
        for d in ([z] if z.is_file() else [x for x in z.rglob("*") if x.is_file()]):
            n += 1; b += d.stat().st_size
        print(f"  {name}")

    print(f"\n{n} Dateien, {b/1e9:.2f} GB in {ziel}")
    # Eine einzelne Zeile mitten in 98 Zeilen Ausgabe uebersieht jeder. Am 02.10.2026 fiel
    # so auf, dass das Muster fuer die Anleitung ins Leere zeigte und der Stick seit
    # Tagen ohne sie gebaut worden waere. Deshalb steht das Fehlende jetzt am Schluss,
    # und der Bau gilt als nicht bestanden.
    sys.path.insert(0, str(ziel / "agent"))
    import importlib, os
    os.environ["KURS_AGENT_WURZEL"] = str(ziel)
    import pfade; importlib.reload(pfade)
    print(pfade.bericht())
    if not pfade.eine("modell/*.gguf"):
        print("\nACHTUNG: ohne Modell startet der Agent im Kurs nicht. "
              "Erst 'python hole_paket.py' laufen lassen, dann diesen Ordner bauen.")
    if fehlt:
        print(f"\n  ES FEHLEN {len(fehlt)} TEILE -- dieser Ordner ist NICHT weitergabefertig:")
        for f in fehlt:
            print(f"      {f}")
        print("  Fehlt ein Muster, zeigt es auf einen Namen, den es nicht (mehr) gibt.")
        return 1
    print("\n  Vollstaendig: jedes Teil der Stueckliste ist im Ordner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
