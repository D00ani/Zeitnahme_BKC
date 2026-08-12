# -*- coding: utf-8 -*-
"""
Ergebniskarte drucken.

Der Ausdruck sieht aus wie bisher: zwei gleiche Karten nebeneinander auf
einem Blatt (eine für den Fahrer, eine für die Auswertung), Schrift Verdana,
Maße in Millimetern.

Aufgeteilt in zwei Teile:

``bauplan()``   rechnet aus, **was wo** steht - reine Zahlen, ohne Drucker.
                Genau diese Funktion prüft die Testsuite gegen die
                Koordinaten des alten Programms.
``drucke()``    schickt den Bauplan über die Windows-Zeichenschnittstelle
                (GDI) an den Drucker - dieselbe Schnittstelle, die auch das
                alte Programm benutzt hat.
"""
import os
import sys
from datetime import datetime

# Schriften: (Name, Punktgröße, fett)
SCHRIFT_NORMAL = ("Verdana", 9, False)
SCHRIFT_FETT = ("Verdana", 9, True)
SCHRIFT_ZEIT = ("Verdana", 14, True)

KARTEN_BREITE = 70      # mm, wie im Original
KARTEN_ABSTAND = 2      # mm zwischen den beiden Karten

# Grobe mittlere Zeichenbreite als Anteil der Schriftgröße. Verdana und
# Helvetica liegen beide in dieser Gegend. Es geht nur darum, überlange
# Namen zu erkennen - auf ein Zehntelmillimeter kommt es dabei nicht an.
_ZEICHENBREITE = 0.55


def _passt_in(text, breite_mm, punkte):
    """Kürzt Text, der über die Karte hinauslaufen würde.

    Ein Name wie „Maximiliane von Und-Zu-Hohenzollern-Sigmaringen“ wäre
    rund 90 mm breit - er würde quer über die zweite Karte laufen, die schon
    bei 82 mm beginnt.
    """
    je_zeichen = punkte * _ZEICHENBREITE * 25.4 / 72
    if je_zeichen <= 0:
        return text
    passt = int(breite_mm / je_zeichen)
    text = str(text)
    if len(text) <= passt:
        return text
    return text[:max(1, passt - 1)].rstrip() + "…"


def bauplan(ergebnis, linker_rand=10, oberer_rand=10, unterer_abstand=20,
            karten=2):
    """Liefert die Zeichenanweisungen für das Blatt.

    ``ergebnis`` ist ein ``wertung.Starterergebnis``.

    Rückgabe: Liste von Anweisungen
        ("text", x_mm, y_mm, schrift, inhalt)
        ("linie", x1_mm, y1_mm, x2_mm, y2_mm, breite_mm)
    """
    lauf1 = ergebnis.als_text(1)
    lauf2 = ergebnis.als_text(2)
    gesamt = ergebnis.gesamt_als_text()

    anweisungen = []
    x = linker_rand
    for karte in range(1, karten + 1):
        if karte > 1:
            x = x + KARTEN_BREITE + KARTEN_ABSTAND
        y = oberer_rand
        breite = KARTEN_BREITE

        x1 = x + 40         # Gesamtzeit oben rechts
        t0 = x              # Spalte "Lauf"
        t1 = x + 10         # Fahrzeit
        t2 = t1 + 16        # Pyl/Fal
        t3 = t2 + 12        # Strafzeit
        t4 = t3 + 15        # Gesamt
        y0 = y + 13         # Kopfzeile der Tabelle
        y1 = y + 18         # 1. Lauf
        y2 = y + 22         # 2. Lauf
        ye = y2 + unterer_abstand

        # Kopf. Klasse und Name werden auf die Kartenbreite beschnitten,
        # damit nichts in die Nachbarkarte läuft.
        anweisungen.append(("text", x, y, SCHRIFT_NORMAL,
                            _passt_in(f"Klasse {ergebnis.klasse}",
                                      x1 - x - 2, SCHRIFT_NORMAL[1])))
        anweisungen.append(("text", x1, y, SCHRIFT_ZEIT, gesamt["gesamtzeit"]))
        anweisungen.append(("text", x, y + 6, SCHRIFT_FETT,
                            _passt_in(f"{ergebnis.name} ({ergebnis.startnummer})",
                                      breite - 3, SCHRIFT_FETT[1])))
        anweisungen.append(("linie", x, y + 12, breite + x - 3, y + 12, 0.5))

        # Tabellenkopf
        for spalte, text in ((t0, "Lauf"), (t1, "Fahrzeit"), (t2, "Pyl/Fal"),
                             (t3, "Strafzeit"), (t4, "Gesamt")):
            anweisungen.append(("text", spalte, y0, SCHRIFT_NORMAL, text))

        # Die beiden Läufe
        for zeile_y, nummer, werte in ((y1, "1", lauf1), (y2, "2", lauf2)):
            anweisungen.append(("text", t0 + 2, zeile_y, SCHRIFT_NORMAL, nummer))
            anweisungen.append(("text", t1, zeile_y, SCHRIFT_NORMAL,
                                werte["fahrzeit"]))
            anweisungen.append(("text", t2 + 3, zeile_y, SCHRIFT_NORMAL,
                                f"{werte['pylonen']}/{werte['adw']}"))
            anweisungen.append(("text", t3 + 3, zeile_y, SCHRIFT_NORMAL,
                                werte["strafzeit"]))
            anweisungen.append(("text", t4 - 3, zeile_y, SCHRIFT_NORMAL,
                                werte["gesamtzeit"]))

        anweisungen.append(("linie", x, ye, breite + x - 3, ye, 0.1))
    return anweisungen


def als_text(ergebnis, **kwargs):
    """Der Ausdruck als schlichte Textfassung - für die Vorschau und für
    Rechner ohne angeschlossenen Drucker."""
    lauf1 = ergebnis.als_text(1)
    lauf2 = ergebnis.als_text(2)
    gesamt = ergebnis.gesamt_als_text()
    breite = 46
    zeilen = [
        f"Klasse {ergebnis.klasse}".ljust(breite - 10) + gesamt["gesamtzeit"],
        f"{ergebnis.name} ({ergebnis.startnummer})",
        "-" * breite,
        "Lauf Fahrzeit   Pyl/Fal Strafzeit Gesamt",
    ]
    for nummer, werte in (("1", lauf1), ("2", lauf2)):
        zeilen.append(f"  {nummer}  {werte['fahrzeit']:<10} "
                      f"{werte['pylonen']}/{werte['adw']:<5} "
                      f"{werte['strafzeit']:<9} {werte['gesamtzeit']}")
    zeilen.append("-" * breite)
    return "\n".join(zeilen)


# ----------------------------------------------------------------------
# Drucken - der Weg dorthin hängt vom Betriebssystem ab
# ----------------------------------------------------------------------

class DruckFehler(Exception):
    """Der Ausdruck konnte nicht erzeugt werden."""


# Windows bringt diesen Drucker mit; er macht aus dem Druckauftrag eine PDF.
PDF_DRUCKER = "Microsoft Print to PDF"

_backend_zwischenspeicher = None


def backend():
    """Der passende Druckweg für dieses Betriebssystem.

    Windows druckt über GDI und damit mit Verdana, genau wie das alte
    Programm. Alles andere erzeugt eine PDF mit denselben Millimetermaßen
    und gibt sie an CUPS.

    Der Import passiert absichtlich erst hier und nicht am Dateianfang:
    ``ausdruck_windows`` lässt sich auf Linux gar nicht laden, weil es
    Windows-Datentypen braucht.
    """
    global _backend_zwischenspeicher
    if _backend_zwischenspeicher is None:
        if sys.platform.startswith("win"):
            from . import ausdruck_windows as gewaehlt
        else:
            from . import ausdruck_linux as gewaehlt
        _backend_zwischenspeicher = gewaehlt
    return _backend_zwischenspeicher


def standarddrucker():
    """Name des eingestellten Standarddruckers ("" wenn keiner da ist)."""
    return backend().standarddrucker()


def drucker_liste():
    """Alle eingerichteten Drucker."""
    return backend().drucker_liste()


def _dateiname(ergebnis, zeitstempel=None):
    zeitstempel = zeitstempel or datetime.now()
    nummer = str(ergebnis.startnummer or "").strip()
    # Aus der Startnummer wird ein Dateiname - Schrägstriche und Ähnliches
    # müssen weg, und übrig bleiben darf nicht nichts.
    sauber = "".join(z for z in nummer if z.isalnum() or z in "-_") or "ohne"
    return f"Ergebniskarte_{sauber}_{zeitstempel:%Y-%m-%d_%H-%M-%S}.pdf"


def ziel_bestimmen(einstellungen, ergebnis, zeitstempel=None):
    """Wohin geht der Auftrag? Gibt (Druckername, Ausgabedatei) zurück;
    Ausgabedatei ist ``None`` beim echten Druck auf Papier."""
    if getattr(einstellungen, "vorschau_statt_druck", False):
        ordner = str(getattr(einstellungen, "vorschau_ordner", "")).strip()
        if not ordner:
            from .einstellungen import PROGRAMM_ORDNER
            ordner = os.path.join(PROGRAMM_ORDNER, "vorschau")
        return PDF_DRUCKER, os.path.join(ordner, _dateiname(ergebnis, zeitstempel))
    return str(einstellungen.drucker).strip() or standarddrucker(), None


def drucke(ergebnis, einstellungen, dokumentname=None, karten=2,
           oeffnen=True):
    """Druckt die Ergebniskarte - oder erzeugt eine PDF-Vorschau, wenn das
    in den Einstellungen so steht.

    Löst ``DruckFehler`` aus, wenn etwas schiefgeht; der Aufrufer zeigt das
    als Hinweis an, statt das Programm abstürzen zu lassen (das alte
    Programm blieb bei einem Druckerfehler mit ``Stop`` stehen).

    Gibt den Pfad der PDF zurück, wenn eine erzeugt wurde, sonst ``None``.
    """
    anweisungen = bauplan(
        ergebnis,
        linker_rand=int(einstellungen.pr_linker_rand),
        oberer_rand=int(einstellungen.pr_oberer_rand),
        unterer_abstand=int(einstellungen.pr_unterer_abstand),
        karten=karten)

    name, ausgabedatei = ziel_bestimmen(einstellungen, ergebnis)
    if not name and not ausgabedatei:
        raise DruckFehler("Es ist kein Drucker eingerichtet.")

    dokumentname = dokumentname or f"StartNr_{ergebnis.startnummer}"
    erzeugt = backend().ausgeben(anweisungen, name, dokumentname, ausgabedatei)

    if erzeugt and oeffnen:
        _oeffne(erzeugt)
    return erzeugt


def _oeffne(pfad):
    """Zeigt die fertige PDF im Standardprogramm an."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(pfad)                  # noqa: S606 - Windows-Vorschau
        else:
            import subprocess
            befehl = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([befehl, pfad],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as fehler:
        raise DruckFehler(f"Die Vorschau {pfad} konnte nicht geöffnet "
                          f"werden: {fehler}") from fehler
