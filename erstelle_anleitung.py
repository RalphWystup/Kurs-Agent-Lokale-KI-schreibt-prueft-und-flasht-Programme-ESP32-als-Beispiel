#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erzeugt ANLEITUNG.html — die Bedienanleitung, die im Ordner mitliegt.

Die Fassungsnummer steht **hier** und sonst nirgends; Dateiname und Kopfzeile der Seite
leiten sich daraus ab.

Die Tabelle der Werkzeuge wird nicht abgeschrieben, sondern von den Werkzeugen selbst
erfragt (``--beschreibung``). Eine abgeschriebene Tabelle stimmt genau bis zur ersten
Aenderung; eine erfragte stimmt immer oder das Erzeugen scheitert.
"""
from __future__ import annotations
import json, subprocess, sys, pathlib, datetime, html

FASSUNG = "3.1"
HIER = pathlib.Path(__file__).resolve().parent
ZIEL = HIER / f"Kurs_Agent_{FASSUNG}.html"


# Ein Ablageort fuer Bilder (Grundsatz: sauber und konsistent) — bis 04.10.2026 zeigte dieser Pfad in
# einen Zwischenordner einer frueheren Sitzung.
BILDER = HIER / "Bilder" / "anleitung"


def bild(name: str, breite=940) -> str:
    """Ein Bildschirmfoto als eingebettetes JPEG — damit die Seite eigenstaendig bleibt.

    Ein <img src="..."> auf eine Datei daneben waere kleiner, aber dann ist die Seite kein
    Blatt mehr, sondern ein Ordner. Verschickt jemand nur die HTML, fehlen die Bilder.
    """
    from PIL import Image
    import base64, io
    d = BILDER / name
    if not d.is_file():
        return f'<div class="kopf">[Bild fehlt: {name}]</div>'
    b = Image.open(d).convert("RGB")
    if b.width > breite:
        b = b.resize((breite, round(b.height * breite / b.width)), Image.LANCZOS)
    puffer = io.BytesIO()
    b.save(puffer, "JPEG", quality=82, optimize=True)
    roh = base64.b64encode(puffer.getvalue()).decode()
    return f'<img src="data:image/jpeg;base64,{roh}" alt="{name}">'


def werkzeuge() -> list:
    w = []
    for d in sorted((HIER / "agent" / "werkzeuge").glob("*.py")):
        if d.name.startswith("_"):
            continue
        r = subprocess.run([sys.executable, str(d), "--beschreibung"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            raise SystemExit(f"{d.name} liefert keine Beschreibung — die Seite waere falsch.")
        b = json.loads(r.stdout)
        b["dateiname"] = d.name
        w.append(b)
    return w


SCHAUBILD = '''
<svg viewBox="0 0 980 300" width="100%" role="img" aria-label="Der Weg vom Auftrag zur blinkenden LED">
 <defs><marker id="sp" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
  <polygon points="0 0, 9 3.5, 0 7" fill="#4a5568"/></marker></defs>
 <rect x="8" y="8" width="964" height="284" rx="10" fill="#f7fafc" stroke="#cbd5e0"/>
 <text x="24" y="32" font-size="14.5" font-weight="600" fill="#2d3748">Der Weg vom Satz zur blinkenden LED</text>

 <rect x="26" y="52" width="150" height="76" rx="7" fill="#fff" stroke="#a0aec0"/>
 <text x="40" y="76" font-size="12.5" font-weight="600" fill="#2d3748">Ihr Auftrag</text>
 <text x="40" y="96" font-size="11.5" fill="#718096">ein Satz auf Deutsch</text>
 <text x="40" y="113" font-size="11.5" fill="#718096">im Menü eingetippt</text>

 <rect x="216" y="52" width="150" height="76" rx="7" fill="#fff" stroke="#4299e1" stroke-width="2"/>
 <text x="230" y="76" font-size="12.5" font-weight="600" fill="#2b6cb0">Modell + Agent</text>
 <text x="230" y="96" font-size="11.5" fill="#718096">wählt ein Werkzeug</text>
 <text x="230" y="113" font-size="11.5" fill="#718096">liest das Ergebnis</text>

 <rect x="406" y="52" width="150" height="76" rx="7" fill="#fff" stroke="#48bb78" stroke-width="2"/>
 <text x="420" y="76" font-size="12.5" font-weight="600" fill="#276749">schreib_datei</text>
 <text x="420" y="96" font-size="11.5" fill="#718096">das Programm</text>
 <text x="420" y="113" font-size="11.5" fill="#718096">entsteht</text>

 <rect x="596" y="52" width="160" height="76" rx="7" fill="#fff" stroke="#ed8936" stroke-width="2.5"/>
 <text x="610" y="76" font-size="12.5" font-weight="600" fill="#9c4221">programm_testen</text>
 <text x="610" y="96" font-size="11.5" fill="#718096">läuft ohne Hardware</text>
 <text x="610" y="113" font-size="11.5" fill="#718096">LED auf dem Schirm</text>

 <rect x="796" y="52" width="152" height="76" rx="7" fill="#fff" stroke="#48bb78" stroke-width="2"/>
 <text x="810" y="76" font-size="12.5" font-weight="600" fill="#276749">esp32_uebertragen</text>
 <text x="810" y="96" font-size="11.5" fill="#718096">dieselbe Datei</text>
 <text x="810" y="113" font-size="11.5" fill="#718096">auf das Gerät</text>

 <line x1="176" y1="90" x2="210" y2="90" stroke="#4a5568" stroke-width="1.6" marker-end="url(#sp)"/>
 <line x1="366" y1="90" x2="400" y2="90" stroke="#4a5568" stroke-width="1.6" marker-end="url(#sp)"/>
 <line x1="556" y1="90" x2="590" y2="90" stroke="#4a5568" stroke-width="1.6" marker-end="url(#sp)"/>
 <line x1="756" y1="90" x2="790" y2="90" stroke="#4a5568" stroke-width="1.6" marker-end="url(#sp)"/>

 <path d="M 676 132 L 676 170 L 481 170 L 481 134" fill="none" stroke="#ed8936"
       stroke-width="1.6" stroke-dasharray="5 3" marker-end="url(#sp)"/>
 <text x="500" y="187" font-size="11.5" fill="#9c4221">bricht der Test ab, wird der Quelltext berichtigt — und erneut geprüft</text>

 <rect x="26" y="212" width="922" height="60" rx="7" fill="#edf2f7" stroke="#cbd5e0"/>
 <text x="42" y="236" font-size="12" fill="#4a5568">
   <tspan font-weight="600">Ohne ESP32 endet die Kette einen Schritt früher.</tspan>
   <tspan x="42" dy="19">Der orange Schritt ist dann das Ergebnis: das Programm läuft, die LED blinkt auf dem Bildschirm — nur eben nicht am Steckbrett.</tspan>
 </text>
</svg>'''


def neun_fragen() -> str:
    """Tabelle der neun festen Anfragen (agent/auftraege.json), live am Laptop mit Coder-3B und ESP32 an COM3,
    aus pruefstand/lauf_neun_fragen.json (vom Prüfstandsskript aus den Ereignissen des Agenten erzeugt)."""
    import json as _json
    d = HIER / "pruefstand" / "lauf_neun_fragen.json"
    if not d.is_file():
        return "<p>(Lauf der neun festen Anfragen noch nicht ausgewertet.)</p>"
    m = _json.loads(d.read_text(encoding="utf-8"))
    k = [f"<p>Gemessen am {m['datum']}, {m['ort']}, Modell {m['modell']}. Jede Zeile ist eine Anweisung aus den Knöpfen der Oberfläche, "
         "der Reihe nach in einem Gespräch; nichts davon ist hinterlegt — die Werkzeugaufrufe, Abnahmen und Zeiten stammen aus dem Ereignisprotokoll des Agenten. "
         f"Läufe: {m.get('laeufe', '')}.</p>",
         "<table><tr><th>Nr</th><th>Anfrage</th><th>Ende</th><th>Aufrufe</th><th>Abnahmen</th><th>Agent griff ein</th><th>Dauer</th><th>vom Werkzeug gemessen</th><th>Bemerkung</th></tr>"]
    for z in m["anweisungen"]:
        eingriffe = []
        if z["fokus"]: eingriffe.append(f"{z['fokus']}× Fokus")
        if z["berichtigung"]: eingriffe.append(f"{z['berichtigung']}× Berichtigung")
        if z["selbst"]: eingriffe.append(f"{z['selbst']}× selbst geprüft")
        if z["anmerkung"]: eingriffe.append(f"{z['anmerkung']}× Anmerkung")
        if z["ersetzt"]: eingriffe.append("Abschluss ersetzt")
        k.append(f"<tr><td>{z['nr']}</td><td>{z['anweisung'][:90] + ('…' if len(z['anweisung']) > 90 else '')}</td><td><strong>{z['ende']}</strong></td><td>{len(z['aufrufe'])}</td>"
                 f"<td>✓{z['bestanden']} ✗{z['durchgefallen']}" + (f" F{z['fehler']}" if z['fehler'] else "") + f"</td>"
                 f"<td>{', '.join(eingriffe) or '—'}</td><td>{z['sekunden'] or 0} s</td><td class=\"klein\">{(z['gemessen'] or '—')[:220]}</td>"
                 f"<td class=\"klein\">{z.get('bemerkung', '')}</td></tr>")
    k.append("</table>")
    return "\n".join(k)


def messreihe() -> str:
    """Tabelle der Messreihe 3 (05.10.2026): Coder-3B aus dem Protokoll (abgebrochen nach 6 von 8),
    Coder-7B aus messung.json, sobald die Reihe durch ist. Was nicht gemessen ist, steht als offen da."""
    import json as _json
    zeilen_3b = [("hallo bist du bereit?", "Antwort in Worten", "0", "—"),
                 ("Wie testen wir ein Blinkprogramm? Gibt es eine LED?", "schrieb und prüfte gleich blink.py; FERTIG", "3", "✓1"),
                 ("blink.py, 1 Hz", "FERTIG", "5", "✓1 ✗1, 1× selbst geprüft"),
                 ("auf 3 Hz ändern", "Abbruch nach 25 Schritten", "15", "✗5, 5× selbst geprüft"),
                 ("atmen.py sinusförmig 1 Hz", "FERTIG", "9", "✓1 ✗1, 3× selbst geprüft"),
                 ("zwei LEDs, zwei Takte", "Textantwort („JSON nicht korrekt“), kein Werkzeug", "0", "—"),
                 ("Taschenrechner tkinter", "nicht mehr gemessen (Reihe abgebrochen)", "", ""),
                 ("Ist nun alles ok?", "nicht mehr gemessen", "", "")]
    d7 = HIER / "pruefstand_coder7b" / "messung.json"
    zeilen_7b = None
    if d7.is_file():
        try:
            m = _json.loads(d7.read_text(encoding="utf-8"))
            zeilen_7b = [(z["ende"] + ("" if z["ende"] != "Antwort" else ""), str(z["aufrufe"]),
                          f"✓{z['bestanden']} ✗{z['durchgefallen']}" + (f", {z['selbst']}× selbst" if z.get("selbst") else "") + (f", {z['fokus']}× Fokus" if z.get("fokus") else ""),
                          f"{z['sekunden']} s") for z in m["anweisungen"]]
        except Exception:
            zeilen_7b = None
    k = ["<table><tr><th>Anweisung</th><th colspan=3>Qwen2.5-Coder-3B</th><th colspan=4>Qwen2.5-Coder-7B</th></tr>",
         "<tr><th></th><th>Ende</th><th>Aufrufe</th><th>Abnahmen</th><th>Ende</th><th>Aufrufe</th><th>Abnahmen</th><th>Dauer</th></tr>"]
    for i, (a, e3, n3, b3) in enumerate(zeilen_3b):
        if zeilen_7b and i < len(zeilen_7b):
            e7, n7, b7, s7 = zeilen_7b[i]
        else:
            e7, n7, b7, s7 = ("läuft noch" if not zeilen_7b else "—"), "", "", ""
        k.append(f"<tr><td>{html.escape(a)}</td><td>{html.escape(e3)}</td><td>{n3}</td><td>{b3}</td><td>{html.escape(e7)}</td><td>{n7}</td><td>{b7}</td><td>{s7}</td></tr>")
    k.append("</table>")
    return "\n".join(k)


SKIZZE = '''
<svg viewBox="0 0 1000 560" width="100%" role="img" aria-label="Funktionsskizze: Mensch, Oberfläche, Agent, Sprachmodell, Werkzeuge, Nachbau, Gerät">
 <defs><marker id="pf" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto"><polygon points="0 0, 9 3.5, 0 7" fill="#4a5568"/></marker></defs>
 <rect x="6" y="6" width="988" height="548" rx="12" fill="#f7fafc" stroke="#cbd5e0"/>
 <text x="22" y="32" font-size="15" font-weight="600" fill="#2d3748">Funktionsskizze — wer tut was, und wer kontrolliert wen</text>

 <rect x="22" y="60" width="170" height="92" rx="8" fill="#fff" stroke="#2d3748" stroke-width="1.8"/>
 <text x="36" y="84" font-size="13" font-weight="600" fill="#2d3748">Mensch</text>
 <text x="36" y="104" font-size="11.5" fill="#718096">stellt die Aufgabe</text>
 <text x="36" y="120" font-size="11.5" fill="#718096">setzt die Erwartung</text>
 <text x="36" y="136" font-size="11.5" fill="#718096">nennt den Anschluss</text>

 <rect x="232" y="60" width="190" height="92" rx="8" fill="#fff" stroke="#4299e1" stroke-width="1.8"/>
 <text x="246" y="84" font-size="13" font-weight="600" fill="#2b6cb0">Oberfläche (Browser)</text>
 <text x="246" y="104" font-size="11.5" fill="#718096">Gespräch: Verlauf, Eingabe,</text>
 <text x="246" y="120" font-size="11.5" fill="#718096">Zwischenruf während des Laufs,</text>
 <text x="246" y="136" font-size="11.5" fill="#718096">jeder Schritt sichtbar</text>

 <rect x="462" y="44" width="300" height="124" rx="8" fill="#fff" stroke="#2b6cb0" stroke-width="2.6"/>
 <text x="476" y="68" font-size="13" font-weight="600" fill="#2b6cb0">Agent (Sitzung)</text>
 <text x="476" y="88" font-size="11.5" fill="#4a5568">hält den Zusammenhang: Verlauf, Dateien,</text>
 <text x="476" y="104" font-size="11.5" fill="#4a5568">Erwartung, Anschlüsse, Abnahmen</text>
 <text x="476" y="122" font-size="11.5" fill="#9c4221">wacht: nichts behaupten, nicht raten, nur</text>
 <text x="476" y="138" font-size="11.5" fill="#9c4221">Geprüftes aufs Gerät, Erwartung bleibt</text>
 <text x="476" y="156" font-size="11.5" fill="#4a5568">kennt Werkzeuge und Methode, prüft notfalls selbst</text>

 <rect x="802" y="60" width="176" height="92" rx="8" fill="#fff" stroke="#805ad5" stroke-width="1.8"/>
 <text x="816" y="84" font-size="13" font-weight="600" fill="#553c9a">Sprachmodell</text>
 <text x="816" y="104" font-size="11.5" fill="#718096">Qwen2.5-Coder, lokal,</text>
 <text x="816" y="120" font-size="11.5" fill="#718096">llama-server (signiert)</text>
 <text x="816" y="136" font-size="11.5" fill="#718096">wählt Werkzeug, schreibt Code</text>

 <line x1="192" y1="106" x2="226" y2="106" stroke="#4a5568" stroke-width="1.6" marker-end="url(#pf)"/>
 <line x1="422" y1="106" x2="456" y2="106" stroke="#4a5568" stroke-width="1.6" marker-end="url(#pf)"/>
 <line x1="762" y1="96" x2="796" y2="96" stroke="#4a5568" stroke-width="1.6" marker-end="url(#pf)"/>
 <line x1="796" y1="126" x2="762" y2="126" stroke="#805ad5" stroke-width="1.6" marker-end="url(#pf)"/>
 <text x="764" y="86" font-size="10.5" fill="#718096">Verlauf + Werkzeugliste</text>
 <text x="764" y="146" font-size="10.5" fill="#553c9a">„WERKZEUG: name {…}“ oder Text</text>

 <rect x="22" y="210" width="956" height="150" rx="8" fill="#f0fff4" stroke="#48bb78" stroke-width="1.8"/>
 <text x="36" y="234" font-size="13" font-weight="600" fill="#276749">Werkzeuge — jedes ein eigenes Programm, ohne Modell einzeln prüfbar</text>
 <g font-size="11.5" fill="#2d3748">
  <rect x="36" y="248" width="150" height="40" rx="6" fill="#fff" stroke="#9ae6b4"/><text x="46" y="265">schreib_datei</text><text x="46" y="281" fill="#718096">in die Werkstatt</text>
  <rect x="200" y="248" width="170" height="40" rx="6" fill="#fff" stroke="#ed8936" stroke-width="1.8"/><text x="210" y="265">programm_testen</text><text x="210" y="281" fill="#718096">Nachbau, Abnahme</text>
  <rect x="384" y="248" width="160" height="40" rx="6" fill="#fff" stroke="#9ae6b4"/><text x="394" y="265">programm_ausfuehren</text><text x="394" y="281" fill="#718096">Konsole, Fenster</text>
  <rect x="558" y="248" width="130" height="40" rx="6" fill="#fff" stroke="#9ae6b4"/><text x="568" y="265">ports_zeigen</text><text x="568" y="281" fill="#718096">welcher Anschluss</text>
  <rect x="702" y="248" width="130" height="40" rx="6" fill="#fff" stroke="#9ae6b4"/><text x="712" y="265">esp32_firmware</text><text x="712" y="281" fill="#718096">MicroPython</text>
  <rect x="846" y="248" width="120" height="40" rx="6" fill="#fff" stroke="#9ae6b4"/><text x="856" y="265">esp32_…</text><text x="856" y="281" fill="#718096">übertragen, nachlesen</text>
  <rect x="36" y="302" width="200" height="40" rx="6" fill="#fff" stroke="#9ae6b4"/><text x="46" y="319">umgebung_anlegen</text><text x="46" y="335" fill="#718096">eigenes Python + tkinter</text>
  <rect x="250" y="302" width="190" height="40" rx="6" fill="#fff" stroke="#9ae6b4"/><text x="260" y="319">paket_installieren</text><text x="260" y="335" fill="#718096">esptool, mpremote aus dem Vorrat</text>
  <rect x="454" y="302" width="200" height="40" rx="6" fill="#fff" stroke="#9ae6b4"/><text x="464" y="319">nachweis_autark</text><text x="464" y="335" fill="#718096">Rechner vorher/nachher</text>
  <rect x="668" y="302" width="150" height="40" rx="6" fill="#fff" stroke="#cbd5e0" stroke-dasharray="4 3"/><text x="678" y="319">aufraeumen</text><text x="678" y="335" fill="#718096">nur am Kursende, nicht fürs Modell</text>
 </g>
 <line x1="612" y1="168" x2="612" y2="204" stroke="#4a5568" stroke-width="1.6" marker-end="url(#pf)"/>
 <text x="622" y="190" font-size="10.5" fill="#718096">ruft auf, liest das Ergebnis, prüft die Regeln</text>

 <rect x="22" y="400" width="300" height="130" rx="8" fill="#fff" stroke="#ed8936" stroke-width="2"/>
 <text x="36" y="424" font-size="13" font-weight="600" fill="#9c4221">Nachbau (ohne Hardware)</text>
 <text x="36" y="444" font-size="11.5" fill="#718096">machine-Modul nachgebildet,</text>
 <text x="36" y="460" font-size="11.5" fill="#718096">gedachte Uhr (Schlaf + Rechenzeit des ESP32),</text>
 <text x="36" y="476" font-size="11.5" fill="#718096">Pins, PWM-Hüllkurve, Takt, Form</text>
 <text x="36" y="500" font-size="11.5" fill="#9c4221">ABNAHME BESTANDEN / NICHT BESTANDEN</text>
 <text x="36" y="516" font-size="11.5" fill="#718096">gegen die Erwartung des Menschen</text>

 <rect x="350" y="400" width="300" height="130" rx="8" fill="#fff" stroke="#276749" stroke-width="2"/>
 <text x="364" y="424" font-size="13" font-weight="600" fill="#276749">Gerät (ESP32 an COMx)</text>
 <text x="364" y="444" font-size="11.5" fill="#718096">main.py läuft nach dem Neustart;</text>
 <text x="364" y="460" font-size="11.5" fill="#718096">Rücklesen misst auf dem Gerät selbst:</text>
 <text x="364" y="476" font-size="11.5" fill="#718096">Flanken per Interrupt (µs-Zähler)</text>
 <text x="364" y="492" font-size="11.5" fill="#718096">oder Tastgrad aus dem PWM-Kanal</text>
 <text x="364" y="516" font-size="11.5" fill="#276749">zweiter, unabhängiger Weg</text>

 <rect x="678" y="400" width="300" height="130" rx="8" fill="#fff" stroke="#4a5568" stroke-width="1.6"/>
 <text x="692" y="424" font-size="13" font-weight="600" fill="#2d3748">Nachweise</text>
 <text x="692" y="444" font-size="11.5" fill="#718096">ablage\\protokoll.txt — jeder Schritt</text>
 <text x="692" y="460" font-size="11.5" fill="#718096">fehlerbericht.txt — bei Abbruch</text>
 <text x="692" y="476" font-size="11.5" fill="#718096">nachweis_autark — der Rechner blieb gleich</text>
 <text x="692" y="492" font-size="11.5" fill="#718096">virtuelle_led.html — die Aufzeichnung</text>
 <text x="692" y="516" font-size="11.5" fill="#718096">Prüfstand mit Gegenproben</text>

 <line x1="285" y1="360" x2="172" y2="394" stroke="#ed8936" stroke-width="1.6" marker-end="url(#pf)"/>
 <line x1="770" y1="360" x2="500" y2="394" stroke="#276749" stroke-width="1.6" marker-end="url(#pf)"/>
 <line x1="520" y1="360" x2="800" y2="394" stroke="#4a5568" stroke-width="1.2" stroke-dasharray="4 3" marker-end="url(#pf)"/>
</svg>'''


def seite() -> str:
    w = werkzeuge()
    zeilen = "\n".join(
        f'<tr><td><code>{html.escape(x["name"])}</code></td>'
        f'<td>{html.escape(x["description"])}</td>'
        f'<td>{html.escape(", ".join(x["input_schema"]["properties"]) or "—")}</td></tr>'
        for x in w)
    heute = datetime.date.today().strftime("%d.%m.%Y")
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kurs-Agent {FASSUNG} — Lehrbeispiel: eine lokale KI schreibt, prüft und flasht Programme</title>
<style>
.klein {{ font-size:.8em; color:#4a5568; }}
 :root {{ --rand:#cbd5e0; --grau:#718096; --dunkel:#2d3748; --blau:#2b6cb0; }}
 * {{ box-sizing:border-box; }}
 body {{ font-family:-apple-system,Segoe UI,Roboto,sans-serif; line-height:1.65; color:#1a202c;
        max-width:1040px; margin:0 auto; padding:24px 20px 80px; background:#fff; }}
 h1 {{ font-size:1.7rem; margin:0 0 4px; }}
 h2 {{ font-size:1.25rem; margin:34px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--rand); }}
 h3 {{ font-size:1.05rem; margin:22px 0 8px; color:var(--dunkel); }}
 .kopf {{ color:var(--grau); font-size:.92rem; margin-bottom:22px; }}
 table {{ border-collapse:collapse; width:100%; margin:14px 0; font-size:.93rem; }}
 th,td {{ border:1px solid var(--rand); padding:8px 10px; text-align:left; vertical-align:top; }}
 th {{ background:#edf2f7; font-weight:600; }}
 code {{ background:#edf2f7; padding:1px 5px; border-radius:3px; font-size:.9em; }}
 pre {{ background:#2d3748; color:#e2e8f0; padding:13px 16px; border-radius:6px; overflow-x:auto;
        font-size:.88rem; line-height:1.5; }}
 pre code {{ background:none; color:inherit; padding:0; }}
 .kasten {{ border-left:4px solid var(--blau); background:#ebf8ff; padding:12px 16px; margin:16px 0;
            border-radius:0 5px 5px 0; }}
 .warn {{ border-left-color:#dd6b20; background:#fffaf0; }}
 .gut {{ border-left-color:#38a169; background:#f0fff4; }}
 .reiter {{ display:flex; flex-wrap:wrap; gap:4px; margin:26px 0 0; border-bottom:2px solid var(--rand); }}
 .reiter button {{ border:1px solid var(--rand); border-bottom:none; background:#edf2f7; cursor:pointer;
                   padding:9px 15px; font-size:.92rem; border-radius:6px 6px 0 0; font-family:inherit; }}
 .reiter button[aria-selected=true] {{ background:#fff; font-weight:600; color:var(--blau);
                                       margin-bottom:-2px; border-bottom:2px solid #fff; }}
 .blatt {{ padding-top:6px; }}
 .schritt {{ display:flex; gap:14px; margin:14px 0; }}
 .nr {{ flex:0 0 30px; height:30px; border-radius:50%; background:var(--blau); color:#fff;
        display:flex; align-items:center; justify-content:center; font-weight:600; font-size:.9rem; }}
 figure {{ margin:18px 0; }}
 figure img {{ width:100%; border:1px solid var(--rand); border-radius:8px; display:block; }}
 figcaption {{ font-size:.85rem; color:var(--grau); margin-top:7px; }}
 footer {{ margin-top:50px; padding-top:14px; border-top:1px solid var(--rand);
           color:var(--grau); font-size:.86rem; }}
 @media (max-width:640px) {{ body {{ padding:16px 14px 60px; }} .reiter button {{ padding:8px 11px; font-size:.86rem; }} }}
</style></head><body>

<h1>Kurs-Agent — Lehrbeispiel: eine lokale KI schreibt, prüft und flasht Programme</h1>
<div class="kopf">Fassung {FASSUNG} · {heute} · Prof. Dr.-Ing. Ralph Wystup M.Sc.</div>

<p><strong>Dieses Paket vertieft am realen System, was die veröffentlichte Seite
<a href="https://ralphwystup.github.io/KI-steuert-lokale-Hardware-ueber-eine-Bruecke/Bruecke_KI_und_Arbeitsplatz_1.0.html#aufgabe">„KI steuert lokale Hardware über eine Brücke"</a> exemplarisch zeigt.</strong>
Ein KI-Agent mit eigenem Sprachmodell richtet auf einem Windows-Rechner Python ein,
schreibt ein Programm für einen ESP32, überspielt es — und entfernt sich danach restlos.
Alles läuft aus <strong>einem Ordner</strong>, vom Stick oder von der Festplatte. Nichts
wird installiert, kein Netz wird gebraucht, keine Adminrechte.</p>

{SCHAUBILD}

<div class="reiter" role="tablist">
 <button role="tab" aria-selected="true" data-z="b1">Wofür das Ganze</button>
 <button role="tab" aria-selected="false" data-z="b2">Was im Paket ist</button>
 <button role="tab" aria-selected="false" data-z="b3">Schritt für Schritt</button>
 <button role="tab" aria-selected="false" data-z="b4">Zwei Beispiele</button>
 <button role="tab" aria-selected="false" data-z="bh">Hardware und Treiber</button>
 <button role="tab" aria-selected="false" data-z="bm">Das Sprachmodell</button>
 <button role="tab" aria-selected="false" data-z="ba">Der Agent</button>
 <button role="tab" aria-selected="false" data-z="bw">Die Werkzeuge</button>
 <button role="tab" aria-selected="false" data-z="bp">Prüfen und Messen</button>
 <button role="tab" aria-selected="false" data-z="bs">Stand und Grenzen</button>
 <button role="tab" aria-selected="false" data-z="b5">Was der Rechner merkt</button>
 <button role="tab" aria-selected="false" data-z="b6">Wenn es klemmt</button>
</div>

<div class="blatt" id="b1">
<h2>Wofür das Ganze</h2>

<p>Nicht nur für den ESP32: Der Agent schreibt auf Anforderung jedes Python-Programm — einen
Taschenrechner mit Fenster (tkinter liegt im Paket), ein Skript, das rechnet — und führt es mit
dem Paket-Python aus, bevor er es für fertig erklärt.</p>

<p>Die veröffentlichte Seite führt vor, wie eine KI über eine Brücke Hardware am Arbeitsplatz
steuert. Dort sieht man zu. Hier hat man es selbst in der Hand: eigenes Modell, eigener ESP32,
kein Netz, ein Ordner — derselbe Kreis aus Anforderung, Bau, Abnahme und Nachweis, nur dass
jeder Schritt auf dem eigenen Rechner läuft und geprüft wird.</p>

<p>Dieses Paket zeigt an einem kleinen, vollständig laufenden Beispiel, <strong>wie
Entwicklung mit einem Sprachmodell wirklich abläuft</strong> — nicht als Folienvortrag,
sondern als Vorgang, den man anstoßen und zusehen kann. Es ist derselbe Ablauf, mit dem
auch dieses Paket selbst entstanden ist, nur im kleinen Rahmen.</p>

<h3>Der Ablauf — und warum er so und nicht anders ist</h3>
<table><tr><th></th><th>Schritt</th><th>wer</th><th>warum er nicht wegfallen darf</th></tr>
<tr><td><strong>1</strong></td><td>Anforderung</td><td>Mensch</td><td>Ein Satz auf Deutsch. Was nicht gesagt wurde, kann auch nicht geprüft werden.</td></tr>
<tr><td><strong>2</strong></td><td>Bau</td><td>Modell</td><td>Das Modell schreibt den Quelltext. Das ist der Teil, über den alle reden — und der kleinste.</td></tr>
<tr><td><strong>3</strong></td><td>Abnahme</td><td>Werkzeug</td><td>Das Programm läuft, und das Gemessene wird mit dem Angekündigten verglichen. <strong>Hier entscheidet sich alles.</strong></td></tr>
<tr><td><strong>4</strong></td><td>Berichtigen</td><td>Modell</td><td>Fällt die Abnahme durch, geht es zurück zu 2 — mit der Fehlermeldung als Eingabe.</td></tr>
<tr><td><strong>5</strong></td><td>Auslieferung</td><td>Werkzeug</td><td>Erst nach bestandener Abnahme geht dieselbe Datei auf die Hardware.</td></tr>
<tr><td><strong>6</strong></td><td>Rücklesen</td><td>Werkzeug</td><td>Das Gerät selbst meldet, was blinkt: Pegel, Wechsel, Takt — gegen dieselbe Erwartung. Der zweite, unabhängige Weg.</td></tr>
<tr><td><strong>7</strong></td><td>Nachweis</td><td>Werkzeug</td><td>Was hat sich am Rechner geändert? Gemessen, nicht behauptet.</td></tr></table>

<div class="kasten"><p><strong>Schritt 3 ist der eigentliche Inhalt des Kurses.</strong> Ein
Sprachmodell schreibt in Sekunden ein Programm, das plausibel aussieht. Ob es tut, was
verlangt war, steht damit nicht fest — und genau diese Lücke schließt kein besseres Modell,
sondern eine Prüfung, die <em>durchfallen kann</em>.</p>
<p>Deshalb nimmt <code>programm_testen</code> eine Erwartung entgegen:</p>
<pre><code>"erwartet": {{"pins": [2], "takt_hz": 1.0}}</code></pre>
<p>Ohne diese Zeile ist der Lauf eine Vorführung: etwas blinkt, und niemand hat vorher
gesagt, was hätte blinken sollen. Mit ihr ist es eine Abnahme.</p></div>

<h3>Was hier anders ist als im großen Aufbau</h3>
<p>Üblicherweise liegen die drei Teile auf drei Rechnern: das Sprachmodell bei einem
Anbieter, der Agent auf einem Server, die Hardware am Arbeitsplatz — verbunden über eine
Brücke. <strong>Hier sind alle drei derselbe Rechner.</strong></p>
<table><tr><th>Teil</th><th>großer Aufbau</th><th>dieses Paket</th></tr>
<tr><td>Sprachmodell</td><td>beim Anbieter, über das Netz</td><td><code>llama-server</code> auf <code>127.0.0.1</code></td></tr>
<tr><td>Agent und Werkzeuge</td><td>auf einem Server</td><td>derselbe Rechner, Ordner <code>agent\\</code></td></tr>
<tr><td>Hardware</td><td>am Arbeitsplatz, über eine Brücke</td><td>am selben USB-Anschluss</td></tr></table>
<p>Am Ablauf ändert das nichts — und das ist der Punkt. Wer ihn hier verstanden hat, hat ihn
auch für den verteilten Fall verstanden; dort kommen Strecke und Rechteverwaltung dazu,
nicht aber ein anderer Vorgang.</p>

<h3>Was gelten soll — und woran man es misst</h3>
<p>Die Anforderungen an dieses Paket stehen geschrieben, nicht im Kopf: <code>ANFORDERUNGEN.md</code>
führt 55 Punkte in neun Gruppen, jeder so gefasst, dass er <strong>scheitern kann</strong>, mit
der Angabe, woran er gemessen wird.</p>
<table><tr><th>Gruppe</th><th>Kern</th></tr>
<tr><td><strong>A — Autarkie</strong></td><td>Der Kursrechner hat Windows und sonst nichts. Das Paket bringt alles mit, sucht kein vorhandenes Python und benutzt auch keines.</td></tr>
<tr><td><strong>B — keine Störung</strong></td><td>Läuft dort schon Thonny oder ein eigenes Python, bleibt daran alles unberührt — auch Benutzerpakete, pip-Zwischenspeicher, PATH, Ports und COM-Anschlüsse.</td></tr>
<tr><td><strong>C — nur im Kursordner</strong></td><td>Geschrieben wird ausschließlich in <code>ablage\\</code>, und das wird erzwungen, nicht gehofft.</td></tr>
<tr><td><strong>D — restlos entfernbar</strong></td><td>Ein Ordner, ein Befehl, danach wird nachgezählt.</td></tr>
<tr><td><strong>E — Weitergabe</strong></td><td>Derselbe Stick startet auf jedem Rechner; das Modell wird beim Start gewählt.</td></tr>
<tr><td><strong>F — Bedienung</strong></td><td>Doppelklick, anklicken, zusehen. Keine Kommandozeile.</td></tr>
<tr><td><strong>G — der Lehrinhalt</strong></td><td>Bauen, Abnahme gegen eine vorher genannte Zahl, berichtigen, erst dann ausliefern.</td></tr>
<tr><td><strong>H — Hardware</strong></td><td>Fabrikneu oder vorprogrammiert, mit oder ohne Treiber, mit oder ohne Steckbrett.</td></tr>
<tr><td><strong>I — Ferndiagnose</strong></td><td>Ein Befehl schreibt alles Nötige in <strong>eine</strong> Datei — ohne Benutzer- und Rechnernamen.</td></tr></table>
<pre><code>python pruefe_alles.py</code></pre>
<p>arbeitet die maschinell prüfbaren Punkte ab — derzeit 17 — und nennt, welche von Hand zu
prüfen bleiben. Beim Schreiben dieses Prüfskripts fielen zwei eigene Fehler auf: eine Prüfung,
die ihr Ergebnis behauptete statt es abzulesen, und eine, die „bestanden" meldete, obwohl der
geprüfte Lauf gar nicht stattgefunden hatte.</p>

<h3>Das Blinkprogramm ist nur das Beispiel</h3>
<p>Eine blinkende Leuchtdiode ist die kleinste Aufgabe, an der sich die ganze Kette zeigen
lässt: sie ist in sechs Zeilen geschrieben, in vier Sekunden geprüft und am Ergebnis sieht
man sofort, ob es stimmt. Aufgezeichnet wird aber <strong>jeder</strong> Anschluss — ein
Programm mit drei Pins und verschiedenen Takten läuft genauso durch, ebenso Pulsweiten­modulation
und Analogeingänge.</p>
</div>

<div class="blatt" id="b2" hidden>
<h2>Was im Paket ist</h2>

<h3>Die Ordner — und die Trennung, auf der alles beruht</h3>
<table><tr><th>Ordner</th><th>Inhalt</th><th>Eigenschaft</th></tr>
<tr><td><code>paket\\</code></td><td>Python, pip, Pakete, MicroPython, llama.cpp, Sprachmodell, Treiber</td><td><strong>wird nur gelesen</strong> — nie beschrieben</td></tr>
<tr><td><code>agent\\</code></td><td>die Schleife, die Modellanbindung, neun Werkzeuge</td><td>der Programmteil, rund 60 kB</td></tr>
<tr><td><code>ablage\\</code></td><td>das entpackte Python, installierte Pakete, erzeugte Dateien, Protokoll</td><td><strong>wird am Ende restlos gelöscht</strong></td></tr></table>
<div class="kasten gut"><p>Diese Trennung ist das ganze Sicherheitskonzept. Geschrieben wird
ausschließlich in <code>ablage\\</code>; das erzwingt der Werkzeugrahmen, indem er jeden
Schreibpfad auflöst und prüft, <em>bevor</em> eine Datei entsteht. Deshalb ist das Aufräumen
ein Beweis und keine Behauptung: es löscht genau einen Ordner und zählt hinterher nach.</p></div>

<h3>Was mitgeliefert wird</h3>
<table><tr><th>Teil</th><th>Datei</th><th>Größe</th><th>wofür</th></tr>
<tr><td>Python, ausgepackt</td><td><code>python_vorlage\\</code></td><td>22 MB</td><td>wird kopiert, nicht installiert — <strong>dies ist der Weg</strong>, den <code>START.bat</code> geht</td></tr>
<tr><td>Python als Archiv</td><td><code>python-3.12.10-embed-amd64.zip</code></td><td>11,1 MB</td><td>Rückfall, falls die Vorlage fehlt. Wird nur entpackt, nie installiert</td></tr>
<tr><td>pip</td><td><code>get-pip.py</code></td><td>2,2 MB</td><td>richtet die Paketverwaltung im entpackten Python ein</td></tr>
<tr><td>Python-Pakete</td><td><code>pakete\\</code> — 25 Dateien</td><td>8,4 MB</td><td>esptool und mpremote samt allem, was dazugehört</td></tr>
<tr><td>MicroPython</td><td><code>firmware\\*.bin</code></td><td>1,8 MB</td><td>die Firmware für den ESP32</td></tr>
<tr><td>llama.cpp</td><td><code>llama\\llama-server.exe</code></td><td>95 MB</td><td>führt das Sprachmodell aus</td></tr>
<tr><td>Sprachmodell</td><td><code>modell\\*.gguf</code></td><td>1,0–4,7 GB</td><td>entscheidet, welches Werkzeug wann läuft</td></tr>
<tr><td>USB-Treiber</td><td><code>treiber\\*.zip</code></td><td>1,4 MB</td><td>falls Windows den Wandler nicht kennt</td></tr></table>
<p>Ohne Modell sind das 137 MB; mit dem mittleren Modell (3b) rund 2,1 GB, und mit beiden
Modellen — so wird der Stick gebaut — rund 6,8 GB.</p>

<h3>Was der Rechner mitbringen muss</h3>
<p>Die folgenden Zahlen sind <strong>gemessen</strong>, nicht geschätzt: am laufenden Paket,
mit <code>ps</code> am Modellserver abgelesen, auf einem Rechner mit 20 Kernen ohne
Grafikbeschleunigung.</p>
<table><tr><th>Modell</th><th>Datei</th><th>Speicher gemessen</th><th>braucht RAM</th><th>Ladezeit</th><th>Urteil aus dem Prüflauf</th></tr>
<tr><td><code>1.5b</code></td><td>0,99 GB</td><td>2,2 GB</td><td>4 GB</td><td>~1 s</td><td>zeigt die Schleife, scheitert an mehrstufigen Aufträgen</td></tr>
<tr><td><code>3b</code></td><td>1,93 GB</td><td><strong>3,48 GB</strong></td><td>8 GB</td><td>2–3 s</td><td>schreibt brauchbare Programme, verliert aber den Faden und ruft Werkzeuge in falscher Reihenfolge; Rückfall</td></tr>
<tr><td><code>7b</code></td><td>4,68 GB</td><td><strong>6,70 GB</strong></td><td>16 GB</td><td>5–6 s</td><td>hält die Kette ein, berichtigt eigene Fehler — Rückfall, wenn kein Coder-Modell da ist</td></tr></table>
<tr><td><code>coder-3b</code></td><td>1,93 GB</td><td><strong>3,5 GB</strong></td><td>8 GB</td><td>2–3 s</td><td><strong>die Wahl ab 8 GB</strong> — speziell für Python: Karte 1 in vier Werkzeugaufrufen (schreiben → durchgefallen → berichtigen → bestanden), gemessen 04.10.2026; zwei Takte zugleich (Karte 3) überfordern es wie jedes 3B</td></tr>
<tr><td><code>coder-7b</code></td><td>4,68 GB</td><td><strong>6,7 GB</strong></td><td>16 GB</td><td>5–6 s</td><td><strong>die Empfehlung ab 16 GB</strong> — dieselbe Familie, für Quelltext trainiert; noch nicht gemessen</td></tr>

<table><tr><th>Sonst</th><th></th></tr>
<tr><td>Betriebssystem</td><td>Windows 10 oder 11, 64 bit. Keine Adminrechte, außer für einen USB-Treiber</td></tr>
<tr><td>Prozessor</td><td>vier Kerne aufwärts. Im Prüflauf lagen 500 % Last an — das Modell nimmt, was da ist</td></tr>
<tr><td>Platz</td><td>200 MB ohne Modell, 2,2 GB mit dem 3B-, 5,0 GB mit dem 7B-Modell</td></tr>
<tr><td>Grafik</td><td>keine nötig. Mit Vulkan (AMD, Intel, NVIDIA) wird es schneller, ohne rechnet llama.cpp auf dem Hauptprozessor weiter</td></tr>
<tr><td>Netz</td><td>einmal zum Füllen des Pakets. Im Kurs nie</td></tr></table>

<div class="kasten"><p><strong>Gemessener Prüflauf</strong> (7B-Modell, 20 Kerne, keine Grafik):
fünf Werkzeugaufrufe in 2 Minuten 48 Sekunden, davon der größte Teil Wartezeit auf das
Modell — rund 15 bis 25 Sekunden je Antwort. Auf vier Kernen ist mit dem Mehrfachen zu
rechnen; dann lohnt das 3B-Modell trotz seiner Schwächen.</p>
<p>Diesen Rechner selbst messen lassen:</p>
<pre><code>python pruefe_rechner.py</code></pre>
<p>Es nennt Arbeitsspeicher, Kerne, freien Platz und Grafik, hält sie gegen die Tabelle oben
und empfiehlt ein Modell — oder sagt, dass keines passt.</p></div>

<div class="kasten gut"><p><strong>Ohne Sprachmodell läuft weiterhin alles andere:</strong>
die neun Werkzeuge, der Prüfschritt mit Abnahme, die virtuelle LED, das Flashen, der
Nachweis und das Aufräumen. Dafür genügen Windows und 200 MB. Nur die Entscheidung, welches
Werkzeug wann läuft, trifft dann ein festes Drehbuch statt eines Modells.</p></div>

<h3>Die neun Werkzeuge</h3>
<p>Jedes ist ein eigenständiges Programm mit genau zwei Betriebsarten:
<code>--beschreibung</code> sagt als JSON, was es kann; <code>'&lt;json&gt;'</code> führt es aus.
Mehr Verbindung zwischen Modell und Werkzeug gibt es nicht — deshalb lässt sich jedes ohne
Modell von Hand prüfen, und genau das ist Menüpunkt&nbsp;[2].</p>
<table><tr><th>Name</th><th>was es tut</th><th>Felder</th></tr>
{zeilen}
</table>
<p class="kopf">Diese Tabelle ist nicht abgeschrieben, sondern beim Erzeugen der Seite von den
Werkzeugen selbst erfragt. Eine abgeschriebene Tabelle stimmt genau bis zur ersten Änderung.</p>

<h3>Wie sie zusammenspielen</h3>
<pre><code>umgebung_anlegen        entpackt Python          muss zuerst laufen
   └─ paket_installieren   esptool, mpremote     braucht das Python von oben
         ├─ ports_zeigen        welcher Anschluss?    braucht pyserial
         └─ esp32_firmware      MicroPython aufs Gerät  braucht esptool

schreib_datei           das Programm entsteht
   └─ programm_testen      Abnahme ohne Hardware   ← hier wird entschieden
         └─ esp32_uebertragen  dieselbe Datei aufs Gerät   braucht mpremote
               └─ esp32_nachlesen  misst am Gerät, ob es blinkt   braucht mpremote

nachweis_autark         vorher / nachher
aufraeumen              löscht die Ablage, zählt nach</code></pre>
<p>Die Reihenfolge erfindet nicht der Agent, sondern sie ergibt sich: jedes Werkzeug sagt in
seiner Fehlermeldung, was ihm fehlt. Ruft das Modell <code>ports_zeigen</code> zu früh, bekommt
es <em>„Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen"</em> — und tut
genau das. So braucht es keinen festen Ablaufplan.</p>

<h3>Ein eigenes Werkzeug</h3>
<p><code>agent\\werkzeuge\\_muster.py</code> nimmt den Rahmen ab. Eine neue Datei im Ordner
genügt — der Agent findet sie beim nächsten Start, weil er die Liste nicht führt, sondern
erfragt.</p>
<pre><code>from _muster import werkzeug, Abbruch, lauf

def tun(e):
    return f"Ergebnis zu {{e['feld']}}"

werkzeug("mein_werkzeug", "Was es tut und wann man es ruft.",
         {{"feld": {{"type": "string", "description": "wofür"}}}},
         ["feld"], {{"feld": "Probe"}}, tun)</code></pre>
</div>

<div class="blatt" id="b3" hidden>
<h2>Schritt für Schritt</h2>

<h3 style="color:#2b6cb0">Teil A — einmal vorbereiten, mit Netz</h3>

<div class="schritt"><div class="nr">1</div><div>
<strong>Ordner bereitlegen.</strong> Auf den Stick kopieren oder auf der Platte lassen, zum
Beispiel <code>C:\\Kurs_Agent</code>. Laufwerksbuchstabe und Name sind beliebig — im ganzen
Paket steht kein fester Pfad.</div></div>

<div class="schritt"><div class="nr">2</div><div>
<strong>Doppelklick auf <code>START.bat</code> — auch beim ersten Mal.</strong> Ist das Paket
noch leer, sagt das Skript genau das und holt alles selbst: rund 6,8 GB — Python, pip, 25
Pakete, MicroPython, llama.cpp, Treiber und zwei Sprachmodelle (3b und 7b). Zehn bis dreißig
Minuten, je nach Leitung. Danach läuft es weiter, als wäre gerade gestartet worden.
<div class="kasten warn"><p><strong>Für diesen einen Schritt — und nur für ihn — wird ein
vorhandenes Python mit pip gebraucht.</strong> Der Grund ist einfach: im leeren Paket liegt
noch keines. <code>START.bat</code> sucht eines, prüft ob darin pip läuft, nennt es beim
Namen und fragt nach, bevor etwas geholt wird. Selbst dabei bleibt der Rechner unberührt —
pip-Zwischenspeicher und Benutzerpakete zeigen in den Kursordner, nicht ins Profil.
Danach wird dieses Python nie wieder angefasst: der ganze Kursbetrieb läuft mit dem Python
aus dem Paket.</p>
<p>Wird keines gefunden, nennt das Skript zwei Wege — Python von python.org installieren,
oder den <strong>gefüllten</strong> Ordner von einem anderen Rechner kopieren. Der zweite
ist der gedachte: füllen einmal, weitergeben beliebig oft. Auf dem Kursrechner ist nie ein
fremdes Python nötig.</p></div></div></div>

<div class="schritt"><div class="nr">3</div><div>
<strong>Doppelklick auf <code>START.bat</code>.</strong> Es sucht <strong>kein</strong>
vorhandenes Python — weder im PATH noch dort, wo Windows oder Thonny eines ablegen. Es kopiert
sein eigenes aus <code>paket\\python_vorlage\\</code> nach <code>ablage\\python\\</code>
und arbeitet nur mit diesem. Was auf dem Rechner schon installiert ist, wird nicht gestartet,
nicht gelesen und nicht verändert.</div></div>

<div class="schritt"><div class="nr">4</div><div>
<strong><code>[1] Installieren und starten</code> — die Eingabetaste.</strong> Mehr fragt
<code>START.bat</code> nicht. Es prüft den Stand des Pakets („Paket: … vollständig"), und
fehlt etwas, holt es das Fehlende von selbst — zuerst aus dem <strong>Vorrat</strong> (ein
Paket nebenan, ein Stick unter <code>X:\\Kurs_Agent</code>, der Download-Ordner), erst dann
aus dem Netz. Liegt irgendwo ein volles Paket, braucht es gar kein Netz.</div></div>

<div class="schritt"><div class="nr">5</div><div>
<strong>Stick bauen</strong> (wenn er weitergegeben werden soll):
<code>python baue_stick.py E:\\Kurs_Agent</code> — nimmt mit, was zum Betrieb gehört, lässt
weg, was beim Entwickeln entsteht, und meldet von selbst, wenn das Modell fehlt.</div></div>

<h3 style="color:#276749">Teil B — im Kurs, ohne Netz</h3>

<div class="schritt"><div class="nr">6</div><div>
<strong>Stick einstecken, <code>START.bat</code> doppelklicken.</strong></div></div>

<div class="schritt"><div class="nr">7</div><div>
<strong>Eine Frage, drei Antworten.</strong>
<table style="margin-top:8px"><tr><th>Wahl</th><th>was sie bedeutet</th></tr>
<tr><td><strong>[1] Installieren und starten</strong></td><td>legt das eigene Python bereit, prüft das Paket, holt Fehlendes, öffnet den Agenten im Browser. Das ist der Normalfall — die Eingabetaste genügt.</td></tr>
<tr><td><strong>[2] Deinstallieren</strong></td><td>zeigt erst den Nachweis, was sich am Rechner verändert hat (nichts), und entfernt dann alles, was der Agent angelegt hat. Das Paket selbst bleibt.</td></tr>
<tr><td><strong>[3] Abbrechen</strong></td><td>nichts geschieht.</td></tr></table>
<p style="margin-top:8px">Wer mehr will — Werkzeuge einzeln prüfen, der Agent ohne Browser,
der Weg ohne Modell, ein Bericht zum Weitergeben —, startet <code>START.bat --menue</code>.
Der Weg „auf die Platte kopieren, danach selbst löschen" heißt <code>START.bat --kopieren</code>.</p></div></div>

<div class="schritt"><div class="nr">8</div><div>
<strong>Beim Start zwei Zeilen lesen.</strong> <code>Paket: … vollständig</code> — jeder Teil ist
da. Und <code>Smart App Control: …</code> — steht dort <strong>EIN</strong>, lässt dieser Rechner nur
signierte Programme laufen. Der mitgelieferte Modellserver ist signiert (Ollama Inc./DigiCert) und
läuft trotzdem; am 04.10.2026 auf einem solchen Rechner gemessen. Sollte das Modell dennoch nicht
starten, sagt der Agent das im Browser in Worten und läuft <strong>ohne Modell weiter</strong>:
dieselben Werkzeuge, dieselbe Abnahme, die virtuelle LED — die Entscheidungen trifft ein festes
Drehbuch.</div></div>

<h3>So sieht die Bedienung aus — ein Gespräch</h3>
<p>Nach <code>[1]</code> öffnet sich der Browser. Oben der Kopf (Ordner, Modell, Zustand), unten
immer das Eingabefeld, dazwischen der Verlauf. Sie sagen dem Agenten, was er tun soll — mit
einem Satz oder einem der Vorschläge —, sehen jeden Schritt mit und geben danach die nächste
Anweisung. Der Agent behält den Zusammenhang: „Nimm jetzt GPIO 4", „ändere auf 10 Hz", „lade es
auf den ESP32 an COM3 und lies nach, ob die LED blinkt" oder ein eigenes Programm in
<code>```</code>-Zeichen zum Prüfen. Im schwarzen Fenster steht derweil, was der Agent tut;
<code>Strg+C</code> dort beendet ihn.</p>
<figure>{bild('ob_start.png')}
<figcaption>Die Oberfläche nach dem Start: oben Ordner und Modell, unten das Eingabefeld mit
Vorschlägen; Enter sendet.</figcaption></figure>

<figure>{bild('ob_lauf.png')}
<figcaption>Während der Agent arbeitet. Jeder Schritt erscheint einzeln: was das Modell
überlegt, welches Werkzeug es mit welchen Werten aufruft, und was dabei herauskam.</figcaption></figure>

<figure>{bild('ob_fertig.png')}
<figcaption>Am Ende der Anweisung: ABNAHME BESTANDEN, das Modell sagt in eigenen Worten, was es
getan hat — und das Eingabefeld ist wieder frei.</figcaption></figure>

<figure>{bild('ob_gespraech.png')}
<figcaption>Die zweite Anweisung im selben Gespräch: „Nimm jetzt GPIO 4 statt 2." Die Erwartung
wird fortgeführt (Pin 4, Takt bleibt), die alte Abnahme gilt nicht mehr, das Programm muss neu
bestehen. Sagt das Modell FERTIG ohne zu prüfen, prüft der Agent selbst.</figcaption></figure>

<h3>Und wenn es nicht auf Anhieb klappt</h3>
<p>Das ist der häufigere Fall und der eigentlich interessante. Hier der Auszug aus einem
Prüflauf, wörtlich aus dem Protokoll — das Modell schrieb <code>time.sleep(1)</code> für
beide Pausen, was eine Periode von zwei Sekunden ergibt:</p>
<pre><code>[2] programm_testen {{"datei": "blink.py", "erwartet": {{"pins": [2], "takt_hz": 1.0}}}}

    ABNAHME NICHT BESTANDEN
      Anschluesse: erwartet [2], gemessen [2]  erfuellt
      Takt: erwartet 1.00 Hz, gemessen 0.50 Hz (Spielraum 10 %)  NICHT ERFUELLT
      Zustandswechsel: erwartet mindestens 6, gemessen 7  erfuellt

    NAECHSTER SCHRITT: Rufe schreib_datei mit berichtigtem Quelltext auf. Dasselbe
    Programm noch einmal zu pruefen aendert nichts am Ergebnis. [...] Bei einem Takt:
    eine Blinkperiode besteht aus zwei Pausen, also ergibt time.sleep(0.5) +
    time.sleep(0.5) genau 1 Hz.

[3] schreib_datei {{"name": "blink.py", ...}}
[4] schreib_datei {{"name": "blink.py", ...}}
[5] programm_testen {{"datei": "blink.py", ...}}

    ABNAHME BESTANDEN
      Takt: erwartet 1.00 Hz, gemessen 1.00 Hz (Spielraum 10 %)  erfuellt

=== fertig nach 5 Werkzeugaufrufen ===</code></pre>
<div class="kasten gut"><p><strong>Das ist der Kurs in acht Zeilen.</strong> Das Modell hat
ein plausibles Programm geschrieben, das nicht tat, was verlangt war. Kein Mensch hat den
Fehler gefunden, sondern eine Messung gegen eine vorher genannte Zahl. Danach hat das
Modell selbst berichtigt.</p>
<p>Ein Agent, der diesen Schritt nicht hat, liefert dasselbe falsche Programm aus — mit der
Meldung, alles sei in Ordnung.</p></div>

<figure>{bild('ob_led.png')}
<figcaption>Ganz unten blinkt die LED — das Programm läuft wirklich, nur eben ohne
Steckbrett. Dieselbe Datei geht anschließend unverändert auf den ESP32.</figcaption></figure>

<div class="schritt"><div class="nr">9</div><div>
<strong>ESP32 anstecken</strong> — falls vorhanden. Ein USB-Kabel <strong>mit Datenadern</strong>;
ein reines Ladekabel sieht genauso aus und überträgt nichts. Das ist der häufigste Fehler
im Kurs. Ohne Hardware geht es trotzdem weiter, siehe Beispiel&nbsp;2.</div></div>

<div class="schritt"><div class="nr">10</div><div>
<strong>Menüpunkt <code>[1] Agent starten</code>.</strong> Die Eingabetaste nimmt den
vorgegebenen Auftrag. Das Modell lädt beim ersten Mal 10 bis 60 Sekunden.</div></div>

<div class="schritt"><div class="nr">11</div><div>
<strong>Menüpunkt <code>[3] Aufräumen</code>.</strong> Zeigt erst den Nachweis — was hat sich
außerhalb des Ordners verändert? — und löscht dann die Ablage, mit Nachzählung.</div></div>

<div class="kasten warn"><p><strong>Wenn das Modell klemmt:</strong> Menüpunkt
<code>[7] Ohne Modell durchlaufen</code> macht dieselben Schritte in fester Reihenfolge, mit
denselben Werkzeugen und derselben Abnahme. Der Kurs läuft dann weiter; nur die
Entscheidungen trifft das Drehbuch statt des Modells.</p></div>
</div>

<div class="blatt" id="b4" hidden>
<h2>Zwei Beispiele</h2>
<p>Beide Male derselbe Auftrag, dasselbe Modell, dieselben Werkzeuge. Der Unterschied ist
nur, ob ein Steckbrett am USB-Anschluss hängt.</p>

<h3>Beispiel 1 — mit ESP32 am Rechner</h3>
<p>Auftrag im Menüpunkt&nbsp;[3]:</p>
<pre><code>Schreibe ein MicroPython-Programm, das die LED an GPIO 2 einmal je Sekunde
blinken lässt. Prüfe es ohne Hardware gegen diese Erwartung, und wenn es
besteht, spiele es auf den ESP32.</code></pre>
<p>Was dann der Reihe nach geschieht — die Zeilen sind die wirklichen Ausgaben der Werkzeuge:</p>
<pre><code>[1] umgebung_anlegen {{}}
    Python-Archiv: mitgeliefert (python-3.12.10-embed-amd64.zip, 11133606 Byte)
    entpackt nach ...\\ablage\\python
    python312._pth: 'import site' freigeschaltet
    pip eingerichtet
    Gegenprobe: pip 25.x from ...\\ablage\\python\\Lib\\site-packages\\pip

[2] paket_installieren {{"paket": "esptool"}}
    esptool installiert aus mitgelieferten Dateien in ...\\paket\\pakete
    Ziel: ...\\ablage\\python (nicht das Python des Rechners)
    Gegenprobe: import esptool -&gt; Fassung 5.4.0

[3] ports_zeigen {{}}
    2 serielle Anschluesse:
      COM3     —         Standardmäßige Seriellenschnittstelle
      COM5     1A86:7523 USB-SERIAL CH340   &lt;- QinHeng CH340
    Nach dem Wandler zu urteilen koennte der ESP32 an COM5 haengen.
    Das ist ein Vorschlag, keine Feststellung.

[4] schreib_datei {{"name": "blink.py", "inhalt": "from machine import Pin..."}}
    ...\\ablage\\werkstatt\\blink.py geschrieben: 9 Zeilen, 145 Byte.

[5] programm_testen {{"datei": "blink.py", "erwartet": {{"pins": [2], "takt_hz": 1.0}}}}
    blink.py lief 4.0 s ohne Hardware (nach der Zeitgrenze beendet).
    Geschaltet wurde Pin 2, 9 Zustandswechsel.
    Takt: 1.000 s zwischen zwei Einschaltvorgaengen (1.00 Hz).
    ABNAHME BESTANDEN
      Anschluesse: erwartet [2], gemessen [2]  erfuellt
      Takt: erwartet 1.00 Hz, gemessen 1.00 Hz (Spielraum 10 %)  erfuellt

[6] esp32_firmware {{"port": "COM5", "nur_pruefen": true}}
    An COM5: Chip is ESP32-D0WD-V3 (revision v3.1)
    Darauf laeuft kein MicroPython — entweder ist das Brett fabrikneu oder es
    traegt ein anderes Programm. Beides macht nichts.

[7] esp32_firmware {{"port": "COM5"}}
    Firmware mitgeliefert (ESP32_GENERIC-...-v1.29.0.bin, 1790000 Byte),
    der gesamte Speicher wurde geloescht und neu beschrieben.

[8] esp32_uebertragen {{"port": "COM5", "datei": "blink.py"}}
    blink.py (145 Byte) nach COM5:main.py kopiert.
    Gegenprobe — Verzeichnis des Geraets: main.py
    Geraet neu gestartet.</code></pre>
<p>Die LED blinkt. Der ESP32 braucht ab jetzt keinen Rechner mehr: MicroPython führt
<code>main.py</code> aus, sobald Strom anliegt.</p>
<div class="kasten"><p><strong>Der ESP32 darf fabrikneu oder schon programmiert sein.</strong>
Schritt&nbsp;[6] sagt, was darauf ist; Schritt&nbsp;[7] löscht den Speicher vollständig und
schreibt MicroPython neu. Was vorher darauf war — ein Arduino-Sketch, ein alter Versuch,
nichts — spielt dafür keine Rolle. Es ist danach allerdings weg.</p></div>

<h3>Beispiel 2 — ohne jede Hardware</h3>
<p>Kein Steckbrett, kein Treiber, kein USB-Anschluss. Derselbe Auftrag, nur der letzte Satz
fällt weg:</p>
<pre><code>Schreibe ein MicroPython-Programm, das die LED an GPIO 2 einmal je Sekunde
blinken lässt, und prüfe es ohne Hardware gegen diese Erwartung.</code></pre>
<p>Die Schritte 1, 4 und 5 laufen genau wie oben. Bei Schritt&nbsp;3 meldet das Werkzeug:</p>
<pre><code>[3] ports_zeigen {{}}
    Es ist kein serieller Anschluss sichtbar.
    Zu pruefen: Steckbrett eingesteckt? USB-Kabel mit Datenadern?
    Treiber fuer CP2102 oder CH340 vorhanden?</code></pre>
<p>Das ist kein Abbruch — das Modell liest es und arbeitet weiter. Nach der bestandenen
Abnahme meldet es FERTIG und sagt dazu, dass das Überspielen aussteht.</p>

<p><strong>Und die LED blinkt trotzdem</strong> — auf dem Bildschirm. Der Prüfschritt öffnet
eine Seite mit der Aufzeichnung:</p>
<div style="background:#1a202c; border-radius:10px; padding:26px; margin:16px 0; text-align:center">
 <div style="display:inline-flex; flex-direction:column; align-items:center; gap:14px;
             background:#2d3748; border:1px solid #4a5568; border-radius:12px; padding:26px 44px">
  <div id="demoled" style="width:64px; height:64px; border-radius:50%; background:#f56565;
       border:3px solid #fc8181; box-shadow:0 0 34px 8px rgba(245,101,101,.6); transition:all .08s"></div>
  <div style="font-family:ui-monospace,monospace; color:#a0aec0; font-size:.85rem">Pin 2</div>
 </div>
 <div style="color:#718096; font-size:.82rem; margin-top:14px">so sieht es aus — hier im Takt der Aufzeichnung</div>
</div>

<div class="kasten gut"><p><strong>Das ist keine Nachahmung.</strong> Es ist dieselbe Datei, die
sonst auf den ESP32 geht, ausgeführt mit einem nachgebauten <code>machine</code>-Modul:
<code>Pin</code> schreibt seine Zustandswechsel in die Ausgabe, statt eine Leitung zu
schalten. Wer die Datei später überspielt, bekommt genau dieses Verhalten — dann an echten
Anschlüssen.</p>
<p>Nachgebildet sind <code>Pin</code>, <code>Signal</code>, <code>PWM</code>, <code>ADC</code>,
<code>reset</code>, <code>freq</code>. Alles andere meldet beim Aufruf, dass es nicht
nachgebildet ist — stillschweigend ein Scheinobjekt zu liefern wäre schlimmer als ein
Fehler: das Programm liefe scheinbar durch und versagte erst auf der Hardware.</p></div>

<h3>Was der Prüfschritt wirklich findet</h3>
<p>Vier Fälle, jeder davon im Entwurf dieses Pakets aufgetreten:</p>
<table><tr><th>Quelltext</th><th>Meldung</th></tr>
<tr><td><code>led.valu(1)</code> — Tippfehler</td><td>ABGEBROCHEN (Rückgabewert 1), mit der Fehlerzeile. <em>Darf so nicht auf den ESP32.</em></td></tr>
<tr><td><code>time.sleep(0.25)</code> statt <code>0.5</code></td><td>ABNAHME NICHT BESTANDEN — Takt: erwartet 1,00 Hz, gemessen 2,00 Hz</td></tr>
<tr><td><code>Pin(13, …)</code> statt <code>Pin(2, …)</code></td><td>ABNAHME NICHT BESTANDEN — Anschlüsse: erwartet [2], gemessen [13]</td></tr>
<tr><td>Pin gesetzt, aber nie umgeschaltet</td><td>ABNAHME NICHT BESTANDEN — nur 1 Einschaltvorgang, Takt nicht prüfbar</td></tr></table>
<p>In allen vier Fällen geht das Modell zurück an den Quelltext. Das ist der Grund für den
Schritt: nicht, dass etwas blinkt, sondern dass etwas <em>nicht</em> durchgeht.</p>
</div>

<div class="blatt" id="bh" hidden>
<h2>Hardware und Treiber</h2>

<div class="kasten"><p>Für den Kurs <strong>ohne</strong> Hardware wird nichts davon gebraucht —
Beispiel 2 läuft auf jedem Rechner. Dieser Reiter gilt, sobald ein echtes Steckbrett
blinken soll.</p></div>

<h3>Was gebraucht wird</h3>
<table><tr><th>Teil</th><th>was taugt</th><th>woran es scheitert</th></tr>
<tr><td>ESP32-Brett</td><td>jedes gängige mit USB-Buchse: ESP32-DevKitC, NodeMCU-32S, WROOM-32, auch S2/S3/C3</td><td>Bretter ohne USB-Buchse brauchen einen eigenen Programmieradapter</td></tr>
<tr><td>USB-Kabel</td><td>ein <strong>Datenkabel</strong></td><td><strong>Der häufigste Fehler im Kurs.</strong> Ein reines Ladekabel sieht genauso aus, hat aber nur die Stromadern. Der Rechner zeigt dann gar nichts an</td></tr>
<tr><td>LED</td><td>die eingebaute an GPIO 2 genügt</td><td>manche Bretter haben sie an GPIO 5, 13 oder 22 — dann die Nummer im Auftrag ändern</td></tr>
<tr><td>USB-Anschluss</td><td>direkt am Rechner</td><td>passive Verteiler liefern zu wenig Strom; das Brett meldet sich dann sprunghaft oder gar nicht</td></tr></table>

<h3>Der Wandler — das Teil, auf das es ankommt</h3>
<p>Der ESP32 spricht keine USB-Sprache. Zwischen ihm und der Buchse sitzt ein kleiner
Übersetzer, und <strong>für den</strong> braucht Windows einen Treiber. Welcher es ist,
steht in winziger Schrift auf dem Chip neben der Buchse — oder <code>ports_zeigen</code>
sagt es:</p>
<pre><code>2 serielle Anschluesse:
  COM3     —         Standardmäßige Seriellenschnittstelle
  COM5     1A86:7523 USB-SERIAL CH340   &lt;- QinHeng CH340
Nach dem Wandler zu urteilen koennte der ESP32 an COM5 haengen.</code></pre>
<table><tr><th>Kennung</th><th>Wandler</th><th>Treiber im Paket</th></tr>
<tr><td><code>1A86:7523</code></td><td>QinHeng CH340 — auf den meisten günstigen Brettern</td><td><code>CH341SER.ZIP</code></td></tr>
<tr><td><code>1A86:55D4</code></td><td>QinHeng CH9102</td><td><code>CH343SER.ZIP</code></td></tr>
<tr><td><code>10C4:EA60</code></td><td>Silicon Labs CP2102 / CP2104</td><td><code>CP210x_Universal_Windows_Driver.zip</code></td></tr>
<tr><td><code>0403:6001</code></td><td>FTDI FT232R</td><td>Windows bringt ihn mit</td></tr>
<tr><td><code>303A:…</code></td><td>Espressif selbst (S2/S3 mit eingebautem USB)</td><td>kein Treiber nötig</td></tr></table>

<h3>Treiber installieren — nur wenn nötig</h3>
<div class="kasten warn"><p><strong>Erst nachsehen, dann installieren.</strong> Windows 10 und 11
bringen CH340 und CP210x oft über Windows Update mit. Rufen Sie zuerst
<code>ports_zeigen</code> auf: erscheint ein COM-Anschluss mit einer der Kennungen oben, ist
nichts zu tun.</p></div>

<div class="schritt"><div class="nr">1</div><div>
<strong>Archiv entpacken.</strong> Rechtsklick auf die Datei in <code>paket\\treiber\\</code>,
„Alle extrahieren".</div></div>
<div class="schritt"><div class="nr">2</div><div>
<strong>Installationsprogramm starten.</strong> Bei WCH ist das <code>SETUP.EXE</code>, bei
Silicon Labs <code>CP210xVCPInstaller_x64.exe</code>. Windows fragt nach Adminrechten —
<strong>das ist das einzige Mal in diesem ganzen Kurs</strong>.</div></div>
<div class="schritt"><div class="nr">3</div><div>
<strong>ESP32 abziehen und neu einstecken.</strong> Ohne das erkennt Windows den gerade
installierten Treiber nicht.</div></div>
<div class="schritt"><div class="nr">4</div><div>
<strong><code>ports_zeigen</code> noch einmal.</strong> Jetzt muss der Anschluss auftauchen.</div></div>

<p>Die Treiber liegen im Paket, unmittelbar von der Herstellerseite über HTTPS geholt, mit
Prüfsummen in <code>paket\\treiber\\LIESMICH.md</code>. Eine Zwischenquelle kommt nicht in
Frage: ein Treiber läuft im Kern des Betriebssystems. Es liegen nur Archive dort und keine
fertigen Programme — ein <code>.exe</code> auf einem Stick lässt Virenscanner anschlagen.</p>

<h3>Was mit dem ESP32 geschieht</h3>
<table><tr><th>Zustand vorher</th><th>was der Agent tut</th></tr>
<tr><td>fabrikneu, ab Werk meist ein Arduino-Testprogramm</td><td>Speicher löschen, MicroPython schreiben</td></tr>
<tr><td>ein alter Arduino-Sketch</td><td>dasselbe — er ist danach weg</td></tr>
<tr><td>bereits MicroPython</td><td>die Prüfung meldet das; neu schreiben geht, ist aber nicht nötig</td></tr></table>
<div class="kasten warn"><p><strong>Der ESP32 wird wirklich verändert</strong>, und zwar
vollständig: <code>erase_flash</code> löscht den gesamten Speicher, dann wird MicroPython
geschrieben. Was vorher darauf war, ist weg. Das ist die einzige bleibende Änderung, die
dieses Paket macht — sie trifft das Steckbrett, nicht den Rechner.</p>
<p>Geschrieben wird erst, nachdem sich an diesem Anschluss ein ESP32 <em>gemeldet</em> hat.
Antwortet dort nichts oder etwas anderes, bricht das Werkzeug ab, ohne zu schreiben.</p></div>

<h3>Wenn sich nichts meldet</h3>
<table><tr><th>Beobachtung</th><th>Ursache und Abhilfe</th></tr>
<tr><td>gar kein COM-Anschluss</td><td>Ladekabel statt Datenkabel; Treiber fehlt; Brett nicht eingesteckt</td></tr>
<tr><td>COM-Anschluss da, aber „meldet sich kein ESP32"</td><td>ein anderes Programm hält ihn (Thonny, Arduino-Monitor, PuTTY) — schließen</td></tr>
<tr><td>Anschluss erscheint und verschwindet</td><td>zu wenig Strom: direkt an den Rechner statt an einen Verteiler</td></tr>
<tr><td>„Failed to connect … Wrong boot mode"</td><td>bei manchen Brettern BOOT gedrückt halten, während esptool verbindet</td></tr>
<tr><td>flasht durch, LED bleibt dunkel</td><td>die LED sitzt an einem anderen Anschluss. GPIO 5, 13 oder 22 im Auftrag versuchen</td></tr></table>
</div>

<div class="blatt" id="bm" hidden>
<h2>Das Sprachmodell</h2>
<p>Das Modell ist eine Datei im Paket, <code>paket\\modell\\*.gguf</code>, und ein Server, der sie lädt:
<code>llama-server.exe</code> aus <code>paket\\llama_signiert</code>. Dieser Server stammt aus dem
Ollama-Archiv und ist signiert (Ollama Inc., DigiCert), deshalb läuft er auch auf Rechnern, deren
Smart App Control nur signierte Programme zulässt. Er antwortet über eine Schnittstelle
(<code>/v1/chat/completions</code>) auf <code>127.0.0.1:8099</code>; der Agent schickt ihm den Verlauf
und bekommt Text zurück. Mehr Verbindung gibt es nicht.</p>
<table><tr><th>Modell</th><th>Datei</th><th>Rechner</th><th>gemessen</th></tr>
<tr><td><strong>Qwen2.5-Coder-3B-Instruct</strong> (Q4_K_M)</td><td>1,93 GB</td><td>ab 8 GB Arbeitsspeicher — <strong>die Wahl</strong></td>
<td>blink.py in 1–2 Anläufen, PWM-Atmen sinusförmig nach 3 Anläufen, Taschenrechner mit tkinter in einem Anlauf; scheitert an 3 Hz und an zwei LEDs mit zwei Takten; erzählt im langen Gespräch erfundene Arbeit; Hardwarefragen falsch</td></tr>
<tr><td>Qwen2.5-Coder-7B-Instruct (Q4_K_M)</td><td>4,68 GB</td><td>ab 16 GB</td><td>siehe Reiter „Stand und Grenzen“, Messreihe 3; schreibt Zeilenumbrüche im JSON doppelt maskiert, der Agent löst das auf</td></tr>
<tr><td>Qwen2.5-3B/7B-Instruct</td><td>1,93 / 4,68 GB</td><td>Rückfall</td><td>16 Aufrufe statt 4 für dieselbe Karte; nicht mehr die Wahl</td></tr>
<tr><td>Qwen3-Coder-30B-A3B</td><td>~18 GB</td><td>ab 24 GB</td><td>nicht gemessen — der ernsthafteste Kandidat für größere Rechner (3 Mrd. aktive Parameter, 30 Mrd. gesamt)</td></tr></table>
<p>Welches Modell läuft, entscheidet sich beim Start am freien Arbeitsspeicher; bei gleicher Größe wird das Coder-Modell vorgezogen,
weil die Aufgabe ein Modell „speziell für die Python-Programmierung“ verlangt. Keines der Modelle ist von uns nachtrainiert — kein
LoRA, kein Feintuning. Was das Modell über Werkzeuge, Methode und Brett weiß, steht in der Anweisung des Agenten und wirkt nur im Gespräch.</p>
<div class="kasten"><p><strong>Was ein kleines Modell kann und was nicht</strong> — gemessen am 04./05.10.2026: Es schreibt kurze
MicroPython- und Python-Programme richtig, hält das Werkzeugformat meist ein, berichtigt nach einer durchgefallenen Abnahme. Es
verwechselt die PWM-Trägerfrequenz mit dem Atemtakt, lässt Parameter weg (den Dateinamen), packt mehrere Aufrufe in eine Antwort,
und im langen Gespräch rutscht es in Erzählung: „Ich habe das Programm geschrieben, geprüft und übertragen“ — ohne ein Werkzeug.
Genau dafür gibt es den Agenten.</p></div>
<p>Kontextfenster 16384 Zeichenstücke; ist es voll, fasst der Agent ältere Schritte zusammen. Jede Antwort des Modells steht im
Protokoll — nichts ist erfunden oder vorgegeben, und nichts gilt, bevor es geprüft ist.</p>
</div>

<div class="blatt" id="ba" hidden>
<h2>Der Agent</h2>
{SKIZZE}
<p>Der Agent ist ein Python-Programm (<code>agent\\agent.py</code>, Klasse <code>Sitzung</code>). Er kennt die Werkzeuge
(er fragt jedes beim Start nach seiner Beschreibung), er kennt die Methode (schreiben, prüfen, berichtigen, ausliefern, nachlesen),
und er stellt beides dem Modell bereit — als Anweisung, als Vorschlag im Ergebnis („NÄCHSTER SCHRITT“), als vorgerechnete Zahl
(welche Pause für 10 Hz), als Wissen über das Brett. Das Modell entscheidet frei; der Agent führt aus und <strong>wacht</strong>.</p>
<h3>Ein Vergleich mit dem Gehirn</h3>
<p>Ein Vergleich, kein Beweis — aber einer, der die Rollen klärt: <strong>Das Sprachmodell ist der Speicher des Erlernten.</strong>
Es hat Millionen Programme gesehen und gibt auf eine Frage das wieder, was dazu passt — flüssig, plausibel, ohne zu wissen, ob es
hier und jetzt stimmt. Erinnerung ohne Gegenwart. <strong>Der Agent ist das Bewusstsein.</strong> Er weiß, was gerade der Fall ist:
welche Datei geschrieben wurde, welche geprüft, was der Mensch wirklich gesagt hat, welcher Anschluss genannt ist. Er hält die
Absicht fest (die Erwartung), vergleicht sie mit dem, was geschieht, und lässt eine Erinnerung nicht als Tat gelten. Die
<strong>Werkzeuge sind Hände und Sinne</strong>: Sie greifen in die Welt (Datei schreiben, Gerät beschreiben) und melden zurück, was
dort wirklich ist (die LED blinkt mit 2,06 Hz). Und die <strong>Werkstatt mit Protokoll ist das Gedächtnis des Tages</strong>: was
getan wurde, steht da, nicht was erzählt wurde.</p>
<p>Daraus folgt die Arbeitsteilung des Pakets. Wo der Speicher erzählt, es habe geprüft, fragt das Bewusstsein: Welches Werkzeug lief?
Wo der Speicher die Erwartung verschiebt, weil das Programm nicht passt, hält das Bewusstsein die Absicht fest. Wo der Speicher
in Prosa verfällt, holt das Bewusstsein ihn ohne Vorgeschichte zur Tat zurück. Ein größeres Modell ist ein größerer Speicher —
ein besseres Bewusstsein ist ein strengerer Agent. Beides braucht man; das zweite ist hier das Lehrstück.</p>

<h3>Der Agent, genau</h3>
<p>Eine <code>Sitzung</code> wird beim ersten Satz geöffnet und bleibt, bis der Mensch ein neues Gespräch beginnt. Jede Anweisung
durchläuft dieselben Schritte:</p>
<table><tr><th></th><th>Schritt</th><th>was genau geschieht</th></tr>
<tr><td>1</td><td>Vom Menschen lesen</td><td>Die Anweisung wird ins Protokoll geschrieben. Aus ihren Worten kommen die <em>Erwartung</em> (Pins aus „GPIO 4“, Takt aus „10 Hz“ oder „eine Periode pro Sekunde“, Form aus „sinusförmig“), die genannten Dateinamen, die genannten Anschlüsse („com 3“ = COM3). Ändert sich die Erwartung, gilt die betroffene Datei als ungeprüft.</td></tr>
<tr><td>2</td><td>Eigenes Programm</td><td>Steht in der Anweisung ein Codeblock, schreibt der Agent ihn selbst wörtlich in die Werkstatt und sagt dem Modell, dass es nur noch prüfen soll.</td></tr>
<tr><td>3</td><td>Modell bereit</td><td>Beim ersten Mal wird der Modellserver gestartet (signiert, Kontext 16384); danach bleibt er geladen. Scheitert der Start, läuft dieselbe Kette mit einem festen Drehbuch — der Kurs darf daran nicht enden.</td></tr>
<tr><td>4</td><td>Zwischenrufe</td><td>Vor jedem Schritt werden Eingaben aufgenommen, die der Mensch während des Laufs gemacht hat (Anschluss, neue Erwartung, Korrektur); die Warteschlange des Modells verfällt dann.</td></tr>
<tr><td>5</td><td>Das Modell fragen</td><td>Der Verlauf geht an den Server. Ist das Kontextfenster voll, werden ältere Schritte zusammengefasst und es wird erneut gefragt. Enthält die Antwort mehrere Werkzeugaufrufe, werden sie der Reihe nach abgearbeitet, ohne das Modell erneut zu fragen.</td></tr>
<tr><td>6</td><td>Antwort in Worten</td><td>Kein Werkzeug, kein FERTIG: Die Antwort gilt dem Menschen und beendet die Anweisung. Behauptet sie etwas, das kein Werkzeug der Sitzung belegt, steht eine Anmerkung des Agenten darunter.</td></tr>
<tr><td>7</td><td>FERTIG prüfen</td><td>In dieser Reihenfolge: Ist etwas ungeprüft und FERTIG kam schon einmal zurück — der Agent prüft selbst. Wurde Arbeit erzählt, die kein Werkzeug tat — „das ist nicht wahr“, und das Modell wird ohne Vorgeschichte nur nach dem nächsten Aufruf gefragt (Fokus). Verlangte die Anweisung laden oder nachlesen und es lief nicht — Fokus mit dem genannten Anschluss. Nennt der Auftrag eine Datei, die nie geschrieben wurde; ist eine Datei ungeprüft; fiel die letzte Prüfung durch — jeweils Zurückweisung mit dem Grund und der vorgerechneten Zahl. Nach drei Zurückweisungen endet die Anweisung als <strong>NICHT ABGENOMMEN</strong>. Erst wenn nichts davon zutrifft, gilt FERTIG.</td></tr>
<tr><td>8</td><td>Werkzeug prüfen</td><td>Vor dem Ausführen: <code>aufraeumen</code> nie; Geräteaufrufe nur mit einem Anschluss, den der Mensch nannte; <code>esp32_uebertragen</code> nur mit einer Datei, die zuletzt bestanden hat; <code>programm_testen</code> nur mit einer in dieser Sitzung geschriebenen Datei, mit der Erwartung des Menschen (nicht der des Modells), ohne eigenen Browser-Reiter; fehlt der Dateiname, gilt die zuletzt geschriebene; doppelt maskierte Zeilenumbrüche werden aufgelöst.</td></tr>
<tr><td>9</td><td>Ausführen und merken</td><td>Das Werkzeug läuft als eigener Prozess. Danach: geschrieben, ungeprüft, abgenommen, letzter Befund werden fortgeschrieben; eine durchgefallene Abnahme bekommt den nächsten Schritt mit der passenden Zahl (bei 10 Hz: 0,05 s je Pause; bei Atmen: Periode geteilt durch Stufen); der dritte gleiche Fehlschlag bekommt den Rat, anders vorzugehen. Ins Protokoll kommt die erste Zeile samt Urteil, in die Oberfläche alles, ins Gedächtnis des Modells eine Kurzfassung.</td></tr>
<tr><td>10</td><td>Ende</td><td>Nach höchstens 25 Schritten endet die Anweisung als Abbruch. Bricht der Agent selbst ab, schreibt er <code>ablage\\fehlerbericht.txt</code>; das Protokoll endet mit ABBRUCH und ENDE. Der Mensch gibt die nächste Anweisung.</td></tr></table>

<h3>Das Gespräch</h3>
<p>Eine Sitzung hält über alle Anweisungen hinweg: den Verlauf für das Modell, welche Dateien geschrieben, geprüft und abgenommen
sind, welche Anschlüsse der Mensch genannt hat, die Erwartung. Der Modellserver bleibt geladen. „Nimm GPIO 4“, „ändere auf 3 Hz“,
„lade es an COM3 und lies nach“, ein eigenes Programm in <code>```</code>-Zeichen — alles bezieht sich auf das Vorige. Während der
Agent arbeitet, bleibt das Eingabefeld offen: ein Zwischenruf wird beim nächsten Schritt aufgenommen.</p>
<h3>Die Regeln, über die der Agent wacht</h3>
<table><tr><th>Regel</th><th>Anlass</th></tr>
<tr><td>Die Erwartung setzt der Mensch (Pins, Takt, Form), aus seinen Worten gelesen, auch „eine Periode pro Sekunde“; sie bleibt, bis er sie ändert. Was er nicht festlegt, legt der erste Aufruf des Modells fest — außer unsichtbare Takte über 50 Hz.</td><td>das Modell schrieb 1,0 Hz in 0,5 Hz um, damit sein Programm besteht; später 1000 Hz Trägerfrequenz als „Takt“</td></tr>
<tr><td>Geprüft wird nur, was in dieser Sitzung geschrieben wurde; eine Änderung ohne neue Prüfung ist nicht abgenommen; FERTIG wird bis zu dreimal zurückgewiesen, dann endet die Anweisung als NICHT ABGENOMMEN.</td><td>Prüfung lief gegen eine alte Datei aus der Nacht; dritte Fassung geschrieben, nie geprüft, FERTIG</td></tr>
<tr><td>Sagt das Modell FERTIG, ohne zu prüfen, prüft der Agent selbst — sichtbar als eigener Aufruf.</td><td>viermal geschrieben, nie programm_testen gerufen</td></tr>
<tr><td>Was im FERTIG steht, muss ein Werkzeug getan haben — in dieser Anweisung. Erzählt das Modell erfundene Arbeit, sagt der Agent, dass es nicht wahr ist, und fragt es ohne Vorgeschichte nur nach dem nächsten Aufruf (Fokus).</td><td>„geschrieben, geprüft, übertragen, die LED blinkt“ — kein Werkzeug lief</td></tr>
<tr><td>Kein Anschluss wird geraten; nur ein vom Menschen genannter gilt (auch als „com 3“). Auf das Gerät kommt nur, was zuletzt bestanden hat.</td><td>das Modell wollte COM5 flashen</td></tr>
<tr><td><code>aufraeumen</code> gehört nicht in die Hand des Modells.</td><td>es löschte mitten im Auftrag die Ablage samt Protokoll</td></tr>
<tr><td>Mehrere Aufrufe in einer Antwort werden der Reihe nach ausgeführt; doppelt maskierte Zeilenumbrüche werden aufgelöst; ein Aufruf ohne JSON gilt als leere Eingabe.</td><td>Formmarotten der Modelle</td></tr>
<tr><td>Bricht der Agent ab, schreibt er <code>ablage\\fehlerbericht.txt</code>; das Protokoll endet mit ABBRUCH und ENDE.</td><td>auf einem fremden Rechner sieht niemand zu</td></tr></table>
<p>Jede dieser Regeln hat eine Gegenprobe im Prüfstand (<code>pruefstand\\pruefe_gespraech.py</code>, <code>pruefe_regeln.py</code>,
<code>pruefe_ungeprueft.py</code>), die durchfallen muss, wenn man die Regel ausbaut. Ohne Modell läuft dieselbe Kette mit einem festen Drehbuch.</p>
</div>

<div class="blatt" id="bw" hidden>
<h2>Die Werkzeuge</h2>
<p>Jedes Werkzeug ist ein eigenes Programm in <code>agent\\werkzeuge\\</code> mit zwei Betriebsarten: <code>--beschreibung</code>
sagt als JSON, was es kann; <code>'{{…}}'</code> tut es und schreibt das Ergebnis als Text. Ein Fehler wird Text, nie eine Ausnahme;
jedes Schreiben geht in die Ablage. Diese Tabelle ist beim Erzeugen der Seite aus den Programmen gelesen, nicht abgeschrieben:</p>
<table><tr><th>Werkzeug</th><th>was es tut</th><th>Felder</th></tr>
{zeilen}
</table>
<h3>Wie sie zusammenspielen</h3>
<pre><code>umgebung_anlegen        eigenes Python aus dem Paket, dazu tkinter      zuerst
   └─ paket_installieren   esptool, mpremote aus dem Vorrat (keine Netzverbindung)
         ├─ ports_zeigen        welcher Anschluss? — der Mensch bestätigt
         └─ esp32_firmware      MicroPython aufs Gerät (löscht das Brett)

schreib_datei           das Programm entsteht in der Werkstatt
   ├─ programm_testen      Nachbau ohne Hardware, Abnahme gegen die Erwartung   ← hier wird entschieden
   │     └─ esp32_uebertragen  nur Abgenommenes aufs Gerät; liest danach selbst nach
   │           └─ esp32_nachlesen  misst am Gerät: Flanken (µs) oder Tastgrad (PWM)
   └─ programm_ausfuehren  jedes andere Python-Programm: Konsole oder Fenster (tkinter)

nachweis_autark         vorher / nachher: der Rechner blieb, wie er war
aufraeumen              am Kursende, über START.bat [2]</code></pre>
</div>

<div class="blatt" id="bp" hidden>
<h2>Prüfen und Messen</h2>
<p>Der Kern des Lehrbeispiels: Ein Sprachmodell schreibt in Sekunden ein Programm, das plausibel aussieht. Ob es tut, was verlangt
war, entscheidet keine Meinung, sondern eine Messung, die durchfallen kann. Es gibt zwei unabhängige Wege, und erst wenn beide
übereinstimmen, gilt ein Programm als abgenommen.</p>
<h3>Weg 1 — der Nachbau (<code>programm_testen</code>)</h3>
<p>Derselbe Quelltext wie für den ESP32 läuft auf dem PC; nur das <code>machine</code>-Modul ist nachgebaut und zeichnet auf, was das
Programm an den Anschlüssen tut. Die Zeit ist eine <strong>gedachte Uhr</strong>: <code>time.sleep</code> rückt sie vor, statt zu warten,
plus 0,8 ms Rechenzeit je Runde, wie sie MicroPython auf dem ESP32 braucht (kalibriert am 05.10.2026: 11 Atemzüge in 20 s bei 1024 Stufen
zu 1 ms). Grund: Windows hält 10 ms Schlaf nicht ein, der ESP32 schon; ein Lauf dauert so Bruchteile einer Sekunde statt sechs.
Gemessen werden Pins (Wechsel, Takt) und bei PWM die Hüllkurve des Tastgrads: Periode, Takt, Form (sinusförmig oder dreieckig —
„Dreieck ist kein Sinus“). Die Abnahme vergleicht mit der Erwartung des Menschen: Anschlüsse, Takt (10 % Spielraum), Form.</p>
<h3>Weg 2 — das Gerät (<code>esp32_nachlesen</code>)</h3>
<p>Das Programm läuft auf dem ESP32, und der ESP32 misst selbst: Flanken per Interrupt mit seinem Mikrosekundenzähler
(2,0000 s zwischen zwei Einschaltvorgängen bei einem 1-s/1-s-Programm), bei PWM der Tastgrad direkt aus dem PWM-Kanal, alle 10 ms aus einem
Zeitgeber-Interrupt, damit das Programm nicht gebremst wird. Ein meldendes Programm und die Brücke, die nur seriell mitliest, waren der
dritte Weg, als Auge und Gerät sich widersprachen — das Gerät hatte recht.</p>
<h3>Was dabei herauskam</h3>
<table><tr><th>Programm</th><th>Nachbau</th><th>Gerät</th><th>Auge</th></tr>
<tr><td>blink.py 1 s an / 1 s aus</td><td>0,50 Hz</td><td>0,500 Hz, 2,0000 s</td><td>„1 zu 1, subjektiv“</td></tr>
<tr><td>blink.py 2 Hz</td><td>2,00 Hz</td><td>2,06 Hz; seriell „AN“ alle 500 ms</td><td>erst „1 Hz“, dann „viel schneller“ — das Auge zählt schlecht</td></tr>
<tr><td>atmen.py 1024 Stufen × 1 ms, Kosinus</td><td>vor der Rechenzeit 1 Hz, danach 0,55 Hz</td><td>0,49 Hz, sinusförmig</td><td>11 Atemzüge in 20 s = 0,55 Hz</td></tr></table>
<p>Der Prüfstand im Arbeitsbereich fährt dieselben Werkzeuge mit einem festen Modell und festen Antworten und hat zu jeder Regel eine
Gegenprobe, die durchfallen muss: <code>pruefe_schleife.py</code> (8), <code>pruefe_regeln.py</code> (28), <code>pruefe_gespraech.py</code> (30),
<code>pruefe_ungeprueft.py</code> (6), <code>pruefe_pwm.py</code> (7), dazu <code>pruefe_alles.py</code> (19) gegen das Anforderungsblatt.</p>
</div>

<div class="blatt" id="bs" hidden>
<h2>Stand und Grenzen</h2>
<div class="kasten warn"><p><strong>Vermerk der Unvollständigkeit.</strong> Dieses Paket ist ein Lehrbeispiel, kein fertiges Produkt. Es
zeigt, wie eine lokale KI mit einem Agenten und messenden Werkzeugen Programme schreibt, prüft und auf Hardware bringt — und es zeigt
ebenso ehrlich, woran ein kleines Modell scheitert. Alles, was hier als „funktioniert“ steht, ist am 04./05.10.2026 auf einem Windows-Laptop
(8 GB frei, Smart App Control EIN) mit einem ESP32 an COM3 gemessen worden; alles andere steht als offen da.</p></div>
<h3>Was funktioniert, gemessen</h3>
<ul>
<li>Das Paket läuft aus einem Ordner, ohne Installation, ohne Netz, mit eigenem Python; der Rechner bleibt unverändert (Nachweis vorher/nachher).</li>
<li>Das Sprachmodell lädt unter Smart App Control über den signierten Server; das Gespräch im Browser; Zwischenruf.</li>
<li>Die Kette: blink.py schreiben, im Nachbau prüfen, nach durchgefallener Abnahme berichtigen, auf den ESP32 übertragen, am Gerät nachlesen — 1 Hz, 2 Hz, 0,5 Hz, jeweils vom Gerät bestätigt.</li>
<li>PWM-Atmen sinusförmig: vom Modell nach drei Anläufen richtig geschrieben, Form und Takt gemessen; auf dem Gerät langsamer als im Nachbau, bis die Rechenzeit kalibriert war.</li>
<li>Ein Taschenrechner mit grafischer Oberfläche (tkinter aus dem Paket) in einem Anlauf; Programme mit Eingabe und Ausgabe.</li>
<li>Keine erfundene Behauptung des Modells ist je als abgenommen durchgegangen.</li>
</ul>
<h3>Was nicht verlässlich geht</h3>
<ul>
<li>Das 3B-Modell trifft 3 Hz nicht (25 Schritte, fünf Selbstprüfungen, Abbruch) und schafft zwei LEDs mit zwei Takten nicht (blockierende Schleifen).</li>
<li>Im langen Gespräch erzählt es Arbeit, die es nicht getan hat; der Agent fängt das ab, aber es kostet Schritte und Zeit (bis zu 25 × 20 s).</li>
<li>Hardwarefragen beantwortet es falsch („die LED am Bildschirm“); das Brettwissen in der Anweisung mildert das, ersetzt es nicht.</li>
<li>Die Rücklesung bei PWM bremst das Programm noch leicht (0,49 Hz gemessen gegen 0,55 Hz gezählt).</li>
</ul>
<h3>Der Nachmittag des 05.10.2026 — die neun festen Anfragen, ohne Fake</h3>
<p>Vorgabe: „Wenigstens die vorgefertigten Fragen müssen durchlaufen durch das System, und zwar ohne eine Fake-Sache. Der Agent soll die
Realität prüfen, nicht das Wunschdenken.“ Die Läufe mit dem echten Modell zeigten neun Lücken im Agenten, jede mit Uhrzeit im
Prüfprotokoll (J19–J27, K7): ein leeres FERTIG auf eine Aufgabe; „die Zeile wurde korrigiert“ ohne Werkzeug, dreimal derselbe Satz; ein
Schlusssatz mit falscher Zahl („Periode von 2 Sekunden“ bei 2 Hz); der Rügetext des Agenten als Schlusssatz des Modells nachgeplappert;
„Lade blink.py auf den ESP32“ ließ das Modell die Datei umschreiben statt zu übertragen; ein fehlgeschlagenes Übertragen zählte als gelaufen;
fünf Minuten je Antwort im langen Gespräch; ein Taschenrechner wurde gegen Pins geprüft, weil eine ESP32-Erwartung aus der
Anweisung davor stand; ein Ein/Aus-Programm erbte die Kurvenform „sinusförmig“ vom Atmen davor. Behoben wurde das im Agenten, nicht im Modell: Unter jedem FERTIG steht jetzt, was die Werkzeuge
gemessen haben; der Agent zeigt dem Modell die Datei und den Befund ohne Vorgeschichte und prüft selbst nach; den Geräteschritt führt er
notfalls selbst aus; der Verlauf wird je Anweisung verdichtet. Was das Modell schreibt, bleibt sichtbar — daneben steht, was wahr ist.</p>
{neun_fragen()}
<h3>Messreihe 3 — Qwen2.5-Coder-3B gegen -7B, dasselbe Gespräch, derselbe Agent (05.10.2026, Prüfstand ohne Grafikkarte)</h3>
{messreihe()}
<p>Lesart: „Ende“ ist, wie die Anweisung ausging; „Abnahmen“ zählt bestandene (✓) und durchgefallene (✗) Prüfungen; „selbst“ heißt, der Agent
musste die Prüfung auslösen, weil das Modell FERTIG sagte, ohne zu prüfen. Die 3B-Reihe wurde nach sechs Anweisungen abgebrochen, um dem 7B
den Prüfstand freizugeben.</p>
<h3>Was als Nächstes käme</h3>
<ul>
<li>Zwei, drei vollständige Beispielabläufe in die Anweisung des Modells — der billigste Hebel, in einer Stunde gebaut und messbar.</li>
<li>Ein LoRA-Adapter aus den gesammelten Protokollen: richtige Abläufe als Lehrbeispiele, erfundene mit der Korrektur als Gegenbeispiele; einige hundert Stück, ein paar GPU-Stunden; llama.cpp lädt den Adapter zur Laufzeit.</li>
<li>Qwen3-Coder-30B-A3B auf einem Rechner mit 24 GB — vermutlich der größte Sprung, nicht gemessen.</li>
<li>Kursmaterial: Aufgabenblätter, die den Weg vom Satz zur Messung in Schritten gehen.</li>
</ul>
</div>

<div class="blatt" id="b5" hidden>
<h2>Was der Rechner davon merkt</h2>
<p><strong>Nichts.</strong> Und das wird gemessen, nicht behauptet: beim Start nimmt das Paket
den Zustand der gefährdeten Stellen auf, beim Aufräumen vergleicht es ihn und zeigt das
Ergebnis, bevor es löscht.</p>

<table><tr><th>Stelle</th><th>warum sie gefährdet wäre</th><th>was dagegen geschieht</th></tr>
<tr><td>Python des Rechners und seine <code>site-packages</code></td><td>hierhin schriebe ein <code>pip install</code> normalerweise</td><td>installiert wird nur mit dem eigenen Python in <code>ablage\\python</code></td></tr>
<tr><td><code>%APPDATA%\\Python</code></td><td>das Benutzer-Paketverzeichnis; pip weicht dorthin aus</td><td><code>PYTHONNOUSERSITE=1</code></td></tr>
<tr><td><code>%LOCALAPPDATA%\\pip</code></td><td>der pip-Zwischenspeicher — wird unbemerkt mehrere hundert MB groß</td><td><code>PIP_CACHE_DIR</code> zeigt in die Ablage</td></tr>
<tr><td><code>PATH</code>, <code>PYTHON*</code>, <code>PIP_*</code></td><td>ein halb fremdes Python ist der am schwersten zu findende Fehler</td><td>werden für die Unterprozesse entfernt</td></tr></table>

<div class="kasten gut"><p>Programme werden an <strong>fünf</strong> Stellen gestartet: die Werkzeuge tun es an genau einer (<code>lauf()</code> in <code>_muster.py</code>), dazu startet der Agent die Werkzeuge, der Modellserver wird gestartet, und einmal startet sich das eigene Python neu. <strong>Alle fünf reichen dieselbe abgeschirmte Umgebung weiter.</strong> Stünde der Aufruf an neun Stellen, würde die zehnte es vergessen, und zwar unbemerkt: auf dem Rechner des Erbauers ist <code>PYTHONPATH</code> nicht gesetzt und der Zwischenspeicher schon warm; der Fehler zeigte sich erst im Kurs. Deshalb prüft <code>pruefe_alles.py</code> das als <strong>B10</strong> und fällt durch, sobald eine Stelle die Umgebung vergisst.</p></div>

<h3>Löschen und nachzählen</h3>
<p>Alles Erzeugte liegt in <strong>einem</strong> Ordner. Das erzwingt der Werkzeugrahmen: jeder
Schreibpfad wird aufgelöst und gegen die Ablage geprüft, bevor eine Datei entsteht. Deshalb
ist <code>aufraeumen</code> ein Beweis und keine Behauptung — es löscht genau diesen Ordner
und zählt hinterher nach.</p>

<h3>Wiederholbar</h3>
<p>Gemessen über drei volle Zyklen: anlegen, nachweisen, aufräumen. Die Prüfsumme über
<code>paket\\</code> war vorher und nachher dieselbe, jedes Mal null Reste. Das Mitgelieferte
wird nur gelesen — darum läuft derselbe Ordner beliebig oft.</p>

<h3>Fremder Quelltext</h3>
<p>Es gibt genau eine Stelle, an der Quelltext ausgeführt wird, den ein Sprachmodell
geschrieben hat: <code>programm_testen</code>. Davor liest ein Prüfer den Syntaxbaum —
erlaubt sind <code>machine</code> und <code>time</code>, verboten sind unter anderem
<code>open</code>, <code>eval</code>, <code>getattr</code> und alle Namen mit doppeltem
Unterstrich, über die der Weg außen herum führt.</p>
<div class="kasten warn"><p>Dieser Prüfer ist <strong>kein Schutz gegen einen Angreifer</strong> —
gegen den hilft kein Filter, sondern nur, fremden Quelltext gar nicht auszuführen. Er ist
ein Schutz gegen ein Modell, das sich vertut, und das ist der Fall, der wirklich eintritt.
Dazu kommen Zeitgrenze, eigenes Python und die abgeschirmte Umgebung.</p></div>

<div class="kasten warn"><p>Zwei Dinge gehören ungeschönt dazu:</p>
<p><strong>Die Registrierung wird nicht gemessen</strong>, nur begründet: nichts im Paket ruft ein
Installationsprogramm auf. Begründet ist nicht gemessen.</p>
<p><strong>Der ESP32 wird wirklich verändert.</strong> Sein Speicher wird gelöscht und mit
MicroPython neu beschrieben; was vorher darauf war, ist weg. Das ist der Zweck der Übung —
und es ist die einzige bleibende Änderung, die dieses Paket macht. Sie trifft das Steckbrett,
nicht den Rechner.</p>
<p>Der <strong>USB-Treiber</strong> ist das Einzige, was eine echte Installation mit Adminrechten
bräuchte — falls Windows den Wandler nicht kennt. Der Agent installiert ihn nicht; das
entscheidet ein Mensch.</p></div>
</div>

<div class="blatt" id="b6" hidden>
<h2>Wenn es klemmt</h2>
<table><tr><th>Meldung</th><th>was zu tun ist</th></tr>
<tr><td>„Es ist kein serieller Anschluss sichtbar"</td><td>Steckbrett eingesteckt? Datenkabel statt Ladekabel? Sonst Treiber aus <code>paket\\treiber\\</code> installieren (Adminrechte) und neu einstecken. Ohne Hardware geht es weiter, siehe Beispiel 2</td></tr>
<tr><td>„An COM5 meldet sich kein ESP32"</td><td>anderer Anschluss (<code>ports_zeigen</code>), oder Thonny hält den Anschluss noch belegt. Bei manchen Brettern BOOT beim Einstecken drücken</td></tr>
<tr><td>„llama-server hat sich sofort beendet"</td><td>zu wenig Arbeitsspeicher. Kleineres Modell: <code>hole_paket.py --modell coder-3b</code> oder <code>1.5b</code></td></tr>
<tr><td>Modell antwortet, ruft aber kein Werkzeug</td><td>kommt bei kleinen Modellen vor. Menüpunkt <strong>[7]</strong> macht dieselben Schritte mit fester Reihenfolge</td></tr>
<tr><td>ABNAHME NICHT BESTANDEN</td><td>kein Fehler des Pakets, sondern sein Zweck. Die Befunde sagen, welche Zahl nicht stimmt; das Modell berichtigt den Quelltext und prüft erneut</td></tr>
<tr><td>„ist abgebrochen (Rückgabewert 1)"</td><td>das erzeugte Programm hat einen Fehler. Die Meldung darunter nennt Datei und Zeile</td></tr>
<tr><td>„machine.I2C ist nicht nachgebildet"</td><td>das Programm benutzt etwas, das der Lauf ohne Hardware nicht kennt. Dann hilft nur das Gerät selbst</td></tr>
<tr><td>„Es blieben N Dateien zurück"</td><td>eine Datei ist noch geöffnet (Editor, serieller Monitor). Schließen, Aufräumen wiederholen</td></tr>
<tr><td>„pip ließ sich nicht einrichten"</td><td>meist ein Virenscanner, der <code>get-pip.py</code> abfängt. Ordner als Ausnahme eintragen</td></tr>
<tr><td>Kein Python gefunden</td><td><code>START.bat</code> packt dann das mitgelieferte aus. Für Menüpunkt [4] genügt das nicht — Füllen braucht ein Python mit pip</td></tr></table>

<h3>Wenn Sie nicht weiterkommen: ein Bericht genügt</h3>
<p>Menüpunkt <strong>[8] Bericht sammeln</strong> schreibt alles, was zur Beurteilung von außen
nötig ist, in <strong>eine</strong> Datei <code>BERICHT_&lt;Datum&gt;.txt</code> neben
<code>START.bat</code>: dieser Rechner, was im Paket liegt und was fehlt, die Selbstprüfung mit
jedem Punkt, jedes Werkzeug einmal aufgerufen, das Protokoll des letzten Laufs und der Inhalt
der Ablage.</p>
<p>Diese Datei weitergeben genügt — niemand muss danebensitzen und erklären, was er gesehen hat.
Benutzer- und Rechnername sind durch Platzhalter ersetzt: der Bericht soll sagen, was das Paket
tut, nicht wem der Rechner gehört.</p>

<h3>Das Protokoll</h3>
<p><code>ablage\\protokoll.txt</code> hält jeden Werkzeugaufruf mit Uhrzeit fest. Es wird beim
Aufräumen mit gelöscht — wer es behalten will, kopiert es vorher heraus.</p>

<h3>Von Hand nachsehen</h3>
<pre><code>python agent\\agent.py --werkzeuge            was es gibt
python agent\\agent.py --probe                jedes einmal aufrufen
python agent\\pfade.py                        was im Paket fehlt
python agent\\werkzeuge\\ports_zeigen.py "{{}}"  ein Werkzeug einzeln</code></pre>
</div>

<footer>
Kurs-Agent {FASSUNG} · {heute} · Prof. Dr.-Ing. Ralph Wystup M.Sc.<br>
erstellt mit KI und Agent (Claude Code, Anthropic)
</footer>

<script>
// Die LED im Beispiel 2 blinkt im Takt der Aufzeichnung: eine Sekunde, wie im Auftrag.
setInterval(() => {{
  const d = document.getElementById('demoled');
  if (!d) return;
  const an = d.dataset.an !== '1';
  d.dataset.an = an ? '1' : '0';
  d.style.background = an ? '#f56565' : '#4a5568';
  d.style.borderColor = an ? '#fc8181' : '#718096';
  d.style.boxShadow = an ? '0 0 34px 8px rgba(245,101,101,.6)' : 'none';
}}, 500);

const knoepfe = document.querySelectorAll('.reiter button');
knoepfe.forEach(k => k.addEventListener('click', () => {{
  knoepfe.forEach(a => a.setAttribute('aria-selected', a === k));
  document.querySelectorAll('.blatt').forEach(b => b.hidden = (b.id !== k.dataset.z));
}}));
</script>
</body></html>"""


if __name__ == "__main__":
    ZIEL.write_text(seite(), encoding="utf-8")
    print(f"{ZIEL.name}: {ZIEL.stat().st_size/1024:.0f} kB, "
          f"{len(werkzeuge())} Werkzeuge aus den Programmen gelesen")
