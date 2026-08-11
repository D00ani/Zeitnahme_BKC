# -*- coding: utf-8 -*-
"""
Zusammenspiel aller Bausteine: ein kompletter Renntag von der Lichtschranke
bis zur fertigen ``livedata.json``.

Zusätzlich ein Startversuch der echten Fenster - der beweist, dass sich die
Oberfläche wirklich aufbauen lässt und nicht nur die Logik stimmt.
"""
import json
import os
import shutil
import tempfile
import unittest

from zeitmessung import ausdruck, livetiming as lt, wertung, zeit
from zeitmessung.ablauf import WERTUNG, Ablauf
from zeitmessung.datenbank import LAUF_1, LAUF_2, LAUF_GESAMT, Datenbank
from zeitmessung.einstellungen import Einstellungen

from .test_ablauf import Uhr


class Renntag(unittest.TestCase):
    """Zwei Fahrer, je zwei Wertungsläufe, danach Ergebnisse und Live-Datei."""

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zeitmessung-ende-")
        self.livedata = os.path.join(self.ordner, "livedata.json")
        self.archiv = os.path.join(self.ordner, "ergebnisse")
        self.einst = Einstellungen(datei=None, werte={
            "we_einfuehrungsrunden": 1, "we_runden_pro_lauf": 2,
            "we_anzahl_laeufe": 2, "strafzeit_pylone": 2, "strafzeit_fehler": 10,
            "sperrzeit_sekunden": 0, "livetiming": True,
            "livedata_datei": self.livedata, "archiv_ordner": self.archiv,
            "veroeffentlichen": False, "veranstaltung": "Testrennen",
        }).pruefen()
        self.db = Datenbank(os.path.join(self.ordner, "renntag.db"))
        self.uhr = Uhr()
        self.live = lt.LiveTiming(self.einst, uhr=self.uhr)
        self.datum = "2026-08-10"

    def tearDown(self):
        self.db.schliessen()
        shutil.rmtree(self.ordner, ignore_errors=True)

    # ------------------------------------------------------------------
    def _fahrer_durchspielen(self, nummer, name, klasse, rundenzeiten,
                             pylonen=(0, 0), fehler=(0, 0)):
        """Spielt einen Fahrer komplett durch: Einführungsrunde, zwei
        Wertungsläufe, Eingabe der Pylonen, Speichern."""
        ablauf = Ablauf(self.einst, uhr=self.uhr)
        ergebnis = wertung.Starterergebnis(
            startnummer=nummer, name=name, klasse=klasse, verein="AC Singen",
            sek_pylone=int(self.einst.strafzeit_pylone),
            sek_fehler=int(self.einst.strafzeit_fehler))

        ablauf.modus_setzen(WERTUNG)
        for lauf in (1, 2):
            ablauf.ausloesen()                       # Lauf starten
            for runde in rundenzeiten[lauf - 1]:
                self.uhr.vor(runde)
                ereignisse = ablauf.ausloesen()
            ende = next(e for e in ereignisse if e.art == "ende_lauf")
            ergebnis.zeit_setzen(lauf, ende["zeit"])
            ergebnis.lauf(lauf).pylonen = pylonen[lauf - 1]
            ergebnis.lauf(lauf).fehler = fehler[lauf - 1]
            self.db.ergebnis_speichern(
                datum=self.datum, starternr=nummer, name=name, klasse=klasse,
                verein="AC Singen", laufnr=lauf, **ergebnis.als_text(lauf))
            self.uhr.vor(30)                          # Pause bis zum nächsten

        self.db.ergebnis_speichern(
            datum=self.datum, starternr=nummer, name=name, klasse=klasse,
            verein="AC Singen", laufnr=LAUF_GESAMT, **ergebnis.gesamt_als_text())
        return ergebnis

    # ------------------------------------------------------------------
    def test_kompletter_renntag(self):
        anton = self._fahrer_durchspielen(
            "1", "Anton", "3", [[20.0, 21.03], [19.0, 18.5]],
            pylonen=(3, 0), fehler=(0, 1))
        berta = self._fahrer_durchspielen(
            "2", "Berta", "3", [[18.0, 19.0], [17.5, 18.0]])

        # --- Zeiten stimmen und sind konsistent formatiert -----------------
        self.assertEqual(zeit.formatiere(anton.lauf(1).fahrzeit), "00:41,03")
        self.assertEqual(zeit.formatiere(anton.lauf(2).fahrzeit), "00:37,50")
        self.assertEqual(anton.strafzeit_gesamt_sekunden(), 16)   # 3*2 + 1*10
        self.assertEqual(zeit.formatiere(anton.gesamt()), "01:34,53")

        self.assertEqual(zeit.formatiere(berta.lauf(1).fahrzeit), "00:37,00")
        self.assertEqual(zeit.formatiere(berta.gesamt()), "01:12,50")

        # --- Datenbank: 3 Datensätze je Fahrer -----------------------------
        alle = self.db.ergebnisse(self.datum)
        self.assertEqual(len(alle), 6)
        for eintrag in alle:
            self.assertRegex(eintrag["gesamtzeit"], r"^\d{2}:\d{2},\d{2}$")

        # --- Platzierung: Berta ist schneller ------------------------------
        gesamt = [e for e in self.db.neueste_je_starter(self.datum)
                  if e["laufnr"] == LAUF_GESAMT]
        gereiht = wertung.rangliste(gesamt)
        self.assertEqual([e["name"] for e in gereiht], ["Berta", "Anton"])
        self.assertEqual([e["platz"] for e in gereiht], [1, 2])

        # --- Live-Datei ----------------------------------------------------
        meldung = self.live.aktualisieren(self.db, self.datum)
        self.assertIn("Ergebnisse", meldung)
        with open(self.livedata, encoding="utf-8") as f:
            daten = json.load(f)

        self.assertEqual(daten["datum"], "10.08.2026")
        self.assertEqual(daten["veranstaltung"], "Testrennen")
        self.assertEqual(len(daten["results"]), 6)   # 2 Fahrer x (1. WL, 2. WL, Gesamt)

        gesamtzeilen = [e for e in daten["results"] if e["lauf"] == "Gesamt"]
        self.assertEqual([e["name"] for e in gesamtzeilen], ["Berta", "Anton"])
        self.assertEqual(gesamtzeilen[0]["diff_first"], "")
        self.assertEqual(gesamtzeilen[1]["diff_first"], "+00:22,03")
        self.assertEqual(gesamtzeilen[1]["fehler"], "(16)")

        # --- Archiv --------------------------------------------------------
        archivdatei = os.path.join(self.archiv, f"{self.datum}.json")
        self.assertTrue(os.path.isfile(archivdatei))
        with open(os.path.join(self.archiv, "index.json"), encoding="utf-8") as f:
            verzeichnis = json.load(f)["renntage"]
        self.assertEqual(verzeichnis[0]["starter"], 2)

    def test_ausdruck_des_ersten_fahrers(self):
        anton = self._fahrer_durchspielen(
            "1", "Anton", "3", [[20.0, 21.03], [19.0, 18.5]],
            pylonen=(3, 0), fehler=(0, 1))
        anweisungen = ausdruck.bauplan(anton)
        texte = [a[4] for a in anweisungen if a[0] == "text"]
        self.assertIn("01:34,53", texte)      # Gesamtzeit oben
        self.assertIn("00:41,03", texte)      # Fahrzeit 1. Lauf
        self.assertIn("3/0", texte)           # Pylonen/Fehler 1. Lauf
        self.assertIn("0/1", texte)           # Pylonen/Fehler 2. Lauf

    def test_wiederholter_lauf_verdraengt_den_alten(self):
        """Wird ein Lauf wiederholt, darf am Ende nur der neue zählen."""
        self._fahrer_durchspielen("1", "Anton", "3",
                                  [[30.0, 30.0], [30.0, 30.0]])
        # zweiter Durchgang desselben Fahrers, schneller
        self._fahrer_durchspielen("1", "Anton", "3",
                                  [[20.0, 20.0], [20.0, 20.0]])
        gesamt = [e for e in self.db.neueste_je_starter(self.datum)
                  if e["laufnr"] == LAUF_GESAMT]
        self.assertEqual(len(gesamt), 1)
        self.assertEqual(gesamt[0]["gesamtzeit"], "01:20,00")

        self.live.aktualisieren(self.db, self.datum)
        with open(self.livedata, encoding="utf-8") as f:
            daten = json.load(f)
        gesamtzeilen = [e for e in daten["results"] if e["lauf"] == "Gesamt"]
        self.assertEqual(len(gesamtzeilen), 1,
                         "der Fahrer darf nicht doppelt auftauchen")


class PasstZurWebseite(unittest.TestCase):
    """Die erzeugte Datei muss dieselben Felder haben wie die, die die
    Live-Seite bisher bekommen hat."""

    ARCHIV_DER_WEBSEITE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "mch-arbeit", "data", "ergebnisse", "2026-05-04.json")

    def test_gleiche_felder_wie_bisher(self):
        if not os.path.isfile(self.ARCHIV_DER_WEBSEITE):
            self.skipTest("Kein Archiv der Webseite zum Vergleichen vorhanden.")
        with open(self.ARCHIV_DER_WEBSEITE, encoding="utf-8") as f:
            alt = json.load(f)

        neu = lt.baue_livedata(
            [{"starternr": "1", "name": "Anton", "verein": "AC Singen",
              "klasse": "3", "laufnr": LAUF_GESAMT, "fahrzeit": "00:42,00",
              "strafzeit": "0", "gesamtzeit": "00:42,00",
              "gesamtzeit_hs": 4200}], "2026-08-10", "Testrennen")

        self.assertEqual(set(alt.keys()), set(neu.keys()),
                         "Die Kopfzeilen der Datei müssen gleich heißen.")
        self.assertEqual(set(alt["results"][0].keys()),
                         set(neu["results"][0].keys()),
                         "Die Felder je Ergebnis müssen gleich heißen.")


class FensterLassenSichAufbauen(unittest.TestCase):
    """Startversuch der echten Oberfläche - sie wird aufgebaut und sofort
    wieder geschlossen."""

    def test_hauptfenster(self):
        try:
            import tkinter
            tkinter.Tk().destroy()
        except Exception as fehler:                   # noqa: BLE001
            self.skipTest(f"Keine Fensteroberfläche verfügbar: {fehler}")

        from zeitmessung.oberflaeche.haupt import Hauptfenster

        ordner = tempfile.mkdtemp(prefix="zeitmessung-fenster-")
        try:
            einst = Einstellungen(datei=None, werte={
                "datenbank": os.path.join(ordner, "test.db"),
                "serieller_port": "", "livetiming": False,
                "eine_lichtschranke": True}).pruefen()
            fenster = Hauptfenster(einst)
            fenster.update()          # einmal wirklich zeichnen

            # Ein Auslöser über die Logik, damit auch die Anzeige mitläuft
            fenster._ausloesen()
            fenster.update()
            self.assertTrue(fenster.ablauf.laeuft)
            self.assertIn("F1", fenster.knopf_messen["text"])

            fenster._abbrechen()
            fenster.update()
            self.assertFalse(fenster.ablauf.laeuft)

            fenster.db.schliessen()
            fenster.destroy()
        finally:
            shutil.rmtree(ordner, ignore_errors=True)

    def test_starter_und_einstellungsfenster(self):
        try:
            import tkinter
            tkinter.Tk().destroy()
        except Exception as fehler:                   # noqa: BLE001
            self.skipTest(f"Keine Fensteroberfläche verfügbar: {fehler}")

        import tkinter as tk

        from zeitmessung.oberflaeche.einstellungsfenster import Einstellungsfenster
        from zeitmessung.oberflaeche.starterfenster import Starterfenster
        from zeitmessung.oberflaeche import stil

        wurzel = tk.Tk()
        wurzel.withdraw()
        stil.grundeinstellung(wurzel)
        try:
            einst = Einstellungen(datei=None).pruefen()
            starter = Starterfenster(wurzel, einst, lambda *_: None,
                                     lambda *_: True, lambda *_: None)
            ergebnis = wertung.Starterergebnis(sek_pylone=2, sek_fehler=10)
            ergebnis.zeit_setzen(1, 4103)
            starter.erfassen_oeffnen(ergebnis, "5")
            wurzel.update()
            self.assertEqual(starter.var_nummer.get(), "5")

            # Pylonen eintragen - die Summen müssen sofort nachziehen
            starter.zeilen[1]["pylonen"].set("3")
            wurzel.update()
            self.assertEqual(starter.zeilen[1]["strafzeit"].get(), "6")
            self.assertEqual(starter.zeilen[1]["summe"].get(), "00:47,03")

            fenster = Einstellungsfenster(wurzel, einst, lambda: None)
            wurzel.update()
            self.assertEqual(fenster.variablen["strafzeit_pylone"].get(), "2")

            # Drucker und Lichtschranken-Port müssen Auswahllisten sein,
            # nicht bloß Textfelder - sonst vertippt man sich am Renntag.
            from zeitmessung.ausdruck import drucker_liste
            auswahl = fenster._druckerauswahl()
            self.assertEqual(auswahl[0], "", "leer = Standarddrucker")
            for drucker in drucker_liste():
                self.assertIn(drucker, auswahl)
            fenster.destroy()
        finally:
            wurzel.destroy()


if __name__ == "__main__":
    unittest.main()
