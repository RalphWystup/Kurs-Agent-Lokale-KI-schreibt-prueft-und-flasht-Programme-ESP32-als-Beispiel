# Kurs-Agent

Dieses Paket vertieft am realen System, was die veröffentlichte Seite [„KI steuert lokale
Hardware über eine Brücke"](https://ralphwystup.github.io/KI-steuert-lokale-Hardware-ueber-eine-Bruecke/Bruecke_KI_und_Arbeitsplatz_1.0.html#aufgabe) exemplarisch zeigt.

Ein KI-Agent mit eigenem Sprachmodell schreibt ein Programm für einen ESP32, **prüft es
selbst**, überspielt es — und entfernt sich danach restlos. Alles läuft aus **einem Ordner**,
vom USB-Stick oder von der Festplatte.

Der Kursrechner braucht **Windows und sonst nichts**: kein Python, kein Netz, keine
Adminrechte.

---

## Anfangen

**Doppelklick auf `START.bat`.** Mehr muss im Kurs niemand wissen.

| vorher, einmal, mit Netz | im Kurs, ohne Netz |
|---|---|
| `START.bat` → es füllt sich selbst (rund 6,8 GB) | `START.bat` → **[1] Agent starten** |
| | am Ende **[3] Aufräumen** |

**Doppelklick genügt immer, auch beim ersten Mal.** Ist das Paket noch leer, sagt
`START.bat` das, sucht **für diesen einen Schritt** ein vorhandenes Python mit pip, fragt
nach und holt alles. Danach läuft es weiter, als wäre gerade gestartet worden — und benutzt
von da an ausschließlich das Python aus dem Paket.

Das ist die einzige Stelle im ganzen Vorgang, die ein fremdes Python braucht: im leeren
Paket liegt ja noch keines. Sie liegt auf dem Vorbereitungsrechner, nie auf dem Kursrechner,
und selbst dort bleibt der Rechner unberührt — pip-Zwischenspeicher und Benutzerpakete
zeigen in den Kursordner. Wer das nicht will, kopiert einfach den **gefüllten** Ordner von
einem anderen Rechner: füllen einmal, weitergeben beliebig oft.

---

## Die ganze Anleitung

**`Kurs_Agent_3.1.html`** — Doppelklick, öffnet im Browser, braucht kein Netz.
Sieben Reiter mit allem: wofür das Ganze, was im Paket ist, Schritt für Schritt, zwei
Beispiele mit und ohne Hardware, Treiber, was der Rechner davon merkt, und was zu tun ist,
wenn es klemmt. Mit Bildern der laufenden Bedienung.

**`ANFORDERUNGEN.md`** — 55 Punkte in neun Gruppen, jeder so gefasst, dass er scheitern kann.
**`PRUEFPROTOKOLL.md`** — was davon geprüft ist, womit, mit welchem Ergebnis; dazu die zwölf
Fehler, die das Prüfen gefunden hat, und was offen bleibt.
`python pruefe_alles.py` arbeitet die maschinell prüfbaren Punkte ab.

---

## Was der Agent tut

```
1  schreib_datei      das Programm entsteht
2  programm_testen    läuft ohne Hardware, gemessen gegen eine vorher genannte Erwartung
3  bei NICHT BESTANDEN zurück zu 1
4  ports_zeigen       welcher Anschluss
5  esp32_firmware     MicroPython aufs Gerät
6  esp32_uebertragen  dieselbe Datei, die geprüft wurde
```

Schritt 2 ist der Inhalt des Kurses. Ein Sprachmodell schreibt in Sekunden ein Programm,
das plausibel aussieht; ob es tut, was verlangt war, steht damit nicht fest. Diese Lücke
schließt kein besseres Modell, sondern eine Prüfung, die **durchfallen kann**:

```
"erwartet": {"pins": [2], "takt_hz": 1.0}
```

Ohne diese Zeile ist der Lauf eine Vorführung. Mit ihr eine Abnahme.

---

## Aufbau

```
START.bat                      Doppelklick — mehr braucht der Kurs nicht
Kurs_Agent_Inbetriebnahme_*.html   die Anleitung
ANFORDERUNGEN.md               was gelten soll, und woran man es misst
pruefe_alles.py                prüft die maschinell prüfbaren Anforderungen
pruefe_rechner.py              was dieser Rechner tragen kann
hole_paket.py                  füllt paket\ einmal vor dem Kurs
baue_stick.py                  stellt den weitergabefertigen Ordner zusammen
sammle_bericht.py              schreibt alles zur Ferndiagnose in eine Datei
agent\
  agent.py                     die Schleife: Modell → Werkzeug → Ergebnis → Modell
  oberflaeche.py + .html       die Bedienung im Browser
  modell.py                    startet llama-server, wählt das Modell nach freiem Speicher
  waechter.py                  meldet Schreibversuche außerhalb der Ablage
  pfade.py                     die einzige Stelle, die Pfade und Umgebung kennt
  pruefe_schleife.py           Selbsttest der Agentenschleife
  werkzeuge\                   neun Programme, jedes einzeln prüfbar
paket\                         das Mitgelieferte — wird nur gelesen
ablage\                        was im Kurs entsteht — wird am Ende restlos gelöscht
```

Die Trennung zwischen `paket\` und `ablage\` ist das Sicherheitskonzept: geschrieben wird
ausschließlich in `ablage\`, das erzwingt der Werkzeugrahmen, und gelöscht wird genau dieser
eine Ordner — mit Nachzählung.

---

## Die neun Werkzeuge

| Werkzeug | was es tut |
|---|---|
| `umgebung_anlegen` | entpackt Python, schaltet `import site` frei, richtet pip ein |
| `paket_installieren` | installiert aus `paket\pakete\` — nur was auf der Liste steht |
| `schreib_datei` | legt eine Datei in der Werkstatt an; weist ungültiges Python ab |
| `programm_testen` | führt das Programm ohne Hardware aus und nimmt es gegen die Erwartung ab |
| `ports_zeigen` | zählt die seriellen Anschlüsse auf, erkennt CH340 / CP2102 / FTDI |
| `esp32_firmware` | sagt, was auf dem Brett ist, und spielt MicroPython auf |
| `esp32_uebertragen` | kopiert das geprüfte Programm als `main.py` und startet neu |
| `nachweis_autark` | nimmt den Zustand des Rechners auf und vergleicht ihn |
| `aufraeumen` | löscht die Ablage und zählt nach, dass nichts blieb |

Jedes ist ein eigenes Programm:

```
python agent\werkzeuge\ports_zeigen.py --beschreibung
python agent\werkzeuge\ports_zeigen.py "{}"
python agent\agent.py --probe          alle der Reihe nach, ohne Modell
```

---

## Wenn das Modell klemmt

`START.bat` → **[7] Ohne Modell durchlaufen**. Dieselben Werkzeuge, dieselbe Abnahme, nur
die Reihenfolge steht fest statt vom Modell entschieden zu werden.

---

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)
