#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fuellt den Ordner paket\\ — einmal vor dem Kurs, danach laeuft alles ohne Netz.

Aufruf:

    python hole_paket.py            alles ausser dem Modell, und das kleine Modell dazu
    python hole_paket.py --modell 7b   stattdessen das grosse Modell
    python hole_paket.py --was llama   nur einen Teil

Was hier hineinkommt, wird spaeter nur noch gelesen. Der Agent selbst laedt im Kurs
nichts mehr; das ist der Unterschied zwischen einer Vorfuehrung, die vom WLAN des
Hoersaals abhaengt, und einer, die laeuft.

Die Python-Raeder (.whl) werden ueber die Schnittstelle von PyPI geholt, nicht mit pip:
so braucht der Rechner, der das Paket schnuert, selbst kein eingerichtetes pip, und die
Raeder sind die fuer **Windows**, auch wenn geschnuert wird auf einem anderen System.
"""
from __future__ import annotations
import json, re, sys, zipfile, io, urllib.request, pathlib, argparse

WURZEL = pathlib.Path(__file__).resolve().parent
PAKET  = WURZEL / "paket"
KOPF   = {"User-Agent": "Mozilla/5.0"}

# ---------------------------------------------------------------- der Vorrat
#  Anweisung vom 04.10.2026: "Wenn es keinen Download gibt, soll auf bereits herunter-
#  geladene Dateien zurueckgegriffen werden - das gilt fuer alle benoetigten Dateien!"
#
#  Was einmal auf diesem Rechner liegt - in einem zweiten Paket nebenan, auf einem Stick,
#  im Download-Ordner -, wird nie wieder aus dem Netz geholt. Gesucht wird VOR jedem
#  Download, nicht erst, wenn er scheitert: Das ist schneller, schont die Leitung und
#  macht das Fuellen auch ohne Netz moeglich, sobald irgendwo ein volles Paket liegt.
#
#  Wo gesucht wird, in dieser Reihenfolge:
#    1. was mit --vorrat genannt wurde, und was in KURS_AGENT_VORRAT steht (durch ; getrennt)
#    2. Pakete nebenan: <Elternordner>\*\paket  (z. B. C:\Kurs_Agent_alt neben C:\Kurs_Agent)
#    3. jedes Laufwerk: X:\Kurs_Agent\paket  (der Stick, von dem kopiert wurde)
#    4. C:\Projekte\Kurs_Agent\paket  (ein Vorratsordner des Dozenten)
#    5. Downloads und Desktop des Benutzers (eine von Hand geholte Datei zaehlt auch)
#  Gefunden wird ueber den Dateinamen, direkt im Ort oder einen Ordner tiefer (modell\,
#  firmware\ ...). Was gefunden wurde, steht im Protokoll mit vollem Pfad - damit niemand
#  raten muss, woher eine Datei stammt.
VORRAT_ORTE: list = []            # aus --vorrat, gefuellt in main()


def vorrat_orte() -> list:
    import os
    orte = list(VORRAT_ORTE)
    for p in (os.environ.get("KURS_AGENT_VORRAT") or "").split(os.pathsep):
        if p.strip():
            orte.append(pathlib.Path(p.strip()))
    try:
        orte += [p for p in WURZEL.parent.glob("*/paket") if p.is_dir()]
    except OSError:
        pass
    if os.name == "nt":
        for b in "DEFGHIJKLMNOPQRSTUVWXYZC":
            orte.append(pathlib.Path(f"{b}:/Kurs_Agent/paket"))
        orte.append(pathlib.Path("C:/Projekte/Kurs_Agent/paket"))
    home = pathlib.Path.home()
    orte += [home / "Downloads", home / "Desktop"]
    eigen = PAKET.resolve()
    fertig, gesehen = [], set()
    for o in orte:
        try:
            if not o.is_dir():
                continue
            r = o.resolve()
        except OSError:
            continue
        if r == eigen or r in gesehen:
            continue
        gesehen.add(r)
        fertig.append(o)
    return fertig


def vorrat_suchen(name: str):
    """Die erste Datei dieses Namens in einem der Vorratsorte - oder None."""
    for ort in vorrat_orte():
        try:
            kandidaten = [ort / name] + list(ort.glob(f"*/{name}"))
        except OSError:
            continue
        for k in kandidaten:
            try:
                if k.is_file() and k.stat().st_size > 0 and not k.name.endswith(".teil"):
                    return k
            except OSError:
                continue
    return None


def vorrat_kopieren(von: pathlib.Path, nach: pathlib.Path) -> pathlib.Path:
    """Kopiert aus dem Vorrat - mit Fortschritt, und wie beim Laden erst unter Hilfsnamen."""
    nach.parent.mkdir(parents=True, exist_ok=True)
    print(f"    aus Vorrat: {von}")
    groesse, getan = von.stat().st_size, 0
    teil = nach.with_name(nach.name + ".teil")
    with von.open("rb") as q, teil.open("wb") as z:
        while True:
            happen = q.read(8 << 20)
            if not happen:
                break
            z.write(happen); getan += len(happen)
            if groesse > 50_000_000:
                print(f"\r    kopiert {nach.name} … {100*getan/groesse:5.1f} %", end="", flush=True)
    teil.replace(nach)
    print(f"\r    {nach.name}: {groesse/1e6:.1f} MB (aus Vorrat)            ")
    return nach


_NETZ = None


def netz_da() -> bool:
    """Einmal je Lauf: Ist ueberhaupt ein Netz da? Ohne Netz wird kein Download versucht -
    sonst stuende man je Datei drei Anlaeufe lang vor einer Zeitueberschreitung."""
    global _NETZ
    if _NETZ is None:
        import socket
        _NETZ = False
        for host in ("huggingface.co", "www.python.org", "pypi.org"):
            try:
                socket.create_connection((host, 443), timeout=5).close()
                _NETZ = True
                break
            except OSError:
                continue
        if not _NETZ:
            print("    KEIN NETZ erreichbar - genommen wird nur, was im Vorrat liegt.")
    return _NETZ

PYTHON_ZIP = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
GETPIP     = "https://bootstrap.pypa.io/get-pip.py"
FIRMWARE   = "https://micropython.org/resources/firmware/ESP32_GENERIC-20260824-v1.29.0.bin"
LLAMA_REPO = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=12"

# USB-Seriell-Treiber. Der ESP32 haengt ueber einen solchen Wandler am Rechner; erkennt
# Windows ihn nicht, findet auch der Agent nichts — und im Kursraum ohne Netz ist dann
# Schluss. Geholt wird ausschliesslich beim Hersteller: ein Treiber laeuft im Kern des
# Betriebssystems, eine Zwischenquelle kommt dafuer nicht in Frage.
TREIBER = [
  ("CH341SER.ZIP", "https://www.wch-ic.com/download/file?id=5",
   "CH340/CH341 — der haeufigste Wandler auf guenstigen ESP32-Brettern",
   "https://www.wch-ic.com/downloads/CH341SER_ZIP.html"),
  ("CH343SER.ZIP", "https://www.wch-ic.com/download/file?id=330",
   "CH342/CH343/CH344/CH347/CH9102 — neuere WCH-Wandler",
   "https://www.wch-ic.com/downloads/CH343SER_ZIP.html"),
  ("CP210x_Universal_Windows_Driver.zip",
   "https://www.silabs.com/documents/public/software/CP210x_Universal_Windows_Driver.zip",
   "CP2102/CP2104 — Silicon Labs, auf vielen Entwicklungsbrettern",
   "https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers"),
]

MODELLE = {   # Name -> (Adresse, ungefaehre Groesse, wofuer)
  "1.5b": ("https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
           "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf", 0.99, "nur zum Vorfuehren der Schleife"),
  "3b":   ("https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/"
           "Qwen2.5-3B-Instruct-Q4_K_M.gguf", 1.93, "ab 8 GB Arbeitsspeicher"),
  "7b":   ("https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/"
           "Qwen2.5-7B-Instruct-Q4_K_M.gguf", 4.68, "ab 16 GB Arbeitsspeicher — Rueckfall ohne Coder"),
  #  Die Aufgabe (04.10.2026) verlangt ein Modell „speziell fuer die Python-Programmierung". Auf dem
  #  Pruefstand brauchte Coder-3B fuer Karte 1 vier Werkzeugaufrufe und lieferte die geprueffte
  #  Fassung; Instruct-3B brauchte sechzehn. Deshalb sind die Coder-Modelle die Wahl bei „passend".
  "coder-3b": ("https://huggingface.co/bartowski/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/"
               "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf", 1.93, "ab 8 GB Arbeitsspeicher — fuer Python, die Wahl"),
  "coder-7b": ("https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/"
               "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf", 4.68, "ab 16 GB Arbeitsspeicher — fuer Python, die Empfehlung"),
}

# Diese Pakete braucht der Agent auf dem Kursrechner. Alles Weitere ergibt sich daraus.
# Was der Agent auf dem Kursrechner braucht. esptool kommt getrennt, weil es nur als
# Quelltext veroeffentlicht wird; setuptools und wheel sind dafuer da, es bauen zu koennen.
BRAUCHT_RAEDER = ["mpremote", "setuptools", "wheel"]

# Pakete, die **nur unter Windows** gebraucht werden. Sie muessen hier einzeln stehen, weil
# pip die Bedingung 'platform_system == "Windows"' nach dem Rechner auswertet, auf dem es
# gerade laeuft — und nicht nach --platform. Wer das Paket auf einem Linux-Rechner schnuert,
# bekommt sie sonst nicht, und im Kurs endet die Installation mit
# "Could not find a version that satisfies the requirement colorama".
NUR_WINDOWS = ["colorama"]


def laden(url: str, ziel: pathlib.Path, name="") -> pathlib.Path:
    """Holt eine Datei — und holt sie fertig.

    Geladen wird in <name>.teil; erst wenn alles da ist, bekommt die Datei ihren Namen.
    Vorher galt jede Datei mit mehr als null Byte als fertig: ein bei 60 % abgebrochenes
    Modell waere beim naechsten Lauf als "liegt schon da" durchgegangen, und im Kursraum
    waere llama.cpp mit einem Leseabbruch gestorben. Bricht die Verbindung ab, wird beim
    naechsten Anlauf an derselben Stelle weitergeladen (HTTP Range) — bei 4,7 GB ist das
    der Unterschied zwischen "geht" und "geht nie". Drei Anlaeufe mit kurzer Pause, damit
    ein Netzaussetzer von selbst ueberstanden wird (03.10.2026: der erste echte Lauf starb
    an einem einzigen Zeitueberlauf).
    """
    import time
    if ziel.exists() and ziel.stat().st_size > 0:
        print(f"    liegt schon da: {ziel.name} ({ziel.stat().st_size/1e6:.1f} MB)")
        return ziel
    #  Erst der Vorrat, dann das Netz - fuer jede Datei (Anweisung vom 04.10.2026).
    vorhanden = vorrat_suchen(ziel.name)
    if vorhanden is not None:
        return vorrat_kopieren(vorhanden, ziel)
    if not netz_da():
        raise OSError(f"kein Netz, und {ziel.name} liegt in keinem der "
                      f"{len(vorrat_orte())} Vorratsorte")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    teil = ziel.with_name(ziel.name + ".teil")
    anzeige = name or ziel.name
    fehler: Exception | None = None
    for anlauf in range(1, 4):
        try:
            schon = teil.stat().st_size if teil.exists() else 0
            kopf = dict(KOPF)
            if schon:
                kopf["Range"] = f"bytes={schon}-"
            try:
                r = urllib.request.urlopen(urllib.request.Request(url, headers=kopf), timeout=60)
            except urllib.error.HTTPError as e:
                if e.code == 416 and schon:          # der Teil ist schon vollstaendig
                    teil.replace(ziel)
                    print(f"    {ziel.name}: {ziel.stat().st_size/1e6:.1f} MB (war schon fertig)")
                    return ziel
                raise
            with r:
                if schon and r.status != 206:         # der Server kann nicht fortsetzen: von vorn
                    schon = 0
                gesamt = int(r.headers.get("Content-Length") or 0) + schon
                getan = schon
                with teil.open("ab" if schon else "wb") as f:
                    while True:
                        happen = r.read(1 << 20)
                        if not happen:
                            break
                        f.write(happen); getan += len(happen)
                        if gesamt:
                            print(f"\r    laedt {anzeige} … {100*getan/gesamt:5.1f} %"
                                  f"{'  (fortgesetzt)' if schon else ''}", end="", flush=True)
            if gesamt and teil.stat().st_size != gesamt:
                raise OSError(f"unvollstaendig: {teil.stat().st_size} von {gesamt} Byte")
            teil.replace(ziel)
            print(f"\r    {ziel.name}: {ziel.stat().st_size/1e6:.1f} MB            ")
            return ziel
        except Exception as e:
            fehler = e
            print(f"\r    {anzeige}: Anlauf {anlauf} abgebrochen ({str(e)[:70]})"
                  f" — {'weiter in 5 s' if anlauf < 3 else 'aufgegeben'}")
            if anlauf < 3:
                time.sleep(5)
    assert fehler is not None
    raise fehler


# ---------------------------------------------------------------- Python-Raeder
def raeder(ziel: pathlib.Path) -> bool:
    """Holt die Python-Pakete fuer **Windows**, auch wenn hier ein anderes System laeuft.

    Die Abhaengigkeiten loest pip auf, nicht dieses Skript. Das ist keine Bequemlichkeit,
    sondern eine Notwendigkeit: bitstring verlangt ``tibs<0.6``, und wer die Bedingungen
    ueberspringt und einfach die neueste Fassung nimmt, baut ein Paket, das erst im Kurs
    beim ersten Import auseinanderfaellt. Ein Abhaengigkeitsloeser ist ein eigenes
    Programm — und eines haben wir schon.

    Zwei Durchgaenge, weil esptool **nur als Quelltext** veroeffentlicht wird:

      a) esptool als Quelltext holen (reines Python, pip baut es spaeter ohne Uebersetzer)
      b) alles Uebrige als fertige Windows-Raeder, von pip aufgeloest

    Dass setuptools und wheel dabei sind, haengt an (a): ohne sie koennte pip das
    Quelltextpaket im Kurs nicht bauen, ohne doch wieder ins Netz zu gehen.
    """
    import subprocess
    ziel.mkdir(parents=True, exist_ok=True)
    if list(ziel.glob("*.whl")) and list(ziel.glob("esptool*")):
        print(f"    liegen schon da: {len(list(ziel.glob('*')))} Dateien in {ziel.name}")
        return True

    #  Erst der Vorrat: ein zweites Paket mit gefuelltem pakete-Ordner liefert alle Raeder
    #  auf einmal - ohne pip, ohne Netz.
    for ort in vorrat_orte():
        quelle = ort / "pakete"
        if quelle.is_dir() and list(quelle.glob("*.whl")) and list(quelle.glob("esptool*")):
            dateien = [d for d in sorted(quelle.iterdir()) if d.is_file() and not d.name.endswith(".teil")]
            print(f"    aus Vorrat: {quelle} ({len(dateien)} Dateien)")
            for d in dateien:
                vorrat_kopieren(d, ziel / d.name) if d.stat().st_size > 50_000_000 else \
                    (ziel / d.name).write_bytes(d.read_bytes())
            print(f"    {len(dateien)} Dateien in {ziel}")
            return True
    if not netz_da():
        raise OSError("kein Netz, und kein Vorrat mit einem gefuellten Ordner pakete")

    def pip(*args):
        r = subprocess.run([sys.executable, "-m", "pip", *args], capture_output=True, text=True)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")

    gut, text = pip("--version")
    if not gut:
        raise OSError("pip laeuft in diesem Python nicht - das Schnueren des Pakets braucht "
                      "ein Python mit pip; der Kursrechner spaeter nicht")

    # (a) Quelltext von esptool und seine unmittelbaren Anforderungen auslesen
    gut, text = pip("download", "--no-deps", "--no-binary", ":all:", "-d", str(ziel), "esptool")
    if not gut:
        raise OSError(f"esptool liess sich nicht holen: {text[-300:].strip()}")
    print(f"    esptool als Quelltext geholt")

    with urllib.request.urlopen(urllib.request.Request(
            "https://pypi.org/pypi/esptool/json", headers=KOPF), timeout=60) as r:
        meta = json.loads(r.read())
    # Der Name **mit** seinen Extras: esptool verlangt esp-pylib[cli,ide,serial], und wer
    # die eckige Klammer abschneidet, holt ein Drittel des Pakets. Im Kurs endet das mit
    # "Could not find a version that satisfies the requirement websockets".
    direkt = []
    for b in (meta["info"].get("requires_dist") or []):
        if "extra ==" in b:
            continue
        m = re.match(r"\s*([A-Za-z0-9._-]+(?:\[[^\]]+\])?)", b)
        if m:
            direkt.append(m.group(1))

    # (b) der Rest als Raeder fuer Windows und CPython 3.12
    gut, text = pip("download", "--platform", "win_amd64", "--python-version", "3.12",
                    "--only-binary=:all:", "-d", str(ziel),
                    *BRAUCHT_RAEDER, *NUR_WINDOWS, *direkt)
    if not gut:
        raise OSError(f"die Raeder liessen sich nicht holen: {text[-300:].strip()}")

    dateien = sorted(ziel.glob("*"))
    print(f"    {len(dateien)} Dateien, {sum(d.stat().st_size for d in dateien)/1e6:.1f} MB in {ziel}")
    return True


# ---------------------------------------------------------------- llama.cpp
#  Die Fassung, die am 02.10.2026 geprueft wurde. Sie wird genommen, wenn das Verzeichnis bei
#  GitHub nicht antwortet — am 03.10.2026 brach daran der erste echte Lauf ab: api.github.com
#  blieb vom Kursrechner aus 60 Sekunden stumm, waehrend alle anderen Quellen antworteten.
LLAMA_BEKANNT = ("b11342", "llama-b11342-bin-win-{art}-x64.zip")


def llama(ziel: pathlib.Path, art: str):
    if (ziel / "llama-server.exe").exists():
        print(f"    liegt schon da: {ziel.name}\\llama-server.exe")
        return
    #  Erst der Vorrat: ein zweites Paket mit fertigem llama-Ordner wird ganz uebernommen.
    for ort in vorrat_orte():
        quelle = ort / "llama"
        if (quelle / "llama-server.exe").is_file():
            dateien = [d for d in sorted(quelle.iterdir()) if d.is_file() and not d.name.endswith(".teil")]
            print(f"    aus Vorrat: {quelle} ({len(dateien)} Dateien)")
            ziel.mkdir(parents=True, exist_ok=True)
            for d in dateien:
                (ziel / d.name).write_bytes(d.read_bytes())
            print(f"    {len(dateien)} Dateien in {ziel}: llama-server.exe gefunden")
            return
    url = name = tag = None
    try:
        with urllib.request.urlopen(urllib.request.Request(LLAMA_REPO, headers=KOPF), timeout=20) as r:
            rel = json.loads(r.read())
        for d in rel:
            treffer = [a for a in d["assets"] if f"bin-win-{art}-x64.zip" in a["name"]]
            if treffer:
                url, name, tag = treffer[0]["browser_download_url"], treffer[0]["name"], d["tag_name"]
                break
    except Exception as e:
        print(f"    Verzeichnis bei GitHub nicht erreichbar ({str(e)[:50]}) — nehme die bekannte Fassung")
    if not url:
        tag, name = LLAMA_BEKANNT[0], LLAMA_BEKANNT[1].format(art=art)
        url = f"https://github.com/ggml-org/llama.cpp/releases/download/{tag}/{name}"
    print(f"    llama.cpp {tag}, Bauart {art}")
    archiv = laden(url, ziel.parent / name)
    ziel.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archiv) as z:
        z.extractall(ziel)
    archiv.unlink()
    exe = list(ziel.rglob("llama-server.exe"))
    # llama.cpp packt je nach Fassung in einen Unterordner — wir holen alles nach oben.
    for p in (exe[0].parent.iterdir() if exe and exe[0].parent != ziel else []):
        p.replace(ziel / p.name)
    if not (ziel / "llama-server.exe").exists():
        raise FileNotFoundError(f"llama-server.exe fehlt nach dem Entpacken in {ziel}")
    print(f"    entpackt nach {ziel}: llama-server.exe gefunden")


def treiber(ziel: pathlib.Path):
    """Holt die USB-Seriell-Treiber — und sagt klar, wenn einer nicht zu bekommen ist.

    Dass hier etwas fehlschlagen kann, ist eingeplant: Silicon Labs liefert nur an
    Browser aus und sperrt manche Netze ganz. Ein fehlender Treiber ist kein Grund,
    den Rest des Pakets nicht zu bauen — aber er muss **im Klartext** gemeldet werden,
    sonst merkt es jemand erst im Kursraum.
    """
    ziel.mkdir(parents=True, exist_ok=True)
    import hashlib
    zeilen, fehlt = [], []
    for name, url, wofuer, seite in TREIBER:
        d = ziel / name
        vorhanden = None if (d.exists() and d.stat().st_size > 0) else vorrat_suchen(name)
        if d.exists() and d.stat().st_size > 0:
            print(f"    liegt schon da: {name}")
        elif vorhanden is not None:
            vorrat_kopieren(vorhanden, d)
        elif not netz_da():
            print(f"    {name}: kein Netz und nicht im Vorrat")
            fehlt.append((name, wofuer, seite))
            continue
        else:
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=KOPF), timeout=120) as r:
                    daten = r.read()
                if daten[:2] not in (b"PK", b"MZ"):
                    raise ValueError(f"die Antwort ist weder Archiv noch Programm "
                                     f"(beginnt mit {daten[:4]!r}) — vermutlich eine Fehlerseite")
                d.write_bytes(daten)
                print(f"    {name}: {len(daten)/1e6:.2f} MB")
            except Exception as e:
                print(f"    {name}: nicht zu holen ({str(e)[:70]})")
                fehlt.append((name, wofuer, seite))
                continue
        zeilen.append(f"| `{name}` | {wofuer} | {d.stat().st_size/1e6:.2f} MB | "
                      f"`{hashlib.sha256(d.read_bytes()).hexdigest()[:32]}…` |")

    (ziel / "LIESMICH.md").write_text(
        "# USB-Seriell-Treiber\n\n"
        "Nur noetig, wenn Windows den ESP32 nicht von selbst erkennt. Windows 10 und 11 "
        "bringen die gaengigen Wandler meist mit — im Kursraum ohne Netz sollte man sich "
        "darauf aber nicht verlassen.\n\n"
        "**Ein Treiber ist das Einzige an diesem Kurs, das eine echte Installation mit "
        "Adminrechten braucht.** Deshalb steht er bewusst ausserhalb des Agenten: der Agent "
        "installiert ihn nicht, ein Mensch entscheidet das.\n\n"
        "Alle Dateien stammen unmittelbar von der Herstellerseite ueber HTTPS. Eine "
        "Zwischenquelle kommt nicht in Frage: ein Treiber laeuft im Kern des Betriebssystems.\n\n"
        "## Installieren\n\n"
        "Nur wenn noetig, und nur von einem Menschen:\n\n"
        "1. Archiv entpacken\n"
        "2. `SETUP.EXE` (WCH) beziehungsweise `CP210xVCPInstaller_x64.exe` (Silicon Labs) "
        "starten — fragt nach Adminrechten\n"
        "3. ESP32 neu einstecken, dann `ports_zeigen` erneut aufrufen\n\n"
        "Nur Archive liegen hier, keine fertigen Programme: ein `.exe` auf einem Stick "
        "laesst Virenscanner anschlagen, und das Installationsprogramm steckt ohnehin im "
        "Archiv.\n\n"
        "| Datei | wofuer | Groesse | SHA-256 (Anfang) |\n|---|---|---|---|\n"
        + "\n".join(zeilen) + "\n\n"
        + ("" if not fehlt else
           "## Fehlt noch\n\n" + "\n".join(
             f"* **{n}** — {w}  \n  Selbst holen bei: {s}" for n, w, s in fehlt)
           + "\n\nDanach die Datei in diesen Ordner legen.\n"),
        encoding="utf-8")

    if fehlt:
        print(f"    ACHTUNG: {len(fehlt)} Treiber fehlt/fehlen — siehe {ziel / 'LIESMICH.md'}")
    return not fehlt


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modell", default="passend", choices=[*MODELLE, "passend", "alle", "keins"],
                   help="welche Sprachmodelle mitgeliefert werden. Vorgabe 'passend': 3b und 7b "
                        "zusammen (6,6 GB) — dann startet derselbe Stick auf einem Rechner mit "
                        "8 GB ebenso wie auf einem mit 32 GB, denn gewaehlt wird erst beim Start")
    p.add_argument("--llama", default="vulkan", choices=["vulkan", "cpu"],
                   help="vulkan laeuft auf AMD, Intel und NVIDIA; cpu ueberall (Vorgabe vulkan)")
    p.add_argument("--was", default="alles",
                   choices=["alles", "python", "raeder", "llama", "modell", "firmware", "treiber"])
    p.add_argument("--vorrat", action="append", default=[], metavar="ORDNER",
                   help="Ordner, in dem schon geholte Dateien liegen (mehrfach moeglich). "
                        "Gesucht wird ausserdem von selbst in Paketen nebenan, auf allen "
                        "Laufwerken unter \\Kurs_Agent\\paket und im Download-Ordner.")
    a = p.parse_args()
    VORRAT_ORTE.extend(pathlib.Path(v) for v in a.vorrat)
    PAKET.mkdir(parents=True, exist_ok=True)
    orte = vorrat_orte()
    print(f"Vorrat: {len(orte)} Ort{'e' if len(orte) != 1 else ''} werden vor jedem Download durchsucht"
          + (" - " + "; ".join(str(o) for o in orte[:4]) + (" ..." if len(orte) > 4 else "") if orte else ""))
    print()
    tu = lambda n: a.was in ("alles", n)

    #  Jeder Schritt steht fuer sich. Scheitert einer, geht es mit dem naechsten weiter,
    #  und am Ende steht, was fehlt. Vorher riss der erste Fehler die ganze Kette ab —
    #  und alles, was danach gekommen waere, blieb ungeholt, obwohl es erreichbar war.
    #  Die Schritte heissen "Schritt n von 6", nicht "[n]": In eckigen Klammern stehen in
    #  START.bat die Menuepunkte, und am 03.10.2026 wurde gefragt, "was soll ich als 2
    #  druecken" — die Anzeige sah aus wie eine Frage.
    fehlgeschlagen = []

    def schritt(nr, titel, tun):
        print(f"Schritt {nr} von 6: {titel}")
        try:
            tun()
        except Exception as e:
            fehlgeschlagen.append((titel, f"{type(e).__name__}: {str(e)[:110]}"))
            print(f"    NICHT GELUNGEN — {type(e).__name__}: {str(e)[:110]}")
            print("    Es geht mit dem naechsten Schritt weiter; dieser wird beim naechsten Start nachgeholt.")
        print()

    def s_python():
        archiv = laden(PYTHON_ZIP, PAKET / PYTHON_ZIP.rsplit("/", 1)[-1])
        laden(GETPIP, PAKET / "get-pip.py")
        # Das Python wird hier **schon ausgepackt** abgelegt, nicht erst auf dem
        # Kursrechner. Grund: zum Auspacken braeuchte es dort PowerShell (Expand-Archive)
        # oder tar — das erste ist in manchen Firmennetzen gesperrt, das zweite gibt es
        # erst ab Windows 10 1803. Kopieren kann dagegen jedes Windows. Die 14 MB mehr auf
        # dem Stick sind der Preis dafuer, dass dieser Schritt nicht scheitern kann.
        vorlage = PAKET / "python_vorlage"
        if vorlage.is_dir() and (vorlage / "python.exe").exists():
            print(f"    liegt schon ausgepackt: {vorlage}")
            return
        vorlage.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archiv) as z:
            z.extractall(vorlage)
        pth = next(iter(sorted(vorlage.glob("python3*._pth"))), None)
        if pth:
            s = pth.read_text(encoding="utf-8")
            if "#import site" in s:
                pth.write_text(s.replace("#import site", "import site"), encoding="utf-8")
        n = sum(1 for _ in vorlage.rglob("*"))
        print(f"    ausgepackt nach {vorlage}: {n} Dateien, 'import site' freigeschaltet")

    def s_modelle():
        wahl = (["coder-3b", "coder-7b"] if a.modell == "passend"
                else list(MODELLE) if a.modell == "alle" else [a.modell])
        gesamt = sum(MODELLE[n][1] for n in wahl)
        print(f"    {', '.join(wahl)} — zusammen {gesamt:.2f} GB")
        if len(wahl) > 1:
            print("    Welches davon benutzt wird, entscheidet sich erst beim Start, auf dem")
            print("    Rechner, auf dem es laeuft — nach dem freien Arbeitsspeicher. Darum")
            print("    kommen beide mit: derselbe Stick soll auf jedem Kursrechner starten.")
        offen = []
        for n in wahl:
            url, gb, wofuer = MODELLE[n]
            print(f"    {n}: {gb:.2f} GB — {wofuer}")
            try:
                laden(url, PAKET / "modell" / url.rsplit("/", 1)[-1])
            except Exception as e:                 # das zweite Modell trotzdem versuchen
                offen.append(f"{n}: {str(e)[:60]}")
        if offen:
            raise OSError("; ".join(offen))

    if tu("python"):   schritt(1, "Python und pip", s_python)
    if tu("raeder"):   schritt(2, "Python-Raeder fuer Windows (esptool, mpremote und was dazugehoert)",
                               lambda: raeder(PAKET / "pakete"))
    if tu("firmware"): schritt(3, "MicroPython fuer den ESP32",
                               lambda: laden(FIRMWARE, PAKET / "firmware" / FIRMWARE.rsplit("/", 1)[-1]))
    if tu("llama"):    schritt(4, "llama.cpp", lambda: llama(PAKET / "llama", a.llama))
    if tu("treiber"):  schritt(5, "USB-Seriell-Treiber", lambda: treiber(PAKET / "treiber"))
    if tu("modell") and a.modell != "keins":
        schritt(6, "Sprachmodelle", s_modelle)

    print("Stand des Pakets:")
    gesamt = 0
    for d in sorted(PAKET.rglob("*")):
        if d.is_file():
            gesamt += d.stat().st_size
    print(f"  {sum(1 for _ in PAKET.rglob('*') if _.is_file())} Dateien, {gesamt/1e9:.2f} GB in {PAKET}")
    sys.path.insert(0, str(WURZEL / "agent"))
    import pfade
    print(pfade.bericht())
    if fehlgeschlagen:
        print("\nNICHT GELUNGEN in diesem Lauf:")
        for titel, grund in fehlgeschlagen:
            print(f"  - {titel}: {grund}")
        print("  START.bat erneut starten holt genau das nach. Vorhandenes wird nicht noch einmal geladen.")
        return 1
    return 0


class Mitschrift:
    """Alles, was hier ausgegeben wird, steht zugleich in fuellen_protokoll.txt.

    Anlass: Am 03.10.2026 brach das Fuellen auf dem Kursrechner nach drei Sekunden ab.
    Die Meldung stand im Fenster -- und das Fenster war zu, als nachgesehen werden
    sollte. Ein Vorgang, der nur auf den Bildschirm spricht, ist aus der Ferne nicht zu
    beurteilen; und wer danebensteht, soll nichts abschreiben muessen.

    Die Datei liegt neben dem Paket und wird bei jedem Lauf neu angelegt. Schlaegt das
    Schreiben fehl (schreibgeschuetzter Stick), laeuft alles unveraendert weiter -- die
    Mitschrift ist eine Hilfe, kein Erfordernis.
    """

    def __init__(self, pfad: pathlib.Path):
        self.schirm = sys.stdout
        try:
            self.datei = pfad.open("w", encoding="utf-8", errors="replace")
        except OSError:
            self.datei = None

    def write(self, s):
        self.schirm.write(s)
        if self.datei:
            #  Die Fortschrittszeile schreibt sich mit \r immer wieder selbst neu. Auf dem
            #  Bildschirm ist das richtig, in der Datei gaebe es eine einzige lange Zeile.
            self.datei.write(s.replace("\r", "\n"))
            self.datei.flush()
        return len(s)

    def flush(self):
        self.schirm.flush()
        if self.datei:
            self.datei.flush()


if __name__ == "__main__":
    mit = Mitschrift(WURZEL / "fuellen_protokoll.txt")
    sys.stdout = mit
    sys.stderr = mit
    import datetime
    print(f"==== Paket fuellen, {datetime.datetime.now():%d.%m.%Y %H:%M:%S} ====")
    print(f"  Python:  {sys.version}")
    print(f"  Laeuft als: {sys.executable}")
    print(f"  Wurzel:  {WURZEL}")
    print(f"  Aufruf:  {' '.join(sys.argv)}")
    print()
    try:
        rueck = main()
    except BaseException:
        #  Auch Abbruch mit Strg+C und SystemExit werden vermerkt: Sonst steht am Ende
        #  "abgebrochen" im Startskript und niemand weiss, ob es der Benutzer war.
        import traceback
        print("\n---- Das Fuellen ist nicht durchgelaufen ----")
        traceback.print_exc()
        print("\n  Diese Datei weitergeben: " + str(WURZEL / "fuellen_protokoll.txt"))
        mit.flush()
        raise SystemExit(1)
    print("\n==== fertig ====")
    mit.flush()
    raise SystemExit(rueck)
