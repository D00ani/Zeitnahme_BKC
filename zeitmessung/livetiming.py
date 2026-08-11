# -*- coding: utf-8 -*-
"""
Live-Timing: die Ergebnisse des Tages als ``livedata.json`` für die Webseite.

Das war früher ein eigenes Werkzeug, das die Access-Datenbank von außen
ausgelesen hat. Jetzt gehört es zum Programm: sobald ein Ergebnis
gespeichert wird, schreibt sich die Datei selbst neu. Kein zweites Fenster,
keine Dauerschleife, nichts, was vergessen oder doppelt gestartet werden
kann.

**Abschaltbar.** Steht der Hauptschalter in den Einstellungen auf "Nein",
passiert hier gar nichts - das Programm ist dann eine reine Zeitmessung.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

from . import zeit
from .wertung import rangliste

# LaufNr in der Datenbank -> Beschriftung auf der Live-Seite
LAUF_NAMEN = {1: "1. WL", 2: "2. WL", 0: "Gesamt"}


# ----------------------------------------------------------------------
# Die Datei bauen
# ----------------------------------------------------------------------

def _klassenname(klasse):
    """Die Zeitmessung kennt "1a", die Webseite zeigt "Klasse 1a"."""
    klasse = (klasse or "").strip()
    if not klasse:
        return "Ohne Klasse"
    return klasse if klasse.lower().startswith("klasse") else f"Klasse {klasse}"


def _startnummer(text):
    text = str(text or "")
    return int(text) if text.isdigit() else text


def _strafzeit_anzeige(eintrag):
    """Mittlere Zeile der Zeitspalte: die Strafsekunden, z. B. "(12)"."""
    strafzeit = str(eintrag.get("strafzeit", "")).strip()
    if strafzeit.isdigit() and int(strafzeit) > 0:
        return f"({int(strafzeit)})"
    return ""


def _natuerlich(text):
    """Sortiert "1a" vor "1b" vor "2" vor "10" statt rein alphabetisch."""
    return [(0, int(teil)) if teil.isdigit() else (1, teil)
            for teil in re.split(r"(\d+)", str(text or "")) if teil]


def baue_ergebnisse(eintraege):
    """Macht aus den Datenbankzeilen die Liste, die ``js/live.js`` erwartet:
    je Klasse und Lauf sortiert, mit Platz und Rückständen."""
    gruppen = {}
    for eintrag in eintraege:
        if eintrag.get("laufnr") not in LAUF_NAMEN:
            continue
        gruppen.setdefault((eintrag.get("klasse", ""), eintrag["laufnr"]), []) \
               .append(eintrag)

    ergebnisse = []
    for klasse, laufnr in sorted(gruppen, key=lambda s: (_natuerlich(s[0]), s[1])):
        gereiht = rangliste(gruppen[(klasse, laufnr)])

        bestzeit = None
        vorherige = None
        for eintrag in gereiht:
            gesamt = eintrag.get("gesamtzeit_hs")
            if gesamt is None:
                gesamt = zeit.parse(eintrag.get("gesamtzeit", ""))
            if gesamt is not None and bestzeit is None:
                bestzeit = gesamt

            rueckstand_erster = rueckstand_vorheriger = ""
            if gesamt is not None and eintrag["platz"] > 1:
                if bestzeit is not None:
                    rueckstand_erster = "+" + zeit.formatiere(gesamt - bestzeit)
                if vorherige is not None:
                    rueckstand_vorheriger = "+" + zeit.formatiere(gesamt - vorherige)
            if gesamt is not None:
                vorherige = gesamt

            ergebnisse.append({
                "klasse": _klassenname(eintrag.get("klasse", "")),
                "lauf": LAUF_NAMEN[laufnr],
                "platz": eintrag["platz"],
                "startnummer": _startnummer(eintrag.get("starternr", "")),
                "name": eintrag.get("name", ""),
                "club": eintrag.get("verein", ""),
                "zeit_raw": eintrag.get("fahrzeit", ""),
                "fehler": _strafzeit_anzeige(eintrag),
                "zeit_total": eintrag.get("gesamtzeit", ""),
                "diff_first": rueckstand_erster,
                "diff_prev": rueckstand_vorheriger,
            })
    return ergebnisse


def baue_livedata(eintraege, datum, veranstaltung="", jetzt=None):
    jetzt = jetzt or datetime.now()
    try:
        anzeigedatum = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        anzeigedatum = datum
    return {
        "last_update": jetzt.strftime("%H:%M:%S"),
        # Voller Zeitstempel, damit die Seite ausrechnen kann, wie alt der
        # Stand ist - eine Uhrzeit allein sagt nicht, ob noch gemessen wird.
        "stand_iso": jetzt.astimezone().isoformat(timespec="seconds"),
        "datum": anzeigedatum,
        "datum_iso": datum,
        "veranstaltung": veranstaltung or "",
        "quelle": "Zeitmessung",
        "results": baue_ergebnisse(eintraege),
    }


def leerer_stand():
    """Der Ruhezustand zwischen zwei Renntagen: die Seite zeigt dann
    "Warte auf Zeitnahme" statt der Ergebnisse von vorgestern."""
    return {"last_update": "", "stand_iso": "", "datum": "", "datum_iso": "",
            "veranstaltung": "", "quelle": "", "results": []}


# ----------------------------------------------------------------------
# Schreiben
# ----------------------------------------------------------------------

def _schreibe_json(pfad, daten):
    ordner = os.path.dirname(os.path.abspath(pfad))
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _kennung(daten):
    """Alles außer dem Zeitstempel - nur wenn sich das ändert, muss die
    Datei überhaupt neu geschrieben werden."""
    return json.dumps([daten.get("datum"), daten.get("veranstaltung"),
                       daten.get("results")], ensure_ascii=False, sort_keys=True)


def schreibe_livedata(pfad, daten):
    """Schreibt die Datei nur, wenn sich inhaltlich etwas geändert hat.
    Gibt True zurück, wenn geschrieben wurde."""
    if os.path.isfile(pfad):
        try:
            with open(pfad, encoding="utf-8") as f:
                if _kennung(json.load(f)) == _kennung(daten):
                    return False
        except (OSError, ValueError):
            pass
    _schreibe_json(pfad, daten)
    return True


def archiviere(archiv_ordner, daten):
    """Legt den Stand zusätzlich als ``<Renntag>.json`` ab und pflegt das
    Verzeichnis der Renntage, damit vergangene Rennen erhalten bleiben.

    Geschrieben wird nur, wenn sich inhaltlich etwas geändert hat - der
    Zeitstempel allein zählt nicht. Sonst entstünde bei jedem Abgleich eine
    neue Fassung der Datei, die committet und über die mobile Verbindung
    hochgeladen werden müsste, ohne dass ein einziges Ergebnis anders wäre.
    """
    if not archiv_ordner:
        return False
    datum = daten.get("datum_iso") or ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum) or not daten.get("results"):
        return False

    geschrieben = schreibe_livedata(os.path.join(archiv_ordner, f"{datum}.json"),
                                    daten)

    index = os.path.join(archiv_ordner, "index.json")
    verzeichnis = []
    if os.path.isfile(index):
        try:
            with open(index, encoding="utf-8") as f:
                verzeichnis = json.load(f).get("renntage", [])
        except (OSError, ValueError):
            verzeichnis = []

    eintrag = {
        "datum": datum,
        "anzeige": daten.get("datum", datum),
        "veranstaltung": daten.get("veranstaltung", ""),
        "starter": len({(e["klasse"], e["startnummer"]) for e in daten["results"]}),
        "ergebnisse": len(daten["results"]),
    }
    neu = [e for e in verzeichnis if e.get("datum") != datum] + [eintrag]
    neu.sort(key=lambda e: e.get("datum", ""), reverse=True)
    if neu != verzeichnis:
        _schreibe_json(index, {"renntage": neu})
        geschrieben = True
    return geschrieben


# ----------------------------------------------------------------------
# Veröffentlichen
# ----------------------------------------------------------------------

# Unter Windows verhindert dieses Kennzeichen, dass bei jedem Git-Aufruf
# kurz ein schwarzes Konsolenfenster aufblitzt. Auf anderen Systemen kennt
# subprocess es nicht und würde einen Fehler werfen.
_OHNE_FENSTER = {"creationflags": 0x08000000} if sys.platform.startswith("win") else {}


def _git(argumente, ordner, umgebung=None):
    return subprocess.run(["git"] + argumente, cwd=ordner, env=umgebung,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          **_OHNE_FENSTER)


def _branch(ordner):
    ergebnis = _git(["rev-parse", "--abbrev-ref", "HEAD"], ordner)
    return (ergebnis.stdout or "").strip() if ergebnis.returncode == 0 else ""


def veroeffentliche(einstellungen, nachricht, pfade):
    """Überträgt **nur** die Ergebnisdateien auf die Live-Seite.

    Bewusst kein ``git merge`` des ganzen Arbeitsstandes: sonst ginge mit
    jedem Zwischenstand während des Rennens auch jeder halbfertige Umbau
    der Webseite mit live. Es werden ausschließlich die übergebenen Pfade
    übernommen.

    Gibt (erfolg, meldung) zurück.
    """
    arbeit = str(einstellungen.arbeits_repo).strip()
    # Ohne zweiten Ordner wird direkt aus dem einen Ordner veröffentlicht.
    # Das ist der einfache Fall: ein eigener kleiner Klon, der nur die
    # Ergebnisdateien enthält und mit der Pflege der Webseite nichts zu tun
    # hat. Der Zwei-Ordner-Weg bleibt für getrennten Arbeits- und Live-Stand.
    live = str(einstellungen.live_repo).strip() or arbeit
    if not arbeit or not os.path.isdir(arbeit):
        return False, "Der Git-Ordner mit den Ergebnisdateien ist nicht eingestellt."
    if not os.path.isdir(live):
        return False, f"Den zweiten Git-Ordner gibt es nicht: {live}"

    relativ = []
    for pfad in pfade:
        if not pfad:
            continue
        try:
            relativ.append(os.path.relpath(pfad, arbeit).replace(os.sep, "/"))
        except ValueError:
            return False, f"{pfad} liegt nicht im Arbeitsordner der Webseite."
    if not relativ:
        return False, "Es ist nichts zu veröffentlichen."

    arbeits_branch = _branch(arbeit)
    if not arbeits_branch:
        return False, "Der Arbeitsordner ist kein Git-Ordner."

    # 1. Im Arbeitsstand festhalten
    if _git(["add", "--"] + relativ, arbeit).returncode != 0:
        return False, "git add ist fehlgeschlagen."
    if _git(["diff", "--cached", "--quiet", "--"] + relativ, arbeit).returncode == 0:
        return True, "nichts zu veröffentlichen"
    ergebnis = _git(["commit", "-m", nachricht, "--"] + relativ, arbeit)
    if ergebnis.returncode != 0:
        return False, f"git commit: {(ergebnis.stderr or ergebnis.stdout).strip()}"

    # 2. Gezielt in den Live-Ordner übernehmen - entfällt beim Ein-Ordner-Weg,
    #    dort ist der Commit aus Schritt 1 schon der richtige.
    zwei_ordner = os.path.abspath(live) != os.path.abspath(arbeit)
    if zwei_ordner:
        ergebnis = _git(["checkout", arbeits_branch, "--"] + relativ, live)
        if ergebnis.returncode != 0:
            return False, f"Übernahme: {(ergebnis.stderr or ergebnis.stdout).strip()}"
        if _git(["diff", "--cached", "--quiet", "--"] + relativ, live).returncode != 0:
            ergebnis = _git(["commit", "-m", nachricht, "--"] + relativ, live)
            if ergebnis.returncode != 0:
                return False, f"Commit: {(ergebnis.stderr or ergebnis.stdout).strip()}"

    # 3. Hochladen
    umgebung = dict(os.environ)
    paar = einstellungen.push_umgebung_paar()
    if paar:
        umgebung[paar[0]] = paar[1]
    umgebung.setdefault("GIT_TERMINAL_PROMPT", "0")
    live_branch = _branch(live) or "main"
    ergebnis = _git(["push", "origin", live_branch], live, umgebung)
    if ergebnis.returncode != 0:
        return False, f"Push: {(ergebnis.stderr or ergebnis.stdout).strip()}"

    # 4. Live-Stand zurück in den Arbeitsstand, damit die beiden nicht
    #    auseinanderlaufen. Nur beim Zwei-Ordner-Weg nötig.
    if zwei_ordner:
        _git(["merge", live_branch, "--no-edit"], arbeit)
    return True, "veröffentlicht"


# ----------------------------------------------------------------------
# Das Ganze zusammen
# ----------------------------------------------------------------------

class LiveTiming:
    """Hält den Zustand zwischen zwei Aktualisierungen."""

    def __init__(self, einstellungen, uhr=time.monotonic):
        self.einst = einstellungen
        self.uhr = uhr
        self.letzter_push = 0.0
        self.wartet_auf_push = False
        self.letzte_meldung = ""

    def aktiv(self):
        return self.einst.livetiming_an()

    def aktualisieren(self, datenbank, datum=None, jetzt=None):
        """Schreibt ``livedata.json`` neu und veröffentlicht, wenn eingestellt.

        Gibt eine kurze Meldung für die Statuszeile zurück ("" = aus).
        """
        if not self.aktiv():
            return ""

        datum = datum or datetime.now().strftime("%Y-%m-%d")
        eintraege = datenbank.neueste_je_starter(datum)
        daten = baue_livedata(eintraege, datum,
                              str(self.einst.veranstaltung).strip(), jetzt)

        pfad = str(self.einst.livedata_datei).strip()
        try:
            geaendert = schreibe_livedata(pfad, daten)
            archiv = str(self.einst.archiv_ordner).strip()
            if geaendert and archiv:
                archiviere(archiv, daten)
        except OSError as fehler:
            self.letzte_meldung = f"Live-Timing: {fehler}"
            return self.letzte_meldung

        if geaendert:
            self.wartet_auf_push = True
        anzahl = len(daten["results"])

        if not self.einst.veroeffentlichen_an():
            self.letzte_meldung = f"Live-Timing: {anzahl} Ergebnisse geschrieben"
            return self.letzte_meldung
        if not self.wartet_auf_push:
            self.letzte_meldung = "Live-Timing: unverändert"
            return self.letzte_meldung

        abstand = int(self.einst.push_abstand_sekunden)
        wartezeit = abstand - (self.uhr() - self.letzter_push)
        if self.letzter_push and wartezeit > 0:
            self.letzte_meldung = (f"Live-Timing: geschrieben, "
                                   f"Veröffentlichen in {int(wartezeit)} s")
            return self.letzte_meldung

        self.letzte_meldung = self.jetzt_veroeffentlichen(daten)
        return self.letzte_meldung

    def jetzt_veroeffentlichen(self, daten=None):
        """Push ohne auf den Mindestabstand zu warten (Knopf im Fenster,
        und einmal beim Beenden)."""
        if not self.einst.veroeffentlichen_an():
            return "Veröffentlichen ist ausgeschaltet."
        stand = (daten or {}).get("last_update") or datetime.now().strftime("%H:%M:%S")
        pfade = [str(self.einst.livedata_datei).strip(),
                 str(self.einst.archiv_ordner).strip()]
        erfolg, meldung = veroeffentliche(
            self.einst, f"Live-Timing: Zwischenstand {stand}",
            [p for p in pfade if p])
        self.letzter_push = self.uhr()
        if erfolg:
            self.wartet_auf_push = False
            return f"Live-Timing: {meldung}"
        return f"Live-Timing: {meldung}"
