# -*- coding: utf-8 -*-
"""Strafzeiten, Summen und Platzierung."""
import unittest

from zeitmessung import zeit
from zeitmessung.wertung import (Lauf, Starterergebnis, platz_von,
                                 platzierungstext, rangliste)


def _ergebnis(**felder):
    grund = dict(startnummer="7", name="Testfahrer", klasse="3",
                 verein="AC Singen", sek_pylone=2, sek_fehler=10)
    grund.update(felder)
    return Starterergebnis(**grund)


class Strafzeiten(unittest.TestCase):

    def test_summe_eines_laufs(self):
        e = _ergebnis()
        e.zeit_setzen(1, zeit.parse("00:41,03"))
        e.lauf(1).pylonen = 3        # 6 s
        e.lauf(1).fehler = 1         # 10 s
        self.assertEqual(e.strafzeit_sekunden(1), 16)
        self.assertEqual(zeit.formatiere(e.summe(1)), "00:57,03")

    def test_ohne_strafe_ist_summe_gleich_fahrzeit(self):
        e = _ergebnis()
        e.zeit_setzen(1, zeit.parse("00:41,03"))
        self.assertEqual(e.summe(1), e.lauf(1).fahrzeit)

    def test_gesamt_ist_summe_beider_laeufe(self):
        e = _ergebnis()
        e.zeit_setzen(1, zeit.parse("00:41,03"))
        e.zeit_setzen(2, zeit.parse("00:17,81"))
        e.lauf(1).pylonen = 1        # 2 s
        e.lauf(2).fehler = 2         # 20 s
        self.assertEqual(e.strafzeit_gesamt_sekunden(), 22)
        self.assertEqual(zeit.formatiere(e.fahrzeit_gesamt()), "00:58,84")
        self.assertEqual(zeit.formatiere(e.gesamt()), "01:20,84")

    def test_strafzeit_ueber_eine_minute(self):
        """Sechs Fahrfehler sind 60 Strafsekunden - der Übertrag in die
        Minutenspalte muss stimmen."""
        e = _ergebnis()
        e.zeit_setzen(1, zeit.parse("00:30,00"))
        e.lauf(1).fehler = 6
        self.assertEqual(e.strafzeit_sekunden(1), 60)
        self.assertEqual(zeit.formatiere(e.summe(1)), "01:30,00")

    def test_textfassung_fuer_die_datenbank(self):
        e = _ergebnis()
        e.zeit_setzen(1, zeit.parse("00:41,03"))
        e.lauf(1).pylonen = 3
        e.lauf(1).fehler = 1
        werte = e.als_text(1)
        self.assertEqual(werte, {"fahrzeit": "00:41,03", "pylonen": "3",
                                 "adw": "1", "strafzeit": "16",
                                 "gesamtzeit": "00:57,03"})

    def test_gesamtfassung_summiert_pylonen_und_fehler(self):
        e = _ergebnis()
        e.lauf(1).pylonen, e.lauf(1).fehler = 2, 1
        e.lauf(2).pylonen, e.lauf(2).fehler = 3, 0
        werte = e.gesamt_als_text()
        self.assertEqual(werte["pylonen"], "5")
        self.assertEqual(werte["adw"], "1")


class Nachrechnen(unittest.TestCase):
    """Berichtigen eines gespeicherten Datensatzes am Renntag."""

    def test_neue_pylonenzahl_ergibt_neue_gesamtzeit(self):
        from zeitmessung.wertung import nachrechnen
        strafe, gesamt = nachrechnen("00:40,00", 3, 0, 2, 10)
        self.assertEqual(strafe, 6)
        self.assertEqual(gesamt, "00:46,00")

    def test_ohne_strafe_bleibt_die_fahrzeit(self):
        from zeitmessung.wertung import nachrechnen
        strafe, gesamt = nachrechnen("00:40,00", 0, 0, 2, 10)
        self.assertEqual(strafe, 0)
        self.assertEqual(gesamt, "00:40,00")

    def test_uebertrag_in_die_minuten(self):
        from zeitmessung.wertung import nachrechnen
        _, gesamt = nachrechnen("00:40,00", 0, 3, 2, 10)      # 30 s Strafe
        self.assertEqual(gesamt, "01:10,00")

    def test_ohne_verwertbare_fahrzeit_bleibt_der_eintrag_stehen(self):
        from zeitmessung.wertung import nachrechnen
        strafe, gesamt = nachrechnen("ADW", 2, 0, 2, 10)
        self.assertEqual(strafe, 4)
        self.assertEqual(gesamt, "ADW")


class Rangliste(unittest.TestCase):

    def _eintrag(self, nr, gesamt, klasse="3", name=None):
        return {"starternr": nr, "name": name or f"Fahrer {nr}",
                "verein": "AC Singen", "klasse": klasse,
                "gesamtzeit": gesamt, "gesamtzeit_hs": zeit.parse(gesamt)}

    def test_schnellste_zuerst(self):
        eintraege = [self._eintrag("1", "00:50,00"),
                     self._eintrag("2", "00:42,00"),
                     self._eintrag("3", "00:47,00")]
        gereiht = rangliste(eintraege)
        self.assertEqual([e["starternr"] for e in gereiht], ["2", "3", "1"])
        self.assertEqual([e["platz"] for e in gereiht], [1, 2, 3])

    def test_zeitgleiche_teilen_sich_den_platz(self):
        """Im alten Programm bekamen zwei gleich schnelle Fahrer
        verschiedene Plätze."""
        eintraege = [self._eintrag("1", "00:42,00"),
                     self._eintrag("2", "00:42,00"),
                     self._eintrag("3", "00:47,00")]
        gereiht = rangliste(eintraege)
        self.assertEqual([e["platz"] for e in gereiht], [1, 1, 3])

    def test_ohne_zeit_ans_ende(self):
        eintraege = [self._eintrag("1", "ADW"),
                     self._eintrag("2", "00:42,00")]
        gereiht = rangliste(eintraege)
        self.assertEqual([e["starternr"] for e in gereiht], ["2", "1"])

    def test_platz_von(self):
        gereiht = rangliste([self._eintrag("1", "00:50,00"),
                             self._eintrag("2", "00:42,00")])
        self.assertEqual(platz_von(gereiht, "2"), 1)
        self.assertEqual(platz_von(gereiht, "1"), 2)
        self.assertIsNone(platz_von(gereiht, "9"))

    def test_platzierungstext_nennt_klasse_und_gesamt(self):
        alle = [self._eintrag("1", "00:50,00", klasse="3", name="Anton"),
                self._eintrag("2", "00:42,00", klasse="3", name="Berta"),
                self._eintrag("3", "00:40,00", klasse="4", name="Cesar")]
        zeilen = platzierungstext(alle, "1", "Anton", "AC Singen", "3")
        text = "\n".join(zeilen)
        self.assertIn("Platzierung für Anton, StartNr 1", text)
        self.assertIn("Platz 2 von 2 Startern in seiner Klasse 3", text)
        self.assertIn("Platz 3 von 3 Gesamt-Startern", text)
        self.assertIn("Ergebnisse Klasse 3", text)
        self.assertIn("Gesamtplatzierung:", text)


if __name__ == "__main__":
    unittest.main()
