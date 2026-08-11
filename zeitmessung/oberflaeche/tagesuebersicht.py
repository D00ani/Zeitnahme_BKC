# -*- coding: utf-8 -*-
"""
Tagesübersicht - was ist heute gespeichert, und wie berichtige ich es.

Der Rettungsanker für den Renntag. Wenn sich jemand bei den Pylonen vertippt
hat oder ein Lauf versehentlich gespeichert wurde, ließ sich das im alten
Programm nur noch direkt in der Access-Datenbank geradeziehen - mitten im
Rennen keine gute Idee.

Hier geht beides in Ruhe: Zahl berichtigen oder Datensatz löschen. Das
Gesamtergebnis des Fahrers wird dabei automatisch mit nachgezogen, damit
Einzelläufe und Gesamtzeit nicht auseinanderlaufen.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from .. import datenbank as db_modul
from .. import wertung, zeit
from . import stil

SPALTEN = [
    ("uhrzeit", "Uhrzeit", 70),
    ("lauf", "Lauf", 60),
    ("starternr", "Nr.", 45),
    ("name", "Name", 150),
    ("klasse", "Klasse", 60),
    ("verein", "Verein", 130),
    ("fahrzeit", "Fahrzeit", 80),
    ("pylonen", "Pyl.", 45),
    ("adw", "Fehler", 55),
    ("strafzeit", "Strafe", 55),
    ("gesamtzeit", "Gesamt", 85),
]

LAUF_TEXT = {db_modul.LAUF_1: "1. WL", db_modul.LAUF_2: "2. WL",
             db_modul.LAUF_GESAMT: "Gesamt"}


class Tagesuebersicht(tk.Toplevel):

    def __init__(self, elternteil, datenbank, einstellungen, bei_aenderung=None):
        super().__init__(elternteil)
        self.db = datenbank
        self.einst = einstellungen
        self.bei_aenderung = bei_aenderung or (lambda: None)
        self.datum = db_modul.heute()

        self.title("Ergebnisse heute")
        self.configure(background=stil.HINTERGRUND)
        self.geometry("1000x560")
        self.transient(elternteil)

        self._baue()
        self.laden()
        self.bind("<Escape>", lambda _: self.destroy())

    # ------------------------------------------------------------------
    def _baue(self):
        rahmen = ttk.Frame(self, padding=12)
        rahmen.pack(fill="both", expand=True)

        kopf = ttk.Frame(rahmen)
        kopf.pack(fill="x")
        self.var_kopf = tk.StringVar()
        ttk.Label(kopf, textvariable=self.var_kopf,
                  style="Ueberschrift.TLabel").pack(side="left")
        ttk.Button(kopf, text="Aktualisieren", width=14,
                   command=self.laden).pack(side="right")

        # --- Tabelle -------------------------------------------------------
        tabelle = ttk.Frame(rahmen)
        tabelle.pack(fill="both", expand=True, pady=(10, 0))
        self.liste = ttk.Treeview(tabelle, columns=[s[0] for s in SPALTEN],
                                  show="headings", selectmode="browse")
        for schluessel, beschriftung, breite in SPALTEN:
            self.liste.heading(schluessel, text=beschriftung)
            self.liste.column(schluessel, width=breite,
                              anchor="w" if schluessel in ("name", "verein")
                              else "center")
        self.liste.pack(side="left", fill="both", expand=True)
        rollbalken = ttk.Scrollbar(tabelle, orient="vertical",
                                   command=self.liste.yview)
        rollbalken.pack(side="right", fill="y")
        self.liste.configure(yscrollcommand=rollbalken.set)
        self.liste.bind("<<TreeviewSelect>>", lambda _: self._auswahl_uebernehmen())

        # --- Berichtigen ---------------------------------------------------
        berichtigen = ttk.LabelFrame(rahmen, text="Ausgewählten Datensatz berichtigen",
                                     padding=10)
        berichtigen.pack(fill="x", pady=(12, 0))

        self.var_pylonen = tk.StringVar(value="0")
        self.var_fehler = tk.StringVar(value="0")
        ttk.Label(berichtigen, text="Anz. Pylonen").grid(row=0, column=0, padx=(0, 6))
        self.feld_pylonen = ttk.Entry(berichtigen, textvariable=self.var_pylonen,
                                      width=6, justify="right")
        self.feld_pylonen.grid(row=0, column=1)
        ttk.Label(berichtigen, text="Fehler").grid(row=0, column=2, padx=(16, 6))
        self.feld_fehler = ttk.Entry(berichtigen, textvariable=self.var_fehler,
                                     width=6, justify="right")
        self.feld_fehler.grid(row=0, column=3)

        self.knopf_uebernehmen = ttk.Button(
            berichtigen, text="Übernehmen und neu rechnen", width=28,
            command=self._uebernehmen)
        self.knopf_uebernehmen.grid(row=0, column=4, padx=(20, 0))
        self.knopf_loeschen = ttk.Button(
            berichtigen, text="Datensatz löschen", width=20,
            command=self._loeschen)
        self.knopf_loeschen.grid(row=0, column=5, padx=(10, 0))

        self.var_meldung = tk.StringVar()
        ttk.Label(rahmen, textvariable=self.var_meldung,
                  style="Hinweis.TLabel").pack(fill="x", pady=(10, 0))

        ttk.Button(rahmen, text="Schließen", width=14,
                   command=self.destroy).pack(anchor="e", pady=(10, 0))
        self._knoepfe_sperren(True)

    def _knoepfe_sperren(self, gesperrt):
        zustand = "disabled" if gesperrt else "normal"
        for element in (self.knopf_uebernehmen, self.knopf_loeschen,
                        self.feld_pylonen, self.feld_fehler):
            element.configure(state=zustand)

    # ------------------------------------------------------------------
    def laden(self):
        self.liste.delete(*self.liste.get_children())
        eintraege = self.db.ergebnisse(self.datum)
        for eintrag in eintraege:
            self.liste.insert("", "end", iid=str(eintrag["id"]), values=(
                eintrag["uhrzeit"],
                LAUF_TEXT.get(eintrag["laufnr"], str(eintrag["laufnr"])),
                eintrag["starternr"], eintrag["name"], eintrag["klasse"],
                eintrag["verein"], eintrag["fahrzeit"], eintrag["pylonen"],
                eintrag["adw"], eintrag["strafzeit"], eintrag["gesamtzeit"]))
        starter = len({(e["starternr"], e["name"]) for e in eintraege
                       if e["starternr"] or e["name"]})
        self.var_kopf.set(f"{self.datum} · {len(eintraege)} Datensätze · "
                          f"{starter} Starter")
        self._knoepfe_sperren(True)
        if not eintraege:
            self.var_meldung.set("Für heute ist noch nichts gespeichert.")

    def _auswahl(self):
        auswahl = self.liste.selection()
        return int(auswahl[0]) if auswahl else None

    def _auswahl_uebernehmen(self):
        kennung = self._auswahl()
        if kennung is None:
            self._knoepfe_sperren(True)
            return
        eintrag = self.db.ergebnis(kennung)
        if not eintrag:
            self._knoepfe_sperren(True)
            return
        self.var_pylonen.set(str(eintrag["pylonen"] or "0"))
        self.var_fehler.set(str(eintrag["adw"] or "0"))
        self._knoepfe_sperren(False)
        self.var_meldung.set("")

    # ------------------------------------------------------------------
    def _zahl(self, text):
        text = str(text or "").strip()
        return int(text) if text.isdigit() else 0

    def _uebernehmen(self):
        kennung = self._auswahl()
        if kennung is None:
            return
        eintrag = self.db.ergebnis(kennung)
        if not eintrag:
            return

        pylonen = self._zahl(self.var_pylonen.get())
        fehler = self._zahl(self.var_fehler.get())
        strafe, gesamt = wertung.nachrechnen(
            eintrag["fahrzeit"], pylonen, fehler,
            int(self.einst.strafzeit_pylone), int(self.einst.strafzeit_fehler))

        self.db.ergebnis_aendern(kennung, pylonen=str(pylonen), adw=str(fehler),
                                 strafzeit=str(strafe), gesamtzeit=gesamt)
        nachgezogen = ""
        if eintrag["laufnr"] in (db_modul.LAUF_1, db_modul.LAUF_2):
            if self._gesamt_nachziehen(eintrag):
                nachgezogen = " Das Gesamtergebnis wurde mit nachgezogen."

        self.laden()
        self.liste.selection_set(str(kennung))
        self.var_meldung.set(
            f"Berichtigt: {pylonen} Pylonen, {fehler} Fehler → "
            f"Strafzeit {strafe} s, Gesamt {gesamt}.{nachgezogen}")
        self.bei_aenderung()

    def _gesamt_nachziehen(self, eintrag):
        """Rechnet das Gesamtergebnis desselben Fahrers neu aus den beiden
        Einzelläufen - sonst passt es nach einer Berichtigung nicht mehr."""
        schluessel = (eintrag["starternr"], eintrag["name"], eintrag["klasse"])
        laeufe, gesamtsatz = {}, None
        for kandidat in self.db.ergebnisse(self.datum):
            if (kandidat["starternr"], kandidat["name"],
                    kandidat["klasse"]) != schluessel:
                continue
            if kandidat["laufnr"] in (db_modul.LAUF_1, db_modul.LAUF_2):
                laeufe[kandidat["laufnr"]] = kandidat      # der jüngste gewinnt
            elif kandidat["laufnr"] == db_modul.LAUF_GESAMT:
                gesamtsatz = kandidat
        if gesamtsatz is None or not laeufe:
            return False

        fahrzeit = sum(zeit.parse(l["fahrzeit"]) or 0 for l in laeufe.values())
        pylonen = sum(self._zahl(l["pylonen"]) for l in laeufe.values())
        fehler = sum(self._zahl(l["adw"]) for l in laeufe.values())
        strafe, gesamt = wertung.nachrechnen(
            zeit.formatiere(fahrzeit), pylonen, fehler,
            int(self.einst.strafzeit_pylone), int(self.einst.strafzeit_fehler))
        self.db.ergebnis_aendern(
            gesamtsatz["id"], fahrzeit=zeit.formatiere(fahrzeit),
            pylonen=str(pylonen), adw=str(fehler), strafzeit=str(strafe),
            gesamtzeit=gesamt)
        return True

    def _loeschen(self):
        kennung = self._auswahl()
        if kennung is None:
            return
        eintrag = self.db.ergebnis(kennung)
        if not eintrag:
            return
        lauf = LAUF_TEXT.get(eintrag["laufnr"], eintrag["laufnr"])
        if not messagebox.askyesno(
                "Löschen",
                f"Diesen Datensatz wirklich löschen?\n\n"
                f"Nr. {eintrag['starternr']}  {eintrag['name']}\n"
                f"{lauf}, Gesamtzeit {eintrag['gesamtzeit']}\n\n"
                f"Das lässt sich nicht rückgängig machen. Eine Sicherung der "
                f"Datenbank vom Programmstart liegt im Ordner „sicherungen“.",
                parent=self):
            return
        self.db.ergebnis_loeschen(kennung)
        self.laden()
        self.var_meldung.set(f"Datensatz gelöscht: Nr. {eintrag['starternr']} "
                             f"{eintrag['name']}, {lauf}.")
        self.bei_aenderung()
