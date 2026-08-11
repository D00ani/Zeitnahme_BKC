# -*- coding: utf-8 -*-
"""
Anbindung der Lichtschranke - wählt den Weg für dieses Betriebssystem.

Die Lichtschranke schickt beim Durchfahren ein paar Bytes über den
USB-Adapter. Was genau sie schickt, ist egal: jedes Signal bedeutet "jemand
ist durchgefahren" und wirkt wie ein Druck auf F1. So hat es das alte
Programm auch gehandhabt.

Beide Fassungen kommen ohne Zusatzpakete aus - Windows über die Win32-API,
Linux über ``termios``. Nach außen sehen sie gleich aus:

``Lichtschranke(port, baudrate, bei_signal=, bei_fehler=)`` mit
``oeffnen()``, ``schliessen()`` und ``offen``, dazu ``verfuegbare_ports()``
und ``port_beschreibungen()``.
"""
import sys

if sys.platform.startswith("win"):
    from .lichtschranke_windows import (Lichtschranke, port_beschreibungen,
                                        verfuegbare_ports)
else:
    from .lichtschranke_linux import (Lichtschranke, port_beschreibungen,
                                      verfuegbare_ports)

__all__ = ["Lichtschranke", "verfuegbare_ports", "port_beschreibungen"]
