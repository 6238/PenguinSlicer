# The owner's feedback on mockup version 6

Given a step at a time from Wed 2026-11-25 00:20 PT. Recorded here until it is built into
mockup version 7 and folded into [DECISIONS.md](../mockups/print-wizard/DECISIONS.md);
then this file is deleted.

## Layout step

- **The rotation handle is bound to the instance.** Dragging it is broken today. The
  handle should behave as if fixed to the instance: it sits on a circle round the
  selection, at a radius set when the drag starts (not recomputed from the turning
  bounding box), and turns with the instance through the same angle, snaps included, so
  the instance and the handle never part. It does not jump to another side while
  dragged; it moves clear of hull patches only when the drag ends or patches appear.

- **Round parts can be laid on edge.** The round-part rule leaves a pulley only its two
  end faces, so it cannot be stood on its rim. When the hull's kept faces leave a
  direction with no flat face (a pulley's rim, or any part with no flat side that way),
  draw patches on the bounding box's sides for that direction, styled like the hull
  patches but lying on the box. A click lays the instance on that side: it rests on its
  rim. Parts whose hull faces already cover every direction get no box patches.
- **Turning is free; Shift snaps to 45°.** Dragging the rotation handle turns the
  instance freely, with no snap, and a small readout beside the handle shows the angle
  while dragging ("↻ 37°"). Holding Shift, the most common modifier for constraining
  angles in CAD and drawing programs, snaps to multiples of 45°. Version 6's narrow
  5-degree catch round each 45° goes, and no text claims it "snaps every 45 degrees".
- **Drop "To print more or fewer of a part, go to the Parts step (tab 1) and change its
  quantity."**
- **No text about orientation.** Remove the line under the orientation controls ("As
  modelled, which is already its best way.") and the notices after an orientation
  change ("Elevator Block Top #1 already lies that way.", "… now lies … tall."). The
  view shows the result; the text only makes the screen busier.

- **Printer and plate figures are always in millimetres.** The plate line reads "Shop
  H2S: plate 340 × 320 mm, up to … mm tall, 12 mm apart" whatever the parts' units, and
  so do the spacing in errors and the layer height readout on Preview. Only a part's
  own size follows its units. This replaces the rule of Tue 2026-11-24 that spacing and
  heights are in inches on an all-inch plate, and settles M27 and M28.

## Send step and the printer's "finished"

The printer reports that a print ended; it cannot tell whether a person has cleared the
plate. So once a print ends the printer is free (ruling R8), and the plate being clear
is the person's check (the Send step's reminder).

- **The printer-status icon says "Free" as soon as the print ends**, never "Finished".
  Its details add "Last print finished 11:25 am (Alex Chen)".
- **The user's own last print is a one-line note, not a card:** "Your print finished at
  11:25 am." On the Send step of a new plate, the old print's progress card goes and
  the note sits above the new plate's Send. When the user comes back to the wizard, the
  note shows on whichever step opens.
- **How long:** the note and the details' line go when the user sends another plate, or
  12 hours after the print finished, whichever comes first. (Printer delivery still
  keeps its final report 24 hours, R11.) This answers M19.
- The time-and-filament chip ("2 h 1 min · 119 g") goes with the other chips: the Send
  step already states the print time and filament.

## The top of the panel at 320 px

The step pills wrap to two rows and, with the chips, push the content the user works
with far down the panel. This settles M20.

- **Steps below 480 px: numbered circles**, as in Material's compact stepper: five small
  circles joined by a line, a check in each done step, the current one filled with its
  name beside it. Every circle stays clickable and has a tooltip with its step's name.
  From 480 px the pills stay as they are.
- **The plate summary is two lines of text, not a row of chips:**
  - first line: parts and instances ("1 part · 1 instance");
  - second line: the settings, filament and profile ("PETG · Structural"), then the
    "+2 changes" pill, which stays a pill because it opens the list of changes. The
    filament and profile text is cut with an ellipsis when too long, never wrapped; the
    pill stays whole.
  - The plate-area chip ("2.362 × 1.181 in of plate") goes.
- **No "Mockup: …" notices in the panel** (for example "Mockup: each file you choose
  becomes one of the mock parts; the file itself is not read."). What the mockup fakes
  is said once, in `DECISIONS.md`'s "What is fake and could mislead", and where needed
  in the scenario strip, never in the panel.
- **Advanced mode's sections are cards.** The five sections (Quality, Strength, Speed,
  Support, Others) and the groups inside them looked alike (same weight, size and
  chevron). Each section becomes a bordered card like PenguinCAM's cards: its heading,
  with the chevron, changed count and the Expand all / Collapse all icon, is the card's
  title, and its groups are rows inside the card. A closed section is a slim card.
  Only below 480 px, where advanced mode is an accordion. From 480 px the rail stays as
  it is, with no card: a card there would make the settings more cramped.
- **Advanced mode's header loses its "‹ Settings" button.** The button at the bottom
  that returns to the Settings step is the only way back; Escape no longer closes
  advanced mode. The header keeps "Advanced
  mode", the profile and changed count ("Structural, 2 changed") and "Reset all".
- **"Loaded from your saved configuration link." goes:** the configuration's name says
  enough. A link that fails still shows an error.
