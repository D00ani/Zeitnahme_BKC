# -*- coding: utf-8 -*-
"""
Ausdruck unter Linux - über CUPS.

Auf Linux gibt es die Windows-Zeichenschnittstelle GDI nicht. Stattdessen
wird die Karte als PDF erzeugt (:mod:`ausdruck_pdf`, gleiche Millimeter-
positionen) und mit ``lp`` an das Drucksystem übergeben. ``lp`` und
``lpstat`` gehören zu CUPS und sind auf praktisch jedem Linux vorhanden.
"""
import os
import subprocess
import tempfile

from . import ausdruck_pdf
from .ausdruck import DruckFehler


def _cups(befehl, *argumente):
    try:
        return subprocess.run([befehl, *argumente], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None


def drucker_liste():
    """Alle eingerichteten Drucker (``lpstat -a``)."""
    ergebnis = _cups("lpstat", "-a")
    if not ergebnis or ergebnis.returncode != 0:
        return []
    namen = []
    for zeile in (ergebnis.stdout or "").splitlines():
        teile = zeile.split()
        if teile:
            namen.append(teile[0])
    return namen


def standarddrucker():
    """Der eingestellte Standarddrucker (``lpstat -d``)."""
    ergebnis = _cups("lpstat", "-d")
    if not ergebnis or ergebnis.returncode != 0:
        return ""
    text = (ergebnis.stdout or "").strip()
    # "system default destination: Drucker" bzw. "no system default destination"
    if ":" in text:
        return text.split(":", 1)[1].strip()
    return ""


def ausgeben(anweisungen, druckername, dokumentname, ausgabedatei=None):
    """Erzeugt die Karte.

    Ist ``ausgabedatei`` gesetzt, bleibt es bei der PDF (Vorschau-Betrieb).
    Sonst wird die PDF in einen Zwischenordner geschrieben und gedruckt.
    """
    if ausgabedatei:
        ausdruck_pdf.schreibe(anweisungen, ausgabedatei)
        return ausgabedatei

    if not druckername:
        raise DruckFehler("Es ist kein Drucker eingerichtet.")

    ordner = tempfile.mkdtemp(prefix="zeitmessung-druck-")
    pfad = os.path.join(ordner, f"{dokumentname}.pdf")
    try:
        ausdruck_pdf.schreibe(anweisungen, pfad)
        ergebnis = _cups("lp", "-d", druckername, "-t", dokumentname, pfad)
        if ergebnis is None:
            raise DruckFehler("Der Befehl „lp“ wurde nicht gefunden - ist "
                              "CUPS installiert?")
        if ergebnis.returncode != 0:
            meldung = (ergebnis.stderr or ergebnis.stdout or "").strip()
            raise DruckFehler(f"Der Drucker „{druckername}“ hat den Auftrag "
                              f"nicht angenommen: {meldung}")
    finally:
        # lp hat die Datei zu diesem Zeitpunkt eingelesen; der Ordner kann weg.
        try:
            os.remove(pfad)
            os.rmdir(ordner)
        except OSError:
            pass
    return None
