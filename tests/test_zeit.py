# -*- coding: utf-8 -*-
"""Zeitarithmetik - hier entscheidet sich, ob die Zeiten konsistent sind."""
import unittest

from zeitmessung import zeit


class FormatierenUndLesen(unittest.TestCase):

    def test_formatiert_immer_zweistellig(self):
        self.assertEqual(zeit.formatiere(0), "00:00,00")
        self.assertEqual(zeit.formatiere(1), "00:00,01")
        self.assertEqual(zeit.formatiere(100), "00:01,00")
        self.assertEqual(zeit.formatiere(6000), "01:00,00")
        self.assertEqual(zeit.formatiere(3661), "00:36,61")

    def test_ueber_eine_stunde(self):
        # Das alte Programm hat ab 60 Minuten abgebrochen; hier wird
        # einfach weitergezählt.
        self.assertEqual(zeit.formatiere(60 * 6000), "60:00,00")
        self.assertEqual(zeit.formatiere(125 * 6000 + 4207), "125:42,07")

    def test_kein_hundertstel_wird_dreistellig(self):
        """Der Fehler des alten Programms: durch Runden von 999 ms entstand
        "00:05,100" - eine Zeit, die sich nicht mehr lesen lässt."""
        for millisekunden in range(0, 1000):
            text = zeit.formatiere(zeit.aus_sekunden(5 + millisekunden / 1000))
            self.assertRegex(text, r"^\d{2}:\d{2},\d{2}$",
                             f"kaputte Zeit bei {millisekunden} ms: {text}")

    def test_lesen(self):
        self.assertEqual(zeit.parse("00:36,61"), 3661)
        self.assertEqual(zeit.parse("01:05,55"), 6555)
        self.assertEqual(zeit.parse("125:42,07"), 125 * 6000 + 4207)

    def test_lesen_einstelliges_hundertstel_ist_zehntel(self):
        self.assertEqual(zeit.parse("00:01,5"), 150)

    def test_unlesbares_gibt_none(self):
        for text in ("", "ADW", "abc", None, "00:61,00", "1:2:3"):
            self.assertIsNone(zeit.parse(text), f"„{text}“ sollte None geben")

    def test_hin_und_zurueck(self):
        for hundertstel in (0, 7, 99, 100, 5999, 6000, 123456):
            self.assertEqual(zeit.parse(zeit.formatiere(hundertstel)), hundertstel)


class Rechnen(unittest.TestCase):

    def test_addieren_mit_uebertrag(self):
        # 00:59,99 + 00:00,01 = 01:00,00
        self.assertEqual(zeit.formatiere(zeit.addiere("00:59,99", "00:00,01")),
                         "01:00,00")

    def test_addieren_gemischt(self):
        self.assertEqual(zeit.addiere("00:10,50", 1050), 2100)

    def test_addieren_ignoriert_unlesbares(self):
        self.assertEqual(zeit.addiere("00:10,00", "ADW", ""), 1000)

    def test_summe_ist_unabhaengig_von_der_reihenfolge(self):
        werte = ["00:41,03", "00:17,81", "00:26,21"]
        for reihenfolge in ([0, 1, 2], [2, 0, 1], [1, 2, 0]):
            self.assertEqual(zeit.addiere(*[werte[i] for i in reihenfolge]),
                             zeit.addiere(*werte))


class AusSekunden(unittest.TestCase):

    def test_schneidet_ab_statt_zu_runden(self):
        """Eine Stoppuhr darf keine Zeit anzeigen, die größer ist als die
        tatsächlich gefahrene."""
        self.assertEqual(zeit.aus_sekunden(36.619), 3661)
        self.assertEqual(zeit.aus_sekunden(36.611), 3661)
        self.assertEqual(zeit.aus_sekunden(0.999), 99)

    def test_negatives_und_null(self):
        self.assertEqual(zeit.aus_sekunden(0), 0)
        self.assertEqual(zeit.aus_sekunden(-3), 0)

    def test_monoton(self):
        """Mehr Sekunden dürfen nie weniger Hundertstel ergeben."""
        vorher = -1
        for schritt in range(0, 2000):
            wert = zeit.aus_sekunden(schritt / 100.0)
            self.assertGreaterEqual(wert, vorher)
            vorher = wert

    def test_rechenungenauigkeit_kostet_kein_hundertstel(self):
        """Zwei Uhrwerte voneinander abgezogen ergeben nicht exakt 41,03,
        sondern 41,029999999999994. Ohne Ausgleich würde daraus 41,02."""
        start = 1000.0
        ende = start + 20.0 + 21.03
        self.assertEqual(zeit.formatiere(zeit.aus_sekunden(ende - start)),
                         "00:41,03")

    def test_viele_zusammengesetzte_zeiten_stimmen(self):
        """Der Rundgang über alle Hundertstel einer Minute - jede Zeit muss
        genau so herauskommen, wie sie hineingegeben wurde."""
        start = 12345.6789
        for hundertstel in range(0, 6000):
            ende = start + hundertstel / 100.0
            self.assertEqual(zeit.aus_sekunden(ende - start), hundertstel,
                             f"bei {hundertstel} Hundertsteln")


class Strafzeit(unittest.TestCase):

    def test_rechnung_wie_im_original(self):
        # 3 Pylonen a 2 s + 1 Fehler a 10 s = 16 s
        self.assertEqual(zeit.strafzeit(3, 1, 2, 10), 16)

    def test_ohne_alles_null(self):
        self.assertEqual(zeit.strafzeit(0, 0, 2, 10), 0)

    def test_in_hundertstel(self):
        self.assertEqual(zeit.sekunden_in_hundertstel(16), 1600)


if __name__ == "__main__":
    unittest.main()
