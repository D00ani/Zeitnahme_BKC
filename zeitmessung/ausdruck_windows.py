# -*- coding: utf-8 -*-
"""
Ausdruck unter Windows - über die Zeichenschnittstelle GDI.

Derselbe Weg, den auch das alte Programm benutzt hat. Dadurch steht die
Karte mit Verdana und exakt denselben Millimetermaßen auf dem Papier.

Ist ein Ziel angegeben, schreibt Windows den Auftrag über den mitgelieferten
Drucker „Microsoft Print to PDF“ direkt in diese Datei - das ist die
PDF-Vorschau.
"""
import ctypes
import os
from ctypes import wintypes

from .ausdruck import PDF_DRUCKER, DruckFehler


# GDI-Konstanten
_LOGPIXELSX = 88
_LOGPIXELSY = 90
_PHYSICALOFFSETX = 112
_PHYSICALOFFSETY = 113
_TA_TOP = 0
_TA_LEFT = 0
_TRANSPARENT = 1
_FW_NORMAL = 400
_FW_BOLD = 700
_ANSI_CHARSET = 0
_PS_SOLID = 0


class _DOCINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_int),
                ("lpszDocName", wintypes.LPCWSTR),
                ("lpszOutput", wintypes.LPCWSTR),
                ("lpszDatatype", wintypes.LPCWSTR),
                ("fwType", wintypes.DWORD)]


def standarddrucker():
    """Name des eingestellten Standarddruckers ("" wenn keiner da ist)."""
    try:
        winspool = ctypes.WinDLL("winspool.drv")
        laenge = wintypes.DWORD(0)
        winspool.GetDefaultPrinterW(None, ctypes.byref(laenge))
        if not laenge.value:
            return ""
        puffer = ctypes.create_unicode_buffer(laenge.value)
        if winspool.GetDefaultPrinterW(puffer, ctypes.byref(laenge)):
            return puffer.value
    except (OSError, AttributeError):
        pass
    return ""


def drucker_liste():
    """Alle eingerichteten Drucker."""
    try:
        winspool = ctypes.WinDLL("winspool.drv")
        noetig = wintypes.DWORD(0)
        anzahl = wintypes.DWORD(0)
        # Stufe 4 = Name + Server, das reicht und ist auf allen Windows da
        winspool.EnumPrintersW(0x00000002 | 0x00000004, None, 4, None, 0,
                               ctypes.byref(noetig), ctypes.byref(anzahl))
        if not noetig.value:
            return []
        puffer = ctypes.create_string_buffer(noetig.value)
        if not winspool.EnumPrintersW(0x00000002 | 0x00000004, None, 4, puffer,
                                      noetig.value, ctypes.byref(noetig),
                                      ctypes.byref(anzahl)):
            return []

        class _PRINTER_INFO_4(ctypes.Structure):
            _fields_ = [("pPrinterName", wintypes.LPWSTR),
                        ("pServerName", wintypes.LPWSTR),
                        ("Attributes", wintypes.DWORD)]

        felder = ctypes.cast(puffer,
                             ctypes.POINTER(_PRINTER_INFO_4 * anzahl.value))
        return [e.pPrinterName for e in felder.contents if e.pPrinterName]
    except (OSError, AttributeError, ValueError):
        return []


# Windows bringt diesen Drucker seit Windows 10 mit. Er erzeugt aus dem
# ganz normalen Druckauftrag eine PDF-Datei.
PDF_DRUCKER = "Microsoft Print to PDF"


def ausgeben(anweisungen, druckername, dokumentname, ausgabedatei=None):
    """Schickt den Bauplan an den Drucker - oder in eine PDF-Datei."""
    if ausgabedatei:
        if PDF_DRUCKER not in (drucker_liste() or [PDF_DRUCKER]):
            raise DruckFehler(
                f"Für die PDF-Vorschau wird der Windows-Drucker "
                f"„{PDF_DRUCKER}“ gebraucht, er ist aber nicht eingerichtet.")
        os.makedirs(os.path.dirname(ausgabedatei), exist_ok=True)
    if not druckername:
        raise DruckFehler("Es ist kein Drucker eingerichtet.")
    _zeichne_auf_drucker(anweisungen, druckername, dokumentname, ausgabedatei)
    return ausgabedatei


def _gdi():
    """Lädt gdi32 und legt für jede benutzte Funktion die Parametertypen fest.

    Das ist auf 64-Bit-Windows zwingend: Zeiger auf Schriften und Stifte sind
    dort 64 Bit breit. Ohne diese Angaben behandelt ctypes sie als einfache
    Ganzzahl und bricht mit „int too long to convert“ ab, sobald Windows
    einen hohen Adresswert zurückgibt.
    """
    gdi = ctypes.WinDLL("gdi32")
    H = wintypes.HANDLE
    HDC = wintypes.HDC
    prototypen = {
        "CreateDCW": ([wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                       ctypes.c_void_p], HDC),
        "DeleteDC": ([HDC], wintypes.BOOL),
        "GetDeviceCaps": ([HDC, ctypes.c_int], ctypes.c_int),
        "CreateFontW": ([ctypes.c_int] * 4 + [wintypes.DWORD] * 5 +
                        [wintypes.DWORD] * 4 + [wintypes.LPCWSTR], H),
        "CreatePen": ([ctypes.c_int, ctypes.c_int, wintypes.COLORREF], H),
        "SelectObject": ([HDC, H], H),
        "DeleteObject": ([H], wintypes.BOOL),
        "SetTextAlign": ([HDC, wintypes.UINT], wintypes.UINT),
        "SetBkMode": ([HDC, ctypes.c_int], ctypes.c_int),
        "SetTextColor": ([HDC, wintypes.COLORREF], wintypes.COLORREF),
        "TextOutW": ([HDC, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR,
                      ctypes.c_int], wintypes.BOOL),
        "MoveToEx": ([HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p],
                     wintypes.BOOL),
        "LineTo": ([HDC, ctypes.c_int, ctypes.c_int], wintypes.BOOL),
        "StartDocW": ([HDC, ctypes.POINTER(_DOCINFO)], ctypes.c_int),
        "StartPage": ([HDC], ctypes.c_int),
        "EndPage": ([HDC], ctypes.c_int),
        "EndDoc": ([HDC], ctypes.c_int),
        "AbortDoc": ([HDC], ctypes.c_int),
    }
    for name, (argumente, rueckgabe) in prototypen.items():
        funktion = getattr(gdi, name)
        funktion.argtypes = argumente
        funktion.restype = rueckgabe
    return gdi


def _zeichne_auf_drucker(anweisungen, druckername, dokumentname,
                         ausgabedatei=None):
    gdi = _gdi()
    hdc = gdi.CreateDCW("WINSPOOL", druckername, None, None)
    if not hdc:
        raise DruckFehler(f"Der Drucker „{druckername}“ ist nicht erreichbar.")

    schriften = {}
    stifte = {}
    try:
        dpi_x = gdi.GetDeviceCaps(hdc, _LOGPIXELSX) or 300
        dpi_y = gdi.GetDeviceCaps(hdc, _LOGPIXELSY) or 300
        # Der Drucker kann am Rand nicht drucken; GDI zählt aber ab der
        # Blattkante. Dieser Versatz wird abgezogen, damit die im Fenster
        # eingestellten Millimeter auch wirklich gemessene Millimeter sind.
        versatz_x = gdi.GetDeviceCaps(hdc, _PHYSICALOFFSETX)
        versatz_y = gdi.GetDeviceCaps(hdc, _PHYSICALOFFSETY)

        def px_x(mm):
            return int(round(mm / 25.4 * dpi_x)) - versatz_x

        def px_y(mm):
            return int(round(mm / 25.4 * dpi_y)) - versatz_y

        def schrift(kennung):
            if kennung not in schriften:
                familie, punkte, fett = kennung
                hoehe = -int(round(punkte * dpi_y / 72.0))
                schriften[kennung] = gdi.CreateFontW(
                    hoehe, 0, 0, 0, _FW_BOLD if fett else _FW_NORMAL,
                    0, 0, 0, _ANSI_CHARSET, 0, 0, 0, 0, familie)
            return schriften[kennung]

        def stift(breite_mm):
            if breite_mm not in stifte:
                dicke = max(1, int(round(breite_mm / 25.4 * dpi_x)))
                stifte[breite_mm] = gdi.CreatePen(_PS_SOLID, dicke, 0x000000)
            return stifte[breite_mm]

        # Ist ein Ziel angegeben, schreibt Windows den Auftrag direkt in
        # diese Datei, statt nach einem Dateinamen zu fragen.
        info = _DOCINFO(ctypes.sizeof(_DOCINFO), dokumentname, ausgabedatei,
                        None, 0)
        if gdi.StartDocW(hdc, ctypes.byref(info)) <= 0:
            raise DruckFehler("Der Druckauftrag wurde nicht angenommen.")
        if gdi.StartPage(hdc) <= 0:
            gdi.AbortDoc(hdc)
            raise DruckFehler("Die Seite konnte nicht begonnen werden.")

        gdi.SetTextAlign(hdc, _TA_TOP | _TA_LEFT)
        gdi.SetBkMode(hdc, _TRANSPARENT)
        gdi.SetTextColor(hdc, 0x000000)

        for anweisung in anweisungen:
            if anweisung[0] == "text":
                _, x, y, kennung, inhalt = anweisung
                alt = gdi.SelectObject(hdc, schrift(kennung))
                text = str(inhalt)
                gdi.TextOutW(hdc, px_x(x), px_y(y), text, len(text))
                gdi.SelectObject(hdc, alt)
            else:
                _, x1, y1, x2, y2, breite = anweisung
                alt = gdi.SelectObject(hdc, stift(breite))
                gdi.MoveToEx(hdc, px_x(x1), px_y(y1), None)
                gdi.LineTo(hdc, px_x(x2), px_y(y2))
                gdi.SelectObject(hdc, alt)

        gdi.EndPage(hdc)
        gdi.EndDoc(hdc)
    finally:
        for objekt in list(schriften.values()) + list(stifte.values()):
            gdi.DeleteObject(objekt)
        gdi.DeleteDC(hdc)
