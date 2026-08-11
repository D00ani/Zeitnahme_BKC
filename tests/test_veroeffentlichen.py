# -*- coding: utf-8 -*-
"""
Veröffentlichen - gegen ein echtes Git, nicht gegen Attrappen.

Zwei Wege werden geprüft:

**Ein Ordner**  Die Zeitnahme hat einen eigenen kleinen Klon, der nur die
                Ergebnisdateien enthält. Nichts hängt an der Pflege der
                Webseite. Das ist der einfache Weg für andere Vereine und
                für einen zweiten Laptop.

**Zwei Ordner** Getrennter Arbeits- und Live-Stand, wie bei MCH Singen.
                Dabei darf ausschließlich das Ergebnisverzeichnis live
                gehen, niemals der Arbeitsstand der Webseite.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from zeitmessung import livetiming as lt
from zeitmessung.einstellungen import Einstellungen


def _git(argumente, ordner):
    return subprocess.run(["git"] + argumente, cwd=ordner, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _git_vorhanden():
    try:
        return subprocess.run(["git", "--version"], capture_output=True).returncode == 0
    except OSError:
        return False


def _beispieldaten(nummer="7", name="Anton"):
    return lt.baue_livedata(
        [{"starternr": nummer, "name": name, "verein": "AC Singen",
          "klasse": "3", "laufnr": 0, "fahrzeit": "00:42,00", "strafzeit": "0",
          "gesamtzeit": "00:42,00", "gesamtzeit_hs": 4200}],
        "2026-08-10", "Testrennen")


class MitGit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not _git_vorhanden():
            raise unittest.SkipTest("Git ist nicht verfügbar.")

    def setUp(self):
        self.basis = tempfile.mkdtemp(prefix="zeitmessung-git-")
        self.fern = os.path.join(self.basis, "fern.git")
        _git(["init", "--bare", "-b", "main", self.fern], self.basis)

    def tearDown(self):
        shutil.rmtree(self.basis, ignore_errors=True)

    def _klon(self, name, branch=None):
        ordner = os.path.join(self.basis, name)
        _git(["clone", self.fern, ordner], self.basis)
        _git(["config", "user.email", "test@test"], ordner)
        _git(["config", "user.name", "Test"], ordner)
        if branch:
            _git(["checkout", "-b", branch], ordner)
        return ordner

    def _daten_anlegen(self, ordner):
        os.makedirs(os.path.join(ordner, "data", "ergebnisse"), exist_ok=True)
        with open(os.path.join(ordner, "data", "livedata.json"), "w",
                  encoding="utf-8") as f:
            json.dump(lt.leerer_stand(), f)
        _git(["add", "-A"], ordner)
        _git(["commit", "-m", "Start"], ordner)

    def _fern_inhalt(self, pfad, branch="main"):
        ergebnis = _git(["show", f"{branch}:{pfad}"], self.fern)
        return ergebnis.stdout if ergebnis.returncode == 0 else None

    def _einstellungen(self, arbeit, live=""):
        return Einstellungen(datei=None, werte={
            "livetiming": True, "veroeffentlichen": True,
            "livedata_datei": os.path.join(arbeit, "data", "livedata.json"),
            "archiv_ordner": os.path.join(arbeit, "data", "ergebnisse"),
            "arbeits_repo": arbeit, "live_repo": live, "push_umgebung": ""})

    def _schreiben_und_veroeffentlichen(self, einst, daten=None):
        daten = daten or _beispieldaten()
        lt.schreibe_livedata(einst.livedata_datei, daten)
        lt.archiviere(einst.archiv_ordner, daten)
        return lt.veroeffentliche(einst, "Zwischenstand",
                                  [einst.livedata_datei, einst.archiv_ordner])


class EinOrdner(MitGit):
    """Die Zeitnahme mit eigenem Klon - unabhängig von der Webseiten-Pflege."""

    def setUp(self):
        super().setUp()
        self.eigen = self._klon("zeitnahme")
        self._daten_anlegen(self.eigen)
        _git(["push", "-u", "origin", "main"], self.eigen)
        self.einst = self._einstellungen(self.eigen)

    def test_zweiter_ordner_ist_nicht_noetig(self):
        self.assertTrue(self.einst.veroeffentlichen_an(),
                        "ein Ordner muss genügen")

    def test_ergebnisse_kommen_an(self):
        erfolg, meldung = self._schreiben_und_veroeffentlichen(self.einst)
        self.assertTrue(erfolg, meldung)
        inhalt = self._fern_inhalt("data/livedata.json")
        self.assertIsNotNone(inhalt)
        self.assertEqual(len(json.loads(inhalt)["results"]), 1)

    def test_archiv_kommt_mit(self):
        self._schreiben_und_veroeffentlichen(self.einst)
        self.assertIsNotNone(self._fern_inhalt("data/ergebnisse/2026-08-10.json"))
        self.assertIsNotNone(self._fern_inhalt("data/ergebnisse/index.json"))

    def test_zweiter_durchgang_aktualisiert(self):
        self._schreiben_und_veroeffentlichen(self.einst)
        erfolg, _ = self._schreiben_und_veroeffentlichen(
            self.einst, _beispieldaten("8", "Berta"))
        self.assertTrue(erfolg)
        ergebnisse = json.loads(self._fern_inhalt("data/livedata.json"))["results"]
        self.assertEqual(ergebnisse[0]["name"], "Berta")

    def test_ohne_aenderung_wird_nicht_gepusht(self):
        self._schreiben_und_veroeffentlichen(self.einst)
        vorher = _git(["rev-parse", "main"], self.fern).stdout.strip()
        erfolg, meldung = self._schreiben_und_veroeffentlichen(self.einst)
        self.assertTrue(erfolg)
        self.assertIn("nichts", meldung)
        self.assertEqual(_git(["rev-parse", "main"], self.fern).stdout.strip(),
                         vorher, "ohne neue Zeiten darf nichts hochgeladen werden")

    def test_nur_die_ergebnisdateien_gehen_mit(self):
        """Auch wenn im Ordner noch etwas anderes herumliegt."""
        with open(os.path.join(self.eigen, "notizen.txt"), "w") as f:
            f.write("nicht veroeffentlichen")
        self._schreiben_und_veroeffentlichen(self.einst)
        self.assertIsNone(self._fern_inhalt("notizen.txt"))


class ZweiOrdner(MitGit):
    """Getrennter Arbeits- und Live-Stand wie bei MCH Singen."""

    def setUp(self):
        super().setUp()
        self.live = self._klon("live")
        self._daten_anlegen(self.live)
        _git(["push", "-u", "origin", "main"], self.live)
        # Arbeitsstand als zweiter Arbeitsordner desselben Repos
        self.arbeit = os.path.join(self.basis, "arbeit")
        _git(["worktree", "add", "-b", "arbeit", self.arbeit], self.live)
        self.einst = self._einstellungen(self.arbeit, self.live)

    def test_ergebnisse_kommen_an(self):
        erfolg, meldung = self._schreiben_und_veroeffentlichen(self.einst)
        self.assertTrue(erfolg, meldung)
        inhalt = self._fern_inhalt("data/livedata.json")
        self.assertEqual(len(json.loads(inhalt)["results"]), 1)

    def test_arbeitsstand_geht_nicht_mit_live(self):
        """Der entscheidende Punkt: ein halbfertiger Umbau der Webseite darf
        durch eine Ergebnis-Veröffentlichung nicht online gehen."""
        with open(os.path.join(self.arbeit, "umbau.html"), "w") as f:
            f.write("<p>halbfertig</p>")
        _git(["add", "umbau.html"], self.arbeit)
        _git(["commit", "-m", "Umbau, noch nicht fertig"], self.arbeit)

        erfolg, meldung = self._schreiben_und_veroeffentlichen(self.einst)
        self.assertTrue(erfolg, meldung)
        self.assertIsNotNone(self._fern_inhalt("data/livedata.json"))
        self.assertIsNone(self._fern_inhalt("umbau.html"),
                          "der Arbeitsstand darf NICHT live gegangen sein")


class FehlendeEinstellungen(MitGit):

    def test_ohne_ordner_kommt_eine_klare_meldung(self):
        einst = self._einstellungen("")
        erfolg, meldung = lt.veroeffentliche(einst, "x", ["irgendwas"])
        self.assertFalse(erfolg)
        self.assertIn("Ergebnisdateien", meldung)

    def test_zweiter_ordner_falsch_eingetragen(self):
        eigen = self._klon("zeitnahme")
        self._daten_anlegen(eigen)
        einst = self._einstellungen(eigen, os.path.join(self.basis, "gibtesnicht"))
        erfolg, meldung = lt.veroeffentliche(
            einst, "x", [os.path.join(eigen, "data", "livedata.json")])
        self.assertFalse(erfolg)
        self.assertIn("gibt es nicht", meldung)


if __name__ == "__main__":
    unittest.main()
