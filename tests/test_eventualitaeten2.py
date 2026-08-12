# -*- coding: utf-8 -*-
"""
Zweite und dritte Runde der Fehlersuche.

Die schwersten Funde stehen oben: der Zeitstempel der Lichtschranke wurde
verworfen, und ein zäher Git-Push konnte die ganze Zeitmessung einfrieren.
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

from zeitmessung import ausdruck, ausdruck_pdf, livetiming as lt, selbsttest, zeit
from zeitmessung.ablauf import TRAINING, WERTUNG, Ablauf
from zeitmessung.datenbank import LAUF_GESAMT, Datenbank
from zeitmessung.einstellungen import Einstellungen
from zeitmessung.wertung import Starterergebnis

from .test_ablauf import Uhr


class ZeitstempelDerLichtschranke(unittest.TestCase):
    """Die Lichtschranke nimmt den Zeitpunkt sofort im Lesefaden. Wurde er
    nicht weitergereicht, stoppte die Uhr erst, wenn das Fenster dazu kam."""

    def setUp(self):
        self.uhr = Uhr()
        einst = Einstellungen(datei=None, werte={
            "tr_max_runden": 9, "sperrzeit_sekunden": 0,
            "we_runden_pro_lauf": 2}).pruefen()
        self.ablauf = Ablauf(einst, uhr=self.uhr)

    def test_uebergebener_zeitpunkt_gilt(self):
        self.ablauf.modus_setzen(TRAINING)
        start = self.uhr()
        self.ablauf.ausloesen(start)
        # Die Oberfläche kommt erst 3 s später dazu - der Durchfahrtszeitpunkt
        # lag aber bei +10,00 s.
        self.uhr.vor(13.0)
        ereignisse = self.ablauf.ausloesen(start + 10.0)
        runde = next(e for e in ereignisse if e.art == "runde")
        self.assertEqual(zeit.formatiere(runde["zeit"]), "00:10,00")

    def test_ohne_angabe_gilt_der_aufrufmoment(self):
        """Bei F1 auf der Tastatur gibt es keinen früheren Zeitpunkt."""
        self.ablauf.modus_setzen(TRAINING)
        self.ablauf.ausloesen()
        self.uhr.vor(7.5)
        ereignisse = self.ablauf.ausloesen()
        runde = next(e for e in ereignisse if e.art == "runde")
        self.assertEqual(zeit.formatiere(runde["zeit"]), "00:07,50")

    def test_auch_der_start_zaehlt_ab_dem_signal(self):
        self.ablauf.modus_setzen(TRAINING)
        start = self.uhr()
        self.uhr.vor(5.0)                    # Fenster war blockiert
        self.ablauf.ausloesen(start)         # gestartet wurde aber bei 0
        self.uhr.vor(0.0)
        ereignisse = self.ablauf.ausloesen(start + 20.0)
        runde = next(e for e in ereignisse if e.art == "runde")
        self.assertEqual(zeit.formatiere(runde["zeit"]), "00:20,00")

    def test_sperrzeit_rechnet_mit_den_signalzeiten(self):
        einst = Einstellungen(datei=None, werte={
            "tr_max_runden": 9, "sperrzeit_sekunden": 3}).pruefen()
        ablauf = Ablauf(einst, uhr=self.uhr)
        ablauf.modus_setzen(TRAINING)
        start = self.uhr()
        ablauf.ausloesen(start)
        ereignisse = ablauf.ausloesen(start + 1.0)     # zu früh
        self.assertEqual([e.art for e in ereignisse], ["gesperrt"])
        ereignisse = ablauf.ausloesen(start + 4.0)
        self.assertIn("runde", [e.art for e in ereignisse])


class GitBlockiertNicht(unittest.TestCase):

    def test_git_aufruf_hat_eine_zeitgrenze(self):
        """Ohne Netz kann ein Push sonst minutenlang stehen."""
        import inspect
        quelle = inspect.getsource(lt._git)
        self.assertIn("timeout", quelle)
        self.assertIn("TimeoutExpired", quelle)

    def test_zeitueberschreitung_gibt_eine_lesbare_meldung(self):
        abgelaufen = lt._Abgelaufen(90)
        self.assertEqual(abgelaufen.returncode, 1)
        self.assertIn("90 Sekunden", abgelaufen.stderr)
        self.assertIn("Netz", abgelaufen.stderr)

    def test_fehlendes_git_stuerzt_nicht_ab(self):
        ordner = tempfile.mkdtemp(prefix="zm-git-")
        try:
            # ein Befehl, den es nicht gibt - so verhält sich ein System
            # ohne installiertes Git
            ergebnis = lt._git(["--version"], os.path.join(ordner, "gibtsnicht"))
            self.assertEqual(ergebnis.returncode, 1)
            self.assertTrue(ergebnis.stderr)
        finally:
            shutil.rmtree(ordner, ignore_errors=True)

    def test_hintergrund_wird_benutzt_statt_zu_warten(self):
        """Mit ``hintergrund`` darf ``aktualisieren`` nicht selbst pushen."""
        ordner = tempfile.mkdtemp(prefix="zm-hg-")
        try:
            datei = os.path.join(ordner, "livedata.json")
            db = Datenbank(os.path.join(ordner, "t.db"))
            db.ergebnis_speichern(starternr="1", name="A", klasse="3",
                                  laufnr=LAUF_GESAMT, gesamtzeit="00:42,00")
            einst = Einstellungen(datei=None, werte={
                "livetiming": True, "livedata_datei": datei,
                "veroeffentlichen": True, "arbeits_repo": ordner,
                "live_repo": ""})
            live = lt.LiveTiming(einst)
            gerufen = []
            meldung = live.aktualisieren(db, hintergrund=lambda: gerufen.append(1))
            self.assertEqual(len(gerufen), 1, "der Anstoß muss kommen")
            self.assertIn("wird veröffentlicht", meldung)
            db.schliessen()
        finally:
            shutil.rmtree(ordner, ignore_errors=True)


class LangeNamenAufDerKarte(unittest.TestCase):
    """Ein langer Name lief quer über die zweite Karte."""

    def _karte(self, name):
        ergebnis = Starterergebnis(startnummer="7", name=name, klasse="3",
                                   sek_pylone=2, sek_fehler=10)
        ergebnis.zeit_setzen(1, 4103)
        return ausdruck.bauplan(ergebnis, linker_rand=10)

    def _namenszeile(self, plan):
        # zweite Textanweisung der ersten Karte ist die Zeile mit dem Namen
        texte = [a for a in plan if a[0] == "text"]
        return next(a for a in texte if a[2] == 16)

    def test_langer_name_wird_gekuerzt(self):
        lang = "Maximiliane von Und-Zu-Hohenzollern-Sigmaringen"
        zeile = self._namenszeile(self._karte(lang))
        self.assertLess(len(zeile[4]), len(lang) + 4)
        self.assertTrue(zeile[4].endswith("…"))

    def test_gekuerzter_name_passt_auf_die_karte(self):
        lang = "Maximiliane von Und-Zu-Hohenzollern-Sigmaringen"
        zeile = self._namenszeile(self._karte(lang))
        breite = len(zeile[4]) * 9 * ausdruck._ZEICHENBREITE * 25.4 / 72
        self.assertLessEqual(breite, ausdruck.KARTEN_BREITE)

    def test_normaler_name_bleibt_unangetastet(self):
        zeile = self._namenszeile(self._karte("Anton Muster"))
        self.assertEqual(zeile[4], "Anton Muster (7)")

    def test_lange_klassenbezeichnung_wird_auch_gekuerzt(self):
        ergebnis = Starterergebnis(startnummer="7", name="A",
                                   klasse="Jugend weiblich bis 12 Jahre")
        plan = ausdruck.bauplan(ergebnis, linker_rand=10)
        klasse = next(a for a in plan if a[0] == "text" and a[2] == 10
                      and str(a[4]).startswith("Klasse"))
        # Die Gesamtzeit beginnt bei x + 40 - so weit darf die Klasse nicht
        breite = len(klasse[4]) * 9 * ausdruck._ZEICHENBREITE * 25.4 / 72
        self.assertLessEqual(breite, 40)


class FremdeSchriftzeichen(unittest.TestCase):

    def test_pdf_kommt_auch_mit_unbekannten_zeichen_zustande(self):
        """Die PDF-Standardschriften können kein Griechisch - dann steht
        dort ein Fragezeichen, aber der Ausdruck kommt zustande."""
        ordner = tempfile.mkdtemp(prefix="zm-zeichen-")
        try:
            for name in ("Łukasz Wiśniewski", "Şahin Öztürk", "Θεόδωρος"):
                ergebnis = Starterergebnis(startnummer="7", name=name,
                                           klasse="3")
                ziel = os.path.join(ordner, "k.pdf")
                ausdruck_pdf.schreibe(ausdruck.bauplan(ergebnis), ziel)
                self.assertGreater(os.path.getsize(ziel), 1000)
        finally:
            shutil.rmtree(ordner, ignore_errors=True)

    def test_umlaute_kommen_richtig_an(self):
        strom = ausdruck_pdf.inhaltsstrom(
            [("text", 10, 10, ("Verdana", 9, False), "Müßiggang")])
        self.assertIn("Müßiggang".encode("cp1252"), strom)


class DruckraenderBleibenAufDemBlatt(unittest.TestCase):

    def test_zu_grosse_raender_werden_begrenzt(self):
        einst = Einstellungen(datei=None, werte={
            "pr_linker_rand": 200, "pr_oberer_rand": 280,
            "pr_unterer_abstand": 90}).pruefen()
        self.assertLessEqual(einst.pr_linker_rand, 60)
        self.assertLessEqual(einst.pr_oberer_rand, 200)
        self.assertLessEqual(einst.pr_unterer_abstand, 60)

    def test_karte_bleibt_auf_a4(self):
        einst = Einstellungen(datei=None, werte={
            "pr_linker_rand": 999, "pr_oberer_rand": 999,
            "pr_unterer_abstand": 999}).pruefen()
        ergebnis = Starterergebnis(startnummer="7", name="A", klasse="3")
        plan = ausdruck.bauplan(ergebnis, int(einst.pr_linker_rand),
                                int(einst.pr_oberer_rand),
                                int(einst.pr_unterer_abstand))
        for anweisung in plan:
            if anweisung[0] == "linie":
                self.assertLessEqual(anweisung[3], 210, "über den rechten Rand")
                self.assertLessEqual(anweisung[4], 297, "über den unteren Rand")

    def test_uebliche_werte_bleiben_wie_sie_sind(self):
        einst = Einstellungen(datei=None, werte={
            "pr_linker_rand": 10, "pr_oberer_rand": 10,
            "pr_unterer_abstand": 20}).pruefen()
        self.assertEqual(einst.pr_linker_rand, 10)
        self.assertEqual(einst.pr_oberer_rand, 10)
        self.assertEqual(einst.pr_unterer_abstand, 20)


class Selbsttest(unittest.TestCase):

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zm-selbst-")
        self.db = Datenbank(os.path.join(self.ordner, "t.db"))

    def tearDown(self):
        self.db.schliessen()
        shutil.rmtree(self.ordner, ignore_errors=True)

    def _einstellungen(self, **werte):
        grund = {"klassen": "1a;2;3", "vereine": "AC Singen",
                 "serieller_port": "", "livetiming": False,
                 "vorschau_statt_druck": False, "drucker": ""}
        grund.update(werte)
        return Einstellungen(datei=None, werte=grund).pruefen()

    def test_bericht_hat_zu_jedem_bereich_einen_befund(self):
        bericht = selbsttest.alles_pruefen(self._einstellungen(), self.db)
        titel = [b.titel for b in bericht]
        for erwartet in ("Datenbank", "Sicherung", "Klassen und Vereine",
                         "Lichtschranke", "Ausdruck", "Live-Timing"):
            self.assertIn(erwartet, titel)

    def test_datenbank_wird_als_beschreibbar_erkannt(self):
        befund = selbsttest.pruefe_datenbank(self.db)
        self.assertEqual(befund.zustand, selbsttest.OK)

    def test_geschlossene_datenbank_faellt_auf(self):
        self.db.schliessen()
        befund = selbsttest.pruefe_datenbank(self.db)
        self.assertEqual(befund.zustand, selbsttest.FEHLER)
        self.db = Datenbank(os.path.join(self.ordner, "t.db"))   # für tearDown

    def test_leere_klassenliste_ist_ein_fehler(self):
        befund = selbsttest.pruefe_klassen(self._einstellungen(klassen=""))
        self.assertEqual(befund.zustand, selbsttest.FEHLER)

    def test_pdf_vorschau_wird_als_hinweis_gemeldet(self):
        befund = selbsttest.pruefe_drucker(
            self._einstellungen(vorschau_statt_druck=True))
        self.assertEqual(befund.zustand, selbsttest.WARNUNG)
        self.assertIn("kein Papier", befund.rat)

    def test_drucker_der_nicht_existiert(self):
        befund = selbsttest.pruefe_drucker(
            self._einstellungen(drucker="Gibt es nicht"))
        if ausdruck.drucker_liste():
            self.assertEqual(befund.zustand, selbsttest.FEHLER)

    def test_ohne_lichtschranke_nur_ein_hinweis(self):
        befund = selbsttest.pruefe_lichtschranke(self._einstellungen(), False)
        self.assertEqual(befund.zustand, selbsttest.WARNUNG)
        self.assertIn("F1", befund.rat)

    def test_eingestellter_port_fehlt(self):
        befund = selbsttest.pruefe_lichtschranke(
            self._einstellungen(serieller_port="COM99"), False)
        self.assertEqual(befund.zustand, selbsttest.FEHLER)
        self.assertIn("Stecker", befund.rat)

    def test_verbundene_lichtschranke_ist_in_ordnung(self):
        befund = selbsttest.pruefe_lichtschranke(
            self._einstellungen(serieller_port="COM6"), True)
        self.assertEqual(befund.zustand, selbsttest.OK)

    def test_livetiming_an_ohne_datei_ist_ein_fehler(self):
        befund = selbsttest.pruefe_livetiming(
            self._einstellungen(livetiming=True, livedata_datei=""))
        self.assertEqual(befund.zustand, selbsttest.FEHLER)

    def test_livetiming_aus_ist_in_ordnung(self):
        befund = selbsttest.pruefe_livetiming(self._einstellungen())
        self.assertEqual(befund.zustand, selbsttest.OK)

    def test_zusammenfassung_nennt_die_zahl_der_fehler(self):
        bericht = selbsttest.alles_pruefen(
            self._einstellungen(klassen="", serieller_port="COM99"), self.db)
        self.assertIn("2 Punkt", bericht.zusammenfassung())
        self.assertEqual(len(bericht.fehler), 2)

    def test_text_enthaelt_die_ratschlaege(self):
        bericht = selbsttest.alles_pruefen(
            self._einstellungen(klassen=""), self.db)
        text = bericht.als_text()
        self.assertIn("[X]", text)
        self.assertIn("Einstellungen", text)


class SelbsttestImFenster(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            tkinter.Tk().destroy()
        except Exception as fehler:                       # noqa: BLE001
            raise unittest.SkipTest(f"Keine Fensteroberfläche: {fehler}")

    def test_menuepunkt_liefert_einen_bericht(self):
        import tkinter.messagebox as mb

        from zeitmessung.oberflaeche.haupt import Hauptfenster

        ordner = tempfile.mkdtemp(prefix="zm-selbstf-")
        gemerkt = (mb.showinfo, mb.showerror)
        mb.showinfo = mb.showerror = lambda *a, **k: None
        try:
            einst = Einstellungen(datei=None, werte={
                "datenbank": os.path.join(ordner, "t.db"),
                "serieller_port": "", "livetiming": False}).pruefen()
            fenster = Hauptfenster(einst)
            fenster.update()
            bericht = fenster._selbsttest()
            self.assertGreaterEqual(len(bericht), 6)
            self.assertTrue(fenster.var_status.get())
            fenster.db.schliessen()
            fenster.sperre.loesen()
            fenster.destroy()
        finally:
            mb.showinfo, mb.showerror = gemerkt
            shutil.rmtree(ordner, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
