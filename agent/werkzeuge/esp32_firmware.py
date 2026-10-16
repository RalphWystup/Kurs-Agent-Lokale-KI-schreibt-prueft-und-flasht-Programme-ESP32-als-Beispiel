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

from _muster import werkzeug, Abbruch, lauf, PAKET, python_exe, eine, Leitung
import re

FIRMWARE_URL = "https://micropython.org/resources/firmware/ESP32_GENERIC-20260824-v1.29.0.bin"


def _esptool(port, *args, zeit=300):
    with Leitung(port=port):
        return lauf([str(python_exe()), "-m", "esptool", "--port", port, *args], zeit)


def _was_ist_drauf(port: str) -> str:
    """Sieht nach, was auf dem Brett schon laeuft — bevor es ueberschrieben wird.

    Ein ESP32 im Kurs kommt in zwei Zustaenden: frisch aus der Packung (ab Werk meist ein
    Arduino-Testprogramm oder gar nichts) oder von einem fruehren Versuch beschrieben. Fuer
    das Flashen ist das gleichgueltig — der Speicher wird ohnehin geloescht. Aber wer
    ueberschreibt, sollte vorher wissen, was er ueberschreibt, und im Kurs spart es Zeit,
    wenn MicroPython schon laeuft.
    """
    #  Gemessen 15.10.2026: Das Oeffnen der Leitung startet das Brett neu; mpremote direkt
    #  danach fand „kein MicroPython", obwohl v1.29.0 lief. Deshalb zuerst auf das Banner
    #  warten (Reset + bis 12 s), dann erst die Dateiliste holen.
    banner = _meldet_sich(port, 12)
    if not banner:
        return ("NICHT GEMESSEN, dass MicroPython laeuft: Nach einem Neustart meldet sich innerhalb "
                "von 12 s kein MicroPython-Banner und keine Eingabeaufforderung. Entweder ist das "
                "Brett fabrikneu, traegt ein anderes Programm — oder es haengt; EN-Taste druecken "
                "und erneut pruefen. esp32_firmware loescht den Speicher und schreibt MicroPython neu.")
    with Leitung(port=port):
        r = lauf([str(python_exe()), "-m", "mpremote", "connect", port, "fs", "ls"], 40)
    if r.returncode == 0:
        dateien = [z.strip() for z in (r.stdout or "").splitlines()[1:] if z.strip()]
        return (f"Darauf laeuft MicroPython — gemessen: {banner}. Dateien auf dem Geraet: "
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
        raise Abbruch(f"Der Speicher liess sich nicht loeschen: {(r.stderr or r.stdout)[-400:]}\n"
            f"Was jetzt hilft: Haelt ein anderes Programm den Anschluss (Thonny, "
            f"serieller Monitor)? Dann schliessen und wiederholen. Sonst das Brett "
            f"ab- und wieder anstecken und esp32_firmware erneut aufrufen.")
    r = _esptool(port, "--baud", "460800", "write_flash", "-z", "0x1000", str(bin_), zeit=900)
    if r.returncode != 0:
        raise Abbruch(f"Die Firmware liess sich nicht schreiben: {(r.stderr or r.stdout)[-400:]}\n"
            f"Was jetzt hilft: Brett ab- und wieder anstecken, dann esp32_firmware "
            f"erneut aufrufen. Bleibt es dabei, haelt ein anderes Programm den Anschluss.")

    # Schritt 4 — nachsehen, ob MicroPython sich wirklich meldet (15.10.2026: Nach dem
    # Schreiben stand hier „Der ESP32 fuehrt jetzt MicroPython aus" — behauptet, nicht
    # gemessen; das Laden danach fand keine REPL. Jetzt: Reset ausloesen, auf das Banner warten.)
    meldung = _meldet_sich(port)
    kopf = (f"An {port}: {chip}\n{mac}\nFirmware {woher}, der gesamte Speicher wurde geloescht "
            f"und neu beschrieben — was vorher darauf war, ist damit weg.\n")
    if meldung:
        return kopf + (f"FIRMWARE BESTANDEN — das Brett meldet sich nach dem Neustart: {meldung}\n"
                       f"Programme kommen mit esp32_laden darauf.")
    return kopf + ("FIRMWARE NICHT BESTANDEN — nach dem Schreiben meldet sich innerhalb von 20 s "
                   "keine MicroPython-Eingabeaufforderung.\n"
                   "Was jetzt hilft: die EN-Taste (Reset) am Brett druecken oder es ab- und wieder "
                   "anstecken; dann mit nur_pruefen: true nachsehen, ob es sich meldet.")


def _meldet_sich(port: str, sekunden: float = 20.0) -> str:
    """Strg+C, Strg+D, dann auf das MicroPython-Banner oder >>> warten — derselbe Weg wie
    esp32_mitlesen (Betriebsart neustart), der am 15.10.2026 das Banner gezeigt hat, als ein
    Reset ueber DTR/RTS es nicht zeigte (ein laufendes main.py druckt kein Banner, erst der
    weiche Neustart). Gibt die Bannerzeile zurueck, sonst leer. Misst, behauptet nicht."""
    import time as _t
    try:
        import serial
    except ImportError:
        return ""
    try:
        with Leitung(port=port):
            v = serial.Serial(port, 115200, timeout=0.3)
            try:
                _t.sleep(1.5)                           # das Oeffnen startet das Brett neu
                gesehen = b""
                ende = _t.time() + sekunden
                for versuch in range(3):
                    v.write(b"\r\x03\x03")
                    _t.sleep(0.3)
                    v.write(b"\x04")
                    bis = min(ende, _t.time() + sekunden / 3)
                    while _t.time() < bis:
                        gesehen += v.read(512)
                        if b"MicroPython v" in gesehen or b">>>" in gesehen:
                            break
                    if b"MicroPython v" in gesehen or b">>>" in gesehen:
                        break
                text = gesehen.decode("utf-8", "replace")
                for z in text.splitlines():
                    if "MicroPython v" in z:
                        return z.strip()[:120]
                if ">>>" in text:
                    return "Eingabeaufforderung >>> vorhanden"
                return ""
            finally:
                v.close()
    except Exception:                                   # noqa: BLE001 — kein Nachweis ist kein Nachweis
        return ""


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
