# The owner's feedback on mockup version 7

Given Thu 2026-11-26, Pacific time, on [mockup version 7](../mockups/print-wizard/index.html)
(PR 15). The owner expects this to be the last round on the mockup before implementation
starts. Every point is a requirement; it is folded into
[DECISIONS.md](../mockups/print-wizard/DECISIONS.md) and this note is deleted when built.

## The step circles

- The tooltips on the step circles (the numbered circles at the top) appear faster, look
  like the rest of the PenguinSlicer interface rather than the browser's default tooltip,
  and have larger text.

## Advanced mode

- Every section of advanced mode is open by default when it is shown.
- Advanced mode remembers, for each section and each setting, whether it is open or
  closed. The memory lasts while the page is open; it need not survive a reload.

## The printer-status icon

- The printer details open when the pointer rests on the printer-status icon, and still
  open on a click.

## Layout

- Arrange never turns an instance back to its original orientation: every instance keeps
  the orientation it was given (by lay on face, by the rotation handle, or by the wizard).

## Preview

- The preview is hard to read with two colours. Four fixed colours, one for each group:
  walls; infill; top and bottom surfaces; supports and brim.
- The colours do not follow the filament's colour, and do not copy Orca's: the user will
  not know Orca's. Choose four colours that colour theory and interface practice say
  work well: distinct from one another (including for the common kinds of colour
  blindness), clear on the light view's background, and calm next to the rest of the
  wizard.
- A colour key, closed by default, behind a small icon on the preview.
- Make test renders of the preview with different numbers of layers shown, look at them,
  and tune the appearance (colours, line weight, lighting, the part ghost, anything else)
  so the preview reads well at every layer count.
