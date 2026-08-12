# -*- coding: utf-8 -*-
"""
Auswertung eines Starters: Pylonen, Fahrfehler, Strafzeit, Gesamtzeit -
und daraus die Platzierung.

Die Rechenregeln sind unverändert die des alten Programms:

    Strafzeit eines Laufs = Pylonen x Strafzeit-pro-Pylone
                          + Fehler  x Strafzeit-pro-Fehler
    Summe eines Laufs     = Fahrzeit + Strafzeit
    Gesamt                = Summe 1. Lauf + Summe 2. Lauf

Neu ist nur, dass durchgehend mit Hundertsteln gerechnet wird statt mit
zusammengesetzten Textbausteinen.
"""
from dataclasses import dataclass, field

from . import zeit


@dataclass
class Lauf:
    """Ein einzelner Wertungslauf."""
    fahrzeit: int = 0        # Hundertstel
    pylonen: int = 0
    fehler: int = 0
    gueltig: bool = True

    def strafzeit_sekunden(self, sek_pylone, sek_fehler):
        return zeit.strafzeit(self.pylonen, self.fehler, sek_pylone, sek_fehler)

    def summe(self, sek_pylone, sek_fehler):
        """Fahrzeit plus Strafzeit, in Hundertstel."""
        return self.fahrzeit + zeit.sekunden_in_hundertstel(
            self.strafzeit_sekunden(sek_pylone, sek_fehler))


@dataclass
class Starterergebnis:
    """Der komplette Zettel eines Fahrers."""
    startnummer: str = ""
    name: str = ""
    klasse: str = ""
    verein: str = ""
    sek_pylone: int = 2
    sek_fehler: int = 10
    laeufe: dict = field(default_factory=lambda: {1: Lauf(), 2: Lauf()})

    # -- Zugriff auf die Läufe ---------------------------------------------
    def lauf(self, nummer):
        return self.laeufe.setdefault(nummer, Lauf())

    def zeit_setzen(self, nummer, hundertstel):
        self.lauf(nummer).fahrzeit = int(hundertstel or 0)

    # -- Abgeleitete Werte --------------------------------------------------
    def strafzeit_sekunden(self, nummer):
        return self.lauf(nummer).strafzeit_sekunden(self.sek_pylone, self.sek_fehler)

    def summe(self, nummer):
        return self.lauf(nummer).summe(self.sek_pylone, self.sek_fehler)

    def strafzeit_gesamt_sekunden(self):
        return sum(self.strafzeit_sekunden(n) for n in sorted(self.laeufe))

    def fahrzeit_gesamt(self):
        return sum(self.lauf(n).fahrzeit for n in sorted(self.laeufe))

    def gesamt(self):
        return sum(self.summe(n) for n in sorted(self.laeufe))

    # -- Als Text, so wie es gespeichert und gedruckt wird -------------------
    def als_text(self, nummer):
        """Die Felder eines Laufs in der Form, in der sie in der Datenbank
        landen."""
        lauf = self.lauf(nummer)
        return {
            "fahrzeit": zeit.formatiere(lauf.fahrzeit),
            "pylonen": str(lauf.pylonen),
            "adw": str(lauf.fehler),
            "strafzeit": str(self.strafzeit_sekunden(nummer)),
            "gesamtzeit": zeit.formatiere(self.summe(nummer)),
        }

    def gesamt_als_text(self):
        return {
            "fahrzeit": zeit.formatiere(self.fahrzeit_gesamt()),
            "pylonen": str(sum(self.lauf(n).pylonen for n in self.laeufe)),
            "adw": str(sum(self.lauf(n).fehler for n in self.laeufe)),
            "strafzeit": str(self.strafzeit_gesamt_sekunden()),
            "gesamtzeit": zeit.formatiere(self.gesamt()),
        }


def nachrechnen(fahrzeit, pylonen, fehler, sek_pylone, sek_fehler):
    """Rechnet einen gespeicherten Datensatz neu durch.

    Wird gebraucht, wenn am Renntag eine Pylonenzahl berichtigt wird:
    aus Fahrzeit und der neuen Zahl entstehen Strafzeit und Gesamtzeit.
    Gibt (strafzeit_sekunden, gesamtzeit_text) zurück.
    """
    gefahren = zeit.parse(fahrzeit)
    strafe = zeit.strafzeit(pylonen, fehler, sek_pylone, sek_fehler)
    if gefahren is None:
        # Keine verwertbare Fahrzeit (z. B. Ausschluss) - dann bleibt der
        # Eintrag stehen, wie er ist.
        return strafe, str(fahrzeit or "")
    return strafe, zeit.formatiere(gefahren + zeit.sekunden_in_hundertstel(strafe))


# ----------------------------------------------------------------------
# Platzierung
# ----------------------------------------------------------------------

def _sortierschluessel(eintrag):
    """Schnellste zuerst; wer keine verwertbare Zeit hat, ganz nach hinten."""
    hundertstel = eintrag.get("gesamtzeit_hs")
    if hundertstel is None:
        hundertstel = zeit.parse(eintrag.get("gesamtzeit", ""))
    ohne_zeit = hundertstel is None
    nummer = eintrag.get("starternr", "")
    return (ohne_zeit, hundertstel or 0, int(nummer) if str(nummer).isdigit() else 0)


def rangliste(eintraege):
    """Sortiert Gesamtergebnisse und hängt den Platz an.

    Zeitgleiche Starter bekommen denselben Platz; der nächste Platz wird
    entsprechend übersprungen (1, 2, 2, 4). Das alte Programm hat stumpf
    hochgezählt und zwei gleich schnellen Fahrern verschiedene Plätze
    gegeben.
    """
    sortiert = sorted(eintraege, key=_sortierschluessel)
    ergebnis = []
    nichts = object()          # Merker, der mit keiner Zeit gleich sein kann
    letzte_zeit = nichts
    letzter_platz = 0
    for stelle, eintrag in enumerate(sortiert, start=1):
        hundertstel = eintrag.get("gesamtzeit_hs")
        if hundertstel is None:
            hundertstel = zeit.parse(eintrag.get("gesamtzeit", ""))
        # None == None ist wahr: auch Starter ohne verwertbare Zeit teilen
        # sich einen Platz. Sie unterscheidet ja nichts voneinander.
        if letzte_zeit is not nichts and hundertstel == letzte_zeit:
            platz = letzter_platz
        else:
            platz = stelle
            letzte_zeit = hundertstel
            letzter_platz = stelle
        ergebnis.append(dict(eintrag, platz=platz))
    return ergebnis


def platz_von(rangliste_eintraege, startnummer, klasse=None):
    """Sucht den Platz eines bestimmten Starters heraus (None, wenn nicht
    dabei)."""
    for eintrag in rangliste_eintraege:
        if str(eintrag.get("starternr", "")) != str(startnummer):
            continue
        if klasse is not None and eintrag.get("klasse", "") != klasse:
            continue
        return eintrag["platz"]
    return None


def platzierungstext(alle_gesamt, startnummer, name, verein, klasse):
    """Baut den Text, der nach dem Drucken im Platzierungsfenster steht -
    inhaltlich derselbe Aufbau wie früher."""
    in_klasse = [e for e in alle_gesamt if e.get("klasse", "") == klasse]
    rang_klasse = rangliste(in_klasse)
    rang_gesamt = rangliste(alle_gesamt)

    platz_klasse = platz_von(rang_klasse, startnummer, klasse)
    platz_gesamt = platz_von(rang_gesamt, startnummer)

    zeilen = [f"Platzierung für {name}, StartNr {startnummer}, {verein}", ""]

    if platz_klasse:
        zeilen.append(f"{name} ist derzeit auf Platz {platz_klasse} von "
                      f"{len(rang_klasse)} Startern in seiner Klasse {klasse}")
    else:
        zeilen.append(f"{name} ist in Klasse {klasse} noch nicht gewertet")
    zeilen.append("")

    zeilen.append(f"Ergebnisse Klasse {klasse}")
    for eintrag in rang_klasse:
        zeilen.append(f"  Platz {eintrag['platz']}: {eintrag.get('name', '')}, "
                      f"{eintrag.get('verein', '')}, {eintrag.get('gesamtzeit', '')}")
    zeilen.append("")

    if platz_gesamt:
        zeilen.append(f"{name} ist von allen Startern derzeit auf Platz "
                      f"{platz_gesamt} von {len(rang_gesamt)} Gesamt-Startern")
    zeilen.append("")

    zeilen.append("Gesamtplatzierung:")
    for eintrag in rang_gesamt:
        zeilen.append(f"   Platz {eintrag['platz']}: {eintrag.get('name', '')}, "
                      f"{eintrag.get('verein', '')}, {eintrag.get('gesamtzeit', '')}")
    return zeilen
