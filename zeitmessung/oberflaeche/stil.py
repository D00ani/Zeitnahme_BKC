# -*- coding: utf-8 -*-
"""
Erscheinungsbild.

Bewusst neutral: Grautöne, Schwarz und Weiß. Keine Vereinsfarben und kein
Logo - das Programm soll unverändert bei jedem Verein einsetzbar sein.
"""

HINTERGRUND = "#f0f0f0"      # Fensterhintergrund, Windows-Standardgrau
FLAECHE = "#ffffff"          # Eingabefelder, Listen
RAHMEN = "#c0c0c0"
SCHRIFT = "#000000"
SCHRIFT_LEISE = "#555555"
HINWEIS = "#8a6d00"          # Warnungen: gedecktes Ockergelb
FEHLER = "#a02020"           # Fehler: gedecktes Rot
ERFOLG = "#1f6d33"           # Bestätigungen: gedecktes Grün

# Anzeigetafel: weiß auf schwarz, wie bisher
TAFEL_HINTERGRUND = "#000000"
TAFEL_SCHRIFT = "#ffffff"

# Zustandsbalken. Der Unterschied läuft über hell/dunkel, nicht über Farbe -
# das bleibt neutral und ist auch bei Sonne auf dem Bildschirm erkennbar.
RUHE_FLAECHE = "#e2e2e2"        # es wird nicht gemessen
LAEUFT_FLAECHE = "#2b2b2b"      # Messung läuft
LAEUFT_SCHRIFT = "#ffffff"
MERKE_FLAECHE = "#d8d8d8"       # Hinweiszustand (Training speichert nicht)

SCHRIFTART = "Segoe UI"
SCHRIFT_NORMAL = (SCHRIFTART, 10)
SCHRIFT_FETT = (SCHRIFTART, 10, "bold")
SCHRIFT_KLEIN = (SCHRIFTART, 9)
SCHRIFT_UEBERSCHRIFT = (SCHRIFTART, 12, "bold")
SCHRIFT_ZEIT = ("Consolas", 96, "bold")     # Stoppuhr im Hauptfenster
SCHRIFT_TABELLE = ("Consolas", 10)
SCHRIFT_KNOPF_GROSS = (SCHRIFTART, 14, "bold")


def grundeinstellung(wurzel):
    """Setzt ein schlichtes, einheitliches Aussehen für alle Fenster."""
    from tkinter import ttk
    stil = ttk.Style(wurzel)
    try:
        stil.theme_use("vista")
    except Exception:                      # noqa: BLE001 - anderes System
        try:
            stil.theme_use("clam")
        except Exception:                  # noqa: BLE001
            pass
    wurzel.configure(background=HINTERGRUND)
    stil.configure("TLabel", background=HINTERGRUND, foreground=SCHRIFT,
                   font=SCHRIFT_NORMAL)
    stil.configure("Leise.TLabel", foreground=SCHRIFT_LEISE, font=SCHRIFT_KLEIN)
    stil.configure("Ueberschrift.TLabel", font=SCHRIFT_UEBERSCHRIFT)
    stil.configure("Hinweis.TLabel", foreground=HINWEIS, font=SCHRIFT_KLEIN)
    stil.configure("Fehler.TLabel", foreground=FEHLER, font=SCHRIFT_KLEIN)
    stil.configure("Erfolg.TLabel", foreground=ERFOLG, font=SCHRIFT_KLEIN)
    stil.configure("TButton", font=SCHRIFT_NORMAL)
    stil.configure("Gross.TButton", font=SCHRIFT_KNOPF_GROSS)
    stil.configure("TCheckbutton", background=HINTERGRUND, font=SCHRIFT_NORMAL)
    stil.configure("TRadiobutton", background=HINTERGRUND, font=SCHRIFT_NORMAL)
    stil.configure("TLabelframe", background=HINTERGRUND)
    stil.configure("TLabelframe.Label", background=HINTERGRUND,
                   font=SCHRIFT_FETT)
    stil.configure("TFrame", background=HINTERGRUND)
    stil.configure("TNotebook", background=HINTERGRUND)
    return stil
