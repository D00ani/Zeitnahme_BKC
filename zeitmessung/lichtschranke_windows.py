# -*- coding: utf-8 -*-
"""
Lichtschranke unter Windows - über die serielle Schnittstelle der Win32-API.

Angesprochen wird sie direkt mit ``ctypes``, damit kein Zusatzpaket
installiert werden muss. Der Zeitstempel wird sofort beim Eintreffen des
Signals genommen, noch bevor die Oberfläche etwas davon mitbekommt.
"""
import ctypes
import threading
import time
from ctypes import wintypes

# --- Windows-Konstanten ---
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_PURGE_RXCLEAR = 0x0008
_PURGE_RXABORT = 0x0002


class _COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [("ReadIntervalTimeout", wintypes.DWORD),
                ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
                ("ReadTotalTimeoutConstant", wintypes.DWORD),
                ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
                ("WriteTotalTimeoutConstant", wintypes.DWORD)]


class _DCB(ctypes.Structure):
    """Wird nicht von Hand befüllt, sondern von ``BuildCommDCBW`` - damit
    müssen die Bitfelder hier nicht nachgebaut werden."""
    _fields_ = [("DCBlength", wintypes.DWORD),
                ("BaudRate", wintypes.DWORD),
                ("fFlags", wintypes.DWORD),
                ("wReserved", wintypes.WORD),
                ("XonLim", wintypes.WORD),
                ("XoffLim", wintypes.WORD),
                ("ByteSize", wintypes.BYTE),
                ("Parity", wintypes.BYTE),
                ("StopBits", wintypes.BYTE),
                ("XonChar", ctypes.c_char),
                ("XoffChar", ctypes.c_char),
                ("ErrorChar", ctypes.c_char),
                ("EofChar", ctypes.c_char),
                ("EvtChar", ctypes.c_char),
                ("wReserved1", wintypes.WORD)]


def verfuegbare_ports():
    """Alle seriellen Schnittstellen des Rechners, z. B. ["COM3", "COM6"].

    Zusätzlich wird - wenn möglich - dazugeschrieben, was daran hängt.
    Das hilft bei der Einrichtung: Bluetooth-Schnittstellen heißen anders
    als der USB-Adapter der Zeitnahme, und man erwischt nicht den falschen.
    """
    ports = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DEVICEMAP\SERIALCOMM") as schluessel:
            for i in range(winreg.QueryInfoKey(schluessel)[1]):
                _, wert, _ = winreg.EnumValue(schluessel, i)
                ports.append(str(wert))
    except (ImportError, OSError):
        pass
    return sorted(set(ports), key=lambda p: (len(p), p))


def port_beschreibungen():
    """{"COM6": "USB Serial Port (COM6)"} - leer, wenn es nicht ermittelbar
    ist. Rein informativ für das Einstellungsfenster."""
    beschreibungen = {}
    try:
        import subprocess
        befehl = ("Get-CimInstance Win32_PnPEntity | "
                  "Where-Object { $_.Name -match '\\(COM\\d+\\)' } | "
                  "ForEach-Object { $_.Name }")
        ergebnis = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", befehl],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, creationflags=0x08000000)  # kein Konsolenfenster
        # (dieses Modul läuft ohnehin nur unter Windows)
        for zeile in (ergebnis.stdout or "").splitlines():
            zeile = zeile.strip()
            if "(COM" in zeile:
                port = zeile[zeile.rfind("(COM") + 1:zeile.rfind(")")]
                beschreibungen[port] = zeile
    except Exception:          # noqa: BLE001 - Beschreibung ist reiner Komfort
        pass
    return beschreibungen


class Lichtschranke:
    """Hört auf einer seriellen Schnittstelle und ruft bei jedem Signal
    ``bei_signal(zeitstempel)`` auf.

    Der Aufruf kommt aus einem Hintergrundfaden. Die Oberfläche muss ihn
    deshalb in den eigenen Faden weiterreichen (tkinter: ``after``).
    """

    def __init__(self, port, baudrate=9600, bei_signal=None,
                 bei_fehler=None, uhr=time.monotonic):
        self.port = port
        self.baudrate = int(baudrate)
        self.bei_signal = bei_signal or (lambda zeitstempel: None)
        self.bei_fehler = bei_fehler or (lambda meldung: None)
        self.uhr = uhr
        self._handle = None
        self._faden = None
        self._laeuft = threading.Event()

    # ------------------------------------------------------------------
    @property
    def offen(self):
        return self._handle is not None

    def oeffnen(self):
        """Öffnet die Schnittstelle. Gibt True zurück, wenn es geklappt hat;
        sonst wird ``bei_fehler`` mit einer Erklärung gerufen."""
        if self.offen:
            return True
        if not self.port:
            self.bei_fehler("Es ist keine Schnittstelle eingestellt. "
                            "Zeiten lassen sich weiterhin mit F1 messen.")
            return False

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.restype = wintypes.HANDLE
        # Die Schreibweise \\.\COM6 ist nötig, sobald die Nummer zweistellig
        # wird - sie funktioniert aber für alle Schnittstellen.
        handle = kernel.CreateFileW(f"\\\\.\\{self.port}",
                                    _GENERIC_READ | _GENERIC_WRITE,
                                    0, None, _OPEN_EXISTING, 0, None)
        if handle == _INVALID_HANDLE or not handle:
            fehler = ctypes.get_last_error()
            if fehler == 5:
                grund = "sie wird schon von einem anderen Programm benutzt"
            elif fehler == 2:
                grund = "es gibt sie nicht (Stecker eingesteckt?)"
            else:
                grund = f"Windows meldet Fehler {fehler}"
            self.bei_fehler(f"Die Schnittstelle {self.port} lässt sich nicht "
                            f"öffnen - {grund}. Zeiten lassen sich weiterhin "
                            f"mit F1 messen.")
            return False

        dcb = _DCB()
        dcb.DCBlength = ctypes.sizeof(_DCB)
        vorgabe = f"baud={self.baudrate} parity=N data=8 stop=1"
        if not kernel.BuildCommDCBW(vorgabe, ctypes.byref(dcb)) or \
           not kernel.SetCommState(handle, ctypes.byref(dcb)):
            # Nicht schlimm: viele Adapter arbeiten auch mit den Werten, die
            # ohnehin eingestellt sind. Weitermachen statt abbrechen.
            pass

        zeiten = _COMMTIMEOUTS(0, 0, 200, 0, 0)   # 200 ms je Leseversuch
        kernel.SetCommTimeouts(handle, ctypes.byref(zeiten))
        kernel.PurgeComm(handle, _PURGE_RXCLEAR | _PURGE_RXABORT)

        self._handle = handle
        self._laeuft.set()
        self._faden = threading.Thread(target=self._lesen, args=(kernel,),
                                       name=f"Lichtschranke-{self.port}",
                                       daemon=True)
        self._faden.start()
        return True

    def schliessen(self):
        self._laeuft.clear()
        faden, self._faden = self._faden, None
        handle, self._handle = self._handle, None
        if handle:
            try:
                kernel = ctypes.WinDLL("kernel32")
                kernel.PurgeComm(handle, _PURGE_RXCLEAR | _PURGE_RXABORT)
                kernel.CloseHandle(handle)
            except OSError:
                pass
        if faden and faden.is_alive():
            faden.join(timeout=1.0)

    # ------------------------------------------------------------------
    def _lesen(self, kernel):
        puffer = ctypes.create_string_buffer(64)
        gelesen = wintypes.DWORD(0)
        while self._laeuft.is_set():
            handle = self._handle
            if not handle:
                break
            erfolg = kernel.ReadFile(handle, puffer, 64,
                                     ctypes.byref(gelesen), None)
            if not erfolg:
                if self._laeuft.is_set():
                    self.bei_fehler(f"Die Verbindung zu {self.port} ist "
                                    f"abgerissen.")
                break
            if gelesen.value <= 0:
                continue                      # nur der Zeitablauf, weiterhören

            zeitstempel = self.uhr()          # so früh wie möglich festhalten
            # Alles, was im selben Moment noch hinterherkommt, gehört zum
            # selben Durchfahren und wird verworfen.
            kernel.PurgeComm(handle, _PURGE_RXCLEAR)
            try:
                self.bei_signal(zeitstempel)
            except Exception as fehler:       # noqa: BLE001
                self.bei_fehler(f"Fehler beim Verarbeiten des Signals: {fehler}")
