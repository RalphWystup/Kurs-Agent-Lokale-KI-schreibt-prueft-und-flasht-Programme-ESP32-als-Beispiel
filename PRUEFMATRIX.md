# Prüfmatrix des Kurs-Agenten

Nach Grundsatz 37 vom 8. Oktober 2026: „immer alles testen, und zwar vollständig". Jedes Feld ist
ein eigener Prüffall. Eingetragen wird, was gemessen wurde, nicht was erwartet war. Leere Felder
bleiben leer und gelten als **nicht geprüft** — nicht als bestanden.

## Die Achsen

| Achse | Werte |
|:--|:--|
| **Was** | die neun festen Aufträge |
| **Womit** | Coder-3B, Coder-7B, ohne Modell (Drehbuch) |
| **Wo** | STEINBEIS_1 (mit ESP32 an COM3), ML202101 (ohne Hardware) |
| **Wie oft** | drei Läufe je Feld; eine Fehlrunde macht das Feld offen |

Neun mal drei mal zwei sind **54 Felder**. Felder, die Hardware brauchen, sind auf ML202101 nicht
prüfbar; das steht dort als Grund, nicht als Lücke.

## Stand

Legende: ✓ bestanden (alle Läufe) · ✗ gefallen · ~ teils · leer = nicht geprüft

| # | Auftrag | 3B · zu Hause | 7B · zu Hause | ohne Modell · zu Hause | 3B · Laptop | 7B · Laptop | ohne Modell · Laptop |
|--:|:--|:--|:--|:--|:--|:--|:--|
| 1 | Hallo, bist du bereit? | | | | | | |
| 2 | LED blinken, 1 Hz | ✓ 3 Läufe, 1,00 Hz, 13 Wechsel | ✓ 1,00 Hz, 13 Wechsel, Abnahme | ✓ 1,00 Hz (07.10.) | | | |
| 3 | auf 2 Hz ändern | | ✓ 1,99 Hz, 25 Wechsel, Abnahme | | | | |
| 4 | 1 s an, 1 s aus | | ✓ 0,50 Hz, 7 Wechsel, Abnahme | | | | |
| 5 | auf ESP32 laden und nachlesen | | ~ übertragen (139 B nach COM3, Verzeichnis gelesen), **Abnahme fiel durch: Erwartung des Vorauftrags galt weiter** | | — kein Gerät | — kein Gerät | — kein Gerät |
| 6 | sinusförmig atmen, 1 Hz | ~ Form sinusförmig, Takt 0,93 statt 1,0 Hz | ✓ Form sinusförmig (Abw. Sinus 0,00), 0,93 Hz, Abnahme | | | | |
| 7 | zwei LEDs, zwei Takte | ✗ beide Pins 1,00 Hz | ✓ Pin 2 mit 2 Hz, Pin 4 mit 1 Hz, Abnahme | | | | |
| 8 | Taschenrechner mit Fenster | | ✗ Fenster läuft und bleibt offen, aber `=` stürzt ab: NameError 'math_operation' | | | ✗ zweimal: Lauf 1 nur Addition, Lauf 2 überschrieben | |
| 9 | was ist angeschlossen? | ~ COM3 gefunden, danach abgeschweift | | | — kein Gerät | — kein Gerät | — kein Gerät |

Geprüft: 14 von 54 Feldern (Stand 08.10.2026 nachmittags). Davon 7 bestanden, 4 gefallen, 3 teils. Der Rest ist offen und wird nicht als bestanden ausgegeben.

## Was in jedes Feld gehört

Nicht „läuft", sondern die gemessene Zeile aus dem Werkzeug: Takt in Hz, Zahl der
Zustandswechsel, Prüfsumme vom Gerät, Abnahmezeile, oder der Fehlertext. Dazu die Dauer und, bei
einem Fehlschlag, die Stelle im Protokoll.

## Wer was tut

* **Auf STEINBEIS_1** kann ich die Aufträge selbst geben (über die Brücke an 127.0.0.1:8777) und
  messe mit. Dort hängt auch der ESP32, also sind die Felder 5 und 9 nur dort prüfbar.
* **Auf ML202101** kann ich nur Dateien holen. Die Aufträge gibt der Auftraggeber in der
  Oberfläche; ich hole danach Protokoll und erzeugtes Programm und trage das Feld ein.

## Befunde, die aus der Matrix entstanden sind

| Datum | Feld | Befund |
|:--|:--|:--|
| 08.10.2026 | 8, alle | **Vier Taschenrechner geprüft, vier mangelhaft.** 05.10. zu Hause: keine Taste rechnet, die Schleife hängt an jede Taste denselben Befehl, die vier fertigen Rechenfunktionen darüber werden nie aufgerufen. 08.10. Laptop, Lauf 1: nur Addition, Minus/Mal/Geteilt stürzen ab. 08.10. zu Hause, 7B: Fenster läuft und bleibt offen, `=` stürzt mit NameError ab. Keiner wäre ohne `pruefe_rechner_programm.py` aufgefallen, denn alle sehen im Fenster vollständig aus. |
| 08.10.2026 | 8, Laptop | **Ursache des Rückfalls ins Blinkprogramm gefunden, zweimal belegt.** Nicht die Verdichtung, sondern der Rettungsgriff: `FOKUS Modell ohne Vorgeschichte nach dem Werkzeugaufruf gefragt` — und 34 s später schreibt das Modell ein Blinkprogramm in `rechner.py`. Ohne Verlauf kennt es den Auftrag nicht mehr und greift zum Beispiel aus seiner festen Anweisung. **Zu bauen:** Der Aufruf ohne Vorgeschichte muss den Auftrag behalten, und `schreib_datei` darf eine Datei nicht stillschweigend durch etwas ersetzen, das zu einem anderen Auftrag gehört. |
| 08.10.2026 | 5, 7B | **Die Erwartung wandert nicht mit.** Beim Laden von blink.py auf den ESP32 prüfte die Abnahme noch gegen die Erwartung des Vorauftrags (zwei Pins, 2 Hz). Das Übertragen selbst gelang. **Zu bauen:** Beim Wechsel des Programms muss die Erwartung mitwechseln oder als unbestimmt gelten. |
| 08.10.2026 | Werkzeug | **Der Agent starb mit der Brücke.** `kursagent start` startete ihn als Kindprozess; eine Selbstaktualisierung der Brücke beendete ihn mitten in der Prüfreihe, und die Läufe lieferten stumm nichts. Behoben in Brücke 3.13 (abgelöster Start), Gegenprobe bestanden. |
| 08.10.2026 | 8, 7B, Laptop | Das Modell schrieb einen brauchbaren Taschenrechner (52 Zeilen, Fenster lief), überschrieb ihn 45 s später mit einem 7-zeiligen Blinkprogramm, lieferte dreimal dieselbe Datei und wurde zurückgewiesen. Unmittelbar davor dreimal `VERLAUF innerhalb der Anweisung verdichtet`. Ursache zu messen. |
| 08.10.2026 | 8, 7B, Laptop | **Zu korrigieren (Auftraggeber: „das muss natürlich später korrigiert werden"):** tkinter war auf dem zweiten Rechner nicht eingerichtet, obwohl `tkinter-8.6.13-py3.12-win-amd64.zip` im Paket lag. `umgebung_anlegen` hatte dort den Schritt nie ausgeführt. Folge: Jedes Fensterprogramm stürzt beim `import tkinter` ab, das Fenster erscheint nie, und niemand sieht warum. **Zu bauen:** Einrichten muss beim ersten Lauf zuverlässig geschehen oder beim Fehlen klar melden, nicht stumm scheitern. |
| 08.10.2026 | 8, 7B, Laptop | **Zu korrigieren:** `paket_installieren` antwortet auf „tkinter" mit „steht nicht auf der Liste der erlaubten Pakete". Das ist richtig und führt doch in die Irre: tkinter kommt nicht über pip, sondern aus dem Paket über `umgebung_anlegen`. Das Modell rief daraufhin viermal dasselbe Werkzeug auf. **Zu bauen:** Die Meldung nennt den richtigen nächsten Schritt, statt nur abzuweisen. Dasselbe gilt für jede Abweisung, die einen gangbaren Weg verschweigt. |
| 08.10.2026 | 8, 7B, Laptop | Der Taschenrechner selbst war nur zur Hälfte richtig: Plus und Gleich rechnen, Minus, Mal und Geteilt schreiben ihr Zeichen nur in die Anzeige. Das fiel keiner Prüfung auf, weil `programm_testen` tkinter nicht zulässt und `programm_ausfuehren` nur startet. |
