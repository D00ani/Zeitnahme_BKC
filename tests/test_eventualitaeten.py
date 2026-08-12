# -*- coding: utf-8 -*-
"""
Fehler, die bei einer gezielten Suche aufgefallen sind.

Jeder Test hier stand am Anfang auf Rot. Sie sollen verhindern, dass genau
diese Fälle wiederkommen - es sind durchweg Dinge, die erst am Renntag
aufgefallen wären.
"""
import json
import os
import shutil
import tempfile
import unittest

from zeitmessung import livetiming as lt
from zeitmessung.ablauf import TRAINING, Ablauf
from zeitmessung.ausdruck import ziel_bestimmen
from zeitmessung.datenbank import LAUF_1, LAUF_2, LAUF_GESAMT, Datenbank
from zeitmessung.einstellungen import STANDARD, Einstellungen
from zeitmessung.sperre import Sperre
from zeitmessung.wertung import Starterergebnis, rangliste

from .test_ablauf import Uhr


class Startnummernvorschlag(unittest.TestCase):
    """Nach einem wiederholten Lauf wurde eine längst vergebene Nummer
    vorgeschlagen - der jüngste Datensatz war ja der des Wiederholers."""

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zm-nr-")
        self.db = Datenbank(os.path.join(self.ordner, "t.db"))

    def tearDown(self):
        self.db.schliessen()
        shutil.rmtree(self.ordner, ignore_errors=True)

    def _speichern(self, nummer):
        self.db.ergebnis_speichern(datum="2026-08-10", starternr=str(nummer),
                                   name=f"F{nummer}", klasse="3",
                                   laufnr=LAUF_GESAMT, gesamtzeit="00:42,00")

    def test_hoechste_nummer_zaehlt_nicht_die_letzte(self):
        for nummer in range(1, 11):
            self._speichern(nummer)
        self._speichern(3)                    # Starter 3 fährt noch einmal
        self.assertEqual(self.db.naechste_startnummer("2026-08-10"), "11")

    def test_erste_nummer_ist_eins(self):
        self.assertEqual(self.db.naechste_startnummer("2026-08-10"), "1")

    def test_buchstabennummern_stoeren_nicht(self):
        self._speichern(5)
        self._speichern("A3")
        self.assertEqual(self.db.naechste_startnummer("2026-08-10"), "6")


class KaputteEinstellungsdatei(unittest.TestCase):

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zm-einst-")
        self.datei = os.path.join(self.ordner, "e.json")

    def tearDown(self):
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_json_ist_eine_liste(self):
        """Gültiges JSON, aber das Falsche darin - das hat das Programm
        beim Start umgeworfen."""
        with open(self.datei, "w", encoding="utf-8") as f:
            json.dump(["das", "ist", "falsch"], f)
        einst = Einstellungen.laden(self.datei)
        self.assertEqual(einst.strafzeit_pylone, STANDARD["strafzeit_pylone"])

    def test_json_ist_eine_zahl(self):
        with open(self.datei, "w", encoding="utf-8") as f:
            f.write("42")
        self.assertEqual(Einstellungen.laden(self.datei).strafzeit_pylone,
                         STANDARD["strafzeit_pylone"])

    def test_speichern_ohne_dateipfad_meldet_sich_verstaendlich(self):
        with self.assertRaises(ValueError):
            Einstellungen(datei=None).speichern()


class TrainingsRestzeit(unittest.TestCase):
    """Die Restzeit lief nach dem Ende des Trainings munter weiter."""

    def setUp(self):
        self.uhr = Uhr()
        einst = Einstellungen(datei=None, werte={
            "tr_max_runden": 2, "tr_max_zeit": 5,
            "sperrzeit_sekunden": 0}).pruefen()
        self.ablauf = Ablauf(einst, uhr=self.uhr)
        self.ablauf.modus_setzen(TRAINING)

    def test_bleibt_nach_dem_ende_stehen(self):
        self.ablauf.ausloesen()
        self.uhr.vor(70)
        self.assertEqual(self.ablauf.training_restzeit_minuten(), 4)
        for _ in range(2):
            self.uhr.vor(5)
            self.ablauf.ausloesen()           # Training endet nach 2 Runden
        self.assertFalse(self.ablauf.laeuft)
        stand = self.ablauf.training_restzeit_minuten()
        self.uhr.vor(600)
        self.assertEqual(self.ablauf.training_restzeit_minuten(), stand,
                         "nach dem Ende darf nicht weitergezählt werden")

    def test_neues_training_faengt_wieder_oben_an(self):
        self.ablauf.ausloesen()
        self.uhr.vor(130)
        self.ablauf.abbrechen()
        self.ablauf.ausloesen()
        self.assertEqual(self.ablauf.training_restzeit_minuten(), 5)


class RanglisteOhneZeit(unittest.TestCase):

    def _eintrag(self, nummer, zeittext, hs):
        return {"starternr": nummer, "gesamtzeit": zeittext, "gesamtzeit_hs": hs}

    def test_starter_ohne_zeit_teilen_sich_den_platz(self):
        gereiht = rangliste([self._eintrag("1", "00:42,00", 4200),
                             self._eintrag("2", "ADW", None),
                             self._eintrag("3", "ADW", None)])
        plaetze = {e["starternr"]: e["platz"] for e in gereiht}
        self.assertEqual(plaetze["1"], 1)
        self.assertEqual(plaetze["2"], plaetze["3"],
                         "beide haben keine Zeit - nichts unterscheidet sie")

    def test_zeitgleiche_weiterhin_gemeinsam(self):
        gereiht = rangliste([self._eintrag("1", "00:42,00", 4200),
                             self._eintrag("2", "00:42,00", 4200),
                             self._eintrag("3", "00:47,00", 4700)])
        self.assertEqual([e["platz"] for e in gereiht], [1, 1, 3])


class VeroeffentlichenAusserhalb(unittest.TestCase):
    """Lag die Ergebnisdatei außerhalb des Git-Ordners, kam nur ein
    unverständlicher Git-Fehler."""

    def test_klare_meldung(self):
        basis = tempfile.mkdtemp(prefix="zm-aussen-")
        try:
            repo = os.path.join(basis, "repo")
            os.makedirs(repo)
            draussen = os.path.join(basis, "woanders", "livedata.json")
            einst = Einstellungen(datei=None, werte={
                "arbeits_repo": repo, "live_repo": "",
                "livedata_datei": draussen})
            erfolg, meldung = lt.veroeffentliche(einst, "Test", [draussen])
            self.assertFalse(erfolg)
            self.assertIn("liegt nicht im Git-Ordner", meldung)
            self.assertIn(draussen, meldung)
        finally:
            shutil.rmtree(basis, ignore_errors=True)


class Dateiname(unittest.TestCase):

    def _datei(self, nummer):
        einst = Einstellungen(datei=None, werte={
            "vorschau_statt_druck": True,
            "vorschau_ordner": tempfile.gettempdir()})
        _, pfad = ziel_bestimmen(einst, Starterergebnis(startnummer=nummer))
        return os.path.basename(pfad)

    def test_startnummer_nur_aus_sonderzeichen(self):
        self.assertIn("_ohne_", self._datei("///"))

    def test_leere_startnummer(self):
        self.assertIn("_ohne_", self._datei(""))

    def test_normale_nummer_bleibt_stehen(self):
        self.assertIn("_7_", self._datei("7"))

    def test_nie_ein_pfadtrenner_im_namen(self):
        for nummer in ("a/b", "c\\d", "e:f", "*?"):
            name = self._datei(nummer)
            for zeichen in '/\\:*?"<>|':
                self.assertNotIn(zeichen, name)


class DatenbankSperre(unittest.TestCase):
    """Zwei Zeitmessungen auf derselben Datei wären ein stiller Datensalat."""

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zm-sperre-")
        self.pfad = os.path.join(self.ordner, "t.db")

    def tearDown(self):
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_zweite_sperre_scheitert(self):
        erste = Sperre(self.pfad)
        self.assertTrue(erste.setzen())
        try:
            zweite = Sperre(self.pfad)
            self.assertFalse(zweite.setzen(),
                             "eine zweite Instanz darf die Sperre nicht bekommen")
        finally:
            erste.loesen()

    def test_nach_dem_loesen_geht_es_wieder(self):
        erste = Sperre(self.pfad)
        erste.setzen()
        erste.loesen()
        zweite = Sperre(self.pfad)
        self.assertTrue(zweite.setzen())
        zweite.loesen()

    def test_prozessnummer_steht_drin(self):
        with Sperre(self.pfad) as gehalten:
            self.assertTrue(gehalten.gehalten)
            self.assertEqual(gehalten.wer_haelt_sie(), str(os.getpid()))


class GesamtergebnisNachziehen(unittest.TestCase):
    """Fehlte ein Wertungslauf, wurde stillschweigend eine zu kurze
    Gesamtzeit geschrieben."""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            tkinter.Tk().destroy()
        except Exception as fehler:                       # noqa: BLE001
            raise unittest.SkipTest(f"Keine Fensteroberfläche: {fehler}")

    def setUp(self):
        from zeitmessung.oberflaeche.haupt import Hauptfenster
        self.ordner = tempfile.mkdtemp(prefix="zm-nachziehen-")
        self.einst = Einstellungen(datei=None, werte={
            "datenbank": os.path.join(self.ordner, "t.db"),
            "serieller_port": "", "livetiming": False,
            "we_anzahl_laeufe": 2, "strafzeit_pylone": 2,
            "strafzeit_fehler": 10}).pruefen()
        self.fenster = Hauptfenster(self.einst)
        self.fenster.update()

    def tearDown(self):
        try:
            self.fenster.db.schliessen()
            self.fenster.sperre.loesen()
            self.fenster.destroy()
        except Exception:                                 # noqa: BLE001
            pass
        shutil.rmtree(self.ordner, ignore_errors=True)

    def _speichern(self, laufnr, fahrzeit):
        self.fenster.db.ergebnis_speichern(
            starternr="7", name="Anton", klasse="3", verein="AC",
            laufnr=laufnr, fahrzeit=fahrzeit, pylonen="0", adw="0",
            strafzeit="0", gesamtzeit=fahrzeit)

    def _uebersicht(self):
        from zeitmessung.oberflaeche.tagesuebersicht import Tagesuebersicht
        fenster = Tagesuebersicht(self.fenster, self.fenster.db, self.einst)
        fenster.update()
        return fenster

    def _berichtigen(self, fenster, laufnr, pylonen):
        satz = [e for e in self.fenster.db.ergebnisse()
                if e["laufnr"] == laufnr][0]
        fenster.liste.selection_set(str(satz["id"]))
        fenster.update()
        fenster.var_pylonen.set(str(pylonen))
        fenster._uebernehmen()

    def test_vollstaendig_wird_nachgezogen(self):
        self._speichern(LAUF_1, "00:40,00")
        self._speichern(LAUF_2, "00:30,00")
        self._speichern(LAUF_GESAMT, "01:10,00")
        fenster = self._uebersicht()
        try:
            self._berichtigen(fenster, LAUF_1, 3)          # 6 s Strafe
            gesamt = [e for e in self.fenster.db.ergebnisse()
                      if e["laufnr"] == LAUF_GESAMT][0]
            self.assertEqual(gesamt["gesamtzeit"], "01:16,00")
            self.assertIn("nachgezogen", fenster.var_meldung.get())
        finally:
            fenster.destroy()

    def test_fehlender_lauf_wird_nicht_stillschweigend_verrechnet(self):
        self._speichern(LAUF_1, "00:40,00")
        self._speichern(LAUF_2, "00:30,00")
        self._speichern(LAUF_GESAMT, "01:10,00")
        zweiter = [e for e in self.fenster.db.ergebnisse()
                   if e["laufnr"] == LAUF_2][0]
        self.fenster.db.ergebnis_loeschen(zweiter["id"])

        fenster = self._uebersicht()
        try:
            self._berichtigen(fenster, LAUF_1, 3)
            gesamt = [e for e in self.fenster.db.ergebnisse()
                      if e["laufnr"] == LAUF_GESAMT][0]
            self.assertEqual(gesamt["gesamtzeit"], "01:10,00",
                             "das Gesamtergebnis darf nicht angefasst werden")
            self.assertIn("ACHTUNG", fenster.var_meldung.get())
            self.assertIn("2. Wertungslauf", fenster.var_meldung.get())
        finally:
            fenster.destroy()


class SignalBeimBeenden(unittest.TestCase):
    """Ein Signal der Lichtschranke traf nach dem Schließen auf eine
    geschlossene Datenbank und warf einen Fehler ins Leere."""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            tkinter.Tk().destroy()
        except Exception as fehler:                       # noqa: BLE001
            raise unittest.SkipTest(f"Keine Fensteroberfläche: {fehler}")

    def test_signal_nach_dem_schliessen_tut_nichts(self):
        from zeitmessung.oberflaeche.haupt import Hauptfenster
        ordner = tempfile.mkdtemp(prefix="zm-ende-")
        try:
            einst = Einstellungen(datei=None, werte={
                "datenbank": os.path.join(ordner, "t.db"),
                "serieller_port": "", "livetiming": False}).pruefen()
            fenster = Hauptfenster(einst)
            fenster.update()
            fenster.db.schliessen()
            fenster.sperre.loesen()
            fenster.destroy()

            fenster._signal_aus_faden(123.0)   # der Lesefaden meldet sich
            self.assertTrue(fenster._beendet)
        finally:
            shutil.rmtree(ordner, ignore_errors=True)


class NurEinWertungslauf(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            tkinter.Tk().destroy()
        except Exception as fehler:                       # noqa: BLE001
            raise unittest.SkipTest(f"Keine Fensteroberfläche: {fehler}")

    def test_zweite_laufzeile_wird_ausgeblendet(self):
        import tkinter as tk

        from zeitmessung.oberflaeche import stil
        from zeitmessung.oberflaeche.starterfenster import Starterfenster

        wurzel = tk.Tk()
        wurzel.withdraw()
        stil.grundeinstellung(wurzel)
        try:
            einst = Einstellungen(datei=None, werte={
                "we_anzahl_laeufe": 1, "ergebnis_drucken": False}).pruefen()
            fenster = Starterfenster(wurzel, einst, lambda *_: None,
                                     lambda *_: True, lambda *_: None)
            ergebnis = Starterergebnis(sek_pylone=2, sek_fehler=10)
            ergebnis.zeit_setzen(1, 4103)
            fenster.lauf_oeffnen(ergebnis, 1)
            wurzel.update()

            # grid_remove() nimmt das Feld aus dem Raster - daran lässt es
            # sich zuverlässig ablesen, auch ohne sichtbares Fenster.
            self.assertTrue(fenster.zeilen[1]["pylonen_feld"].grid_info())
            self.assertFalse(fenster.zeilen[2]["pylonen_feld"].grid_info(),
                             "bei einem Wertungslauf ist die 2. Zeile unnötig")
        finally:
            wurzel.destroy()

    def test_bei_zwei_laeufen_bleiben_beide_zeilen(self):
        import tkinter as tk

        from zeitmessung.oberflaeche import stil
        from zeitmessung.oberflaeche.starterfenster import Starterfenster

        wurzel = tk.Tk()
        wurzel.withdraw()
        stil.grundeinstellung(wurzel)
        try:
            einst = Einstellungen(datei=None, werte={
                "we_anzahl_laeufe": 2, "ergebnis_drucken": False}).pruefen()
            fenster = Starterfenster(wurzel, einst, lambda *_: None,
                                     lambda *_: True, lambda *_: None)
            ergebnis = Starterergebnis(sek_pylone=2, sek_fehler=10)
            fenster.lauf_oeffnen(ergebnis, 2)
            wurzel.update()
            self.assertTrue(fenster.zeilen[1]["pylonen_feld"].grid_info())
            self.assertTrue(fenster.zeilen[2]["pylonen_feld"].grid_info())
        finally:
            wurzel.destroy()


if __name__ == "__main__":
    unittest.main()
