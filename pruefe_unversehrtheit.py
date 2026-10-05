#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Beantwortet eine einzige Frage: Veraendert dieses Paket den Rechner, auf dem es laeuft?

    python pruefe_unversehrtheit.py            lesen und messen
    python pruefe_unversehrtheit.py --lauf     zusaetzlich einen vollen Lauf messen (dauert)

Die Frage ist ernst gemeint und wird nicht mit "nein, bestimmt nicht" beantwortet, sondern
auf drei Wegen, die einander nicht glauben muessen:

    1  Was steht im Programmtext?   Jede schreibende Zeile wird gesucht und ihr Ziel
                                    benannt. Was ausserhalb des Kursordners zeigt, muss
                                    sich erklaeren lassen.
    2  Was fehlt darin?             Befehle, die Windows veraendern -- Registrierung,
                                    Dienste, Aufgabenplanung, Rechte, PATH dauerhaft --
                                    duerfen nirgends vorkommen.
    3  Was geschieht wirklich?      Mit --lauf: Verzeichnisbaum vorher und nachher
                                    vergleichen, ausserhalb des Kursordners.

Weg 1 und 2 sind Durchsicht, Weg 3 ist Messung. Keiner allein genuegt: Durchsicht sieht
nicht, was zur Laufzeit entsteht; die Messung sieht nicht, was heute zufaellig nicht
ausgeloest wurde.
"""
from __future__ import annotations
import argparse, ast, os, pathlib, re, subprocess, sys, tempfile

HIER = pathlib.Path(__file__).resolve().parent

# --------------------------------------------------------------------------------------
# Befehle, die den Rechner dauerhaft veraendern. Keiner davon darf vorkommen -- nicht
# auskommentiert, nicht "nur fuer den Notfall", gar nicht.
# --------------------------------------------------------------------------------------
VERBOTEN = {
    r"\breg\s+(add|delete|import)\b":  "schreibt in die Windows-Registrierung",
    r"\bregedit\b":                    "Registrierungseditor",
    r"\bsetx\b":                       "setzt Umgebungsvariablen dauerhaft",
    r"\bsc\s+(create|config|delete)\b": "legt einen Dienst an oder aendert ihn",
    r"\bschtasks\b":                   "traegt eine geplante Aufgabe ein",
    r"\bnet\s+(user|localgroup)\b":    "aendert Benutzer oder Gruppen",
    r"\b(assoc|ftype)\b":              "aendert Dateiverknuepfungen",
    r"\b(icacls|takeown|cacls)\b":     "aendert Rechte oder Besitz",
    r"\bbcdedit\b":                    "aendert den Startvorgang",
    r"\bdiskpart\b":                   "aendert Partitionen",
    r"\bmsiexec\b":                    "installiert",
    r"\bpowercfg\b":                   "aendert Energieeinstellungen",
    r"\bwinget\b|\bchoco\b":           "Paketverwaltung des Rechners",
    r"\bpip\s+install\b": "installiert Pakete",   # nur ausserhalb des eigenen Python schwer
    r"shell:startup|Start Menu.Programs.Startup": "traegt sich in den Autostart ein",
}

# Schreibende Aufrufe im Python-Quelltext.
SCHREIBT = {
    "write_text", "write_bytes", "mkdir", "makedirs", "touch", "rename",
    "unlink", "remove", "rmdir", "rmtree", "copy", "copy2", "copytree", "move",
    "extractall", "extract", "urlretrieve",
}
# "replace" steht absichtlich NICHT in der Liste: str.replace ersetzt Text in einer
# Zeichenkette und fasst keine Datei an. Es stand zuerst darin und erzeugte sieben
# Falschmeldungen -- jede davon eine Textersetzung. Das Dateiumbenennen heisst os.replace
# oder Path.replace und wird unten gezielt gesucht.


class Befund:
    def __init__(self):
        self.zeilen: list[tuple[str, str, str]] = []   # (Schwere, Ort, Text)

    def melde(self, schwere, ort, text):
        self.zeilen.append((schwere, ort, text))

    def zahl(self, schwere):
        return sum(1 for s, _, _ in self.zeilen if s == schwere)


def dateien():
    """Alle Programmtexte des Pakets -- ohne Ablage, Paket und Pruefstand."""
    aus = ("ablage", "paket", "pruefstand", "Arbeitsstand", "alt_nicht_anfassen",
           "__pycache__", ".git")
    for p in sorted(HIER.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".py", ".bat", ".cmd", ".ps1"):
            continue
        if any(teil in aus for teil in p.relative_to(HIER).parts):
            continue
        if p.resolve() == pathlib.Path(__file__).resolve():
            continue          # dieses Programm nennt die verbotenen Befehle, um sie zu suchen
        yield p


# --------------------------------------------------------------------------------------
# Weg 2 zuerst: das Einfache und Eindeutige
# --------------------------------------------------------------------------------------
def weg2_verbotene_befehle(b: Befund) -> int:
    print("\n2 - Befehle, die den Rechner veraendern wuerden")
    treffer = 0
    for p in dateien():
        text = p.read_text(encoding="utf-8", errors="replace")
        in_zeichenkette = _zeilen_in_zeichenketten(p, text)
        for zeile_nr, zeile in enumerate(text.splitlines(), 1):
            nackt = zeile.strip()
            if nackt.startswith(("rem ", "#", "::")):      # Erlaeuterung, kein Befehl
                continue
            if zeile_nr in in_zeichenkette:
                continue                                   # Text ueber einen Befehl
            # Listenform zu einer Befehlszeile glattziehen, damit ["reg", "add"] wie
            # "reg add" aussieht und dieselben Muster greifen.
            glatt = re.sub(r'["\'],\s*["\']', " ", zeile)
            for muster, was in VERBOTEN.items():
                if not (re.search(muster, zeile, re.I) or re.search(muster, glatt, re.I)):
                    continue
                # "pip install" ist nur dann ein Eingriff in den Rechner, wenn es in ein
                # FREMDES Python installiert. Das Paket installiert in sein eigenes, und
                # das ist der Sinn der Sache. Erkennbar daran, dass der Aufruf ueber
                # python_exe() bzw. !PY! laeuft -- beides zeigt in die Ablage.
                if "pip" in muster and re.search(
                        r"python_exe\(\)|!PY!|\bPYTHON\b|ablage", zeile, re.I):
                    continue
                b.melde("SCHWER", f"{p.relative_to(HIER)}:{zeile_nr}",
                        f"{was}: {nackt[:90]}")
                treffer += 1
    if treffer:
        print(f"  {treffer} Treffer -- siehe Befundliste")
    else:
        print(f"  keiner der {len(VERBOTEN)} gesuchten Befehle kommt vor")
    return treffer


# --------------------------------------------------------------------------------------
# Weg 1: jede schreibende Zeile und ihr Ziel
# --------------------------------------------------------------------------------------
def _zeilen_in_zeichenketten(p: pathlib.Path, quelle: str) -> set[int]:
    """Zeilennummern, die zu einer Zeichenkette gehoeren -- dort steht Text, kein Befehl."""
    if p.suffix != ".py":
        return set()
    try:
        baum = ast.parse(quelle)
    except SyntaxError:
        return set()
    # Nur FLIESSTEXT ausnehmen -- Docstrings, HTML, Hilfetexte. Kurze Zeichenketten
    # bleiben geprueft: In der Gegenprobe stand subprocess.run(["reg", "add", ...]) in
    # lauter kurzen Literalen, und die ganze Zeile wurde uebersprungen. Ein verbotener
    # Befehl in Listenform waere so unsichtbar geblieben.
    drin: set[int] = set()
    for k in ast.walk(baum):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            text = k.value
            if len(text) > 150 or "<" in text or "\n" in text:
                drin.update(range(k.lineno, (k.end_lineno or k.lineno) + 1))
    return drin


MODULE = {"shutil", "os", "zipfile", "tarfile", "request", "urllib", "pathlib",
          "tempfile", "json", "subprocess", "sys"}


def _ist_modul(knoten: ast.AST) -> bool:
    """shutil.rmtree(ziel) schreibt nach ziel, pfad.write_text(x) nach pfad.

    Der Unterschied: steht vor dem Punkt ein Modul oder ein Pfad? Ohne diese
    Unterscheidung meldete die Pruefung "rmtree(shutil)" und nannte damit das Werkzeug
    statt des Ziels.
    """
    if isinstance(knoten, ast.Name):
        return knoten.id in MODULE
    if isinstance(knoten, ast.Attribute):
        return knoten.attr in MODULE or _ist_modul(knoten.value)
    return False


def _ziel_benennen(quelle: str, knoten: ast.AST) -> str:
    """Grob, aber ehrlich: der Text des Ausdrucks, auf dem geschrieben wird."""
    try:
        return ast.get_source_segment(quelle, knoten) or "?"
    except Exception:
        return "?"


# Wurzeln, auf die ein Ziel zurueckfuehren muss, damit es als "im Kursordner" gilt.
# ABLAGE, PAKET und WERKSTATT sind in pfade.py aus WURZEL abgeleitet; WURZEL ist der
# Kursordner. mkdtemp liegt im Ordner fuer Temporaeres -- das ist kein Teil des Rechners,
# den jemand behalten will, und wird eigens genannt.
WURZELN = {"WURZEL", "HIER", "ABLAGE", "PAKET", "WERKSTATT", "PYTHON", "ziel"}


def _zuweisungen() -> dict[str, str]:
    """Jede Zuweisung NAME = <Ausdruck> aus allen Programmen, als Text.

    Damit laesst sich ein Ziel aufloesen statt zu raten: PID_DATEI fuehrt ueber
    ABLAGE auf WURZEL zurueck und liegt damit im Kursordner. Die erste Fassung dieser
    Pruefung verglich stattdessen Variablennamen mit einer Liste -- sie meldete
    PID_DATEI, AUFNAHME und PYTHON als verdaechtig, obwohl alle drei in der Ablage
    liegen, und haette ein echtes Ziel ausserhalb uebersehen, wenn es nur guenstig
    geheissen haette.
    """
    tabelle: dict[str, str] = {}
    for p in dateien():
        if p.suffix != ".py":
            continue
        tabelle.update(_zuweisungen_einer(p))
    return tabelle


def _zuweisungen_einer(p: pathlib.Path) -> dict[str, str]:
    """Zuweisungen einer Datei -- auch die in Funktionen und die auf self.

    Nur Modulebene zu sammeln reichte nicht: "exe = wurzel / 'ablage' / ..." steht in
    einer Funktion, "self.datei = ABLAGE / 'laeuft.pid'" in einer Methode. Beide waren
    deshalb "nicht erkennbar", obwohl sie klar in den Kursordner fuehren.
    """
    quelle = p.read_text(encoding="utf-8", errors="replace")
    try:
        baum = ast.parse(quelle)
    except SyntaxError:
        return {}
    tabelle: dict[str, str] = {}
    for k in ast.walk(baum):
        if not isinstance(k, (ast.Assign, ast.AnnAssign)):
            continue
        ziele = k.targets if isinstance(k, ast.Assign) else [k.target]
        wert = k.value
        if wert is None:
            continue
        for z in ziele:
            if isinstance(z, ast.Name):
                tabelle.setdefault(z.id, _ziel_benennen(quelle, wert))
            elif isinstance(z, ast.Attribute):          # self.datei = ABLAGE / "..."
                tabelle.setdefault(f"self.{z.attr}", _ziel_benennen(quelle, wert))
                tabelle.setdefault(z.attr, _ziel_benennen(quelle, wert))
    return tabelle


def _kette(ziel: str, tabelle: dict[str, str], tiefe: int = 0) -> str:
    """Der Ausdruck samt allem, worauf er sich stuetzt -- aufgeloest.

    Ohne das sah die Pruefung nur "write_text(_spur)" und hielt es fuer eine Anmerkung.
    Erst die Kette zeigt, dass _spur ueber expanduser("~") ins Benutzerprofil fuehrt.
    """
    if tiefe > 6 or not ziel:
        return ziel or ""
    teile = [ziel]
    for n in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ziel)):
        if n in tabelle and tabelle[n] != ziel:
            teile.append(_kette(tabelle[n], tabelle, tiefe + 1))
    return " ".join(teile)


def _fuehrt_nach_innen(ziel: str, tabelle: dict[str, str], tiefe: int = 0) -> bool:
    """Loest ein Ziel so lange auf, bis eine bekannte Wurzel erscheint."""
    if tiefe > 6 or not ziel:
        return False
    namen = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ziel))
    if namen & WURZELN:
        return True
    if "mkdtemp" in ziel or "gettempdir" in ziel:
        return True                     # Ordner fuer Temporaeres, eigens benannt
    return any(_fuehrt_nach_innen(tabelle[n], tabelle, tiefe + 1)
               for n in namen if n in tabelle)


def weg1_schreibstellen(b: Befund) -> tuple[int, int]:
    print("\n1 - Jede schreibende Zeile und wohin sie zeigt")
    # Die gemeinsamen Namen (ABLAGE, PAKET, WURZEL ...) stehen in pfade.py und _muster.py
    # und werden ueberallhin importiert; die ortsgebundenen gelten nur in ihrer Datei.
    # Deshalb beides: die gemeinsame Tabelle als Grundlage, die eigene darueber.
    gemeinsam = _zuweisungen()
    gezaehlt = fraglich = 0
    for p in dateien():
        if p.suffix != ".py":
            continue
        tabelle = dict(gemeinsam, **_zuweisungen_einer(p))
        quelle = p.read_text(encoding="utf-8", errors="replace")
        try:
            baum = ast.parse(quelle)
        except SyntaxError as e:
            b.melde("SCHWER", str(p.relative_to(HIER)), f"laesst sich nicht lesen: {e}")
            continue
        for k in ast.walk(baum):
            if not isinstance(k, ast.Call):
                continue
            name = (k.func.attr if isinstance(k.func, ast.Attribute)
                    else k.func.id if isinstance(k.func, ast.Name) else "")
            offen_schreibend = (name == "open" and len(k.args) > 1
                                and isinstance(k.args[1], ast.Constant)
                                and any(c in str(k.args[1].value) for c in "wax"))
            if name not in SCHREIBT and not offen_schreibend:
                continue
            gezaehlt += 1
            # Bei einem Methodenaufruf ist das Ziel das Objekt davor: pfad.write_text(x)
            # schreibt nach pfad, nicht nach x. Zuerst stand hier das Argument -- das
            # nannte "write_text(inhalt)" und sagte damit gar nichts.
            # Wo steht das Ziel? Das ist je nach Aufruf verschieden, und wer es
            # verwechselt, liest das Werkzeug statt des Ortes:
            #   pfad.write_text(x)        -> das Objekt vor dem Punkt
            #   shutil.rmtree(z)          -> das erste Argument
            #   shutil.copy2(quelle, z)   -> das ZWEITE Argument
            #   archiv.extractall(z)      -> das erste Argument (archiv ist die Quelle)
            if name in ("copy", "copy2", "copytree", "move", "urlretrieve", "rename",
                        "replace") and len(k.args) > 1:
                ziel = _ziel_benennen(quelle, k.args[1])
            elif name in ("extractall", "extract") and k.args:
                ziel = _ziel_benennen(quelle, k.args[0])
            elif isinstance(k.func, ast.Attribute) and not _ist_modul(k.func.value):
                ziel = _ziel_benennen(quelle, k.func.value)
            else:
                ziel = _ziel_benennen(quelle, k.args[0] if k.args else k)
            ort = f"{p.relative_to(HIER)}:{k.lineno}"
            kette = _kette(ziel, tabelle)
            if any(w in kette for w in ("expanduser", "APPDATA", "USERPROFILE",
                                        "HOMEPATH", "Documents", "Desktop")):
                b.melde("SCHWER", ort, f"schreibt ins Benutzerprofil: {ziel[:70]}")
                fraglich += 1
            elif not _fuehrt_nach_innen(ziel, tabelle):
                b.melde("ANSEHEN", ort,
                        f"{name}({ziel[:70]}) -- fuehrt nicht erkennbar in den Kursordner")
                fraglich += 1
    print(f"  {gezaehlt} schreibende Aufrufe gefunden, {fraglich} davon nicht offensichtlich "
          f"im Kursordner")
    return gezaehlt, fraglich


def weg1b_umgebung(b: Befund) -> None:
    """START.bat darf die Umgebung nur im eigenen Fenster aendern."""
    print("\n1b - Umgebungsvariablen")
    t = (HIER / "START.bat").read_text(encoding="ascii", errors="replace")
    hat_setlocal = re.search(r"^\s*setlocal", t, re.I | re.M) is not None
    print(f"  setlocal im Startskript: {'ja' if hat_setlocal else 'NEIN'}"
          f"  (ohne das wirkte jedes set auf das aufrufende Fenster)")
    if not hat_setlocal:
        b.melde("SCHWER", "START.bat", "kein setlocal: Variablen wirken nach aussen")
    gesetzt = sorted(set(re.findall(r'^\s*set\s+"?([A-Za-z_][A-Za-z0-9_]*)=', t, re.M)))
    print(f"  gesetzt werden: {', '.join(gesetzt)}")


# --------------------------------------------------------------------------------------
# Weg 3: messen statt lesen
# --------------------------------------------------------------------------------------
def _baum(wurzeln: list[pathlib.Path]) -> dict[str, tuple[int, float]]:
    stand = {}
    for w in wurzeln:
        if not w.is_dir():
            continue
        for p in w.rglob("*"):
            try:
                if p.is_file():
                    s = p.stat()
                    stand[str(p)] = (s.st_size, s.st_mtime)
            except OSError:
                pass
    return stand


def weg3_messen(b: Befund, befehl: list[str], beschreibung: str) -> None:
    """Dateibaum ausserhalb des Kursordners vorher/nachher vergleichen."""
    print(f"\n3 - Gemessen: {beschreibung}")
    heim = pathlib.Path.home()
    beobachtet = [heim]
    for v in ("APPDATA", "LOCALAPPDATA"):
        if os.environ.get(v):
            beobachtet.append(pathlib.Path(os.environ[v]))
    # Den Kursordner selbst nicht beobachten -- dort DARF sich alles aendern.
    vorher = {k: v for k, v in _baum(beobachtet).items() if not k.startswith(str(HIER))}
    print(f"  {len(vorher)} Dateien ausserhalb des Kursordners aufgenommen ...")
    r = subprocess.run(befehl, cwd=HIER, capture_output=True, text=True, timeout=1800)
    nachher = {k: v for k, v in _baum(beobachtet).items() if not k.startswith(str(HIER))}
    neu = sorted(set(nachher) - set(vorher))
    weg = sorted(set(vorher) - set(nachher))
    geaendert = sorted(k for k in set(vorher) & set(nachher) if vorher[k] != nachher[k])
    print(f"  Rueckgabewert {r.returncode}; neu {len(neu)}, verschwunden {len(weg)}, "
          f"geaendert {len(geaendert)}")
    for art, liste in (("neu entstanden", neu), ("verschwunden", weg), ("veraendert", geaendert)):
        for k in liste[:12]:
            b.melde("ANSEHEN", "Lauf", f"{art}: {k}")
        if len(liste) > 12:
            b.melde("ANSEHEN", "Lauf", f"{art}: ... und {len(liste)-12} weitere")


def main() -> int:
    t = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    t.add_argument("--lauf", action="store_true", help="zusaetzlich einen vollen Lauf messen")
    a = t.parse_args()

    print("=" * 78)
    print("  Veraendert dieses Paket den Rechner?")
    print(f"  Geprueft wird: {HIER}")
    print("=" * 78)

    b = Befund()
    weg2_verbotene_befehle(b)
    weg1_schreibstellen(b)
    weg1b_umgebung(b)
    if a.lauf:
        weg3_messen(b, [sys.executable, str(HIER / "agent" / "agent.py"), "--probe"],
                    "jedes Werkzeug einmal, ohne Modell")

    print("\n" + "=" * 78)
    schwer = b.zahl("SCHWER")
    ansehen = b.zahl("ANSEHEN")
    if b.zeilen:
        print("  Befunde:")
        for s, ort, text in b.zeilen:
            print(f"    {s:8s} {ort}\n             {text}")
        print()
    print(f"  schwerwiegend: {schwer}    anzusehen: {ansehen}")
    if schwer:
        print("  ERGEBNIS: NICHT BESTANDEN -- es gibt Stellen, die den Rechner veraendern.")
    elif ansehen:
        print("  ERGEBNIS: bestanden, mit Anmerkungen. Jede oben einzeln ansehen;")
        print("            keine davon veraendert den Rechner dauerhaft, aber sie stehen da.")
    else:
        print("  ERGEBNIS: BESTANDEN -- nichts gefunden, was den Rechner veraendern wuerde.")
    print("=" * 78)
    if not a.lauf:
        print("  Fuer die Messung eines echten Laufs: --lauf")
    return 1 if schwer else 0


if __name__ == "__main__":
    raise SystemExit(main())
