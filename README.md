<p align="center"><img src="docs/icon.png" width="160" alt="WindowWheel-Icon"></p>

<h1 align="center">WindowWheel</h1>

<p align="center"><b>Fenster-Layouts per Radmenü für macOS – wie das Waffenrad in GTA.</b></p>

> **Hinweis:** Dieses Programm ist in enger Zusammenarbeit mit LLMs (KI-Sprachmodellen) entstanden.
> Ohne diese Zusammenarbeit wäre es in dieser Form nicht möglich gewesen.

## Warum ich das gebaut habe

Auf meinem großen Bildschirm habe ich oft drei oder vier Fenster nebeneinander offen – fast immer
in ähnlicher Anordnung und Größe. Mission Control ist super, um Fenster zu finden, hilft aber nicht
dabei, sie anzuordnen. Jedes Mal alle Fenster von Hand so hinzuziehen, dass es sauber und
symmetrisch aussieht, dauert lange und nervt.

Also wollte ich etwas wie das Waffenrad aus GTA: Tastenkombination drücken, die gewünschte
Anordnung im Rad auswählen und dann einfach anklicken, welches Fenster wohin kommt. Fertig.

## Was es kann

- **Radmenü per ⌥⇥** – Layout auswählen wie im Spiel: halten, mit der Maus zielen, loslassen.
- **Fenster per Klick zuordnen** – eine Mission-Control-artige Ansicht zeigt alle Fenster als
  **Live-Vorschau** (Videos laufen weiter); ein Klick setzt das Fenster in den nächsten Platz.
- **Pixelgenau und symmetrisch** – Außenränder und Zwischenräume sind immer gleich groß.
  Den Abstand stellst du per Mausziehen ein; er wird pro Layout gemerkt.
- **Einrasten beim Ziehen** – ein Fenster ziehen und dabei ⌥⇥ drücken: Die Plätze des zuletzt
  gewählten Layouts erscheinen, loslassen lässt das Fenster einrasten.
- **Aufgeräumter Schreibtisch** – nicht gewählte Fenster verschwinden hinter den gewählten,
  bleiben aber offen (auch in Mission Control und im App-Umschalter).
- **Mehrere Bildschirme** – es zählt immer der Bildschirm, auf dem die Maus steht.
- **Eigene Layouts** – Fenster einmal von Hand anordnen und als Layout speichern.
- Flüssige Animationen und Liquid-Glass-Optik (macOS 26+).

## Installation

Voraussetzung ist [Homebrew](https://brew.sh). Dann im Terminal:

```zsh
brew install limburgmoritz-gh/tap/windowwheel && brew services start windowwheel
```

Damit ist WindowWheel installiert, läuft sofort und startet ab jetzt automatisch beim Anmelden.
Oben in der Menüleiste erscheint ein ◎-Symbol.

Außerdem legt WindowWheel beim ersten Start das Programm **WindowWheel** in deinem
Programme-Ordner (`~/Programme`) an. Du findest es damit wie jede andere App über
**Spotlight (⌘ Leertaste → „WindowWheel“)**, im Launchpad oder im Finder und kannst es dort
starten, falls du es einmal beendet hast.

### Berechtigungen (einmalig)

macOS fragt beim ersten Start nach zwei Berechtigungen. Beide findest du unter
**Systemeinstellungen › Datenschutz & Sicherheit**; der Eintrag heißt dort **„Python“**:

1. **Bedienungshilfen** – für die Tastenkombination und zum Verschieben der Fenster.
   WindowWheel wartet, bis die Freigabe da ist, und ist dann sofort einsatzbereit.
2. **Bildschirm- & Systemaudioaufnahme** – für die Vorschaubilder der Fenster. Wird erst beim
   ersten Öffnen der Fensteransicht abgefragt. Danach einmal neu starten:
   `brew services restart windowwheel`

WindowWheel nimmt nichts auf und sendet nichts irgendwohin – die Aufnahme-Berechtigung dient nur
den Vorschaubildern auf deinem eigenen Bildschirm.

## Bedienung

**Rad** – `⌥ Option` gedrückt halten und `⇥ Tab` drücken:

| Aktion | Wirkung |
|---|---|
| Maus in eine Richtung bewegen, dann ⌥ loslassen | Layout wählen (GTA-Stil) |
| ⇥ erneut drücken (⌥ halten) | nächstes Layout, Loslassen wählt es |
| Klick / `1`–`9` / ⏎ | Layout wählen |
| `esc`, Rechtsklick, Klick weit außerhalb | abbrechen |

Tippst du ⌥⇥ nur kurz an, ohne zu zielen, bleibt das Rad offen und du kannst in Ruhe klicken.

**Fenster zuordnen** – nach der Layout-Wahl gleiten alle Fenster des Bildschirms als
Live-Vorschau ins Raster, oben zeigt eine Karte das Layout mit dem aktiven Platz:

| Aktion | Wirkung |
|---|---|
| Klick auf ein Vorschaubild | Fenster kommt in den aktiven Platz |
| Klick auf einen Platz in der Karte | diesen Platz (neu) belegen |
| Ziehen auf freier Fläche → / ← | horizontalen Abstand größer / kleiner |
| Ziehen auf freier Fläche ↑ / ↓ | vertikalen Abstand größer / kleiner |
| Doppelklick auf freie Fläche | Abstand zurücksetzen |
| `␣` / `⇥` | Platz überspringen |
| `⌫` / Rechtsklick | letzten Schritt rückgängig machen |
| `1`–`9` | bestimmten Platz (neu) belegen |
| ⏎ | fertig, auch wenn noch Plätze frei sind |
| `esc` | abbrechen – alle Fenster gehen an ihren alten Platz zurück |

**Einrasten ohne Rad** – ein Fenster ganz normal ziehen und dabei `⌥ ⇥` drücken: Die Plätze des
Layouts, das du zuletzt im Rad für diesen Bildschirm gewählt hast, erscheinen. Das Feld unter dem
Cursor leuchtet auf, Loslassen lässt das Fenster einrasten. `⌥ ⇥` nochmal oder `esc` blendet die
Felder aus.

## Eigene Layouts und Einstellungen

- **Am einfachsten:** Fenster einmal von Hand anordnen und im ◎-Menü
  *„Aktuelle Anordnung als Layout speichern …“* wählen. Die Kanten rasten dabei auf glatte
  Anteile ein (1/2, 1/3, 1/4, …), damit alles symmetrisch wird.
- **Von Hand:** ◎-Menü › *„Layouts bearbeiten“* öffnet die Datei
  `~/Library/Application Support/WindowWheel/config.json`. Jeder Platz ist
  `[x, y, breite, höhe]` als Anteil der nutzbaren Bildschirmfläche (0 bis 1, `y` von oben);
  die Reihenfolge ist die Reihenfolge beim Zuordnen.

Weitere Einstellungen in derselben Datei:

| Einstellung | Bedeutung |
|---|---|
| `hotkey` | Tastenkombination, z. B. `"alt+tab"` oder `"ctrl+alt+space"` |
| `gap` | Standard-Abstand in Pixeln |
| `center_cursor` | Maus beim Öffnen in die Radmitte setzen |
| `hide_others` | nicht gewählte Fenster hinter die gewählten schieben |

## Update und Deinstallation

```zsh
brew upgrade windowwheel && brew services restart windowwheel   # Update
brew services stop windowwheel && brew uninstall windowwheel    # Deinstallieren
rm -rf ~/Applications/WindowWheel.app                           # Programm-Eintrag entfernen
```

Deine Layouts bleiben in `~/Library/Application Support/WindowWheel` erhalten; den Ordner kannst
du bei Bedarf löschen.

## Gut zu wissen

- **Nach Python-Updates durch Homebrew** (`brew upgrade`) kann macOS die Berechtigungen für
  „Python“ wieder entziehen, weil es eine neue Programmdatei ist. Dann den Eintrag „Python“ unter
  Bedienungshilfen bzw. Bildschirmaufnahme mit „–“ entfernen, neu erlauben und
  `brew services restart windowwheel` ausführen.

- Getestet auf macOS 27 mit Apple Silicon. Ab macOS 14 sollte es laufen (statt Liquid Glass gibt es
  dort klassisches Milchglas), das ist aber nicht getestet.
- Fenster auf anderen Schreibtischen (Spaces) und im Vollbildmodus kann macOS nicht verschieben –
  sie tauchen in der Ansicht nicht auf.
- Apps mit festem Größenraster (z. B. Terminal: ganze Zeilen/Spalten) können einen Platz nicht
  pixelgenau füllen; sie werden so groß wie möglich und mittig eingesetzt.
- Fenster, die auf dem Schreibtisch komplett hinter anderen liegen, pausieren in manchen Apps
  (z. B. Browsern) ihr Bild – deren Vorschau steht dann still.

## Aus dem Quellcode starten

```zsh
git clone https://github.com/limburgmoritz-gh/windowwheel.git && cd windowwheel
python3 -m venv .venv && .venv/bin/pip install -e .
./run.sh
```

## Lizenz

[MIT](LICENSE)
