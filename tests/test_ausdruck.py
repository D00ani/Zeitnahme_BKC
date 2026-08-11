# -*- coding: utf-8 -*-
"""
Der Ausdruck.

Geprüft wird der Bauplan - also welcher Text an welcher Millimeterposition
steht. Die Sollwerte stammen direkt aus dem alten ``frmStarter.PrintPage``,
damit die Karte hinterher genauso aussieht wie bisher.
"""
import os
import unittest

from zeitmessung import zeit
from zeitmessung.ausdruck import (KARTEN_ABSTAND, KARTEN_BREITE, SCHRIFT_FETT,
                                  SCHRIFT_NORMAL, SCHRIFT_ZEIT, als_text,
                                  bauplan)
from zeitmessung.wertung import Starterergebnis


def _ergebnis():
    e = Starterergebnis(startnummer="7", name="Anton Muster", klasse="3",
                        verein="AC Singen", sek_pylone=2, sek_fehler=10)
    e.zeit_setzen(1, zeit.parse("00:41,03"))
    e.zeit_setzen(2, zeit.parse("00:17,81"))
    e.lauf(1).pylonen = 3
    e.lauf(2).fehler = 1
    return e


class Layout(unittest.TestCase):

    def setUp(self):
        self.anweisungen = bauplan(_ergebnis(), linker_rand=10, oberer_rand=10,
                                   unterer_abstand=20, karten=2)
        self.texte = [a for a in self.anweisungen if a[0] == "text"]
        self.linien = [a for a in self.anweisungen if a[0] == "linie"]

    def _text_bei(self, x, y):
        return [a[4] for a in self.texte if a[1] == x and a[2] == y]

    def test_zwei_karten_nebeneinander(self):
        """Auf ein Blatt kommen zwei gleiche Karten - eine für den Fahrer,
        eine für die Auswertung."""
        self.assertEqual(len(self.linien), 4)          # 2 Linien je Karte
        klassen = [a for a in self.texte if str(a[4]).startswith("Klasse ")]
        self.assertEqual(len(klassen), 2)
        self.assertEqual(klassen[0][1], 10)
        self.assertEqual(klassen[1][1], 10 + KARTEN_BREITE + KARTEN_ABSTAND)

    def test_kopf_der_ersten_karte(self):
        # Gesamt = (41,03 + 3 Pylonen a 2 s) + (17,81 + 1 Fehler a 10 s)
        #        =  47,03                    +  27,81               = 74,84
        self.assertEqual(self._text_bei(10, 10), ["Klasse 3"])
        self.assertEqual(self._text_bei(50, 10), ["01:14,84"])   # x1 = x + 40
        self.assertEqual(self._text_bei(10, 16), ["Anton Muster (7)"])

    def test_schriften_wie_im_original(self):
        klasse = next(a for a in self.texte if a[4] == "Klasse 3")
        gesamt = next(a for a in self.texte if a[1] == 50 and a[2] == 10)
        name = next(a for a in self.texte if a[4] == "Anton Muster (7)")
        self.assertEqual(klasse[3], SCHRIFT_NORMAL)      # Verdana 9
        self.assertEqual(gesamt[3], SCHRIFT_ZEIT)        # Verdana 14 fett
        self.assertEqual(name[3], SCHRIFT_FETT)          # Verdana 9 fett

    def test_tabellenkopf(self):
        # t0=10, t1=20, t2=36, t3=48, t4=63 bei y0 = 10 + 13
        erwartet = {10: "Lauf", 20: "Fahrzeit", 36: "Pyl/Fal",
                    48: "Strafzeit", 63: "Gesamt"}
        for x, text in erwartet.items():
            self.assertEqual(self._text_bei(x, 23), [text],
                             f"Spalte bei x={x}")

    def test_zeilen_der_beiden_laeufe(self):
        # 1. Lauf auf y1 = 28, 2. Lauf auf y2 = 32
        self.assertEqual(self._text_bei(12, 28), ["1"])       # t0 + 2
        self.assertEqual(self._text_bei(20, 28), ["00:41,03"])  # t1
        self.assertEqual(self._text_bei(39, 28), ["3/0"])     # t2 + 3
        self.assertEqual(self._text_bei(51, 28), ["6"])       # t3 + 3
        self.assertEqual(self._text_bei(60, 28), ["00:47,03"])  # t4 - 3

        self.assertEqual(self._text_bei(12, 32), ["2"])
        self.assertEqual(self._text_bei(20, 32), ["00:17,81"])
        self.assertEqual(self._text_bei(39, 32), ["0/1"])
        self.assertEqual(self._text_bei(51, 32), ["10"])
        self.assertEqual(self._text_bei(60, 32), ["00:27,81"])

    def test_linien(self):
        # obere Linie bei y + 12, untere bei y2 + unterer_abstand
        erste, zweite = self.linien[0], self.linien[1]
        self.assertEqual(erste[1:5], (10, 22, 10 + KARTEN_BREITE - 3, 22))
        self.assertEqual(zweite[1:5], (10, 52, 10 + KARTEN_BREITE - 3, 52))
        self.assertEqual(erste[5], 0.5)
        self.assertEqual(zweite[5], 0.1)

    def test_raender_verschieben_alles(self):
        anweisungen = bauplan(_ergebnis(), linker_rand=20, oberer_rand=15,
                              unterer_abstand=30, karten=1)
        klasse = next(a for a in anweisungen if a[4] == "Klasse 3")
        self.assertEqual((klasse[1], klasse[2]), (20, 15))
        linie = [a for a in anweisungen if a[0] == "linie"][-1]
        self.assertEqual(linie[2], 15 + 22 + 30)

    def test_eine_karte_auf_wunsch(self):
        anweisungen = bauplan(_ergebnis(), karten=1)
        klassen = [a for a in anweisungen if str(a[4]).startswith("Klasse ")]
        self.assertEqual(len(klassen), 1)


class VorschauStattDruck(unittest.TestCase):
    """Der Übungsbetrieb: es wird kein Papier bedruckt, sondern eine PDF
    über denselben Zeichenweg erzeugt."""

    def _einstellungen(self, **abweichungen):
        from zeitmessung.einstellungen import Einstellungen
        werte = {"pr_linker_rand": 10, "pr_oberer_rand": 10,
                 "pr_unterer_abstand": 20, "drucker": "Mein Drucker"}
        werte.update(abweichungen)
        return Einstellungen(datei=None, werte=werte)

    def test_normalfall_geht_auf_den_eingestellten_drucker(self):
        from zeitmessung.ausdruck import ziel_bestimmen
        name, datei = ziel_bestimmen(
            self._einstellungen(vorschau_statt_druck=False), _ergebnis())
        self.assertEqual(name, "Mein Drucker")
        self.assertIsNone(datei, "es darf keine Datei erzeugt werden")

    def test_leeres_feld_nimmt_den_standarddrucker(self):
        from zeitmessung.ausdruck import standarddrucker, ziel_bestimmen
        name, _ = ziel_bestimmen(
            self._einstellungen(drucker="", vorschau_statt_druck=False),
            _ergebnis())
        self.assertEqual(name, standarddrucker())

    def test_leerzeichen_zaehlen_als_leer(self):
        from zeitmessung.ausdruck import standarddrucker, ziel_bestimmen
        name, _ = ziel_bestimmen(
            self._einstellungen(drucker="   ", vorschau_statt_druck=False),
            _ergebnis())
        self.assertEqual(name, standarddrucker())


    def test_vorschau_geht_in_eine_pdf(self):
        from zeitmessung.ausdruck import PDF_DRUCKER, ziel_bestimmen
        name, datei = ziel_bestimmen(
            self._einstellungen(vorschau_statt_druck=True), _ergebnis())
        self.assertEqual(name, PDF_DRUCKER)
        self.assertTrue(datei.endswith(".pdf"))
        self.assertIn("vorschau", datei.lower())
        self.assertIn("_7_", datei, "die Startnummer gehört in den Dateinamen")

    def test_eigener_vorschauordner(self):
        from zeitmessung.ausdruck import ziel_bestimmen
        _, datei = ziel_bestimmen(
            self._einstellungen(vorschau_statt_druck=True,
                                vorschau_ordner=r"C:\Temp\Karten"), _ergebnis())
        self.assertTrue(datei.startswith(r"C:\Temp\Karten"))

    def test_dateiname_ohne_gefaehrliche_zeichen(self):
        from zeitmessung.ausdruck import ziel_bestimmen
        from zeitmessung.wertung import Starterergebnis
        ergebnis = Starterergebnis(startnummer=r"7/A\B", name="X", klasse="3")
        _, datei = ziel_bestimmen(
            self._einstellungen(vorschau_statt_druck=True), ergebnis)
        dateiname = os.path.basename(datei)
        for zeichen in "/\\:*?\"<>|":
            self.assertNotIn(zeichen, dateiname)

    def test_layout_ist_in_beiden_faellen_gleich(self):
        """Die Vorschau muss dasselbe zeigen wie der spätere Ausdruck."""
        mit = bauplan(_ergebnis(), linker_rand=10, oberer_rand=10,
                      unterer_abstand=20)
        ohne = bauplan(_ergebnis(), linker_rand=10, oberer_rand=10,
                       unterer_abstand=20)
        self.assertEqual(mit, ohne)


class Druckerliste(unittest.TestCase):
    """Die Auswahlliste im Einstellungsfenster speist sich hieraus."""

    def test_liste_und_standard_passen_zusammen(self):
        from zeitmessung.ausdruck import drucker_liste, standarddrucker
        drucker = drucker_liste()
        if not drucker:
            self.skipTest("Auf diesem Rechner ist kein Drucker eingerichtet.")
        self.assertTrue(all(isinstance(d, str) and d for d in drucker))
        standard = standarddrucker()
        if standard:
            self.assertIn(standard, drucker,
                          "der Standarddrucker muss in der Liste stehen")

    def test_pdf_drucker_ist_fuer_die_vorschau_da(self):
        from zeitmessung.ausdruck import PDF_DRUCKER, drucker_liste
        drucker = drucker_liste()
        if not drucker:
            self.skipTest("Auf diesem Rechner ist kein Drucker eingerichtet.")
        self.assertIn(PDF_DRUCKER, drucker,
                      "ohne diesen Windows-Drucker gibt es keine PDF-Vorschau")


class Textfassung(unittest.TestCase):

    def test_enthaelt_alle_werte(self):
        text = als_text(_ergebnis())
        for erwartet in ("Klasse 3", "Anton Muster (7)", "00:41,03",
                         "00:17,81", "01:14,84"):
            self.assertIn(erwartet, text)


if __name__ == "__main__":
    unittest.main()
