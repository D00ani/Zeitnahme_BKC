# -*- coding: utf-8 -*-
"""Datenhaltung: Speichern, Lesen, Startnummern, Altdaten-Import."""
import os
import tempfile
import unittest

from zeitmessung import datenbank as db_modul
from zeitmessung.datenbank import LAUF_1, LAUF_2, LAUF_GESAMT, Datenbank


class MitDatenbank(unittest.TestCase):

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zeitmessung-test-")
        self.db = Datenbank(os.path.join(self.ordner, "test.db"))

    def tearDown(self):
        self.db.schliessen()
        import shutil
        shutil.rmtree(self.ordner, ignore_errors=True)

    def _speichere(self, nr, gesamt, laufnr=LAUF_GESAMT, klasse="3",
                   datum="2026-08-10", uhrzeit="10:00:00", name=None):
        self.db.ergebnis_speichern(
            datum=datum, uhrzeit=uhrzeit, starternr=nr,
            name=name or f"Fahrer {nr}", klasse=klasse, verein="AC Singen",
            laufnr=laufnr, fahrzeit=gesamt, pylonen="0", adw="0",
            strafzeit="0", gesamtzeit=gesamt)


class SpeichernUndLesen(MitDatenbank):

    def test_gespeichertes_kommt_zurueck(self):
        self._speichere("7", "00:42,00")
        eintraege = self.db.ergebnisse("2026-08-10")
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["starternr"], "7")
        self.assertEqual(eintraege[0]["gesamtzeit"], "00:42,00")

    def test_zeit_wird_auch_als_zahl_abgelegt(self):
        """Sortiert wird nach der Zahl, nicht nach dem Text."""
        self._speichere("7", "00:42,00")
        self.assertEqual(self.db.ergebnisse()[0]["gesamtzeit_hs"], 4200)

    def test_unlesbare_zeit_gibt_none_statt_fehler(self):
        self._speichere("7", "ADW")
        self.assertIsNone(self.db.ergebnisse()[0]["gesamtzeit_hs"])

    def test_filter_nach_lauf(self):
        self._speichere("7", "00:42,00", laufnr=LAUF_1)
        self._speichere("7", "00:40,00", laufnr=LAUF_2)
        self.assertEqual(len(self.db.ergebnisse("2026-08-10", LAUF_1)), 1)

    def test_renntage(self):
        self._speichere("1", "00:42,00", datum="2026-08-10")
        self._speichere("2", "00:43,00", datum="2026-05-04")
        self.assertEqual(self.db.renntage(), ["2026-05-04", "2026-08-10"])


class WiederholteLaeufe(MitDatenbank):

    def test_nur_der_juengste_datensatz_zaehlt(self):
        """Ein wiederholter Lauf wird angehängt - für die Auswertung darf
        aber nur der neue zählen. Im alten Programm tauchte der Fahrer in
        der Platzierung doppelt auf."""
        self._speichere("7", "00:50,00", uhrzeit="10:00:00")
        self._speichere("7", "00:42,00", uhrzeit="10:05:00")
        alle = self.db.ergebnisse("2026-08-10")
        neueste = self.db.neueste_je_starter("2026-08-10")
        self.assertEqual(len(alle), 2)
        self.assertEqual(len(neueste), 1)
        self.assertEqual(neueste[0]["gesamtzeit"], "00:42,00")

    def test_verschiedene_laeufe_bleiben_nebeneinander(self):
        self._speichere("7", "00:42,00", laufnr=LAUF_1)
        self._speichere("7", "00:40,00", laufnr=LAUF_2)
        self._speichere("7", "01:22,00", laufnr=LAUF_GESAMT)
        self.assertEqual(len(self.db.neueste_je_starter("2026-08-10")), 3)

    def test_leerzeilen_werden_uebersprungen(self):
        self.db.ergebnis_speichern(datum="2026-08-10", uhrzeit="10:00:00",
                                   starternr="", name="", laufnr=LAUF_GESAMT)
        self.assertEqual(self.db.neueste_je_starter("2026-08-10"), [])


class Startnummern(MitDatenbank):

    def test_erste_nummer_ist_eins(self):
        self.assertEqual(self.db.naechste_startnummer("2026-08-10"), "1")

    def test_zaehlt_hoch(self):
        self._speichere("7", "00:42,00")
        self.assertEqual(self.db.naechste_startnummer("2026-08-10"), "8")

    def test_ueberspringt_nicht_numerische_nummern(self):
        """Das alte Programm ist an einer Startnummer wie "A3" in den
        Fehlerzweig gelaufen und hat wieder bei 1 angefangen."""
        self._speichere("5", "00:42,00", uhrzeit="10:00:00")
        self._speichere("A3", "00:43,00", uhrzeit="10:01:00")
        self.assertEqual(self.db.naechste_startnummer("2026-08-10"), "6")

    def test_je_tag_getrennt(self):
        self._speichere("7", "00:42,00", datum="2026-05-04")
        self.assertEqual(self.db.naechste_startnummer("2026-08-10"), "1")


class Verlauf(MitDatenbank):

    def test_verlauf_in_richtiger_reihenfolge(self):
        for text in ("Start Training", "Runde1: 00:42,00", "Ende Training"):
            self.db.verlauf_speichern(text, "7")
        eintraege = self.db.verlauf()
        self.assertEqual([e["text"] for e in eintraege],
                         ["Start Training", "Runde1: 00:42,00", "Ende Training"])

    def test_grenze_liefert_die_juengsten(self):
        for i in range(10):
            self.db.verlauf_speichern(f"Eintrag {i}")
        eintraege = self.db.verlauf(3)
        self.assertEqual([e["text"] for e in eintraege],
                         ["Eintrag 7", "Eintrag 8", "Eintrag 9"])


class BerichtigenUndSichern(MitDatenbank):

    def test_einzelne_felder_aendern(self):
        self._speichere("7", "00:42,00")
        kennung = self.db.ergebnisse()[0]["id"]
        self.assertTrue(self.db.ergebnis_aendern(
            kennung, pylonen="3", strafzeit="6", gesamtzeit="00:48,00"))
        eintrag = self.db.ergebnis(kennung)
        self.assertEqual(eintrag["pylonen"], "3")
        self.assertEqual(eintrag["gesamtzeit"], "00:48,00")

    def test_zahlenspalte_wird_mitgezogen(self):
        """Sonst stimmt die Sortierung nach einer Berichtigung nicht mehr."""
        self._speichere("7", "00:42,00")
        kennung = self.db.ergebnisse()[0]["id"]
        self.db.ergebnis_aendern(kennung, gesamtzeit="00:48,00")
        self.assertEqual(self.db.ergebnis(kennung)["gesamtzeit_hs"], 4800)

    def test_unbekannte_felder_werden_nicht_angefasst(self):
        self._speichere("7", "00:42,00")
        kennung = self.db.ergebnisse()[0]["id"]
        self.assertFalse(self.db.ergebnis_aendern(kennung, laufnr=9))
        self.assertEqual(self.db.ergebnis(kennung)["laufnr"], LAUF_GESAMT)

    def test_loeschen(self):
        self._speichere("7", "00:42,00")
        kennung = self.db.ergebnisse()[0]["id"]
        self.assertTrue(self.db.ergebnis_loeschen(kennung))
        self.assertEqual(self.db.ergebnisse(), [])
        self.assertFalse(self.db.ergebnis_loeschen(kennung))

    def test_sicherung_ist_eine_vollstaendige_kopie(self):
        self._speichere("7", "00:42,00")
        ziel = self.db.sicherung_anlegen()
        self.assertTrue(os.path.isfile(ziel))
        kopie = Datenbank(ziel)
        try:
            self.assertEqual(len(kopie.ergebnisse()), 1)
            self.assertEqual(kopie.ergebnisse()[0]["starternr"], "7")
        finally:
            kopie.schliessen()

    def test_sicherung_haelt_die_anzahl_klein(self):
        ordner = os.path.join(self.ordner, "sicherungen")
        for _ in range(5):
            self.db.sicherung_anlegen(ordner, behalten=2)
        self.assertLessEqual(
            len([d for d in os.listdir(ordner) if d.endswith(".db")]), 2)


class AltdatenImport(MitDatenbank):

    ALTDATEN = [
        {"datum": "2026-05-04", "uhrzeit": "10:00:00", "starternr": "1",
         "name": "Anton", "klasse": "3", "verein": "AC Singen", "laufnr": "1",
         "fahrzeit": "00:42,00", "pylonen": "0", "adw": "0", "strafzeit": "0",
         "gesamtzeit": "00:42,00"},
        {"datum": "2026-05-04", "uhrzeit": "10:00:00", "starternr": "1",
         "name": "Anton", "klasse": "3", "verein": "AC Singen", "laufnr": "0",
         "fahrzeit": "00:42,00", "pylonen": "0", "adw": "0", "strafzeit": "0",
         "gesamtzeit": "00:42,00"},
        {"datum": "", "uhrzeit": "", "starternr": "", "name": "", "klasse": "",
         "verein": "", "laufnr": "", "fahrzeit": "", "pylonen": "", "adw": "",
         "strafzeit": "", "gesamtzeit": ""},
    ]

    def test_uebernimmt_und_ueberspringt_muell(self):
        uebernommen, uebersprungen = db_modul.importiere_aus_access(
            self.db, "egal.accdb", lesefunktion=lambda _: self.ALTDATEN)
        self.assertEqual(uebernommen, 2)
        self.assertEqual(uebersprungen, 1)

    def test_zweiter_import_verdoppelt_nichts(self):
        db_modul.importiere_aus_access(self.db, "egal.accdb",
                                       lesefunktion=lambda _: self.ALTDATEN)
        uebernommen, uebersprungen = db_modul.importiere_aus_access(
            self.db, "egal.accdb", lesefunktion=lambda _: self.ALTDATEN)
        self.assertEqual(uebernommen, 0)
        self.assertEqual(uebersprungen, 3)
        self.assertEqual(len(self.db.ergebnisse()), 2)


if __name__ == "__main__":
    unittest.main()
