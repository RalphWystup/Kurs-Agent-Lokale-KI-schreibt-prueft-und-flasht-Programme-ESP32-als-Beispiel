#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ein Programm auf den ESP32 bringen — die ganze Kette in einem Werkzeug, mit Diagnose.

Anweisung des Auftraggebers vom 10.10.2026: „Ich brauche im Werkzeugkasten eine 100 % taugliche
Lade- und Debugroutine fuer den ESP32 inklusive Treibertest etc. Das macht nicht das System,
das macht das Werkzeug."

Warum ein Werkzeug statt fuenf
------------------------------
Bis dahin musste das Modell die Kette selbst zusammensetzen: ports_zeigen, paket_installieren,
esp32_firmware, esp32_uebertragen, esp32_pruefsumme, esp32_nachlesen. Sechs Aufrufe, und jeder
konnte an einer anderen Stelle scheitern. Gemessen am 09.10.2026 (drei Durchgaenge): Der Auftrag
„blink.py auf das Brett laden" scheiterte jedes Mal — einmal an einem fehlenden pyserial, einmal
an einem verschriebenen Werkzeugnamen, einmal an der Zeit, die die sechs Aufrufe brauchten.

Hier laeuft die Kette in einem Aufruf, und zwar als **Pruefkette**: Jeder Schritt wird gemessen,
jeder Fehlschlag sagt, woran es liegt und was jetzt hilft. Was das Werkzeug nicht selbst
beheben kann, benennt es.

Die Schritte
------------
  1  Treiber und Anschluss     welche seriellen Anschluesse gibt es, welcher Wandler
  2  Leitung                   laesst sich der Anschluss oeffnen
  3  MicroPython               antwortet das Brett auf der Raw-REPL, welche Fassung
  4  Platz                     ist genug Dateispeicher frei
  5  Schreiben                 die Datei blockweise, mit Mitschnitt
  6  Pruefsumme                SHA-256 AUF DEM BRETT gegen die Werkstattdatei
  7  Neustart                  weicher Neustart, Startmeldungen mitgelesen
  8  Meldungen des Programms   was es in den ersten Sekunden sagt — AUSKUNFT, kein
                            Urteil: ein Blinkprogramm sagt nichts und ist trotzdem
                            richtig geladen

Der Weg ist die Raw-REPL ueber pyserial — derselbe, den die Bruecke seit Fassung 3.6 benutzt
und der dort seit Wochen traegt. Kein mpremote: ein Abhaengigkeit weniger, und der Mitschnitt
zeigt jedes Byte.

Betriebsarten
-------------
  pruefen   nur Schritte 1 bis 4: geht es ueberhaupt? Aendert nichts auf dem Brett.
  laden     alle acht Schritte (Vorgabe)
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, WERKSTATT, in_der_ablage, python_exe
from pfade import umgebung
import os
import hashlib
import re
import time


# ---------------------------------------------------------------- Schritt fuer Schritt
class Bericht:
    """Jeder Schritt mit Urteil. Ein Fehlschlag beendet die Kette und sagt, was jetzt hilft."""

    def __init__(self):
        self.zeilen = []
        self.gescheitert = None

    notiz = staticmethod(lambda z: None)      # wird in tun() gesetzt: schreibt mit

    def schritt(self, nr, was, gut, gemessen, hilfe=""):
        zeile = f"  {nr}. {was:<28} {'ok   ' if gut else 'FEHL '} {gemessen}"
        self.zeilen.append(zeile)
        self.notiz(zeile)
        if not gut and hilfe:
            self.notiz(f"      -> {hilfe}")
        if not gut and self.gescheitert is None:
            self.gescheitert = (nr, was, gemessen, hilfe)
        return gut

    def auskunft(self, nr, was, gemessen):
        """Ein Schritt, der BERICHTET statt zu urteilen (10.10.2026). Er erscheint in der
        Liste wie die anderen, kann aber nichts zum Scheitern bringen: Was hier steht, ist
        eine Beobachtung, kein Mass."""
        zeile = f"  {nr}. {was:<28} —     {gemessen}"
        self.zeilen.append(zeile)
        self.notiz(zeile)
        return True

    def text(self, kopf):
        t = [kopf, ""] + self.zeilen + [""]
        if self.gescheitert:
            nr, was, gemessen, hilfe = self.gescheitert
            t.append(f"LADEN NICHT BESTANDEN — Schritt {nr} ({was})")
            t.append(f"  Gemessen: {gemessen}")
            if hilfe:
                t.append(f"  Was jetzt hilft: {hilfe}")
        else:
            t.append("LADEN BESTANDEN — die Datei liegt Byte fuer Byte auf dem Brett "
                     "(Pruefsumme VOM BRETT, Schritt 6) und der Neustart ist gelaufen "
                     "(Schritt 7). Was das Programm an den Anschluessen tut, misst "
                     "esp32_nachlesen.")
        return "\n".join(t)



def _stiller_lauf() -> bool:
    """Laeuft gerade eine Pruefreihe? Dann wird KEIN Fenster geoeffnet.

    Angelegt am 10.10.2026. Jeder Auftrag fuehrt vor, jede Vorfuehrung oeffnet ein Fenster
    — bei drei Durchgaengen ueber acht Auftraege sind das vierundzwanzig, die nacheinander
    auf dem Bildschirm aufgehen. Der Auftraggeber: „das wird mir zu bunt. Wenn du sie nicht
    zumachst, mach ich das halt." und „immer nur die aktuellen Fenster oeffnen".

    Ein Pruefmittel prueft und zeigt nichts. Die Fenster sind fuer den Menschen, der
    zusieht — im Prueflauf sitzt niemand davor. Gesetzt wird der Schalter von dem Programm,
    das die Reihe faehrt; fehlt er, geht alles auf wie bisher.
    """
    return in_der_ablage("pruefbetrieb.txt").exists()


def _vorgaenger_schliessen(_marke: str = "") -> None:
    """ALLE frueheren Vorfuehrfenster beenden, bevor ein neues aufgeht.

    Angelegt am 10.10.2026, verschaerft am selben Tag. Jeder Auftrag fuehrt vor, jede
    Vorfuehrung oeffnet ein Fenster — nach einem Durchgang ueber acht Auftraege beendete
    `kursagent stop` **17** Prozesse aus dem Paket, und ebenso viele Fenster standen auf
    dem Bildschirm. Der Auftraggeber: „bevor du einen neuen Kursagenten auf meinem
    Bildschirm aufmachst, schliesse die alten!" und, als zuerst nur das gleichartige
    Fenster geschlossen wurde: „immer nur die aktuellen Fenster auf, alles Alte
    schliessen." (Kriterium O4).

    Geschlossen wird ausschliesslich, was dieses Paket selbst geoeffnet hat: Die Kennungen
    stehen in zwei Dateien in der Ablage, und beendet wird nur, was dort steht. Fremde
    Fenster bleiben unberuehrt — ein Aufraeumen, das fremde Fenster schliesst, ist kein
    Aufraeumen, sondern ein Schaden.
    """
    import os as _os
    import subprocess as _sp
    for marke in ("simulation_fenster.pid", "esp32_fenster.pid"):
        d = in_der_ablage(marke)
        try:
            alt = int(d.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        try:
            _sp.run(["taskkill", "/PID", str(alt), "/T", "/F"] if _os.name == "nt"
                    else ["kill", str(alt)],
                    capture_output=True, timeout=20,
                    creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0) if _os.name == "nt" else 0)
        except Exception:
            pass                               # ein Fenster, das nicht mehr da ist, ist gut
        finally:
            try:
                d.unlink(missing_ok=True)
            except OSError:
                pass


def anschluesse() -> list:
    """(Port, Beschreibung, Wandler) je serieller Anschluss — Wandler leer, wenn unbekannt.

    Wiederhergestellt am 10.10.2026: Beim Einfuegen der Fensterfunktionen ist diese Funktion
    verlorengegangen. Das Werkzeug stuerzte danach bei JEDEM Aufruf mit
    „NameError: name 'anschluesse' is not defined" ab — und das Pruefmittel fand es nicht,
    weil es nur Namen mit Unterstrich pruefte. Die Wandlertabelle ist dieselbe wie in
    ports_zeigen; zwei Tabellen waeren zwei Wahrheiten.
    """
    try:
        import serial.tools.list_ports as lp
    except ImportError:
        raise Abbruch("pyserial fehlt. Rufe WERKZEUG: umgebung_anlegen {} auf — es richtet "
                      "pyserial, mpremote und esptool zusammen ein.")
    WANDLER = {"10C4:EA60": "Silicon Labs CP2102", "1A86:7523": "QinHeng CH340",
               "1A86:55D4": "QinHeng CH9102", "0403:6001": "FTDI FT232R",
               "0403:6015": "FTDI FT231X", "303A:1001": "Espressif USB (S2/S3)",
               "303A:0002": "Espressif USB (S2/S3)"}
    gefunden = []
    for q in lp.comports():
        schluessel = (f"{q.vid:04X}:{q.pid:04X}" if q.vid and q.pid else "")
        gefunden.append((q.device, q.description or "", WANDLER.get(schluessel, "")))
    return gefunden


def _lies(v, bis, zeit, mit=None):
    t0 = time.time()
    alles = b""
    while time.time() - t0 < zeit:
        teil = v.read(512)
        if teil:
            alles += teil
            if mit is not None:
                mit.append(("<-", teil))
            if bis and bis in alles:
                break
        else:
            time.sleep(0.01)
    return alles


def _sende(v, daten, mit=None):
    if mit is not None:
        mit.append(("->", daten))
    v.write(daten)


def _repl_an(v, mit=None) -> bool:
    """In die Raw-REPL schalten. Gibt True, wenn das Brett sich meldet.

    Gemessen 15.10.2026: Das Oeffnen der Leitung (DTR/RTS) startet das Brett neu; direkt nach
    frisch aufgespielter Firmware braucht es dann Sekunden, bis die REPL da ist — ein einziger
    Versuch mit 4 s Wartezeit sah „keine Raw-REPL", obwohl MicroPython v1.29.0 lief (von Hand
    und mit mpremote nachgewiesen). Darum: erst das Hochlaufen abwarten, dann bis zu vier
    Versuche mit Pausen. Was nicht antwortet, antwortet dann wirklich nicht."""
    _lies(v, b">>>", 2.5, mit)                 # Banner und Eingabeaufforderung des Starts abwarten
    for versuch in range(4):
        _sende(v, b"\r\x03\x03", mit)
        time.sleep(0.4)
        v.reset_input_buffer()
        _sende(v, b"\x01", mit)
        if b"raw REPL" in _lies(v, b">", 3, mit):
            return True
        time.sleep(1.5)
    return False


def _ausfuehren(v, code: str, zeit=20, mit=None) -> tuple:
    """Ein Stueck MicroPython auf dem Brett ausfuehren. (Ausgabe, Fehlertext)."""
    _sende(v, b"\x01", mit)
    _lies(v, b">", 3, mit)
    _sende(v, code.encode("utf-8") + b"\x04", mit)
    roh = _lies(v, b"\x04>", zeit, mit)
    if b"OK" not in roh:
        return "", "Das Brett hat den Auftrag nicht angenommen: " + repr(roh[-150:])
    teile = roh.split(b"OK", 1)[1].split(b"\x04")
    aus = teile[0].decode("utf-8", "replace").strip()
    fehler = teile[1].decode("utf-8", "replace").strip() if len(teile) > 1 else ""
    return aus, fehler


SUMME_AUF_DEM_BRETT = """
import uhashlib, ubinascii
h = uhashlib.sha256(); f = open({ziel!r}, 'rb'); n = 0
while True:
    b = f.read(256)
    if not b: break
    n += len(b); h.update(b)
f.close(); print('SUMME', ubinascii.hexlify(h.digest()).decode(), n)
"""

PLATZ = """
import os, sys
s = os.statvfs('/')
print('FREI', s[0] * s[3], 'FASSUNG', sys.version.replace(' ', '_'))
"""


def tun(e):
    art = str(e.get("art", "laden")).strip().lower()
    if art not in ("laden", "pruefen"):
        raise Abbruch('art muss "laden" oder "pruefen" sein.')
    b = Bericht()
    mit = []

    #  Das Fenster (Anweisung vom 10.10.2026): Es zeigt jeden Schritt, waehrend er geschieht,
    #  und liest danach die serielle Leitung weiter mit — bis der Mensch es schliesst.
    #  Zwei Programme koennen nicht dieselbe Leitung halten; deshalb schreibt dieses Werkzeug
    #  alles in eine Mitschnittdatei, das Fenster zeigt sie an, und erst wenn hier die
    #  Schlusszeile steht, uebernimmt das Fenster die Leitung.
    mitschnitt = in_der_ablage("esp32_lauf.txt")
    try:
        mitschnitt.write_text("", encoding="utf-8")
    except OSError:
        pass

    def notiz(zeile: str):
        try:
            with open(mitschnitt, "a", encoding="utf-8") as f:
                f.write(zeile + "\n")
        except OSError:
            pass

    b.notiz = notiz

    # --- 1. Treiber und Anschluss --------------------------------------------------
    liste = anschluesse()
    mit_wandler = [x for x in liste if x[2]]
    port = str(e.get("port", "")).strip()
    if not port:
        if len(mit_wandler) == 1:
            port = mit_wandler[0][0]
        elif not liste:
            b.schritt(1, "Treiber und Anschluss", False, "kein serieller Anschluss gefunden",
                      "Haengt das Brett am USB? Ist der Treiber eingerichtet? Der liegt im "
                      "Paket unter treiber/ (CH341SER.ZIP fuer den haeufigsten Wandler).")
            return b.text("ESP32 laden")
        else:
            b.schritt(1, "Treiber und Anschluss", False,
                      f"{len(liste)} Anschluesse, keiner eindeutig: "
                      + ", ".join(f"{p} {w or '(unbekannter Wandler)'}" for p, _, w in liste),
                      "Nenne den Anschluss ausdruecklich, zum Beispiel "
                      '{"port": "COM3", "datei": "blink.py"}')
            return b.text("ESP32 laden")
    hier = next((x for x in liste if x[0].upper() == port.upper()), None)
    #  Ab hier kann die Marke gesetzt werden; vorher gibt es keinen Anschluss zu belegen.
    b.schritt(1, "Treiber und Anschluss", bool(hier),
              f"{port}: {hier[1][:40]}, Wandler {hier[2] or 'unbekannt'}" if hier
              else f"{port} ist nicht da; es gibt: {', '.join(p for p, _, _ in liste) or 'keinen'}",
              "" if hier else "Brett ab- und wieder anstecken, dann WERKZEUG: ports_zeigen {}")
    if not hier:
        return b.text("ESP32 laden")

    # --- 2. Leitung ----------------------------------------------------------------
    #  Erst anmelden, dann oeffnen: Ein offenes Mitlese-Fenster haelt die Leitung. Es sieht
    #  diese Marke und tritt zurueck (10.10.2026 gemessen: ohne das kam der zweite
    #  Ladevorgang nicht mehr an COM3 — PermissionError, Zugriff verweigert).
    marke = in_der_ablage("esp32_leitung.txt")
    try:
        marke.write_text("belegt", encoding="utf-8")
    except OSError:
        pass
    import time as _t
    _t.sleep(1.2)                                  # dem Fenster Zeit lassen, zurueckzutreten

    try:
        import serial
        v = None
        for versuch in range(6):                   # bis zu drei Sekunden auf die Freigabe warten
            try:
                v = serial.Serial(port, 115200, timeout=0.2)
                break
            except Exception:
                _t.sleep(0.5)
        if v is None:
            v = serial.Serial(port, 115200, timeout=0.2)   # noch einmal, fuer die Meldung
    except Exception as ex:
        b.schritt(2, "Leitung oeffnen", False, f"{type(ex).__name__}: {ex}",
                  "Haelt ein anderes Programm den Anschluss (Thonny, serieller Monitor, ein "
                  "zweites esp32-Werkzeug)? Schliessen und wiederholen.")
        return b.text("ESP32 laden")
    b.schritt(2, "Leitung oeffnen", True, f"{port} offen, 115200 Baud")

    if e.get("fenster", True) and not _stiller_lauf():
        try:
            import subprocess as _sp
            kennung = {"creationflags": 0x00000008} if os.name == "nt" else {}
            _vorgaenger_schliessen("esp32_fenster.pid")
            _vorgang = _sp.Popen([str(python_exe()),
                       str(pathlib.Path(__file__).resolve().parent.parent / "esp32_fenster.py"),
                       str(mitschnitt), port],
                      stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, env=umgebung(), **kennung)
            in_der_ablage("esp32_fenster.pid").write_text(str(_vorgang.pid), encoding="utf-8")
        except Exception:
            pass                                  # ohne Fenster laedt es trotzdem

    try:
        # --- 3. MicroPython --------------------------------------------------------
        if not _repl_an(v, mit):
            b.schritt(3, "MicroPython antwortet", False, "keine Raw-REPL auf dieser Leitung",
                      "Laeuft MicroPython auf dem Brett? Aufspielen mit "
                      'WERKZEUG: esp32_firmware {"port": "' + port + '"}')
            return b.text("ESP32 laden")
        aus, fehler = _ausfuehren(v, PLATZ, 15, mit)
        m = re.search(r"FREI (\d+) FASSUNG (\S+)", aus)
        b.schritt(3, "MicroPython antwortet", bool(m),
                  m.group(2).replace("_", " ")[:52] if m else (fehler or aus)[:60],
                  "" if m else "Das Brett meldet sich, antwortet aber nicht wie MicroPython.")
        if not m:
            return b.text("ESP32 laden")
        frei = int(m.group(1))

        # --- 4. Platz --------------------------------------------------------------
        name = str(e.get("datei", "")).strip()
        if art == "pruefen":
            b.schritt(4, "Platz auf dem Brett", frei > 4096, f"{frei/1024:.0f} kB frei")
            v.close()
            t = b.text(f"ESP32 an {port} geprueft (nichts veraendert)")
            return t + ("\n\nDas Brett ist bereit. Laden mit "
                        'WERKZEUG: esp32_laden {"port": "' + port + '", "datei": "<datei>.py"}'
                        if not b.gescheitert else "")
        if not name:
            raise Abbruch('Zum Laden fehlt "datei" — der Name in der Werkstatt, zum Beispiel '
                          '{"port": "' + port + '", "datei": "blink.py"}')
        if "/" in name or "\\" in name:
            raise Abbruch("datei muss ein Name aus der Werkstatt sein, ohne Pfad.")
        quelle = WERKSTATT / name
        if not quelle.is_file():
            da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*"))) or "(nichts)"
            raise Abbruch(f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}.\n"
                          f"Lege sie erst an: WERKZEUG: schreib_datei "
                          f'{{"name": "{name}", "inhalt": "<der Quelltext>"}}')
        inhalt = quelle.read_bytes()
        b.schritt(4, "Platz auf dem Brett", frei > len(inhalt) + 2048,
                  f"{frei/1024:.0f} kB frei, gebraucht {len(inhalt)/1024:.1f} kB",
                  "Das Brett ist voll. Alte Dateien loeschen oder die Firmware neu aufspielen.")
        if b.gescheitert:
            return b.text("ESP32 laden")

        # --- 5. Schreiben ----------------------------------------------------------
        ziel = str(e.get("ziel", "main.py")).strip() or "main.py"
        if "/" in ziel or "\\" in ziel or "'" in ziel:
            raise Abbruch("Der Name auf dem Geraet darf keinen Pfad enthalten.")
        aus, fehler = _ausfuehren(v, f"f = open({ziel!r}, 'wb')", 10, mit)
        bloecke = 0
        for i in range(0, len(inhalt), 192):
            block = inhalt[i:i + 192]
            aus, fehler = _ausfuehren(v, f"f.write({block!r})", 10, mit)
            if fehler:
                break
            bloecke += 1
        _ausfuehren(v, "f.close()", 10, mit)
        b.schritt(5, "Datei schreiben", not fehler,
                  f"{len(inhalt)} Byte in {bloecke} Bloecken nach {port}:{ziel}"
                  if not fehler else fehler[:70],
                  "" if not fehler else "Leitung gestoert oder Brett voll. Noch einmal.")
        if b.gescheitert:
            return b.text("ESP32 laden")

        # --- 6. Pruefsumme AUF DEM BRETT -------------------------------------------
        aus, fehler = _ausfuehren(v, SUMME_AUF_DEM_BRETT.format(ziel=ziel), 30, mit)
        t = re.search(r"SUMME\s+([0-9a-f]{64})\s+(\d+)", aus)
        if t:
            sha_g, byte_g = t.group(1), int(t.group(2))
            h = hashlib.sha256()
            for i in range(0, len(inhalt), 256):
                h.update(inhalt[i:i + 256])
            gleich = (h.hexdigest() == sha_g) and (byte_g == len(inhalt))
            b.schritt(6, "Pruefsumme vom Brett", gleich,
                      f"SHA-256 {sha_g[:16]}…, {byte_g} Byte — "
                      + ("gleich der Werkstattdatei" if gleich
                         else f"VERSCHIEDEN (Rechner {h.hexdigest()[:16]}…, {len(inhalt)} Byte)"),
                      "" if gleich else "Die Uebertragung war unvollstaendig. Noch einmal laden.")
        else:
            b.schritt(6, "Pruefsumme vom Brett", False, (fehler or aus)[:70],
                      "Das Brett konnte die Summe nicht bilden.")
        if b.gescheitert:
            return b.text("ESP32 laden")

        # --- 7. Neustart -----------------------------------------------------------
        _sende(v, b"\x02", mit)
        time.sleep(0.2)
        _sende(v, b"\r\x03\x03", mit)
        time.sleep(0.2)
        v.reset_input_buffer()
        _sende(v, b"\x04", mit)
        start = _lies(v, None, 3, mit).decode("utf-8", "replace")
        b.schritt(7, "Neustart", True, "weicher Neustart ausgeloest")

        # --- 8. Lebenszeichen ------------------------------------------------------
        sekunden = float(e.get("sekunden", 6))
        gehoert = _lies(v, None, min(max(sekunden, 2), 30), mit).decode("utf-8", "replace")
        zeilen = [z for z in (start + gehoert).splitlines() if z.strip()
                  and not z.startswith(">>>") and "MPY:" not in z]
        #  AUSKUNFT, KEIN URTEIL (10.10.2026, gemessen). Bis hierher liess dieser Schritt
        #  das ganze Laden durchfallen, wenn das Programm nichts sagte. Genau das tat ein
        #  Blinkprogramm: Die Datei lag Byte fuer Byte auf dem Brett (Schritt 6, Pruefsumme
        #  VOM BRETT), der Neustart lief (Schritt 7), und am Geraet mass esp32_nachlesen
        #  1,0000 s Taktzeit — das Programm lief also nachweislich. Trotzdem hiess es
        #  „LADEN NICHT BESTANDEN", der Agent verlangte eine Berichtigung, und das Modell
        #  haette ein funktionierendes Programm umgeschrieben.
        #  Ob ein Programm etwas SAGT, ist eine Eigenschaft des Programms und kein Mass
        #  dafuer, ob es GELADEN wurde. Geladen ist geladen, wenn die Pruefsumme stimmt.
        #  Was das Programm tut, misst esp32_nachlesen an den Anschluessen.
        b.auskunft(8, "Meldungen des Programms",
                   (f"{len(zeilen)} Zeilen in {sekunden:.0f} s, erste: {zeilen[0][:40]}"
                    if zeilen else
                    f"keine in {sekunden:.0f} s — ein Blinkprogramm gibt nichts aus; "
                    f"was es an den Anschluessen tut, misst esp32_nachlesen"))
    finally:
        try:
            v.close()
        except Exception:
            pass
        #  Windows gibt einen COM-Anschluss nicht im selben Augenblick frei, in dem das
        #  Programm ihn schliesst — der Treiber braucht einen Moment. Ohne diese Pause
        #  scheiterte am 10.10.2026 die Messung direkt nach dem Laden mit „failed to
        #  access COM3 (it may be in use by another program)", und damit der ganze
        #  Auftrag. Eine halbe Sekunde kostet nichts und erspart einen Fehlschlag.
        try:
            import time as _zeit
            _zeit.sleep(0.5)
        except Exception:
            pass
        #  Jetzt ist die Leitung frei: Das Fenster darf uebernehmen und weiter mitlesen.
        try:
            marke.write_text("frei", encoding="utf-8")
        except OSError:
            pass
        notiz("### LEITUNG FREI ###")

    t = b.text(f"ESP32 an {port}: {name} -> {ziel}")
    #  Der Mitschnitt gehoert dazu: Wer laedt, soll sehen, dass geladen wird.
    sicht = []
    for richtung, daten in mit[:40]:
        s = daten.decode("utf-8", "replace").replace("\r", "").strip()
        s = (s.replace("\x01", "<Strg-A>").replace("\x02", "<Strg-B>")
             .replace("\x03", "<Strg-C>").replace("\x04", "<Strg-D>"))
        if s:
            sicht.append(f"    {richtung} {s[:96]}")
    if sicht:
        t += ("\n\nDie ersten Zeilen der Unterhaltung mit dem Brett:\n"
              + "\n".join(sicht)
              + (f"\n    … und {len(mit) - 40} weitere" if len(mit) > 40 else ""))
    return t


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "esp32_laden",
        "Bringt ein Programm aus der Werkstatt auf den ESP32 — die ganze Kette in einem "
        "Aufruf: Treiber und Anschluss, Leitung, MicroPython, Platz, Schreiben, Pruefsumme "
        "VOM BRETT, Neustart, Lebenszeichen. Jeder Schritt wird gemessen; ein Fehlschlag sagt, "
        "woran es liegt und was jetzt hilft. Mit art 'pruefen' wird nur geprueft, ob es ginge, "
        "ohne etwas zu veraendern. Urteil: LADEN BESTANDEN / NICHT BESTANDEN.",
        {"datei":    {"type": "string", "description": "Name in der Werkstatt, z. B. blink.py"},
         "port":     {"type": "string", "description": "Anschluss, z. B. COM3; leer = selbst suchen"},
         "ziel":     {"type": "string", "description": "Name auf dem Brett, Vorgabe main.py"},
         "art":      {"type": "string", "description": "laden (Vorgabe) oder pruefen"},
         "sekunden": {"type": "number", "description": "wie lange auf Lebenszeichen gewartet wird"},
         "fenster":  {"type": "boolean", "description": "Fenster mit Mitschnitt oeffnen, Vorgabe true"}},
        [], {"art": "pruefen"}, tun))
