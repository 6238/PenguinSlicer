# Result: wizard mockup version 5

**Status: DONE.** Fri 2026-11-20 22:15 Pacific. Brief: [brief.md](brief.md).

## What was done

1. **Lay on face as Orca Slicer does it.** A fifth option, *Faces on the hull (like Orca)*,
   in the scenario strip's **Lay on face** menu, and the default. New file
   `docs/mockups/print-wizard/js/hullfaces.js` (convex hull, flat faces, Orca's filters,
   the round-part rule, rounded patches), written from
   [the algorithm note](../../research/2026-11-21-lay-on-face-hull-faces.md); drawing,
   hover and click in `js/layout3d.js`. The other four options still switch.
2. **Parts first, then Setup.** Step order Parts, Setup, Layout, Preview, Send in the step
   tabs, Back and Next, the step the wizard opens on (Reset, two hours away, no work to
   resume), the chips row, the Layout step's instruction and its "more ways" list, and
   every sentence in [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) that named a
   step.
3. **The Preview step's breakdown by line type is gone** (the coordinator's third change).
   The list beside the layer preview was both the colour legend and the breakdown, so it
   stays as a plain legend: each line type's colour and name, no time, no share, and the
   "Heating, travel, layer changes" row removed. A click on a name still hides that line
   type, as before. Its unused styles were removed.
4. DECISIONS.md: "What changed in version 5" at the top, M1 lists the five options, the
   terms **convex hull** and **hull patches**, decision 49 with the choices below, fake 19,
   and the step names and numbers corrected. No new questions.

## How Orca finds and filters faces (short)

Convex hull of the object; hull triangles that meet along an edge and match the starting
triangle's normal within 0.001 per component form one face; faces under 5 mm², lone
triangles with a side under 1 mm and outlines with a corner under 1 degree are dropped;
the 254 largest are kept; no stability test. Patches: outline drawn in 10%, corners
rounded in ten passes, raised 0.1 mm, near-white at 50% (75% hovered), drawn over the
object. The research's 5 mm² and 254 are right; the file's shortcut key is Ctrl+F, not F.

## Round parts

Orca's filters alone offer 96 rim slivers on the HTD Pulley 24T and on the Hex Bore Spacer
1in, and 40 on the Shooter Hood Rib's curved edge. The mockup's rule: **a face is left out
when a neighbouring hull face bends away from it by less than 20 degrees and is at least
half its size.** Result: pulley and spacer 2 faces (their ends), rib 5 (sides, ends, the
face across the inner curve), the other four parts unchanged (7, 7, 7, 8). A share-of-area
rule and a minimum-width rule were checked against the measured faces and fail (rib ends
are 1.1% of its sides; the rib's curved facets are as wide as its ends).

## Time to find the faces, per part (ms, in the browser)

| Part | Load 1 | Load 2, reverse order |
|---|---|---|
| L Bracket | 2.2 | 0.4 |
| HTD Pulley 24T | 9.5 | 5.3 |
| Camera Mount | 1.1 | 0.8 |
| Hex Bore Spacer 1in | 1.9 | 2.0 |
| Gusset Plate | 2.8 | 3.2 |
| Shooter Hood Rib | 1.5 | 3.1 |
| 1/2in Hex Shaft | 0.2 | 1.0 |

Chrome under a virtual display with software WebGL on an aarch64 Linux machine; first
request for each part after a page load.

## Choices the brief left open

- **Opening lay on face = selecting one instance** (no button, no mode), as the arrows and
  the box do; decision 27 keeps the Layout step free of modes. Several selected: no patches.
- **Colours:** PenguinCAM's accent blue at 22% opacity, 55% hovered (Orca's near-white is
  invisible on the light theme's pale parts).
- **A patch behind the part is hidden and not clickable**; Orca draws all patches over it.
- **The face the instance lies on has no patch**; a drag that starts on a patch moves the
  instance.
- **No stability test**, as in Orca; the note and decision 49 name a face the L Bracket
  would fall off (by hand arithmetic) and say the real wizard should test it.
- **"(recommended)" removed from *Pictures under the view*** since it is no longer the default.
- **Chips:** parts and instances from the Setup step on, then filament, profile and changes
  from the Layout step on (each chip is what an earlier step decided).
- **The Layout step's instruction** says "go to the Parts step (tab 1)" instead of "go Back
  to Parts", since Back from Layout now goes to Setup. The remedy buttons labelled "Back to
  Parts" go straight to Parts and were kept.
- Version 4's "What changed" list is kept as history, with "(version 5 puts Parts first,
  then Setup)" added to its step list.

## Checks

Served `docs/mockups/print-wizard/` on port 8817 (Python's static server), headed Chrome
under its own Xvfb display with SwiftShader; both stopped, `.playwright-cli/` removed.

- **Every part, both widths (800 and 320 px):** selected each of the seven parts alone on
  the plate, hovered the largest clickable patch (tooltip "Lay it on this face: N mm
  tall"), clicked it: all 14 laid the instance down, with the step's usual sentence, and
  the patches redrawn. One exception, then resolved: the spacer at 800 px, whose patch
  middle sat under the rotation handle (the handle wins, as before); a click elsewhere on
  the patch laid it down.
- **Step order:** opens on Parts with Back off and no chips; Setup shows the parts chip;
  Layout adds filament and profile; Preview adds plate area; Send adds time and grams;
  Back from Setup to Parts and from Layout to Setup; Refresh page with an unsent slice
  reopens on Preview; Come back 2 h later opens on Parts with the expiry notification;
  the printer-status icon shows another student's print on the Parts step.
- **Legend:** six names (outer wall to bottom surface), no times or shares, at 320 and 800 px.
- **Lay on face menu:** all five options switch on a selected instance (pictures, box, tip
  handle and patches appear; arrows show none on the spacer, whose two ends are one
  resting position, as in version 4).
- **Console:** no errors or warnings after the walks.

## Screenshots

In [screenshots/](screenshots/): `01-parts-first-320.png`, `02-setup-second-320.png`;
`hull-<part>-<width>-a-selected.png`, `-b-hover.png`, `-c-laid.png` for each of the seven
parts at 800 and 320 px; `preview-legend-320.png`, `preview-legend-800.png`;
`send-chips-800.png`; `come-back-later-opens-parts-800.png`;
`printer-icon-on-parts-800.png`.

## Concerns

- The round-part rule is per neighbour; irregular exported meshes need it applied to whole
  runs of shallow-bend facets (the note says how).
- The hull is a plain incremental one; parts with tens of thousands of corners would need a
  faster one or a Web Worker.
- Untracked `docs/reference/orca-lay-on-face/` (the owner's screenshot) is not mine and was
  left as found.
