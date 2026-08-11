# -*- coding: utf-8 -*-
"""
Ergebniskarte als PDF - ohne Zusatzpakete, auf jedem Betriebssystem.

Wird auf Linux benutzt, wo es die Windows-Zeichenschnittstelle GDI nicht
gibt. Die Positionen kommen aus demselben ``bauplan()`` wie beim
Windows-Druck, die Karte sitzt also millimetergenau gleich.

Ein Unterschied bleibt: verwendet wird Helvetica statt Verdana. Helvetica
ist eine der 14 Schriften, die jedes PDF-Programm mitbringt - dadurch muss
nichts eingebettet werden und die Datei bleibt winzig. Verdana gehört
Microsoft und darf nicht einfach mitgeliefert werden.

Aufbau der Datei bewusst schlicht: ein Katalog, eine Seitenliste, eine
Seite, ein Inhaltsstrom, zwei Schriften. Mehr braucht die Karte nicht.
"""
import os

# DIN A4 in Punkt (1 Punkt = 1/72 Zoll)
SEITE_BREITE = 595.276
SEITE_HOEHE = 841.890

PUNKT_JE_MM = 72.0 / 25.4

# Abstand von der Oberkante der Zeile bis zur Grundlinie, als Vielfaches der
# Schriftgröße. PDF setzt Text auf der Grundlinie ab, der Bauplan gibt aber -
# wie die Windows-Fassung - die Oberkante an.
#
# Der Wert ist nicht geraten, sondern an einem echten Windows-Ausdruck
# gemessen: dort landet die Grundlinie bei 1,010 x Schriftgröße unter der
# angegebenen Oberkante (die Oberlänge von Verdana). Damit sitzen die Zeilen
# der Linux-Fassung auf denselben Grundlinien wie die der Windows-Fassung.
OBERLAENGE = 1.010

SCHRIFT_KENNUNG = {False: "/F1", True: "/F2"}   # normal / fett


def _mm_x(mm):
    return mm * PUNKT_JE_MM


def _mm_y(mm):
    """PDF zählt von unten, der Bauplan von oben."""
    return SEITE_HOEHE - mm * PUNKT_JE_MM


def _text_maskieren(text):
    """Klammern und Rückstriche haben in PDF eine Sonderbedeutung."""
    text = str(text)
    for zeichen, ersatz in (("\\", r"\\"), ("(", r"\("), (")", r"\)")):
        text = text.replace(zeichen, ersatz)
    return text


def _als_bytes(text):
    """PDF-Standardschriften sprechen WinAnsi - das deckt Umlaute ab.
    Alles, was dort fehlt, wird zu einem Fragezeichen statt zu einem
    Absturz."""
    return _text_maskieren(text).encode("cp1252", errors="replace")


def inhaltsstrom(anweisungen):
    """Übersetzt den Bauplan in PDF-Zeichenbefehle."""
    teile = []
    for anweisung in anweisungen:
        if anweisung[0] == "text":
            _, x, y, (_familie, punkte, fett), inhalt = anweisung
            grundlinie = _mm_y(y) - punkte * OBERLAENGE
            teile.append(b"BT " + SCHRIFT_KENNUNG[bool(fett)].encode("ascii")
                         + f" {punkte} Tf ".encode("ascii")
                         + f"{_mm_x(x):.2f} {grundlinie:.2f} Td ".encode("ascii")
                         + b"(" + _als_bytes(inhalt) + b") Tj ET")
        else:
            _, x1, y1, x2, y2, breite = anweisung
            teile.append(
                f"{breite * PUNKT_JE_MM:.2f} w "
                f"{_mm_x(x1):.2f} {_mm_y(y1):.2f} m "
                f"{_mm_x(x2):.2f} {_mm_y(y2):.2f} l S".encode("ascii"))
    return b"\n".join(teile)


def schreibe(anweisungen, pfad):
    """Erzeugt die PDF-Datei und gibt ihren Pfad zurück."""
    inhalt = inhaltsstrom(anweisungen)

    objekte = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {SEITE_BREITE:.3f} "
         f"{SEITE_HOEHE:.3f}] /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> "
         f"/Contents 4 0 R >>").encode("ascii"),
        b"<< /Length " + str(len(inhalt)).encode("ascii") + b" >>\nstream\n"
        + inhalt + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>",
    ]

    datei = bytearray(b"%PDF-1.4\n")
    stellen = []
    for nummer, koerper in enumerate(objekte, start=1):
        stellen.append(len(datei))
        datei += f"{nummer} 0 obj\n".encode("ascii") + koerper + b"\nendobj\n"

    verweistabelle = len(datei)
    datei += f"xref\n0 {len(objekte) + 1}\n".encode("ascii")
    datei += b"0000000000 65535 f \n"
    for stelle in stellen:
        datei += f"{stelle:010d} 00000 n \n".encode("ascii")
    datei += (f"trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R >>\n"
              f"startxref\n{verweistabelle}\n%%EOF\n").encode("ascii")

    ordner = os.path.dirname(os.path.abspath(pfad))
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    with open(pfad, "wb") as f:
        f.write(datei)
    return pfad
