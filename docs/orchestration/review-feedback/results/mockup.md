# Result: new terms in the wizard mockup

Status: DONE. Written Fri 11-20 09:43 PT. Brief: [mockup.md](../briefs/mockup.md).

## What changed

All in `docs/mockups/print-wizard/` (vendor files untouched):

- **copy → instance, copies → instances**, wherever they mean one placement of a part:
  student-visible text, scenario strip options (3a, 3b, 3c), button titles, comments, code
  identifiers (`S.instances`, `instanceById`, `instanceLabel`, `newInstance`,
  `totalInstances`, `layInstances`, `hitInstance`, `hoverInstance`, `instancesBox`,
  `instanceMaterial`, `instanceId`, the `instances` field of plate problems, and so on), and
  [DECISIONS.md](../../../mockups/print-wizard/DECISIONS.md), including the Terms table.
  Every "a copy" became "an instance".
- **`MAX_COPIES` → `MAX_INSTANCES`, value 25 → 100**, with
  `TOO_MANY_COPIES_MESSAGE` → `TOO_MANY_INSTANCES_MESSAGE`. DECISIONS entry 29 now says
  100 and `MAX_INSTANCES`.
- **Penguin Slicer → PenguinSlicer** in the page title, brand, stand-in Onshape panel head
  and app strip, file header comments, a toolbar hint, and DECISIONS.
- **plate job** and **HTTP face** do not appear in the folder; nothing to change.
- Kept as "copy": the three.js `.copy()` calls (vector, quaternion, colour copies), which
  copy values, not placements.

## Choices made

- Five places built the plural by hand (`' cop' + (n === 1 ? 'y' : 'ies')`): the summary
  chip, the Parts step total, the selection row, the slice summary line and the send
  confirmation. They now build `' instance' + (n === 1 ? '' : 's')`; same output shape.
- The hover key in `layout3d.js` changed from `'copy:' + id` to `'instance:' + id`, so its
  `key.slice(5)` became `key.slice(9)`. Same behaviour.
- The Onshape Assembly's own word "Instances" (its list title, "Click instances in the
  list", entry 27's "instance count") was already there and is Onshape's term; it is left
  as is. It now shares the word with PenguinSlicer's instance; in the Assembly an Onshape
  instance becomes one PenguinSlicer instance, so the two agree.
- "Zoom to instances" (button) and "F zooms to the instances" stay plural even with one
  instance on the plate, as "copies" did before.

## Sentences reworded beyond a plain word swap

1. Status line with one instance (`wizard.js`): was "✓ The copy fits the plate."; a plain
   swap gave "The instance fits the plate.", which reads oddly. Now it names the instance:
   "✓ Hex Bore Spacer 1in #1 fits the plate."
2. Plate-too-large remedy with one instance (`wizard.js`): was "This one copy is more than
   the server can slice, …"; now "This part alone is more than the server can slice, …".
3. DECISIONS, Open facts: "*Like Onshape* copies Onshape's mouse" (a verb) became
   "*Like Onshape* imitates Onshape's mouse", so that DECISIONS.md does not use "copy" at all.

No question, entry or option was added, removed or renumbered.

## What I walked

Headed Chrome under Xvfb with SwiftShader (WebGL on), driven by `playwright-cli`, folder
served on 127.0.0.1:8731. Scripts are in the scratch folder `mockup-builder/walk*.js`.

- Setup step, advanced mode (search "infill", Back to Setup), Parts step (three parts, one
  quantity raised to 3), Layout step, Preview step (slice finished, summary and legend shown).
- On the Layout step, every combination of the three scenario-strip menus: **Parts arrive**
  (lying their best way, as modelled) × **Mouse** (Like Onshape, Like a slicer, Top-down
  first) × **Lay on face** (Pictures under the view, Arrows on the part's faces, Box around
  the part, Tip handle). For each, an instance was selected by clicking it, then laid by a
  picture (strip) or a double-click on a flat face (the other three).
- Arrange, Auto-orient, undo and redo, and the armed errors 3a, 3b and 3c, with their
  sentences read ("instances need 5 mm between them").
- A plate of one instance (status line, slice summary, Send to Printer confirmation "1
  instance: Hex Bore Spacer 1in"), a quantity of 150 clamped to 100, and a plate of 100
  spacers (arrived and arranged in about 2.4 s: "✓ All 100 instances fit the plate.").

Console errors and page errors: none in any run. Browser, static server and Xvfb are
stopped; the `.playwright-cli/` snapshot folder the browser created at the repository root
was removed.

## For the coordinator

- The comment beside `MAX_INSTANCES` still points at `print/limits.py MAX_INSTANCES`, and
  DECISIONS entry 29 at `MAX_INSTANCES` in `limits.py`; whether the slice service's own
  constant has that name and value 100 is for the slice agent's change.
