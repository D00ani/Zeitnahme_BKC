# -*- coding: utf-8 -*-
"""
Startet die Zeitmessung.

Als .pyw gespeichert, damit beim Doppelklick kein schwarzes Konsolenfenster
mit aufgeht. Zum Suchen von Fehlern lässt sich dieselbe Datei mit
``python Zeitmessung.pyw`` starten, dann sind Meldungen sichtbar.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from zeitmessung.oberflaeche import starte
    datei = sys.argv[1] if len(sys.argv) > 1 else None
    starte(datei)


if __name__ == "__main__":
    try:
        main()
    except Exception:                                    # noqa: BLE001
        # Ohne Konsole würde ein Fehler beim Start sonst spurlos verpuffen.
        meldung = traceback.format_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror("Zeitmessung konnte nicht starten", meldung)
        except Exception:                                # noqa: BLE001
            sys.stderr.write(meldung)
        raise
