# -*- coding: utf-8 -*-
"""
Ablaufsteuerung der Messung - Training, Einführungsrunde, Wertungslauf.

Dieses Modul kennt **keine** Oberfläche. Es bekommt Auslöser herein
(Lichtschranke oder Taste F1) und gibt zurück, was daraufhin passiert ist.
Dadurch lässt sich der komplette Rennablauf testen, ohne ein Fenster zu
öffnen - im alten Programm steckte diese Logik zwischen Knopf-Ereignissen
und Formularfeldern und war nur von Hand prüfbar.

Die Uhr ist austauschbar (``uhr=``). Voreingestellt ist ``time.monotonic``:
eine Uhr, die nur vorwärts läuft und die eine Zeitumstellung oder eine
Korrektur der Systemzeit nicht beeinflusst. Das alte Programm hat mit
``Now`` gerechnet - stellte sich die Uhr mitten im Lauf, war die Zeit falsch.
"""
import time
from dataclasses import dataclass, field

from . import zeit

TRAINING = "training"
EINFUEHRUNG = "einfuehrung"
WERTUNG = "wertung"

MODI = (TRAINING, EINFUEHRUNG, WERTUNG)


@dataclass
class Ereignis:
    """Was durch einen Auslöser passiert ist."""
    art: str
    daten: dict = field(default_factory=dict)

    def __getitem__(self, name):
        return self.daten[name]


class Ablauf:
    """Der Zustand einer laufenden Zeitmessung."""

    def __init__(self, einstellungen, uhr=time.monotonic):
        self.einst = einstellungen
        self.uhr = uhr
        self.modus = TRAINING
        self.laeuft = False
        self.runden = 0                 # abgeschlossene Runden im aktuellen Lauf
        self.lauf_nummer = 0            # 0 = kein Wertungslauf, sonst 1 oder 2
        self.einfuehrung_zaehler = 0
        self.zeiten = {}                # Lauf-Nr -> Fahrzeit in Hundertstel
        self._lauf_start = None         # Beginn der laufenden Runde
        self._gesamt_start = None       # Beginn des Laufs bzw. des Trainings
        self._letzter_ausloeser = None  # für die Sperrzeit
        self._letzte_zeit = 0           # zuletzt angezeigte/gestoppte Zeit

    # ------------------------------------------------------------------
    # Abfragen
    # ------------------------------------------------------------------
    @property
    def max_runden(self):
        if self.modus == TRAINING:
            return int(self.einst.tr_max_runden)
        return int(self.einst.we_runden_pro_lauf)

    def aktuelle_zeit(self):
        """Zeit der laufenden Runde in Hundertstel. Steht die Messung, wird
        die zuletzt gestoppte Zeit zurückgegeben."""
        if not self.laeuft or self._lauf_start is None:
            return self._letzte_zeit
        return zeit.aus_sekunden(self.uhr() - self._lauf_start)

    def training_restzeit_minuten(self):
        """Verbleibende Trainingsminuten (kann 0 werden, nie negativ)."""
        if self._gesamt_start is None:
            return int(self.einst.tr_max_zeit)
        verbraucht = (self.uhr() - self._gesamt_start) / 60.0
        return max(0, int(self.einst.tr_max_zeit) - int(verbraucht))

    def training_zeit_abgelaufen(self):
        if self._gesamt_start is None:
            return False
        return (self.uhr() - self._gesamt_start) / 60.0 >= int(self.einst.tr_max_zeit)

    def knopfbeschriftung(self):
        """Text auf dem großen Knopf - dieselben Texte wie früher."""
        if not self.laeuft:
            if self.modus == TRAINING:
                return "Start Training (F1)"
            if self.modus == EINFUEHRUNG:
                return "Start Einführung (F1)"
            return "Start Wertung (F1)"
        if self.runden + 1 >= self.max_runden:
            return "Stop (F1)"
        return "Rundenzeit (F1)" if self.modus == TRAINING else "Zwischenzeit (F1)"

    # ------------------------------------------------------------------
    # Bedienung
    # ------------------------------------------------------------------
    def modus_setzen(self, modus):
        """Umschalten ist nur möglich, solange nicht gemessen wird - sonst
        ließe sich mitten im Wertungslauf auf Training stellen."""
        if self.laeuft or modus not in MODI:
            return []
        self.modus = modus
        self.runden = 0
        self._letzte_zeit = 0
        ereignisse = [Ereignis("modus", {"modus": modus})]
        if modus == WERTUNG:
            # Wer die Wertung direkt anwählt, hat die Einführungsrunde hinter
            # sich - genau wie im alten Programm.
            self.einfuehrung_zaehler = int(self.einst.we_einfuehrungsrunden)
            self.lauf_nummer = 0
            self.zeiten = {}
            if self.einst.starter_eingabe and not self.einst.starter_bei_einfuehrung:
                ereignisse.append(Ereignis("starter_erfassen", {"anlass": "vor_wertung"}))
        elif modus == EINFUEHRUNG:
            self.einfuehrung_zaehler = 0
            self.lauf_nummer = 0
            self.zeiten = {}
            if self.einst.starter_eingabe and self.einst.starter_bei_einfuehrung:
                ereignisse.append(Ereignis("starter_erfassen", {"anlass": "vor_einfuehrung"}))
        return ereignisse

    def abbrechen(self):
        """Bricht den laufenden Lauf ab, ohne bereits gefahrene Zeiten zu
        löschen - der ESC-Knopf von früher."""
        self.laeuft = False
        self.runden = 0
        self._lauf_start = None
        self._gesamt_start = None
        text = {TRAINING: "Abbruch Training",
                EINFUEHRUNG: "Abbruch Einführung"}.get(
                    self.modus, f"Abbruch {max(1, self.lauf_nummer)}. Wertungslauf")
        if self.modus == WERTUNG:
            # Der abgebrochene Lauf zählt nicht - der nächste Auslöser
            # startet ihn erneut. Dafür muss auch der Einführungszähler
            # wieder auf "Einführung erledigt" stehen, sonst würde der
            # nächste Druck auf F1 als Einführungsrunde gedeutet.
            self.lauf_nummer = max(0, self.lauf_nummer - 1)
            self.einfuehrung_zaehler = int(self.einst.we_einfuehrungsrunden)
        return [Ereignis("abbruch", {"text": text})]

    def ausloesen(self):
        """Ein Signal der Lichtschranke oder ein Druck auf F1."""
        jetzt = self.uhr()
        if self.laeuft and self._gesperrt(jetzt):
            return [Ereignis("gesperrt", {})]
        self._letzter_ausloeser = jetzt
        if self.laeuft:
            return self._runde_beenden(jetzt)
        return self._starten(jetzt)

    # ------------------------------------------------------------------
    # Innenleben
    # ------------------------------------------------------------------
    def _gesperrt(self, jetzt):
        """Innerhalb der Sperrzeit wird ein zweites Signal verworfen -
        gegen Doppelauslösung, wenn ein Kart die Schranke langsam passiert."""
        sperre = int(self.einst.sperrzeit_sekunden)
        if sperre <= 0 or self._letzter_ausloeser is None:
            return False
        return (jetzt - self._letzter_ausloeser) < sperre

    def _starten(self, jetzt):
        if self.modus == TRAINING:
            self.laeuft = True
            self.runden = 0
            self._lauf_start = jetzt
            self._gesamt_start = jetzt
            return [Ereignis("protokoll", {"text": "Start Training"}),
                    Ereignis("start", {"modus": TRAINING})]

        # Einführung und Wertung teilen sich einen Zähler
        self.einfuehrung_zaehler += 1
        noetig = int(self.einst.we_einfuehrungsrunden)

        if self.einfuehrung_zaehler < noetig and self.lauf_nummer == 0:
            return [Ereignis("protokoll",
                             {"text": f"Start Einführung {self.einfuehrung_zaehler}"})]

        if self.einfuehrung_zaehler == noetig and self.lauf_nummer == 0:
            # Letzte Einführungsrunde ist gefahren: ab jetzt zählt es.
            self.modus = WERTUNG
            return [Ereignis("protokoll", {"text": "Ende Einführung"}),
                    Ereignis("wechsel_wertung", {})]

        # Wertungslauf beginnt
        self.modus = WERTUNG
        self.lauf_nummer += 1
        self.laeuft = True
        self.runden = 0
        self.einfuehrung_zaehler = 0
        self._lauf_start = jetzt
        self._gesamt_start = jetzt
        return [Ereignis("protokoll",
                         {"text": f"Start Wertungslauf {self.lauf_nummer}"}),
                Ereignis("start", {"modus": WERTUNG, "lauf": self.lauf_nummer})]

    def _runde_beenden(self, jetzt):
        gefahren = zeit.aus_sekunden(jetzt - self._lauf_start)
        self.runden += 1
        self._letzte_zeit = gefahren
        ereignisse = []

        if self.modus == TRAINING:
            beschriftung = f"Runde{self.runden}: "
            ereignisse.append(Ereignis("runde", {
                "nummer": self.runden, "zeit": gefahren,
                "text": beschriftung + zeit.formatiere(gefahren)}))

            fertig = (self.runden >= self.max_runden
                      or self.training_zeit_abgelaufen())
            if fertig:
                self.laeuft = False
                self._lauf_start = None
                ereignisse.append(Ereignis("protokoll", {"text": "Ende Training"}))
                ereignisse.append(Ereignis("ende_training", {
                    "runden": self.runden, "zeit": gefahren}))
                return ereignisse

            # Im Training wird jede Runde einzeln gemessen: die Uhr fängt
            # für die nächste Runde wieder bei null an.
            self._lauf_start = jetzt
            verbleibend = self.max_runden - self.runden
            if verbleibend <= int(self.einst.tr_warnung_runden):
                ereignisse.append(Ereignis("warnton", {"verbleibend": verbleibend}))
            return ereignisse

        # --- Wertungslauf: die Uhr läuft über alle Runden durch -----------
        vorsatz = "+ " if self.runden > 1 else ""
        ereignisse.append(Ereignis("runde", {
            "nummer": self.runden, "zeit": gefahren,
            "text": f"{vorsatz}Runde{self.runden}: " + zeit.formatiere(gefahren)}))

        if self.runden < self.max_runden:
            return ereignisse

        self.laeuft = False
        self._lauf_start = None
        self.zeiten[self.lauf_nummer] = gefahren
        ereignisse.append(Ereignis("protokoll", {"text": "Ende Wertungslauf"}))
        ereignisse.append(Ereignis("ende_lauf", {
            "lauf": self.lauf_nummer, "zeit": gefahren}))

        if self.lauf_nummer >= int(self.einst.we_anzahl_laeufe):
            gesamt = sum(self.zeiten.values())
            ereignisse.append(Ereignis("protokoll", {
                "text": "Gesamtfahrzeit: " + zeit.formatiere(gesamt)}))
            ereignisse.append(Ereignis("starter_erfassen", {
                "anlass": "wertung_ende", "lauf": self.lauf_nummer,
                "zeit": gefahren}))
        else:
            ereignisse.append(Ereignis("starter_erfassen", {
                "anlass": "lauf_ende", "lauf": self.lauf_nummer,
                "zeit": gefahren}))
        return ereignisse

    # ------------------------------------------------------------------
    def lauf_wiederholen(self, lauf):
        """Ein Lauf wird für ungültig erklärt und noch einmal gefahren."""
        self.zeiten.pop(lauf, None)
        self.lauf_nummer = max(0, lauf - 1)
        self.runden = 0
        self.laeuft = False
        self._lauf_start = None
        self._letzte_zeit = 0
        self.modus = WERTUNG
        self.einfuehrung_zaehler = int(self.einst.we_einfuehrungsrunden)
        return [Ereignis("protokoll",
                         {"text": f"{lauf}. Wertungslauf wiederholen"})]

    def neuer_starter(self):
        """Alles auf Anfang für den nächsten Fahrer."""
        self.laeuft = False
        self.runden = 0
        self.lauf_nummer = 0
        self.einfuehrung_zaehler = 0
        self.zeiten = {}
        self._lauf_start = None
        self._gesamt_start = None
        self._letzte_zeit = 0
        self.modus = EINFUEHRUNG if int(self.einst.we_einfuehrungsrunden) > 0 else WERTUNG
        if self.modus == WERTUNG:
            self.einfuehrung_zaehler = int(self.einst.we_einfuehrungsrunden)
        return [Ereignis("neuer_starter", {"modus": self.modus})]
