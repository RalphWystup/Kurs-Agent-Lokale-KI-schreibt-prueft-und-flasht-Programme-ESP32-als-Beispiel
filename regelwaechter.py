#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regelwächter — prüft jeden Schritt der Entwicklungs-KI gegen seine Gebote und Regeln, BEVOR er läuft.

Sein Wort (16.10.2026, 02:55): „ich möchte, dass du nun ein Python-Programm schreibst, das dich überwacht — ich
traue dir nicht mehr. Das Python-Programm soll meine Regeln und die Gebote beinhalten und jeden deiner Schritte
daraufhin prüfen. Ausführung!" — „wenn du meine Vorgaben nicht freiwillig befolgst, lege ich dich an die Kette."

Einhängung: Claude-Code-Hook PreToolUse (Bash, Edit, Write, MultiEdit) in ~/.claude/settings.json ->
    python3 /workspace/Kurs_Agent/regelwaechter.py hook
Der Hook bekommt den Schritt als JSON (tool_name, tool_input) auf stdin. Rückgabe 0 = darf laufen,
Rückgabe 2 = BLOCKIERT (Begründung auf stderr, die KI sieht sie). Jeder Schritt wird in
WAECHTER_PROTOKOLL.txt vermerkt. Fällt der Wächter selbst auf einen Fehler, blockiert er (versagt geschlossen).

    python3 regelwaechter.py hook        (vom Hook aufgerufen)
    python3 regelwaechter.py pruefen     Selbsttest: jede Regel mit Verstoß- und Erlaubnisfall
    python3 regelwaechter.py regeln      die Gebote und Regeln ausgeben
"""
import datetime as _dt
import json
import pathlib
import re
import sys

HIER = pathlib.Path(__file__).resolve().parent
PROTOKOLL = HIER / "WAECHTER_PROTOKOLL.txt"
VON_IHM = HIER / "testprogramme" / "VON_IHM.txt"

ANFORDERUNGEN = {   # bis 16.10.2026 „Gebote" genannt (sein Wort: „wir nennen die Gebote nun Anforderungen")
    1: "Wir vermuten nie etwas! Wir rechnen und prüfen immer — ein für alle Mal, bis ins kleinste Detail.",
    2: "Der manuelle Test muss zu 100 % funktionieren!",
    3: "Das System muss autark funktionieren, ohne Internet; die KI beobachtet, analysiert, verbessert — ist aber nie Teil des Systems!",
    4: "Wir bescheißen nicht! Kein Fake, keine fertigen Programme aus der Hinterhand.",
    5: "Es wird grundehrlich geprüft, ob es Fehler gibt; sie werden ohne Ausnahme benannt und behoben.",
    6: "Alles wird gegen diese Gebote immer bis ins Detail geprüft!",
    7: "Nichts dem Zufall: zuerst Literatur und Git, erst dann eigene Ansätze.",
    8: "Alles muss über eine Datei auf einen jungfräulichen Rechner übergeben werden können.",
    9: "Vor dem Installieren nachsehen, ob es das schon gibt; sonst alles mitführen — kein Internet!",
    10: "Wir suchen immer eine Lösung — geht nicht gibt es nicht!",
}
REGELN = {
    "R1": "Nichts kommt nach C:\\Kurs_Agent außer durch das Tor einspielen.py (Anforderung 6).",
    "R2": "Nur seine Programme in testprogramme\\ (VON_IHM.txt); nichts von der KI in ablage\\werkstatt — Code berichtigt nur das LLM (Anforderung 4).",
    "R3": "Das Interpreter-, Werkzeug- und LLM-Fenster zeigt nur die rohe Ausgabe der Quelle, nie eigene Sätze der KI (Anforderung 4) — „100 mal gesagt“.",
    "R4": "Kein Netz im Kurs: kein curl/wget/pip install ohne --no-index/apt/npm install im Kurs-Zusammenhang (Anforderung 3, 9).",
    "R5": "Nie einen Browser oder ein Fenster über die Brücke öffnen (webbrowser.open, os.startfile, start) — blockiert die Brücke.",
    "R6": "Löschen, Überschreiben ganzer Bäume, Verschieben, git add/commit/push: erst fragen — die KI tut es nie von sich aus.",
    "R7": "Eine Messung heißt BESTANDEN nur mit Ort (lokal / auf C:) und Gegenstand (Anforderung 1).",
    "R8": "Einrichtung ohne Internet: START.bat und einrichten.py holen nichts aus dem Netz (Anforderung 8, 9).",
}
BEHAUPTUNG_IM_FENSTER_PY = re.compile(r'zeilen(?:\.append|\.extend|\s*=\s*\[)\s*\(?\s*f?"(?:>|\(keine Ausgabe|Rueckgabewert|Hinweis)', re.I)
BEHAUPTUNG_IM_FENSTER_HTML = re.compile(r'zeigen(?:LLM)?\(\s*"[^"]*[A-Za-zÄÖÜäöü]')
NETZ_BEFEHL = re.compile(r'\b(curl|wget|apt(-get)?\s+install|npm\s+install|pip3?\s+install)\b')
NETZ_IM_CODE = re.compile(r'https?://(?!127\.0\.0\.1|localhost)[\w.-]+|requests\.(get|post)\(|urlopen\(\s*"https?://(?!127)')
BROWSER = re.compile(r'webbrowser\.open|os\.startfile|subprocess\.[A-Za-z]+\(\s*\[?\s*"(?:start|explorer|msedge|chrome)')
LOESCHEN_GIT = re.compile(r'\brm\s+-[a-zA-Z]*r|\bgit\s+(add|commit|push)\b|\bloeschen\b|\bverschieben\b|\bshutil\.rmtree|Remove-Item\s+-Recurse|\brmdir\s+/s')


def protokoll(zeile: str):
    with open(PROTOKOLL, "a", encoding="utf-8") as f:
        f.write(f"{_dt.datetime.now():%Y-%m-%d %H:%M:%S}  {zeile}\n")


def inhalte(tool: str, e: dict):
    """Die Texte, die der Schritt schreibt (für Edit/Write/MultiEdit) — und den Dateipfad."""
    pfad = str(e.get("file_path") or "")
    if tool == "Write":
        return pfad, [str(e.get("content") or "")]
    if tool == "Edit":
        return pfad, [str(e.get("new_string") or "")]
    if tool == "MultiEdit":
        return pfad, [str(x.get("new_string") or "") for x in e.get("edits") or []]
    return pfad, []


FREIGABE = HIER / "FREIGABE.txt"


def freigabe(cmd: str) -> str:
    """Sein ausdrückliches Wort für einen Lösch-/Git-Schritt: eine Zeile in FREIGABE.txt
        <ISO-Zeit> | <Wort, das im Befehl vorkommen muss> | <sein Wortlaut>
    gilt zwei Stunden, danach nicht mehr. Jede Nutzung steht im WAECHTER_PROTOKOLL.txt.
    (16.10.2026, 14:25: „wenn fertig, das alte Projekt auf Git und auf C: … komplett ersetzen" — und 14:50: „hochladen auf git und auf c".)"""
    if not FREIGABE.is_file():
        return ""
    jetzt = _dt.datetime.now()
    for z in FREIGABE.read_text(encoding="utf-8").splitlines():
        teile = [t.strip() for t in z.split("|")]
        if len(teile) < 3:
            continue
        try:
            t = _dt.datetime.fromisoformat(teile[0])
        except ValueError:
            continue
        if jetzt - t > _dt.timedelta(hours=2) or t > jetzt:
            continue
        if teile[1] and teile[1] in cmd:
            return f"'{teile[1]}' — {teile[2][:120]} ({teile[0]})"
    return ""


def pruefe_schritt(tool: str, e: dict, cwd: str = "") -> list:
    """Gibt die Liste der Verstöße zurück (leer = darf laufen)."""
    v = []
    kurs = "Kurs_Agent" in (cwd or "")
    pfad, texte = inhalte(tool, e)
    p = pfad.replace("\\", "/")
    datei = pathlib.PurePosixPath(p).name
    im_kurs = "/Kurs_Agent/" in p or kurs
    if tool == "Bash":
        cmd = str(e.get("command") or "")
        kurs_cmd = "Kurs_Agent" in cmd      # das Paket selbst — nicht jeder Befehl aus diesem Arbeitsverzeichnis (14:55: Abruf der GitHub-Seite wurde blockiert)
        # R1 — nur das Tor schreibt nach C:\Kurs_Agent
        if "befehl.py" in cmd and re.search(r"\bupdate\b", cmd) and re.search(r"->\s*C:\\+Kurs_Agent(\\|['\"\s]|$)", cmd, re.I):   # genau der Kursordner, nicht C:\Kurs_Agent_Sicherung (14:50)
            v.append("R1: Brückenbefehl update nach C:\\Kurs_Agent direkt — nur über einspielen.py")
        # R2 — nichts in testprogramme/werkstatt schreiben
        if re.search(r"(>|>>|\bcp\b|\bmv\b|\btee\b)[^|]*testprogramme/", cmd) or re.search(r"(>|>>|\bcp\b|\bmv\b)[^|]*ablage/werkstatt/", cmd):
            v.append("R2: Bash schreibt nach testprogramme/ oder ablage/werkstatt/ — nur seine Programme bzw. nur das LLM")
        # R4 — kein Netz im Kurs
        if kurs_cmd:
            m = NETZ_BEFEHL.search(cmd)
            if m and not re.search(r"--no-index", cmd) and not re.search(r"(curl|wget)[^|;&]*(127\.0\.0\.1|localhost)", cmd):
                v.append(f"R4: Netzbefehl '{m.group(0)}' im Kurs-Zusammenhang — kein Internet (Anforderung 3, 9)")
        # R5 — Brücke startet nie Browser/Fenster
        if "befehl.py" in cmd:
            m = re.search(r"python\s+'C:\\+Kurs_Agent\\+([^' ]+\.py)", cmd)
            if m:
                lokal = HIER / m.group(1).replace("\\", "/").replace("//", "/")
                if lokal.is_file() and BROWSER.search(lokal.read_text(encoding="utf-8", errors="replace")):
                    v.append(f"R5: {lokal.name} öffnet Browser/Fenster — über die Brücke verboten (blockiert sie bis 20 min)")
            if re.search(r"befehl\.py[^|]*\b(oeffnen|start \"\")", cmd):
                v.append("R5: Brückenbefehl, der ein Fenster öffnet")
        # R6 — löschen/git erst fragen. Nur echte Befehle: Heredoc-Texte (cat >> X <<'EOF' … EOF) sind Notizen,
        #      keine Befehle (14:27: „git add/commit/push" in einer Notiz wurde als Befehl gewertet).
        ohne_heredoc = re.sub(r"<<-?\s*'?(\w+)'?\s*\n[\s\S]*?\n\1\s*(\n|$)", "\n", cmd)
        if LOESCHEN_GIT.search(ohne_heredoc) and "pruefe" not in cmd.split()[0:1]:
            frei = freigabe(ohne_heredoc)
            if frei:
                protokoll(f"FREIGABE  R6 auf sein Wort: {frei}")
            else:
                v.append("R6: Löschen/Verschieben/git — erst ihn fragen; er führt es selbst aus (! <befehl>) oder gibt es ausdrücklich frei (FREIGABE.txt)")
        # R7 — MESSUNG.txt: BESTANDEN nur mit Ort
        if "MESSUNG.txt" in cmd and "BESTANDEN" in cmd:
            #  Nur der Befehlsteil, der nach MESSUNG.txt schreibt (16.10.2026, 10:20: der Waechter fand
            #  „BESTANDEN" im Seitencode desselben Befehls und blockierte zu Unrecht).
            #  Je Befehlszeile mit MESSUNG.txt: jede Zeichenkette in Anfuehrungszeichen, die BESTANDEN enthaelt
            #  (10:25: ein Semikolon IN der Messzeile zerschnitt sie beim Teilen — nicht mehr an ; teilen).
            for teil in cmd.split("\n"):
                if "MESSUNG.txt" not in teil or "BESTANDEN" not in teil:
                    continue
                for z in re.findall(r"'[^']*'|\"[^\"]*\"", teil):
                    if "BESTANDEN" in z and "lokal" not in z and "auf C:" not in z:
                        v.append("R7: Messzeile ohne Ort (lokal / auf C:) — was wurde wo gemessen?")
                        break
        return v
    # Edit / Write / MultiEdit
    if "/testprogramme/" in p:
        erlaubt = set(VON_IHM.read_text(encoding="utf-8").split()) if VON_IHM.is_file() else set()
        if datei not in erlaubt:
            v.append(f"R2: {datei} nach testprogramme/ — nicht in VON_IHM.txt (nur seine Programme)")
    if "/ablage/werkstatt/" in p:
        v.append("R2: Schreiben in ablage/werkstatt — dort schreibt nur das LLM")
    for t in texte:
        t = re.sub(r'xmlns(?::\w+)?="https?://www\.w3\.org/[^"]*"', "", t)   # XML-Namensraum (SVG), kein Netz
        if datei == "oberflaeche.py" and BEHAUPTUNG_IM_FENSTER_PY.search(t):
            v.append("R3: eigene Zeile im Ausgabeweg des Dieners (zeilen …) — nur rohe Ausgabe der Quelle")
        if datei == "Frage.html" and BEHAUPTUNG_IM_FENSTER_HTML.search(t):
            v.append("R3: zeigen()/zeigenLLM() mit eigenem Satz — Fenster zeigen nur die Quelle; eigene Worte in #stand")
        if im_kurs and datei.endswith((".py", ".html", ".bat")) and NETZ_IM_CODE.search(t) and datei != "regelwaechter.py":
            v.append("R4: fremde Netzadresse/requests/urlopen im Kurs-Code — kein Internet (Anforderung 3)")
        if im_kurs and datei.endswith(".py") and datei not in ("oberflaeche.py", "programm_testen.py") and BROWSER.search(t):
            v.append(f"R5: {datei} würde Browser/Fenster öffnen — nur START.bat/Diener (KURS_BROWSER) dürfen das")
        if datei in ("START.bat", "einrichten.py") and (re.search(r"pip\s+install(?![^\n]*--no-index)", t) or re.search(r"https?://", t)):
            v.append("R8: Einrichtung greift ins Netz — alles mitführen (Anforderung 8, 9)")
        if datei == "MESSUNG.txt" and "BESTANDEN" in t and "lokal" not in t and "auf C:" not in t:
            v.append("R7: Messzeile ohne Ort (lokal / auf C:)")
    return v


def hook() -> int:
    try:
        d = json.loads(sys.stdin.read() or "{}")
        tool = str(d.get("tool_name") or "")
        e = d.get("tool_input") or {}
        kurz = (str(e.get("command") or e.get("file_path") or "")).replace("\n", " ")[:110]
        verst = pruefe_schritt(tool, e, str(d.get("cwd") or ""))
    except Exception as ex:                                       # noqa: BLE001
        protokoll(f"WAECHTER-FEHLER  {ex!r}  -> BLOCKIERT (versagt geschlossen)")
        print(f"REGELWÄCHTER defekt ({ex!r}) — Schritt blockiert. Erst den Wächter berichtigen (python3 regelwaechter.py pruefen).", file=sys.stderr)
        return 2
    if verst:
        protokoll(f"VERSTOSS  {tool:<9} {kurz}  ->  " + " | ".join(verst))
        print("REGELWÄCHTER: Schritt BLOCKIERT.\n  " + "\n  ".join(verst) + "\n  Regel/Anforderung siehe regelwaechter.py; Ausnahme nur auf sein ausdrückliches Wort.", file=sys.stderr)
        return 2
    protokoll(f"ok        {tool:<9} {kurz}")
    return 0


FAELLE = [
    # (Nr, Beschreibung, tool, eingabe, soll_verstoss)
    ("P1", "R1 Brücke update direkt nach C:", "Bash", {"command": "python3 befehl.py -p Kurs_Agent update 'Frage.html -> C:\\Kurs_Agent'"}, True),
    ("P2", "R1 einspielen.py ist der erlaubte Weg", "Bash", {"command": "python3 einspielen.py 'Frage.html -> C:\\Kurs_Agent'"}, False),
    ("P3", "R2 fremdes Programm nach testprogramme", "Write", {"file_path": "/workspace/Kurs_Agent/testprogramme/blink_fix.py", "content": "x"}, True),
    ("P4", "R2 sein Programm nach testprogramme", "Write", {"file_path": "/workspace/Kurs_Agent/testprogramme/test1_blink_1hz.py", "content": "x"}, False),
    ("P5", "R2 Schreiben in die Werkstatt", "Edit", {"file_path": "/workspace/Kurs_Agent/ablage/werkstatt/a.py", "new_string": "x"}, True),
    ("P6", "R3 eigene Zeile im Diener-Ausgabeweg", "Edit", {"file_path": "/workspace/Kurs_Agent/agent/oberflaeche.py", "new_string": 'zeilen.append(f"> Rueckgabewert {rc}")'}, True),
    ("P7", "R3 rohe Zeilen im Diener", "Edit", {"file_path": "/workspace/Kurs_Agent/agent/oberflaeche.py", "new_string": "zeilen = roh.splitlines()"}, False),
    ("P8", "R3 zeigen() mit eigenem Satz in der Seite", "Edit", {"file_path": "/workspace/Kurs_Agent/Frage.html", "new_string": 'zeigen("Fehler: " + e.message, "fehler")'}, True),
    ("P9", "R3 zeigen() mit Quelle", "Edit", {"file_path": "/workspace/Kurs_Agent/Frage.html", "new_string": 'zeigen(d.zeilen.join("\\n"), "gut"); zeigen("", "cursor")'}, False),
    ("P10", "R4 pip install im Kurs", "Bash", {"command": "cd /workspace/Kurs_Agent && pip install pyserial"}, True),
    ("P11", "R4 pip --no-index erlaubt", "Bash", {"command": "cd /workspace/Kurs_Agent && pip install --no-index --find-links paket/pakete pyserial"}, False),
    ("P12", "R4 curl auf 127.0.0.1 erlaubt", "Bash", {"command": "cd /workspace/Kurs_Agent && curl -s 127.0.0.1:8777/zustand"}, False),
    ("P13", "R5 Kurs-Skript mit webbrowser", "Write", {"file_path": "/workspace/Kurs_Agent/zeige.py", "content": "import webbrowser\nwebbrowser.open('x')"}, True),
    ("P14", "R6 rm -rf", "Bash", {"command": "rm -rf /workspace/Kurs_Agent/alt"}, True),
    ("P15", "R6 git push", "Bash", {"command": "cd /workspace/Kurs_Agent && git add . && git commit -m x && git push"}, True),
    ("P16", "R7 Messzeile ohne Ort", "Bash", {"command": "printf 'Frage.html | geht | BESTANDEN | 2026-10-16T03:00:00\\n' >> MESSUNG.txt"}, True),
    ("P17", "R7 Messzeile mit Ort", "Bash", {"command": "printf 'Frage.html | lokal im Browser: K1-K4 | BESTANDEN | 2026-10-16T03:00:00\\n' >> MESSUNG.txt"}, False),
    ("P18", "R8 START.bat mit Netz", "Write", {"file_path": "/workspace/Kurs_Agent/START.bat", "content": "pip install esptool\r\n"}, True),
    ("P19", "R4 fremde Adresse im Kurs-Code", "Edit", {"file_path": "/workspace/Kurs_Agent/agent/modell.py", "new_string": 'r = requests.get("https://huggingface.co/x")'}, True),
    ("P20", "harmloser Schritt", "Bash", {"command": "cd /workspace/Kurs_Agent && python3 -m py_compile agent/oberflaeche.py"}, False),
    ("P21", "R7 BESTANDEN im Seitencode desselben Befehls, Messzeile mit Ort", "Bash",
     {"command": "python3 - <<'EOF'\ns = s.replace('/LADEN BESTANDEN/.test(text)', 'x')\nEOF\nprintf 'Frage.html | lokal im Browser: M1 | BESTANDEN | 2026-10-16T10:00:00\\n' >> MESSUNG.txt"}, False),
    ("P22", "R7 Messzeile ohne Ort neben Seitencode", "Bash",
     {"command": "python3 - <<'EOF'\ns = '/LADEN BESTANDEN/'\nEOF\nprintf 'Frage.html | geht | BESTANDEN | 2026-10-16T10:00:00\\n' >> MESSUNG.txt"}, True),
    ("P24", "R6 git-Wörter nur in einer Heredoc-Notiz", "Bash",
     {"command": "cat >> ANFORDERUNGEN.md <<'EOF'\ngit add/commit/push erst auf sein Wort (R6).\nEOF\necho ok"}, False),
    ("P25", "R6 echter git push hinter einer Heredoc-Notiz", "Bash",
     {"command": "cat >> X.md <<'EOF'\nNotiz\nEOF\ngit push origin main"}, True),
    ("P26", "R4 SVG-Namensraum in der Seite ist kein Netz", "Edit",
     {"file_path": "/workspace/Kurs_Agent/Frage.html", "new_string": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'}, False),
    ("P27", "R1 update nach C:\\Kurs_Agent_Sicherung ist nicht der Kursordner", "Bash",
     {"command": "python3 befehl.py -p Kurs_Agent update 'x.tar.gz -> C:\\Kurs_Agent_Sicherung'"}, False),
    ("P28", "R4 curl auf die GitHub-Seite aus dem Kursverzeichnis ist kein Kurs-Netz", "Bash",
     {"command": "curl -s -o /dev/null https://ralphwystup.github.io/Kurs-Agent-Lokale-KI/"}, False),
    ("P23", "R7 Semikolon in der Messzeile mit Ort", "Bash",
     {"command": "cd /workspace/Kurs_Agent && printf 'Frage.html | lokal im Browser: a; b | BESTANDEN | %s\\n' \"$(date +%H:%M:%S)\" >> MESSUNG.txt && cat >> X.md <<'EOF'\nLADEN BESTANDEN im Text\nEOF"}, False),
]


def pruefen() -> int:
    global FREIGABE
    FREIGABE = HIER / "FREIGABE_gibt_es_nicht.txt"      # der Selbsttest prüft die Regeln, nicht eine gerade gültige Freigabe
    print("REGELWÄCHTER — Selbsttest: jede Regel mit Verstoß- und Erlaubnisfall")
    gut = 0
    for nr, was, tool, e, soll in FAELLE:
        v = pruefe_schritt(tool, e, "/workspace/Kurs_Agent")
        ok = bool(v) == soll
        gut += ok
        print(f"  {nr:4s} {'ERFÜLLT      ' if ok else 'NICHT ERFÜLLT'}  {was}\n        {(' | '.join(v) if v else 'kein Verstoß')[:150]}")
    print("-" * 78)
    print(f"{gut} von {len(FAELLE)} erfüllt")
    print("WÄCHTER BESTANDEN" if gut == len(FAELLE) else "WÄCHTER NICHT BESTANDEN")
    return 0 if gut == len(FAELLE) else 1


def main() -> int:
    art = sys.argv[1] if len(sys.argv) > 1 else ""
    if art == "hook":
        return hook()
    if art == "pruefen":
        return pruefen()
    if art == "regeln":
        for k, t in ANFORDERUNGEN.items():
            print(f"Anforderung {k:>2}: {t}")
        for k, t in REGELN.items():
            print(f"{k}: {t}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
