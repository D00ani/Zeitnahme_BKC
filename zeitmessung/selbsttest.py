# -*- coding: utf-8 -*-
"""
Selbsttest - vor dem Renntag einmal alles durchklingeln.

Prüft der Reihe nach, was am Renntag gebraucht wird, und sagt bei jedem
Punkt in einem Satz, was zu tun ist, wenn er nicht stimmt. Bewusst ohne
Oberfläche, damit sich die Prüfungen einzeln testen lassen.

Jede Prüfung gibt ein ``Befund`` zurück. ``ok`` heißt: passt. ``warnung``
heißt: geht, ist aber nicht optimal. ``fehler`` heißt: das muss vor dem
Rennen erledigt werden.
"""
import os
from dataclasses import dataclass, field

from . import ausdruck, lichtschranke, livetiming

OK = "ok"
WARNUNG = "warnung"
FEHLER = "fehler"


@dataclass
class Befund:
    titel: str
    zustand: str
    text: str
    rat: str = ""

    @property
    def zeichen(self):
        return {OK: "OK", WARNUNG: "!", FEHLER: "X"}.get(self.zustand, "?")


@dataclass
class Bericht:
    befunde: list = field(default_factory=list)

    def __iter__(self):
        return iter(self.befunde)

    def __len__(self):
        return len(self.befunde)

    @property
    def fehler(self):
        return [b for b in self.befunde if b.zustand == FEHLER]

    @property
    def warnungen(self):
        return [b for b in self.befunde if b.zustand == WARNUNG]

    @property
    def alles_gut(self):
        return not self.fehler and not self.warnungen

    def zusammenfassung(self):
        if self.fehler:
            return (f"{len(self.fehler)} Punkt(e) müssen vor dem Rennen "
                    f"erledigt werden.")
        if self.warnungen:
            return f"Startklar, mit {len(self.warnungen)} Hinweis(en)."
        return "Alles bereit."

    def als_text(self):
        zeilen = []
        for befund in self.befunde:
            zeilen.append(f"[{befund.zeichen}] {befund.titel}: {befund.text}")
            if befund.rat:
                zeilen.append(f"      -> {befund.rat}")
        zeilen.append("")
        zeilen.append(self.zusammenfassung())
        return "\n".join(zeilen)


# ----------------------------------------------------------------------
# Die einzelnen Prüfungen
# ----------------------------------------------------------------------

def pruefe_datenbank(datenbank):
    try:
        anzahl = len(datenbank.renntage())
        datenbank.verlauf_speichern("Selbsttest")
        return Befund("Datenbank", OK,
                      f"beschreibbar, {anzahl} Renntag(e) gespeichert")
    except Exception as fehler:                       # noqa: BLE001
        return Befund("Datenbank", FEHLER, f"nicht beschreibbar ({fehler})",
                      "Pfad unter Einstellungen → Pfade prüfen.")


def pruefe_sicherung(sicherungspfad):
    if sicherungspfad and os.path.isfile(sicherungspfad):
        groesse = os.path.getsize(sicherungspfad) / 1024
        return Befund("Sicherung", OK,
                      f"beim Start angelegt ({groesse:.0f} kB)")
    return Befund("Sicherung", WARNUNG, "beim Start wurde keine angelegt",
                  "Schreibrechte im Ordner „daten“ prüfen.")


def pruefe_lichtschranke(einstellungen, offen):
    port = str(einstellungen.serieller_port).strip()
    vorhanden = lichtschranke.verfuegbare_ports()
    if not port:
        return Befund("Lichtschranke", WARNUNG, "keine eingestellt",
                      f"Gemessen wird dann nur mit F1. Vorhanden wäre: "
                      f"{', '.join(vorhanden) or 'nichts'}")
    if offen:
        return Befund("Lichtschranke", OK, f"verbunden an {port}")
    if port not in vorhanden:
        return Befund("Lichtschranke", FEHLER,
                      f"{port} ist nicht da",
                      f"Stecker prüfen. Gefunden wurde: "
                      f"{', '.join(vorhanden) or 'nichts'}")
    return Befund("Lichtschranke", FEHLER, f"{port} lässt sich nicht öffnen",
                  "Benutzt sie noch ein anderes Programm?")


def pruefe_drucker(einstellungen):
    if einstellungen.vorschau_statt_druck:
        return Befund("Ausdruck", WARNUNG, "steht auf PDF-Vorschau",
                      "Es wird kein Papier bedruckt. Für den Renntag den "
                      "Haken unter Einstellungen → Ausdruck entfernen.")
    gewaehlt = str(einstellungen.drucker).strip()
    vorhanden = ausdruck.drucker_liste()
    if not gewaehlt:
        standard = ausdruck.standarddrucker()
        if not standard:
            return Befund("Ausdruck", FEHLER, "kein Drucker eingerichtet",
                          "Unter Einstellungen → Ausdruck einen wählen.")
        if "PDF" in standard or "OneNote" in standard:
            return Befund("Ausdruck", WARNUNG,
                          f"Standarddrucker ist „{standard}“",
                          "Daraus kommt kein Papier. Besser den echten "
                          "Drucker ausdrücklich auswählen.")
        return Befund("Ausdruck", OK, f"Standarddrucker „{standard}“")
    if vorhanden and gewaehlt not in vorhanden:
        return Befund("Ausdruck", FEHLER, f"„{gewaehlt}“ gibt es nicht",
                      f"Vorhanden: {', '.join(vorhanden)}")
    return Befund("Ausdruck", OK, f"„{gewaehlt}“")


def pruefe_klassen(einstellungen):
    klassen = einstellungen.klassen_liste()
    vereine = einstellungen.vereine_liste()
    if not klassen or not vereine:
        return Befund("Klassen und Vereine", FEHLER, "Liste ist leer",
                      "Unter Einstellungen → Allgemein eintragen.")
    return Befund("Klassen und Vereine", OK,
                  f"{len(klassen)} Klassen, {len(vereine)} Vereine")


def pruefe_livetiming(einstellungen):
    if not einstellungen.livetiming:
        return Befund("Live-Timing", OK, "ausgeschaltet - reine Zeitmessung")
    datei = str(einstellungen.livedata_datei).strip()
    if not datei:
        return Befund("Live-Timing", FEHLER, "eingeschaltet, aber ohne Datei",
                      "Unter Einstellungen → Live-Timing die Datei "
                      "livedata.json eintragen.")
    ordner = os.path.dirname(datei)
    if ordner and not os.path.isdir(ordner):
        return Befund("Live-Timing", FEHLER, f"Ordner fehlt: {ordner}",
                      "Pfad prüfen.")
    if not einstellungen.veroeffentlichen:
        return Befund("Live-Timing", WARNUNG,
                      "schreibt nur lokal, veröffentlicht nicht",
                      "Zum Üben richtig. Am Renntag den Haken "
                      "„Ergebnisse automatisch veröffentlichen“ setzen.")
    return Befund("Live-Timing", OK, "eingeschaltet, veröffentlicht")


def pruefe_veroeffentlichen(einstellungen):
    if not einstellungen.veroeffentlichen_an():
        return None                    # nichts zu prüfen
    ordner = str(einstellungen.arbeits_repo).strip()
    if not os.path.isdir(os.path.join(ordner, ".git")) and \
            not os.path.isfile(os.path.join(ordner, ".git")):
        return Befund("Verbindung zur Webseite", FEHLER,
                      f"{ordner} ist kein Git-Ordner",
                      "Unter Einstellungen → Live-Timing den richtigen "
                      "Ordner wählen.")
    ergebnis = livetiming._git(["ls-remote", "--exit-code", "origin", "HEAD"],
                               ordner, geduld=25)
    if ergebnis.returncode != 0:
        return Befund("Verbindung zur Webseite", WARNUNG,
                      "GitHub ist gerade nicht erreichbar",
                      "Gemessen und gespeichert wird trotzdem; "
                      "veröffentlicht wird, sobald wieder Netz da ist.")
    return Befund("Verbindung zur Webseite", OK, "GitHub erreichbar")


def alles_pruefen(einstellungen, datenbank, lichtschranke_offen=False,
                  sicherungspfad=""):
    """Führt alle Prüfungen aus und gibt einen Bericht zurück."""
    befunde = [
        pruefe_datenbank(datenbank),
        pruefe_sicherung(sicherungspfad),
        pruefe_klassen(einstellungen),
        pruefe_lichtschranke(einstellungen, lichtschranke_offen),
        pruefe_drucker(einstellungen),
        pruefe_livetiming(einstellungen),
    ]
    verbindung = pruefe_veroeffentlichen(einstellungen)
    if verbindung is not None:
        befunde.append(verbindung)
    return Bericht([b for b in befunde if b is not None])
