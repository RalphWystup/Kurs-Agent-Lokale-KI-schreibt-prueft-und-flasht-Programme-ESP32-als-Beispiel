#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zeigt, welche Felder ein Werkzeug erwartet — auf Abruf statt auf Vorrat.

Warum es dieses Werkzeug gibt (10.10.2026)
------------------------------------------
Bis zu diesem Tag bekam das Modell bei JEDEM Auftrag alle zwanzig Werkzeuge mit voller
Beschreibung und vollstaendiger Feldliste vorgelegt: 3081 Token. Gemessen wurde, was das
kostet — fuer „hallo, bist du bereit?" las der Server 5730 Token ein und brauchte dafuer
173 Sekunden, waehrend dasselbe Modell ohne diesen Ballast in 10 Sekunden freundlich
antwortet.

Der Auftraggeber: „immer doch nur das fragen an das LLM, was noetig ist. Schau doch mal
nach, wie Claude Code das macht." Claude Code macht es so: Die staendig gebrauchten
Werkzeuge stehen vollstaendig im Anweisungstext, alle uebrigen nur mit Namen, und ihr
Schema wird nachgeladen, wenn es gebraucht wird. Dieses Werkzeug ist das Nachladen.

Im Anweisungstext stehen seitdem vollstaendig: schreib_datei, programm_testen,
quelltext_pruefen. Von allen anderen sieht das Modell nur, wofuer sie da sind.

Gerechnet: Die Werkzeugliste faellt damit von 3081 auf rund 814 Token, der ganze
Anweisungstext von 5730 auf 3441 (gemessen). Der Preis ist ein zusaetzlicher Aufruf, wenn
die Felder wirklich gebraucht werden — rund zwei Sekunden.
"""
import json
import pathlib
import sys

_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch                                   # noqa: E402


def _alle() -> dict:
    """Alle Werkzeuge mit ihrer Beschreibung — gelesen wie der Agent sie liest."""
    import agent                                                        # noqa: E402
    return agent.sammlung()


def tun(e: dict) -> str:
    name = (e.get("name") or e.get("werkzeug") or "").strip()
    alle = _alle()
    if not name:
        liste = "\n".join(f"  {n}" for n in sorted(alle))
        raise Abbruch("Welches Werkzeug? Gib seinen Namen an:\n"
                      '  WERKZEUG: werkzeug_zeigen {"name": "esp32_laden"}\n\n'
                      f"Es gibt diese:\n{liste}")
    if name not in alle:
        from difflib import get_close_matches
        nah = get_close_matches(name, list(alle), n=3, cutoff=0.6)
        #  Wer Nein sagt, sagt wohin (Kriterium L1): Die Abweisung nennt den naechsten
        #  Schritt mit Werkzeugnamen und Feldern, nicht nur das Problem.
        vorschlag = nah[0] if nah else sorted(alle)[0]
        raise Abbruch(f"Ein Werkzeug '{name}' gibt es nicht."
                      + (f" Meintest du {', '.join(nah)}?" if nah else "")
                      + f"\nRufe es mit dem richtigen Namen auf:\n"
                        f'  WERKZEUG: werkzeug_zeigen {{"name": "{vorschlag}"}}\n'
                        f"Ohne Namen zeigt dieses Werkzeug alle vorhandenen:\n"
                        f"  WERKZEUG: werkzeug_zeigen {{}}")

    w = alle[name]
    schema = w["input_schema"]
    felder = schema.get("properties", {})
    pflicht = set(schema.get("required", []))

    t = [f"{name}", "=" * len(name), "", w["description"], "", "Felder:"]
    if not felder:
        t.append("  (keine — dieses Werkzeug wird ohne Felder aufgerufen)")
    for f, b in felder.items():
        art = b.get("type", "?")
        marke = "  (noetig)" if f in pflicht else ""
        t.append(f"  {f} ({art}){marke}: {b.get('description', '')}")

    #  Ein Beispielaufruf sagt mehr als die Aufzaehlung — und er ist sofort benutzbar.
    beispiel = w.get("beispiel") or {}
    if not beispiel:
        beispiel = {f: ("COM3" if "port" in f else
                        "blink.py" if "datei" in f or "name" in f else
                        6 if b.get("type") == "number" else
                        True if b.get("type") == "boolean" else "…")
                    for f, b in felder.items() if f in pflicht}
    t += ["", "So rufst du es auf:",
          f"  WERKZEUG: {name} {json.dumps(beispiel, ensure_ascii=False)}"]
    return "\n".join(t)


if __name__ == "__main__":
    raise SystemExit(werkzeug(
        "werkzeug_zeigen",
        "Zeigt, welche Felder ein Werkzeug erwartet, mit Beispielaufruf. Im Anweisungstext "
        "stehen nur drei Werkzeuge vollstaendig; von allen anderen siehst du zunaechst nur, "
        "wofuer sie da sind. Brauchst du die Felder, hol sie dir hiermit. Ohne Namen zeigt "
        "es alle vorhandenen Werkzeuge.",
        {"name": {"type": "string", "description": "Name des Werkzeugs, zum Beispiel esp32_laden"}},
        [], {"name": "esp32_laden"}, tun))
