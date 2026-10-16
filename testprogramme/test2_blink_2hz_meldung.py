# Testprogramm 2: LED an GPIO 2 blinkt mit 2 Hz und meldet jeden Durchgang ueber die serielle Leitung.
# Die Meldung sieht man beim Laden (Mitschnitt) — so ist nachpruefbar, dass das Programm auf dem Brett laeuft.
import machine
import time

led = machine.Pin(2, machine.Pin.OUT)
durchgang = 0

while True:
    durchgang += 1
    led.value(1)
    time.sleep(0.25)
    led.value(0)
    time.sleep(0.25)
    print("Durchgang", durchgang)
