# -*- coding: utf-8 -*-
"""
Lichtschranke unter Linux - über die serielle Schnittstelle mit ``termios``.

``termios`` gehört zur Standardbibliothek, es muss also auch hier nichts
installiert werden. Der USB-Adapter der Zeitnahme (FTDI) wird von Linux
ohne Treiber erkannt und meldet sich als ``/dev/ttyUSB0``.

Wie in der Windows-Fassung gilt: **jedes** eingehende Signal bedeutet
"jemand ist durchgefahren", der Inhalt ist egal. Der Zeitstempel wird sofort
beim Eintreffen genommen.
"""
import glob
import os
import threading
import time

try:
    import select
    import termios
except ImportError:                     # pragma: no cover - nur auf Windows
    select = termios = None


def _baudkonstante(baudrate):
    """9600 -> termios.B9600. Unbekannte Werte fallen auf 9600 zurück."""
    name = f"B{int(baudrate)}"
    return getattr(termios, name, termios.B9600)


def verfuegbare_ports():
    """Alle seriellen Schnittstellen, z. B. ["/dev/ttyUSB0"].

    ``ttyUSB`` sind USB-Seriell-Adapter (dazu gehört der Transceiver der
    Zeitnahme), ``ttyACM`` sind Geräte mit eigener USB-Steuerung. Die alten
    ``ttyS``-Anschlüsse werden weggelassen - davon meldet Linux meist ein
    Dutzend, die es gar nicht gibt.
    """
    gefunden = []
    for muster in ("/dev/ttyUSB*", "/dev/ttyACM*"):
        gefunden.extend(glob.glob(muster))
    return sorted(set(gefunden))


def port_beschreibungen():
    """{"/dev/ttyUSB0": "FTDI FT232R USB UART"} - so weit ermittelbar.

    Die Angaben stehen im System unter ``/sys``; dafür wird kein
    Zusatzprogramm gebraucht.
    """
    beschreibungen = {}
    for pfad in verfuegbare_ports():
        name = os.path.basename(pfad)
        teile = []
        for feld in ("manufacturer", "product"):
            # ../.. führt vom tty-Gerät zum eigentlichen USB-Gerät
            datei = f"/sys/class/tty/{name}/device/../../{feld}"
            try:
                with open(datei, encoding="utf-8", errors="replace") as f:
                    wert = f.read().strip()
                if wert:
                    teile.append(wert)
            except OSError:
                pass
        beschreibungen[pfad] = " ".join(teile) + f" ({pfad})" if teile else pfad
    return beschreibungen


class Lichtschranke:
    """Hört auf einer seriellen Schnittstelle und ruft bei jedem Signal
    ``bei_signal(zeitstempel)`` auf - aus einem Hintergrundfaden."""

    def __init__(self, port, baudrate=9600, bei_signal=None,
                 bei_fehler=None, uhr=time.monotonic):
        self.port = port
        self.baudrate = int(baudrate)
        self.bei_signal = bei_signal or (lambda zeitstempel: None)
        self.bei_fehler = bei_fehler or (lambda meldung: None)
        self.uhr = uhr
        self._fd = None
        self._faden = None
        self._laeuft = threading.Event()

    @property
    def offen(self):
        return self._fd is not None

    # ------------------------------------------------------------------
    def oeffnen(self):
        if self.offen:
            return True
        if not self.port:
            self.bei_fehler("Es ist keine Schnittstelle eingestellt. "
                            "Zeiten lassen sich weiterhin mit F1 messen.")
            return False
        if termios is None:
            self.bei_fehler("Serielle Schnittstellen werden auf diesem System "
                            "nicht unterstützt.")
            return False

        try:
            fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        except PermissionError:
            self.bei_fehler(
                f"Keine Berechtigung für {self.port}. Der Benutzer muss in "
                f"der Gruppe „dialout“ sein:  sudo usermod -aG dialout $USER  "
                f"(danach neu anmelden). Zeiten lassen sich weiterhin mit F1 "
                f"messen.")
            return False
        except OSError as fehler:
            self.bei_fehler(f"Die Schnittstelle {self.port} lässt sich nicht "
                            f"öffnen ({fehler.strerror}). Zeiten lassen sich "
                            f"weiterhin mit F1 messen.")
            return False

        try:
            self._einstellen(fd)
        except (termios.error, OSError) as fehler:
            os.close(fd)
            self.bei_fehler(f"Die Schnittstelle {self.port} ließ sich nicht "
                            f"einstellen: {fehler}")
            return False

        self._fd = fd
        self._laeuft.set()
        self._faden = threading.Thread(target=self._lesen, daemon=True,
                                       name=f"Lichtschranke-{self.port}")
        self._faden.start()
        return True

    def _einstellen(self, fd):
        """8 Datenbits, keine Parität, 1 Stoppbit, keine Flusssteuerung -
        dieselben Werte wie in der Windows-Fassung."""
        einstellungen = termios.tcgetattr(fd)
        iflag, oflag, cflag, lflag, ispeed, ospeed, cc = einstellungen

        cflag |= termios.CLOCAL | termios.CREAD
        cflag &= ~termios.CSIZE
        cflag |= termios.CS8
        cflag &= ~termios.PARENB          # keine Parität
        cflag &= ~termios.CSTOPB          # 1 Stoppbit
        if hasattr(termios, "CRTSCTS"):
            cflag &= ~termios.CRTSCTS     # keine Hardware-Flusssteuerung

        # Rohbetrieb: nichts umkodieren, nichts auf Zeilen warten
        lflag &= ~(termios.ICANON | termios.ECHO | termios.ECHOE | termios.ISIG)
        iflag &= ~(termios.IXON | termios.IXOFF | termios.IXANY)
        iflag &= ~(termios.INLCR | termios.ICRNL | termios.IGNCR)
        oflag &= ~termios.OPOST

        cc = list(cc)
        cc[termios.VMIN] = 0
        cc[termios.VTIME] = 0

        baud = _baudkonstante(self.baudrate)
        termios.tcsetattr(fd, termios.TCSANOW,
                          [iflag, oflag, cflag, lflag, baud, baud, cc])
        termios.tcflush(fd, termios.TCIFLUSH)

    # ------------------------------------------------------------------
    def schliessen(self):
        self._laeuft.clear()
        faden, self._faden = self._faden, None
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if faden and faden.is_alive():
            faden.join(timeout=1.0)

    def _lesen(self):
        while self._laeuft.is_set():
            fd = self._fd
            if fd is None:
                break
            try:
                bereit, _, _ = select.select([fd], [], [], 0.2)
            except (OSError, ValueError):
                break
            if not bereit:
                continue                      # nur der Zeitablauf, weiterhören
            try:
                daten = os.read(fd, 64)
            except BlockingIOError:
                continue
            except OSError:
                if self._laeuft.is_set():
                    self.bei_fehler(f"Die Verbindung zu {self.port} ist "
                                    f"abgerissen.")
                break
            if not daten:
                continue

            zeitstempel = self.uhr()          # so früh wie möglich festhalten
            try:
                # Alles, was im selben Moment nachkommt, gehört zum selben
                # Durchfahren und wird verworfen.
                termios.tcflush(fd, termios.TCIFLUSH)
            except (termios.error, OSError):
                pass
            try:
                self.bei_signal(zeitstempel)
            except Exception as fehler:       # noqa: BLE001
                self.bei_fehler(f"Fehler beim Verarbeiten des Signals: {fehler}")
