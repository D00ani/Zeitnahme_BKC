# -*- coding: utf-8 -*-
"""
Datenhaltung in SQLite.

SQLite bringt Python von Haus aus mit - es braucht also weder den
Access-Treiber noch eine 32-Bit-Installation, und die Datei lässt sich
einfach kopieren und sichern.

Zwei Tabellen, genau wie früher:

``laufergebnisse``  ein Datensatz je Starter und Lauf
                    (LaufNr 1 = 1. Wertungslauf, 2 = 2., 0 = Gesamtergebnis)
``verlauf``         fortlaufendes Protokoll dessen, was passiert ist

Zusätzlich zu den Textzeiten wird die Zeit **auch als Hundertstel-Zahl**
abgelegt. Früher wurde nach der Textspalte sortiert; das geht nur so lange
gut, wie alle Zeiten exakt gleich formatiert sind. Mit einer Zahlenspalte
kann die Sortierung nicht mehr kippen.
"""
import os
import sqlite3
from datetime import datetime

from . import zeit

# Reihenfolge der Läufe, wie sie überall im Programm benutzt wird
LAUF_GESAMT = 0
LAUF_1 = 1
LAUF_2 = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS laufergebnisse (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    datum         TEXT    NOT NULL,
    uhrzeit       TEXT    NOT NULL,
    starternr     TEXT    NOT NULL DEFAULT '',
    name          TEXT    NOT NULL DEFAULT '',
    klasse        TEXT    NOT NULL DEFAULT '',
    verein        TEXT    NOT NULL DEFAULT '',
    laufnr        INTEGER NOT NULL,
    fahrzeit      TEXT    NOT NULL DEFAULT '',
    pylonen       TEXT    NOT NULL DEFAULT '',
    adw           TEXT    NOT NULL DEFAULT '',
    strafzeit     TEXT    NOT NULL DEFAULT '',
    gesamtzeit    TEXT    NOT NULL DEFAULT '',
    gesamtzeit_hs INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ergebnisse_tag ON laufergebnisse (datum, laufnr);

CREATE TABLE IF NOT EXISTS verlauf (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    zeitpunkt TEXT NOT NULL,
    text      TEXT NOT NULL,
    starternr TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_verlauf_zeit ON verlauf (zeitpunkt);
"""

SPALTEN = ["id", "datum", "uhrzeit", "starternr", "name", "klasse", "verein",
           "laufnr", "fahrzeit", "pylonen", "adw", "strafzeit", "gesamtzeit",
           "gesamtzeit_hs"]


def heute():
    return datetime.now().strftime("%Y-%m-%d")


class Datenbank:
    """Eine offene SQLite-Datei. Alle Schreibzugriffe committen sofort -
    bei einem Stromausfall mitten im Rennen ist damit höchstens der gerade
    laufende Eintrag weg, nicht der ganze Tag."""

    def __init__(self, pfad):
        self.pfad = pfad
        ordner = os.path.dirname(os.path.abspath(pfad))
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        self.verbindung = sqlite3.connect(pfad)
        self.verbindung.row_factory = sqlite3.Row
        self.verbindung.executescript(SCHEMA)
        self.verbindung.commit()

    def schliessen(self):
        try:
            self.verbindung.close()
        except sqlite3.Error:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.schliessen()

    # -- Schreiben ----------------------------------------------------------
    def ergebnis_speichern(self, datum=None, uhrzeit=None, starternr="", name="",
                           klasse="", verein="", laufnr=LAUF_1, fahrzeit="",
                           pylonen="", adw="", strafzeit="", gesamtzeit=""):
        """Hängt einen Ergebnisdatensatz an.

        Wiederholte Läufe werden - wie früher - als **zusätzlicher** Datensatz
        angehängt. Für Auswertungen zählt jeweils der jüngste, siehe
        ``neueste_je_starter``.
        """
        datum = datum or heute()
        uhrzeit = uhrzeit or datetime.now().strftime("%H:%M:%S")
        self.verbindung.execute(
            "INSERT INTO laufergebnisse (datum, uhrzeit, starternr, name, klasse,"
            " verein, laufnr, fahrzeit, pylonen, adw, strafzeit, gesamtzeit,"
            " gesamtzeit_hs) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (datum, uhrzeit, str(starternr), name, klasse, verein, int(laufnr),
             fahrzeit, str(pylonen), str(adw), str(strafzeit), gesamtzeit,
             zeit.parse(gesamtzeit)))
        self.verbindung.commit()

    def verlauf_speichern(self, text, starternr=""):
        self.verbindung.execute(
            "INSERT INTO verlauf (zeitpunkt, text, starternr) VALUES (?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text, str(starternr)))
        self.verbindung.commit()

    # -- Lesen --------------------------------------------------------------
    def ergebnisse(self, datum=None, laufnr=None):
        bedingungen, werte = [], []
        if datum:
            bedingungen.append("datum = ?")
            werte.append(datum)
        if laufnr is not None:
            bedingungen.append("laufnr = ?")
            werte.append(int(laufnr))
        wo = (" WHERE " + " AND ".join(bedingungen)) if bedingungen else ""
        zeilen = self.verbindung.execute(
            f"SELECT * FROM laufergebnisse{wo} ORDER BY id", werte).fetchall()
        return [dict(z) for z in zeilen]

    def neueste_je_starter(self, datum=None, laufnr=None):
        """Je Starter und Lauf nur der jüngste Datensatz.

        Das brauchen Platzierung, Ausdruck und Live-Timing gleichermaßen. Im
        alten Programm hat die Platzierung noch alle Datensätze gezählt - ein
        wiederholter Lauf tauchte dort doppelt auf und hat die Starterzahl
        und damit die Platzangabe verfälscht.
        """
        neueste = {}
        for eintrag in self.ergebnisse(datum, laufnr):
            if not eintrag["starternr"] and not eintrag["name"]:
                continue
            schluessel = (eintrag["laufnr"], eintrag["starternr"],
                          eintrag["name"], eintrag["klasse"])
            neueste[schluessel] = eintrag  # nach id sortiert, der letzte gewinnt
        return list(neueste.values())

    def renntage(self):
        zeilen = self.verbindung.execute(
            "SELECT DISTINCT datum FROM laufergebnisse ORDER BY datum").fetchall()
        return [z["datum"] for z in zeilen]

    def verlauf(self, grenze=400):
        zeilen = self.verbindung.execute(
            "SELECT * FROM verlauf ORDER BY id DESC LIMIT ?", (int(grenze),)
        ).fetchall()
        return [dict(z) for z in reversed(zeilen)]

    def naechste_startnummer(self, datum=None):
        """Die um eins erhöhte zuletzt vergebene Startnummer des Tages.
        Nicht-numerische Startnummern werden übersprungen, statt - wie früher -
        das Programm in den Fehlerzweig laufen zu lassen."""
        datum = datum or heute()
        zeilen = self.verbindung.execute(
            "SELECT starternr FROM laufergebnisse WHERE datum = ? ORDER BY id DESC",
            (datum,)).fetchall()
        for zeile in zeilen:
            text = (zeile["starternr"] or "").strip()
            if text.isdigit():
                return str(int(text) + 1)
        return "1"

    def loesche_tag(self, datum):
        """Nur für Aufräumarbeiten und Tests."""
        self.verbindung.execute("DELETE FROM laufergebnisse WHERE datum = ?", (datum,))
        self.verbindung.commit()

    # -- Berichtigen am Renntag ---------------------------------------------
    def ergebnis(self, kennung):
        """Ein einzelner Datensatz anhand seiner Kennung (id)."""
        zeile = self.verbindung.execute(
            "SELECT * FROM laufergebnisse WHERE id = ?", (int(kennung),)).fetchone()
        return dict(zeile) if zeile else None

    def ergebnis_aendern(self, kennung, **felder):
        """Ändert einzelne Spalten eines Datensatzes.

        Wird am Renntag gebraucht, wenn sich jemand bei den Pylonen vertippt
        hat - im alten Programm ging das nur über Access.
        """
        erlaubt = {"starternr", "name", "klasse", "verein", "fahrzeit",
                   "pylonen", "adw", "strafzeit", "gesamtzeit"}
        felder = {k: v for k, v in felder.items() if k in erlaubt}
        if not felder:
            return False
        if "gesamtzeit" in felder:
            felder["gesamtzeit_hs"] = zeit.parse(felder["gesamtzeit"])
        zuweisung = ", ".join(f"{name} = ?" for name in felder)
        self.verbindung.execute(
            f"UPDATE laufergebnisse SET {zuweisung} WHERE id = ?",
            list(felder.values()) + [int(kennung)])
        self.verbindung.commit()
        return True

    def ergebnis_loeschen(self, kennung):
        """Entfernt einen Datensatz - der saubere Weg, wenn ein Lauf
        versehentlich gespeichert wurde."""
        cursor = self.verbindung.execute(
            "DELETE FROM laufergebnisse WHERE id = ?", (int(kennung),))
        self.verbindung.commit()
        return cursor.rowcount > 0

    # -- Sicherung ----------------------------------------------------------
    def sicherung_anlegen(self, ordner=None, behalten=20):
        """Legt eine Kopie der Datenbank an und räumt alte Kopien weg.

        Läuft bei jedem Programmstart. Geht am Renntag etwas schief, ist der
        Stand von vorhin noch da.
        """
        ordner = ordner or os.path.join(
            os.path.dirname(os.path.abspath(self.pfad)), "sicherungen")
        os.makedirs(ordner, exist_ok=True)
        name = (f"{os.path.splitext(os.path.basename(self.pfad))[0]}"
                f"_{datetime.now():%Y-%m-%d_%H-%M-%S}.db")
        ziel = os.path.join(ordner, name)

        # Über die SQLite-eigene Sicherung, damit die Kopie auch dann in sich
        # stimmig ist, wenn gerade geschrieben wird.
        kopie = sqlite3.connect(ziel)
        try:
            with kopie:
                self.verbindung.backup(kopie)
        finally:
            kopie.close()

        vorhanden = sorted(
            (d for d in os.listdir(ordner) if d.endswith(".db")), reverse=True)
        for alt in vorhanden[int(behalten):]:
            try:
                os.remove(os.path.join(ordner, alt))
            except OSError:
                pass
        return ziel


# ----------------------------------------------------------------------
# Einmaliger Import der Altdaten aus der Access-Datenbank
# ----------------------------------------------------------------------

def importiere_aus_access(datenbank, accdb_pfad, lesefunktion=None):
    """Übernimmt die Tabelle ``Laufergebnisse`` aus der alten Access-Datei.

    Die Access-Datei wird dabei **nur gelesen**. Bereits vorhandene
    Datensätze (gleicher Tag, gleiche Uhrzeit, gleiche Startnummer, gleicher
    Lauf) werden übersprungen, der Import lässt sich also gefahrlos
    wiederholen.

    Gibt (übernommen, übersprungen) zurück.
    """
    lesefunktion = lesefunktion or _lies_access
    zeilen = lesefunktion(accdb_pfad)

    vorhanden = {
        (e["datum"], e["uhrzeit"], e["starternr"], e["laufnr"])
        for e in datenbank.ergebnisse()
    }
    uebernommen = uebersprungen = 0
    for zeile in zeilen:
        try:
            laufnr = int(str(zeile.get("laufnr", "")).strip() or -1)
        except ValueError:
            uebersprungen += 1
            continue
        if laufnr not in (LAUF_GESAMT, LAUF_1, LAUF_2):
            uebersprungen += 1
            continue
        schluessel = (zeile.get("datum", ""), zeile.get("uhrzeit", ""),
                      str(zeile.get("starternr", "")), laufnr)
        if schluessel in vorhanden:
            uebersprungen += 1
            continue
        datenbank.ergebnis_speichern(
            datum=zeile.get("datum", ""), uhrzeit=zeile.get("uhrzeit", ""),
            starternr=zeile.get("starternr", ""), name=zeile.get("name", ""),
            klasse=zeile.get("klasse", ""), verein=zeile.get("verein", ""),
            laufnr=laufnr, fahrzeit=zeile.get("fahrzeit", ""),
            pylonen=zeile.get("pylonen", ""), adw=zeile.get("adw", ""),
            strafzeit=zeile.get("strafzeit", ""),
            gesamtzeit=zeile.get("gesamtzeit", ""))
        vorhanden.add(schluessel)
        uebernommen += 1
    return uebernommen, uebersprungen


def _lies_access(accdb_pfad):
    """Liest die Access-Tabelle über PowerShell und den ACE-OLEDB-Treiber,
    den Windows für Access ohnehin mitbringt - ohne Zusatzpakete und ohne
    an der Datei etwas zu ändern."""
    import json
    import shutil
    import subprocess
    import tempfile

    spalten = [("Datum", "datum"), ("Uhrzeit", "uhrzeit"),
               ("StarterNr", "starternr"), ("StarterName", "name"),
               ("Klasse", "klasse"), ("Verein", "verein"), ("LaufNr", "laufnr"),
               ("Fahrzeit", "fahrzeit"), ("Pylonen", "pylonen"), ("ADW", "adw"),
               ("Strafzeit", "strafzeit"), ("Gesamtzeit", "gesamtzeit")]
    zuweisungen = "\n".join(
        f"        {ziel} = [string]$z['{quelle}']" for quelle, ziel in spalten)
    skript = f"""
param([string]$Datenbank, [string]$Ziel)
$ErrorActionPreference = 'Stop'
$tabelle = $null
foreach ($p in @('Microsoft.ACE.OLEDB.16.0','Microsoft.ACE.OLEDB.12.0')) {{
    try {{
        $v = New-Object System.Data.OleDb.OleDbConnection(
            "Provider=$p;Data Source=$Datenbank;Mode=Read")
        $v.Open()
        $a = New-Object System.Data.OleDb.OleDbDataAdapter(
            "SELECT {','.join(q for q, _ in spalten)} FROM Laufergebnisse", $v)
        $tabelle = New-Object System.Data.DataTable
        [void]$a.Fill($tabelle)
        $v.Close()
        break
    }} catch {{ $tabelle = $null }}
}}
if ($null -eq $tabelle) {{ throw 'Access-Treiber nicht gefunden' }}
$zeilen = New-Object System.Collections.ArrayList
foreach ($z in $tabelle.Rows) {{
    [void]$zeilen.Add([ordered]@{{
{zuweisungen}
    }})
}}
[System.IO.File]::WriteAllText($Ziel,
    (ConvertTo-Json -InputObject @($zeilen) -Depth 4),
    (New-Object System.Text.UTF8Encoding($false)))
"""
    ordner = tempfile.mkdtemp(prefix="zeitmessung-import-")
    skriptdatei = os.path.join(ordner, "lies.ps1")
    zieldatei = os.path.join(ordner, "daten.json")
    try:
        with open(skriptdatei, "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write(skript)
        for powershell in _powershell_kandidaten():
            ergebnis = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-File", skriptdatei,
                 "-Datenbank", os.path.abspath(accdb_pfad), "-Ziel", zieldatei],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            if ergebnis.returncode == 0 and os.path.isfile(zieldatei):
                with open(zieldatei, encoding="utf-8") as f:
                    roh = json.load(f)
                if isinstance(roh, dict):
                    roh = [roh]
                return [{k: (v or "").strip() for k, v in eintrag.items()}
                        for eintrag in (roh or [])]
        raise RuntimeError("Die Access-Datenbank konnte nicht gelesen werden.")
    finally:
        shutil.rmtree(ordner, ignore_errors=True)


def _powershell_kandidaten():
    import shutil
    windows = os.environ.get("SystemRoot", r"C:\Windows")
    kandidaten = [
        shutil.which("pwsh"),
        os.path.join(windows, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        os.path.join(windows, "SysWOW64", "WindowsPowerShell", "v1.0", "powershell.exe"),
    ]
    return [k for k in kandidaten if k and os.path.isfile(k)]
