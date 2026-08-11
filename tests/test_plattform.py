# -*- coding: utf-8 -*-
"""
Betriebssystem-Unabhängigkeit.

Geprüft wird, dass das Programm auf Linux laufen kann: der PDF-Erzeuger
setzt dieselben Millimeterpositionen wie der Windows-Druck, die
Linux-Bausteine lassen sich laden, und in den portablen Modulen steckt
nichts Windows-Eigenes.

Das meiste davon lässt sich auch von Windows aus prüfen - nur der
tatsächliche Druck und ein echtes Lichtschrankensignal brauchen das jeweilige
System.
"""
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

from zeitmessung import ausdruck, ausdruck_pdf, zeit
from zeitmessung.wertung import Starterergebnis

PAKET = pathlib.Path(ausdruck.__file__).parent


def _ergebnis():
    e = Starterergebnis(startnummer="7", name="Anton Müster", klasse="3",
                        verein="AC Singen", sek_pylone=2, sek_fehler=10)
    e.zeit_setzen(1, zeit.parse("00:41,03"))
    e.zeit_setzen(2, zeit.parse("00:17,81"))
    e.lauf(1).pylonen = 3
    e.lauf(2).fehler = 1
    return e


class PortableModule(unittest.TestCase):
    """Nur zwei Module dürfen Windows-Datentypen benutzen - alle anderen
    müssen sich auf Linux laden lassen."""

    ERLAUBT = {"ausdruck_windows.py", "lichtschranke_windows.py"}

    def test_kein_wintypes_in_portablen_modulen(self):
        for datei in sorted(PAKET.rglob("*.py")):
            if datei.name in self.ERLAUBT:
                continue
            inhalt = datei.read_text(encoding="utf-8")
            self.assertNotIn("from ctypes import wintypes", inhalt,
                             f"{datei.name} ließe sich auf Linux nicht laden")
            self.assertNotIn("ctypes.WinDLL", inhalt,
                             f"{datei.name} ruft eine Windows-Bibliothek auf")

    def test_creationflags_nur_unter_windows(self):
        """``creationflags`` gibt es nur unter Windows; anderswo wirft
        subprocess damit einen Fehler."""
        for datei in sorted(PAKET.rglob("*.py")):
            if datei.name in self.ERLAUBT:
                continue
            inhalt = datei.read_text(encoding="utf-8")
            for zeile in inhalt.splitlines():
                if "creationflags" in zeile and not zeile.strip().startswith("#"):
                    self.assertIn("sys.platform", inhalt,
                                  f"{datei.name} setzt creationflags ungeprüft")

    def test_kein_startfile_ohne_pruefung(self):
        inhalt = (PAKET / "ausdruck.py").read_text(encoding="utf-8")
        stelle = inhalt.index("os.startfile")
        self.assertIn("sys.platform", inhalt[:stelle],
                      "os.startfile gibt es nur unter Windows")


class PdfErzeuger(unittest.TestCase):

    def setUp(self):
        self.ordner = tempfile.mkdtemp(prefix="zeitmessung-pdf-")
        self.plan = ausdruck.bauplan(_ergebnis(), linker_rand=10,
                                     oberer_rand=10, unterer_abstand=20)
        self.datei = os.path.join(self.ordner, "karte.pdf")
        ausdruck_pdf.schreibe(self.plan, self.datei)

    def tearDown(self):
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_ist_eine_gueltige_pdf(self):
        with open(self.datei, "rb") as f:
            inhalt = f.read()
        self.assertTrue(inhalt.startswith(b"%PDF-1.4"))
        self.assertTrue(inhalt.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/Type /Catalog", inhalt)
        self.assertIn(b"startxref", inhalt)

    def test_bleibt_klein(self):
        """Ohne eingebettete Schriften bleibt die Datei winzig - wichtig,
        wenn sie über eine mobile Verbindung geht."""
        self.assertLess(os.path.getsize(self.datei), 10 * 1024)

    def test_din_a4(self):
        with open(self.datei, "rb") as f:
            inhalt = f.read().decode("latin-1")
        self.assertIn("/MediaBox [0 0 595.276 841.890]", inhalt)

    def test_jeder_text_des_bauplans_kommt_vor(self):
        with open(self.datei, "rb") as f:
            inhalt = f.read().decode("cp1252", errors="replace")
        for anweisung in self.plan:
            if anweisung[0] != "text":
                continue
            # Klammern und Rückstriche stehen in der Datei maskiert -
            # "Anton Müster (7)" wird zu "Anton Müster \(7\)".
            erwartet = ausdruck_pdf._text_maskieren(anweisung[4])
            self.assertIn(f"({erwartet}) Tj", inhalt,
                          f"„{anweisung[4]}“ fehlt in der PDF")

    def test_anzahl_der_linien_stimmt(self):
        with open(self.datei, "rb") as f:
            inhalt = f.read().decode("latin-1")
        linien = len(re.findall(r"\bl S\b", inhalt))
        erwartet = len([a for a in self.plan if a[0] == "linie"])
        self.assertEqual(linien, erwartet)

    def test_umlaute_bleiben_erhalten(self):
        with open(self.datei, "rb") as f:
            inhalt = f.read()
        self.assertIn("Müster".encode("cp1252"), inhalt)

    def test_klammern_werden_maskiert(self):
        """„Anton Müster (7)“ enthält Klammern - die haben in PDF eine
        Sonderbedeutung und müssen entwertet werden."""
        strom = ausdruck_pdf.inhaltsstrom(
            [("text", 10, 10, ("Verdana", 9, False), "A (b) \\ c")])
        self.assertIn(rb"A \(b\) \\ c", strom)

    def test_positionen_stimmen_mit_dem_bauplan(self):
        """Unabhängige Gegenprobe: die Koordinaten im Inhaltsstrom müssen
        den Millimeterangaben des Bauplans entsprechen."""
        strom = ausdruck_pdf.inhaltsstrom(self.plan).decode("cp1252")
        for anweisung in self.plan:
            if anweisung[0] != "text":
                continue
            _, x_mm, y_mm, (_f, punkte, _fett), inhalt = anweisung
            x_soll = x_mm * ausdruck_pdf.PUNKT_JE_MM
            y_soll = (ausdruck_pdf.SEITE_HOEHE - y_mm * ausdruck_pdf.PUNKT_JE_MM
                      - punkte * ausdruck_pdf.OBERLAENGE)
            self.assertIn(f"{x_soll:.2f} {y_soll:.2f} Td", strom,
                          f"Position von „{inhalt}“ stimmt nicht")

    def test_grundlinie_wie_beim_windows_druck(self):
        """Der Abstand Oberkante -> Grundlinie ist an einem echten
        Windows-Ausdruck gemessen worden."""
        self.assertAlmostEqual(ausdruck_pdf.OBERLAENGE, 1.010, places=3)


class PdfNachgemessen(unittest.TestCase):
    """Gegenprobe mit einem fremden PDF-Leser, falls vorhanden."""

    def setUp(self):
        try:
            import fitz                                   # noqa: F401
        except ImportError:
            self.skipTest("PyMuPDF ist nicht installiert.")
        self.ordner = tempfile.mkdtemp(prefix="zeitmessung-pdf2-")

    def tearDown(self):
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_text_sitzt_auf_den_millimetern(self):
        import fitz
        plan = ausdruck.bauplan(_ergebnis(), linker_rand=10, oberer_rand=10,
                                unterer_abstand=20, karten=1)
        datei = os.path.join(self.ordner, "k.pdf")
        ausdruck_pdf.schreibe(plan, datei)

        dokument = fitz.open(datei)
        seite = dokument[0]
        gefunden = {}
        for block in seite.get_text("dict")["blocks"]:
            for zeile in block.get("lines", []):
                for teil in zeile["spans"]:
                    text = teil["text"].strip()
                    if text:
                        gefunden.setdefault(text, teil["origin"])
        dokument.close()

        for anweisung in plan:
            if anweisung[0] != "text":
                continue
            _, x_mm, y_mm, (_f, punkte, _fett), inhalt = anweisung
            self.assertIn(inhalt, gefunden)
            x_ist = gefunden[inhalt][0] / 72 * 25.4
            self.assertAlmostEqual(x_ist, x_mm, delta=0.1,
                                   msg=f"x von „{inhalt}“")


class LinuxBausteine(unittest.TestCase):
    """Die Linux-Module müssen sich laden lassen und sich sauber verhalten,
    auch wenn das System sie gerade nicht braucht."""

    def test_ausdruck_linux_laedt(self):
        from zeitmessung import ausdruck_linux
        self.assertTrue(hasattr(ausdruck_linux, "ausgeben"))
        self.assertTrue(hasattr(ausdruck_linux, "drucker_liste"))

    def test_lichtschranke_linux_laedt(self):
        from zeitmessung import lichtschranke_linux
        self.assertTrue(hasattr(lichtschranke_linux, "Lichtschranke"))

    def test_ohne_cups_gibt_es_eine_leere_liste(self):
        """Auf einem System ohne lpstat darf nichts abstürzen."""
        from zeitmessung import ausdruck_linux
        self.assertIsInstance(ausdruck_linux.drucker_liste(), list)
        self.assertIsInstance(ausdruck_linux.standarddrucker(), str)

    def test_linux_schreibt_dieselbe_pdf(self):
        from zeitmessung import ausdruck_linux
        ordner = tempfile.mkdtemp(prefix="zeitmessung-lin-")
        try:
            ziel = os.path.join(ordner, "k.pdf")
            plan = ausdruck.bauplan(_ergebnis())
            ergebnis = ausdruck_linux.ausgeben(plan, "", "Karte", ziel)
            self.assertEqual(ergebnis, ziel)
            self.assertTrue(os.path.isfile(ziel))
        finally:
            shutil.rmtree(ordner, ignore_errors=True)

    def test_drucken_ohne_drucker_meldet_sich(self):
        from zeitmessung import ausdruck_linux
        with self.assertRaises(ausdruck.DruckFehler):
            ausdruck_linux.ausgeben(ausdruck.bauplan(_ergebnis()), "", "Karte")

    def test_portliste_ist_eine_liste(self):
        from zeitmessung import lichtschranke_linux
        self.assertIsInstance(lichtschranke_linux.verfuegbare_ports(), list)
        self.assertIsInstance(lichtschranke_linux.port_beschreibungen(), dict)

    def test_ohne_port_kommt_eine_verstaendliche_meldung(self):
        from zeitmessung import lichtschranke_linux
        meldungen = []
        schranke = lichtschranke_linux.Lichtschranke(
            "", bei_fehler=meldungen.append)
        self.assertFalse(schranke.oeffnen())
        self.assertIn("F1", meldungen[0])


class BackendAuswahl(unittest.TestCase):

    def test_passt_zum_betriebssystem(self):
        gewaehlt = ausdruck.backend().__name__
        if sys.platform.startswith("win"):
            self.assertTrue(gewaehlt.endswith("ausdruck_windows"), gewaehlt)
        else:
            self.assertTrue(gewaehlt.endswith("ausdruck_linux"), gewaehlt)

    def test_lichtschranke_reicht_die_schnittstelle_durch(self):
        from zeitmessung import lichtschranke
        for name in ("Lichtschranke", "verfuegbare_ports", "port_beschreibungen"):
            self.assertTrue(hasattr(lichtschranke, name), name)


if __name__ == "__main__":
    unittest.main()
