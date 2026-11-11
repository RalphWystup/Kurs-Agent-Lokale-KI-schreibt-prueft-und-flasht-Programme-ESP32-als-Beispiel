#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""alles_gut.py — Fassung 1.0 vom 11.11.2026. Das Helferprogramm von ALLES_GUT_START_1.0.bat.

Laeuft mit dem eingebetteten Python aus paket\\python_vorlage, das die Startdatei zuvor geholt
hat, und macht aus dem Klon von GitHub ein vollstaendiges Kurspaket — auf einem frischen
Rechner, auf dem sonst nichts ist:

  1. Bericht: Windows, Arbeitsspeicher, freier Platz, Python
  2. 'import site' im eingebetteten Python freischalten (sonst findet es keine Pakete)
  3. pip einrichten (get-pip.py), damit hole_paket.py die Windows-Raeder aufloesen kann
  4. Sprachmodell nach dem Arbeitsspeicher waehlen: ab 12 GB das 7B, sonst das 3B;
     die Wahl steht danach in paket\\modell\\GEWAEHLT.txt
  5. hole_paket.py: Raeder, llama.cpp, MicroPython-Firmware, USB-Treiber, Modell
  6. Kurs-Python vervollstaendigen: setuptools, wheel, esptool aus dem Quellarchiv als Rad bauen
     (im eingebetteten Python geht das nur ohne pip-Abschirmung), pyserial, mpremote, esptool
  7. Treiber-Archive entpacken (die Einrichtung in START.bat braucht die .inf)
  8. Bestand pruefen und sagen, was fehlt

Nichts wird installiert; alles bleibt im Kursordner. Was schon da ist, wird nicht noch einmal
geholt — ein zweiter Lauf holt nur nach. Alles, was hier ausgegeben wird, steht zugleich in
alles_gut_protokoll.txt (hole_paket.py schreibt dazu fuellen_protokoll.txt).

    python alles_gut.py                  alles
    python alles_gut.py --modell 3b      Modell erzwingen (7b, 3b, keins)
    python alles_gut.py --nur-pruefen    nur Bericht und Bestand, nichts aendern
    python alles_gut.py --llama cpu      llama.cpp als reine CPU-Bauart (Vorgabe vulkan, wie gemessen)

Dieses Programm ist wie hole_paket.py ein Werkzeug der Vorbereitung — es ruft ins Netz. Der Kurs
selbst (START.bat, Diener, Seite, Werkzeuge) tut das nicht.
"""
from __future__ import annotations
import argparse
import datetime
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import zipfile

FASSUNG = "1.0"
WURZEL = pathlib.Path(__file__).resolve().parent
PAKET = WURZEL / "paket"
#  Gesamtspeicher, ab dem das Modell genommen wird. 12 GB fuer das 7B: Windows meldet auf dem
#  Rechner, auf dem der Kurs mit dem 7B gemessen wurde (16 GB eingebaut), nur 13,8 GB nutzbar
#  (Grafik und Firmware behalten den Rest) — 14 GB als Grenze haette dort das 3B gewaehlt (11.11.2026).
MODELL_AB_GB = {"7b": 12.0, "3b": 6.0}
GEWAEHLT = PAKET / "modell" / "GEWAEHLT.txt"


# ---------------------------------------------------------------- Mitschrift
class Mitschrift:
    """Bildschirm und Datei zugleich — wie in hole_paket.py: Ein Fenster, das zu ist, sagt nichts mehr."""

    def __init__(self, pfad: pathlib.Path):
        self.schirm = sys.stdout
        try:
            self.datei = pfad.open("w", encoding="utf-8", errors="replace")
        except OSError:
            self.datei = None

    def write(self, s):
        try:
            self.schirm.write(s)
        except UnicodeEncodeError:                       # Windows-Konsole in cp1252
            self.schirm.write(s.encode("ascii", "replace").decode("ascii"))
        if self.datei:
            self.datei.write(s.replace("\r", "\n"))
            self.datei.flush()
        return len(s)

    def flush(self):
        self.schirm.flush()
        if self.datei:
            self.datei.flush()


# ---------------------------------------------------------------- Messungen
def speicher_gb() -> "tuple[float, float] | None":
    """(gesamt, frei) in GB — Windows ueber GlobalMemoryStatusEx, sonst /proc/meminfo."""
    try:
        import ctypes
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return m.ullTotalPhys / 2 ** 30, m.ullAvailPhys / 2 ** 30
    except Exception:                                    # noqa: BLE001 — kein Windows
        pass
    try:
        werte = {}
        for z in pathlib.Path("/proc/meminfo").read_text().splitlines():
            k, _, v = z.partition(":")
            werte[k.strip()] = int(v.split()[0]) / 2 ** 20
        return werte["MemTotal"], werte.get("MemAvailable", 0.0)
    except Exception:                                    # noqa: BLE001
        return None


def lauf(befehl: list, zeit=600) -> subprocess.CompletedProcess:
    return subprocess.run(befehl, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=zeit)


def lauf_sichtbar(befehl: list) -> int:
    """Kindprozess mit laufender Ausgabe — die Fortschrittszeilen von hole_paket.py sollen zu sehen sein."""
    umgebung = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    p = subprocess.Popen(befehl, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=umgebung, cwd=str(WURZEL))
    rest = b""
    while True:
        happen = p.stdout.read(256)
        if not happen:
            break
        rest += happen
        try:
            text = rest.decode("utf-8")
            rest = b""
        except UnicodeDecodeError:                       # ein Zeichen ist am Blockende zerschnitten
            text = rest[:-3].decode("utf-8", "replace")
            rest = rest[-3:]
        sys.stdout.write(text)
        sys.stdout.flush()
    if rest:
        sys.stdout.write(rest.decode("utf-8", "replace"))
    return p.wait()


# ---------------------------------------------------------------- Schritte
def s1_bericht():
    print("Schritt 1 von 8: Bericht")
    print(f"    System:   {platform.system()} {platform.release()} ({platform.version()}), {platform.machine()}")
    print(f"    Python:   {sys.version.split()[0]} — {sys.executable}")
    print(f"    Ordner:   {WURZEL}")
    sp = speicher_gb()
    if sp:
        print(f"    Arbeitsspeicher: {sp[0]:.1f} GB gesamt, {sp[1]:.1f} GB frei")
    else:
        print("    Arbeitsspeicher: NICHT GEMESSEN")
    try:
        du = shutil.disk_usage(WURZEL)
        print(f"    Platz auf dem Laufwerk: {du.free / 2**30:.1f} GB frei von {du.total / 2**30:.0f} GB")
        if du.free / 2 ** 30 < 7:
            print("    ACHTUNG: unter 7 GB frei — das Paket braucht etwa 6 GB.")
    except OSError:
        print("    Platz auf dem Laufwerk: NICHT GEMESSEN")
    print()
    return sp


def s2_import_site(aendern: bool) -> bool:
    print("Schritt 2 von 8: 'import site' im eingebetteten Python")
    exe = pathlib.Path(sys.executable).resolve().parent
    pths = sorted(exe.glob("python3*._pth"))
    if not pths:
        print("    kein ._pth — das ist kein eingebettetes Python, nichts zu tun.\n")
        return True
    pth = pths[0]
    s = pth.read_text(encoding="utf-8")
    if "#import site" not in s:
        print(f"    schon freigeschaltet: {pth.name}\n")
        return True
    if not aendern:
        print(f"    waere freizuschalten: {pth.name} (nur geprueft)\n")
        return False
    pth.write_text(s.replace("#import site", "import site"), encoding="utf-8")
    print(f"    freigeschaltet in {pth.name}\n")
    return True


def s3_pip(aendern: bool, hole_paket) -> bool:
    print("Schritt 3 von 8: pip")
    if lauf([sys.executable, "-m", "pip", "--version"], 120).returncode == 0:
        print("    pip laeuft schon in diesem Python.\n")
        return True
    if not aendern:
        print("    pip fehlt (nur geprueft).\n")
        return False
    getpip = PAKET / "get-pip.py"
    if not getpip.is_file():
        hole_paket.laden(hole_paket.GETPIP, getpip)
    r = lauf([sys.executable, str(getpip), "--no-warn-script-location"], 900)
    gut = lauf([sys.executable, "-m", "pip", "--version"], 120)
    if gut.returncode == 0:
        print(f"    pip eingerichtet: {gut.stdout.strip()[:70]}\n")
        return True
    print("    pip NICHT eingerichtet:\n    " + (r.stderr or r.stdout)[-400:].replace("\n", "\n    ") + "\n")
    return False


def s4_modellwahl(sp, wunsch: str, aendern: bool, hole_paket) -> "str | None":
    print("Schritt 4 von 8: Sprachmodell waehlen")
    vorhanden = sorted((PAKET / "modell").glob("*.gguf")) if (PAKET / "modell").is_dir() else []
    fest = GEWAEHLT.read_text(encoding="utf-8").strip() if GEWAEHLT.is_file() else ""
    if wunsch == "keins":
        print("    kein Modell (--modell keins)\n")
        return None
    if wunsch in ("7b", "3b"):
        wahl = wunsch
        print(f"    erzwungen: {wahl}")
    elif fest and any(v.name == fest for v in vorhanden):
        print(f"    liegt schon da und ist gewaehlt: {fest}\n")
        return None
    elif sp is None:
        wahl = "3b"
        print("    Arbeitsspeicher nicht messbar — vorsichtshalber das 3B")
    elif sp[0] >= MODELL_AB_GB["7b"]:
        wahl = "7b"
        print(f"    {sp[0]:.1f} GB Arbeitsspeicher, ab {MODELL_AB_GB['7b']:.0f} GB: das 7B (Qwen2.5-7B-Instruct, 4,7 GB)")
    else:
        wahl = "3b"
        print(f"    {sp[0]:.1f} GB Arbeitsspeicher, unter {MODELL_AB_GB['7b']:.0f} GB: das 3B (Qwen2.5-3B-Instruct, 1,9 GB)")
        if sp[0] < MODELL_AB_GB["3b"]:
            print(f"    ACHTUNG: unter {MODELL_AB_GB['3b']:.0f} GB — auch das 3B wird im Betrieb knapp.")
    datei = hole_paket.MODELLE[wahl][0].rsplit("/", 1)[-1]
    if aendern:
        GEWAEHLT.parent.mkdir(parents=True, exist_ok=True)
        GEWAEHLT.write_text(datei + "\n", encoding="utf-8")
        print(f"    eingetragen in paket\\modell\\GEWAEHLT.txt: {datei}\n")
    else:
        print(f"    wuerde eingetragen: {datei} (nur geprueft)\n")
    return wahl


def s5_hole_paket(wahl: "str | None", llama_art: str, aendern: bool) -> bool:
    print("Schritt 5 von 8: hole_paket.py (Raeder, llama.cpp, Firmware, Treiber, Modell)")
    if not aendern:
        print("    uebersprungen (nur geprueft)\n")
        return True
    befehl = [sys.executable, str(WURZEL / "hole_paket.py"), "--modell", wahl or "keins", "--llama", llama_art]
    print("    " + " ".join(befehl[1:]))
    rc = lauf_sichtbar(befehl)
    print(f"    hole_paket.py: Rueckgabe {rc}" + ("" if rc == 0 else " — siehe fuellen_protokoll.txt") + "\n")
    return rc == 0


def infs(ordner: pathlib.Path) -> list:
    """Alle .inf unterhalb — unabhaengig von der Schreibweise (WCH liefert CH341SER.INF; Linux unterscheidet Gross/Klein)."""
    return sorted(p for p in ordner.rglob("*") if p.is_file() and p.suffix.lower() == ".inf") if ordner.is_dir() else []


def s6_kurs_python(aendern: bool) -> bool:
    """Das Kurs-Python in paket\\python_vorlage vervollstaendigen: setuptools, wheel, dann esptool aus dem
    Quellarchiv zu einem Rad bauen, dann pyserial, mpremote, esptool einrichten.

    Gemessen 11.11.2026 auf Windows 11: `pip install esptool` aus dem .tar.gz scheitert im eingebetteten Python
    mit "Cannot import build backend 'setuptools.build_meta'", obwohl das setuptools-Rad daneben liegt —
    pip baut in einer abgeschirmten Umgebung ueber PYTHONPATH, und ein Python mit ._pth ignoriert PYTHONPATH.
    Darum hier: setuptools in das Python selbst, Bau ohne Abschirmung (--no-build-isolation), und das fertige
    Rad nach paket\\pakete — die Einrichtung in START.bat findet dann ein Rad und baut nichts mehr. Dass die
    drei Pakete danach schon im Kurs-Python liegen, entspricht der Vorlage vom 16.10.2026 (vollstaendiges
    Kurs-Python, erster Start kopiert nur)."""
    print("Schritt 6 von 8: Kurs-Python vervollstaendigen (setuptools, wheel, esptool als Rad, pyserial, mpremote)")
    vorlage = PAKET / "python_vorlage"
    pakete = PAKET / "pakete"
    if pathlib.Path(sys.executable).resolve().parent != vorlage.resolve():
        print("    uebersprungen: laeuft nicht mit dem Kurs-Python aus paket\\python_vorlage (Pruefung auf einem anderen System)\n")
        return True
    if not aendern:
        print("    uebersprungen (nur geprueft)\n")
        return True
    pip = [sys.executable, "-m", "pip", "--disable-pip-version-check"]
    einbau = ["install", "--no-warn-script-location", "--no-index", "--find-links", str(pakete)]
    r = lauf(pip + einbau + ["setuptools", "wheel"], 600)
    print("    setuptools, wheel: " + ("eingerichtet" if r.returncode == 0 else "NICHT eingerichtet: " + (r.stderr or r.stdout)[-300:].strip()))
    if r.returncode != 0:
        print()
        return False
    raeder = sorted(pakete.glob("esptool-*.whl"))
    quellen = sorted(p for p in pakete.glob("esptool-*") if p.suffix in (".gz", ".zip"))
    if raeder:
        print(f"    esptool-Rad liegt schon da: {raeder[-1].name}")
    elif quellen:
        r = lauf(pip + ["wheel", "--no-build-isolation", "--no-deps", "--no-index", "--find-links", str(pakete),
                        "-w", str(pakete), str(quellen[-1])], 900)
        raeder = sorted(pakete.glob("esptool-*.whl"))
        print(f"    esptool aus {quellen[-1].name} gebaut: " + (raeder[-1].name if raeder else "NICHT gelungen: " + (r.stderr or r.stdout)[-300:].strip()))
        if not raeder:
            print()
            return False
    else:
        print("    kein esptool in paket\\pakete — hole_paket.py hat es nicht geholt")
        print()
        return False
    r = lauf(pip + einbau + ["pyserial", "mpremote", "esptool"], 900)
    gut = True
    for modul, paketname in (("serial", "pyserial"), ("mpremote", "mpremote"), ("esptool", "esptool")):
        v = lauf([sys.executable, "-c", f"import {modul}; print(getattr({modul}, '__version__', 'da'))"], 60)
        print(f"    {paketname}: " + (f"laeuft ({v.stdout.strip()[:30]})" if v.returncode == 0 else "FEHLT: " + (r.stderr or r.stdout)[-200:].strip()))
        gut &= v.returncode == 0
    print()
    return gut


def s7_treiber(aendern: bool) -> int:
    """Archive in paket\\treiber entpacken — einrichten.py (E5) installiert nur aus einer entpackten .inf."""
    print("Schritt 7 von 8: Treiber-Archive entpacken")
    ordner = PAKET / "treiber"
    archive = sorted(p for p in ordner.glob("*") if p.suffix.lower() == ".zip") if ordner.is_dir() else []
    if not archive:
        print("    keine Archive in paket\\treiber\n")
        return 0
    n = 0
    for a in archive:
        ziel = ordner / a.stem
        if ziel.is_dir() and infs(ziel):
            print(f"    schon entpackt: {a.name} -> {ziel.name}\\ ({len(infs(ziel))} .inf)")
            n += 1
            continue
        if not aendern:
            print(f"    waere zu entpacken: {a.name} (nur geprueft)")
            continue
        try:
            with zipfile.ZipFile(a) as z:
                z.extractall(ziel)
            print(f"    entpackt: {a.name} -> {ziel.name}\\ ({len(infs(ziel))} .inf)")
            n += 1
        except (zipfile.BadZipFile, OSError) as e:
            print(f"    {a.name}: nicht entpackbar ({str(e)[:60]})")
    print()
    return n


def s8_bestand() -> "tuple[list, list]":
    """(fehlt_pflicht, fehlt_hinweis). Pflicht: ohne das startet der Kurs nicht. Hinweis: der Kurs startet,
    die Einrichtung in START.bat sagt es noch einmal (Treiber: Windows 10/11 bringen den CH340 meist selbst mit)."""
    print("Schritt 8 von 8: Bestand")
    pakete = PAKET / "pakete"
    gguf = sorted((PAKET / "modell").glob("*.gguf")) if (PAKET / "modell").is_dir() else []
    fest = GEWAEHLT.read_text(encoding="utf-8").strip() if GEWAEHLT.is_file() else ""
    pruefung = [   # (Pflicht?, Name, da?, wo)
        (True, "Python-Vorlage", (PAKET / "python_vorlage" / "python.exe").is_file(), "paket\\python_vorlage\\python.exe"),
        (False, "get-pip.py", (PAKET / "get-pip.py").is_file(), "paket\\get-pip.py"),
        (True, "pip-Rad", bool(list(pakete.glob("pip-*.whl"))) if pakete.is_dir() else False, "paket\\pakete\\pip-*.whl"),
        (True, "mpremote-Rad", bool(list(pakete.glob("mpremote-*.whl"))) if pakete.is_dir() else False, "paket\\pakete\\mpremote-*.whl"),
        (True, "pyserial-Rad", bool(list(pakete.glob("pyserial-*.whl"))) if pakete.is_dir() else False, "paket\\pakete\\pyserial-*.whl"),
        (True, "esptool", bool(list(pakete.glob("esptool*"))) if pakete.is_dir() else False, "paket\\pakete\\esptool*"),
        (False, "esptool-Rad (vorgebaut)", bool(list(pakete.glob("esptool-*.whl"))) if pakete.is_dir() else False, "paket\\pakete\\esptool-*.whl"),
        (True, "setuptools-Rad", bool(list(pakete.glob("setuptools-*.whl"))) if pakete.is_dir() else False, "paket\\pakete\\setuptools-*.whl"),
        (True, "tkinter-Archiv", bool(list(PAKET.glob("tkinter-*.zip"))), "paket\\tkinter-*.zip"),
        (True, "MicroPython-Firmware", bool(list((PAKET / "firmware").glob("*.bin"))) if (PAKET / "firmware").is_dir() else False,
         "paket\\firmware\\*.bin"),
        (True, "llama-server", (PAKET / "llama" / "llama-server.exe").is_file(), "paket\\llama\\llama-server.exe"),
        (False, "CH340-Treiber (.inf)", bool(infs(PAKET / "treiber")), "paket\\treiber\\**\\*.inf"),
        (True, "Sprachmodell", bool(gguf), "paket\\modell\\*.gguf"),
        (True, "GEWAEHLT.txt zeigt auf ein vorhandenes Modell", bool(fest) and any(g.name == fest for g in gguf),
         f"paket\\modell\\GEWAEHLT.txt = {fest or '(leer)'}"),
        (True, "START.bat", (WURZEL / "START.bat").is_file(), "START.bat"),
        (True, "Seite", (WURZEL / "Frage.html").is_file(), "Frage.html"),
        (True, "Einrichtung", (WURZEL / "agent" / "einrichten.py").is_file(), "agent\\einrichten.py"),
    ]
    fehlt, hinweis = [], []
    for pflicht, name, da, wo in pruefung:
        print(f"    {'DA     ' if da else ('FEHLT  ' if pflicht else 'HINWEIS')} {name:<44} {wo}")
        if not da:
            (fehlt if pflicht else hinweis).append(name)
    for g in gguf:
        print(f"            Modell: {g.name} ({g.stat().st_size / 1e9:.2f} GB)")
    gesamt = sum(p.stat().st_size for p in PAKET.rglob("*") if p.is_file()) if PAKET.is_dir() else 0
    print(f"    Paket: {gesamt / 1e9:.2f} GB")
    print()
    return fehlt, hinweis


# ---------------------------------------------------------------- Hauptlauf
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modell", default="passend", choices=["passend", "7b", "3b", "keins"],
                   help="passend (Vorgabe): nach dem Arbeitsspeicher; sonst erzwingen")
    p.add_argument("--llama", default="vulkan", choices=["vulkan", "cpu"],
                   help="Bauart von llama.cpp (Vorgabe vulkan — die Bauart, mit der der Kurs gemessen wurde; sie laeuft auch ohne Grafikkarte)")
    p.add_argument("--nur-pruefen", action="store_true", help="nur Bericht und Bestand, nichts aendern, nichts holen")
    a = p.parse_args()
    aendern = not a.nur_pruefen

    sys.path.insert(0, str(WURZEL))
    try:
        import hole_paket                                 # das vorhandene Werkzeug, nicht noch einmal gebaut
    except ImportError as e:
        print(f"hole_paket.py fehlt neben alles_gut.py: {e}")
        return 2

    sp = s1_bericht()
    gut = True
    gut &= s2_import_site(aendern)
    gut &= s3_pip(aendern, hole_paket)
    if not gut and aendern:
        print("Ohne pip kann hole_paket.py die Windows-Raeder nicht aufloesen — Abbruch an dieser Stelle.")
        return 1
    wahl = s4_modellwahl(sp, a.modell, aendern, hole_paket)
    holen_gut = s5_hole_paket(wahl, a.llama, aendern)
    python_gut = s6_kurs_python(aendern)
    s7_treiber(aendern)
    fehlt, hinweis = s8_bestand()
    if not python_gut:
        fehlt.append("Kurs-Python vollstaendig (Schritt 6)")
    if hinweis:
        print("HINWEIS (der Kurs startet trotzdem; die Einrichtung in START.bat sagt es noch einmal): " + ", ".join(hinweis))
    if not holen_gut:
        print("HINWEIS: hole_paket.py meldete einen nicht gelungenen Schritt — siehe fuellen_protokoll.txt"
              + (" (der Bestand ist dennoch vollstaendig)." if not fehlt else "."))
    if fehlt:
        print("FEHLT: " + ", ".join(fehlt))
        print("Erneut starten holt genau das nach. Bleibt es dabei, diese Datei weitergeben: " + str(WURZEL / "alles_gut_protokoll.txt"))
        return 1
    print("ALLES DA — START.bat kann den Kurs starten." if aendern else "ALLES DA (nur geprueft).")
    return 0


if __name__ == "__main__":
    for strom in (sys.stdout, sys.stderr):          # die Startdatei stellt die Konsole auf UTF-8 (chcp 65001)
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                            # noqa: BLE001
            pass
    mit = Mitschrift(WURZEL / "alles_gut_protokoll.txt")
    sys.stdout = mit
    sys.stderr = mit
    print(f"==== alles_gut.py {FASSUNG}, {datetime.datetime.now():%d.%m.%Y %H:%M:%S} ====")
    print(f"  Aufruf: {' '.join(sys.argv)}\n")
    try:
        rueck = main()
    except BaseException:
        import traceback
        print("\n---- alles_gut.py ist nicht durchgelaufen ----")
        traceback.print_exc()
        print("\n  Diese Datei weitergeben: " + str(WURZEL / "alles_gut_protokoll.txt"))
        mit.flush()
        raise SystemExit(1)
    print(f"\n==== fertig, Rueckgabe {rueck} ====")
    mit.flush()
    raise SystemExit(rueck)
