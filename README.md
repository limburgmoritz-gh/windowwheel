<p align="center"><img src="docs/icon.png" width="160" alt="WindowWheel icon"></p>

<h1 align="center">WindowWheel</h1>

<p align="center"><b>Arrange your windows into predefined layouts in seconds – with a radial menu for macOS.</b></p>

> **Note:** WindowWheel was built in close collaboration with large language models (LLMs).
> Without that collaboration, this project would not have been possible in its current form.

## Why

macOS makes it easy to find windows, but not to arrange them. If you regularly work with the same
setup of several windows side by side, you end up dragging and resizing them by hand every time –
and they rarely line up cleanly.

WindowWheel turns this into a two-step action: pick a layout from a radial menu, then click the
windows that belong in each slot. Typical situations where this helps:

- **Development:** editor, terminal and browser preview side by side.
- **Research and writing:** source material on one side, your document on the other.
- **Meetings and calls:** video call, notes and shared document in a fixed arrangement.
- **Monitoring:** several dashboards, logs or streams visible at the same time.
- **Switching contexts:** quickly rebuilding the same arrangement after moving between
  a laptop screen and an external display.

## Features

- **Radial layout menu** – press `⌥ Tab`, point at a layout, release.
- **Click-to-assign** – an overview shows all windows of the current screen as live previews;
  one click places a window in the next slot.
- **Precise, symmetric spacing** – outer margins and gaps are always equal. Adjust them by dragging;
  the spacing is saved per layout and scales with the screen size.
- **Snap while dragging** – press `⌥ Tab` while dragging a window to show the slots of the last
  used layout, then drop the window into one.
- **Tidy desktop** – windows you didn't pick are moved behind the arranged ones, not closed
  or minimized, so they remain available in Mission Control and the app switcher.
- **Multiple displays** – always works on the screen under the cursor.
- **Custom layouts** – arrange windows by hand once and save the arrangement as a layout.

## Installation

Requires [Homebrew](https://brew.sh) and macOS 14 or later.

```zsh
brew install limburgmoritz-gh/tap/windowwheel && brew services start windowwheel
```

WindowWheel starts immediately and launches automatically at login. It lives in the menu bar (◎)
and also adds **WindowWheel** to `~/Applications`, so you can find and start it via Spotlight
(`⌘ Space`), Launchpad or Finder.

### Permissions

On first launch macOS asks for two permissions under
**System Settings › Privacy & Security**. The entry is listed as **“Python”**:

1. **Accessibility** – required for the keyboard shortcut and for moving windows.
2. **Screen & System Audio Recording** – required for the window previews. After granting it,
   restart once: `brew services restart windowwheel`

WindowWheel does not record or transmit anything; screen access is used only to display the
previews locally.

## Usage

**Layout menu** – hold `⌥ Option` and press `Tab`:

| Action | Result |
|---|---|
| Move the mouse towards a layout, release `⌥` | Select layout |
| Press `Tab` again while holding `⌥` | Next layout |
| Click, `1`–`9` or `Return` | Select layout |
| `Esc` or right-click | Cancel |

**Assigning windows** – after choosing a layout, all windows of the screen appear as live
previews, with a map of the layout at the top:

| Action | Result |
|---|---|
| Click a preview | Place the window in the active slot |
| Click a slot in the map | Select (or reassign) that slot |
| Drag on empty space → / ← | Increase / decrease horizontal spacing |
| Drag on empty space ↑ / ↓ | Increase / decrease vertical spacing |
| Double-click on empty space | Reset spacing |
| `Space` | Skip slot |
| `Delete` or right-click | Undo last step |
| `Return` | Finish |
| `Esc` | Cancel and restore all windows |

**Snap while dragging** – drag a window by its title bar and press `⌥ Tab`. Release over a slot
to snap the window into it; press `⌥ Tab` or `Esc` again to drop it normally.

## Configuration

Use **“Save current arrangement as layout…”** in the menu bar to turn your current window
arrangement into a layout. Edges snap to clean fractions (½, ⅓, ¼, …).

All settings live in `~/Library/Application Support/WindowWheel/config.json`
(menu bar › *Edit layouts*). Each slot is `[x, y, width, height]` as a fraction of the usable
screen area, with `y` measured from the top.

| Key | Description |
|---|---|
| `hotkey` | Keyboard shortcut, e.g. `"alt+tab"` or `"ctrl+alt+space"` |
| `gap` | Default spacing in pixels |
| `center_cursor` | Center the cursor when the menu opens |
| `hide_others` | Move windows that were not picked behind the arranged ones |

## Update and uninstall

```zsh
brew upgrade windowwheel && brew services restart windowwheel
```

```zsh
brew services stop windowwheel && brew uninstall windowwheel
rm -rf ~/Applications/WindowWheel.app ~/Library/Application\ Support/WindowWheel
```

## Known limitations

- The user interface is currently in German.
- After Homebrew updates Python, macOS may revoke the permissions for “Python”. Remove the entry
  in System Settings, grant it again and run `brew services restart windowwheel`.
- Windows on other Spaces or in full-screen mode cannot be arranged.
- Apps that resize in fixed steps (e.g. Terminal) are centered in their slot instead of
  filling it exactly.
- Some apps (e.g. browsers) pause rendering while their window is completely covered, so their
  preview may not update.
- Tested on macOS 27 (Apple Silicon). macOS 14–25 should work with a frosted-glass fallback
  instead of Liquid Glass, but is untested.

## Running from source

```zsh
git clone https://github.com/limburgmoritz-gh/windowwheel.git && cd windowwheel
python3 -m venv .venv && .venv/bin/pip install -e .
./run.sh
```

## License

[MIT](LICENSE)
