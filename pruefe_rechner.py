#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zeigt, was dieses Paket auf diesem Rechner tun wuerde — bevor der Kurs beginnt.

Aufruf:  python pruefe_rechner.py

**Zu entscheiden ist hier nichts.** Welches Modell benutzt wird, waehlt das Paket beim
Start selbst, nach dem freien Arbeitsspeicher des Rechners, auf dem es gerade laeuft —
denn der Stick wandert von Rechner zu Rechner und weiss beim Schnueren nicht, wo er landet.

Dieses Programm nimmt diese Wahl nur vorweg, damit man vor dem Kurs sieht, woran man ist:
Reicht der Speicher? Ist genug Platz? Welches Modell wird es werden?
"""
from __future__ import annotations
import os, platform, shutil, subprocess, sys, pathlib

HIER = pathlib.Path(__file__).resolve().parent

# Gemessen am Pruefstand: Dateigroesse, Spitzenspeicher des Modellservers, Ladezeit.
MODELLE = [
    # Name,    Datei GB, Speicher GB, braucht RAM GB, Bemerkung
    ("1.5b",   0.99, 2.2,  4,  "zeigt die Schleife; scheitert an mehrstufigen Auftraegen"),
    ("3b",     1.93, 3.5,  8,  "schreibt brauchbare Programme, verliert aber den Faden"),
    ("7b",     4.68, 6.7, 16,  "haelt die Reihenfolge ein — die Empfehlung"),
]


def _ram_gb() -> float | None:
    try:
        if os.name == "nt":
            import ctypes

            class S(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            s = S(); s.dwLength = ctypes.sizeof(S)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return s.ullTotalPhys / 1e9
        with open("/proc/meminfo") as f:
            for z in f:
                if z.startswith("MemTotal:"):
                    return int(z.split()[1]) * 1024 / 1e9
    except Exception:
        return None
    return None


def _grafik() -> str:
    try:
        if os.name == "nt":
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController).Name"],
                capture_output=True, text=True, timeout=40, encoding="utf-8", errors="replace")
            namen = [z.strip() for z in (r.stdout or "").splitlines() if z.strip()]
            return ", ".join(namen) if namen else "nicht ermittelt"
        r = subprocess.run(["sh", "-c", "lspci 2>/dev/null | grep -i 'vga\\|3d'"],
                           capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
        return (r.stdout or "").strip().split(":")[-1].strip() or "nicht ermittelt"
    except Exception:
        return "nicht ermittelt"


def _smart_app_control():
    """Sperrt dieser Rechner unsignierte Programme? (Windows 11, Smart App Control)

    Anlass, 04.10.2026, 0:35 Uhr: Der erste Start des Agenten auf echtem Windows endete mit
    einem Fehlerfenster — "llama-server-impl.dll ist entweder nicht fuer die Ausfuehrung
    unter Windows vorgesehen oder enthaelt einen Fehler, Fehlerstatus 0xc0e90002". Die
    Datei war Byte fuer Byte in Ordnung (Pruefsumme verglichen). 0xc0e90002 ist der
    Fehlerstatus der Code-Integritaetspruefung: Smart App Control laesst nur signierte
    Programme laufen. Python von python.org ist signiert, llama.cpp ist es nicht.

    Der Zustand steht in der Registrierung und laesst sich ohne Adminrechte lesen:
      0 = Aus, 1 = Ein (sperrt), 2 = Auswertung (sperrt noch nicht, kann aber umschalten).
    Rueckgabe: (Text fuer die Anzeige, sperrt: bool)
    """
    #  Gefragt wird die EINE Stelle, die auch der Agent fragt (agent/modell.py) — nicht eine
    #  zweite, aehnliche. Zwei Stellen mit derselben Aufgabe laufen auseinander, und dann
    #  sagt die Vorschau etwas anderes als der Lauf.
    sys.path.insert(0, str(HIER / "agent"))
    try:
        import modell
        return modell.signaturpflicht()
    except Exception as e:
        return f"nicht ermittelbar ({type(e).__name__}: {e})", False


def _wahl():
    """Fragt dieselbe Stelle, die spaeter auch der Agent fragt — nicht eine zweite,
    aehnliche. Zwei Stellen mit derselben Aufgabe laufen frueher oder spaeter auseinander,
    und dann sagt die Vorschau etwas anderes als der Lauf."""
    import sys as _s
    _s.path.insert(0, str(HIER / "agent"))
    try:
        import modell
        return modell.waehlen(laut=False), modell.freier_speicher_gb()
    except Exception as e:
        return (None, f"nicht ermittelbar: {type(e).__name__}: {e}"), None


def main():
    sac_text, sac_sperrt = _smart_app_control()
    if "--kurz" in sys.argv:
        # Zwei Zeilen fuer den Start: was wuerde jetzt gewaehlt, und darf es ueberhaupt laufen?
        (gewaehlt, grund), frei = _wahl()
        if gewaehlt:
            print(f"    Modell:  {gewaehlt.name}  (frei: {frei:.1f} GB)")
        else:
            print(f"    Modell:  {grund.splitlines()[0]}")
        print(f"    Smart App Control:  {sac_text}")
        #  Dieselben zwei Zeilen auch ins Laufprotokoll: Die Konsole ist weg, sobald das
        #  Fenster zu ist — die Datei bleibt, und sie ist das, was aus der Ferne gelesen wird.
        prot = HIER / "letzter_lauf.txt"
        if prot.is_file():
            try:
                import datetime
                with prot.open("a", encoding="utf-8") as f:
                    f.write(f"[{datetime.datetime.now():%H:%M:%S}] Modell: "
                            f"{gewaehlt.name if gewaehlt else grund.splitlines()[0]}\n"
                            f"[{datetime.datetime.now():%H:%M:%S}] Smart App Control: {sac_text}\n")
            except OSError:
                pass
        #  Seit 04.10.2026 liegt im Paket ein SIGNIERTER llama-server (aus dem Ollama-Archiv,
        #  paket\llama_signiert). Die Sperre trifft dann nur noch den unsignierten Rueckfall;
        #  gewarnt wird, wie in modell.starten, nach der Datei und nicht nach dem Ruf.
        server_signiert = False
        if sac_sperrt:
            try:
                import modell
                exe = modell.eine("llama_signiert/llama-server.exe")
                server_signiert = bool(exe) and modell.signiert(exe)
            except Exception:
                server_signiert = False
        if sac_sperrt and server_signiert:
            print()
            print("    Smart App Control ist EIN; der mitgelieferte llama-server traegt eine Signatur")
            print("    (Ollama Inc. / DigiCert) und darf laufen. Ob Windows ihn wirklich startet, zeigt")
            print("    der erste Auftrag -- das Protokoll in ablage\\protokoll.txt haelt es fest.")
        if sac_sperrt and not server_signiert:
            print()
            print("    ACHTUNG: Dieser Rechner laesst nur signierte Programme laufen. Das Sprachmodell")
            print("    (llama.cpp) ist nicht signiert und wird nicht starten - Windows meldet dann")
            print("    'Ungueltiges Bild, Fehlerstatus 0xc0e90002'. Alles ohne Modell laeuft trotzdem:")
            print("    Werkzeuge, Pruefschritt, virtuelle LED, Nachweis, und der Weg mit Drehbuch.")
            print("    Smart App Control steht in: Windows-Sicherheit > App- & Browsersteuerung.")
            print("    Es laesst sich dort ausschalten - aber nur einmal; wieder ein geht nur mit")
            print("    einer Neuinstallation von Windows. Diese Entscheidung trifft der Besitzer.")
        return 0

    ram = _ram_gb()
    kerne = os.cpu_count() or 0
    platz = shutil.disk_usage(HIER).free / 1e9
    grafik = _grafik()

    print(f"\nDieser Rechner")
    print(f"  Betriebssystem   {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"  Arbeitsspeicher  {f'{ram:.1f} GB' if ram else 'nicht ermittelt'}")
    print(f"  Prozessorkerne   {kerne}")
    print(f"  Freier Platz     {platz:.1f} GB in {HIER}")
    print(f"  Grafik           {grafik}")
    print(f"  Python           {sys.version.split()[0]} ({sys.executable})")
    print(f"  Smart App Control  {sac_text}")
    if sac_sperrt:
        print(f"                   -> das Sprachmodell (llama.cpp, unsigniert) wird hier NICHT starten;")
        print(f"                      alles ohne Modell laeuft. Siehe Hinweis am Ende.")

    (gewaehlt, grund), frei = _wahl()
    print(f"\nWas beim Start passieren wird")
    if frei is not None:
        print(f"  Frei im Augenblick  {frei:.1f} GB von {ram:.1f} GB" if ram
              else f"  Frei im Augenblick  {frei:.1f} GB")
    if gewaehlt:
        print(f"  Gewaehlt wird       {gewaehlt.name}")
        print(f"  Das entscheidet das Paket beim Start selbst — hier steht es nur zur Vorschau.")
    else:
        print(f"  {grund}")

    print(f"\nDie Modelle im Einzelnen")
    print(f"  {'Modell':8s} {'Datei':>8s} {'Speicher':>9s} {'braucht':>8s}   Urteil")
    empfehlung = None
    for name, datei, speicher, braucht, bemerkung in MODELLE:
        if ram is None:
            urteil = "nicht beurteilbar"
        elif ram >= braucht and platz >= datei + 0.3:
            urteil = "laeuft"
            empfehlung = name
        elif platz < datei + 0.3:
            urteil = f"zu wenig Platz (braucht {datei+0.3:.1f} GB)"
        else:
            urteil = f"zu wenig Speicher (braucht {braucht} GB)"
        print(f"  {name:8s} {datei:6.2f} GB {speicher:7.1f} GB {braucht:6d} GB   {urteil}")
        print(f"  {'':8s} {'':8s} {'':9s} {'':8s}   {bemerkung}")

    print()
    if empfehlung:
        print(f"  Fuer den Stick: python hole_paket.py        (holt 3b und 7b, 6,6 GB)")
        print(f"  Nur fuer diesen Rechner: --modell {empfehlung}")
    elif ram:
        print(f"  Mit {ram:.1f} GB Arbeitsspeicher und {platz:.1f} GB freiem Platz traegt dieser")
        print(f"  Rechner keines der Modelle. Ohne Modell laeuft weiterhin:")
        print(f"    START.bat  ->  [7] Ohne Modell durchlaufen")
        print(f"  Dabei wird dieselbe Kette mit denselben Werkzeugen gezeigt, nur die")
        print(f"  Entscheidungen trifft ein festes Drehbuch.")

    print(f"\nWas ohne Modell in jedem Fall laeuft")
    print(f"  Werkzeuge, Pruefschritt, virtuelle LED, Aufraeumen und der Nachweis brauchen")
    print(f"  kein Sprachmodell — nur Windows und 200 MB Platz.")

    if kerne and kerne < 4:
        print(f"\n  Hinweis: {kerne} Kern(e). Das Modell rechnet dann sehr langsam;")
        print(f"  rechne mit einer Minute je Schritt statt zehn Sekunden.")
    if "nvidia" not in grafik.lower() and "amd" not in grafik.lower() and "radeon" not in grafik.lower():
        print(f"\n  Hinweis: keine erkannte Grafikkarte fuer Vulkan. llama.cpp rechnet dann")
        print(f"  auf dem Hauptprozessor weiter — langsamer, aber es laeuft.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
