#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sorgt dafuer, dass dieses Programm in einer sauberen Umgebung laeuft — notfalls durch
einen Neustart seiner selbst.

Auf einem benutzten Rechner koennen ``PYTHONPATH`` oder ``PYTHONHOME`` gesetzt sein: von
einer anderen Python-Installation, einem Werkzeugkasten, einem alten Versuch. Beides wirkt,
**bevor** die erste eigene Zeile laeuft:

  ``PYTHONPATH``  laedt fremde Module in unseren Prozess. Liegt dort ein ``sitecustomize.py``
                  oder ein ``machine.py``, bekommen wir deren Fassung statt unserer.
  ``PYTHONHOME``  verbiegt den Ort der Standardbibliothek; das Programm startet dann gar nicht.

Zur Laufzeit laesst sich das nicht mehr rueckgaengig machen — geladen ist geladen. Also
startet sich das Programm einmal neu, mit ``-E`` (Umgebungsvariablen ignorieren) und ``-s``
(kein Benutzer-Paketverzeichnis). Das Startskript raeumt diese Variablen ohnehin weg; dieser
Weg greift, wenn jemand ein Werkzeug von Hand aufruft.
"""
from __future__ import annotations
import os, sys

STOERER = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "PYTHONEXECUTABLE")
MARKE = "KURS_AGENT_SAUBER"


def sicherstellen():
    """Startet sich einmal neu, falls die Umgebung verunreinigt ist. Kehrt sonst zurueck."""
    if os.environ.get(MARKE) == "1":
        return                                  # schon der saubere Durchgang
    gesetzt = [v for v in STOERER if os.environ.get(v)]
    if not gesetzt:
        return
    u = {k: v for k, v in os.environ.items() if k not in STOERER}
    u[MARKE] = "1"
    u["PYTHONNOUSERSITE"] = "1"
    import subprocess
    r = subprocess.run([sys.executable, "-E", "-s", *sys.argv], env=u)
    # Die Ausgabe des Kindes ist schon geschrieben; wir reichen nur noch seinen Stand weiter.
    raise SystemExit(r.returncode)
