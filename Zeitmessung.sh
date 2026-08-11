#!/bin/sh
# Startet die Zeitmessung unter Linux.
#
# Vorher einmalig nötig (Beispiel Debian/Ubuntu):
#   sudo apt install python3 python3-tk git cups-client
#   sudo usermod -aG dialout $USER      # Zugriff auf die Lichtschranke
# Danach einmal ab- und wieder anmelden.

cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 wurde nicht gefunden."
    echo "Installieren mit:  sudo apt install python3 python3-tk"
    exit 1
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "Die Fensterbibliothek tkinter fehlt."
    echo "Installieren mit:  sudo apt install python3-tk"
    exit 1
fi

exec python3 Zeitmessung.pyw "$@"
