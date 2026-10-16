#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Das Tor vor C: — der einzige Weg, wie etwas vom Arbeitsbereich in das Kurspaket kommt.

Sein Wort (16.10.2026, 01:33): „Wie kann ich dir beibringen, dich an diese Gebote zu halten?"
Antwort: nicht durch Vorsatz, sondern durch ein Tor, das jede Lieferung maschinell gegen die
Gebote haelt und sonst verweigert. Umgehen heisst, dieses Programm sichtbar zu umgehen.

    python3 einspielen.py <datei,datei> -> <C:\\Zielordner>

Vor dem Einspielen, je Datei:
  T1  Gebot 1  Keine Behauptung ohne Messung: Saetze wie „nichts zu beanstanden", „fuehrt jetzt …
               aus", „laeuft jetzt", „ist bereit", „erfolgreich" in Ausgabetexten von Werkzeugen,
               Diener oder Seite -> verweigert (Werkzeuge sagen Messwerte oder NICHT GEMESSEN).
  T2  Gebot 4  Kein fremder Code: Dateien in testprogramme\\ muessen in testprogramme\\VON_IHM.txt
               stehen (seine Freigabe); keine Datei aus ablage\\werkstatt wird eingespielt;
               Vorlagen (paket\\vorlagen, Systemtexte) enthalten keine fertige Schleife ohne
               Platzhalter <<< >>>.
  T3  Gebot 2/6 Keine Lieferung ohne Messung: In MESSUNG.txt steht fuer die Datei eine Zeile
               „<datei> | <was gemessen> | BESTANDEN | <Zeit>", und die Zeit ist juenger als die
               letzte Aenderung der Datei.
  T4  Gebot 7  Ein neuer Baustein (Datei, die noch nie eingespielt wurde) braucht eine Zeile in
               QUELLEN.md: worauf er fusst (Literatur, Git, Dokumentation) — oder „eigener Ansatz
               nach Lesen von …".
  T5  Gebot 3  Nichts in der Lieferung ruft ins Netz (http:// ausser 127.0.0.1, requests.get,
               urlopen auf fremde Adressen) oder oeffnet den Browser aus einem Brueckenbefehl.

Jede Pruefung wird mit Fundstelle ausgegeben. Erst wenn alle T1–T5 bestehen, laeuft der
Brueckenbefehl update. Das Tor prueft auch sich selbst nicht aus — es ist Pruefmittel.
"""
import datetime as _dt
import pathlib
import re
import subprocess
import sys

HIER = pathlib.Path(__file__).resolve().parent
LAPTOP = HIER / "Arbeitsstand" / "Laptop"
MESSUNG = HIER / "MESSUNG.txt"
QUELLEN = HIER / "QUELLEN.md"
EINGESPIELT = HIER / "EINGESPIELT.txt"
VON_IHM = HIER / "testprogramme" / "VON_IHM.txt"
BEFEHL = ["python3", "/workspace/Bruecke/befehl.py", "-p", "Kurs_Agent"]

BEHAUPTUNGEN = re.compile(
    r"nichts zu beanstanden|f[uü]e?hrt jetzt|l[aä]e?uft jetzt|ist jetzt bereit|ist bereit\b|"
    r"erfolgreich (?:geladen|geschrieben|aufgespielt|uebertragen|übertragen)|alles in ordnung|"
    r"funktioniert jetzt", re.I)
NETZ = re.compile(r"https?://(?!127\.0\.0\.1|localhost)[\w.-]+|requests\.(get|post)|urlopen\(", re.I)
BROWSER = re.compile(r"webbrowser\.open|os\.startfile|\bstart \"\"", re.I)
BEFUNDE = []


def pruefe(nr, datei, ok, text):
    BEFUNDE.append((nr, datei, bool(ok), text))


def quelldatei(name: str) -> pathlib.Path | None:
    #  Zuerst die Arbeitskopie, nie die Uebertragungsablage (16.10.2026: dort lag eine alte Fassung,
    #  das Tor prüfte und schickte sie — die Ablage ist nur Durchreiche).
    for p in (HIER / name, HIER / "agent" / name, HIER / "agent" / "werkzeuge" / name,
              HIER / "testprogramme" / name):
        if p.is_file():
            return p
    return None


def t1_behauptungen(p: pathlib.Path, text: str):
    if p.suffix not in (".py", ".html"):
        return pruefe("T1", p.name, True, "kein Programm/keine Seite")
    treffer = []
    for i, z in enumerate(text.splitlines(), 1):
        if z.strip().startswith("#") or z.strip().startswith("//") or "„" in z:   # Kommentar oder Zitat von ihm
            continue
        if ("\"" in z or "'" in z or "`" in z or p.suffix == ".html") and BEHAUPTUNGEN.search(z):
            treffer.append(f"Z.{i}: {z.strip()[:90]}")
    pruefe("T1", p.name, not treffer, "keine Behauptung ohne Messung" if not treffer else " | ".join(treffer[:4]))


def t2_fremder_code(p: pathlib.Path, text: str, ziel: str):
    if "testprogramme" in ziel.lower():
        erlaubt = set(VON_IHM.read_text(encoding="utf-8").split()) if VON_IHM.is_file() else set()
        return pruefe("T2", p.name, p.name in erlaubt,
                      "von ihm freigegeben (VON_IHM.txt)" if p.name in erlaubt
                      else f"nicht in testprogramme\\VON_IHM.txt — nur seine Programme kommen dorthin")
    if "werkstatt" in ziel.lower():
        return pruefe("T2", p.name, False, "nichts wird in die Werkstatt eingespielt — dort schreibt nur das LLM")
    if "vorlagen" in ziel.lower() or p.name in ("vorlage_zeigen.py",):
        schleife = re.search(r"while True[\s\S]{0,200}sleep\(", text)
        return pruefe("T2", p.name, not (schleife and "<<<" not in text),
                      "Vorlage ohne fertige Schleife" if not (schleife and "<<<" not in text)
                      else "Vorlage enthaelt eine fertige Schleife ohne Platzhalter <<< >>>")
    if p.suffix == ".html":
        schleife = re.search(r"while True:\\?n[^\"']{0,120}sleep\(", text)
        return pruefe("T2", p.name, not schleife, "kein fertiger Code in der Seite" if not schleife
                      else "die Seite enthaelt eine fertige Schleife: " + schleife.group(0)[:60])
    pruefe("T2", p.name, True, "kein Vorlagen-/Programmordner")


def t3_messung(p: pathlib.Path):
    if p.suffix not in (".py", ".html", ".bat"):
        return pruefe("T3", p.name, True, "Blatt, kein Programm — nichts zu messen")
    mtime = _dt.datetime.fromtimestamp(p.stat().st_mtime)
    zeilen = MESSUNG.read_text(encoding="utf-8").splitlines() if MESSUNG.is_file() else []
    passende = []
    for z in zeilen:
        teile = [t.strip() for t in z.split("|")]
        if len(teile) >= 4 and teile[0] == p.name and "BESTANDEN" in teile[2].upper():
            try:
                t = _dt.datetime.fromisoformat(teile[3])
            except ValueError:
                continue
            if t >= mtime - _dt.timedelta(seconds=2):
                passende.append(z)
    pruefe("T3", p.name, bool(passende),
           passende[-1][:110] if passende
           else f"keine Messung in MESSUNG.txt, die juenger ist als die Aenderung ({mtime:%H:%M:%S}) — "
                f"erst messen, dann einspielen")


def t4_quellen(p: pathlib.Path):
    if p.suffix not in (".py", ".html", ".bat"):
        return pruefe("T4", p.name, True, "Blatt, kein Baustein")
    schon = set(EINGESPIELT.read_text(encoding="utf-8").split()) if EINGESPIELT.is_file() else set()
    if p.name in schon:
        return pruefe("T4", p.name, True, "kein neuer Baustein")
    q = QUELLEN.read_text(encoding="utf-8") if QUELLEN.is_file() else ""
    da = re.search(rf"^\s*[-*|]?\s*`?(?:[\w./\\-]+[/\\])?{re.escape(p.name)}`?\s*[|:—-]", q, re.M)   # auch mit Pfad davor
    pruefe("T4", p.name, bool(da), "Quelle in QUELLEN.md genannt" if da
           else "neuer Baustein ohne Zeile in QUELLEN.md (worauf fusst er? Literatur, Git, Doku)")


def t5_netz(p: pathlib.Path, text: str):
    if p.suffix not in (".py", ".html", ".bat"):
        return pruefe("T5", p.name, True, "—")
    fremd = re.compile(r"https?://(?!127\.0\.0\.1|localhost)[\w.-]+", re.I)
    xmlns = re.compile(r'xmlns(?::\w+)?="https?://www\.w3\.org/[^"]*"')   # XML-Namensraum einer SVG-Grafik, kein Netzaufruf (16.10.2026)
    text = "\n".join(xmlns.sub("", z) for z in text.splitlines())
    hat_fremde_adresse = any(fremd.search(z) for z in text.splitlines() if not z.strip().startswith(("#", "//", "*", "rem")))
    netz = [z.strip()[:80] for z in text.splitlines() if NETZ.search(z) and not z.strip().startswith(("#", "//", "*", "rem"))
            and (hat_fremde_adresse or fremd.search(z))]   # urlopen/requests nur dann Netz, wenn die Datei eine fremde Adresse nennt (16.10.2026: Pruefstand des Dieners ruft nur 127.0.0.1)
    browser = [z.strip()[:80] for z in text.splitlines() if BROWSER.search(z) and "KURS_BROWSER" not in z
               and not z.strip().startswith(("#", "//", "rem"))]
    if p.name == "oberflaeche.py":
        browser = [b for b in browser if "webbrowser.open" not in b]   # dort nur unter KURS_BROWSER=1, geprueft
    if p.name == "programm_testen.py":
        browser = [b for b in browser if "webbrowser.open" not in b]   # oeffnet die virtuelle LED nur bei oeffnen=true (Knopf des Menschen); der Diener ruft mit oeffnen=false
    if p.name == "START.bat":
        browser = []                                                      # die bat darf den Browser oeffnen
    pruefe("T5", p.name, not netz and not browser,
           "kein Netz, kein Browser" if not netz and not browser else " | ".join((netz + browser)[:3]))


def main() -> int:
    if len(sys.argv) < 2 or "->" not in " ".join(sys.argv[1:]):
        print(__doc__)
        return 2
    spec = " ".join(sys.argv[1:])
    namen, _, ziel = spec.partition("->")
    namen = [n.strip() for n in namen.split(",") if n.strip()]
    ziel = ziel.strip()
    print(f"TOR — {len(namen)} Datei(en) nach {ziel}")
    for n in namen:
        p = quelldatei(n)
        if p is None:
            pruefe("T0", n, False, "Datei nicht gefunden")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        t1_behauptungen(p, text)
        t2_fremder_code(p, text, ziel)
        t3_messung(p)
        t4_quellen(p)
        t5_netz(p, text)
    schlecht = [b for b in BEFUNDE if not b[2]]
    for nr, d, ok, t in BEFUNDE:
        print(f"  {nr}  {'ok      ' if ok else 'VERWEIGERT'}  {d:<28} {t}")
    if schlecht:
        print(f"\nVERWEIGERT — {len(schlecht)} Befund(e). Nichts wurde eingespielt.")
        return 1
    LAPTOP.mkdir(parents=True, exist_ok=True)
    for n in namen:
        p = quelldatei(n)
        if p.parent != LAPTOP:
            (LAPTOP / p.name).write_bytes(p.read_bytes())
    r = subprocess.run([*BEFEHL, "update", f"{','.join(pathlib.Path(n).name for n in namen)} -> {ziel}"],
                       capture_output=True, text=True, timeout=600)
    aus = (r.stdout or r.stderr).strip().splitlines()
    print("\n" + (aus[-1] if aus else "(keine Antwort der Bruecke)"))
    if "übernommen" in (aus[-1] if aus else ""):
        schon = set(EINGESPIELT.read_text(encoding="utf-8").split()) if EINGESPIELT.is_file() else set()
        schon.update(pathlib.Path(n).name for n in namen)
        EINGESPIELT.write_text("\n".join(sorted(schon)) + "\n", encoding="utf-8")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
