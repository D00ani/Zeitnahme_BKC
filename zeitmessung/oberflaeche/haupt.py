# -*- coding: utf-8 -*-
"""
Hauptfenster - Stoppuhr, Bedienung, Verlauf.

Hier laufen alle Teile zusammen: die Ablaufsteuerung liefert Ereignisse,
daraufhin wird angezeigt, gespeichert, gedruckt und - wenn eingeschaltet -
das Live-Timing aktualisiert.

Die Anzeige wird von einem ruhigen Takt (alle 50 ms) aufgefrischt. Das alte
Programm hatte an dieser Stelle eine Endlosschleife mit ``DoEvents``, die
einen Prozessorkern dauerhaft ausgelastet und sich selbst verschachtelt
aufgerufen hat.
"""
import os
import sqlite3
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .. import ablauf as ablauf_modul
from .. import einstellungen as einstellungen_modul
from .. import ausdruck, datenbank as db_modul, lichtschranke as ls_modul
from .. import livetiming as lt_modul, selbsttest as selbsttest_modul
from .. import sperre as sperre_modul, wertung, zeit
from . import stil
from .einstellungsfenster import Einstellungsfenster
from .starterfenster import ENDE, ERFASSEN, LAUF1, Starterfenster

TAKT_MS = 50


class Anzeigetafel(tk.Toplevel):
    """Großes Fenster für den zweiten Bildschirm an der Strecke."""

    def __init__(self, elternteil):
        super().__init__(elternteil)
        self.title("Anzeige")
        self.configure(background=stil.TAFEL_HINTERGRUND)
        self.geometry("960x420")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.label = tk.Label(self, text="00:00", fg=stil.TAFEL_SCHRIFT,
                              bg=stil.TAFEL_HINTERGRUND,
                              font=("Consolas", 200, "bold"))
        self.label.pack(fill="both", expand=True)
        self.bind("<Double-Button-1>", self._vollbild_umschalten)
        self._vollbild = False

    def _vollbild_umschalten(self, _=None):
        self._vollbild = not self._vollbild
        self.attributes("-fullscreen", self._vollbild)

    def zeige(self, text):
        if self.label["text"] != text:
            self.label.configure(text=text)


class Platzierungsfenster(tk.Toplevel):
    """Zeigt nach dem Drucken, wo der Fahrer gerade steht."""

    def __init__(self, elternteil):
        super().__init__(elternteil)
        self.title("Platzierung")
        self.configure(background=stil.HINTERGRUND)
        self.geometry("560x520")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        rahmen = ttk.Frame(self, padding=10)
        rahmen.pack(fill="both", expand=True)
        self.liste = tk.Listbox(rahmen, font=stil.SCHRIFT_TABELLE,
                                background=stil.FLAECHE, borderwidth=1,
                                relief="solid", activestyle="none")
        self.liste.pack(fill="both", expand=True)
        ttk.Button(rahmen, text="Schließen",
                   command=self.withdraw).pack(pady=(8, 0))
        self.withdraw()

    def zeige(self, zeilen):
        self.liste.delete(0, "end")
        for zeile in zeilen:
            self.liste.insert("end", zeile)
        self.deiconify()
        self.lift()


class Hauptfenster(tk.Tk):

    def __init__(self, einstellungen):
        super().__init__()
        self.einst = einstellungen
        self.title("Zeitmessung")
        stil.grundeinstellung(self)

        # Nur ein Programm je Datenbank - sonst schreiben zwei Fenster
        # nebeneinander Ergebnisse, ohne voneinander zu wissen.
        self.sperre = sperre_modul.Sperre(str(self.einst.datenbank))
        if not self.sperre.setzen():
            messagebox.showwarning(
                "Zeitmessung läuft bereits",
                f"Auf dieser Datenbank arbeitet schon ein anderes Fenster "
                f"(Prozess {self.sperre.wer_haelt_sie() or '?'}).\n\n"
                f"Dieses Fenster wird trotzdem geöffnet, speichert aber in "
                f"dieselbe Datei. Am Renntag sollte nur EINE Zeitmessung "
                f"laufen - das andere Fenster bitte schließen.",
                parent=None)

        self.db = self._datenbank_oeffnen()
        # Sicherungskopie bei jedem Start - wenn am Renntag etwas schiefgeht,
        # ist der Stand von vorhin noch da.
        try:
            self.sicherung = self.db.sicherung_anlegen()
        except (OSError, sqlite3.Error):
            self.sicherung = ""
        self.ablauf = ablauf_modul.Ablauf(self.einst)
        self.live = lt_modul.LiveTiming(self.einst)
        self.ergebnis = self._neues_ergebnis()
        self.lichtschranke = None

        self._halten_bis = 0.0        # bis wann die Zwischenzeit stehen bleibt
        self._haltetext = ""
        self._gespeichert_lauf2 = False
        self._takt_id = None          # laufender Anzeigetakt, zum Abbestellen
        self._beendet = False         # ab hier keine Signale mehr annehmen
        self._push_laeuft = False     # es veröffentlicht immer nur einer

        self._baue()
        self.tafel = Anzeigetafel(self)
        self.platzierung = Platzierungsfenster(self)
        self.starter = Starterfenster(self, self.einst, self._starter_weiter,
                                      self._starter_drucken,
                                      self._starter_wiederholen)

        self._tasten_binden()
        self._lichtschranke_starten()
        self._verlauf_laden()
        self._auffrischen_sofort()   # Balken, Schranke und Live-Anzeige füllen
        self._auffrischen()
        self.protocol("WM_DELETE_WINDOW", self._beenden)

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------
    def _datenbank_oeffnen(self):
        """Öffnet die Datenbank - und wird verständlich, wenn das nicht geht.

        Der häufigste Fall: die Datenbank liegt auf einem Stick oder einem
        Netzlaufwerk, das gerade nicht da ist. Ohne diese Behandlung stünde
        beim Start nur ein roher Systemfehler.
        """
        pfad = str(self.einst.datenbank)
        try:
            return db_modul.Datenbank(pfad)
        except (OSError, sqlite3.Error) as fehler:
            ausweich = os.path.join(einstellungen_modul.PROGRAMM_ORDNER,
                                    "daten", "zeitmessung.db")
            weiter = messagebox.askyesno(
                "Datenbank nicht erreichbar",
                f"Die eingestellte Datenbank lässt sich nicht öffnen:\n\n"
                f"{pfad}\n{fehler}\n\n"
                f"Liegt sie auf einem Stick oder Netzlaufwerk, das gerade "
                f"nicht angeschlossen ist?\n\n"
                f"Stattdessen die Datenbank neben dem Programm benutzen?\n"
                f"{ausweich}",
                parent=None)
            if not weiter:
                raise
            self.einst.datenbank = ausweich
            return db_modul.Datenbank(ausweich)

    def _neues_ergebnis(self):
        return wertung.Starterergebnis(
            sek_pylone=int(self.einst.strafzeit_pylone),
            sek_fehler=int(self.einst.strafzeit_fehler))

    def _baue(self):
        self._baue_menue()

        aussen = ttk.Frame(self, padding=12)
        aussen.pack(fill="both", expand=True)
        aussen.columnconfigure(0, weight=3)
        aussen.columnconfigure(1, weight=2)
        aussen.rowconfigure(3, weight=1)

        # --- Zustandsbalken -------------------------------------------------
        # Sagt in einem Satz, was gerade passiert. Vorher musste man drei
        # kleine Felder zusammenlesen, um zu merken, dass man im Training
        # steht und deshalb nichts gespeichert wird.
        self.balken = tk.Label(aussen, text="", anchor="w", padx=14, pady=10,
                               font=(stil.SCHRIFTART, 13, "bold"),
                               background=stil.RUHE_FLAECHE,
                               foreground=stil.SCHRIFT)
        self.balken.grid(row=0, column=0, columnspan=2, sticky="ew")

        # --- Lichtschranke: dauerhaft sichtbar, nicht nur als Meldung -------
        geraet = ttk.Frame(aussen, padding=(0, 8))
        geraet.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.var_schranke = tk.StringVar()
        self.anzeige_schranke = ttk.Label(geraet, textvariable=self.var_schranke)
        self.anzeige_schranke.pack(side="left")
        ttk.Button(geraet, text="Neu verbinden", width=16,
                   command=self._lichtschranke_starten).pack(side="left", padx=(10, 0))

        # --- Kopfbereich: Modus und Stoppuhr -------------------------------
        oben = ttk.Frame(aussen)
        oben.grid(row=2, column=0, columnspan=2, sticky="ew")

        modus = ttk.LabelFrame(oben, text="Was wird gemessen?", padding=10)
        modus.pack(side="left", fill="y")
        self.var_modus = tk.StringVar(value=ablauf_modul.TRAINING)
        for wert, text in ((ablauf_modul.TRAINING, "Training (T)"),
                           (ablauf_modul.EINFUEHRUNG, "Einführungsrunde (E)"),
                           (ablauf_modul.WERTUNG, "Wertungslauf (W)")):
            ttk.Radiobutton(modus, text=text, value=wert, variable=self.var_modus,
                            command=self._modus_gewaehlt).pack(anchor="w", pady=2)

        uhr = ttk.Frame(oben, padding=(20, 0))
        uhr.pack(side="left", fill="both", expand=True)
        self.var_zeit = tk.StringVar(value="00:00")
        tk.Label(uhr, textvariable=self.var_zeit, font=stil.SCHRIFT_ZEIT,
                 background=stil.HINTERGRUND, foreground=stil.SCHRIFT).pack()

        zaehler = ttk.Frame(oben)
        zaehler.pack(side="left", fill="y", padx=(10, 0))
        self.var_runde = tk.StringVar(value="0")
        self.var_restzeit = tk.StringVar(value="0")
        ttk.Label(zaehler, text="Runde:").grid(row=0, column=0, sticky="w")
        ttk.Label(zaehler, textvariable=self.var_runde,
                  font=stil.SCHRIFT_UEBERSCHRIFT).grid(row=0, column=1, sticky="w",
                                                       padx=(8, 0))
        self.beschriftung_restzeit = ttk.Label(zaehler,
                                               text="Training Restzeit (Minuten):")
        self.beschriftung_restzeit.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.wert_restzeit = ttk.Label(zaehler, textvariable=self.var_restzeit,
                                       font=stil.SCHRIFT_UEBERSCHRIFT)
        self.wert_restzeit.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(6, 0))

        # --- Knöpfe und Verlauf --------------------------------------------
        links = ttk.Frame(aussen)
        links.grid(row=3, column=0, sticky="nsew", pady=(14, 0))

        self.knopf_messen = ttk.Button(links, text="Start Training (F1)",
                                       style="Gross.TButton",
                                       command=self._ausloesen)
        self.knopf_messen.pack(fill="x", ipady=18)

        reihe = ttk.Frame(links)
        reihe.pack(fill="x", pady=(10, 0))
        # "Abbruch" klang nach "Programm beenden" - gemeint ist immer nur
        # der gerade laufende Lauf.
        ttk.Button(reihe, text="Diesen Lauf verwerfen (ESC)",
                   command=self._abbrechen).pack(side="left")
        self.knopf_zwischenzeit = ttk.Button(reihe, text="Zwischenzeit (F5)",
                                             command=self._zwischenzeit_halten)
        self.knopf_aktuelle_zeit = ttk.Button(reihe, text="Aktuelle Zeit (F4)",
                                              command=self._zwischenzeit_aus)
        if not self.einst.eine_lichtschranke:
            self.knopf_zwischenzeit.pack(side="left", padx=(8, 0))
            self.knopf_aktuelle_zeit.pack(side="left", padx=(8, 0))

        ttk.Button(links, text="Nächsten Starter beginnen",
                   command=self._naechster_starter).pack(fill="x", pady=(10, 0))

        rechts = ttk.LabelFrame(aussen, text="Verlauf", padding=8)
        rechts.grid(row=3, column=1, sticky="nsew", pady=(14, 0), padx=(14, 0))
        self.verlauf = tk.Listbox(rechts, font=stil.SCHRIFT_TABELLE,
                                  background=stil.FLAECHE, borderwidth=1,
                                  relief="solid", activestyle="none")
        self.verlauf.pack(side="left", fill="both", expand=True)
        rollbalken = ttk.Scrollbar(rechts, orient="vertical",
                                   command=self.verlauf.yview)
        rollbalken.pack(side="right", fill="y")
        self.verlauf.configure(yscrollcommand=rollbalken.set)

        # --- Statuszeile ----------------------------------------------------
        self.var_status = tk.StringVar()
        self.var_live = tk.StringVar()
        leiste = ttk.Frame(self, padding=(12, 4))
        leiste.pack(fill="x", side="bottom")
        ttk.Label(leiste, textvariable=self.var_status,
                  style="Leise.TLabel").pack(side="left")
        ttk.Label(leiste, textvariable=self.var_live,
                  style="Leise.TLabel").pack(side="right")

    def _baue_menue(self):
        leiste = tk.Menu(self)
        datei = tk.Menu(leiste, tearoff=0)
        datei.add_command(label="Einstellungen …", command=self._einstellungen)
        datei.add_separator()
        datei.add_command(label="Ergebnisse aus altem Programm übernehmen …",
                          command=self._altdaten_uebernehmen)
        datei.add_separator()
        datei.add_command(label="Beenden", command=self._beenden)
        leiste.add_cascade(label="Datei", menu=datei)

        ergebnisse = tk.Menu(leiste, tearoff=0)
        ergebnisse.add_command(label="Ergebnisse heute …",
                               command=self._tagesuebersicht)
        leiste.add_cascade(label="Ergebnisse", menu=ergebnisse)

        ansicht = tk.Menu(leiste, tearoff=0)
        ansicht.add_command(label="Anzeigetafel zeigen",
                            command=lambda: self.tafel.deiconify())
        ansicht.add_command(label="Anzeigetafel verbergen",
                            command=lambda: self.tafel.withdraw())
        ansicht.add_separator()
        ansicht.add_command(label="Lichtschranke neu verbinden",
                            command=self._lichtschranke_starten)
        leiste.add_cascade(label="Ansicht", menu=ansicht)

        self.menue_live = tk.Menu(leiste, tearoff=0)
        self.menue_live.add_command(label="Stand jetzt schreiben",
                                    command=lambda: self._live_aktualisieren(True))
        self.menue_live.add_command(label="Jetzt veröffentlichen",
                                    command=self._jetzt_veroeffentlichen)
        leiste.add_cascade(label="Live-Timing", menu=self.menue_live)
        self.leiste = leiste

        hilfe = tk.Menu(leiste, tearoff=0)
        hilfe.add_command(label="Selbsttest – ist alles bereit?",
                          command=self._selbsttest)
        hilfe.add_separator()
        hilfe.add_command(label="Kurzanleitung", command=self._hilfe)
        leiste.add_cascade(label="Hilfe", menu=hilfe)
        self.configure(menu=leiste)

    def _tasten_binden(self):
        self.bind_all("<F1>", lambda _: self._ausloesen())
        self.bind_all("<Escape>", lambda _: self._abbrechen())
        self.bind_all("<F4>", lambda _: self._zwischenzeit_aus())
        for taste in ("<F5>", "<F6>", "<F7>", "<F8>"):
            self.bind_all(taste, lambda _: self._zwischenzeit_halten())
        for taste, modus in (("t", ablauf_modul.TRAINING),
                             ("e", ablauf_modul.EINFUEHRUNG),
                             ("w", ablauf_modul.WERTUNG)):
            self.bind(taste, lambda _, m=modus: self._modus_setzen(m))
            self.bind(taste.upper(), lambda _, m=modus: self._modus_setzen(m))

    # ------------------------------------------------------------------
    # Lichtschranke
    # ------------------------------------------------------------------
    def _lichtschranke_starten(self):
        if self.lichtschranke:
            self.lichtschranke.schliessen()
            self.lichtschranke = None
        port = str(self.einst.serieller_port).strip()
        if not port:
            self._status("Keine Lichtschranke eingestellt - Messung mit F1.")
            return
        self.lichtschranke = ls_modul.Lichtschranke(
            port, self.einst.baudrate,
            bei_signal=self._signal_aus_faden,
            bei_fehler=lambda m: self.after(0, lambda: self._status(m)))
        if self.lichtschranke.oeffnen():
            self._status(f"Lichtschranke an {port} verbunden. "
                         f"Die Anzeigetafel der Lichtschranke muss ausgeschaltet bleiben.")
        self._schranke_zeichnen()

    def _signal_aus_faden(self, zeitstempel):
        """Kommt aus dem Lesefaden - an den Fensterfaden weiterreichen.

        Beim Beenden kann ein Signal unterwegs sein, während Fenster und
        Datenbank schon zugehen. Ohne diese Absicherung landet es auf einer
        geschlossenen Datenbank und wirft einen Fehler, den niemand mehr
        sieht.
        """
        if self._beendet:
            return
        try:
            # Der Zeitstempel muss mitgereicht werden. Gestoppt wird der
            # Moment der Durchfahrt, nicht der Moment, in dem das Fenster
            # dazu kommt.
            self.after(0, lambda t=zeitstempel: self._ausloesen(t))
        except tk.TclError:
            pass                       # Fenster ist bereits weg

    # ------------------------------------------------------------------
    # Bedienung
    # ------------------------------------------------------------------
    def _eingabe_offen(self):
        """Steht gerade das Starterfenster offen?"""
        try:
            return bool(self.starter.winfo_viewable())
        except tk.TclError:
            return False

    def _ausloesen(self, zeitpunkt=None):
        if self._beendet:
            return
        # Solange die Eingabe offen ist, darf kein Signal einen Lauf starten.
        # Sonst läuft im Hintergrund unbemerkt die Uhr, während vorne noch
        # Pylonen eingetragen werden - und die Zeit des nächsten Laufs ist
        # von Anfang an falsch.
        if self._eingabe_offen():
            self._protokoll("Signal während der Eingabe ignoriert")
            self._status("Signal ignoriert - erst die Eingabe abschließen "
                         "(„Weiter“).")
            self.bell()
            return
        self._verarbeiten(self.ablauf.ausloesen(zeitpunkt))

    def _abbrechen(self):
        if self._eingabe_offen():
            return
        self._verarbeiten(self.ablauf.abbrechen())

    def _modus_gewaehlt(self):
        self._modus_setzen(self.var_modus.get())

    def _modus_setzen(self, modus):
        if self.ablauf.laeuft:
            self.var_modus.set(self.ablauf.modus)
            self._status("Während der Messung lässt sich nicht umschalten.")
            return
        self._verarbeiten(self.ablauf.modus_setzen(modus))

    def _naechster_starter(self, nachfragen=True):
        if self.ablauf.laeuft:
            self._status("Erst den laufenden Lauf beenden oder verwerfen.")
            return
        # Ein Fehlklick hier hätte früher die gerade eingetippten Daten
        # kommentarlos weggeworfen.
        if nachfragen and self._hat_unfertige_daten() and not messagebox.askyesno(
                "Nächster Starter",
                f"Für Nr. {self.ergebnis.startnummer or '?'} "
                f"{self.ergebnis.name or ''} sind Daten eingetragen, die noch "
                f"nicht vollständig gespeichert sind.\n\n"
                f"Wirklich mit dem nächsten Starter weitermachen?",
                parent=self):
            return
        self.ergebnis = self._neues_ergebnis()
        self._gespeichert_lauf2 = False
        self.starter.gedruckt = False
        self._verarbeiten(self.ablauf.neuer_starter())

    def _zwischenzeit_halten(self):
        self._halten_bis = self.ablauf.uhr() + int(self.einst.zwischenzeit_halten)
        self._haltetext = zeit.formatiere(self.ablauf.aktuelle_zeit())

    def _zwischenzeit_aus(self):
        self._halten_bis = 0.0

    # ------------------------------------------------------------------
    # Ereignisse der Ablaufsteuerung
    # ------------------------------------------------------------------
    def _verarbeiten(self, ereignisse):
        for ereignis in ereignisse or []:
            art = ereignis.art
            if art == "protokoll":
                self._protokoll(ereignis["text"])
            elif art == "runde":
                self._protokoll(ereignis["text"])
                self._halten_bis = self.ablauf.uhr() + int(self.einst.zwischenzeit_halten)
                self._haltetext = zeit.formatiere(ereignis["zeit"])
            elif art == "warnton":
                self.bell()
            elif art == "ende_training":
                self._haltetext = zeit.formatiere(ereignis["zeit"])
                self._halten_bis = self.ablauf.uhr() + 10
            elif art == "ende_lauf":
                self.ergebnis.zeit_setzen(ereignis["lauf"], ereignis["zeit"])
            elif art == "starter_erfassen":
                self._starter_oeffnen(ereignis["anlass"], ereignis.daten)
            elif art == "wechsel_wertung":
                self.var_modus.set(ablauf_modul.WERTUNG)
            elif art == "abbruch":
                self._protokoll(ereignis["text"])
            elif art in ("modus", "neuer_starter"):
                self.var_modus.set(self.ablauf.modus)
        self._auffrischen_sofort()

    def _starter_oeffnen(self, anlass, daten):
        if not self.einst.starter_eingabe:
            return
        if anlass in ("vor_wertung", "vor_einfuehrung"):
            self.starter.erfassen_oeffnen(
                self.ergebnis, self.db.naechste_startnummer())
        elif anlass == "lauf_ende":
            self.starter.lauf_oeffnen(self.ergebnis, 1)
        elif anlass == "wertung_ende":
            self.starter.gedruckt = False
            self._gespeichert_lauf2 = False
            self.starter.lauf_oeffnen(self.ergebnis, 2)

    def _protokoll(self, text):
        self.db.verlauf_speichern(text, self.ergebnis.startnummer)
        self.verlauf.insert("end", text)
        grenze = int(self.einst.history_zeilen)
        while self.verlauf.size() > grenze:
            self.verlauf.delete(0)
        self.verlauf.see("end")

    def _verlauf_laden(self):
        for eintrag in self.db.verlauf(int(self.einst.history_zeilen)):
            self.verlauf.insert("end", eintrag["text"])
        self.verlauf.see("end")

    # ------------------------------------------------------------------
    # Rückmeldungen aus dem Starterfenster
    # ------------------------------------------------------------------
    def _starter_weiter(self, zustand, ergebnis):
        if zustand == ERFASSEN:
            self.starter.verbergen()
            self.focus_force()
            return

        if zustand == LAUF1:
            self._lauf_speichern(1)
            self.starter.verbergen()
            self.focus_force()
            return

        # Zustand ENDE
        if not self._gespeichert_lauf2:
            self._lauf_speichern(2)
            self._gesamt_speichern()
        self.starter.verbergen()
        self._naechster_starter(nachfragen=False)   # alles gespeichert

    def _starter_drucken(self, ergebnis):
        # Wie früher: mit dem Drucken werden 2. Lauf und Gesamtergebnis
        # festgeschrieben - aber garantiert nur einmal.
        if not self._gespeichert_lauf2:
            self._lauf_speichern(2)
            self._gesamt_speichern()
        try:
            vorschau = ausdruck.drucke(ergebnis, self.einst)
        except ausdruck.DruckFehler as fehler:
            if not messagebox.askyesno(
                    "Drucken", f"{fehler}\n\nTrotzdem weitermachen?",
                    parent=self.starter):
                return False
        else:
            if vorschau:
                self._status(f"PDF-Vorschau erzeugt: {vorschau} "
                             f"(es wurde nichts gedruckt)")
        self._platzierung_zeigen(ergebnis)
        return True

    def _starter_wiederholen(self, lauf, ergebnis):
        self.starter.verbergen()
        self._gespeichert_lauf2 = False
        self.starter.gedruckt = False
        self._verarbeiten(self.ablauf.lauf_wiederholen(lauf))
        self.focus_force()

    # ------------------------------------------------------------------
    # Speichern
    # ------------------------------------------------------------------
    def _lauf_speichern(self, nummer):
        werte = self.ergebnis.als_text(nummer)
        self.db.ergebnis_speichern(
            starternr=self.ergebnis.startnummer, name=self.ergebnis.name,
            klasse=self.ergebnis.klasse, verein=self.ergebnis.verein,
            laufnr=nummer, **werte)
        if nummer == 2:
            self._gespeichert_lauf2 = True
        self._live_aktualisieren()

    def _gesamt_speichern(self):
        self.db.ergebnis_speichern(
            starternr=self.ergebnis.startnummer, name=self.ergebnis.name,
            klasse=self.ergebnis.klasse, verein=self.ergebnis.verein,
            laufnr=db_modul.LAUF_GESAMT, **self.ergebnis.gesamt_als_text())
        self._live_aktualisieren()

    def _platzierung_zeigen(self, ergebnis):
        heute = db_modul.heute()
        gesamt = [e for e in self.db.neueste_je_starter(heute)
                  if e["laufnr"] == db_modul.LAUF_GESAMT]
        zeilen = wertung.platzierungstext(
            gesamt, ergebnis.startnummer, ergebnis.name, ergebnis.verein,
            ergebnis.klasse)
        self.platzierung.zeige(zeilen)

    # ------------------------------------------------------------------
    # Live-Timing
    # ------------------------------------------------------------------
    def _live_aktualisieren(self, laut=False):
        if not self.live.aktiv():
            if laut:
                messagebox.showinfo(
                    "Live-Timing",
                    "Das Live-Timing ist ausgeschaltet.\n\nEinschalten unter "
                    "Datei → Einstellungen → Live-Timing.", parent=self)
            self.var_live.set("Live-Timing: aus")
            return
        meldung = self.live.aktualisieren(
            self.db, hintergrund=self._veroeffentlichen_anstossen)
        self.var_live.set(meldung or "Live-Timing: aus")
        if laut and meldung:
            self._status(meldung)

    def _veroeffentlichen_anstossen(self):
        """Schiebt den Push in einen eigenen Faden.

        Git kann am Streckenrand zäh sein. Liefe es hier im Fenster, stünde
        die ganze Zeitmessung so lange - und der nächste Fahrer wartet nicht,
        bis GitHub geantwortet hat.
        """
        if self._push_laeuft or self._beendet:
            return
        self._push_laeuft = True

        def arbeiten():
            meldung = self.live.jetzt_veroeffentlichen()
            self._push_laeuft = False
            if self._beendet:
                return
            try:
                self.after(0, lambda: self._push_fertig(meldung))
            except tk.TclError:
                pass

        threading.Thread(target=arbeiten, daemon=True,
                         name="Veroeffentlichen").start()

    def _push_fertig(self, meldung):
        self.var_live.set(meldung)
        if "fehl" in meldung.lower() or "nicht" in meldung.lower():
            self._status(meldung)

    def _jetzt_veroeffentlichen(self):
        if not self.live.aktiv():
            self._live_aktualisieren(True)
            return
        if self._push_laeuft:
            self._status("Es wird gerade schon veröffentlicht.")
            return
        self.live.aktualisieren(self.db)
        self.var_live.set("Live-Timing: wird veröffentlicht …")
        self._veroeffentlichen_anstossen()

    # ------------------------------------------------------------------
    # Anzeige
    # ------------------------------------------------------------------
    def _status(self, text):
        self.var_status.set(text)

    def _hat_unfertige_daten(self):
        """Sind Fahrerdaten oder Zeiten erfasst, die noch nicht vollständig
        gespeichert sind?"""
        if self._gespeichert_lauf2:
            return False
        hat_zeiten = any(self.ergebnis.lauf(n).fahrzeit for n in (1, 2))
        return bool(self.ergebnis.startnummer or self.ergebnis.name or hat_zeiten)

    def _zustandsbalken(self):
        """Ein Satz, der sagt was gerade läuft - und ob gespeichert wird."""
        fahrer = ""
        if self.ergebnis.startnummer or self.ergebnis.name:
            fahrer = f" · Nr. {self.ergebnis.startnummer or '?'} " \
                     f"{self.ergebnis.name}".rstrip()

        if self._eingabe_offen():
            return ("EINGABE OFFEN · Pylonen und Fehler eintragen, dann "
                    "„Weiter“" + fahrer), "ruhe"

        if self.ablauf.modus == ablauf_modul.TRAINING:
            if self.ablauf.laeuft:
                return (f"TRAINING LÄUFT · Runde {self.ablauf.runden + 1} "
                        f"von {self.ablauf.max_runden} · noch "
                        f"{self.ablauf.training_restzeit_minuten()} Min. · "
                        f"es wird nichts gespeichert"), "laeuft"
            return ("TRAINING · F1 startet · im Training wird nichts "
                    "gespeichert"), "merke"

        if self.ablauf.modus == ablauf_modul.EINFUEHRUNG:
            return (f"EINFÜHRUNGSRUNDE · wird nicht gemessen · F1 beim "
                    f"Durchfahren{fahrer}"), "ruhe"

        if self.ablauf.laeuft:
            return (f"WERTUNGSLAUF {self.ablauf.lauf_nummer} von "
                    f"{self.einst.we_anzahl_laeufe} LÄUFT · Runde "
                    f"{self.ablauf.runden + 1} von {self.ablauf.max_runden}"
                    f"{fahrer}"), "laeuft"
        naechster = min(self.ablauf.lauf_nummer + 1,
                        int(self.einst.we_anzahl_laeufe))
        return (f"WERTUNG · bereit für Lauf {naechster} von "
                f"{self.einst.we_anzahl_laeufe} · F1 startet{fahrer}"), "ruhe"

    def _balken_zeichnen(self):
        text, art = self._zustandsbalken()
        flaeche, schrift = {
            "laeuft": (stil.LAEUFT_FLAECHE, stil.LAEUFT_SCHRIFT),
            "merke": (stil.MERKE_FLAECHE, stil.SCHRIFT),
        }.get(art, (stil.RUHE_FLAECHE, stil.SCHRIFT))
        if self.balken["text"] != text:
            self.balken.configure(text=text)
        if self.balken["background"] != flaeche:
            self.balken.configure(background=flaeche, foreground=schrift)

    def _schranke_zeichnen(self):
        port = str(self.einst.serieller_port).strip()
        if self.lichtschranke and self.lichtschranke.offen:
            self.var_schranke.set(f"Lichtschranke: verbunden an {port}")
            self.anzeige_schranke.configure(style="Erfolg.TLabel")
        elif not port:
            self.var_schranke.set("Lichtschranke: keine eingestellt · "
                                  "Messung mit F1")
            self.anzeige_schranke.configure(style="Hinweis.TLabel")
        else:
            self.var_schranke.set(f"Lichtschranke: NICHT verbunden ({port}) · "
                                  f"Messung nur mit F1")
            self.anzeige_schranke.configure(style="Fehler.TLabel")

    def _auffrischen_sofort(self):
        self.knopf_messen.configure(text=self.ablauf.knopfbeschriftung())
        self.var_runde.set(str(self.ablauf.runden + (1 if self.ablauf.laeuft else 0)))
        training = self.ablauf.modus == ablauf_modul.TRAINING
        for element in (self.beschriftung_restzeit, self.wert_restzeit):
            if training:
                element.grid()
            else:
                element.grid_remove()
        if training:
            self.var_restzeit.set(str(self.ablauf.training_restzeit_minuten()))
        self._live_menue_pflegen()
        self._balken_zeichnen()
        self._schranke_zeichnen()

    def _live_menue_pflegen(self):
        zustand = "normal" if self.live.aktiv() else "disabled"
        for eintrag in range(2):
            try:
                self.menue_live.entryconfigure(eintrag, state=zustand)
            except tk.TclError:
                pass
        if not self.live.aktiv():
            self.var_live.set("Live-Timing: aus")
        elif not self.var_live.get():
            # Beim Start soll auf einen Blick klar sein, ob Ergebnisse
            # nur lokal geschrieben oder auch veröffentlicht werden.
            self.var_live.set("Live-Timing: an, Veröffentlichen "
                              + ("an" if self.einst.veroeffentlichen_an() else "aus"))

    def _auffrischen(self):
        """Der ruhige Takt: Uhr weiterzählen, Anzeigetafel nachführen."""
        if self._halten_bis and self.ablauf.uhr() < self._halten_bis:
            text = self._haltetext
        elif self.ablauf.laeuft:
            text = zeit.formatiere(self.ablauf.aktuelle_zeit())
        else:
            self._halten_bis = 0.0
            text = self._haltetext or zeit.formatiere(self.ablauf.aktuelle_zeit())

        self.var_zeit.set(text)
        self.tafel.zeige(text)
        self._balken_zeichnen()
        if self.ablauf.laeuft:
            self.var_runde.set(str(self.ablauf.runden + 1))
            if self.ablauf.modus == ablauf_modul.TRAINING:
                self.var_restzeit.set(str(self.ablauf.training_restzeit_minuten()))
        self._takt_id = self.after(TAKT_MS, self._auffrischen)

    # ------------------------------------------------------------------
    def _einstellungen(self):
        if self.ablauf.laeuft:
            self._status("Einstellungen lassen sich nicht während der Messung ändern.")
            return
        Einstellungsfenster(self, self.einst, self._einstellungen_uebernommen)

    def _einstellungen_uebernommen(self):
        self.ergebnis.sek_pylone = int(self.einst.strafzeit_pylone)
        self.ergebnis.sek_fehler = int(self.einst.strafzeit_fehler)
        self.starter.feld_klasse.configure(values=self.einst.klassen_liste())
        self.starter.feld_verein.configure(values=self.einst.vereine_liste())
        self._lichtschranke_starten()
        self._auffrischen_sofort()
        self._status("Einstellungen übernommen.")

    def _tagesuebersicht(self):
        """Was ist heute gespeichert - und Berichtigen, falls nötig."""
        from .tagesuebersicht import Tagesuebersicht
        Tagesuebersicht(self, self.db, self.einst,
                        bei_aenderung=self._live_aktualisieren)

    def _altdaten_uebernehmen(self):
        """Einmaliger Import der Ergebnisse aus der Access-Datenbank des
        alten Programms. Die alte Datei wird dabei nur gelesen."""
        from tkinter import filedialog
        pfad = filedialog.askopenfilename(
            parent=self, title="Zeitmessung_Kart_Data.accdb auswählen",
            filetypes=[("Access-Datenbank", "*.accdb"), ("Alle Dateien", "*.*")])
        if not pfad:
            return
        try:
            uebernommen, uebersprungen = db_modul.importiere_aus_access(
                self.db, pfad)
        except Exception as fehler:                      # noqa: BLE001
            messagebox.showerror(
                "Übernehmen",
                f"Die alte Datenbank konnte nicht gelesen werden:\n\n{fehler}",
                parent=self)
            return
        messagebox.showinfo(
            "Übernehmen",
            f"{uebernommen} Ergebnisse übernommen.\n"
            f"{uebersprungen} übersprungen (schon vorhanden oder leer).\n\n"
            f"An der alten Datenbank wurde nichts verändert.",
            parent=self)
        self._live_aktualisieren()

    def _selbsttest(self):
        """Vor dem Renntag einmal alles durchklingeln."""
        self._status("Selbsttest läuft …")
        self.update_idletasks()
        bericht = selbsttest_modul.alles_pruefen(
            self.einst, self.db,
            lichtschranke_offen=bool(self.lichtschranke
                                     and self.lichtschranke.offen),
            sicherungspfad=self.sicherung)
        self._status(bericht.zusammenfassung())
        anzeigen = messagebox.showerror if bericht.fehler else messagebox.showinfo
        anzeigen("Selbsttest", bericht.als_text(), parent=self)
        return bericht

    def _hilfe(self):
        messagebox.showinfo("Kurzanleitung", KURZANLEITUNG, parent=self)

    def _beenden(self):
        if self.ablauf.laeuft and not messagebox.askyesno(
                "Beenden", "Es läuft gerade eine Messung. Wirklich beenden?",
                parent=self):
            return
        if self.live.aktiv() and self.live.wartet_auf_push \
                and self.einst.veroeffentlichen_an():
            self.live.jetzt_veroeffentlichen()
        if self.lichtschranke:
            self.lichtschranke.schliessen()
        self.db.schliessen()
        self.sperre.loesen()
        self.destroy()

    def destroy(self):
        """Beim Schließen den Anzeigetakt abbestellen - sonst versucht
        tkinter, ihn auf einem nicht mehr vorhandenen Fenster auszuführen."""
        self._beendet = True
        if self.lichtschranke:
            # zuerst den Lesefaden anhalten, dann erst abbauen
            self.lichtschranke.schliessen()
            self.lichtschranke = None
        if self._takt_id is not None:
            try:
                self.after_cancel(self._takt_id)
            except tk.TclError:
                pass
            self._takt_id = None
        super().destroy()


KURZANLEITUNG = """Messen
  F1            Start bzw. Runde/Zwischenzeit - genau wie ein Signal
                der Lichtschranke
  ESC           laufenden Lauf abbrechen
  T / E / W     Training, Einführungsrunde, Wertungslauf

Ablauf eines Wertungslaufs
  1. Modus "Wertungslauf" wählen, Starterdaten eingeben
  2. F1 startet den 1. Wertungslauf
  3. Nach der letzten Runde: Pylonen und Fehler eintragen, "Weiter"
  4. F1 startet den 2. Wertungslauf
  5. Nach der letzten Runde: eintragen, "Drucken", dann "Weiter"

Training schreibt bewusst keine Ergebnisse in die Datenbank.

Die Anzeigetafel der Lichtschranke muss ausgeschaltet bleiben - sie
stört den USB-Adapter."""
