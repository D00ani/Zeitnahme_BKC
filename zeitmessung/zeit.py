# -*- coding: utf-8 -*-
"""
Zeitarithmetik.

Alle Zeiten laufen im Programm als **ganze Hundertstelsekunden** (int) durch.
Erst zur Anzeige und zum Speichern wird daraus Text im Format ``mm:ss,hh``.

Warum so: Das alte Programm hat Zeiten als Text herumgereicht und an mehreren
Stellen mit Stringschnippeln zusammengerechnet. Dabei sind zwei Formate
entstanden (``mm:ss,hh`` mit Komma und ``mm:ss:hh`` mit Doppelpunkt), und beim
Runden konnte ``00:05,100`` herauskommen. Mit einer einzigen Ganzzahl als
Grundlage kann das nicht mehr passieren.
"""
import re

HUNDERTSTEL_PRO_SEKUNDE = 100
HUNDERTSTEL_PRO_MINUTE = 60 * HUNDERTSTEL_PRO_SEKUNDE

# "mm:ss,hh" - Minuten dürfen auch dreistellig werden, Hundertstel ein- oder
# zweistellig (einstellig wird als Zehntel gelesen: "1,5" = 50 Hundertstel).
_MUSTER = re.compile(r"^\s*(\d{1,3}):([0-5]?\d),(\d{1,2})\s*$")

NULLZEIT = "00:00,00"

# Kennzeichnung "nicht gewertet" (Ausschluss/Disqualifikation). Das alte
# Programm hat dafür an einzelnen Stellen den Text "ADW" in die Zeitspalte
# geschrieben; die Live-Seite kennt ihn bereits und sortiert solche Starter
# ans Ende.
AUSSCHLUSS = "ADW"


def formatiere(hundertstel):
    """3661 -> "00:36,61". Negative Werte werden als Betrag ausgegeben."""
    hundertstel = abs(int(hundertstel))
    minuten = hundertstel // HUNDERTSTEL_PRO_MINUTE
    sekunden = hundertstel % HUNDERTSTEL_PRO_MINUTE // HUNDERTSTEL_PRO_SEKUNDE
    rest = hundertstel % HUNDERTSTEL_PRO_SEKUNDE
    return f"{minuten:02d}:{sekunden:02d},{rest:02d}"


def parse(text):
    """"00:36,61" -> 3661. Gibt None zurück, wenn dort keine Zeit steht
    (z. B. leer oder "ADW")."""
    if isinstance(text, (int, float)):
        return int(text)
    treffer = _MUSTER.match(text or "")
    if not treffer:
        return None
    minuten, sekunden, rest = treffer.groups()
    # "1,5" meint 5 Zehntel, also 50 Hundertstel
    rest = rest.ljust(2, "0")
    return (int(minuten) * 60 + int(sekunden)) * HUNDERTSTEL_PRO_SEKUNDE + int(rest)


def addiere(*zeiten):
    """Summiert Zeiten, die als Text oder als Hundertstel vorliegen.
    Unlesbare Angaben zählen als 0 - so wie im alten Programm ein leeres
    Feld als "00:00,00" behandelt wurde."""
    summe = 0
    for zeit in zeiten:
        wert = parse(zeit) if isinstance(zeit, str) else zeit
        summe += int(wert or 0)
    return summe


# Rechenungenauigkeit der Fließkommazahlen, in Hundertsteln. Zieht man zwei
# Uhrwerte voneinander ab, kommt statt 41,03 s schon mal 41,029999999999994
# heraus. Ohne diesen Ausgleich würde daraus beim Abschneiden 41,02 - eine
# um ein Hundertstel zu kurze Zeit. Der Wert liegt bei einem Hunderttausendstel
# einer Sekunde und damit weit unter allem, was eine Lichtschranke auflöst.
_RECHENUNSCHAERFE = 1e-6


def aus_sekunden(sekunden):
    """Sekunden (float, z. B. aus der Stoppuhr) -> Hundertstel.

    Es wird **abgeschnitten und nicht gerundet**: eine Zeit von 36,619 s ist
    36,61 - genau wie eine Stoppuhr, die nur Hundertstel anzeigt. Rundung
    würde bedeuten, dass eine Zeit auf dem Ausdruck größer sein kann als die
    tatsächlich gefahrene.
    """
    if sekunden <= 0:
        return 0
    return int(sekunden * HUNDERTSTEL_PRO_SEKUNDE + _RECHENUNSCHAERFE)


def strafzeit(pylonen, fehler, sekunden_pro_pylone, sekunden_pro_fehler):
    """Strafsekunden aus Pylonen und Fahrfehlern - als ganze Sekunden,
    so wie sie auf der Ergebniskarte stehen."""
    return (int(pylonen or 0) * int(sekunden_pro_pylone or 0)
            + int(fehler or 0) * int(sekunden_pro_fehler or 0))


def sekunden_in_hundertstel(sekunden):
    """Ganze Strafsekunden -> Hundertstel."""
    return int(sekunden or 0) * HUNDERTSTEL_PRO_SEKUNDE


def ist_zeit(text):
    """Steht in dem Feld eine verwertbare Zeit?"""
    return parse(text) is not None
