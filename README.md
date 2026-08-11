# Zeitmessung

Zeitmessung für Kart-Slalom mit eingebautem Live-Timing. Nachbau des
Vereinsprogramms `Zeitmessung_Kart` in Python – gleiche Funktionen, gleiche
Rechenregeln, gleicher Ausdruck, aber übersichtlicher aufgebaut und
automatisch geprüft.

Das alte Programm bleibt unangetastet und weiter benutzbar.

## Starten

**Windows:** Doppelklick auf `Zeitmessung.bat`
**Linux:** `./Zeitmessung.sh`

Es wird nichts installiert und nichts zusätzlich gebraucht – nur Python,
das auf dem Rechner schon vorhanden ist. Weder Access-Treiber noch
Zusatzpakete.

### Linux

Läuft ab Werk mit. Einmalig gebraucht werden Python, tkinter, Git und das
Drucksystem:

```
sudo apt install python3 python3-tk git cups-client
sudo usermod -aG dialout $USER      # Zugriff auf die Lichtschranke
```

Nach dem `usermod` einmal ab- und wieder anmelden, sonst darf das Programm
die serielle Schnittstelle nicht öffnen.

Was anders ist als unter Windows:

| | Windows | Linux |
|---|---|---|
| Lichtschranke | `COM6` | `/dev/ttyUSB0` |
| Druck | über GDI, Schrift **Verdana** | als PDF an CUPS, Schrift **Helvetica** |
| Altdaten aus Access übernehmen | ja | nein – einmalig unter Windows machen |

Der FTDI-Adapter der Zeitnahme wird von Linux ohne Treiber erkannt. Der
Knopf „Ports prüfen“ in den Einstellungen zeigt, was woran hängt.

Die Ergebniskarte sitzt auf **denselben Millimeterpositionen** wie unter
Windows – das ist gemessen und durch Tests abgesichert, die Grundlinien
weichen um höchstens 0,05 mm ab. Nur die Schrift ist eine andere: Verdana
gehört Microsoft und darf nicht mitgeliefert werden, deshalb Helvetica.

## Beim ersten Mal einrichten

**Datei → Einstellungen**. Wichtig sind:

| Reiter | Was einstellen |
|---|---|
| Wertung | Runden, Wertungsläufe, Strafzeiten pro Pylone und Fehler |
| Training | Rundenzahl, Dauer, Warnton |
| Allgemein | Klassen und Vereine (mit `;` getrennt) |
| Lichtschranke | **Port** – der Knopf „Ports prüfen“ zeigt, was woran hängt |
| Ausdruck | **Drucker** (Auswahlliste), Ränder, PDF-Vorschau |
| Pfade | wo die Datenbank liegt |
| Live-Timing | siehe unten – ab Werk **aus** |

Der Knopf **Abbruch** verwirft nur; er setzt nichts zurück. Zum Zurücksetzen
gibt es einen eigenen Knopf, der vorher nachfragt und erst mit „Speichern“
wirksam wird.

### Alte Ergebnisse übernehmen

**Datei → Ergebnisse aus altem Programm übernehmen …** und die Datei
`Zeitmessung_Kart_Data.accdb` auswählen. Die alte Datenbank wird dabei
**nur gelesen** und bleibt bitgenau unverändert. Der Import lässt sich
gefahrlos wiederholen – schon vorhandene Ergebnisse werden übersprungen.

## Bedienen

Ganz oben steht immer ein Balken, der in einem Satz sagt, was gerade
passiert – z. B. `WERTUNGSLAUF 1 von 2 LÄUFT · Runde 2 von 2 · Nr. 7 Anton`
oder `TRAINING · im Training wird nichts gespeichert`. Während gemessen wird,
ist der Balken dunkel.

Darunter steht dauerhaft, ob die Lichtschranke verbunden ist. Steht dort
`NICHT verbunden`, läuft die Messung nur über `F1` – der Knopf
„Neu verbinden“ daneben versucht es noch einmal.

| Taste | Wirkung |
|---|---|
| `F1` | Start bzw. Runde/Zwischenzeit – identisch zum Lichtschrankensignal |
| `ESC` | laufenden Lauf verwerfen |
| `T` / `E` / `W` | Training, Einführungsrunde, Wertungslauf |
| `F4` | zurück auf die laufende Uhr |
| `F5`–`F8` | Zwischenzeit stehen lassen |

**Ablauf eines Wertungslaufs**

1. Modus „Wertungslauf“ wählen → Starterdaten eingeben
2. `F1` startet den 1. Wertungslauf; die Uhr läuft über alle Runden durch
3. Nach der letzten Runde: Pylonen und Fehler eintragen → „Weiter“
4. `F1` startet den 2. Wertungslauf
5. Nach der letzten Runde: eintragen → „Drucken“ → „Weiter“

Im **Training** wird jede Runde einzeln gemessen. Training schreibt bewusst
keine Ergebnisse in die Datenbank – so wie bisher.

Ein Lauf lässt sich wiederholen: Haken bei „Gültig“ entfernen, dann
„Wiederholen“.

### Drucker wählen

**Einstellungen → Ausdruck → Drucker.** Die Liste zeigt alle eingerichteten
Drucker; „Drucker prüfen“ liest sie neu ein und nennt den Windows-Standard.

Ein **leeres Feld** bedeutet „nimm den Windows-Standarddrucker“. Das ist
bequem, aber unsicher: Steht der Windows-Standard zufällig auf
„Microsoft Print to PDF“, kommt kein Papier heraus. Für den Renntag deshalb
lieber das Gerät ausdrücklich auswählen.

### Üben ohne Papier

**Einstellungen → Ausdruck → „Nur PDF-Vorschau statt Drucken“**

Dann wird nichts gedruckt. Stattdessen entsteht eine PDF im Unterordner
`vorschau\`, die sich sofort öffnet. Der Knopf im Starterfenster heißt in
diesem Fall „PDF-Vorschau“.

Die PDF entsteht über denselben Zeichenweg wie der echte Druck – sie zeigt
also millimetergenau das, was später auf dem Papier steht. Damit lassen sich
die Ränder bequem am Bildschirm einstellen, bevor das erste Blatt bedruckt
wird.

Zum Scharfschalten den Haken wieder entfernen.

Solange das Starterfenster offen ist, wird **jedes Signal ignoriert** – auch
das der Lichtschranke. Sonst liefe im Hintergrund unbemerkt schon der
nächste Lauf, während vorne noch Pylonen eingetragen werden. Ignorierte
Signale stehen im Verlauf, man sieht also hinterher, dass eines kam.

> **Wichtig am Renntag:** Die Anzeigetafel der Lichtschranke muss
> ausgeschaltet bleiben. Sie stört den USB-Adapter und führt zu falschen
> Zeiten.

### Wenn etwas schiefgegangen ist

**Ergebnisse → Ergebnisse heute …** zeigt alle Datensätze des Tages.
Dort lässt sich

* eine falsche **Pylonen- oder Fehlerzahl berichtigen** – Strafzeit und
  Gesamtzeit werden neu gerechnet, und das Gesamtergebnis des Fahrers wird
  automatisch mitgezogen,
* ein versehentlich gespeicherter **Datensatz löschen**.

Bei jedem Programmstart entsteht außerdem eine **Sicherungskopie** der
Datenbank in `daten\sicherungen\`. Die letzten 20 bleiben liegen.

## Live-Timing (abschaltbar)

Ab Werk **ausgeschaltet**. Dann ist das Programm eine reine Zeitmessung
ohne jeden Bezug zu einer Webseite – so kann es jeder andere Verein
unverändert benutzen.

Einschalten unter **Einstellungen → Live-Timing**:

| Einstellung | Bedeutung |
|---|---|
| Live-Timing benutzen | Hauptschalter |
| Name der Veranstaltung | steht im Kopf der Live-Seite |
| Datei livedata.json | wohin der aktuelle Stand geschrieben wird |
| Ordner für die Archive | dort landet je Renntag eine Datei |
| Ergebnisse automatisch veröffentlichen | zusätzlich per Git hochladen |
| Git-Ordner mit den Ergebnisdateien | der Ordner, in dem `livedata.json` liegt |
| Zweiter Git-Ordner | **nur** bei getrenntem Arbeits- und Live-Stand |
| Mindestabstand | wie oft höchstens hochgeladen wird |
| Zusätzliche Umgebungsvariable | z. B. `MCH_ERGEBNIS_PUSH=1` |

### Ein Ordner oder zwei?

**Ein Ordner – der einfache Weg.** Die Zeitnahme bekommt einen eigenen
kleinen Git-Ordner, der nur die Ergebnisdateien enthält, und veröffentlicht
daraus direkt. Das Feld „Zweiter Git-Ordner“ bleibt leer.

Damit hängt die Zeitnahme an keiner Webseiten-Pflege: Sie lässt sich auf
jeden Laptop kopieren, kann außerhalb von OneDrive liegen, und wer die
Webseite umbaut, kann der Zeitnahme nicht ins Gehege kommen.

**Zwei Ordner.** Nur nötig, wenn die Webseite mit getrenntem Arbeits- und
Live-Stand gepflegt wird (so wie bei MCH Singen). Dann werden gezielt nur
die Ergebnisdateien vom Arbeits- in den Live-Stand übernommen – ein
halbfertiger Umbau der Webseite geht dabei nie mit live.

Beide Wege sind durch Tests gegen ein echtes Git abgesichert.

Ist das Live-Timing an, schreibt sich die Datei **bei jedem gespeicherten
Ergebnis von selbst neu**. Es gibt keine Dauerschleife und kein zweites
Fenster mehr, das man vergessen oder doppelt starten kann.

Über das Menü **Live-Timing** lässt sich der Stand jederzeit von Hand
schreiben oder sofort veröffentlichen.

## Wo liegen die Daten

```
Zeitmessung_Daniel\
  daten\zeitmessung.db     alle Ergebnisse und der Verlauf (SQLite)
  einstellungen.json       alle Einstellungen
```

Beides sind schlichte Dateien – zum Sichern einfach kopieren.

## Was gegenüber dem alten Programm repariert wurde

| Problem im alten Programm | jetzt |
|---|---|
| Zeiten in zwei Formaten (`mm:ss,hh` und `mm:ss:hh`), je nach Codestelle | durchgehend ein Format |
| Runden konnte `00:05,100` erzeugen – eine unlesbare Zeit | kann nicht mehr auftreten |
| Zeitmessung über die Systemuhr: eine Uhrumstellung im Lauf verfälschte die Zeit | monotone Uhr, unabhängig von der Systemzeit |
| Zeit stammte aus einem 10-ms-Zeitgeber, nicht aus dem Moment der Auslösung | Zeitstempel direkt beim Signal |
| Endlosschleife mit `DoEvents`, die einen Prozessorkern auslastete | ruhiger Anzeigetakt |
| „Abbruch“ in den Einstellungen setzte alles auf Werkseinstellungen zurück | Abbruch verwirft nur |
| Platzierung zählte wiederholte Läufe doppelt mit | je Starter zählt der jüngste Lauf |
| Zwei zeitgleiche Fahrer bekamen verschiedene Plätze | gleicher Platz, nächster wird übersprungen |
| Startnummernvorschlag begann bei einer Nummer wie `A3` wieder bei 1 | überspringt nicht-numerische Nummern |
| Sortierung nach der Textspalte der Zeit | nach einer Zahlenspalte |
| Prüfung der Fahrfehler rechnete mit der Pylonen-Strafzeit | rechnet mit der richtigen |
| Druckerfehler hielt das Programm mit `Stop` an | Hinweis, Weiterarbeiten möglich |
| Nach Abbruch eines Wertungslaufs galt der nächste Auslöser als Einführungsrunde | startet den Lauf neu |
| Ein Signal während der Eingabe startete unbemerkt den nächsten Lauf | wird ignoriert und protokolliert |
| Eine falsche Pylonenzahl ließ sich nur direkt in Access berichtigen | „Ergebnisse heute“ im Programm |
| Keine Sicherung der Daten | Kopie bei jedem Programmstart |

Alle diese Punkte sind durch Tests abgesichert.

## Tests

```
Tests.bat
```

oder von Hand:

```
python -m unittest discover -s tests -t .
```

202 Tests: Zeitarithmetik, Strafzeiten, Platzierung, kompletter Rennablauf
mit gestellter Uhr, Datenbank, Berichtigen und Sichern, Altdaten-Import,
Druck-Layout, PDF-Vorschau, Live-Timing – und die Bedienung im echten
Fenster: Zustandsbalken, Lichtschranken-Anzeige und der Schutz gegen
Signale zur falschen Zeit.

## Aufbau

```
zeitmessung\
  zeit.py                    Zeitarithmetik in Hundertsteln
  einstellungen.py           alle Einstellungen und Pfade
  datenbank.py               Ergebnisse und Verlauf (SQLite), Access-Import
  ablauf.py                  Training/Einführung/Wertung als reine Logik
  wertung.py                 Strafzeiten, Summen, Platzierung
  livetiming.py              livedata.json, Archiv, Veröffentlichen

  ausdruck.py                Layout der Ergebniskarte, wählt den Druckweg
  ausdruck_pdf.py              als PDF – auf jedem System gleich
  ausdruck_windows.py          über GDI, mit Verdana
  ausdruck_linux.py            über CUPS

  lichtschranke.py           wählt die passende Schnittstelle
  lichtschranke_windows.py     über die Win32-API
  lichtschranke_linux.py       über termios

  oberflaeche\               die Fenster
```

Windows-Eigenes steckt ausschließlich in den beiden `*_windows.py` – alles
andere lässt sich auf Linux laden. Ein Test wacht darüber, dass das so
bleibt.

Die Logik ist bewusst von den Fenstern getrennt – nur dadurch lässt sich
ein kompletter Rennablauf automatisch durchspielen, ohne dass jemand
danebensitzen und Knöpfe drücken muss.
