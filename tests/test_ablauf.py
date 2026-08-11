# -*- coding: utf-8 -*-
"""
Der komplette Rennablauf - ohne Fenster, mit einer gestellten Uhr.

Genau das war am alten Programm nicht prüfbar: die Logik steckte zwischen
Knopf-Ereignissen und Formularfeldern.
"""
import unittest

from zeitmessung import zeit
from zeitmessung.ablauf import EINFUEHRUNG, TRAINING, WERTUNG, Ablauf
from zeitmessung.einstellungen import Einstellungen


class Uhr:
    """Eine Uhr, die nur auf Kommando weiterläuft."""

    def __init__(self, start=1000.0):
        self.jetzt = float(start)

    def __call__(self):
        return self.jetzt

    def vor(self, sekunden):
        self.jetzt += sekunden
        return self.jetzt


def _einstellungen(**abweichungen):
    werte = {"we_einfuehrungsrunden": 1, "we_runden_pro_lauf": 2,
             "we_anzahl_laeufe": 2, "tr_max_runden": 3, "tr_max_zeit": 5,
             "tr_warnung_runden": 1, "sperrzeit_sekunden": 0,
             "strafzeit_pylone": 2, "strafzeit_fehler": 10,
             "starter_eingabe": True, "starter_bei_einfuehrung": False}
    werte.update(abweichungen)
    return Einstellungen(datei=None, werte=werte).pruefen()


def _arten(ereignisse):
    return [e.art for e in ereignisse]


def _erstes(ereignisse, art):
    for ereignis in ereignisse:
        if ereignis.art == art:
            return ereignis
    return None


class TrainingLauf(unittest.TestCase):

    def setUp(self):
        self.uhr = Uhr()
        self.ablauf = Ablauf(_einstellungen(), uhr=self.uhr)
        self.ablauf.modus_setzen(TRAINING)

    def test_start_und_runden(self):
        ereignisse = self.ablauf.ausloesen()
        self.assertIn("start", _arten(ereignisse))
        self.assertTrue(self.ablauf.laeuft)

        self.uhr.vor(42.5)
        ereignisse = self.ablauf.ausloesen()
        runde = _erstes(ereignisse, "runde")
        self.assertEqual(runde["nummer"], 1)
        self.assertEqual(zeit.formatiere(runde["zeit"]), "00:42,50")
        self.assertTrue(self.ablauf.laeuft, "nach Runde 1 läuft es weiter")

    def test_jede_runde_wird_einzeln_gemessen(self):
        """Im Training zeigt die Uhr die Zeit der einzelnen Runde, nicht die
        Gesamtzeit - deshalb fängt sie nach jeder Runde neu an."""
        self.ablauf.ausloesen()
        self.uhr.vor(40.0)
        erste = _erstes(self.ablauf.ausloesen(), "runde")["zeit"]
        self.uhr.vor(30.0)
        zweite = _erstes(self.ablauf.ausloesen(), "runde")["zeit"]
        self.assertEqual(zeit.formatiere(erste), "00:40,00")
        self.assertEqual(zeit.formatiere(zweite), "00:30,00")

    def test_endet_nach_der_letzten_runde(self):
        self.ablauf.ausloesen()
        for _ in range(3):                       # tr_max_runden = 3
            self.uhr.vor(10)
            ereignisse = self.ablauf.ausloesen()
        self.assertIn("ende_training", _arten(ereignisse))
        self.assertFalse(self.ablauf.laeuft)

    def test_warnton_vor_dem_ende(self):
        self.ablauf.ausloesen()
        self.uhr.vor(10)
        self.assertNotIn("warnton", _arten(self.ablauf.ausloesen()))
        self.uhr.vor(10)                          # jetzt bleibt 1 Runde
        self.assertIn("warnton", _arten(self.ablauf.ausloesen()))

    def test_zeitlimit_beendet_das_training(self):
        ablauf = Ablauf(_einstellungen(tr_max_runden=99, tr_max_zeit=2),
                        uhr=self.uhr)
        ablauf.modus_setzen(TRAINING)
        ablauf.ausloesen()
        self.uhr.vor(121)                         # über 2 Minuten
        ereignisse = ablauf.ausloesen()
        self.assertIn("ende_training", _arten(ereignisse))

    def test_restzeit_zaehlt_herunter_und_bleibt_bei_null(self):
        ablauf = Ablauf(_einstellungen(tr_max_zeit=2), uhr=self.uhr)
        ablauf.modus_setzen(TRAINING)
        ablauf.ausloesen()
        self.assertEqual(ablauf.training_restzeit_minuten(), 2)
        self.uhr.vor(65)
        self.assertEqual(ablauf.training_restzeit_minuten(), 1)
        self.uhr.vor(600)
        self.assertEqual(ablauf.training_restzeit_minuten(), 0)


class Wertungslauf(unittest.TestCase):

    def setUp(self):
        self.uhr = Uhr()
        self.ablauf = Ablauf(_einstellungen(), uhr=self.uhr)

    def test_wertung_direkt_gewaehlt_ueberspringt_die_einfuehrung(self):
        ereignisse = self.ablauf.modus_setzen(WERTUNG)
        self.assertIn("starter_erfassen", _arten(ereignisse))
        ereignisse = self.ablauf.ausloesen()
        self.assertIn("start", _arten(ereignisse))
        self.assertEqual(self.ablauf.lauf_nummer, 1)

    def test_zeit_laeuft_ueber_alle_runden_durch(self):
        """Anders als im Training ist die Fahrzeit eines Wertungslaufs die
        Zeit über alle Runden zusammen."""
        self.ablauf.modus_setzen(WERTUNG)
        self.ablauf.ausloesen()
        self.uhr.vor(20.0)
        erste = _erstes(self.ablauf.ausloesen(), "runde")["zeit"]
        self.uhr.vor(21.03)
        ereignisse = self.ablauf.ausloesen()
        zweite = _erstes(ereignisse, "runde")["zeit"]
        self.assertEqual(zeit.formatiere(erste), "00:20,00")
        self.assertEqual(zeit.formatiere(zweite), "00:41,03")
        self.assertEqual(zeit.formatiere(_erstes(ereignisse, "ende_lauf")["zeit"]),
                         "00:41,03")

    def test_nach_lauf1_kommt_die_eingabe_dann_lauf2(self):
        self.ablauf.modus_setzen(WERTUNG)
        self.ablauf.ausloesen()
        for _ in range(2):
            self.uhr.vor(20)
            ereignisse = self.ablauf.ausloesen()
        erfassen = _erstes(ereignisse, "starter_erfassen")
        self.assertEqual(erfassen["anlass"], "lauf_ende")
        self.assertFalse(self.ablauf.laeuft)

        ereignisse = self.ablauf.ausloesen()
        self.assertIn("start", _arten(ereignisse))
        self.assertEqual(self.ablauf.lauf_nummer, 2)

    def test_nach_dem_letzten_lauf_kommt_das_ende(self):
        self.ablauf.modus_setzen(WERTUNG)
        for lauf in (1, 2):
            self.ablauf.ausloesen()
            for _ in range(2):
                self.uhr.vor(20)
                ereignisse = self.ablauf.ausloesen()
        erfassen = _erstes(ereignisse, "starter_erfassen")
        self.assertEqual(erfassen["anlass"], "wertung_ende")
        self.assertEqual(self.ablauf.zeiten, {1: 4000, 2: 4000})

    def test_nur_ein_wertungslauf(self):
        ablauf = Ablauf(_einstellungen(we_anzahl_laeufe=1), uhr=self.uhr)
        ablauf.modus_setzen(WERTUNG)
        ablauf.ausloesen()
        for _ in range(2):
            self.uhr.vor(20)
            ereignisse = ablauf.ausloesen()
        self.assertEqual(_erstes(ereignisse, "starter_erfassen")["anlass"],
                         "wertung_ende")


class Einfuehrungsrunde(unittest.TestCase):

    def setUp(self):
        self.uhr = Uhr()

    def test_eine_einfuehrungsrunde_schaltet_auf_wertung(self):
        ablauf = Ablauf(_einstellungen(we_einfuehrungsrunden=1), uhr=self.uhr)
        ablauf.modus_setzen(EINFUEHRUNG)
        ereignisse = ablauf.ausloesen()
        self.assertIn("wechsel_wertung", _arten(ereignisse))
        self.assertEqual(ablauf.modus, WERTUNG)
        self.assertFalse(ablauf.laeuft, "die Einführungsrunde wird nicht gemessen")

        ereignisse = ablauf.ausloesen()
        self.assertIn("start", _arten(ereignisse))
        self.assertEqual(ablauf.lauf_nummer, 1)

    def test_zwei_einfuehrungsrunden(self):
        ablauf = Ablauf(_einstellungen(we_einfuehrungsrunden=2), uhr=self.uhr)
        ablauf.modus_setzen(EINFUEHRUNG)
        erste = ablauf.ausloesen()
        self.assertEqual(_arten(erste), ["protokoll"])
        self.assertNotIn("wechsel_wertung", _arten(erste))
        zweite = ablauf.ausloesen()
        self.assertIn("wechsel_wertung", _arten(zweite))
        dritte = ablauf.ausloesen()
        self.assertIn("start", _arten(dritte))

    def test_ohne_einfuehrungsrunde_startet_der_erste_ausloeser_die_wertung(self):
        ablauf = Ablauf(_einstellungen(we_einfuehrungsrunden=0), uhr=self.uhr)
        ablauf.modus_setzen(EINFUEHRUNG)
        self.assertIn("start", _arten(ablauf.ausloesen()))


class SperrzeitUndAbbruch(unittest.TestCase):

    def setUp(self):
        self.uhr = Uhr()
        self.ablauf = Ablauf(_einstellungen(sperrzeit_sekunden=3), uhr=self.uhr)
        self.ablauf.modus_setzen(TRAINING)

    def test_zweites_signal_innerhalb_der_sperrzeit_wird_verworfen(self):
        self.ablauf.ausloesen()
        self.uhr.vor(1.0)
        ereignisse = self.ablauf.ausloesen()
        self.assertEqual(_arten(ereignisse), ["gesperrt"])
        self.assertEqual(self.ablauf.runden, 0, "die Runde darf nicht zählen")

    def test_nach_der_sperrzeit_zaehlt_es_wieder(self):
        self.ablauf.ausloesen()
        self.uhr.vor(3.5)
        self.assertIn("runde", _arten(self.ablauf.ausloesen()))

    def test_sperrzeit_verschiebt_die_gemessene_zeit_nicht(self):
        """Ein verworfenes Signal darf die Uhr nicht anfassen."""
        self.ablauf.ausloesen()
        self.uhr.vor(1.0)
        self.ablauf.ausloesen()          # gesperrt
        self.uhr.vor(39.0)               # zusammen 40,0 s seit dem Start
        runde = _erstes(self.ablauf.ausloesen(), "runde")
        self.assertEqual(zeit.formatiere(runde["zeit"]), "00:40,00")

    def test_abbruch_stoppt_und_meldet(self):
        self.ablauf.ausloesen()
        ereignisse = self.ablauf.abbrechen()
        self.assertEqual(_arten(ereignisse), ["abbruch"])
        self.assertIn("Abbruch Training", ereignisse[0]["text"])
        self.assertFalse(self.ablauf.laeuft)

    def test_abbruch_im_wertungslauf_gibt_den_lauf_wieder_frei(self):
        ablauf = Ablauf(_einstellungen(), uhr=self.uhr)
        ablauf.modus_setzen(WERTUNG)
        ablauf.ausloesen()
        self.assertEqual(ablauf.lauf_nummer, 1)
        ablauf.abbrechen()
        self.assertEqual(ablauf.lauf_nummer, 0)
        ablauf.ausloesen()
        self.assertEqual(ablauf.lauf_nummer, 1, "der Lauf wird neu gefahren")


class Wiederholen(unittest.TestCase):

    def test_wiederholter_lauf_wird_neu_gefahren(self):
        uhr = Uhr()
        ablauf = Ablauf(_einstellungen(), uhr=uhr)
        ablauf.modus_setzen(WERTUNG)
        ablauf.ausloesen()
        for _ in range(2):
            uhr.vor(20)
            ablauf.ausloesen()
        self.assertEqual(set(ablauf.zeiten), {1})

        ablauf.lauf_wiederholen(1)
        self.assertEqual(ablauf.zeiten, {})
        self.assertEqual(ablauf.lauf_nummer, 0)
        ablauf.ausloesen()
        self.assertEqual(ablauf.lauf_nummer, 1)


class UhrUndUmschalten(unittest.TestCase):

    def test_aktuelle_zeit_haengt_nicht_am_anzeigetakt(self):
        """Die Zeit wird im Moment des Auslösens berechnet, nicht beim
        nächsten Bildschirmtakt - das alte Programm hat den Wert eines
        10-ms-Zeitgebers benutzt."""
        uhr = Uhr()
        ablauf = Ablauf(_einstellungen(), uhr=uhr)
        ablauf.modus_setzen(TRAINING)
        ablauf.ausloesen()
        uhr.vor(12.34)
        self.assertEqual(zeit.formatiere(ablauf.aktuelle_zeit()), "00:12,34")

    def test_umschalten_waehrend_der_messung_ist_gesperrt(self):
        uhr = Uhr()
        ablauf = Ablauf(_einstellungen(), uhr=uhr)
        ablauf.modus_setzen(TRAINING)
        ablauf.ausloesen()
        self.assertEqual(ablauf.modus_setzen(WERTUNG), [])
        self.assertEqual(ablauf.modus, TRAINING)

    def test_knopfbeschriftung_folgt_dem_zustand(self):
        uhr = Uhr()
        ablauf = Ablauf(_einstellungen(we_runden_pro_lauf=2), uhr=uhr)
        ablauf.modus_setzen(TRAINING)
        self.assertEqual(ablauf.knopfbeschriftung(), "Start Training (F1)")
        ablauf.ausloesen()
        self.assertEqual(ablauf.knopfbeschriftung(), "Rundenzeit (F1)")

        ablauf2 = Ablauf(_einstellungen(), uhr=Uhr())
        ablauf2.modus_setzen(WERTUNG)
        self.assertEqual(ablauf2.knopfbeschriftung(), "Start Wertung (F1)")
        ablauf2.ausloesen()
        self.assertEqual(ablauf2.knopfbeschriftung(), "Zwischenzeit (F1)")


if __name__ == "__main__":
    unittest.main()
