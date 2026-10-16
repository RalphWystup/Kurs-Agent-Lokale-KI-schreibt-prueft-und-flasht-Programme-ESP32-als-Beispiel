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
LOG = ABLAGE / "llama_start.log"      # was der Modellserver beim Start meldet
GELADEN_DATEI = ABLAGE / "modell_geladen.txt"   # welche Modelldatei wirklich laeuft

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


def _wer_haelt_den_speicher() -> str:
    """Die fuenf groessten Prozesse nennen — damit die Ursache im Text steht, nicht im Kopf."""
    if os.name != "nt":
        return ""
    try:
        r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                           timeout=60, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return ""
        zeilen = []
        for z in (r.stdout or "").splitlines():
            teile = [s.strip('"') for s in z.split('","')]
            if len(teile) < 5:
                continue
            kb = teile[4].replace(".", "").replace(",", "").replace(" K", "").strip()
            if kb.isdigit():
                zeilen.append((int(kb), teile[0]))
        zeilen.sort(reverse=True)
        if not zeilen:
            return ""
        gross = [f"{n} ({k/1e6:.1f} GB)" for k, n in zeilen[:5] if k > 300000]
        if not gross:
            return ""
        hinweis = ""
        if any("llama-server" in n for _, n in zeilen[:5]):
            hinweis = ("\n  Darunter ist llama-server — ein Modellserver aus einem frueheren "
                       "Lauf. Beende ihn, dann ist der Platz wieder da.")
        return "Den Speicher halten gerade: " + ", ".join(gross) + "." + hinweis + "\n"
    except Exception:
        return ""


#  Welches Modell genommen wird, wenn es festgelegt ist. Leer heisst: nach freiem Speicher
#  waehlen, wie bisher. Anweisung des Auftraggebers vom 10.10.2026: „das mit dem Umschalten
#  der LLM lassen wir auch, welches der Modelle kann die Aufgaben erledigen, das nehmen wir."
#
#  Eine Wahl nach freiem Speicher ist keine Wahl, sondern ein Zufall: Dasselbe Paket laedt
#  mal das 3B, mal das 7B — je nachdem, was sonst auf dem Rechner laeuft. Damit schwankt
#  jedes Ergebnis, und keine Pruefung ist wiederholbar.
#
#  Gesetzt wird es in paket/modell/GEWAEHLT.txt (eine Zeile, der Dateiname) oder ueber die
#  Umgebungsvariable KURS_AGENT_MODELL. Steht dort nichts, bleibt es bei der alten Wahl.
def festgelegt() -> "pathlib.Path | None":
    """Das Modell, das ausdruecklich gewaehlt wurde — oder None."""
    import os
    name = (os.environ.get("KURS_AGENT_MODELL") or "").strip()
    if not name:
        d = PAKET / "modell" / "GEWAEHLT.txt"
        try:
            name = d.read_text(encoding="utf-8").strip() if d.is_file() else ""
        except OSError:
            name = ""
    if not name:
        return None
    treffer = sorted(PAKET.glob(f"modell/{name}"))
    return treffer[-1] if treffer else None


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
    fest = festgelegt()
    if fest:
        #  Ausdruecklich gewaehlt: Dann wird dieses genommen und sonst keines. Passt es nicht
        #  in den Speicher, ist das ein Fehler, den der Mensch sehen muss — und nicht ein
        #  stiller Wechsel auf ein kleineres Modell, nach dem die Ergebnisse anders aussehen.
        frei_ = freier_speicher_gb()
        if frei_ is not None and bedarf_gb(fest) > frei_:
            return None, (f"Festgelegt ist {fest.name} (braucht {bedarf_gb(fest):.1f} GB), "
                          f"frei sind nur {frei_:.1f} GB.\n"
                          f"{_wer_haelt_den_speicher()}"
                          f"Entweder Speicher freimachen, oder in "
                          f"paket/modell/GEWAEHLT.txt ein kleineres Modell eintragen.")
        if laut:
            print(f"  Festgelegt: {fest.name} ({fest.stat().st_size/1e9:.2f} GB)")
        return fest, None

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
    #  Wer den Speicher haelt, gehoert in die Meldung. Am 09.10.2026 war es der eigene
    #  Vorgaenger: ein llama-server aus dem vorigen Lauf lief weiter und hielt 5 GB. Die
    #  Meldung sagte nur „kein Platz" — und der Agent fiel auf das Drehbuch zurueck, das ein
    #  Blinkprogramm schrieb, obwohl ein Taschenrechner verlangt war. Eine Ursache, die man
    #  nennen kann, gehoert genannt (je schwaecher der Schueler, desto besser der Lehrer).
    return None, (f"Keines der {len(alle)} mitgelieferten Modelle passt in den freien "
                  f"Speicher ({frei:.1f} GB). Das kleinste, {klein.name}, braucht "
                  f"{bedarf_gb(klein):.1f} GB.\n"
                  f"{_wer_haelt_den_speicher()}"
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


#  Warum die Antwort beim letzten Mal endete: "stop" (das Modell war fertig), "length" (die
#  Laengengrenze war erreicht — die Antwort ist abgeschnitten), oder leer (unbekannt).
LETZTER_GRUND = ""
LETZTE_KENNUNG: dict = {}


class _FremderServer:
    """Ein Modellserver, den jemand anderes gestartet hat. Verhaelt sich nach aussen wie ein
    laufender Unterprozess (poll() -> None), laesst sich aber nicht beenden: Wer ihn nicht
    gestartet hat, beendet ihn auch nicht."""

    def poll(self):
        return None if laeuft_schon(1.0) else 0

    def terminate(self):
        pass

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 0


FREMDER_SERVER = _FremderServer()


def laeuft_schon(zeit: float = 2.0) -> bool:
    """Antwortet auf 127.0.0.1:8099 bereits ein Modellserver?

    Angelegt am 10.10.2026, gemessen: Nach einem Neustart des Agenten lief llama-server noch
    mit 4,4 GB und antwortete auf /health mit {"status":"ok"} — der Agent kannte aber nur
    seinen EIGENEN Unterprozess (`self.server`), hielt das Modell fuer nicht vorhanden,
    versuchte einen zweiten Server zu starten, bekam den Speicher nicht und fiel stumm auf
    das Drehbuch zurueck. Ein laufender Server ist ein laufender Server, gleich wer ihn
    gestartet hat.
    """
    import urllib.request
    try:
        with urllib.request.urlopen(ADRESSE + "/health", timeout=zeit) as a:
            return b'"ok"' in a.read(200)
    except Exception:
        return False


def starten(laut=True):
    """Startet llama-server und wartet, bis er antwortet. Gibt den Prozess zurueck.

    Laeuft schon einer auf dem Port, wird dieser weiterverwendet (None als Rueckgabe heisst:
    es gibt einen Server, aber er gehoert uns nicht).
    """
    if laeuft_schon():
        if laut:
            print(f"Auf {ADRESSE} antwortet bereits ein Modellserver — er wird "
                  f"weiterverwendet (kein zweiter Start, der Speicher reicht fuer einen).")
        return FREMDER_SERVER
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
    #  "-np 1": genau EIN Steckplatz. Gemessen am 09.10.2026 aus den Startmeldungen des
    #  Servers, die bis dahin nach DEVNULL gingen:
    #
    #      srv load_model: initializing, n_slots = 4, n_ctx_slot = 16384
    #
    #  Vier Steckplaetze zu je 16384 Token — der Server legte Platz fuer 65536 Token an,
    #  obwohl immer nur ein Agent fragt. Der Zwischenspeicher dafuer (KV-Cache) ist das
    #  Vierfache des Noetigen. Folge, ebenfalls gemessen: 2,9 bis 3,7 Token je Sekunde beim
    #  Schreiben, und der freie Speicher sank auf 2,6 GB, worauf der naechste Agentenstart
    #  kein Modell mehr unterbrachte und stumm auf das Drehbuch zurueckfiel.
    #
    #  Die Vorgabe von llama-server ist 4, weil ein Server ueblicherweise mehrere Nutzer
    #  bedient. Hier fragt genau einer. Ein Steckplatz genuegt, und was er nicht belegt,
    #  bleibt fuer das Modell selbst.
    #  "--cache-reuse 256": den schon gelesenen Prompt weiterverwenden, auch wenn in der
    #  Mitte etwas fehlt. Gemessen am 09.10.2026 aus den Zeitangaben des Servers:
    #
    #      prompt eval time =  4613 ms /   85 tokens   (der Rest war zwischengespeichert)
    #      prompt eval time = 68103 ms / 1689 tokens   (nach einer Aenderung in der Mitte)
    #
    #  Solange nur hinten etwas dazukommt, liest der Server nur das Neue -- 16 s je Schritt.
    #  Sobald der Agent den Verlauf verdichtet (er fasst aeltere Schritte zu je einer Zeile
    #  zusammen, damit das Kontextfenster reicht), aendert sich die MITTE des Prompts, der
    #  Zwischenspeicher passt nicht mehr, und alles wird neu gelesen: bei 24 Token je Sekunde
    #  und 16000 Token sind das elf Minuten fuer einen einzigen Schritt.
    #
    #  --cache-reuse erlaubt dem Server, auch ueber eine Luecke hinweg weiterzuverwenden,
    #  solange sie kleiner als der angegebene Wert ist. Genau dafuer ist der Schalter gebaut.
    #  Der vorgewaermte Zustand wird auf die Platte gelegt (10.10.2026, Befund B1).
    #
    #  Gemessen an seinem eigenen Lauf: Von START.bat bis zur ersten Antwort vergingen vier
    #  Minuten, davon 184 s allein fuer das Einlesen des Anweisungstextes (6036 Token bei
    #  38 Token je Sekunde). Dieser Text ist bei JEDEM Start derselbe — er wird trotzdem
    #  jedes Mal neu gerechnet.
    #
    #  llama-server kann den Zustand eines Steckplatzes speichern und wieder laden. Damit
    #  faellt das Rechnen weg: Beim zweiten und jedem weiteren Start wird gelesen statt
    #  gerechnet. Sein Wort dazu: „das vorwaermen dauert eher 4 minuten".
    kv = ABLAGE / "vorgewaermt"
    try:
        kv.mkdir(parents=True, exist_ok=True)
    except OSError:
        kv = None
    befehl = [str(exe), "-m", str(gguf), "--host", "127.0.0.1", "--port", "8099",
              "-c", "16384", "-np", "1", "--cache-reuse", "256",
              "-ngl", "99", "--jinja", "--no-webui"]
    if kv is not None:
        befehl += ["--slot-save-path", str(kv)]
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
    #  Die Startmeldungen des Servers gehoeren in eine Datei, nicht ins Nichts (09.10.2026).
    #  Bis dahin gingen sie nach DEVNULL. Als der Agent mit 2,9 Token je Sekunde arbeitete —
    #  gemessen, nicht geschaetzt —, liess sich nicht feststellen, warum: Ob eine Grafikkarte
    #  benutzt wird, wieviel Speicher der Kontext belegt und mit wievielen Faeden gerechnet
    #  wird, steht genau in diesen Zeilen. Wer sie wegwirft, kann hinterher nicht messen
    #  (Grundsatz 36). Die Datei wird bei jedem Start ueberschrieben und bleibt klein.
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "w", encoding="utf-8", errors="replace")
    #  Kein eigenes Konsolenfenster (10.10.2026): Der Server schreibt alles in llama_start.log;
    #  ein schwarzes Fenster auf dem Bildschirm des Auftraggebers zeigt nichts, was dort nicht
    #  steht, und steht dauerhaft im Weg. CREATE_NO_WINDOW statt DETACHED_PROCESS, damit der
    #  Prozess weiter an den Agenten gebunden bleibt und mit ihm endet.
    p = subprocess.Popen(befehl, stdout=log, stderr=subprocess.STDOUT,
                         env=u, cwd=str(exe.parent),
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    ABLAGE.mkdir(parents=True, exist_ok=True)
    PID_DATEI.write_text(str(p.pid), encoding="utf-8")
    #  Welche Datei WIRKLICH geladen wurde. Bis zum 09.10.2026 nahm die Oberflaeche dafuer
    #  „die letzte .gguf im Paketordner" — sie riet also. Gemessen an diesem Tag: geladen war
    #  Qwen2.5-7B, angezeigt wurde Qwen2.5-Coder-3B. Wer sich auf die Anzeige verlaesst, misst
    #  das falsche Modell (Kriterium P5).
    GELADEN_DATEI.write_text(gguf.name, encoding="utf-8")

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


#  Wieviel Platz eine Antwort hoechstens hat. Nachgerechnet am 09.10.2026, nicht geschaetzt:
#
#    Ein brauchbarer Taschenrechner mit Fenster  2056 Zeichen Quelltext
#    JSON-Huelle des Werkzeugaufrufs               60 Zeichen
#    Aufschlag fuer \n und \" als je zwei Zeichen  123 Zeichen
#    zusammen                                    2239 Zeichen  =  rund 640 Token
#    dazu die zwei Saetze, die das Modell gern davorschreibt       ~120 Token
#    gebraucht also                                                ~760 Token
#
#  Die Grenze stand bei 800. Das reichte rechnerisch — und in jedem der vier Laeufe vom
#  09.10.2026 endete die Antwort trotzdem an der Grenze, weil das Modell etwas mehr Vorrede
#  schrieb. Eine Grenze ohne Spielraum ist keine Grenze, sondern eine Falle: Der Agent sah nur
#  einen Formatfehler und wies ihn zurueck, das Modell schickte dasselbe wieder.
#  1600 gibt den doppelten Spielraum. Bei einem Modell mit 20 Token je Sekunde kostet das im
#  schlimmsten Fall 80 s je Antwort — hinnehmbar gegenueber einem Lauf, der nie fertig wird.
MAX_TOKEN = 1600


def vorwaermen(systemtext: str, laut: bool = False) -> float:
    """Den gleichbleibenden Anfang des Prompts EINMAL einlesen lassen, bevor jemand wartet.

    Warum (10.10.2026, gemessen an den Meldungen des Servers):

        Anfrage 1:  162,8 s fuer 5735 Token einlesen,  0,0 s antworten
        Anfrage 2:    1,3 s fuer   49 Token einlesen,  0,0 s antworten
        Anfrage 3:    4,8 s fuer  104 Token einlesen,  0,0 s antworten

    Der Systemtext ist bei jedem Auftrag derselbe; llama-server verwendet den
    gleichbleibenden Anfang wieder (--cache-reuse), deshalb kostet nur der ERSTE Aufruf
    nach dem Start die vollen 163 Sekunden. Der Auftraggeber bemerkte es an der Stelle, an
    der es am meisten stoert: beim Gruss. „Warum dauert ‚hallo bist du bereit‘ so lange? …
    Eine Anfrage an ein LLM ist eine Matrixoperation, Text rein, Text raus."

    Also wird diese eine teure Anfrage dorthin verlegt, wo niemand davorsitzt: in den
    Start. Verlangt wird genau EIN Token Antwort — gebraucht wird nicht die Antwort,
    sondern der gefuellte Zwischenspeicher.

    Gibt die gebrauchte Zeit in Sekunden zurueck (0.0, wenn es nicht ging).
    """
    import hashlib as _h
    import time as _t
    t0 = _t.time()

    #  Der Name traegt die Pruefsumme des Systemtexts UND des Modells (10.10.2026):
    #  Ein gespeicherter Zustand gehoert zu genau diesem Text und genau diesem Modell.
    #  Aendert sich eine Zeile der Anweisung, passt er nicht mehr — und ein unbemerkt
    #  veralteter Zustand waere schlimmer als gar keiner: Der Agent liefe mit Regeln, die
    #  niemand mehr im Quelltext findet. Darum steht die Pruefsumme im Dateinamen, und ein
    #  alter Stand wird nie gefunden, sondern bleibt einfach liegen.
    try:
        welches = GELADEN_DATEI.read_text(encoding="utf-8").strip()
    except OSError:
        welches = "unbekannt"
    marke = _h.sha256((systemtext + "|" + welches).encode("utf-8")).hexdigest()[:16]
    name = f"anweisung_{marke}.bin"

    def _slot(aktion: str) -> bool:
        """save oder restore auf Steckplatz 0. Gibt zurueck, ob es ging."""
        try:
            d = json.dumps({"filename": name}).encode()
            a = urllib.request.Request(f"{ADRESSE}/slots/0?action={aktion}", data=d,
                                       headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(a, timeout=120) as r:
                r.read()
            return True
        except Exception:
            return False

    #  Erst laden versuchen. Gelingt es, war der Text schon einmal gelesen.
    geladen = _slot("restore")
    if geladen:
        d = _t.time() - t0
        if laut:
            print(f"  Vorgewaermter Zustand geladen in {d:.1f} s (statt neu zu rechnen).")
        return d

    try:
        fragen([{"role": "system", "content": systemtext},
                {"role": "user", "content": "bereit?"}], max_token=1, temperatur=0.0)
    except Exception as ex:
        if laut:
            print(f"  Vorwaermen nicht moeglich ({type(ex).__name__}) — der erste Auftrag "
                  f"dauert dann laenger.")
        return 0.0
    d = _t.time() - t0
    #  Jetzt liegt der Text im Zwischenspeicher — aufheben fuer den naechsten Start.
    #  Schlaegt das fehl (alter Server, kein Platz, Rechte), ist nichts verloren: Dann
    #  wird beim naechsten Mal wieder gerechnet wie bisher.
    wenn_gespeichert = _slot("save")
    if laut:
        print(f"  Modell vorgewaermt in {d:.0f} s — der erste Auftrag beginnt jetzt sofort."
              + ("  Der Zustand ist aufgehoben; der naechste Start wird schnell."
                 if wenn_gespeichert else ""))
    return d


def fragen(verlauf, max_token=MAX_TOKEN, temperatur=0.2) -> str:
    """Schickt den Verlauf an das Modell und gibt die Antwort als Text zurueck."""
    daten = json.dumps({"messages": verlauf, "max_tokens": max_token,
                        "temperature": temperatur, "stream": False}).encode()
    a = urllib.request.Request(f"{ADRESSE}/v1/chat/completions", data=daten,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(a, timeout=600) as r:
            antwort = json.loads(r.read())
            wahl = antwort["choices"][0]
            #  Warum der Grund mitgeschrieben wird (09.10.2026, gemessen):
            #  Qwen2.5-Coder-3B schrieb den Taschenrechner und erreichte dabei die
            #  Laengengrenze — die Antwort endete mitten in einer Zeile
            #  ("self.master.bind('<Key-0>', lambda e: self"). Der Agent sah nur, dass der
            #  Aufruf kein gueltiges JSON war, wies ihn zurueck, bekam dasselbe wieder und
            #  lief zehn Minuten im Kreis. Eine abgeschnittene Antwort ist kein Formatfehler
            #  des Modells, sondern eine erschoepfte Laengengrenze — und dagegen hilft nur
            #  eine andere Anweisung: kuerzer schreiben. Kriterium C1 des Prueffplans fuer
            #  selbstaendige Agenten ("abgeschnittene Antworten gelten nicht als Erfolg").
            global LETZTER_GRUND, LETZTE_KENNUNG
            LETZTER_GRUND = wahl.get("finish_reason") or ""
            #  Echtheit (15.10.2026, Kriterium E1): Kennung, Zeit, Modellname und Tokenzahl des
            #  Servers zu dieser Antwort — damit ein Lauf belegen kann, dass jede Antwort ein
            #  eigener Aufruf war und nicht aus einer Ablage kam.
            LETZTE_KENNUNG = {"id": antwort.get("id"), "created": antwort.get("created"),
                              "model": antwort.get("model"), "usage": antwort.get("usage")}
            return wahl["message"]["content"] or ""
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


def geladenes() -> str:
    """Der Name der Modelldatei, die gerade laeuft — oder leer, wenn keine laeuft."""
    try:
        if PID_DATEI.is_file() and GELADEN_DATEI.is_file():
            return GELADEN_DATEI.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def beenden(p):
    GELADEN_DATEI.unlink(missing_ok=True)
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
