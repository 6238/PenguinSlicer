# Result: wizard mockup version 8

Built Thu 2026-11-26, about 09:28 to 10:30 PT, on branch `mockup/v8`, from
[the brief](brief.md). The mockup is in [docs/mockups/print-wizard/](../../mockups/print-wizard/index.html);
its decisions are in [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md), now version 8,
with "What changed in version 8" at the top. The owner's feedback file
(`docs/handoffs/2026-11-26-mockup-v7-feedback.md`) is folded into DECISIONS.md and deleted
with `git rm`; the one link to it, in the brief, now names it in words.

## Every point of the feedback, and where it is met

| Point | Met | Where |
|---|---|---|
| Step-circle tooltips appear faster | Yes | 150 ms after the pointer rests (the browser's took about a second); at once on keyboard focus. `bindTips`, `showTip` in `js/wizard.js`; decision 63. Walk: hidden at 60 ms, shown at 260 ms, at 320, 480 and 800 px |
| …look like the rest of PenguinSlicer, not the browser's tooltip | Yes | `.wiz-tip` in `css/panel.css`: white box, 1 px `#d0d7de` border, radius 8 px and the shadow of the printer details; the panel's font; kept 6 px inside the panel (measured inside at all three widths) |
| …and have larger text | Yes | 14 px, the body text size (the browser's is about 12 px) |
| Every section of advanced mode open by default | Yes | `groupOpen`, `sectionOpen` default to open; walk: "sections 11111, groups all 1" at 320 px, every group open in the rail at 480 and 800 px; decision 13 |
| Advanced mode remembers each section's and each setting's open state while the page is open | Yes | `S.advSecOpen`, `S.advOpen` in the page's memory. Walk at each width: a closed group (and, below 480 px, a closed section) stayed closed after going to another step and back, after closing and reopening advanced mode, after crossing 480 px and back; the Expand all icon's change was remembered too. "Each setting" is read as each group of settings (see choice 3) |
| Printer details open when the pointer rests on the icon, and still on a click | Yes | `bindPrinterHover`, `openPrinterPop`, `togglePrinterPop`; decision 44. Walk: closed at 60 ms, open at 260 ms; never closed while the pointer moved from icon into the details; still open 120 ms after leaving both, closed at 520 ms; a click pinned them (open 700 ms after leaving); Escape closed; Enter opened and closed |
| Arrange never turns an instance back to its original orientation; every instance keeps its orientation | Yes | `arrange` and `pile` in `js/plate.js` turn nothing; decision 64. Walk: a 1/2in Hex Shaft turned 37°, then Arrange: every instance turned by 0.000°, no problems, smallest gap 5.3 mm with supports off (5 mm needed) |
| Four fixed colours: walls; infill; top and bottom surfaces; supports and brim | Yes | `GROUPS` in `js/preview3d.js`; decision 33 |
| Not the filament's colour, not Orca's; distinct (also for colour blindness), clear on the light background, calm | Yes | Chosen and checked by script (below); the filaments lost their colour (`js/settings.js`) |
| A colour key, closed by default, behind a small icon on the preview | Yes | `#btn-key`, `#pv-key`, `renderKey`; four rows; closed at first, closes on Escape, a click elsewhere or leaving the step |
| Test renders at different layer counts; tune colours, line weight, lighting, ghost | Yes | Below, and `screenshots/before/`, `screenshots/pass-1/`, `screenshots/after/` |

## The four colours

| Group | Colour | L\* | C\* | Hue | Contrast on `#f2f4f7` |
|---|---|---|---|---|---|
| Walls | `#2b5c9e` blue | 39.0 | 41.2 | 279° | 6.09:1 |
| Infill | `#e0912f` orange | 66.8 | 64.6 | 70° | 2.31:1 |
| Top and bottom surfaces | `#2f9e7a` green | 58.5 | 41.0 | 166° | 3.03:1 |
| Supports and brim | `#9a8fb8` violet-grey | 61.6 | 23.5 | 302° | 2.72:1 |

Why: four hues about a quarter of the wheel apart; different lightness so pairs survive the
loss of hue; the darkest, strongest colour for the walls, which outline every part; the
least saturated colour for supports and brim, which are not the part and should recede;
chroma kept moderate so the view is calm beside the wizard's blue and greys.

Checked with a script (`colours.py` in the scratch folder): Machado, Oliveira and
Fernandes (2009) simulation at full severity in linear RGB, distances in CIEDE2000.
Smallest pair distance: normal 27.7 (walls and supports), protanopia 16.8 (infill and
surfaces), deuteranopia 21.4 (surfaces and supports), tritanopia 20.3 (walls and
surfaces). Every colour is at least 24.4 from the background in every vision. Candidates
rejected: the Okabe-Ito blue, orange, bluish green and reddish purple (smallest 10.9, and
louder); darker greens and lighter oranges (smallest 12.2 to 14.3).

## The test renders and what each change fixed

Scripted with `playwright-cli` (`renders.js`): two plates (a mixed plate of six instances:
L Bracket, two HTD Pulleys, Gusset Plate, Hex Bore Spacer, Hex Shaft; and an overhang plate:
Shooter Hood Rib, Camera Mount, L Bracket), supports off and on, at layers 1, 4, 68, 121 and
134 of 134, at 480 px; a zoomed view at half height for each. Every image was looked at.

- **Before** (`screenshots/before/`, version 7): every layer of every part a flat orange
  silhouette; walls, infill and surfaces indistinguishable; no depth; at a few layers or
  half height nothing showed where the layer was or what was still to print; supports
  barely visible.
- **Pass 1** (`screenshots/pass-1/`, mixed plate only): four colours; lines drawn as
  quads of the extrusion's width (0.42 mm) seen from the camera, at least 1 px, instead of
  WebGL's fixed 1 px lines, which gives the lines weight when zoomed in; walls shaded by
  the way they face from the Layout view's main light, which turned the stacked walls into
  readable lit surfaces; the current layer drawn again, unshaded and at least 2 px wide,
  over the layers below; a ghost of the part above the current layer. Seen: colours read
  well; the ghost (grey `#a3adb8` at 28%) was too faint to see at a few layers.
- **After** (`screenshots/after/`): the ghost darkened to `#95a0ac` at 36%, now visible
  above the current layer on the pulleys, spacer and bracket and gone at the last layer.
  The overhang plate failed to render in pass 1 because Arrange no longer turned the rib
  (see choice 5); fixed by the wizard's turn on arrival. Each of the 20 standard images and
  4 zoomed ones was looked at: walls blue and shaded on every part, infill orange inside,
  surfaces green on first layers and tops, supports violet-grey under the pulley flanges;
  no colour clashes with the plate grid.

## Choices made (the owner was away)

1. **Every tooltip in the panel became the panel's own,** not only the step circles'
   (simple: one delegated rule that takes over each `title` as it is set). Kept the
   browser's: options inside menus, and the Preview view's "Drag to turn…", which would
   sit over the view while dragging. The scenario strip is not the panel and keeps the
   browser's.
2. **The printer-status icon lost its tooltip;** its sentence ("Shop H2S is free") is
   now the icon's description for screen readers, since the details open on hover.
3. **"Each setting" was read as each group of settings.** Nothing on a single setting
   opens or closes today (its "Profile … · Reset" line shows whenever it is changed), so
   there was no per-setting state to remember; no new control was added.
4. **Below 480 px the sections no longer close each other.** "Open by default" and
   "remember each" cannot hold with one open at a time. Clicking a section heading also
   makes it the rail's section, so crossing to 480 px shows the last section touched.
5. **The wizard still turns an instance that arrives too long for the plate** (the
   Shooter Hood Rib, 353 mm), once, on arrival, and one Auto-orient lays down that is then
   too long. The owner's point names "by the wizard" as a source of orientation, and
   without it the rib waits beside the plate and Next stays off. Arrange itself never
   turns. Its message for instances that do not fit now ends "or turn or lay instances
   another way to make room."
6. **The rest delays:** tooltip 150 ms; printer details open 150 ms after the pointer
   enters and close 300 ms after it leaves icon and details; a click on hover-opened
   details pins them rather than closing them.
7. **The key always has four rows,** with supports off too, as the brief asks; the brim
   uses the supports' colour.
8. **Filaments lost their preview colour** in `js/settings.js`, and the requirement on
   the configuration for a colour per filament was dropped from DECISIONS.md.
9. **Shading uses the Layout view's main light direction** (front left, above), so both
   views are lit alike.
10. **The browser session was named `mockup-v8`,** not the one in `$PLAYWRIGHT_CLI_SESSION`,
    on its own Xvfb display (`:118`), with the folder served on port 8742 by a small
    no-cache server (the first server let Chrome keep old scripts).

## What I could not do, or did not

- **How the hover feels** is the owner's to judge; the walk only times it.
- **Line weight on a real GPU:** the renders come from SwiftShader in Xvfb; antialiasing
  and pixel ratio on the owner's Mac will differ (sharper at 2× pixel ratio).
- **The camera** was left as version 7 framed it; the renders did not show a need.
- **The overhang plate shows no supports** with supports on: the mock's support finder
  does not mark the Camera Mount's overhang. That is the mock geometry, not version 8.

## The walk

Served `docs/mockups/print-wizard/` on port 8742; Chrome under Xvfb with SwiftShader WebGL,
driven by `playwright-cli`. Screenshots are in [screenshots/](screenshots/).

- **Every step at 320, 480 and 800 px** (`walk.js`; Parts, Settings with a change,
  advanced mode, Layout, Preview, the colour key, Send, sending): `320-*.png`,
  `480-*.png`, `800-*.png`. Nothing scrolls sideways; no console error or warning.
- **The version 8 checks at each width** (`checks.js`): tooltip, Arrange, printer hover,
  advanced mode, colour key, as in the table above; no console error or warning.
- **Every scenario-strip control at 320, 480 and 800 px** (version 7's sweep, unchanged
  but for the folder; screenshots at 320, `sweep-320-*.png`): widths, Fewer controls,
  Hide strip, How to use, speed, every context, uploads in both units, every armed error,
  every Printer state, Refresh, Close and reopen, Come back 2 h later, 12 hours later. The
  script ran to its end at each width; no console error or warning. The printer details
  it opens with clicks behaved as in version 7.
- **The step-circle tooltip photographs** (`*-tooltip-step-circle.png`) are of the whole
  page: a shot clipped to the panel came out without that tooltip although the page showed
  it (the Arrange tooltip's clipped shot has it); the panel is at the right.
