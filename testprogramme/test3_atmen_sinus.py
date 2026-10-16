# Testprogramm 3: LED an GPIO 2 (D2) atmet sinusfoermig, ein Atemzug je 2 Sekunden (0,5 Hz).
# PWM: duty(0) = aus, duty(1023) = voll hell. Die Helligkeit folgt einer angehobenen Kosinuskurve.
import machine
import time
import math

led = machine.PWM(machine.Pin(2), freq=1000)
PERIODE = 2.0          # Sekunden je Atemzug
SCHRITTE = 100         # Stuetzstellen je Atemzug

while True:
    for i in range(SCHRITTE):
        helligkeit = (1 - math.cos(2 * math.pi * i / SCHRITTE)) / 2   # 0 .. 1 .. 0, weich
        led.duty(int(1023 * helligkeit))
        time.sleep(PERIODE / SCHRITTE)
