# -*- coding: utf-8 -*-
"""Einstellungen: laden, speichern, prüfen."""
import json
import os
import shutil
import tempfile
import unittest

from zeitmessung.einstellungen import FELDER, GRUPPEN, STANDARD, Einstellungen


class Grundlagen(unittest.TestCase):

    def test_jedes_feld_hat_einen_standardwert(self):
        for schluessel, gruppe, beschriftung, typ, standard, _ in FELDER:
            self.assertIn(gruppe, GRUPPEN)
            self.assertTrue(beschriftung, f"{schluessel} ohne Beschriftung")
            self.assertIn(typ, ("int", "text", "bool", "liste", "datei",
                                "ordner", "port", "drucker"))
            self.assertIn(schluessel, STANDARD)

    def test_keine_doppelten_schluessel(self):
        schluessel = [f[0] for f in FELDER]
        self.assertEqual(len(schluessel), len(set(schluessel)))

    def test_zugriff_ueber_attribute(self):
        einst = Einstellungen(datei=None)
        self.assertEqual(einst.strafzeit_pylone, 2)
        einst.strafzeit_pylone = 5
        self.assertEqual(einst.strafzeit_pylone, 5)

    def test_unbekanntes_attribut_meldet_sich(self):
        einst = Einstellungen(datei=None)
        with self.assertRaises(AttributeError):
            _ = einst.gibtesnicht


class Umwandlung(unittest.TestCase):

    def test_text_wird_zu_zahl(self):
        einst = Einstellungen(datei=None)
        einst.strafzeit_pylone = "7"
        self.assertEqual(einst.strafzeit_pylone, 7)

    def test_unsinn_faellt_auf_den_standard(self):
        einst = Einstellungen(datei=None)
        einst.strafzeit_pylone = "abc"
        self.assertEqual(einst.strafzeit_pylone, STANDARD["strafzeit_pylone"])

    def test_ja_nein_in_vielen_schreibweisen(self):
        einst = Einstellungen(datei=None)
        for wahr in ("ja", "Ja", "true", "1", True):
            einst.livetiming = wahr
            self.assertTrue(einst.livetiming, wahr)
        for falsch in ("nein", "false", "0", False, ""):
            einst.livetiming = falsch
            self.assertFalse(einst.livetiming, falsch)


class Pruefung(unittest.TestCase):

    def test_hoechstens_zwei_wertungslaeufe(self):
        einst = Einstellungen(datei=None, werte={"we_anzahl_laeufe": 5}).pruefen()
        self.assertEqual(einst.we_anzahl_laeufe, 2)

    def test_keine_negativen_werte(self):
        einst = Einstellungen(datei=None,
                              werte={"strafzeit_pylone": -3,
                                     "sperrzeit_sekunden": -1}).pruefen()
        self.assertEqual(einst.strafzeit_pylone, 0)
        self.assertEqual(einst.sperrzeit_sekunden, 0)

    def test_warnung_nicht_groesser_als_rundenzahl(self):
        einst = Einstellungen(datei=None,
                              werte={"tr_max_runden": 3,
                                     "tr_warnung_runden": 10}).pruefen()
        self.assertEqual(einst.tr_warnung_runden, 3)

    def test_mindestens_eine_runde(self):
        einst = Einstellungen(datei=None,
                              werte={"we_runden_pro_lauf": 0}).pruefen()
        self.assertEqual(einst.we_runden_pro_lauf, 1)


class Listen(unittest.TestCase):

    def test_klassen_und_vereine_zerlegen(self):
        einst = Einstellungen(datei=None,
                              werte={"klassen": "1a; 1b ;2;",
                                     "vereine": "AC Singen;MCH Singen"})
        self.assertEqual(einst.klassen_liste(), ["1a", "1b", "2"])
        self.assertEqual(einst.vereine_liste(), ["AC Singen", "MCH Singen"])


class LadenUndSpeichern(unittest.TestCase):

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zeitmessung-einst-")
        self.datei = os.path.join(self.ordner, "einstellungen.json")

    def tearDown(self):
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_hin_und_zurueck(self):
        einst = Einstellungen(self.datei)
        einst.serieller_port = "COM6"
        einst.klassen = "1a;2;3"
        einst.livetiming = True
        einst.speichern()

        wieder = Einstellungen.laden(self.datei)
        self.assertEqual(wieder.serieller_port, "COM6")
        self.assertEqual(wieder.klassen, "1a;2;3")
        self.assertTrue(wieder.livetiming)

    def test_fehlende_datei_gibt_standardwerte(self):
        einst = Einstellungen.laden(os.path.join(self.ordner, "gibtesnicht.json"))
        self.assertEqual(einst.strafzeit_pylone, STANDARD["strafzeit_pylone"])

    def test_kaputte_datei_blockiert_nicht(self):
        with open(self.datei, "w", encoding="utf-8") as f:
            f.write("{kein gueltiges json")
        einst = Einstellungen.laden(self.datei)
        self.assertEqual(einst.strafzeit_pylone, STANDARD["strafzeit_pylone"])

    def test_einzelner_unsinniger_wert_kippt_nicht_alles(self):
        with open(self.datei, "w", encoding="utf-8") as f:
            json.dump({"strafzeit_pylone": "viel", "serieller_port": "COM6"}, f)
        einst = Einstellungen.laden(self.datei)
        self.assertEqual(einst.strafzeit_pylone, STANDARD["strafzeit_pylone"])
        self.assertEqual(einst.serieller_port, "COM6")

    def test_unbekannte_felder_werden_ignoriert(self):
        with open(self.datei, "w", encoding="utf-8") as f:
            json.dump({"altes_feld": 1, "serieller_port": "COM3"}, f)
        einst = Einstellungen.laden(self.datei)
        self.assertEqual(einst.serieller_port, "COM3")

    def test_zuruecksetzen_speichert_nicht_von_selbst(self):
        """Der Fehler des alten Programms: der Abbruch-Knopf hat die
        Werkseinstellungen sofort geschrieben."""
        einst = Einstellungen(self.datei)
        einst.serieller_port = "COM6"
        einst.speichern()
        einst.auf_standard()
        self.assertEqual(einst.serieller_port, STANDARD["serieller_port"])

        wieder = Einstellungen.laden(self.datei)
        self.assertEqual(wieder.serieller_port, "COM6",
                         "in der Datei muss der alte Wert stehen")


class LiveTimingSchalter(unittest.TestCase):

    def test_aus_wenn_hauptschalter_aus(self):
        einst = Einstellungen(datei=None, werte={"livetiming": False,
                                                 "livedata_datei": "C:/x.json"})
        self.assertFalse(einst.livetiming_an())

    def test_an_wenn_schalter_und_pfad_stimmen(self):
        einst = Einstellungen(datei=None, werte={"livetiming": True,
                                                 "livedata_datei": "C:/x.json"})
        self.assertTrue(einst.livetiming_an())

    def test_veroeffentlichen_braucht_alles(self):
        werte = {"livetiming": True, "livedata_datei": "C:/x.json",
                 "veroeffentlichen": True, "arbeits_repo": "",
                 "live_repo": "C:/live"}
        self.assertFalse(Einstellungen(datei=None, werte=werte).veroeffentlichen_an())
        werte["arbeits_repo"] = "C:/arbeit"
        self.assertTrue(Einstellungen(datei=None, werte=werte).veroeffentlichen_an())

    def test_umgebungsvariable_zerlegen(self):
        einst = Einstellungen(datei=None,
                              werte={"push_umgebung": "MCH_ERGEBNIS_PUSH=1"})
        self.assertEqual(einst.push_umgebung_paar(), ("MCH_ERGEBNIS_PUSH", "1"))
        einst.push_umgebung = ""
        self.assertIsNone(einst.push_umgebung_paar())


if __name__ == "__main__":
    unittest.main()
