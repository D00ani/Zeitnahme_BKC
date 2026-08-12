# -*- coding: utf-8 -*-
"""
Nur ein Programm je Datenbank.

Zwei gleichzeitig laufende Zeitmessungen auf derselben Datei wären ein
stiller Datensalat: beide schreiben Ergebnisse, beide vergeben
Startnummern, und keine merkt etwas von der anderen. Genau so ein
Durcheinander gab es beim alten Live-Timing, wo versehentlich drei Fenster
gleichzeitig liefen.

Umgesetzt über eine gesperrte Datei neben der Datenbank. Das Betriebssystem
gibt die Sperre beim Beenden von selbst wieder frei - auch dann, wenn das
Programm abstürzt oder der Rechner ausgeht. Es bleiben also keine
Sperrdateien liegen, die man von Hand wegräumen müsste.
"""
import os
import sys

if sys.platform.startswith("win"):
    import msvcrt
else:
    import fcntl


class Sperre:
    """Wird beim Start gesetzt und beim Beenden gelöst."""

    def __init__(self, datenbankpfad):
        self.pfad = os.path.abspath(datenbankpfad) + ".sperre"
        self._datei = None

    @property
    def gehalten(self):
        return self._datei is not None

    def setzen(self):
        """True, wenn diese Instanz die Datenbank allein benutzt."""
        if self.gehalten:
            return True
        ordner = os.path.dirname(self.pfad)
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        try:
            datei = open(self.pfad, "a+")
        except OSError:
            # Kein Schreibrecht - dann eben ohne Sperre weiterarbeiten,
            # statt das Programm am Renntag gar nicht starten zu lassen.
            return True
        try:
            self._verriegeln(datei)
        except OSError:
            datei.close()
            return False

        datei.seek(0)
        datei.truncate()
        datei.write(str(os.getpid()))
        datei.flush()
        self._datei = datei
        return True

    def loesen(self):
        datei, self._datei = self._datei, None
        if datei is None:
            return
        try:
            self._entriegeln(datei)
        except OSError:
            pass
        datei.close()
        try:
            os.remove(self.pfad)
        except OSError:
            pass          # unter Windows kann die Datei noch belegt sein

    def __enter__(self):
        self.setzen()
        return self

    def __exit__(self, *_):
        self.loesen()

    # ------------------------------------------------------------------
    # Windows sperrt einzelne Bytes und lässt sie dann auch nicht mehr lesen.
    # Gesperrt wird deshalb ein Byte weit hinter dem Text, damit die
    # Prozessnummer am Dateianfang lesbar bleibt.
    _SPERRSTELLE = 4096

    @classmethod
    def _verriegeln(cls, datei):
        if sys.platform.startswith("win"):
            datei.seek(cls._SPERRSTELLE)
            msvcrt.locking(datei.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(datei.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @classmethod
    def _entriegeln(cls, datei):
        if sys.platform.startswith("win"):
            datei.seek(cls._SPERRSTELLE)
            msvcrt.locking(datei.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(datei.fileno(), fcntl.LOCK_UN)

    def wer_haelt_sie(self):
        """Prozessnummer der anderen Instanz, so weit lesbar."""
        try:
            with open(self.pfad, encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        except OSError:
            return ""
