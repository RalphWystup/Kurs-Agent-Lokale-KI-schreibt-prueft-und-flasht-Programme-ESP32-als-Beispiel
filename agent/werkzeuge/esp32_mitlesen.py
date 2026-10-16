#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schreibt die Unterhaltung mit dem Brett im Wortlaut mit — beide Richtungen, mit Zeitstempel.

Warum es dieses Werkzeug gibt
-----------------------------
Am 09.10.2026 sagte der Auftraggeber: „ich sehe weder das Runterladen noch das Atmen … ich will
sehen, dass es runterlaedt, und will auch die Kommunikation mit dem Board sehen." Bis dahin
meldeten die ESP32-Werkzeuge nur ihr Ergebnis. Was ueber die Leitung ging, sah niemand; ein
Fehlschlag war eine Zeile Text ohne Vorgeschichte.

Dieses Werkzeug zeigt die Vorgeschichte. Es spricht die serielle Leitung unmittelbar an
(pyserial, 115200 Baud) und schreibt jedes Byte mit:

    -> 13:42:07.412  <was der Rechner sendet>
    <- 13:42:07.455  <was das Brett antwortet>

Vier Betriebsarten:

  * ``horchen``   nur mitlesen, n Sekunden lang: was das laufende Programm ausgibt
  * ``zeile``     eine Zeile an die REPL schicken und die Antwort mitschreiben
  * ``datei``     eine Datei aus der Werkstatt senden und den ganzen Austausch mitschreiben
  * ``neustart``  das Brett zuruecksetzen und die Startmeldungen mitschreiben

Der Weg ist die Raw-REPL, die jede MicroPython-Firmware mitbringt: Strg-A schaltet um, Strg-D
fuehrt aus, Strg-B schaltet zurueck. Auf dem Rechner wird dabei nichts gestartet; es gehen Bytes
ueber eine Leitung. Dasselbe Verfahren laeuft seit Fassung 3.6 in der Bruecke.

Dieses Werkzeug **urteilt nicht**. Es zeigt. Das Urteil faellt esp32_pruefsumme oder
esp32_nachlesen — und zwar aus Messwerten, nicht aus einem Mitschnitt.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, WERKSTATT, Leitung
import re
import time


class Mitschnitt:
    """Sammelt, was in beide Richtungen geht, mit Zeitstempel in Millisekunden."""

    def __init__(self, hoechstens=400):
        self.zeilen = []
        self.hoechstens = hoechstens
        self.verworfen = 0

    def _stempel(self):
        t = time.time()
        return time.strftime("%H:%M:%S", time.localtime(t)) + f".{int(t % 1 * 1000):03d}"

    def dazu(self, richtung: str, rohdaten: bytes):
        if not rohdaten:
            return
        text = rohdaten.decode("utf-8", "replace")
        for stueck in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if stueck == "":
                continue
            #  Steuerzeichen sichtbar machen: sonst sieht man eine leere Zeile, wo Strg-A steht.
            sichtbar = (stueck.replace("\x01", "<Strg-A>").replace("\x02", "<Strg-B>")
                        .replace("\x03", "<Strg-C>").replace("\x04", "<Strg-D>"))
            if len(self.zeilen) >= self.hoechstens:
                self.verworfen += 1
                continue
            self.zeilen.append(f"  {richtung} {self._stempel()}  {sichtbar[:200]}")

    def text(self) -> str:
        if not self.zeilen:
            return "  (nichts gegangen — das Brett schwieg und der Rechner sandte nichts)"
        rest = (f"\n  … und {self.verworfen} weitere Zeilen, hier nicht gezeigt"
                if self.verworfen else "")
        return "\n".join(self.zeilen) + rest


def _oeffnen(port: str):
    try:
        import serial
    except ImportError:
        raise Abbruch("pyserial fehlt. Rufe WERKZEUG: paket_installieren {\"paket\": \"pyserial\"} auf.")
    try:
        with Leitung(port=port):
            return serial.Serial(port, 115200, timeout=0.2)
    except Exception as e:
        raise Abbruch(f"{port} laesst sich nicht oeffnen: {e}\n"
                      f"Haelt ein anderes Programm ihn fest (Thonny, serieller Monitor, ein "
                      f"laufendes esp32_nachlesen)? Welche Anschluesse es gibt, sagt "
                      f"WERKZEUG: ports_zeigen {{}}")


def _lesen(verbindung, m: Mitschnitt, sekunden: float, bis: bytes = None) -> bytes:
    """Liest und schreibt mit, bis die Zeit um ist oder das Endezeichen kam."""
    t0 = time.time()
    alles = b""
    while time.time() - t0 < sekunden:
        teil = verbindung.read(512)
        if teil:
            alles += teil
            m.dazu("<-", teil)
            if bis and bis in alles:
                break
        else:
            time.sleep(0.01)
    return alles


def _senden(verbindung, m: Mitschnitt, rohdaten: bytes):
    m.dazu("->", rohdaten)
    verbindung.write(rohdaten)


def tun(e):
    port = str(e["port"]).strip()
    if not re.fullmatch(r"(COM\d+|/dev/[A-Za-z0-9._/-]+)", port):
        raise Abbruch(f"'{port}' sieht nicht wie ein Anschluss aus. "
                      f"Welche es gibt, sagt WERKZEUG: ports_zeigen {{}}")
    art = str(e.get("art", "horchen")).strip().lower()
    if art not in ("horchen", "zeile", "datei", "neustart"):
        raise Abbruch("art muss horchen, zeile, datei oder neustart sein.")
    sekunden = float(e.get("sekunden", 6))
    if not 1 <= sekunden <= 60:
        raise Abbruch("sekunden muss zwischen 1 und 60 liegen.")

    m = Mitschnitt()
    verbindung = _oeffnen(port)
    kopf = f"Mitschnitt der Leitung {port}, 115200 Baud, Betriebsart '{art}':"
    try:
        if art == "horchen":
            _lesen(verbindung, m, sekunden)
            schluss = (f"{sekunden:.0f} s lang mitgelesen. Was oben steht, hat das Programm auf "
                       f"dem Brett selbst ausgegeben.")

        elif art == "neustart":
            _senden(verbindung, m, b"\r\x03\x03")          # zweimal Strg-C: anhalten
            time.sleep(0.2)
            _senden(verbindung, m, b"\x04")                # Strg-D in der gewohnten REPL: weicher Neustart
            _lesen(verbindung, m, sekunden)
            schluss = ("Weicher Neustart ausgeloest. Darueber steht, was das Brett beim Hochlaufen "
                       "meldet; danach laeuft main.py wieder.")

        elif art == "zeile":
            befehl = str(e.get("befehl", "")).strip()
            if not befehl:
                raise Abbruch("Bei art 'zeile' muss 'befehl' gesetzt sein, "
                              "zum Beispiel {\"art\": \"zeile\", \"befehl\": \"import os; print(os.listdir())\"}")
            _senden(verbindung, m, b"\r\x03\x03")
            time.sleep(0.2)
            verbindung.reset_input_buffer()
            _senden(verbindung, m, b"\x01")                # Strg-A: Raw-REPL
            _lesen(verbindung, m, 3, b">")
            _senden(verbindung, m, befehl.encode("utf-8") + b"\x04")
            _lesen(verbindung, m, sekunden, b"\x04>")
            _senden(verbindung, m, b"\x02")                # Strg-B: zurueck
            schluss = "Eine Zeile an die Raw-REPL geschickt; die Antwort steht darueber."

        else:   # datei
            name = str(e.get("datei", "")).strip()
            if not name:
                raise Abbruch("Bei art 'datei' muss 'datei' gesetzt sein, der Name in der Werkstatt.")
            if "/" in name or "\\" in name:
                raise Abbruch("datei muss ein Name aus der Werkstatt sein, ohne Pfad.")
            quelle = WERKSTATT / name
            if not quelle.is_file():
                da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*"))) or "(nichts)"
                raise Abbruch(f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}. "
                              f"Erst WERKZEUG: schreib_datei aufrufen.")
            ziel = str(e.get("ziel", "main.py")).strip() or "main.py"
            if "/" in ziel or "\\" in ziel or "'" in ziel:
                raise Abbruch("Der Name auf dem Geraet darf keinen Pfad enthalten.")
            inhalt = quelle.read_bytes()
            _senden(verbindung, m, b"\r\x03\x03")
            time.sleep(0.2)
            verbindung.reset_input_buffer()
            _senden(verbindung, m, b"\x01")
            _lesen(verbindung, m, 3, b">")
            #  Blockweise schreiben: der Mitschnitt zeigt jeden Block, damit das Herunterladen
            #  wirklich zu sehen ist und nicht als ein einziger Klotz erscheint.
            schreiber = f"f = open({ziel!r}, 'wb')\n"
            _senden(verbindung, m, schreiber.encode("utf-8") + b"\x04")
            _lesen(verbindung, m, 5, b"\x04>")
            bloecke = 0
            for i in range(0, len(inhalt), 128):
                block = inhalt[i:i + 128]
                _senden(verbindung, m, b"\x01")
                _lesen(verbindung, m, 2, b">")
                _senden(verbindung, m, f"f.write({block!r})\n".encode("utf-8") + b"\x04")
                _lesen(verbindung, m, 5, b"\x04>")
                bloecke += 1
            _senden(verbindung, m, b"\x01")
            _lesen(verbindung, m, 2, b">")
            _senden(verbindung, m, b"f.close()\nprint('FERTIG', " + repr(ziel).encode() + b")\n\x04")
            _lesen(verbindung, m, 5, b"\x04>")
            _senden(verbindung, m, b"\x02")
            schluss = (f"{name} ({len(inhalt)} Byte) in {bloecke} Bloecken nach {port}:{ziel} "
                       f"geschrieben — Block fuer Block oben mitzulesen.\n"
                       f"Dass der Inhalt angekommen ist, beweist dieser Mitschnitt NICHT. "
                       f"Das beweist WERKZEUG: esp32_pruefsumme "
                       f"{{\"port\": \"{port}\", \"ziel\": \"{ziel}\", \"datei\": \"{name}\"}}")
    finally:
        try:
            verbindung.close()
        except Exception:
            pass

    return f"{kopf}\n{m.text()}\n\n{schluss}"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gegenprobe":
        #  Geprueft wird hier, was ohne Geraet pruefbar ist: dass der Mitschnitt beide
        #  Richtungen sauber trennt, Steuerzeichen sichtbar macht und nicht ueberlaeuft.
        print("Gegenprobe des Mitschnitts (ohne Geraet):")
        m = Mitschnitt(hoechstens=3)
        m.dazu("->", b"\x01import os\r\n")
        m.dazu("<-", b"raw REPL; CTRL-B to exit\r\n>")
        m.dazu("->", b"\x04")
        m.dazu("<-", b"OK\x04\x04>")
        print(m.text())
        nicht_leer = len(m.zeilen) == 3 and m.verworfen >= 1
        hat_beide = any(z.strip().startswith("->") for z in m.zeilen) and \
                    any(z.strip().startswith("<-") for z in m.zeilen)
        sichtbar = any("<Strg-A>" in z for z in m.zeilen)
        print(f"  Grenze haelt:        {'richtig' if nicht_leer else 'FALSCH'}")
        print(f"  beide Richtungen:    {'richtig' if hat_beide else 'FALSCH'}")
        print(f"  Steuerzeichen lesbar:{'richtig' if sichtbar else 'FALSCH'}")
        raise SystemExit(0)
    raise SystemExit(werkzeug(
        "esp32_mitlesen",
        "Zeigt die Unterhaltung mit dem ESP32 im Wortlaut: jede gesendete und empfangene Zeile "
        "mit Zeitstempel. art horchen (nur mitlesen), zeile (einen Befehl schicken), datei "
        "(eine Datei Block fuer Block senden, sichtbar), neustart. Dieses Werkzeug zeigt nur; "
        "ob die Uebertragung stimmt, sagt esp32_pruefsumme.",
        {"port":     {"type": "string", "description": "der Anschluss, zum Beispiel COM3"},
         "art":      {"type": "string", "description": "horchen, zeile, datei oder neustart"},
         "sekunden": {"type": "number", "description": "wie lange mitgelesen wird, Vorgabe 6"},
         "befehl":   {"type": "string", "description": "bei art zeile: die MicroPython-Zeile"},
         "datei":    {"type": "string", "description": "bei art datei: Name in der Werkstatt"},
         "ziel":     {"type": "string", "description": "bei art datei: Name auf dem Geraet, Vorgabe main.py"}},
        ["port"], {"port": "COM3", "art": "horchen", "sekunden": 5}, tun))
