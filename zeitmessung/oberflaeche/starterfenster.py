# -*- coding: utf-8 -*-
"""
Starterfenster - Fahrerdaten eingeben und die Läufe auswerten.

Dasselbe Fenster in drei Zuständen, genau wie früher:

``erfassen``   vor dem Start: Startnummer, Name, Klasse, Verein
``lauf1``      nach dem 1. Wertungslauf: Pylonen und Fahrfehler eintragen
``ende``       nach dem 2. Wertungslauf: eintragen, drucken, weiter

Die Zeitfelder rechnen bei jeder Eingabe sofort nach - Strafzeit und Summe
stehen also immer aktuell da, ohne dass man ein Feld verlassen muss.
"""
import tkinter as tk
from tkinter import ttk

from .. import zeit
from . import stil

ERFASSEN = "erfassen"
LAUF1 = "lauf1"
ENDE = "ende"


class Starterfenster(tk.Toplevel):
    """Wird einmal erzeugt und danach nur noch ein- und ausgeblendet."""

    def __init__(self, elternteil, einstellungen, bei_weiter, bei_drucken,
                 bei_wiederholen):
        super().__init__(elternteil)
        self.einst = einstellungen
        self.bei_weiter = bei_weiter
        self.bei_drucken = bei_drucken
        self.bei_wiederholen = bei_wiederholen
        self.ergebnis = None
        self.zustand = ERFASSEN
        self.gedruckt = False

        self.title("Starter")
        self.configure(background=stil.HINTERGRUND)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # nicht wegklickbar
        self.transient(elternteil)
        self.withdraw()

        self._baue()

    # ------------------------------------------------------------------
    def _baue(self):
        rahmen = ttk.Frame(self, padding=12)
        rahmen.pack(fill="both", expand=True)

        # --- Fahrerdaten ---------------------------------------------------
        kopf = ttk.LabelFrame(rahmen, text="Starter", padding=10)
        kopf.pack(fill="x")

        self.var_nummer = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_klasse = tk.StringVar()
        self.var_verein = tk.StringVar()

        ttk.Label(kopf, text="Starter Nr.").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.feld_nummer = ttk.Entry(kopf, textvariable=self.var_nummer, width=8)
        self.feld_nummer.grid(row=0, column=1, sticky="w", pady=3)

        ttk.Label(kopf, text="Name").grid(row=0, column=2, sticky="w", padx=(20, 8), pady=3)
        self.feld_name = ttk.Entry(kopf, textvariable=self.var_name, width=28)
        self.feld_name.grid(row=0, column=3, sticky="w", pady=3)

        ttk.Label(kopf, text="Klasse").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        self.feld_klasse = ttk.Combobox(kopf, textvariable=self.var_klasse, width=6,
                                        values=self.einst.klassen_liste())
        self.feld_klasse.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(kopf, text="Verein").grid(row=1, column=2, sticky="w", padx=(20, 8), pady=3)
        self.feld_verein = ttk.Combobox(kopf, textvariable=self.var_verein, width=26,
                                        values=self.einst.vereine_liste())
        self.feld_verein.grid(row=1, column=3, sticky="w", pady=3)

        # --- Läufe ---------------------------------------------------------
        tabelle = ttk.LabelFrame(rahmen, text="Läufe", padding=10)
        tabelle.pack(fill="x", pady=(12, 0))

        ueberschriften = ["", "Gültig", "Anz. Pylonen", "Fehler", "Zeit",
                          "Strafzeit", "Summe"]
        for spalte, text in enumerate(ueberschriften):
            ttk.Label(tabelle, text=text, style="Leise.TLabel").grid(
                row=0, column=spalte, padx=6, pady=(0, 4), sticky="w")

        self.zeilen = {}
        for zeile, nummer in ((1, 1), (2, 2)):
            self.zeilen[nummer] = self._baue_lauf_zeile(tabelle, zeile, nummer)

        # Summenzeile
        ttk.Separator(tabelle, orient="horizontal").grid(
            row=3, column=0, columnspan=7, sticky="ew", pady=6)
        ttk.Label(tabelle, text="Gesamt", style="Ueberschrift.TLabel").grid(
            row=4, column=0, padx=6, sticky="w")
        self.var_zeit_gesamt = tk.StringVar(value=zeit.NULLZEIT)
        self.var_strafzeit_gesamt = tk.StringVar(value="0")
        self.var_summe_gesamt = tk.StringVar(value=zeit.NULLZEIT)
        ttk.Label(tabelle, textvariable=self.var_zeit_gesamt,
                  font=stil.SCHRIFT_TABELLE).grid(row=4, column=4, padx=6, sticky="w")
        ttk.Label(tabelle, textvariable=self.var_strafzeit_gesamt,
                  font=stil.SCHRIFT_TABELLE).grid(row=4, column=5, padx=6, sticky="w")
        ttk.Label(tabelle, textvariable=self.var_summe_gesamt,
                  font=(stil.SCHRIFTART, 14, "bold")).grid(
            row=4, column=6, padx=6, sticky="w")

        # --- Knöpfe --------------------------------------------------------
        knoepfe = ttk.Frame(rahmen)
        knoepfe.pack(fill="x", pady=(14, 0))

        self.knopf_weiter = ttk.Button(knoepfe, text="Weiter", width=14,
                                       command=self._weiter)
        self.knopf_weiter.pack(side="left")
        self.knopf_drucken = ttk.Button(knoepfe, text="Drucken", width=14,
                                        command=self._drucken)
        self.knopf_drucken.pack(side="left", padx=(8, 0))
        self.knopf_wiederholen = ttk.Button(knoepfe, text="Wiederholen", width=14,
                                            command=self._wiederholen)
        self.knopf_wiederholen.pack(side="left", padx=(8, 0))
        ttk.Button(knoepfe, text="Abbruch", width=12,
                   command=self._abbruch).pack(side="right")

        self.var_meldung = tk.StringVar()
        self.meldung = ttk.Label(rahmen, textvariable=self.var_meldung,
                                 style="Fehler.TLabel")
        self.meldung.pack(fill="x", pady=(8, 0))

    def _baue_lauf_zeile(self, elternteil, zeile, nummer):
        felder = {}
        ttk.Label(elternteil, text=f"{nummer}. Lauf",
                  font=stil.SCHRIFT_FETT).grid(row=zeile, column=0, padx=6,
                                               pady=3, sticky="w")

        felder["gueltig"] = tk.BooleanVar(value=True)
        knopf = ttk.Checkbutton(elternteil, variable=felder["gueltig"],
                                command=self._gueltigkeit_geaendert)
        knopf.grid(row=zeile, column=1, padx=6, pady=3)
        felder["gueltig_knopf"] = knopf

        for spalte, name, breite in ((2, "pylonen", 6), (3, "fehler", 6)):
            var = tk.StringVar(value="0")
            feld = ttk.Entry(elternteil, textvariable=var, width=breite,
                             justify="right")
            feld.grid(row=zeile, column=spalte, padx=6, pady=3, sticky="w")
            var.trace_add("write", lambda *_: self._nachrechnen())
            felder[name] = var
            felder[name + "_feld"] = feld

        for spalte, name in ((4, "zeit"), (5, "strafzeit"), (6, "summe")):
            var = tk.StringVar(value=zeit.NULLZEIT if name != "strafzeit" else "0")
            ttk.Label(elternteil, textvariable=var,
                      font=stil.SCHRIFT_TABELLE).grid(row=zeile, column=spalte,
                                                      padx=6, pady=3, sticky="w")
            felder[name] = var
        return felder

    # ------------------------------------------------------------------
    # Öffnen in den drei Zuständen
    # ------------------------------------------------------------------
    def erfassen_oeffnen(self, ergebnis, vorschlag_nummer=""):
        """Vor dem Start: nur die Fahrerdaten."""
        self.ergebnis = ergebnis
        self.zustand = ERFASSEN
        self.gedruckt = False
        self.var_nummer.set(ergebnis.startnummer or vorschlag_nummer)
        self.var_name.set(ergebnis.name)
        self.var_klasse.set(ergebnis.klasse)
        self.var_verein.set(ergebnis.verein)
        for nummer in (1, 2):
            self.zeilen[nummer]["pylonen"].set("0")
            self.zeilen[nummer]["fehler"].set("0")
            self.zeilen[nummer]["gueltig"].set(True)
        self._nachrechnen()
        self._zustand_anwenden()
        self._zeigen(self.feld_nummer)

    def lauf_oeffnen(self, ergebnis, lauf):
        """Nach einem Wertungslauf: Pylonen und Fehler eintragen."""
        self.ergebnis = ergebnis
        self.zustand = LAUF1 if lauf == 1 else ENDE
        self.var_nummer.set(ergebnis.startnummer)
        self.var_name.set(ergebnis.name)
        self.var_klasse.set(ergebnis.klasse)
        self.var_verein.set(ergebnis.verein)
        self._nachrechnen()
        self._zustand_anwenden()
        self._zeigen(self.zeilen[lauf]["pylonen_feld"])

    def _zeigen(self, feld):
        self.deiconify()
        self.lift()
        self.focus_force()
        feld.focus_set()
        try:
            feld.selection_range(0, "end")
        except tk.TclError:
            pass

    def verbergen(self):
        self.withdraw()

    def _zustand_anwenden(self):
        """Welche Felder und Knöpfe sind gerade sinnvoll?"""
        erfassen = self.zustand == ERFASSEN
        ende = self.zustand == ENDE
        drucken_moeglich = ende and bool(self.einst.ergebnis_drucken)

        for nummer in (1, 2):
            zeile = self.zeilen[nummer]
            aktiv = (not erfassen) and (
                nummer == 1 if self.zustand == LAUF1 else nummer == 2)
            zustand = "normal" if aktiv else "disabled"
            zeile["pylonen_feld"].configure(state=zustand)
            zeile["fehler_feld"].configure(state=zustand)
            zeile["gueltig_knopf"].configure(state=zustand)

        self.knopf_drucken.pack_forget()
        self.knopf_wiederholen.pack_forget()
        if drucken_moeglich:
            # Im Übungsbetrieb soll auf dem Knopf stehen, was er wirklich tut.
            self.knopf_drucken.configure(
                text="PDF-Vorschau" if self.einst.vorschau_statt_druck
                else "Drucken")
            self.knopf_drucken.pack(side="left", padx=(8, 0))
        if not erfassen:
            self.knopf_wiederholen.pack(side="left", padx=(8, 0))

        # Erst drucken, dann weiter - wie früher
        muss_erst_drucken = drucken_moeglich and not self.gedruckt
        self.knopf_weiter.configure(
            state="disabled" if muss_erst_drucken else "normal")
        self.var_meldung.set("")

    def _gueltigkeit_geaendert(self):
        ungueltig = [n for n in (1, 2) if not self.zeilen[n]["gueltig"].get()]
        if ungueltig:
            self.knopf_weiter.configure(state="disabled")
            self.var_meldung.set(
                f"{ungueltig[0]}. Lauf ist als ungültig markiert - "
                f"mit „Wiederholen“ noch einmal fahren.")
        else:
            self.var_meldung.set("")
            self._zustand_anwenden()

    # ------------------------------------------------------------------
    def _zahl(self, text):
        text = str(text or "").strip()
        return int(text) if text.isdigit() else 0

    def _nachrechnen(self):
        """Übernimmt die Eingaben ins Ergebnis und schreibt die Summen
        zurück in die Anzeige."""
        if self.ergebnis is None:
            return
        self.ergebnis.sek_pylone = int(self.einst.strafzeit_pylone)
        self.ergebnis.sek_fehler = int(self.einst.strafzeit_fehler)
        for nummer in (1, 2):
            lauf = self.ergebnis.lauf(nummer)
            lauf.pylonen = self._zahl(self.zeilen[nummer]["pylonen"].get())
            lauf.fehler = self._zahl(self.zeilen[nummer]["fehler"].get())
            lauf.gueltig = bool(self.zeilen[nummer]["gueltig"].get())
            self.zeilen[nummer]["zeit"].set(zeit.formatiere(lauf.fahrzeit))
            self.zeilen[nummer]["strafzeit"].set(
                str(self.ergebnis.strafzeit_sekunden(nummer)))
            self.zeilen[nummer]["summe"].set(
                zeit.formatiere(self.ergebnis.summe(nummer)))
        self.var_zeit_gesamt.set(zeit.formatiere(self.ergebnis.fahrzeit_gesamt()))
        self.var_strafzeit_gesamt.set(str(self.ergebnis.strafzeit_gesamt_sekunden()))
        self.var_summe_gesamt.set(zeit.formatiere(self.ergebnis.gesamt()))

    def _daten_uebernehmen(self):
        """Fahrerdaten aus den Feldern ins Ergebnis. Gibt einen Fehlertext
        zurück, wenn etwas Pflichtiges fehlt."""
        self.ergebnis.startnummer = self.var_nummer.get().strip()
        self.ergebnis.name = self.var_name.get().strip()
        self.ergebnis.klasse = self.var_klasse.get().strip()
        self.ergebnis.verein = self.var_verein.get().strip()
        if not self.einst.starter_eingabe:
            return ""
        for wert, bezeichnung in ((self.ergebnis.startnummer, "Startnummer"),
                                  (self.ergebnis.name, "Name"),
                                  (self.ergebnis.klasse, "Klasse"),
                                  (self.ergebnis.verein, "Verein")):
            if not wert:
                return f"{bezeichnung} fehlt."
        return ""

    # ------------------------------------------------------------------
    def _weiter(self):
        fehler = self._daten_uebernehmen()
        if fehler:
            self.var_meldung.set(fehler)
            return
        self._nachrechnen()
        self.bei_weiter(self.zustand, self.ergebnis)

    def _drucken(self):
        fehler = self._daten_uebernehmen()
        if fehler:
            self.var_meldung.set(fehler)
            return
        self._nachrechnen()
        if self.bei_drucken(self.ergebnis):
            self.gedruckt = True
            self.knopf_weiter.configure(state="normal")
            self.knopf_weiter.focus_set()

    def _wiederholen(self):
        ungueltig = [n for n in (1, 2) if not self.zeilen[n]["gueltig"].get()]
        if not ungueltig:
            self.var_meldung.set(
                "Zum Wiederholen zuerst den Haken bei „Gültig“ entfernen.")
            return
        lauf = ungueltig[0]
        self.zeilen[lauf]["gueltig"].set(True)
        self.zeilen[lauf]["pylonen"].set("0")
        self.zeilen[lauf]["fehler"].set("0")
        self.ergebnis.zeit_setzen(lauf, 0)
        self._nachrechnen()
        self.bei_wiederholen(lauf, self.ergebnis)

    def _abbruch(self):
        """Zurück zum Hauptfenster, ohne zu speichern."""
        self.verbergen()
        self.master.focus_force()
