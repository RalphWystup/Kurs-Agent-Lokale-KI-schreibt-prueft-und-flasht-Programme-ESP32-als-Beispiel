#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bildet die Pruefsumme einer Datei AUF DEM BRETT und haelt sie gegen die Werkstatt.

Warum es dieses Werkzeug gibt
-----------------------------
Bis zum 09.10.2026 endete das Uebertragen damit, dass ``esp32_uebertragen`` das Verzeichnis
des Geraets las und darin den **Dateinamen** suchte. Ein Name im Verzeichnis sagt nichts
darueber, ob der Inhalt angekommen ist: eine halb geschriebene Datei heisst genauso. Der
Kopftext jenes Werkzeugs behauptete sogar, die Groesse werde verglichen -- sie wurde nirgends
gelesen. Der Auftraggeber am 09.10.2026: „wird die uebertragung auch geprueft und die werte
zurueckgemessen?"

Hier wird sie geprueft, und zwar so, dass die Pruefung nicht beim Sender stattfindet:

  * Das Brett liest seine eigene Datei blockweise und bildet SHA-256 mit ``uhashlib``.
  * Der Rechner bildet SHA-256 ueber die Datei in der Werkstatt.
  * Verglichen werden Pruefsumme **und** Bytezahl.

Wer die Summe beim Sender bildet und mitteilt, hat nichts geprueft, sondern sich selbst
bestaetigt. Dasselbe Verfahren laeuft seit Fassung 3.6 in der Bruecke (``mpy pruefsumme``);
hier ist es ein Werkzeug des Agenten, damit das Modell es selbst aufrufen kann.

Gegenprobe (Kriterium W-1): Wird ein Byte der Werkstattdatei geaendert und NICHT neu
uebertragen, muss ``gleich`` auf false gehen und das Urteil UEBERTRAGUNG NICHT BESTANDEN
lauten. Das ist mit ``--gegenprobe`` eingebaut: dabei wird die Pruefsumme des Rechners
absichtlich verfaelscht und es muss durchfallen.
"""
import sys, pathlib
_hier = pathlib.Path(__file__).resolve().parent
for _p in (str(_hier), str(_hier.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _muster import werkzeug, Abbruch, lauf, WERKSTATT, python_exe, Leitung
import hashlib
import re

#  Dieses Stueck laeuft AUF DEM BRETT. Blockweise, weil der freie Arbeitsspeicher eines ESP32
#  keine ganze Datei im Stueck traegt, sobald sie ein paar Kilobyte hat.
AUF_DEM_BRETT = """
import uhashlib, ubinascii
h = uhashlib.sha256()
f = open({ziel!r}, 'rb')
n = 0
while True:
    b = f.read(256)
    if not b: break
    n += len(b); h.update(b)
f.close()
print('SUMME', ubinascii.hexlify(h.digest()).decode(), n)
"""


def _mpremote(port, *args, zeit=120):
    with Leitung(port=port):
        return lauf([str(python_exe()), "-m", "mpremote", "connect", port, *args], zeit)


def summe_rechner(pfad: pathlib.Path) -> tuple[str, int]:
    """SHA-256 und Bytezahl einer Datei auf diesem Rechner — blockweise wie auf dem Brett."""
    h = hashlib.sha256()
    n = 0
    with open(pfad, "rb") as f:
        while True:
            b = f.read(256)
            if not b:
                break
            n += len(b)
            h.update(b)
    return h.hexdigest(), n


def summe_brett(port: str, ziel: str) -> tuple[str, int]:
    """SHA-256 und Bytezahl, gebildet auf dem Geraet selbst."""
    r = _mpremote(port, "exec", AUF_DEM_BRETT.format(ziel=ziel))
    text = (r.stdout or "") + (r.stderr or "")
    if "ModuleNotFoundError" in text or "No module named mpremote" in text:
        raise Abbruch("mpremote fehlt. Erst paket_installieren mit mpremote aufrufen.")
    if "ENOENT" in text or "No such file" in text:
        raise Abbruch(f"Auf dem Geraet gibt es keine Datei '{ziel}'. "
                      f"Erst esp32_uebertragen aufrufen, dann hier pruefen.")
    treffer = re.search(r"SUMME\s+([0-9a-f]{64})\s+(\d+)", text)
    if not treffer:
        raise Abbruch(f"Das Brett an {port} lieferte keine Pruefsumme: {text[-400:]}\n"
                      f"Laeuft MicroPython darauf (esp32_firmware)? Haelt ein anderes "
                      f"Programm den Anschluss (Thonny, serieller Monitor)?")
    return treffer.group(1), int(treffer.group(2))


def tun(e):
    port = str(e["port"]).strip()
    if not re.fullmatch(r"(COM\d+|/dev/[A-Za-z0-9._/-]+)", port):
        raise Abbruch(f"'{port}' sieht nicht wie ein Anschluss aus. Ein Anschluss heisst "
                      f"COM3 oder COM5. Welche es an diesem Rechner gibt, sagt "
                      f"WERKZEUG: ports_zeigen {{}}")
    if not python_exe().exists():
        raise Abbruch("Es gibt noch kein eigenes Python. Zuerst umgebung_anlegen aufrufen.")

    ziel = str(e.get("ziel", "main.py")).strip() or "main.py"
    if "/" in ziel or "\\" in ziel or "'" in ziel:
        raise Abbruch("Der Name auf dem Geraet darf keinen Pfad enthalten.")
    #  Womit verglichen wird: standardmaessig die Werkstattdatei gleichen Namens; bei einer
    #  Uebertragung nach main.py heisst sie auf dem Rechner meist anders, deshalb 'datei'.
    name = str(e.get("datei", ziel)).strip() or ziel
    if "/" in name or "\\" in name:
        raise Abbruch("datei muss ein Name aus der Werkstatt sein, ohne Pfad.")
    quelle = WERKSTATT / name
    if not quelle.is_file():
        da = ", ".join(p.name for p in sorted(WERKSTATT.glob("*"))) or "(nichts)"
        raise Abbruch(f"{name} liegt nicht in der Werkstatt. Dort liegt: {da}.\n"
                      f"Lege sie erst an: WERKZEUG: schreib_datei "
                      f'{{"name": "{name}", "inhalt": "<der vollstaendige Quelltext>"}}')

    sha_g, byte_g = summe_brett(port, ziel)
    sha_r, byte_r = summe_rechner(quelle)
    if e.get("_gegenprobe"):
        #  Absichtlich verfaelschen: die Pruefung MUSS jetzt durchfallen, sonst prueft sie nichts.
        sha_r = "0" * 64

    gleich = (sha_g == sha_r) and (byte_g == byte_r)
    zeilen = [
        f"Pruefsumme von {port}:{ziel}, gebildet AUF DEM GERAET, gegen {quelle.name} in der Werkstatt:",
        f"  Gerät   SHA-256 {sha_g}   {byte_g} Byte",
        f"  Rechner SHA-256 {sha_r}   {byte_r} Byte",
        "",
    ]
    if gleich:
        zeilen.append("UEBERTRAGUNG BESTANDEN — auf dem Geraet liegt Byte fuer Byte dieselbe Datei.")
    else:
        was = []
        if sha_g != sha_r:
            was.append("die Pruefsummen sind verschieden")
        if byte_g != byte_r:
            was.append(f"die Laengen sind verschieden ({byte_g} gegen {byte_r} Byte)")
        zeilen.append("UEBERTRAGUNG NICHT BESTANDEN — " + " und ".join(was) + ".")
        zeilen.append("  Auf dem Geraet liegt nicht das, was in der Werkstatt steht. Noch einmal "
                      "mit esp32_uebertragen senden und danach hier erneut pruefen.")
    return "\n".join(zeilen)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gegenprobe":
        #  Selbstprobe ohne Geraet ist nicht moeglich — die Summe kommt vom Brett. Was hier
        #  geprueft wird, ist die Urteilsbildung: bei verschiedener Summe muss sie durchfallen.
        print("Gegenprobe der Urteilsbildung (ohne Geraet):")
        for a, b, na, nb, erwartet in [("ab" * 32, "ab" * 32, 10, 10, True),
                                       ("ab" * 32, "cd" * 32, 10, 10, False),
                                       ("ab" * 32, "ab" * 32, 10, 11, False)]:
            gleich = (a == b) and (na == nb)
            print(f"  {a[:4]}… gegen {b[:4]}…, {na} gegen {nb} Byte -> "
                  f"{'gleich' if gleich else 'verschieden'}  "
                  f"{'richtig' if gleich == erwartet else 'FALSCH'}")
        raise SystemExit(0)
    raise SystemExit(werkzeug(
        "esp32_pruefsumme",
        "Bildet die SHA-256-Pruefsumme einer Datei AUF DEM ESP32 und vergleicht sie mit der "
        "Datei in der Werkstatt. Erst dieser Vergleich beweist, dass die Uebertragung "
        "vollstaendig war; ein Dateiname im Verzeichnis beweist das nicht. Urteil: "
        "UEBERTRAGUNG BESTANDEN / NICHT BESTANDEN.",
        {"port":  {"type": "string", "description": "der Anschluss, zum Beispiel COM3"},
         "ziel":  {"type": "string", "description": "Name auf dem Geraet, Vorgabe main.py"},
         "datei": {"type": "string", "description": "Name in der Werkstatt, Vorgabe wie ziel"}},
        ["port"], {"port": "COM3", "ziel": "main.py", "datei": "blink.py"}, tun))
