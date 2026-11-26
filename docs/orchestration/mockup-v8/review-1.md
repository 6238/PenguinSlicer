# Review 1 of wizard mockup version 8

Reviewed: the mockup in `docs/mockups/print-wizard/` (its record of decisions is
[DECISIONS.md](../../mockups/print-wizard/DECISIONS.md); "decision 33" below is a
numbered decision of that file) as built in commit `c464a61` on branch `mockup/v8` (the
branch stood at `55e84f6`), against
[the review brief](review-brief.md), the owner's feedback on version 7 (the handoff note
of Thu 2026-11-26, read from `git show c464a61~1`) and [the builder's brief](brief.md).
Walked on Thu 2026-11-26, 10:10 to 11:15 PST, by a reviewer who did not build it.
Nothing in the mockup was changed. Every server and browser started for the walk is
stopped, and no `.playwright-cli/` folder is left in the repository or in the scratch
folder.

**10 findings: 1 serious, 4 medium, 5 low** (two of the low ones are taste or need the
owner's word). Every point of the owner's feedback is built: the step circles' tooltip,
advanced mode's open state, the printer details on hover and Arrange's keeping of every
orientation all do what the feedback asks at 320, 480 and 800 px. The serious finding is
what "Arrange never turns" left behind: an instance too long for the plate as it is
turned now has no way back onto the plate that the panel names, and a scenario on the
strip that ended well in version 7 ends in a dead end. The medium findings are about how
the layer preview draws (its cost, its wall shading, its line width) and how far the new
tooltip was spread. No text a user sees says "student", "mentor" or "team". Nothing
overflows the panel or scrolls sideways at 320, 480 or 800 px in any state walked (about
320 layout audits). No JavaScript error in any walk; the only console messages
were the WebGL warnings of finding M1.

Severity as used here: **serious** is a point of the owner's feedback that is not met, or
a rule of the owner's that the mockup breaks; **medium** is a false or confusing statement
a user would notice, a usability fault, or something the implementation would copy to its
cost; **low** is polish. A finding that is a matter of taste, or that needs the owner's
word, says so.

One limit of this review, said first because it shapes what was seen: this container's
Chrome draws WebGL in software (SwiftShader), with no graphics card. Called **software
WebGL** below. On software WebGL version 8's layer preview is too slow to show a plate of
five instances reliably (finding M1), so its renders were judged on plates of one to
three instances. On the owner's Mac the same page may be smooth; that is the one thing in
this review only the owner's machine can settle.

## What was walked

A headed Chrome with software WebGL, driven by `playwright-cli`, the folder served on port
6311, at panel widths 320, 480 and 800 px:

- **Every step** on the plain path at each width, with a layout audit (nothing outside the
  panel, no sideways scroll) on every state.
- **The step circles' tooltip:** the delay timed on a circle at each width; every circle
  hovered and its tooltip's box measured against the panel; Tab onto the circles, Escape,
  Tab away; then every element that has the tooltip, on the five steps and in advanced
  mode, hovered at each width, its text read and its box measured; removing a part and
  closing a notification from the keyboard while its tooltip showed.
- **Advanced mode:** first opening; closing a section and two groups; closing and
  reopening advanced mode; going to the Layout and Parts steps and back; widening to 480
  px and narrowing again with advanced mode open, and to 800 px with it closed; Collapse
  all and Expand all in the accordion and in the rail; opening from a line of the changes
  box; changing the profile; switching Part Studio tabs; Refresh page.
- **The printer details:** a pass over the icon without resting; resting; moving slowly
  from the icon into the details; leaving; leaving and coming back inside the grace time;
  a click while open; a quick click; a second click; a click elsewhere; Escape; Tab and
  Enter; all 8 printer states, at each width. Touch was read in the code only: there is
  no touch screen here.
- **Arrange:** an instance turned with the real rotation handle, then Arrange; every one
  of 11 instances turned to its own odd angle, then Arrange with supports off (5 mm) and
  on (12 mm), the gaps between the outlines measured in the page; Arrange after lay on
  face; Arrange twice; Auto-orient after; the Shooter Hood Rib on arrival, squared by the
  user, then Arrange.
- **The layer preview:** two plates (a Gusset Plate with an L Bracket; a Camera Mount, a
  1/2in Hex Shaft and an HTD Pulley 24T), supports off and on, at layer 1, 4, 68, 131 and
  134 of 134, at 800 and at 320 px: 40 renders, each looked at (39 drawn; one came out
  blank at a lost WebGL context, M1), kept as four sheets
  ([800 px, gusset and bracket](screenshots/review-renders-800-gusset-and-bracket.png),
  [800 px, mount, shaft and pulley](screenshots/review-renders-800-mount-shaft-and-pulley.png),
  [320 px, gusset and bracket](screenshots/review-renders-320-gusset-and-bracket.png),
  [320 px, mount, shaft and pulley](screenshots/review-renders-320-mount-shaft-and-pulley.png));
  the colour key open and closed; close-ups of a
  finished top surface and of walls beside supports; the four colours' contrast and their
  differences for three kinds of colour blindness computed afresh (a script of this
  review, not the builder's). A plate of five or six instances was shown seven times;
  four of those lost the WebGL context (M1).
- **What version 7 fixed:** the rotation handle's place in the instance's own frame read
  before, during and after a turn; Shift turning; lay on face by a click on a hull patch;
  at 320 and 800 px.
- **Every state the scenario strip offers,** at each width: the four contexts and both
  settings of "Configuration: uploads in"; all 15 armed errors; all 8 printer states on
  the Send step; Refresh page, Close and reopen, Come back 2 h later and 12 hours later;
  the 5 ways to lay on a face, the 3 mouse schemes and both ways parts arrive; Speed at
  Real-time-ish for one slice and the two returns made during it; Fewer controls. Each
  state was audited for layout and its messages read from the page; the 320 px
  screenshots (92) were all looked at, the 480 and 800 px ones in a sample of about 20;
  the layout audit and the message texts cover the rest.

Every user-visible string that changed in version 8 was read in the diff of `c464a61` and
again on the page: the two Arrange messages, the four rows of the colour key and its
icon's name, the printer-status icon's description for a screen reader, and every
tooltip's text (unchanged words in a new box).

## The owner's feedback, point by point

| Point of the feedback | Met | Where checked, and what remains |
|---|---|---|
| Step circles' tooltips appear faster | Yes | Shown 155 to 163 ms after the pointer rests on a circle, at each width (the browser's waits about a second). At once on keyboard focus ([screenshot](screenshots/review-tooltip-step-circle-keyboard-320.png)); gone on Escape, on leaving and on Tab away. |
| ... look like the rest of PenguinSlicer | Yes | The panel's font, a white box with the printer details' border, radius and shadow. Never clipped: at 320 px the tooltip of circle 5 ends 6 px inside the panel's right edge, and no tooltip of any element left the panel at any width. Remains: M4 (the same tooltip now also sits on elements it does not suit), L1, L2, L4. |
| ... and have larger text | Yes | 14 px, the panel's body text size. |
| Every section of advanced mode open by default | Yes | First opening at 320 px: 5 sections and 30 groups open, 99 settings, a list 5,263 px tall in a 742 px window. At 480 and 800 px the rail shows one section, all its groups open. |
| Advanced mode remembers what is open, for each section and each setting, while the page is open | Yes, with "each setting" read as each group | The state survived closing and reopening advanced mode, the Layout and Parts steps, both crossings of 480 px, Collapse all and Expand all, a profile change and a Part Studio tab switch; Refresh page forgot it, as the feedback allows. A setting has nothing that opens, so the builder kept the state per group and said so in decision 13; that reading needs the owner's nod. Remains: L3. |
| Printer details open when the pointer rests on the icon, and still on a click | Yes | Open 154 to 163 ms after the pointer rests ([screenshot](screenshots/review-printer-details-on-hover-320.png)); a pass over the icon does not open them. Icon and details overlap by 1 px, and a slow move from one into the other never closed them. Closed 302 to 317 ms after the pointer left. A click pins them; Escape, a click elsewhere, × or a second click closes them. Tab and Enter open, Escape closes and focus stays on the icon. Inside the panel in all 8 printer states at each width. |
| Arrange never turns an instance | Yes | An instance turned to 32.4° with the rotation handle stayed at 32.4°. Eleven instances at eleven angles all kept their orientation ([arranged at 12 mm](screenshots/review-arrange-eleven-angles-12-mm-480.png)); smallest gap between outlines 5.56 mm with supports off and 12.88 mm with supports on, the median gap to the nearest neighbour 5.77 and 13.23 mm, so the spacing is measured on the turned outline and is neither broken nor loose. Kept after lay on face too. Remains: S1 (what the rule left behind for an instance too long for the plate). |
| Four fixed colours, one for each group | Yes | Walls `#2b5c9e`, infill `#e0912f`, top and bottom surfaces `#2f9e7a`, supports and brim `#9a8fb8`, read from the page; no filament has a colour any more. |
| Colours not the filament's, not Orca's; distinct, also for colour blindness; clear on the light background; calm | Mostly | This review's own computation gives the builder's figures for the four colours as chosen: the least CIEDE2000 difference between two of them is 16.8 (infill and surfaces, protanopia). Contrast on `#f2f4f7` is 6.1:1 for walls and 2.3:1 to 3.0:1 for the other three, which decision 33 says. Calm: yes, to this reviewer's eye (taste). Remains: M2 (the view does not draw the walls in the colour that was checked). |
| A colour key, closed by default, behind a small icon | Yes | A 26 px icon at the view's top left; closed on arrival; four rows; closes on a second click, a click elsewhere, Escape and on leaving the step. At 320 px the open key ends 10 px short of the layer bar's label. Remains: L1. |
| Test renders at different layer counts, looked at, appearance tuned | Yes | The builder's before and after images are in `screenshots/before/` and `screenshots/after/`. This review's 40 renders read well at layer 1, 4, 68, 131 and 134: the first layer, the solid layers above it, the current layer and the ghost above it are each plain to see at 800 and at 320 px. Remains: M1 (cost), M3 (line width). |

## Findings

Each finding says where it is, what is wrong, why it matters and the smallest fix.
Screenshots are in `screenshots/`, named `review-…`.

### Serious

#### S1. Since Arrange no longer turns, an instance too long for the plate as it is turned is stuck beside the plate, and every message sends the user to Arrange (a regression)

- **Where:** Layout step, 320, 480 and 800 px. Three ways in, each tried:
  1. The scenario strip's own error: arm "3c. Instance too tall", go to the Layout step,
     press the error's **Auto-orient** button, then **Arrange**.
  2. The scenario strip's "Parts arrive: as modelled" with a Shooter Hood Rib on the
     plate: the same two buttons.
  3. Plain use: select the Shooter Hood Rib, hold Shift and turn it square to the plate
     with the rotation handle (the use decision 62 names: "an instance turned at an odd
     angle can be squared again"), then press the error's **Arrange** button.
- **What is wrong:** the Shooter Hood Rib is 353 mm long and the plate takes 334 mm, so
  it fits only turned. In way 1, Auto-orient lays the rib flat; no spot is free for it
  among the two small parts in the middle of the plate, so it waits beside the plate,
  put back square (plate angle 0°, footprint 353 × 82 mm), under two messages:
  "Shooter Hood Rib #1 no longer fits on the plate and waits beside it. No spot on the
  plate is free for it lying this way. The other instances stay where you put them; press
  Arrange to make room." and "Shooter Hood Rib #1 is off the plate. Drag it onto the
  plate, or press Arrange."
  ([after Auto-orient](screenshots/review-s1-too-tall-after-auto-orient-320.png)).
  Arrange then answers: "Arrange placed 2 of 3 instances; 1 instance does not fit and
  waits beside the plate. Lower the quantities and print the rest on a second plate, or
  turn or lay instances another way to make room.", with one button, Back to Parts, and
  Next off ([after Arrange](screenshots/review-s1-too-tall-after-arrange-320.png)).
  Arrange again, and Auto-orient with or without a selection, change nothing. Way 3 ends
  in the same message after "Shooter Hood Rib #1 is not fully on the plate: it crosses
  the front and back edges. Drag it inward, or press Arrange."
  ([squared with Shift](screenshots/review-s1-rib-squared-480.png),
  [after its Arrange button](screenshots/review-s1-rib-squared-after-arrange-480.png)).
  The same clicks in version 7, run beside version 8 in this review: after Arrange the
  rib stands at 49.1° on the plate, "All 3 instances fit the plate. Arranged 3 instances,
  turning 2."
- **Why it matters:** version 7's Arrange was what turned such an instance back onto the
  plate. Version 8 took the turn out of Arrange, as the feedback asks, but left three
  sentences, two of them with an Arrange button, that still name Arrange as the remedy
  where it can no longer be one, and
  Arrange's own answer is false here in its first half (the rib fits no second plate as
  it is turned; quantity and room are not the matter) and too vague to act on in its
  second (it names neither the instance nor its length nor which way to turn it). The
  only way out is to work out unaided that the rib must be turned about 45° by hand where
  it sits beside the plate. The owner's bar for errors is text specific to the error
  that helps fix it. This is serious, not medium, because a scenario on the strip that
  ended well in version 7 now ends in a dead end, and because decision 64 records the
  case ("An instance that fits only turned and was not turned waits beside the plate
  after Arrange") without a remedy, which is what the implementation would build.
- **Smallest fix:** two changes, both inside what decision 64 already allows (the wizard
  may turn an instance when it gives it an orientation; Arrange itself never turns).
  1. Where the wizard parks an instance after a lay-down (`settle` in `js/wizard.js`),
     leave it turned as `fitTurn` would turn it, not put back square. "Press Arrange to
     make room" is then true again.
  2. When an instance beside the plate is longer or wider than the plate takes as it is
     turned (the test `fitTurn` already makes), the message names it with both figures,
     "Shooter Hood Rib #1 is 353 mm long as it is turned; the plate takes 334 mm.", and
     offers one button, **Turn it to fit**, which turns it as `fitTurn` does and arranges
     again. The "not fully on the plate" error offers the same button for such an
     instance in place of Arrange. The user presses a button that says turn.

### Medium

#### M1. The layer preview costs about 40 times what version 7's did to draw; on software WebGL a five-instance plate lost the WebGL context four times in seven

- **Where:** Preview step, every width, any sliced plate; `js/preview3d.js`, the instanced
  quads of `lineMesh` and `LINE_VS`.
- **What is wrong:** version 8 draws every toolpath segment as a quad with a width, where
  version 7 drew a one-pixel line. Measured on the same plates, the same machine and the
  same software WebGL, by timing a one-pixel `readPixels` after a layer change:

  | Plate | Segments | Version 7, one frame | Version 8, one frame |
  |---|---|---|---|
  | 1 Gusset Plate, 22 layers, panel 800 px | 152,101 | 0.10 s | 4.2 s |
  | the same, panel 320 px | 152,101 | not measured | 4.1 s |
  | 2 L Brackets, pulley, gusset, spacer, 134 layers | 399,261 | 0.25 s | 18.7 to 21.5 s |

  The cost follows the number of segments, not the size of the view: about 27 µs a
  segment. Frames of about 20 s make Chrome restart its graphics process (it was found
  restarted after the two losses where that was looked at; most likely Chrome's watchdog
  on a graphics process that stops answering), and with it the WebGL context of all three
  3D views is lost. Of the seven times this walk showed a plate of five or six instances,
  four lost the context; a fifth loss came on a two-instance plate at 320 px while the
  layer was being changed. A first loss in a page mended itself in about 2 s. After a second loss in the
  same page (seen once) Chrome gave the context back to none of the views: the stand-in
  Onshape picture, the Layout view and the layer preview all stayed blank, through Reset
  and a new slice, until the page was reloaded
  ([the blank layer preview](screenshots/review-m1-layer-preview-blank-800.png)).
- **Why it matters:** the owner's Mac draws on a graphics card and may show none of this;
  it could not be measured here. But not every machine that will run PenguinSlicer has
  the Mac's graphics card (an old laptop or a remote desktop sits somewhere between the
  Mac and this container); the wizard allows 150 instances on a plate, many times the
  segments measured here; and decision 33's "How the view draws" records the wide lines
  as the design with no word on what they cost, so the implementation would copy the
  technique without a budget. About three quarters of what is drawn can never be
  seen: on the five-instance plate 287,646 inner-wall segments and 12,393 infill segments
  of 399,261 lie inside the parts, under the layers above them. The builder's renders of a
  six-instance plate did come out, on the same kind of software WebGL, and the builder's
  walk met no console warning; so the loss is at the edge, not certain, which is the worst
  kind to leave unrecorded.
- **Smallest fix:** first, the owner tries the five-instance plate on the Mac and turns
  the view: if it is smooth, the mockup can stay as it is and only
  [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) changes.
  Either way decision 33 says what was measured here, and names two requirements for the
  implementation: a frame budget for the layer preview on a machine without a graphics
  card, and a view that draws again after a lost WebGL context. If the Mac stutters too:
  below the current layer draw only what can be seen (outer walls, top and bottom
  surfaces, supports and brim) and keep inner walls and infill for the current layer and
  the few under it, which removes about three quarters of the quads.

#### M2. The walls are not drawn in the colour that was checked: a wall facing the light comes within 4.2 of the supports' colour under protanopia

- **Where:** Preview step, every width, any plate with supports on; `js/preview3d.js`,
  `shaded()`.
- **What is wrong:** the four colours were checked for colour blindness as flat colours,
  and decision 33 gives 16.8 as the least difference between any two. But the view shades
  each wall by the way it faces: from `#1c3d68` facing away from the light to `#668ab9`
  facing it. Computed the builder's way (CIEDE2000, Machado's simulation at full
  severity):

  | Wall shade | Colour | Least difference from another group, normal vision | Protanopia | Deuteranopia | Tritanopia |
  |---|---|---|---|---|---|
  | facing away | `#1c3d68` | 35.5 | 32.6 | 34.6 | 31.3 |
  | flat (the colour checked) | `#2b5c9e` | 27.7 | 21.3 | 25.9 | 20.3 |
  | half way to the light | `#4973ac` | 20.6 | 12.2 | 16.4 | 12.8 |
  | facing the light | `#668ab9` | 15.4 | 4.2 | 7.5 | 8.8 |

  The near colour is supports and brim (`#9a8fb8`) in every column but tritanopia, where
  it is top and bottom surfaces. A third of all wall directions are within 60° of the
  light and so at or beyond "half way". Supports always stand against walls, so the pair
  that the shading brings together is the pair a user most needs to tell apart
  ([walls beside supports, with the three simulations](screenshots/review-m2-walls-beside-supports-colour-vision.png)).
  A wall facing the light also drops to 3.2:1 against the background, from 6.1:1.
- **Why it matters:** the feedback asks for colours distinct "including for the common
  kinds of colour blindness", and decision 33 states that as checked; for the walls it
  was checked on a colour the view mostly does not use.
- **Smallest fix:** shade by darkening only: a wall facing the light gets the flat colour
  `#2b5c9e` and the others go darker, down to `#1c3d68`. Every wall then stays at least
  20.3 from every other group in all four kinds of vision, and the walls still read as
  surfaces. Decision 33 gives the shaded range and the least difference over it.

#### M3. Lines are drawn 0.42 mm wide on paths laid 0.62 mm apart, so a solid surface shows a third of what is under it

- **Where:** Preview step, every width, every layer count; plainest on a finished top
  surface and on the solid layers 2 to 4. `js/preview3d.js`, `lineMaterial(1, 0.42)` and
  `lineMaterial(2, 0.42)`.
- **What is wrong:** the mock toolpaths are laid one line width apart, and the profile's
  line width is 0.62 mm (the printer has a 0.6 mm nozzle; advanced mode shows "Line width
  · Default 0.62 mm"). The view draws every line 0.42 mm wide, a number written into the
  code. So a third of every solid surface is gap: a finished top surface shows the orange
  infill of the layer under it between its green lines, and reads as a green and orange
  weave with moiré bands rather than as a green surface
  ([close up at 800 px](screenshots/review-m3-top-surface-close-up-800.png);
  [the same weave at 320 px](screenshots/review-m3-top-surface-320.png)). Decision 33
  says "each line has the extrusion's width (0.42 mm)", which contradicts the setting the
  panel itself shows.
- **Why it matters:** the colours were chosen so that each group reads as its own colour;
  on surfaces, the group the feedback names third, two colours mix. And 0.42 mm is a
  wrong number in the record the implementation will read.
- **Smallest fix:** give the line material the sliced settings' line width (the result
  already carries `settings.line_width`), and write decision 33 as "the line width of the
  settings (0.62 mm in every profile of the mock, unless changed in advanced mode)".

#### M4. The tooltip is now on every element that had a `title`; some of those texts only suited a slow tooltip

- **Where:** Settings step, Parts step, the step pills from 480 px, the Layout step's
  status line; `js/wizard.js`, `adoptTitle` and `bindTips`.
- **What is wrong:** the builder's brief allowed the other `title` tooltips to get the new
  tooltip "only if it is simple to do". All of them got it, with the same 150 ms delay
  and the same showing at once on keyboard focus. That suits an icon or a step circle,
  whose name is otherwise unseen. It does not suit these:
  1. **The four quick-change menus on the Settings step.** Their tooltip ("Sparse infill
     density in advanced mode") shows at once when a menu gets keyboard focus, stays while
     the arrow keys change the value, and shows again on a mouse click on the menu (in
     Chrome a menu counts as keyboard-focused after a click). It sits under the menu, on
     top of the next field's label
     ([focus on Infill hides "Walls"](screenshots/review-m4-tooltip-covers-next-label-320.png)).
     A user tabbing down the step has one label covered at every stop.
  2. **A part's name on the Parts step.** The tooltip repeats the name that is in full
     view and covers the size under it
     ([Hex Bore Spacer 1in](screenshots/review-m4-tooltip-repeats-part-name-320.png)). It
     is useful only when the name is cut short, as a long file name is.
  3. **The step pills at 480 px and wider,** and the current step's circle below 480 px:
     the tooltip "3. Layout" opens under a pill that already reads "3. Layout"
     ([at 480 px](screenshots/review-m4-tooltip-repeats-step-pill-480.png)). After a click
     on a circle or pill the tooltip comes back while the pointer rests there, over the
     first line of the plate summary of the step just opened (it shows in
     [this screenshot of S1](screenshots/review-s1-too-tall-after-auto-orient-320.png)).
  4. **The Layout step's status line** in a problem state: the tooltip repeats the line
     also where the line is shown in full (at 800 px; at 320 px the line is cut short and
     the tooltip is of use).
- **Why it matters:** a tooltip that repeats what is on screen was harmless after the
  browser's second of waiting; at 150 ms it flickers under the pointer on every pass over
  the step bar and the parts list, and on focus it hides the neighbouring control's
  label. The owner's bar is little text on working screens; these four add text that says
  nothing new.
- **Smallest fix:** three rules in `showTip`. A tooltip whose text is the element's own
  visible text shows only when that text is cut short. A step pill or circle whose name is
  showing has no tooltip. Showing at once on focus is kept for elements with no visible
  text (icons, step circles); a menu or a text field shows its tooltip on hover only.

### Low

#### L1. One browser tooltip is left in the panel, and it now also shows on the colour-key icon

- **Where:** Preview step, every width: the layer preview's `title` ("Drag to turn,
  right-drag to pan, scroll to zoom; drag the bar on the right to go through the
  layers").
- **What is wrong:** decision 63 keeps this one as the browser's tooltip on purpose. The
  colour-key icon and the open colour key sit inside the layer preview, and the icon's
  own `title` was taken over by the tooltip, so the nearest `title` above both is the
  layer preview's: a pointer resting on the icon gets "Colour key" at once and, about a
  second later, the browser's box about dragging. This was read from the page's structure;
  the browser's own tooltip cannot be captured here. Also, "What changed in version 8"
  says "The browser's tooltip is gone from the panel", which decision 63 contradicts.
- **Why it matters:** the browser's tooltip is the look the feedback asked to be rid of,
  and the two steps with a 3D view explain their gestures in two different ways (a "?"
  icon on Layout, a browser tooltip on Preview).
- **Smallest fix:** put the sentence behind a "?" icon beside "Reset view", as the Layout
  step does, and drop the `title`; correct the sentence in "What changed in version 8".

#### L2. "Tooltip" now names more than one thing, and the Layout view's does not look like the panel's (needs the owner's word)

- **Where:** Layout step, every width: the line the Layout view shows at its bottom left
  for what is under the pointer ("Drag to turn · Shift: 45° steps", "Lay it on this face:
  … tall", an instance's name).
- **What is wrong:** [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) calls that
  line a tooltip (decision 62: "The handle's
  tooltip is …"), and its glossary now defines **tooltip** as the panel's own white box,
  of which decision 63 says "Every tooltip in the panel is one small white box … at the
  body text size, 14 px". The Layout view's line is 11 px, with a 4 px radius and no
  shadow, fixed in the view's corner
  ([the line](screenshots/review-l2-layout-view-line-320.png) beside
  [the tooltip on the same step](screenshots/review-l2-layout-step-tooltip-320.png)).
  Decision 33 uses the word a third way: "How to turn, pan and zoom the view is its
  tooltip", which is the browser's (L1).
- **Why it matters:** one name for two things in the record the implementation reads;
  and the feedback's "larger text" may or may not be meant for this line. That part needs
  the owner's word.
- **Smallest fix:** give the line its own name in the glossary (it is a status line of
  the view, not a tooltip) and use it in decision 62; leave its look alone unless the
  owner wants it larger.

#### L3. After a section is closed in the accordion, widening the panel shows that section in the rail (taste)

- **Where:** advanced mode, crossing 480 px upward.
- **What is wrong:** a click on a section's heading in the accordion also makes it the
  rail's section, whether the click opened or closed it. Close Quality at 320 px, widen
  to 480 px: the rail opens on Quality, the one section the user just put away. The
  builder chose "the last section touched" on purpose (choice 4 of the result); this
  review would not count a closing as a choosing.
- **Smallest fix:** set the rail's section only when the click opens a section.

#### L4. A screen reader hears a step circle's name twice, and the colour key has two names

- **Where:** the step circles on keyboard focus; the colour key.
- **What is wrong:** `adoptTitle` rightly gives a step circle no description, since its
  name ("Step 3: Layout") says it. But `showTip` then points `aria-describedby` at the
  tooltip, which shows at once on focus, so the circle is read as "Step 3: Layout" and
  then "3. Layout". And the icon is named "Colour key" while the list it opens is named
  "Colours" (left from version 7's legend).
- **Smallest fix:** skip `aria-describedby` where `adoptTitle` skipped the description;
  name the list "Colour key".

#### L5. Leftovers of version 7 in the code

- **Where:** `js/wizard.js` line 1 still says "PenguinSlicer mockup, version 7";
  `bestArrange` in `js/plate.js` still counts and returns `turned`, which is always 0 and
  which nothing reads.
- **Smallest fix:** correct the header; drop `turned`.

## The builder's claims

[The result](result.md) was read only after the findings above were written. Its claims,
checked against this walk:

| Claim of the result | Holds | Note |
|---|---|---|
| Tooltip: hidden at 60 ms, shown at 260 ms; 14 px; 6 px inside the panel | Yes | Shown at 155 to 163 ms here. |
| Advanced mode: everything open; closed groups and sections stay closed across steps, reopening and 480 px | Yes | 30 groups, not counted in the result. |
| Printer details: open by 260 ms, never closed between icon and details, closed by 520 ms after leaving, a click pins, Escape closes | Yes | Open at 154 to 163 ms, closed at 302 to 317 ms here. |
| Arrange: a shaft turned 37° kept; smallest gap 5.3 mm with supports off | Yes | 5.34 mm on this review's plate; 12.88 mm with supports on, which the result did not measure. |
| The four colours' figures: least differences 27.7, 16.8, 21.4 and 20.3; at least 24.4 from the background; contrast 6.09, 2.31, 3.03, 2.72 | Yes, for the flat colours | Every figure reproduced by this review's own script. They do not hold for the walls as drawn (M2). |
| "Lines drawn as quads of the extrusion's width (0.42 mm)" | The drawing, yes; the number, no | The profile's line width is 0.62 mm (M3). The weave it causes shows in the builder's own `after/mixed-supports-on-6-half-zoomed.png`. |
| Renders of a six-instance plate and an overhang plate, at five layer counts, each looked at; no console error or warning | Taken on trust for the images, which exist | Here a plate that size lost the WebGL context four times in seven (M1). |
| Choice 5: the wizard still turns an instance that arrives too long, "and one Auto-orient lays down that is then too long" | In part | True on arrival and for Auto-orient with nothing selected. Not for the Auto-orient button of the too-tall error, which lays the one instance down by another path and leaves it square beside the plate (S1). |
| Every scenario-strip control walked at each width with version 7's sweep; no console error | Yes, as far as the sweep goes | The sweep shows each armed error and stops; it presses no remedy button, which is how S1 passed it. |
| "The overhang plate shows no supports": the mock's support finder does not mark the Camera Mount | Yes | Seen here too; supports show under the pulley's flange only. |
| The step-circle tooltip's screenshots are of the whole page because a clipped shot lost the tooltip | Yes | The same happened here: a clipped screenshot makes this Chrome send the page a pointer-leave. A test artefact, not a fault of the mockup. |

The result does not mention the drawing cost of the wide lines (M1); its "What I could not
do" names line weight on a real graphics card but not speed without one.
