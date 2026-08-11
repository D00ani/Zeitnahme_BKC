# -*- coding: utf-8 -*-
"""
Live-Timing.

Wichtig ist zweierlei: die Datei muss genau die Form haben, die
``js/live.js`` der Webseite erwartet - und der Hauptschalter muss das Ganze
vollständig stilllegen können.
"""
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime

from zeitmessung import livetiming as lt
from zeitmessung.datenbank import LAUF_1, LAUF_GESAMT, Datenbank
from zeitmessung.einstellungen import Einstellungen


def _eintrag(nr, gesamt, klasse="3", laufnr=LAUF_GESAMT, name=None,
             fahrzeit=None, strafzeit="0"):
    from zeitmessung import zeit
    return {"starternr": nr, "name": name or f"Fahrer {nr}",
            "verein": "AC Singen", "klasse": klasse, "laufnr": laufnr,
            "fahrzeit": fahrzeit or gesamt, "strafzeit": strafzeit,
            "gesamtzeit": gesamt, "gesamtzeit_hs": zeit.parse(gesamt)}


class AufbauDerDatei(unittest.TestCase):

    def test_felder_wie_von_der_webseite_erwartet(self):
        daten = lt.baue_livedata([_eintrag("1", "00:42,00")], "2026-08-10",
                                 "Testrennen",
                                 jetzt=datetime(2026, 8, 10, 14, 3, 21))
        for feld in ("last_update", "stand_iso", "datum", "datum_iso",
                     "veranstaltung", "quelle", "results"):
            self.assertIn(feld, daten)
        self.assertEqual(daten["last_update"], "14:03:21")
        self.assertEqual(daten["datum"], "10.08.2026")
        self.assertEqual(daten["datum_iso"], "2026-08-10")
        self.assertEqual(daten["veranstaltung"], "Testrennen")

        ergebnis = daten["results"][0]
        for feld in ("klasse", "lauf", "platz", "startnummer", "name", "club",
                     "zeit_raw", "fehler", "zeit_total", "diff_first",
                     "diff_prev"):
            self.assertIn(feld, ergebnis)

    def test_klasse_bekommt_das_wort_klasse(self):
        daten = lt.baue_livedata([_eintrag("1", "00:42,00", klasse="1a")],
                                 "2026-08-10")
        self.assertEqual(daten["results"][0]["klasse"], "Klasse 1a")

    def test_ohne_klasse(self):
        daten = lt.baue_livedata([_eintrag("1", "00:42,00", klasse="")],
                                 "2026-08-10")
        self.assertEqual(daten["results"][0]["klasse"], "Ohne Klasse")

    def test_laufbezeichnungen(self):
        eintraege = [_eintrag("1", "00:42,00", laufnr=LAUF_1),
                     _eintrag("1", "01:20,00", laufnr=LAUF_GESAMT)]
        daten = lt.baue_livedata(eintraege, "2026-08-10")
        laeufe = {e["lauf"] for e in daten["results"]}
        self.assertEqual(laeufe, {"1. WL", "Gesamt"})

    def test_startnummer_wird_zahl_wenn_moeglich(self):
        daten = lt.baue_livedata([_eintrag("7", "00:42,00"),
                                  _eintrag("A3", "00:43,00")], "2026-08-10")
        nummern = [e["startnummer"] for e in daten["results"]]
        self.assertIn(7, nummern)
        self.assertIn("A3", nummern)


class SortierungUndRueckstaende(unittest.TestCase):

    def test_schnellste_zuerst_mit_rueckstaenden(self):
        eintraege = [_eintrag("1", "00:50,00"), _eintrag("2", "00:42,00"),
                     _eintrag("3", "00:47,00")]
        ergebnisse = lt.baue_ergebnisse(eintraege)
        self.assertEqual([e["startnummer"] for e in ergebnisse], [2, 3, 1])
        self.assertEqual(ergebnisse[0]["diff_first"], "")
        self.assertEqual(ergebnisse[1]["diff_first"], "+00:05,00")
        self.assertEqual(ergebnisse[2]["diff_first"], "+00:08,00")
        self.assertEqual(ergebnisse[2]["diff_prev"], "+00:03,00")

    def test_strafzeit_wird_in_klammern_angezeigt(self):
        ergebnisse = lt.baue_ergebnisse(
            [_eintrag("1", "00:54,00", strafzeit="12")])
        self.assertEqual(ergebnisse[0]["fehler"], "(12)")

    def test_ohne_strafzeit_bleibt_das_feld_leer(self):
        ergebnisse = lt.baue_ergebnisse(
            [_eintrag("1", "00:42,00", strafzeit="0")])
        self.assertEqual(ergebnisse[0]["fehler"], "")

    def test_klassen_natuerlich_sortiert(self):
        eintraege = [_eintrag("1", "00:42,00", klasse="10"),
                     _eintrag("2", "00:43,00", klasse="2"),
                     _eintrag("3", "00:44,00", klasse="1a")]
        ergebnisse = lt.baue_ergebnisse(eintraege)
        self.assertEqual([e["klasse"] for e in ergebnisse],
                         ["Klasse 1a", "Klasse 2", "Klasse 10"])


class DateienSchreiben(unittest.TestCase):

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zeitmessung-live-")
        self.livedata = os.path.join(self.ordner, "livedata.json")
        self.archiv = os.path.join(self.ordner, "ergebnisse")

    def tearDown(self):
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_schreibt_und_erkennt_unveraendert(self):
        daten = lt.baue_livedata([_eintrag("1", "00:42,00")], "2026-08-10")
        self.assertTrue(lt.schreibe_livedata(self.livedata, daten))
        # gleicher Inhalt, nur andere Uhrzeit -> nicht noch einmal schreiben
        gleich = lt.baue_livedata([_eintrag("1", "00:42,00")], "2026-08-10",
                                  jetzt=datetime(2026, 8, 10, 23, 59, 59))
        self.assertFalse(lt.schreibe_livedata(self.livedata, gleich))

    def test_neue_zeit_wird_geschrieben(self):
        lt.schreibe_livedata(self.livedata,
                             lt.baue_livedata([_eintrag("1", "00:42,00")],
                                              "2026-08-10"))
        self.assertTrue(lt.schreibe_livedata(
            self.livedata,
            lt.baue_livedata([_eintrag("1", "00:41,00")], "2026-08-10")))

    def test_archiv_und_verzeichnis(self):
        daten = lt.baue_livedata([_eintrag("1", "00:42,00")], "2026-08-10")
        self.assertTrue(lt.archiviere(self.archiv, daten))
        self.assertTrue(os.path.isfile(os.path.join(self.archiv, "2026-08-10.json")))
        with open(os.path.join(self.archiv, "index.json"), encoding="utf-8") as f:
            verzeichnis = json.load(f)["renntage"]
        self.assertEqual(verzeichnis[0]["datum"], "2026-08-10")
        self.assertEqual(verzeichnis[0]["starter"], 1)

    def test_archiv_ohne_ergebnisse_legt_nichts_an(self):
        daten = lt.baue_livedata([], "2026-08-10")
        self.assertFalse(lt.archiviere(self.archiv, daten))
        self.assertFalse(os.path.isdir(self.archiv))

    def test_unveraendertes_archiv_wird_nicht_neu_geschrieben(self):
        """Sonst entstünde bei jedem Abgleich eine neue Fassung, die über die
        mobile Verbindung hochgeladen werden müsste - ohne neue Zeiten."""
        daten = lt.baue_livedata([_eintrag("1", "00:42,00")], "2026-08-10")
        self.assertTrue(lt.archiviere(self.archiv, daten))
        gleich = lt.baue_livedata([_eintrag("1", "00:42,00")], "2026-08-10",
                                  jetzt=datetime(2026, 8, 10, 23, 59, 59))
        self.assertFalse(lt.archiviere(self.archiv, gleich),
                         "nur ein neuer Zeitstempel ist keine Änderung")

    def test_neue_zeit_landet_im_archiv(self):
        lt.archiviere(self.archiv, lt.baue_livedata([_eintrag("1", "00:42,00")],
                                                    "2026-08-10"))
        self.assertTrue(lt.archiviere(
            self.archiv, lt.baue_livedata([_eintrag("1", "00:41,00")],
                                          "2026-08-10")))

    def test_verzeichnis_bekommt_keine_doppelten_tage(self):
        for zeitpunkt in ("00:42,00", "00:41,00"):
            lt.archiviere(self.archiv,
                          lt.baue_livedata([_eintrag("1", zeitpunkt)],
                                           "2026-08-10"))
        with open(os.path.join(self.archiv, "index.json"), encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["renntage"]), 1)

    def test_leerer_stand(self):
        leer = lt.leerer_stand()
        self.assertEqual(leer["results"], [])
        self.assertEqual(leer["last_update"], "")


class Hauptschalter(unittest.TestCase):
    """Für andere Vereine muss sich das Live-Timing vollständig abschalten
    lassen."""

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zeitmessung-aus-")
        self.livedata = os.path.join(self.ordner, "livedata.json")
        self.db = Datenbank(os.path.join(self.ordner, "test.db"))
        self.db.ergebnis_speichern(datum="2026-08-10", starternr="1",
                                   name="Anton", klasse="3", verein="AC",
                                   laufnr=LAUF_GESAMT, gesamtzeit="00:42,00")

    def tearDown(self):
        self.db.schliessen()
        shutil.rmtree(self.ordner, ignore_errors=True)

    def _live(self, **werte):
        grund = {"livetiming": False, "livedata_datei": self.livedata,
                 "archiv_ordner": "", "veroeffentlichen": False,
                 "arbeits_repo": "", "live_repo": ""}
        grund.update(werte)
        return lt.LiveTiming(Einstellungen(datei=None, werte=grund))

    def test_ausgeschaltet_schreibt_nichts(self):
        live = self._live(livetiming=False)
        self.assertFalse(live.aktiv())
        self.assertEqual(live.aktualisieren(self.db, "2026-08-10"), "")
        self.assertFalse(os.path.exists(self.livedata))

    def test_ohne_dateipfad_bleibt_es_aus(self):
        live = self._live(livetiming=True, livedata_datei="")
        self.assertFalse(live.aktiv())

    def test_eingeschaltet_schreibt(self):
        live = self._live(livetiming=True)
        meldung = live.aktualisieren(self.db, "2026-08-10")
        self.assertTrue(os.path.isfile(self.livedata))
        self.assertIn("1 Ergebnisse", meldung)

    def test_veroeffentlichen_braucht_beide_ordner(self):
        live = self._live(livetiming=True, veroeffentlichen=True)
        self.assertFalse(live.einst.veroeffentlichen_an())
        live.aktualisieren(self.db, "2026-08-10")
        self.assertTrue(os.path.isfile(self.livedata),
                        "lokal schreiben muss trotzdem funktionieren")


if __name__ == "__main__":
    unittest.main()
