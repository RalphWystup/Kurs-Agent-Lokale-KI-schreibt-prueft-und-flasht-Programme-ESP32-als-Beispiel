#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spielt MicroPython auf einen ESP32 — nachdem geprueft wurde, dass dort einer haengt.

Warum MicroPython und nicht Arduino: fuer einen Arduino-Sketch braucht es einen
C-Uebersetzer samt Werkzeugkette, rund ein Gigabyte. MicroPython ist eine Firmware-Datei
von etwa 1,6 MB; danach ist der ESP32 ein Geraet, auf das man Python-Dateien kopiert.
Das passt zum Kurs: das Modell schreibt Python, und der ESP32 fuehrt genau das aus.

**Der wichtigste Teil dieses Werkzeugs ist nicht das Schreiben, sondern das Nicht-Schreiben.**
Ein Flashvorgang auf den falschen Anschluss trifft irgendein anderes Geraet. Deshalb wird
zuerst gefragt, wer dort antwortet. Meldet sich kein ESP32, wird nichts geschrieben.
"""
import sys, pathlib
# Der eigene Ordner und der des Agenten muessen in den Suchpfad, bevor etwas daraus geholt
# wird. Unter einem gewoehnlichen Python stehen sie von selbst darin — beim eingebetteten
# Python nicht: dort legt python3xx._pth den Suchpfad abschliessend fest, und sys.path hat
# genau zwei Eintraege. Ohne diese Zeilen scheitert jedes Werkzeug auf dem Kursrechner mit
# "No module named _muster", waehrend es auf dem Entwicklungsrechner tadellos laeuft.
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, lauf, PAKET, python_exe, eine
import re

FIRMWARE_URL = "https://micropython.org/resources/firmware/ESP32_GENERIC-20260824-v1.29.0.bin"


def _esptool(port, *args, zeit=300):
    return lauf([str(python_exe()), "-m", "esptool", "--port", port, *args], zeit)


def _was_ist_drauf(port: str) -> str:
    """Sieht nach, was auf dem Brett schon laeuft — bevor es ueberschrieben wird.

    Ein ESP32 im Kurs kommt in zwei Zustaenden: frisch aus der Packung (ab Werk meist ein
    Arduino-Testprogramm oder gar nichts) oder von einem fruehren Versuch beschrieben. Fuer
    das Flashen ist das gleichgueltig — der Speicher wird ohnehin geloescht. Aber wer
    ueberschreibt, sollte vorher wissen, was er ueberschreibt, und im Kurs spart es Zeit,
    wenn MicroPython schon laeuft.
    """
    r = lauf([str(python_exe()), "-m", "mpremote", "connect", port, "fs", "ls"], 40)
    if r.returncode == 0:
        dateien = [z.strip() for z in (r.stdout or "").splitlines()[1:] if z.strip()]
        return (f"Darauf laeuft bereits MicroPython. Dateien auf dem Geraet: "
                + (", ".join(d.split()[-1] for d in dateien) if dateien else "(keine)")
                + "\nEin erneutes Flashen ist moeglich, aber nicht noetig — mit "
                  "esp32_uebertragen laesst sich sofort ein Programm aufspielen.")
    if "ModuleNotFoundError" in (r.stderr or ""):
        return "Ob MicroPython laeuft, liess sich nicht pruefen: mpremote fehlt noch."
    return ("Darauf laeuft kein MicroPython — entweder ist das Brett fabrikneu oder es "
            "traegt ein anderes Programm (etwa einen Arduino-Sketch). Beides macht nichts: "
            "esp32_firmware loescht den Speicher und schreibt MicroPython neu.")


def tun(e):
    port = str(e["port"]).strip()
    if not re.fullmatch(r"(COM\d+|/dev/[A-Za-z0-9._/-]+)", port):
        raise Abbruch(f"'{port}' sieht nicht wie ein Anschluss aus. Erwartet wird COM5 "
                      f"oder /dev/ttyUSB0. ports_zeigen nennt die vorhandenen.")
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")

    # Schritt 1 — wer ist da? Ohne Antwort wird nichts geschrieben.
    r = _esptool(port, "chip_id", zeit=120)
    if r.returncode != 0:
        raise Abbruch(
            f"An {port} meldet sich kein ESP32, es wurde nichts geschrieben.\n"
            f"Zu pruefen: richtiger Anschluss (ports_zeigen)? Steckbrett eingesteckt? "
            f"Belegt ein anderes Programm den Anschluss (Thonny, serieller Monitor)? "
            f"Bei manchen Brettern muss BOOT beim Einstecken gedrueckt werden.\n"
            f"Meldung von esptool: {(r.stderr or r.stdout)[-400:]}")
    chip = next((z.strip() for z in r.stdout.splitlines() if z.startswith("Chip is")), "ESP32 erkannt")
    mac  = next((z.strip() for z in r.stdout.splitlines() if "MAC:" in z), "")

    if e.get("nur_pruefen"):
        return f"An {port}: {chip}\n{mac}\n{_was_ist_drauf(port)}\n" \
               f"Es wurde nichts geschrieben (nur_pruefen war gesetzt)."

    # Schritt 2 — Firmware nehmen. Nur aus dem Paket; es wird nichts geladen.
    #
    # Hier stand bis zum 02.10.2026 ein Rueckfall ins Netz: fehlt die Datei, dann laden
    # und nach paket\firmware\ legen. Das war gleich zweimal falsch. Erstens holt der
    # Kurs nichts aus dem Netz (A2) -- auf dem Kursrechner gibt es keines, und wo es
    # eines gibt, soll es nicht benutzt werden. Zweitens wird paket\ nur gelesen, nie
    # beschrieben (C5); ein Schreibvorgang dort haette die Pruefsumme veraendert, mit
    # der belegt wird, dass das Mitgelieferte unberuehrt bleibt.
    #
    # Fehlt die Firmware, ist das Paket unvollstaendig. Das wird gesagt, nicht geheilt:
    # Gefuellt wird vor dem Kurs, mit hole_paket.py.
    bin_ = eine("firmware/*.bin") or eine("*.bin")
    if not bin_:
        raise Abbruch(
            f"Im Paket liegt keine MicroPython-Firmware (paket\\firmware\\*.bin).\n"
            f"Es wird nichts aus dem Netz geholt -- das Paket bringt alles mit oder nichts.\n"
            f"Naechster Schritt: START.bat auf dem Vorbereitungsrechner starten, es fuellt "
            f"das Paket nach; oder eine .bin von micropython.org nach "
            f"{PAKET / 'firmware'} legen.")
    woher = f"mitgeliefert ({bin_.name}, {bin_.stat().st_size} Byte)"

    # Schritt 3 — loeschen und schreiben.
    r = _esptool(port, "erase_flash", zeit=300)
    if r.returncode != 0:
        raise Abbruch(f"Der Speicher liess sich nicht loeschen: {(r.stderr or r.stdout)[-400:]}")
    r = _esptool(port, "--baud", "460800", "write_flash", "-z", "0x1000", str(bin_), zeit=900)
    if r.returncode != 0:
        raise Abbruch(f"Die Firmware liess sich nicht schreiben: {(r.stderr or r.stdout)[-400:]}")

    return (f"An {port}: {chip}\n{mac}\nFirmware {woher}, der gesamte Speicher wurde geloescht "
            f"und neu beschrieben — was vorher darauf war, ist damit weg.\n"
            f"Der ESP32 fuehrt jetzt MicroPython aus. Mit esp32_uebertragen kommt das Programm darauf.")


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "esp32_firmware",
        "Spielt MicroPython auf den ESP32 am angegebenen Anschluss. Prueft zuerst, ob dort "
        "ueberhaupt ein ESP32 antwortet, und schreibt nur dann. Einmal je Geraet noetig, bevor "
        "Python-Programme uebertragen werden koennen. Mit nur_pruefen: true sagt es, was auf "
        "dem Brett schon ist — fabrikneu, fremdes Programm oder bereits MicroPython — und "
        "schreibt nichts.",
        {"port": {"type": "string", "description": "der Anschluss, zum Beispiel COM5"},
         "nur_pruefen": {"type": "boolean",
                         "description": "true: nur nachsehen, wer antwortet, und nichts schreiben"}},
        ["port"], {"port": "COM5", "nur_pruefen": True}, tun))
