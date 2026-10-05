# Prüfstand

Die Gegenproben brauchen `ablage/python/python.exe` — unter Linux ein Verweis auf `python3`:

    mkdir -p ablage/python && ln -s /usr/bin/python3 ablage/python/python.exe

`messe_modell.py <wurzel>` braucht zusätzlich einen Linux-Build von llama.cpp unter `<wurzel>/paket/llama/llama-server` und ein Modell unter `<wurzel>/paket/modell/`.
