# -*- coding: utf-8 -*-
"""
Zeitmessung mit eingebautem Live-Timing.

Nachbau des Vereinsprogramms "Zeitmessung_Kart" in Python, mit denselben
Funktionen, denselben Rechenregeln und demselben Ausdruck - aber mit
sauberer getrennten Bausteinen, damit sich alles automatisch prüfen lässt.

Aufbau:

``zeit``          Zeitarithmetik in Hundertsteln
``einstellungen`` alle Einstellungen und Pfade in einer JSON-Datei
``datenbank``     Ergebnisse und Verlauf in SQLite
``ablauf``        Training / Einführung / Wertung als reine Zustandslogik
``wertung``       Strafzeiten, Summen, Platzierung
``ausdruck``      Ergebniskarte (Layout und Windows-Druck)
``lichtschranke`` serielle Schnittstelle über die Windows-API
``livetiming``    livedata.json, Archiv und Veröffentlichen (abschaltbar)
``oberflaeche``   die Fenster
"""
__version__ = "1.0"
