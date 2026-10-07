#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Das lokale Sprachmodell — gestartet, befragt, wieder beendet.

Benutzt wird ``llama-server`` aus llama.cpp: ein einzelnes Programm, das eine Modelldatei
(.gguf) laedt und ueber HTTP auf 127.0.0.1 antwortet. Nichts davon verlaesst den Rechner,
und nichts davon wird installiert — beide Dateien liegen im Paket und werden am Ende
einfach nicht mehr gestartet.

Warum ein eigener Server und nicht eine Bibliothek im Agenten: so laesst sich das Modell
wechseln, ohne eine Zeile am Agenten zu aendern, und ein abgestuerztes Modell reisst den
Agenten nicht mit. Ausserdem spricht llama-server dieselbe Schnittstelle wie die grossen
Anbieter — wer spaeter umsteigt, tauscht die Adresse und sonst nichts.
"""
from __future__ import annotations
import json, os, subprocess, time, urllib.request, urllib.error, sys
from pfade import ABLAGE, PAKET, eine, umgebung

PID_DATEI = ABLAGE / "llama.pid"

ADRESSE = "http://127.0.0.1:8099"


class KeinModell(Exception):
    pass


class KontextVoll(KeinModell):
    """Der Verlauf passt nicht mehr ins Kontextfenster — die Schleife kuerzt und fragt erneut."""


def signaturpflicht():
    """Laesst dieser Rechner nur signierte Programme laufen? (Windows 11, Smart App Control)

    Anlass, 04.10.2026, 0:35 Uhr: Der erste Start auf echtem Windows endete mit einem
    Fehlerfenster — "llama-server-impl.dll ist entweder nicht fuer die Ausfuehrung unter
    Windows vorgesehen oder enthaelt einen Fehler, Fehlerstatus 0xc0e90002". Die Datei war
    Byte fuer Byte in Ordnung (Pruefsumme verglichen). 0xc0e90002 ist der Fehlerstatus der
    Code-Integritaetspruefung: Smart App Control laesst nur signierte Programme laufen.
    Python von python.org ist signiert, llama.cpp ist es nicht.

    Der Zustand steht in der Registrierung und ist ohne Adminrechte lesbar:
      0 = Aus, 1 = Ein (sperrt), 2 = Auswertung (sperrt noch nicht, kann aber umschalten).
    Rueckgabe: (Text fuer die Anzeige, sperrt: bool). Diese Funktion ist die EINE Stelle
    dafuer — pruefe_rechner.py fragt sie, der Agent fragt sie, START.bat zeigt sie.
    """
    if os.name != "nt":
        return "nicht Windows", False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            wert, _ = winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")
    except FileNotFoundError:
        return "nicht vorhanden (Windows 10 oder aelter)", False
    except OSError as e:
        return f"nicht lesbar ({e})", False
    return {0: ("Aus", False), 1: ("EIN - sperrt unsignierte Programme", True),
            2: ("Auswertung - sperrt noch nicht", False)}.get(wert, (f"unbekannt ({wert})", False))


GESPERRT = (
    "Dieser Rechner laesst nur signierte Programme laufen (Smart App Control: EIN). Das "
    "Sprachmodell braucht llama.cpp, und das ist nicht signiert — Windows weist es ab "
    "(Fehlerstatus 0xc0e90002, 'Ungueltiges Bild').\n"
    "Alles ohne Modell laeuft trotzdem: dieselben Werkzeuge, dieselbe Abnahme, die "
    "virtuelle LED, der Nachweis — die Entscheidungen trifft dann ein festes Drehbuch.\n"
    "Smart App Control steht in Windows-Sicherheit > App- & Browsersteuerung. Es laesst "
    "sich dort ausschalten, aber nur einmal; wieder einschalten geht nur mit einer "
    "Neuinstallation von Windows. Das entscheidet der Besitzer des Rechners, nicht dieses "
    "Programm.")


def _fehlercode(rc: int) -> str:
    """Den Rueckgabewert eines gestorbenen llama-server in Worte fassen."""
    code = rc & 0xFFFFFFFF
    if code == 0xC0E90002:
        return "0xC0E90002 — Windows hat die Datei gesperrt (Code-Integritaet, Smart App Control)"
    if code == 0xC000007B:
        return "0xC000007B — falsche Bitbreite oder beschaedigte Datei"
    if code == 0xC0000135:
        return "0xC0000135 — eine DLL fehlt (meist vulkan-1.dll: Grafiktreiber ohne Vulkan)"
    return f"{rc} (0x{code:08X})"


def freier_speicher_gb() -> float | None:
    """Wieviel Arbeitsspeicher steht jetzt zur Verfuegung?

    Nicht der eingebaute, sondern der **freie**: auf einem Kursrechner laufen Browser,
    Virenscanner und was sonst noch offen ist. Ein Modell, das rechnerisch hineinpasst,
    aber den Rechner ins Auslagern treibt, ist unbrauchbar langsam.
    """
    try:
        if os.name == "nt":
            import ctypes

            class S(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            s = S(); s.dwLength = ctypes.sizeof(S)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return s.ullAvailPhys / 1e9
        with open("/proc/meminfo") as f:
            for z in f:
                if z.startswith("MemAvailable:"):
                    return int(z.split()[1]) * 1024 / 1e9
    except Exception:
        return None
    return None


def bedarf_gb(gguf) -> float:
    """Was dieses Modell im Betrieb braucht, abgeleitet aus der Dateigroesse.

    Gemessen am Pruefstand: 1,93 GB Datei brauchten 3,48 GB, 4,68 GB Datei brauchten
    6,70 GB. Das sind Faktoren von 1,80 und 1,43 — der Zuschlag faellt mit der Groesse,
    weil der feste Anteil (Kontext, Puffer) gleich bleibt. Die Gerade durch beide Punkte
    ist Datei x 1,17 + 1,22 GB; aufgerundet auf x 1,25 + 1,3, damit kein Rechner knapp
    daneben liegt.

    **Berichtigt am 07.10.2026.** Diese Schaetzung hat ein Modell abgelehnt, das laeuft.
    Auf dem Rechner des Auftraggebers waren 3,6 GB frei; die Formel verlangte 4,2 GB fuer
    Qwen2.5-Coder-3B (1,93 GB Datei) und der Agent arbeitete ohne Modell weiter. Derselbe
    llama-server wurde daraufhin mit demselben Modell und demselben Kontext (16384) von Hand
    gestartet: Er lief nach 3 s und belegte **1,69 GB** (Arbeitssatz, gemessen mit tasklist).
    Der Unterschied kommt daher, dass llama.cpp die Modelldatei ueber eine Speicherabbildung
    liest; sie steht im Dateicache und zaehlt nicht voll zum Bedarf. Die alten Zahlen vom
    Pruefstand massen offenbar den belegten Gesamtspeicher, nicht den Bedarf des Programms.

    Neue Gerade durch den gemessenen Punkt, mit Reserve: Datei x 1,0 + 0,9 GB. Fuer das
    3B-Modell sind das 2,8 GB statt 4,2 GB, fuer das 7B-Modell 5,6 GB. Wer knapp daneben
    liegt, merkt es sofort: starten() wartet ohnehin, bis der Server antwortet, und meldet
    sonst einen Fehler — ein zu knapp geschaetztes Modell faellt also auf, ein zu grosszuegig
    geschaetztes nicht.
    """
    return gguf.stat().st_size / 1e9 * 1.0 + 0.9


def waehlen(laut=True):
    """Sucht aus den mitgelieferten Modellen das groesste aus, das hier laeuft.

    Welches Modell passt, entscheidet sich **auf dem Rechner, auf dem es laufen soll** —
    nicht auf dem, der den Stick geschnuert hat. Ein Kursraum hat Rechner mit 8 und mit
    32 GB; derselbe Stick muss auf beiden starten. Liegen mehrere Modelle im Paket, wird
    hier gewaehlt, und der Benutzer muss davon nichts wissen.
    """
    #  Gleich grosse Modelle: das Coder-Modell zuerst. Die Aufgabe verlangt ein Modell „speziell
    #  fuer die Python-Programmierung" (04.10.2026); auf dem Pruefstand brauchte Qwen2.5-Coder-3B
    #  4 Werkzeugaufrufe fuer Karte 1, Qwen2.5-3B-Instruct 16.
    alle = sorted(PAKET.glob("modell/*.gguf"),
                  key=lambda d: (d.stat().st_size, "coder" in d.name.lower()), reverse=True)
    if not alle:
        return None, "Im Paket liegt keine Modelldatei (paket/modell/*.gguf)."
    frei = freier_speicher_gb()
    if frei is None:
        if laut:
            print(f"  Freier Speicher nicht ermittelbar — genommen wird {alle[-1].name} "
                  f"(das kleinste, das sicherste).")
        return alle[-1], None
    for d in alle:
        if bedarf_gb(d) <= frei:
            if laut:
                andere = [x for x in alle if x is not d]
                print(f"  Gewaehlt: {d.name} ({d.stat().st_size/1e9:.2f} GB, braucht "
                      f"{bedarf_gb(d):.1f} GB; frei sind {frei:.1f} GB)"
                      + (f", uebergangen: {', '.join(x.name for x in andere)}" if andere else ""))
            return d, None
    klein = alle[-1]
    return None, (f"Keines der {len(alle)} mitgelieferten Modelle passt in den freien "
                  f"Speicher ({frei:.1f} GB). Das kleinste, {klein.name}, braucht "
                  f"{bedarf_gb(klein):.1f} GB.\n"
                  f"Was jetzt hilft: andere Programme schliessen, oder ein kleineres Modell "
                  f"holen (hole_paket.py --modell 1.5b), oder ohne Modell arbeiten — "
                  f"START.bat, Punkt 'Ohne Modell durchlaufen'. Dabei laufen dieselben "
                  f"Werkzeuge und dieselbe Abnahme, nur die Reihenfolge steht fest.")


def signiert(pfad) -> bool:
    """Traegt diese Windows-Programmdatei eine Signatur?

    Gelesen am Zertifikatsverzeichnis im PE-Kopf (Datenverzeichnis 4). Geprueft wird nur,
    OB eine Signatur da ist -- ob sie gueltig ist, entscheidet Windows beim Start. Anlass
    (04.10.2026): Smart App Control sperrte unser llama.cpp; im Ollama-Archiv liegt derselbe
    Server, von Ollama Inc. ueber DigiCert signiert (alle 66 Dateien, gemessen am Archiv).
    """
    try:
        import pathlib
        d = pathlib.Path(pfad).read_bytes()
        pe = int.from_bytes(d[0x3C:0x40], "little")
        if d[pe:pe + 4] != b"PE\0\0":
            return False
        magic = int.from_bytes(d[pe + 24:pe + 26], "little")
        dd = pe + 24 + (112 if magic == 0x20B else 96)
        return int.from_bytes(d[dd + 36:dd + 40], "little") > 0
    except Exception:
        return False


def starten(laut=True):
    """Startet llama-server und wartet, bis er antwortet. Gibt den Prozess zurueck."""
    #  Zuerst der signierte Server (aus dem Ollama-Archiv, paket\llama_signiert), dann der
    #  unsignierte aus dem llama.cpp-Archiv. Beides ist dasselbe Programm; den Unterschied
    #  macht nur die Unterschrift -- und die entscheidet unter Smart App Control alles.
    exe = (eine("llama_signiert/llama-server.exe") or eine("llama/llama-server.exe")
           or eine("llama/llama-server"))
    if not exe:
        raise KeinModell(
            f"Im Paket fehlt llama-server.\n"
            f"Erwartet wird {PAKET/'llama'/'llama-server.exe'}.\n"
            f"Siehe PAKET_FUELLEN.md. Ohne Modell laeuft der Agent nur mit --drehbuch.")
    #  VOR dem Start fragen, ob Windows ihn ueberhaupt zuliesse. Sonst oeffnet der Lader ein
    #  Fehlerfenster, der Prozess lebt, solange es offen ist, und diese Schleife wartete bis
    #  zu zehn Minuten auf eine Antwort, die nie kommt — die Oberflaeche blieb derweil auf
    #  "laeuft ..." und jeder Knopf war gesperrt (04.10.2026, 0:36 Uhr).
    #  Gesperrt wird nur, was keine Signatur traegt -- die Datei wird gefragt, nicht der Ruf.
    sac_text, sac_sperrt = signaturpflicht()
    if sac_sperrt and not signiert(exe):
        raise KeinModell(GESPERRT + f"\nGeprueft wurde {exe} -- ohne Signatur.")
    gguf, grund = waehlen(laut=laut)
    if not gguf:
        raise KeinModell(grund)

    # --jinja nutzt die im Modell hinterlegte Gespraechsvorlage; ohne sie antworten
    # Instruct-Modelle oft mit Rohtext statt mit einer Antwort.
    befehl = [str(exe), "-m", str(gguf), "--host", "127.0.0.1", "--port", "8099",
              "-c", "16384", "-ngl", "99", "--jinja", "--no-webui"]
    if laut:
        print(f"  Modell wird geladen: {gguf.name} ({gguf.stat().st_size/1e9:.1f} GB) …", flush=True)
    u = umgebung()
    # Unter Windows findet llama-server seine DLL im eigenen Ordner, weil dort gearbeitet
    # wird. Unter Linux fuehrt der Weg zu den .so-Dateien nur ueber diese Variable — ohne
    # sie startet derselbe Server mit "error while loading shared libraries".
    u["LD_LIBRARY_PATH"] = str(exe.parent) + ":" + u.get("LD_LIBRARY_PATH", "")
    if os.name == "nt":
        #  Kein Fehlerfenster, wenn der Lader eine Datei abweist: Der Fehlermodus wird an
        #  den Kindprozess vererbt, der dann sofort mit seinem Fehlercode endet — und die
        #  Schleife unten meldet ihn in Worten, statt dass jemand auf OK klicken muss.
        import ctypes
        SEM_FAILCRITICALERRORS, SEM_NOGPFAULTERRORBOX, SEM_NOOPENFILEERRORBOX = 0x0001, 0x0002, 0x8000
        ctypes.windll.kernel32.SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
                                            | SEM_NOOPENFILEERRORBOX)
    p = subprocess.Popen(befehl, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=u, cwd=str(exe.parent))

    ABLAGE.mkdir(parents=True, exist_ok=True)
    PID_DATEI.write_text(str(p.pid), encoding="utf-8")

    for i in range(600):                      # bis zu zehn Minuten; grosse Modelle brauchen das
        if p.poll() is not None:
            raise KeinModell(f"llama-server hat sich sofort beendet: {_fehlercode(p.returncode)}. "
                             f"Sonst haeufig: zu wenig Arbeitsspeicher fuer dieses Modell.")
        try:
            with urllib.request.urlopen(f"{ADRESSE}/health", timeout=2) as a:
                if a.status == 200:
                    if laut:
                        print(f"  Modell bereit nach {i+1} s.", flush=True)
                    return p
        except Exception:
            time.sleep(1)
    p.terminate()
    raise KeinModell("Das Modell antwortete nach zehn Minuten nicht.")


def fragen(verlauf, max_token=800, temperatur=0.2) -> str:
    """Schickt den Verlauf an das Modell und gibt die Antwort als Text zurueck."""
    daten = json.dumps({"messages": verlauf, "max_tokens": max_token,
                        "temperature": temperatur, "stream": False}).encode()
    a = urllib.request.Request(f"{ADRESSE}/v1/chat/completions", data=daten,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(a, timeout=600) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"] or ""
    except urllib.error.HTTPError as e:
        #  400 heisst bei llama-server fast immer: mehr Text als das Kontextfenster fasst.
        #  Am 04.10.2026 endete so der erste echte Lauf auf Windows nach 23 Schritten.
        #  Die Schleife kann darauf antworten (zusammenfassen) — also ein eigener Fehler.
        inhalt = e.read(2000).decode("utf-8", "replace") if hasattr(e, "read") else ""
        if e.code == 400:
            raise KontextVoll(f"Das Kontextfenster des Modells ist voll (HTTP 400): {inhalt[:300]}")
        raise KeinModell(f"Das Modell antwortet mit Fehler {e.code}: {inhalt[:300]}")
    except urllib.error.URLError as e:
        raise KeinModell(f"Das Modell antwortet nicht mehr: {e}")


def beenden(p):
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
    PID_DATEI.unlink(missing_ok=True)


if __name__ == "__main__":
    p = starten()
    try:
        print(fragen([{"role": "user", "content": "Antworte mit genau einem Wort: bereit"}]))
    finally:
        beenden(p)
