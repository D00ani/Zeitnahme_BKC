# -*- coding: utf-8 -*-
"""
Einstellungsfenster.

Baut sich vollständig aus der Feldbeschreibung in ``einstellungen.FELDER``
auf - eine neue Einstellung dort einzutragen genügt, das Fenster kennt sie
dann automatisch.

Zwei Dinge sind bewusst anders als früher:

* **"Abbruch" verwirft nur.** Im alten Programm hing am Abbruch-Knopf
  versehentlich das Zurücksetzen auf Werkseinstellungen - ein Fehlklick hat
  Klassen, Vereine und den Lichtschranken-Port überschrieben.
* **Zurücksetzen fragt nach** und speichert erst mit "Speichern".
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import ausdruck, lichtschranke
from ..einstellungen import FELDER, GRUPPEN, TYPEN
from . import stil


class Einstellungsfenster(tk.Toplevel):

    def __init__(self, elternteil, einstellungen, bei_speichern):
        super().__init__(elternteil)
        self.einst = einstellungen
        self.bei_speichern = bei_speichern
        self.variablen = {}

        self.title("Einstellungen")
        self.configure(background=stil.HINTERGRUND)
        self.transient(elternteil)
        self.protocol("WM_DELETE_WINDOW", self._abbruch)

        self._baue()
        self._werte_laden()
        self.bind("<Escape>", lambda _: self._abbruch())

    # ------------------------------------------------------------------
    def _baue(self):
        rahmen = ttk.Frame(self, padding=12)
        rahmen.pack(fill="both", expand=True)

        self.mappen = ttk.Notebook(rahmen)
        self.mappen.pack(fill="both", expand=True)

        seiten = {}
        for gruppe in GRUPPEN:
            seite = ttk.Frame(self.mappen, padding=14)
            self.mappen.add(seite, text=gruppe)
            seiten[gruppe] = seite
            seite.columnconfigure(1, weight=1)

        zeilen = {gruppe: 0 for gruppe in GRUPPEN}
        for schluessel, gruppe, beschriftung, typ, standard, hinweis in FELDER:
            seite = seiten[gruppe]
            zeile = zeilen[gruppe]
            self._baue_feld(seite, zeile, schluessel, beschriftung, typ, hinweis)
            zeilen[gruppe] = zeile + 1

        # --- Knopfleiste ---------------------------------------------------
        knoepfe = ttk.Frame(rahmen)
        knoepfe.pack(fill="x", pady=(14, 0))
        ttk.Button(knoepfe, text="Einstellungen speichern", width=24,
                   command=self._speichern).pack(side="left")
        ttk.Button(knoepfe, text="Abbruch", width=12,
                   command=self._abbruch).pack(side="left", padx=(8, 0))
        ttk.Button(knoepfe, text="Alles auf Standardwerte setzen", width=28,
                   command=self._zuruecksetzen).pack(side="right")

        self.var_meldung = tk.StringVar()
        ttk.Label(rahmen, textvariable=self.var_meldung,
                  style="Hinweis.TLabel").pack(fill="x", pady=(8, 0))

    def _baue_feld(self, seite, zeile, schluessel, beschriftung, typ, hinweis):
        ttk.Label(seite, text=beschriftung).grid(
            row=zeile, column=0, sticky="w", padx=(0, 12), pady=4)

        if typ == "bool":
            var = tk.BooleanVar()
            ttk.Checkbutton(seite, variable=var).grid(
                row=zeile, column=1, sticky="w", pady=4)
        elif typ == "port":
            var = tk.StringVar()
            ports = lichtschranke.verfuegbare_ports()
            feld = ttk.Combobox(seite, textvariable=var, values=ports, width=16)
            feld.grid(row=zeile, column=1, sticky="w", pady=4)
            ttk.Button(seite, text="Ports prüfen", width=14,
                       command=lambda f=feld: self._ports_pruefen(f)).grid(
                row=zeile, column=2, sticky="w", padx=(8, 0))
        elif typ == "drucker":
            var = tk.StringVar()
            feld = ttk.Combobox(seite, textvariable=var,
                                values=self._druckerauswahl(), width=40)
            feld.grid(row=zeile, column=1, sticky="w", pady=4)
            ttk.Button(seite, text="Drucker prüfen", width=14,
                       command=lambda f=feld: self._drucker_pruefen(f)).grid(
                row=zeile, column=2, sticky="w", padx=(8, 0))
        elif typ in ("datei", "ordner"):
            var = tk.StringVar()
            ttk.Entry(seite, textvariable=var, width=52).grid(
                row=zeile, column=1, sticky="ew", pady=4)
            ttk.Button(seite, text="Durchsuchen", width=14,
                       command=lambda v=var, t=typ: self._waehlen(v, t)).grid(
                row=zeile, column=2, sticky="w", padx=(8, 0))
        elif typ == "int":
            var = tk.StringVar()
            ttk.Entry(seite, textvariable=var, width=10,
                      justify="right").grid(row=zeile, column=1, sticky="w", pady=4)
        else:
            var = tk.StringVar()
            breite = 52 if typ == "liste" else 34
            ttk.Entry(seite, textvariable=var, width=breite).grid(
                row=zeile, column=1, sticky="ew", pady=4)

        if hinweis:
            ttk.Label(seite, text=hinweis, style="Leise.TLabel").grid(
                row=zeile, column=3, sticky="w", padx=(10, 0))
        self.variablen[schluessel] = var

    # ------------------------------------------------------------------
    def _ports_pruefen(self, feld):
        ports = lichtschranke.verfuegbare_ports()
        feld.configure(values=ports)
        beschreibungen = lichtschranke.port_beschreibungen()
        if not ports:
            self.var_meldung.set("Es ist keine serielle Schnittstelle vorhanden.")
            return
        zeilen = [beschreibungen.get(p, p) for p in ports]
        self.var_meldung.set("Gefunden: " + " | ".join(zeilen))

    def _druckerauswahl(self):
        """Alle eingerichteten Drucker; der leere erste Eintrag steht für
        „der Windows-Standarddrucker“, damit es auch dann stimmt, wenn am
        Renntag ein anderes Gerät angeschlossen ist."""
        return [""] + ausdruck.drucker_liste()

    def _drucker_pruefen(self, feld):
        drucker = ausdruck.drucker_liste()
        feld.configure(values=[""] + drucker)
        standard = ausdruck.standarddrucker()
        if not drucker:
            self.var_meldung.set("Es ist kein Drucker eingerichtet.")
            return
        self.var_meldung.set(
            f"{len(drucker)} Drucker gefunden. Standard: "
            f"{standard or 'keiner'}. Leeres Feld = Standarddrucker.")

    def _waehlen(self, var, typ):
        vorgabe = var.get().strip()
        if typ == "ordner":
            pfad = filedialog.askdirectory(parent=self, initialdir=vorgabe or None)
        else:
            pfad = filedialog.askopenfilename(parent=self,
                                              initialdir=vorgabe or None)
        if pfad:
            # tkinter liefert immer Schrägstriche zurück; unter Windows sind
            # Rückstriche gewohnter, unter Linux wären sie falsch.
            var.set(os.path.normpath(pfad))

    # ------------------------------------------------------------------
    def _werte_laden(self):
        for schluessel, var in self.variablen.items():
            wert = getattr(self.einst, schluessel)
            if isinstance(var, tk.BooleanVar):
                var.set(bool(wert))
            else:
                var.set(str(wert))

    def _speichern(self):
        fehlerhaft = []
        for schluessel, var in self.variablen.items():
            wert = var.get()
            if TYPEN[schluessel] == "int" and not str(wert).strip().lstrip("-").isdigit():
                fehlerhaft.append(schluessel)
                continue
            self.einst.setzen(schluessel, wert)
        if fehlerhaft:
            self.var_meldung.set(
                "Diese Felder brauchen eine ganze Zahl: " + ", ".join(fehlerhaft))
            return
        self.einst.speichern()
        self.bei_speichern()
        self.destroy()

    def _abbruch(self):
        """Verwirft die Änderungen. Gespeichert wird hier ausdrücklich
        **nichts**."""
        self.destroy()

    def _zuruecksetzen(self):
        if not messagebox.askyesno(
                "Standardwerte",
                "Wirklich alle Einstellungen auf die Standardwerte "
                "zurücksetzen?\n\nKlassen, Vereine, Pfade und der "
                "Lichtschranken-Port gehen dabei verloren.\n\n"
                "Gespeichert wird erst, wenn du danach auf "
                "„Einstellungen speichern“ klickst.",
                parent=self):
            return
        self.einst.auf_standard()
        self._werte_laden()
        self.var_meldung.set("Standardwerte eingetragen - noch nicht gespeichert.")
