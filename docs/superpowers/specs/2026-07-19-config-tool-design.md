# G13 Configurator — Design

**Date:** 2026-07-19
**Status:** Approved by user (pending spec review)
**Mockup:** https://claude.ai/code/artifact/8fec8306-ff29-4fa7-ab8b-976b03c85b08

## Purpose

A standalone GUI so the user can reprogram the G13 without hand-editing
properties files or AI assistance. Must be easy to use as a human, support
modifier combos (Ctrl+C, Super+X, Ctrl+Shift+T), present a clickable device
overlay like Logitech's original software, and support template profiles and
cloning.

## Decisions (user-approved)

- **Form factor:** native Qt desktop app.
- **Stack:** PySide6 (Python + Qt6 Widgets), installed from Fedora repos
  (`python3-pyside6`). Repo stays two-language: C++ driver, Python tooling.
- **Combos:** small driver patch adding combo passthrough (`p,k.29+46`),
  not auto-generated macros.
- **v1 scope:** key bindings with combos, profile templates/cloning, profile
  name + LCD color, stick settings, macro editor. (Assigning real L3/L4
  content is deferred — "we'll come back for the rest of the hotkeys".)

## Architecture

New `configurator/` directory in the repo; entry point installed as
`g13-config` to `~/.local/bin` by the existing `install.sh`, plus a
`.desktop` file for the KDE launcher.

**The files are the single source of truth.** The tool reads and writes
`~/.config/g13/bindings-N.properties` and `macro-N.properties` in the exact
format the driver parses. No database, no sidecar state, no IPC with the
driver — the file boundary is the interface. The tool works whether or not
the driver is running; the driver's existing live-reload applies changes.

**Apply model:** edits accumulate in an in-memory profile model with a dirty
indicator. **Apply** writes the files; **Revert** re-reads from disk.

**Templates:** `~/.config/g13/templates/*.properties` — same format plus a
`template_name=` line. Actions: Save as template, New from template, Clone
to slot (with overwrite confirmation, since slots are live config). Repo
ships starter templates: blank, WASD gaming, Fusion 360.

**Data flow:** overlay click → binding editor dialog → in-memory profile
model → Apply → properties files → driver live-reload.

## UI

**Main window:** profile tabs M1–M4 (name + LCD-color chip) above a
custom-painted device overlay mirroring the physical G13: rows G1–G7,
G8–G14, G15–G19, G20–G22; thumb cluster (two thumb keys, stick, stick
click); LCD + M-row drawn for orientation. Each keycap shows its current
assignment abbreviated (`Ctrl+C`, `W`, `M: Undo`, `Pan ←`); hover shows the
full assignment; the profile's LCD color tints bound keycaps. The 0-based
`G0–G39` property mapping is internal only — the UI shows physical names
(G1–G22, thumb, stick) exclusively.

**Binding editor** (opens on key click), one of four action types:

- **Key or combo** — capture field: focus, press the real chord, captured
  with Linux input keycodes (Qt provides scancodes; map to evdev codes).
  Searchable dropdown fallback for keys that can't be pressed (media keys).
- **Macro** — pick from the profile's macros, set repeat count, or open the
  macro editor.
- **Mouse pan** — dx/dy step and optional hold-buttons (the `mp` type).
- **Unbound** — clear the key.

**Per-profile settings panel:** name, LCD color picker, stick mode
(mouse/keys; in keys mode the four direction bindings are editable), stick
speed, orbit hold-combo.

**Macro editor:** list of the profile's macros; each is a sequence of steps
(key down / key up / delay ms) editable inline, plus **Record mode** —
capture keys naturally with timing, then trim.

## Driver patch: combo passthrough

Extend the `p` binding parser (`G13.cpp parse_bindings_from_stream`) to
accept `p,k.29+42+20` via the existing `parse_plus_list`. New
`ComboPassThroughAction`: on G-key press, key-down each code in listed order
(modifiers written first); on release, key-up in reverse order. Hold
semantics — key repeat behaves like holding the real chord. The combo path
triggers only when `+` is present; single-key `p,k.20` and all existing
profiles parse unchanged.

## Error handling

- **Lenient parse, loud warning:** malformed lines are skipped like the
  driver does, but a warning banner names the file and line. Unknown keys
  are preserved on rewrite, never dropped.
- **Atomic writes:** temp file in the same directory + rename, so
  live-reload never sees a half-written config.
- **Fresh machine:** if `~/.config/g13/` is missing, offer to create it
  from the starter templates.
- **External edits:** a file watcher flags "changed on disk" with a reload
  offer — no silent clobbering in either direction.

## Testing

- **Round-trip unit tests (pytest, no Qt):** parse → model → serialize
  reproduces every binding type (`p`, combo `p`, `m`, `mp`, stick settings,
  name, color).
- **Golden test:** the four real config files re-serialize semantically
  identical.
- **Driver patch:** hardware verification — bind Ctrl+C to a spare key,
  confirm hold-repeat in a text editor (same verify-on-device pattern as
  orbit/pan).
- **GUI:** manual verification of capture field and overlay; no automated
  Qt UI tests (poor value here).

## Out of scope (v1)

- Assigning real L3/L4 profile content (follow-up session).
- Bottom LCD line (separate open item).
- Editing the number of profile slots (driver is fixed at 4).
- Upstream PR of driver patches (separate open item).
