# Testprogramm 1: LED an GPIO 2 (Bord-LED, Beschriftung D2) blinkt mit 1 Hz.
# Zum Pruefen der Kette von Hand: aendern, uebersetzen, simulieren, laden.
import machine
import time

led = machine.Pin(2, machine.Pin.OUT)

while True:
    led.value(1)
    time.sleep(0.5)
    led.value(0)
    time.sleep(0.5)
