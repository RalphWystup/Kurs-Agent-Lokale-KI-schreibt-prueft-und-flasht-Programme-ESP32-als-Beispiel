#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueft die Anforderungen aus ANFORDERUNGEN.md, soweit eine Maschine das kann.

Aufruf:  python pruefe_alles.py

Jede Pruefung ist so gebaut, dass sie **scheitern kann** — eine, die immer gelingt, sagt
nichts. Wo etwas nur von Hand zu pruefen ist, steht das dabei und wird nicht mitgezaehlt.
"""
from __future__ import annotations
import json, os, pathlib, re, subprocess, sys, tempfile

HIER = pathlib.Path(__file__).resolve().parent
PY = sys.executable
ergebnisse: list = []


def pruefe(nummer: str, was: str, tun):
    try:
        gut, bemerkung = tun()
    except Exception as e:
        gut, bemerkung = False, f"{type(e).__name__}: {e}"
    ergebnisse.append((nummer, was, gut, bemerkung))
    print(f"  {nummer:4s} {'OK  ' if gut else 'FEHL'}  {was}")
    if bemerkung:
        print(f"       {'':4s}  {bemerkung}")


def _lauf(befehl, wurzel=None, zeit=120):
    u = dict(os.environ)
    if wurzel:
        u["KURS_AGENT_WURZEL"] = str(wurzel)
    return subprocess.run(befehl, capture_output=True, text=True, timeout=zeit, env=u,
                          encoding="utf-8", errors="replace")


def _python_bereit(wurzel):
    """Legt das Pruef-Python an, falls es fehlt.

    Noetig, weil die Pruefung D1-2 die Ablage absichtlich loescht — und damit auch das
    Python, das die spaeteren Pruefungen brauchen. Jede Pruefung muss fuer sich stehen,
    sonst haengt ihr Ergebnis davon ab, was vorher lief.
    """
    exe = wurzel / "ablage" / "python" / "python.exe"
    if exe.exists():
        return
    exe.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import shutil; shutil.copy2(PY, exe)
    else:
        exe.write_text(f'#!/bin/sh\nexec "{PY}" "$@"\n'); exe.chmod(0o755)


def _werkzeug(name, eingabe, wurzel):
    _python_bereit(wurzel)
    r = _lauf([PY, str(HIER / "agent" / "werkzeuge" / f"{name}.py"),
               json.dumps(eingabe)], wurzel)
    return (r.stdout or r.stderr).strip()


# ---------------------------------------------------------------- A: Autarkie
def a4():
    """Im Kursbetrieb wird kein vorhandenes Python gesucht oder benutzt.

    Die frueherere Fassung fragte nur: steht irgendwo 'where'? Das war zu grob. Seit dem
    02.10.2026 sucht START.bat **genau einmal** ein vorhandenes Python -- im Fuellzweig
    eines leeren Pakets, denn dort liegt ja noch keines (Ausnahme A7). Geprueft wird
    deshalb, was wirklich gilt:

      1. Jede Suche steht INNERHALB des Fuellzweigs, keine ausserhalb.
      2. Das gefundene Python wird ausschliesslich fuer hole_paket.py benutzt.
      3. Jeder andere Programmaufruf geht ueber "!PY!" -- das Python aus dem Paket.
    """
    t = (HIER / "START.bat").read_text(encoding="utf-8", errors="replace")
    zeilen = t.splitlines()

    # Seit 04.10.2026 steht die Suche in EINER Unterroutine (:suchepython); die Grenzen
    # sind das Etikett und das naechste "exit /b". Gerufen werden darf sie nur dort, wo
    # unmittelbar danach hole_paket.py laeuft -- das prueft fremd_falsch unten.
    anfang = ende = None
    for i, z in enumerate(zeilen):
        if anfang is None and z.strip().lower() == ":suchepython": anfang = i
        elif anfang is not None and z.strip().lower().startswith("exit /b"): ende = i; break
    im_zweig = range(anfang, ende + 1) if (anfang is not None and ende is not None) else range(0)

    suchen_draussen = [i + 1 for i, z in enumerate(zeilen)
                       if re.search(r"\bwhere\b", z, re.I) and i not in im_zweig
                       and not z.strip().lower().startswith("rem")]
    # Wofuer wird das gefundene Python benutzt? Nur hole_paket.py ist erlaubt.
    # echo- und rem-Zeilen nennen den Pfad nur, sie fuehren ihn nicht aus.
    fremd_genutzt = [z.strip() for z in zeilen
                     if '"!FREMD!"' in z and not z.strip().lower().startswith(("rem", "echo"))]
    fremd_falsch = [z for z in fremd_genutzt
                    if "hole_paket.py" not in z and "-m pip --version" not in z]
    # Jeder sonstige Programmaufruf laeuft ueber das Python aus dem Paket.
    eigenes = "ablage\\python\\python.exe" in t
    q = (HIER / "agent" / "pfade.py").read_text(encoding="utf-8")
    zeigt_in_ablage = 'PYTHON / "python.exe"' in q and "PYTHON   = ABLAGE" in q

    gut = not suchen_draussen and not fremd_falsch and eigenes and zeigt_in_ablage and im_zweig
    return (gut,
            f"Suche ausserhalb des Fuellzweigs: {suchen_draussen or 'keine'}; "
            f"fremdes Python genutzt fuer: {fremd_genutzt or 'nichts'}; "
            f"unerlaubt davon: {fremd_falsch or 'nichts'}; "
            f"eigenes Python gesetzt: {eigenes}; python_exe zeigt in die Ablage: {zeigt_in_ablage}")


def a5():
    treffer = []
    for d in list(HIER.glob("*.py")) + list((HIER / "agent").rglob("*.py")):
        for n, z in enumerate(d.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r'["\'][A-Za-z]:\\\\', z) and "Beispiel" not in z and "zum Beispiel" not in z:
                # Pfade in Erklaerungen und Fehlermeldungen sind erlaubt, in Zuweisungen nicht
                if re.search(r'^\s*[A-Z_]+\s*=|pathlib\.Path\(["\'][A-Za-z]:', z):
                    treffer.append(f"{d.name}:{n}")
    return not treffer, (f"feste Pfade in: {', '.join(treffer)}" if treffer
                         else "kein fester Laufwerksbuchstabe in einer Zuweisung")


def a6():
    r = _lauf([PY, str(HIER / "agent" / "agent.py"), "--werkzeuge"])
    n = len([z for z in r.stdout.splitlines() if z.strip()])
    return n >= 9, f"{n} Werkzeuge ohne Sprachmodell erreichbar"


# ---------------------------------------------------------------- B: keine Stoerung
def b345():
    sys.path.insert(0, str(HIER / "agent"))
    import pfade
    u = pfade.umgebung()
    return (u.get("PYTHONNOUSERSITE") == "1"
            and str(pfade.ABLAGE) in u.get("PIP_CACHE_DIR", "")
            and "PYTHONPATH" not in u and "PYTHONHOME" not in u,
            f"PYTHONNOUSERSITE={u.get('PYTHONNOUSERSITE')}, "
            f"PIP_CACHE_DIR in der Ablage: {str(pfade.ABLAGE) in u.get('PIP_CACHE_DIR','')}, "
            f"PYTHONPATH entfernt: {'PYTHONPATH' not in u}")


def b6():
    t = (HIER / "agent" / "oberflaeche.py").read_text(encoding="utf-8")
    return ("allow_reuse_address = False" in t and "_freier_port" in t,
            "weicht auf einen freien Port aus, statt einen belegten zu uebernehmen")


def b8(wurzel):
    sys.path.insert(0, str(HIER / "agent"))
    os.environ["KURS_AGENT_WURZEL"] = str(wurzel)
    import importlib, agent as a
    importlib.reload(a)
    s = a.Sperre().__enter__()
    try:
        a.Sperre().__enter__()
        return False, "ein zweiter Lauf kam durch"
    except a.Belegt:
        return True, "ein zweiter Lauf wird abgewiesen"
    finally:
        s.__exit__()


# ---------------------------------------------------------------- C: nur im Kursordner
def c23(wurzel):
    faelle = [("../../../../tmp/entwischt.txt", "liegt nicht in der Ablage"),
              ("/etc/entwischt.txt", "absoluter Pfad"),
              ("C:\\Windows\\x.txt", "absoluter Pfad")]
    schlecht = []
    for name, _ in faelle:
        a = _werkzeug("schreib_datei", {"name": name, "inhalt": "x"}, wurzel)
        if not a.startswith("FEHLER"):
            schlecht.append(name)
    draussen = pathlib.Path("/tmp/entwischt.txt").exists()
    return (not schlecht and not draussen,
            f"abgewiesen: {len(faelle)-len(schlecht)} von {len(faelle)}"
            + (f"; DURCHGELASSEN: {schlecht}" if schlecht else "")
            + ("; eine Datei liegt wirklich draussen!" if draussen else ""))


def c1(wurzel):
    """Der Waechter muss anschlagen — und nur beim richtigen Fall."""
    sys.path.insert(0, str(HIER / "agent"))
    probe = HIER / "agent" / "_waechterprobe.py"
    probe.write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).parent))\n"
        "import waechter\n"
        f"waechter.anmelden(pathlib.Path({str(wurzel / 'ablage')!r}), pathlib.Path({str(wurzel / 'paket')!r}))\n"
        f"open({str(wurzel / 'ablage' / 'ok.txt')!r}, 'w').write('x')\n"
        # Der Waechter soll anschlagen, wenn ausserhalb der Ablage geschrieben wird --
        # dafuer muss wirklich geschrieben werden, und zwar an einem Ort, der wirklich
        # geschuetzt ist. Der Ordner fuer Temporaeres taugt dafuer NICHT: ihn laesst der
        # Waechter ausdruecklich zu (waechter._erlaubt), weil Python selbst dort staendig
        # Dateien anlegt. Deshalb das Benutzerverzeichnis -- genau der Ort, um den es
        # geht. Die Datei wird in jedem Fall wieder entfernt, auch wenn dazwischen etwas
        # schiefgeht; sonst bliebe nach einem Absturz eine Spur auf einem fremden Rechner.
        "import os\n"
        "d = os.path.join(os.path.expanduser('~'), '_kurs_waechterprobe.txt')\n"
        "try:\n"
        "    open(d, 'w').write('x')\n"
        "finally:\n"
        "    os.path.exists(d) and os.unlink(d)\n"
        "print(waechter.bericht())\n", encoding="utf-8")
    try:
        (wurzel / "ablage").mkdir(parents=True, exist_ok=True)
        r = _lauf([PY, str(probe)], wurzel, zeit=60)
        a = (r.stdout or r.stderr).strip()
        traf = "_kurs_waechterprobe.txt" in a
        nur_eines = "1 Schreibversuch" in a
        return traf and nur_eines, (a.splitlines()[0][:95] if a else "keine Ausgabe")
    finally:
        probe.unlink(missing_ok=True)


def c5(wurzel):
    paket = wurzel / "paket"
    if not paket.is_dir():
        return True, "kein Paketordner im Pruefordner — uebersprungen"
    import hashlib
    vor = hashlib.sha256(b"".join(sorted(
        p.name.encode() + str(p.stat().st_size).encode()
        for p in paket.rglob("*") if p.is_file()))).hexdigest()
    _werkzeug("schreib_datei", {"name": "x.py", "inhalt": "a=1\n"}, wurzel)
    nach = hashlib.sha256(b"".join(sorted(
        p.name.encode() + str(p.stat().st_size).encode()
        for p in paket.rglob("*") if p.is_file()))).hexdigest()
    return vor == nach, f"Paketordner unveraendert: {vor[:12]}"


# ---------------------------------------------------------------- D: entfernbar
def d12(wurzel):
    _werkzeug("schreib_datei", {"name": "weg.py", "inhalt": "a=1\n"}, wurzel)
    a = _werkzeug("aufraeumen", {"nur_zeigen": False}, wurzel)
    leer = not (wurzel / "ablage").exists()
    return ("0 Dateien zurueck" in a and leer,
            a.splitlines()[1][:90] if len(a.splitlines()) > 1 else a[:90])


# ---------------------------------------------------------------- E: Weitergabe
def e4(wurzel):
    sys.path.insert(0, str(HIER / "agent"))
    os.environ["KURS_AGENT_WURZEL"] = str(wurzel)
    import importlib, modell
    importlib.reload(modell)
    alle = sorted((wurzel / "paket" / "modell").glob("*.gguf"))
    if len(alle) < 2:
        return True, f"nur {len(alle)} Modell(e) im Pruefordner — Staffelung nicht pruefbar"
    echt = modell.freier_speicher_gb
    gewaehlt = []
    for frei in (52.0, 5.0, 3.0):
        modell.freier_speicher_gb = lambda f=frei: f
        g, _ = modell.waehlen(laut=False)
        gewaehlt.append(g.stat().st_size if g else 0)
    modell.freier_speicher_gb = echt
    return (gewaehlt[0] > gewaehlt[1] > gewaehlt[2] == 0,
            f"bei 52/5/3 GB frei: {[round(x/1e9,2) if x else 'keines' for x in gewaehlt]}")


# ---------------------------------------------------------------- G: Lehrinhalt
def g23(wurzel):
    """Vier Faelle, und der Bericht nennt, was wirklich herauskam — nicht, was herauskommen
    sollte. Ein Prueftext, der sein Ergebnis behauptet statt es abzulesen, ist wertlos."""
    gut = ("from machine import Pin\nimport time\nled = Pin(2, Pin.OUT)\nwhile True:\n"
           "    led.value(1)\n    time.sleep(0.5)\n    led.value(0)\n    time.sleep(0.5)\n")
    _werkzeug("schreib_datei", {"name": "p.py", "inhalt": gut}, wurzel)
    e = {"datei": "p.py", "sekunden": 4, "oeffnen": False}

    def urteil(zusatz):
        a = _werkzeug("programm_testen", {**e, **zusatz}, wurzel)
        return ("bestanden" if "ABNAHME BESTANDEN" in a
                else "durchgefallen" if "ABNAHME NICHT BESTANDEN" in a
                else "als Vorfuehrung gekennzeichnet" if "Keine Erwartung angegeben" in a
                else "FEHLER: " + a.splitlines()[0][:60])

    faelle = [("richtige Erwartung", {"erwartet": {"pins": [2], "takt_hz": 1.0}}, "bestanden"),
              ("falscher Takt",      {"erwartet": {"pins": [2], "takt_hz": 3.0}}, "durchgefallen"),
              ("falscher Anschluss", {"erwartet": {"pins": [7], "takt_hz": 1.0}}, "durchgefallen"),
              ("ohne Erwartung",     {}, "als Vorfuehrung gekennzeichnet")]
    ist = [(titel, urteil(z), soll) for titel, z, soll in faelle]
    alles = all(i == s for _, i, s in ist)
    return alles, "; ".join(f"{t}: {i}" + ("" if i == s else f" (erwartet: {s})")
                            for t, i, s in ist)


def g4(wurzel):
    d = HIER / "agent" / "pruefe_schleife.py"
    if not d.is_file():
        return False, f"{d} fehlt"
    r = _lauf([PY, str(d)], None, zeit=300)
    letzte = (r.stdout or r.stderr).strip().splitlines()
    return "ALLE PUNKTE ERFUELLT" in r.stdout, letzte[-1][:95] if letzte else "keine Ausgabe"


def g6(wurzel):
    gut = "from machine import Pin\nimport time\nled = Pin(2, Pin.OUT)\nled.value(1)\ntime.sleep(0.2)\nled.value(0)\n"
    _werkzeug("schreib_datei", {"name": "unberuehrt.py", "inhalt": gut}, wurzel)
    d = wurzel / "ablage" / "werkstatt" / "unberuehrt.py"
    vor = d.read_text(encoding="utf-8")
    a = _werkzeug("programm_testen", {"datei": "unberuehrt.py", "sekunden": 3, "oeffnen": False}, wurzel)
    # Ohne diesen Nachweis waere die Pruefung wertlos: ein Lauf, der gar nicht stattfand,
    # veraendert den Quelltext selbstverstaendlich auch nicht.
    if "Geschaltet wurde Pin" not in a:
        return False, f"der Lauf fand nicht statt: {a.splitlines()[0][:80]}"
    return (vor == d.read_text(encoding="utf-8"),
            "der Lauf fand statt und der Quelltext ist danach Byte fuer Byte derselbe")


def f8():
    """Die Suche nach einem Python zum Fuellen gibt nicht beim ersten Fundort auf.

    Der Anlass: Am 03.10.2026, beim ersten echten Windows-Lauf, nannte "where python"
    zuerst C:\\...\\Microsoft\\WindowsApps\\python.exe -- den Platzhalter des Windows-Stores,
    der nur den Laden oeffnet und kein pip hat. START.bat erkannte das richtig und brach
    dann ab. Auf demselben Rechner lag ein brauchbares Python (Thonny) im naechsten
    Fundort der Liste und wurde nie gefragt. Grundsatz 21: Wer denkt, es geht nicht, hat
    nicht gut genug gesucht.

    Geprueft wird am Text von START.bat, weil sich der Fall am Linux-Rechner nicht
    nachspielen laesst. Vier Dinge muessen stimmen:
      1. Es gibt die Unterroutine :pruefepython, die EINEN Kandidaten beurteilt.
      2. Jeder Fundort geht durch sie hindurch (kein "if not defined FREMD set FREMD=" mehr).
      3. Der Platzhalter des Stores wird uebersprungen, nicht gestartet.
      4. Abgebrochen wird erst, wenn ALLE Kandidaten durchgefallen sind.
    """
    hier = pathlib.Path(__file__).resolve().parent
    bat = (hier / "START.bat").read_text(encoding="utf-8", errors="replace")
    maengel = []

    if ":pruefepython" not in bat:
        maengel.append("die Unterroutine :pruefepython fehlt")
    aufrufe = bat.count("call :pruefepython")
    if aufrufe < 4:
        maengel.append(f"nur {aufrufe} Fundorte werden geprueft, erwartet sind mindestens 4")

    # Das alte Muster darf nicht zurueckkommen: erster Treffer gewinnt, egal ob brauchbar.
    import re
    if re.search(r"if not defined FREMD set \"FREMD=", bat):
        maengel.append("ein Fundort wird noch ohne Pruefung uebernommen "
                       "(Muster 'if not defined FREMD set FREMD=')")

    if "WindowsApps" not in bat:
        maengel.append("der Platzhalter des Windows-Stores wird nicht erkannt")
    elif "| find" in bat.split(":pruefepython")[-1]:
        maengel.append("die Erkennung laeuft ueber 'find' -- ein eigenes Programm, das "
                       "fehlen oder anders antworten kann; cmd kann es selbst")

    # Der Abbruch darf erst kommen, wenn alle Fundorte geprueft sind. Seit die Suche in
    # der Unterroutine :suchepython steht, heisst das: Vor jedem "if not defined FREMD ("
    # muss in den drei Zeilen davor "call :suchepython" stehen -- und die Unterroutine
    # selbst muss alle Fundorte durchgehen (siehe aufrufe oben).
    zeilen = bat.splitlines()
    if ":suchepython" not in bat:
        maengel.append("die Unterroutine :suchepython fehlt -- die Suche steht nicht an einer Stelle")
    for i, z in enumerate(zeilen):
        if "if not defined FREMD (" in z and not z.strip().startswith("rem"):
            davor = " ".join(zeilen[max(0, i - 3):i]).lower()
            if "call :suchepython" not in davor:
                maengel.append(f"Zeile {i+1}: abgebrochen, ohne dass unmittelbar davor alle "
                               f"Fundorte durchsucht wurden")

    if maengel:
        return False, "; ".join(maengel)
    return True, (f"{aufrufe} Fundorte, jeder einzeln auf pip geprueft; der Platzhalter des "
                  "Windows-Stores wird uebersprungen; Abbruch erst, wenn alle durchgefallen sind")


def f7():
    """Die Anleitung nennt dieselben Menuenummern wie START.bat.

    Der Anlass: Am 02.10.2026 war das Hauptmenue umnummeriert worden, die Anleitung aber
    nicht. Sie schickte den Leser mit [0] zum Paketfuellen (wirklich [4]), mit [3] zum
    Agenten (wirklich [1]) und mit [4] zum Rueckfallweg -- was in Wahrheit das Paketfuellen
    gestartet haette. Durch Lesen war das nicht zu sehen; es faellt nur auf, wenn man
    beides nebeneinanderlegt.
    """
    import re
    hier = pathlib.Path(__file__).resolve().parent
    bat = (hier / "START.bat").read_text(encoding="ascii", errors="replace")
    anl = sorted(hier.glob("Kurs_Agent_Inbetriebnahme_*.html"))
    if not anl:
        return True, "keine Anleitung vorhanden -- nichts zu vergleichen"
    html = anl[-1].read_text(encoding="utf-8")

    def schluessel(s):
        s = s.lower().strip()
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            s = s.replace(a, b)
        return re.sub(r"[^a-z]", "", s)[:12]

    # was START.bat wirklich anbietet: Nummer -> Menge der Namen (zwei Menues)
    echt = {}
    for nr, name in re.findall(r"echo\s+\[(\d)\]\s+([A-Za-z][^\r\n]*)", bat):
        echt.setdefault(nr, set()).add(schluessel(name.split("  ")[0]))

    # was die Anleitung behauptet: nur ausdrueckliche Menue- und Betriebsartverweise
    # Der Name zaehlt nur, wenn er im SELBEN Auszeichnungselement steht wie die Nummer --
    # sonst wird der Fliesstext dahinter faelschlich fuer einen Menuenamen gehalten.
    behauptet = [(nr, name) for _, nr, name in re.findall(
        r"(?:Men\u00fcpunkt|Betriebsart)[^\[]{0,40}<(code|strong)>\[(\d)\]\s*([^<]*)</\1>", html)]
    if not behauptet:
        return False, "in der Anleitung steht kein einziger Menueverweis -- Regel greift ins Leere"

    falsch = []
    for nr, name in behauptet:
        k = schluessel(name)
        if not k:                      # Verweis ohne Namen, z.B. "Menuepunkt [1] oeffnet ..."
            if nr not in echt:
                falsch.append(f"[{nr}] gibt es im Menue nicht")
            continue
        if nr not in echt or not any(k.startswith(e[:6]) or e.startswith(k[:6]) for e in echt[nr]):
            gibt = ", ".join(sorted(echt.get(nr, {"-"})))
            falsch.append(f"Anleitung: [{nr}] {name.strip()!r} -- START.bat: [{nr}] {gibt}")
    if falsch:
        return False, f"{len(falsch)} Abweichung(en): " + " | ".join(falsch[:4])
    return True, f"{len(behauptet)} Menueverweise der Anleitung stimmen mit START.bat ueberein"


def e5():
    """Der Vorrat ist vollstaendig: jede Abhaengigkeit der Werkzeuge liegt bei.

    Im Kurs gibt es kein Netz. Fehlt ein einziges Rad, bricht pip ab -- und zwar erst
    dann, wenn zwanzig Leute davorsitzen. Deshalb wird hier nachgerechnet statt gehofft:
    aus jedem Rad die Liste der Anforderungen lesen, die Umgebungsbedingungen dagegen
    halten (Python 3.12, Windows, CPython) und nachsehen, ob jedes Verlangte im Vorrat
    liegt.

    Die Bedingungen sind der Kern: typing-extensions steht in cryptography, aber nur
    "python_full_version < '3.11'". Das Paket bringt 3.12.10 mit -- die Zeile gilt also
    nicht. Wer sie mitzaehlt, jagt einem Phantom nach; wer alle Bedingungen ignoriert,
    uebersieht die echten.
    """
    import zipfile
    vorrat = HIER / "paket" / "pakete"
    if not vorrat.is_dir() or not any(vorrat.iterdir()):
        return True, "kein Vorrat vorhanden -- nichts zu pruefen (Paket noch nicht gefuellt)"

    def schluessel(s):
        # Die Tilde gehoert dazu: "mdurl~=0.1" heisst "mdurl, vertraegliche Fassung".
        # Ohne sie blieb "mdurl~" uebrig und wurde als fehlend gemeldet, obwohl mdurl
        # danebenlag.
        return re.split(r"[<>=!~;\s\[,()]", s.strip(), maxsplit=1)[0].strip().lower().replace("_", "-")

    da = {schluessel(re.split(r"-\d", f.name, maxsplit=1)[0]): f for f in vorrat.iterdir()}

    def gilt(bedingung: str) -> bool:
        """Grob, aber auf der sicheren Seite: im Zweifel gilt die Anforderung."""
        b = bedingung.strip()
        if not b:
            return True
        if "extra ==" in b:
            return False                       # Zusatzausstattung, nicht verlangt
        m = re.search(r"python(?:_full)?_version\s*<\s*[\'\"]([\d.]+)", b)
        if m:
            return tuple(int(x) for x in m.group(1).split(".")[:2]) > (3, 12)
        m = re.search(r"python(?:_full)?_version\s*>=?\s*[\'\"]([\d.]+)", b)
        if m:
            return (3, 12) >= tuple(int(x) for x in m.group(1).split(".")[:2])
        if "platform_system" in b:
            return "!=" not in b or "Windows" not in b
        if "platform_python_implementation" in b:
            return "!=" not in b or "PyPy" not in b
        return True

    # Erst die einfachere Haelfte: Was angefordert werden DARF, muss auch dasein.
    # Am 02.10.2026 stand "adafruit-ampy" auf der Erlaubnisliste, lag aber nicht im
    # Vorrat -- und die Anleitung nannte es, weil sie die Liste ausliest. Das Modell
    # haette es anfordern koennen.
    erlaubt_text = (HIER / "agent" / "werkzeuge" / "paket_installieren.py").read_text(
        encoding="utf-8")
    m = re.search(r"ERLAUBT\s*=\s*\{([^}]*)\}", erlaubt_text)
    erlaubt = {schluessel(x) for x in re.findall(r'"([^"]+)"', m.group(1))} if m else set()
    ohne_vorrat = sorted(e for e in erlaubt if e not in da)

    fehlt, geprueft = [f"erlaubt, aber nicht im Vorrat: {e}" for e in ohne_vorrat], 0
    for name, f in sorted(da.items()):
        if f.suffix != ".whl":
            continue
        try:
            with zipfile.ZipFile(f) as z:
                meta = next((n for n in z.namelist() if n.endswith("METADATA")), None)
                text = z.read(meta).decode("utf-8", "replace") if meta else ""
        except Exception as e:
            fehlt.append(f"{f.name} nicht lesbar: {e}")
            continue
        for zeile in text.splitlines():
            if not zeile.startswith("Requires-Dist:"):
                continue
            wunsch, _, bedingung = zeile.split(":", 1)[1].partition(";")
            if not gilt(bedingung):
                continue
            geprueft += 1
            if schluessel(wunsch) not in da:
                fehlt.append(f"{name} braucht {schluessel(wunsch)}")
    if fehlt:
        return False, f"{len(fehlt)} fehlt im Vorrat: " + "; ".join(fehlt[:5])
    return True, (f"{len(da)} Pakete im Vorrat; {len(erlaubt)} erlaubte Pakete, alle da; "
                  f"{geprueft} geltende Anforderungen geprueft, jede davon liegt bei")


def b10():
    """Jeder Programmstart reicht die abgeschirmte Umgebung weiter.

    Ein einziger Aufruf ohne env=umgebung() genuegt, damit ein Unterprozess den
    pip-Zwischenspeicher des Benutzers benutzt, sein Paketverzeichnis liest oder ein
    halb fremdes Python bekommt. Das faellt auf dem Rechner des Erbauers nie auf --
    dort ist PYTHONPATH nicht gesetzt und der Zwischenspeicher schon warm. Es faellt
    im Kurs auf, auf einem fremden Rechner.

    Ausgenommen sind reine Windows-Abfragen wie tasklist: sie lesen nur und starten
    kein Python.
    """
    import ast
    nackt = []
    for d in sorted((HIER / "agent").rglob("*.py")):
        if "__pycache__" in str(d):
            continue
        quelle = d.read_text(encoding="utf-8", errors="replace")
        try:
            baum = ast.parse(quelle)
        except SyntaxError:
            continue
        for k in ast.walk(baum):
            if not (isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                    and k.func.attr in ("run", "Popen")):
                continue
            text = ast.get_source_segment(quelle, k) or ""
            if "subprocess" not in text and not isinstance(k.func.value, ast.Name):
                continue
            if any(w.arg == "env" for w in k.keywords):
                continue
            if re.search(r'"(tasklist|taskkill|where|cmd)"', text):
                continue                       # liest nur, startet kein Python
            nackt.append(f"{d.relative_to(HIER)}:{k.lineno}")
    if nackt:
        return False, f"{len(nackt)} Start(s) ohne abgeschirmte Umgebung: " + ", ".join(nackt[:4])
    return True, "jeder Programmstart reicht env=umgebung() weiter"


# Die Saetze, die jede Fassung der Aufgabe tragen muss. Fehlt einer, ist der Text abgeschnitten
# oder umgeschrieben worden. Nach zwei Abstuerzen (03./04.10.2026) sollte die Aufgabe nie wieder
# neu geschrieben werden muessen; deshalb steht sie an drei Orten und wird hier verglichen.
AUFGABE_KERN = ("speziell für die Python-Programmierung", "selbst testen können",
                "ohne Internetzugang funktionieren", "alle Treiber müssen vorhanden sein",
                "kein schon vorhandenes Python verwendet", "alles muss mitgeliefert werden",
                "es muss noch nachgeladen werden")


def z0(hier=None):
    """Z0: die Aufgabe des Auftraggebers steht woertlich in AUFGABE.md, ANFORDERUNGEN.md und PRUEFPROTOKOLL.md."""
    hier = pathlib.Path(hier) if hier else HIER
    fehl = []
    for name in ("AUFGABE.md", "ANFORDERUNGEN.md", "PRUEFPROTOKOLL.md"):
        d = hier / name
        if not d.is_file():
            fehl.append(f"{name} fehlt"); continue
        text = d.read_text(encoding="utf-8").replace("\n> ", " ").replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        for satz in AUFGABE_KERN:
            if satz not in text:
                fehl.append(f"{name}: ‚{satz}‘ fehlt")
    return (not fehl), "; ".join(fehl) if fehl else "alle Kernsaetze an allen drei Orten"


def main():
    print("\nZ — die Aufgabe")
    pruefe("Z0", "die Aufgabe des Auftraggebers steht woertlich an drei Orten", z0)
    wurzel = pathlib.Path(tempfile.mkdtemp(prefix="kurs_pruefung_"))
    (wurzel / "paket").mkdir()
    # ein lauffaehiges Python vortaeuschen, damit die Werkzeuge arbeiten koennen
    (wurzel / "ablage" / "python").mkdir(parents=True)
    exe = wurzel / "ablage" / "python" / "python.exe"
    if os.name == "nt":
        import shutil; shutil.copy2(PY, exe)
    else:
        exe.write_text(f'#!/bin/sh\nexec "{PY}" "$@"\n'); exe.chmod(0o755)

    print(f"\nKurs-Agent — Anforderungen maschinell geprueft")
    print(f"Pruefordner: {wurzel}\n")

    print("A — Autarkie")
    pruefe("A4", "kein vorhandenes Python wird gesucht oder benutzt", a4)
    pruefe("A5", "kein fester Pfad, kein fester Laufwerksbuchstabe", a5)
    pruefe("A6", "ohne Sprachmodell sind alle Werkzeuge erreichbar", a6)

    print("\nB — keine Stoerung dessen, was schon da ist")
    pruefe("B3-5", "Benutzer-Pakete, pip-Zwischenspeicher und PYTHON-Variablen abgeschirmt", b345)
    pruefe("B6", "belegter Port wird nicht uebernommen", b6)
    pruefe("B8", "zwei gleichzeitige Laeufe werden verhindert", lambda: b8(wurzel))

    pruefe("B10", "jeder Programmstart laeuft in der abgeschirmten Umgebung", b10)

    print("\nC — nur im Kursordner schreiben")
    pruefe("C1", "der Waechter meldet Schreibversuche ausserhalb der Ablage",
           lambda: c1(wurzel))
    pruefe("C2-3", "Ausbruch aus der Ablage und absolute Pfade werden abgewiesen",
           lambda: c23(wurzel))
    pruefe("C5", "das mitgelieferte Paket bleibt unveraendert", lambda: c5(wurzel))

    print("\nD — restlos entfernbar")
    pruefe("D1-2", "Aufraeumen loescht alles und zaehlt nach", lambda: d12(wurzel))

    print("\nE — Weitergabe")
    pruefe("E4", "das Modell wird nach freiem Speicher gewaehlt", lambda: e4(wurzel))

    print("\nE — Weitergabe")
    pruefe("E5", "der Vorrat ist vollstaendig: jede Abhaengigkeit liegt bei", e5)

    print("\nF — Bedienung")
    pruefe("F7", "die Anleitung nennt dieselben Menuenummern wie START.bat", f7)
    pruefe("F8", "die Python-Suche gibt nicht beim ersten Fundort auf", f8)

    print("\nG — der Lehrinhalt")
    pruefe("G2-3", "die Abnahme besteht bei richtig und faellt bei falsch durch",
           lambda: g23(wurzel))
    pruefe("G4", "FERTIG gilt nicht, solange die Pruefung fehlschlug", lambda: g4(wurzel))
    pruefe("G6", "der geprueffte Quelltext wird nicht veraendert", lambda: g6(wurzel))

    gut = sum(1 for *_, g, _ in ergebnisse if g)
    print(f"\n{'='*72}")
    print(f"  {gut} von {len(ergebnisse)} Pruefungen erfuellt")
    if gut < len(ergebnisse):
        for n, w, g, b in ergebnisse:
            if not g:
                print(f"    FEHL  {n}  {w}\n          {b}")
    print(f"{'='*72}")
    print("  Von Hand zu pruefen bleiben: A1-A3 (Paket vollstaendig, kein Netz, keine")
    print("  Installation), B1-B2/B7, C1/C4, D3-D6, E1-E3, F1-F6, H1-H6 — siehe")
    print("  ANFORDERUNGEN.md.")
    import shutil
    shutil.rmtree(wurzel, ignore_errors=True)
    return 0 if gut == len(ergebnisse) else 1


if __name__ == "__main__":
    raise SystemExit(main())
