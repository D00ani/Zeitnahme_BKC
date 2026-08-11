# -*- coding: utf-8 -*-
"""
Bedienung und Schutz vor Fehlbedienung.

Diese Tests bauen das echte Hauptfenster auf und prüfen das Verhalten, das
am Renntag zählt: Was steht im Zustandsbalken, was passiert bei einem Signal
zur falschen Zeit, und lässt sich ein Fehler hinterher berichtigen.
"""
import os
import shutil
import tempfile
import unittest

from zeitmessung.datenbank import LAUF_1, LAUF_2, LAUF_GESAMT
from zeitmessung.einstellungen import Einstellungen


def _fenster_moeglich():
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:                                  # noqa: BLE001
        return False


class MitFenster(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not _fenster_moeglich():
            raise unittest.SkipTest("Keine Fensteroberfläche verfügbar.")

    def setUp(self):
        from zeitmessung.oberflaeche.haupt import Hauptfenster
        self.ordner = tempfile.mkdtemp(prefix="zeitmessung-bedienung-")
        self.einst = Einstellungen(datei=None, werte={
            "datenbank": os.path.join(self.ordner, "t.db"),
            "serieller_port": "", "livetiming": False,
            "we_einfuehrungsrunden": 1, "we_runden_pro_lauf": 2,
            "we_anzahl_laeufe": 2, "sperrzeit_sekunden": 0,
            "strafzeit_pylone": 2, "strafzeit_fehler": 10,
            "ergebnis_drucken": False, "eine_lichtschranke": True}).pruefen()
        self.fenster = Hauptfenster(self.einst)
        self.fenster.update()

    def tearDown(self):
        try:
            self.fenster.db.schliessen()
            self.fenster.destroy()
        except Exception:                              # noqa: BLE001
            pass
        shutil.rmtree(self.ordner, ignore_errors=True)

    def _wertung_vorbereiten(self, nummer="7", name="Anton"):
        """Modus „Wertung“ wählen und die Starterabfrage ausfüllen.

        Beim Umschalten geht das Starterfenster sofort auf - und solange es
        offen ist, wird jedes Signal bewusst ignoriert. Genau deshalb muss
        es hier erst geschlossen werden.
        """
        self.fenster._modus_setzen("wertung")
        self.fenster.update()
        if self.fenster._eingabe_offen():
            self.fenster.ergebnis.startnummer = nummer
            self.fenster.ergebnis.name = name
            self.fenster.ergebnis.klasse = "3"
            self.fenster.ergebnis.verein = "AC Singen"
            self.fenster._starter_weiter("erfassen", self.fenster.ergebnis)
            self.fenster.update()

    def _lauf_fahren(self):
        """Einen kompletten Wertungslauf auslösen."""
        self.fenster._ausloesen()
        for _ in range(int(self.einst.we_runden_pro_lauf)):
            self.fenster._ausloesen()
        self.fenster.update()


class SignalZurFalschenZeit(MitFenster):

    def test_signal_waehrend_der_eingabe_startet_keinen_lauf(self):
        """Der gefundene Fehler: fuhr jemand durch die Schranke, während
        vorne noch Pylonen eingetragen wurden, lief im Hintergrund
        unbemerkt der nächste Lauf los."""
        self._wertung_vorbereiten()
        self._lauf_fahren()
        self.assertTrue(self.fenster._eingabe_offen())
        self.assertEqual(self.fenster.ablauf.lauf_nummer, 1)

        self.fenster._ausloesen()          # Signal während der Eingabe
        self.fenster.update()

        self.assertEqual(self.fenster.ablauf.lauf_nummer, 1,
                         "es darf kein zweiter Lauf gestartet werden")
        self.assertFalse(self.fenster.ablauf.laeuft)

    def test_ignoriertes_signal_wird_protokolliert(self):
        self._wertung_vorbereiten()
        self._lauf_fahren()
        self.fenster._ausloesen()
        texte = [e["text"] for e in self.fenster.db.verlauf()]
        self.assertIn("Signal während der Eingabe ignoriert", texte,
                      "im Verlauf muss nachvollziehbar sein, dass ein "
                      "Signal kam")

    def test_esc_waehrend_der_eingabe_verwirft_nichts(self):
        self._wertung_vorbereiten()
        self._lauf_fahren()
        vorher = self.fenster.ablauf.lauf_nummer
        self.fenster._abbrechen()
        self.assertEqual(self.fenster.ablauf.lauf_nummer, vorher)

    def test_nach_dem_schliessen_geht_es_normal_weiter(self):
        self._wertung_vorbereiten()
        self._lauf_fahren()
        self.fenster._starter_weiter("lauf1", self.fenster.ergebnis)
        self.fenster.update()
        self.assertFalse(self.fenster._eingabe_offen())

        self.fenster._ausloesen()
        self.assertEqual(self.fenster.ablauf.lauf_nummer, 2)
        self.assertTrue(self.fenster.ablauf.laeuft)


class Zustandsbalken(MitFenster):

    def _text(self):
        return self.fenster._zustandsbalken()[0]

    def _art(self):
        return self.fenster._zustandsbalken()[1]

    def test_training_warnt_dass_nichts_gespeichert_wird(self):
        self.fenster._modus_setzen("training")
        self.assertIn("TRAINING", self._text())
        self.assertIn("nichts gespeichert", self._text())

    def test_laufendes_training_zeigt_runde_und_restzeit(self):
        self.fenster._modus_setzen("training")
        self.fenster._ausloesen()
        text = self._text()
        self.assertIn("TRAINING LÄUFT", text)
        self.assertIn("Runde 1 von", text)
        self.assertIn("Min.", text)
        self.assertEqual(self._art(), "laeuft")

    def test_wertung_zeigt_welcher_lauf_ansteht(self):
        self._wertung_vorbereiten()
        self.assertIn("bereit für Lauf 1 von 2", self._text())

    def test_laufende_wertung_zeigt_lauf_und_runde(self):
        self._wertung_vorbereiten()
        self.fenster._ausloesen()
        text = self._text()
        self.assertIn("WERTUNGSLAUF 1 von 2 LÄUFT", text)
        self.assertIn("Runde 1 von 2", text)

    def test_fahrername_steht_im_balken(self):
        self._wertung_vorbereiten()
        self.assertIn("Nr. 7 Anton", self._text())

    def test_offene_eingabe_wird_angesagt(self):
        self._wertung_vorbereiten()
        self._lauf_fahren()
        self.assertIn("EINGABE OFFEN", self._text())

    def test_einfuehrungsrunde(self):
        self.fenster._modus_setzen("einfuehrung")
        self.assertIn("EINFÜHRUNGSRUNDE", self._text())
        self.assertIn("nicht gemessen", self._text())


class LichtschrankenAnzeige(MitFenster):

    def test_ohne_port_steht_der_hinweis_dauerhaft_da(self):
        self.fenster._schranke_zeichnen()
        text = self.fenster.var_schranke.get()
        self.assertIn("keine eingestellt", text)
        self.assertIn("F1", text)

    def test_eingestellt_aber_nicht_verbunden_faellt_auf(self):
        self.fenster.einst.serieller_port = "COM99"
        self.fenster.lichtschranke = None
        self.fenster._schranke_zeichnen()
        text = self.fenster.var_schranke.get()
        self.assertIn("NICHT verbunden", text)
        self.assertIn("COM99", text)


class AnzeigeBeimStart(MitFenster):
    """Direkt nach dem Start muss ohne Klick klar sein, woran man ist."""

    def test_balken_ist_gefuellt(self):
        self.assertTrue(self.fenster.balken["text"].strip())

    def test_lichtschranke_ist_beschriftet(self):
        self.assertTrue(self.fenster.var_schranke.get().strip())

    def test_live_timing_zeigt_seinen_zustand(self):
        self.assertEqual(self.fenster.var_live.get(), "Live-Timing: aus")


class NaechsterStarter(MitFenster):

    def test_fragt_nach_wenn_daten_drin_sind(self):
        self.fenster.ergebnis.startnummer = "7"
        self.fenster.ergebnis.name = "Anton"
        self.assertTrue(self.fenster._hat_unfertige_daten())

    def test_fragt_nicht_nach_wenn_alles_gespeichert_ist(self):
        self.fenster.ergebnis.startnummer = "7"
        self.fenster._gespeichert_lauf2 = True
        self.assertFalse(self.fenster._hat_unfertige_daten())

    def test_leerer_starter_braucht_keine_rueckfrage(self):
        self.assertFalse(self.fenster._hat_unfertige_daten())


class SicherungBeimStart(MitFenster):

    def test_kopie_wird_angelegt(self):
        self.assertTrue(self.fenster.sicherung)
        self.assertTrue(os.path.isfile(self.fenster.sicherung))

    def test_alte_kopien_werden_aufgeraeumt(self):
        ordner = os.path.join(self.ordner, "viele")
        for _ in range(6):
            self.fenster.db.sicherung_anlegen(ordner, behalten=3)
        dateien = [d for d in os.listdir(ordner) if d.endswith(".db")]
        self.assertLessEqual(len(dateien), 3)


class BerichtigenAmRenntag(MitFenster):

    def _speichern(self, laufnr, fahrzeit, pylonen="0", fehler="0",
                   strafzeit="0", gesamt=None):
        self.fenster.db.ergebnis_speichern(
            starternr="7", name="Anton", klasse="3", verein="AC Singen",
            laufnr=laufnr, fahrzeit=fahrzeit, pylonen=pylonen, adw=fehler,
            strafzeit=strafzeit, gesamtzeit=gesamt or fahrzeit)

    def test_pylonen_berichtigen_zieht_das_gesamtergebnis_nach(self):
        from zeitmessung.oberflaeche.tagesuebersicht import Tagesuebersicht

        self._speichern(LAUF_1, "00:40,00")
        self._speichern(LAUF_2, "00:30,00")
        self._speichern(LAUF_GESAMT, "01:10,00")

        fenster = Tagesuebersicht(self.fenster, self.fenster.db, self.einst)
        fenster.update()
        try:
            erster = [e for e in self.fenster.db.ergebnisse()
                      if e["laufnr"] == LAUF_1][0]
            fenster.liste.selection_set(str(erster["id"]))
            fenster.update()
            fenster.var_pylonen.set("3")       # 3 x 2 s = 6 s Strafe
            fenster._uebernehmen()

            alle = {e["laufnr"]: e for e in self.fenster.db.ergebnisse()}
            self.assertEqual(alle[LAUF_1]["strafzeit"], "6")
            self.assertEqual(alle[LAUF_1]["gesamtzeit"], "00:46,00")
            self.assertEqual(alle[LAUF_GESAMT]["gesamtzeit"], "01:16,00",
                             "das Gesamtergebnis muss mitgezogen werden")
            self.assertEqual(alle[LAUF_GESAMT]["pylonen"], "3")
        finally:
            fenster.destroy()

    def test_datensatz_loeschen(self):
        from zeitmessung.oberflaeche.tagesuebersicht import Tagesuebersicht

        self._speichern(LAUF_1, "00:40,00")
        fenster = Tagesuebersicht(self.fenster, self.fenster.db, self.einst)
        fenster.update()
        try:
            kennung = self.fenster.db.ergebnisse()[0]["id"]
            self.assertTrue(self.fenster.db.ergebnis_loeschen(kennung))
            self.assertEqual(self.fenster.db.ergebnisse(), [])
        finally:
            fenster.destroy()

    def test_uebersicht_zeigt_alle_datensaetze_des_tages(self):
        from zeitmessung.oberflaeche.tagesuebersicht import Tagesuebersicht

        self._speichern(LAUF_1, "00:40,00")
        self._speichern(LAUF_2, "00:30,00")
        fenster = Tagesuebersicht(self.fenster, self.fenster.db, self.einst)
        fenster.update()
        try:
            self.assertEqual(len(fenster.liste.get_children()), 2)
            self.assertIn("2 Datensätze", fenster.var_kopf.get())
            self.assertIn("1 Starter", fenster.var_kopf.get())
        finally:
            fenster.destroy()


if __name__ == "__main__":
    unittest.main()
