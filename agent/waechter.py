#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Meldet jeden Schreibversuch ausserhalb der Ablage — waehrend er geschieht.

Python meldet seit Fassung 3.8 sicherheitsrelevante Vorgaenge an angemeldete Beobachter
(PEP 578). Einer davon ist ``open`` mit Schreibabsicht. Dieser Waechter haengt sich dort
ein und sieht damit **jedes** Oeffnen zum Schreiben, das aus diesem Programm kommt — auch
aus einer Bibliothek, die man nicht gelesen hat.

Das ist etwas anderes als die Pruefung in ``in_der_ablage()``: die prueft, was ein Werkzeug
bewusst tun will, dieser hier sieht, was wirklich geschieht. Beides zusammen deckt den Fall
ab, dass eine Bibliothek nebenbei eine Datei anlegt, an die niemand gedacht hat.

**Grenze, die dazugehoert:** Unterprozesse sind nicht erfasst. Wenn das entpackte Python
pip startet, laeuft dort ein eigener Beobachterkreis; dieser Waechter sieht davon nichts.
Dafuer sorgen die abgeschirmte Umgebung (``PIP_CACHE_DIR``, ``PYTHONNOUSERSITE``) und der
Nachweis vorher/nachher. Ein Waechter, der mehr verspraeche, als er sieht, waere schlimmer
als keiner.
"""
from __future__ import annotations
import sys, pathlib, os

_verstoesse: list = []
_netz: list = []
_an = False

# Verbindungen hierher sind das eigene Sprachmodell und die eigene Oberflaeche.
EIGEN = ("127.0.0.1", "::1", "localhost")


def _erlaubt(pfad: str, ablage: pathlib.Path, paket: pathlib.Path) -> bool:
    try:
        p = pathlib.Path(pfad).resolve()
    except (OSError, ValueError):
        return True                      # nicht beurteilbar — nicht melden
    for erlaubt in (ablage, pathlib.Path(os.environ.get("TEMP", "/tmp"))):
        try:
            if erlaubt.resolve() in p.parents or p == erlaubt.resolve():
                return True
        except OSError:
            pass
    return False


def anmelden(ablage: pathlib.Path, paket: pathlib.Path, laut=False):
    """Haengt den Waechter ein. Einmal angemeldet, laesst er sich nicht wieder abmelden —
    das ist Absicht von Python und hier gerade recht."""
    global _an
    if _an:
        return
    _an = True

    def beobachter(ereignis, daten):
        # Netzverbindungen: im Kurs darf keine nach draussen gehen. Das Modell laeuft auf
        # 127.0.0.1, die Oberflaeche ebenso — alles andere waere ein Zugriff ins Netz, und
        # genau den soll es nicht geben, damit der Kurs ohne Verbindung laeuft.
        if ereignis == "socket.connect":
            # Die Felder sind (socket, adresse) — die Adresse steht an Stelle 1, nicht 2.
            ziel = daten[1] if len(daten) > 1 else None
            adresse = ziel[0] if isinstance(ziel, tuple) and ziel else str(ziel)
            if adresse and not any(str(adresse).startswith(e) for e in EIGEN):
                eintrag = f"{adresse}"
                if eintrag not in _netz:
                    _netz.append(eintrag)
                    if laut:
                        print(f"  WAECHTER: Netzverbindung nach aussen: {eintrag}",
                              file=sys.stderr)
            return
        if ereignis != "open":
            return
        pfad, modus = daten[0], daten[1]
        if not modus or not any(z in str(modus) for z in ("w", "a", "x", "+")):
            return
        if isinstance(pfad, int):
            return
        if not _erlaubt(str(pfad), ablage, paket):
            eintrag = f"{pfad} (Modus {modus})"
            if eintrag not in _verstoesse:
                _verstoesse.append(eintrag)
                if laut:
                    print(f"  WAECHTER: Schreibversuch ausserhalb der Ablage: {eintrag}",
                          file=sys.stderr)

    sys.addaudithook(beobachter)


def bericht() -> str:
    if not _an:
        return "Der Waechter war nicht angemeldet."
    z = []
    if _verstoesse:
        z.append("WAECHTER: {} Schreibversuch(e) ausserhalb der Ablage:\n  ".format(
            len(_verstoesse)) + "\n  ".join(_verstoesse))
    if _netz:
        z.append("WAECHTER: {} Verbindung(en) nach aussen:\n  ".format(len(_netz))
                 + "\n  ".join(_netz))
    if not z:
        return ("Waechter: kein Schreibversuch ausserhalb der Ablage, keine Verbindung "
                "nach aussen. (Unterprozesse sind davon nicht erfasst — siehe "
                "nachweis_autark.)")
    return "\n".join(z)


def verstoesse() -> list:
    return list(_verstoesse) + [f"Netz: {n}" for n in _netz]


def netzzugriffe() -> list:
    return list(_netz)
