# -*- coding: utf-8 -*-
"""
Einstellungen.

Alles, was sich einstellen lässt, steht in **einer** Datei ``einstellungen.json``
neben dem Programm. Jedes Feld ist unten in ``FELDER`` einmal beschrieben -
Beschriftung, Typ, Standardwert. Daraus baut sich das Einstellungsfenster von
selbst auf, und daraus kommt auch die Prüfung beim Laden.

Im alten Programm lagen die Einstellungen in der Access-Datenbank und die
Pfade teils fest im Code, teils in der ``App.config``. Hier ist beides an
einer Stelle, und **alle** Pfade sind einstellbar.
"""
import json
import os

# Ordner des Programms (eine Ebene über diesem Paket)
PROGRAMM_ORDNER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STANDARD_DATEI = os.path.join(PROGRAMM_ORDNER, "einstellungen.json")

# (Schlüssel, Gruppe, Beschriftung, Typ, Standardwert, Hinweis)
#
# Typen:  int   - ganze Zahl
#         text  - Freitext
#         bool  - Ja/Nein
#         liste - mit Semikolon getrennte Aufzählung
#         datei / ordner - Pfad (mit Durchsuchen-Knopf im Fenster)
#         port    - serielle Schnittstelle (Auswahlliste)
#         drucker - eingerichteter Drucker (Auswahlliste)
FELDER = [
    # --- Wertung -----------------------------------------------------------
    ("we_einfuehrungsrunden", "Wertung", "Anzahl Einführungsrunden", "int", 1, ""),
    ("we_runden_pro_lauf", "Wertung", "Anzahl Runden pro Wertung", "int", 2, ""),
    ("we_anzahl_laeufe", "Wertung", "Anzahl Wertungsläufe", "int", 2, "maximal 2"),
    ("strafzeit_pylone", "Wertung", "Strafzeit pro Pylone", "int", 2, "Sekunden"),
    ("strafzeit_fehler", "Wertung", "Strafzeit für Fehler", "int", 10, "Sekunden"),
    ("starter_eingabe", "Wertung", "Eingabe StarterNr, Name, Klasse", "bool", True, ""),
    ("starter_bei_einfuehrung", "Wertung",
     "Starter-Fenster schon während der Einführungsrunde", "bool", False, ""),
    ("ergebnis_drucken", "Wertung", "Ergebniskarte drucken", "bool", True, ""),

    # --- Training ----------------------------------------------------------
    ("tr_max_runden", "Training", "Max. Anzahl Trainingsrunden", "int", 15, ""),
    ("tr_max_zeit", "Training", "Maximale Dauer", "int", 5, "Minuten"),
    ("tr_warnung_runden", "Training", "Warnton x Runden vor Ende", "int", 3, ""),

    # --- Allgemein ---------------------------------------------------------
    ("klassen", "Allgemein", "Klassen", "liste", "1;1a;1b;1c;1d;2;3;4",
     "Trennzeichen = ;"),
    ("vereine", "Allgemein", "Vereine", "liste",
     "MCH Singen;AC Engen;MSC Steisslingen;AC Singen;AMC Messkirch;MSG Salemertal",
     "Trennzeichen = ;"),
    ("eine_lichtschranke", "Allgemein", "Nur eine Lichtschranke", "bool", True,
     "aus = zusätzliche Zwischenzeit-Lichtschranken"),
    ("zwischenzeit_halten", "Allgemein",
     "Zwischenzeit stehen lassen für", "int", 7, "Sekunden"),
    ("history_zeilen", "Allgemein", "Max. Zeilen im Verlauf", "int", 400, ""),

    # --- Lichtschranke -----------------------------------------------------
    ("serieller_port", "Lichtschranke", "Lichtschranken-Port", "port", "", ""),
    ("baudrate", "Lichtschranke", "Baudrate", "int", 9600, ""),
    ("ls_bei_tastendruck", "Lichtschranke",
     "Signal = Unterbruch (wie Taste F1 drücken)", "bool", True, ""),
    ("sperrzeit_sekunden", "Lichtschranke",
     "Sperrzeit, in der kein zweites Signal verarbeitet wird", "int", 1, "Sekunden"),

    # --- Ausdruck ----------------------------------------------------------
    # Zum Üben und Einrichten: es wird kein Papier bedruckt, sondern eine PDF
    # erzeugt und angezeigt. Der Zeichenweg ist derselbe wie beim echten
    # Druck, die Vorschau sieht also aus wie das spätere Blatt.
    ("vorschau_statt_druck", "Ausdruck", "Nur PDF-Vorschau statt Drucken",
     "bool", False, "zum Üben - es wird kein Papier bedruckt"),
    ("vorschau_ordner", "Ausdruck", "Ordner für die PDF-Vorschau", "ordner", "",
     "leer = Unterordner „vorschau“ beim Programm"),
    ("drucker", "Ausdruck", "Drucker", "drucker", "",
     "leer = der Windows-Standarddrucker"),
    ("pr_linker_rand", "Ausdruck", "Linker Rand", "int", 10, "Millimeter"),
    ("pr_oberer_rand", "Ausdruck", "Oberer Rand", "int", 10, "Millimeter"),
    ("pr_unterer_abstand", "Ausdruck", "Unterer Abstand", "int", 20, "Millimeter"),

    # --- Pfade -------------------------------------------------------------
    ("datenbank", "Pfade", "Datenbank dieses Programms", "datei",
     os.path.join(PROGRAMM_ORDNER, "daten", "zeitmessung.db"), ""),

    # --- Live-Timing -------------------------------------------------------
    # Hauptschalter. Steht er auf Nein, verhält sich das Programm wie eine
    # reine Zeitmessung: kein Live-Bereich im Hauptfenster, keine Dateien,
    # kein Git. So kann es ein anderer Verein unverändert benutzen.
    ("livetiming", "Live-Timing", "Live-Timing benutzen", "bool", False,
     "aus = reine Zeitmessung ohne Webseiten-Anbindung"),
    ("veranstaltung", "Live-Timing", "Name der Veranstaltung", "text", "",
     "steht im Kopf der Live-Seite"),
    ("livedata_datei", "Live-Timing", "Datei livedata.json der Webseite",
     "datei", "", ""),
    ("archiv_ordner", "Live-Timing", "Ordner für die Renntag-Archive",
     "ordner", "", ""),
    ("veroeffentlichen", "Live-Timing", "Ergebnisse automatisch veröffentlichen",
     "bool", False, "aus = Datei wird nur lokal geschrieben"),
    ("arbeits_repo", "Live-Timing", "Git-Ordner mit den Ergebnisdateien",
     "ordner", "", "der Ordner, in dem livedata.json liegt"),
    ("live_repo", "Live-Timing", "Zweiter Git-Ordner (Live-Seite)", "ordner", "",
     "leer = nur ein Ordner, direkt veröffentlichen"),
    ("push_abstand_sekunden", "Live-Timing",
     "Mindestabstand zwischen zwei Veröffentlichungen", "int", 60, "Sekunden"),
    ("push_umgebung", "Live-Timing", "Zusätzliche Umgebungsvariable beim Push",
     "text", "", "z. B. MCH_ERGEBNIS_PUSH=1; leer lassen, wenn nicht gebraucht"),
]

GRUPPEN = []
for _, _gruppe, *_ in FELDER:
    if _gruppe not in GRUPPEN:
        GRUPPEN.append(_gruppe)

STANDARD = {schluessel: standard for schluessel, _, _, _, standard, _ in FELDER}
TYPEN = {schluessel: typ for schluessel, _, _, typ, _, _ in FELDER}


def _umwandeln(typ, wert, standard):
    """Bringt einen gelesenen Wert auf den richtigen Typ. Unbrauchbares fällt
    auf den Standardwert zurück, damit eine kaputte Zeile in der Datei nicht
    das ganze Programm blockiert."""
    try:
        if typ == "int":
            return int(str(wert).strip())
        if typ == "bool":
            if isinstance(wert, bool):
                return wert
            return str(wert).strip().lower() in ("1", "true", "ja", "wahr", "j")
        return str(wert).strip()
    except (TypeError, ValueError):
        return standard


class Einstellungen:
    """Zugriff über Attribute: ``einst.strafzeit_pylone``."""

    def __init__(self, datei=STANDARD_DATEI, werte=None):
        self.datei = datei
        self._werte = dict(STANDARD)
        if werte:
            self._werte.update(werte)

    # -- Lesen und Schreiben ------------------------------------------------
    @classmethod
    def laden(cls, datei=STANDARD_DATEI):
        einst = cls(datei)
        if os.path.isfile(datei):
            try:
                with open(datei, encoding="utf-8") as f:
                    gelesen = json.load(f)
            except (OSError, ValueError):
                gelesen = {}
            for schluessel, wert in (gelesen or {}).items():
                if schluessel in STANDARD:
                    einst._werte[schluessel] = _umwandeln(
                        TYPEN[schluessel], wert, STANDARD[schluessel])
        einst.pruefen()
        return einst

    def speichern(self):
        self.pruefen()
        ordner = os.path.dirname(os.path.abspath(self.datei))
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        with open(self.datei, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self._werte, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")

    # -- Zugriff ------------------------------------------------------------
    def __getattr__(self, name):
        # wird nur aufgerufen, wenn das Attribut nicht normal gefunden wurde
        try:
            return self.__dict__["_werte"][name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, wert):
        if name in ("datei", "_werte") or name.startswith("_"):
            super().__setattr__(name, wert)
        elif name in STANDARD:
            self._werte[name] = _umwandeln(TYPEN[name], wert, STANDARD[name])
        else:
            super().__setattr__(name, wert)

    def setzen(self, schluessel, wert):
        setattr(self, schluessel, wert)

    def alle(self):
        return dict(self._werte)

    def auf_standard(self):
        """Setzt die Werte zurück - **ohne** zu speichern.

        Im alten Programm hing das Zurücksetzen versehentlich am Knopf
        "Abbruch" und hat sofort geschrieben. Hier passiert das nur auf
        ausdrückliche Nachfrage, und gespeichert wird erst mit "Speichern".
        """
        self._werte = dict(STANDARD)

    # -- Abgeleitetes -------------------------------------------------------
    def pruefen(self):
        """Hält unsinnige Werte aus dem Rest des Programms heraus."""
        w = self._werte
        w["we_anzahl_laeufe"] = max(1, min(2, int(w["we_anzahl_laeufe"])))
        w["we_runden_pro_lauf"] = max(1, int(w["we_runden_pro_lauf"]))
        w["we_einfuehrungsrunden"] = max(0, int(w["we_einfuehrungsrunden"]))
        w["tr_max_runden"] = max(1, int(w["tr_max_runden"]))
        w["tr_max_zeit"] = max(1, int(w["tr_max_zeit"]))
        w["tr_warnung_runden"] = max(0, min(int(w["tr_warnung_runden"]),
                                            int(w["tr_max_runden"])))
        w["strafzeit_pylone"] = max(0, int(w["strafzeit_pylone"]))
        w["strafzeit_fehler"] = max(0, int(w["strafzeit_fehler"]))
        w["sperrzeit_sekunden"] = max(0, int(w["sperrzeit_sekunden"]))
        w["history_zeilen"] = max(10, int(w["history_zeilen"]))
        w["zwischenzeit_halten"] = max(1, int(w["zwischenzeit_halten"]))
        w["push_abstand_sekunden"] = max(0, int(w["push_abstand_sekunden"]))
        w["baudrate"] = max(50, int(w["baudrate"]))
        return self

    def klassen_liste(self):
        return [t.strip() for t in str(self.klassen).split(";") if t.strip()]

    def vereine_liste(self):
        return [t.strip() for t in str(self.vereine).split(";") if t.strip()]

    def push_umgebung_paar(self):
        """"MCH_ERGEBNIS_PUSH=1" -> ("MCH_ERGEBNIS_PUSH", "1"); sonst None."""
        text = str(self.push_umgebung).strip()
        if "=" not in text:
            return None
        name, _, wert = text.partition("=")
        name = name.strip()
        return (name, wert.strip()) if name else None

    def livetiming_an(self):
        """Hauptschalter **und** ein eingetragener Dateipfad - beides muss
        stimmen, sonst wird nichts geschrieben."""
        return bool(self.livetiming) and bool(str(self.livedata_datei).strip())

    def veroeffentlichen_an(self):
        """Zusätzlich zum Live-Timing muss das Veröffentlichen an sein und
        der Git-Ordner mit den Ergebnisdateien stehen.

        Ein **zweiter** Ordner ist nur nötig, wenn die Webseite - wie bei
        MCH Singen - mit getrenntem Arbeits- und Live-Stand gepflegt wird.
        Wer einen eigenen kleinen Klon nur für die Ergebnisse benutzt, lässt
        das Feld leer.
        """
        return (self.livetiming_an() and bool(self.veroeffentlichen)
                and bool(str(self.arbeits_repo).strip()))
