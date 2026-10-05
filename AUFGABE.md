# Kurs-Agent — die Aufgabe

Gesetzt vom Auftraggeber am 04.10.2026, 12:40 Uhr, wörtlich (Tippfehler bereinigt). Dieses
Blatt ist die Quelle; `ANFORDERUNGEN.md` und `PRUEFPROTOKOLL.md` tragen denselben Text als
ersten Kasten, und `pruefe_alles.py` (Prüfung Z0) schlägt an, sobald er irgendwo fehlt oder
abweicht. Er muss nach keinem Absturz neu geschrieben werden.

> „Ziel der Kurs-KI ist es, auf einem Ordner ein SLM oder kleines LLM speziell für die
> Python-Programmierung zusammen mit einem dafür passenden Agenten und den Python-Werkzeugen auf
> einen einzigen Ordner zu installieren. Das System soll Python-Programme auf Anforderung
> schreiben und selbst testen können, um Syntaxfehler über den Agenten selbst zu korrigieren,
> dann entweder simulieren oder direkt auf die Hardware laden. Das alles muss so geschehen, dass
> der Anwender nichts laden muss; es muss ohne Internetzugang funktionieren, auch alle Treiber
> müssen vorhanden sein. Es wird nichts installiert außer eventuell nötigen Treibern, und alles
> läuft nur mit den Werkzeugen auf dem besagten Ordner; es wird kein schon vorhandenes Python
> verwendet, keine Libs, die irgendwo gefunden wurden, nichts sonst — alles muss mitgeliefert
> werden. Ich will nicht sehen: ‚es muss noch nachgeladen werden‘."

## Was daraus unmittelbar folgt

| | Satz der Aufgabe | Folge für das Paket | gemessen durch |
|:--|:--|:--|:--|
| 1 | SLM/LLM **speziell für die Python-Programmierung** | ein Coder-Modell (Qwen2.5-Coder) ist gesetzt, nicht Option; Instruct bleibt nur, wenn Coder beim Werkzeugprotokoll messbar schlechter ist | Vergleich auf dem Prüfstand: Schritte bis FERTIG, Abnahmen, Formatfehler |
| 2 | dafür passender Agent, Python-Werkzeuge, **ein einziger Ordner** | alles unter einer Wurzel, kein Pfad außerhalb | `pruefe_unversehrtheit.py`, Nachweis vorher/nachher |
| 3 | schreibt auf Anforderung, **testet selbst**, korrigiert Syntaxfehler über den Agenten | `programm_testen` mit Erwartung, Berichtigungsschleife, FERTIG erst nach bestandener Abnahme | G2–G4 |
| 4 | dann **simulieren oder direkt auf die Hardware** | virtuelle LED und echter ESP32 (flashen, übertragen) | Säulen Agent und Hardware im Prüfprotokoll |
| 5 | Anwender lädt nichts, **kein Internet**, alle Treiber dabei | Vorrat statt Netz; CH340-Treiber im Paket; nichts installiert außer eventuell dem Treiber | A1–A3, E5 |
| 6 | **kein vorhandenes Python**, keine fremden Libs, alles mitgeliefert | nur `paket\python`, nur Räder aus `paket\`; das Selbstfüllen über ein fremdes Python ist ein **Vorbereitungsschritt des Dozenten mit Netz**, nie ein Schritt im Kurs | A4, C5, E5 |
| 7 | nie zu sehen: „es muss noch nachgeladen werden" | im Kursbetrieb (volles Paket) erscheint keine Nachlade-Meldung; fehlt etwas, sagt START.bat **was** fehlt und dass der Dozent das Paket füllt | F-Gruppe, Lauf auf `C:\Kurs_Agent` |

Maßstab bleibt der Satz vom 04.10.2026, 1:30 Uhr: alles muss echt auf dem Rechner des
Auftraggebers laufen — LLM, Agent, Werkzeuge, Hardware.
