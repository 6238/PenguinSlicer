# PenguinCAM in Onshape: the visual reference for the wizard

Three screenshots of PenguinCAM, the Popcorn Penguins' CNC wizard, running in Onshape's
right panel, taken by the owner on Sat 2026-11-21. PenguinSlicer is a separate codebase,
but its wizard should look like PenguinCAM and reuse the choices PenguinCAM already made
in appearance and idioms. These screenshots are the reference for that.

| Screenshot | Step |
|---|---|
| [parts.png](parts.png) | Step 2, Parts: a selection prompt, the list of chosen parts |
| [layout.png](layout.png) | Step 3, Layout: the machine card, the 2D layout of the stock |
| [preview.png](preview.png) | Step 4, Preview & Save: the 3D toolpath preview and its player |

## What to take from them

The owner's feedback of Sat 2026-11-21, given after trying mockup version 3:

- **The panel's width is not fixed.** A user widens Onshape's right panel simply by
  dragging its edge; in the screenshots it is far wider than 320 px. The wizard must work
  at 320 px and must support a wider panel well. It is not a 320 px design.
- **Light mode.** PenguinCAM is light, like Onshape around it. Mockup version 3 is dark,
  which sets it apart from everything beside it.
- **Size of text and controls.** The font sizes of the text and controls, relative to
  Onshape's own interface and the whole screen, should match PenguinCAM's. The owner sees
  substantially different font sizes in the mockup.
- **Font sizes, spacing and alignment** generally: the mockup should come much closer to
  PenguinCAM's.

PenguinCAM's idioms visible in the screenshots:

- A header: the application's name, then "Config: 6238 (Popcorn Penguins)" as a link.
- The four steps as pill-shaped tabs ("1. Setup ✓", "2. Parts ✓", "3. Layout",
  "4. Preview"): the current step filled blue, finished steps with a check mark.
- A row of chips summarising earlier choices (material, thickness, tool, part count).
- A bold title for the step, then one or two lines of plain instruction text.
- Light grey bordered cards for selections and parts, with a small outline picture, the
  part's name in bold and its size below, and a red × to remove it.
- Back and Next as two wide buttons pinned to the bottom of the panel: Back light grey,
  Next solid blue. On the last step the blue button is the action ("Send to Google Drive")
  with a menu arrow.
- The preview: a light 3D view, then "Move 1 of 1967" with the current G-code line, a
  scrubber, play and restart buttons, a speed menu and "Reset view".

The mockup is not to be changed until the owner's review of it is finished.
