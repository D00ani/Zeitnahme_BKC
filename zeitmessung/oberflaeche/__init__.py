# -*- coding: utf-8 -*-
"""Die Fenster des Programms."""


def starte(einstellungsdatei=None):
    """Startet das Programm."""
    from ..einstellungen import STANDARD_DATEI, Einstellungen
    from .haupt import Hauptfenster

    einst = Einstellungen.laden(einstellungsdatei or STANDARD_DATEI)
    fenster = Hauptfenster(einst)
    fenster.mainloop()
