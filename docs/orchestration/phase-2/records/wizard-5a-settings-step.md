# Batch wizard-5a-settings-step: the record

Item 9 of [the wizard's details, "By phase", phase 2](../../../../wizard/README-details.md#phase-2-one-machine):
the Settings step and advanced mode. Built on Sat 2026-11-28 by one builder, with no one to ask,
while another builder built the Layout step in another worktree. What is built is described in
the details file's sections [The Settings step](../../../../wizard/README-details.md#the-settings-step)
and [Advanced mode](../../../../wizard/README-details.md#advanced-mode) and, in plain words, in the
guide's [The Settings step](../../../../wizard/README.md#the-settings-step) and
[Advanced mode](../../../../wizard/README.md#advanced-mode).

## Decisions made

1. **A quick change whose value is not on its menu shows that value as one more entry at the
   top of the menu, chosen.** To decide: the guide leaves it to the owner
   ([its open item](../../../../wizard/README.md#a-quick-change-whose-value-is-not-on-its-menu))
   and the details file says to build its recommendation. Chosen: the recommendation, the value
   written as advanced mode writes it ("35 %", "Mouse ear"); the profile's entry stays while it
   is the profile's value, a change's entry goes once another value is picked; when both the
   profile's value and the change are off the list, the profile's entry comes first. Counted
   while building: none of the 16 process profiles of the pinned Orca 2.4.2 has a value off any
   of the four lists, so the case comes from a configuration profile's overrides (the
   hand-written example's 35 % infill) and from advanced mode. To overrule: change `quickMenu`
   in `wizard/src/settings.js`.
2. **A quick change's menu has no "Default (…)" entry.** The mockup's menus start with "Default
   (40 %)"; the details file lists each menu's entries without it and says a menu shows the
   value the plate will be sliced with. Chosen: the details file's list, the profile's value
   chosen when there is no change. Reason: the guide is right where the two differ, and picking
   the profile's own value already removes the change. To overrule: put an entry before
   `menu.entries` in `quick()` of `wizard/src/settings.js` and adjust the tests.
3. **Supports Off writes `enable_support` and leaves a change of `support_type` as it stands.**
   The details file says "Off: `enable_support` `"0"`, and nothing for `support_type`". Chosen:
   the words as written, so On then Off over a profile whose type is not tree(auto) leaves the
   type's change in the box, where the user sees and can reset it. To overrule: delete the
   `support_type` change in `setQuick` when Off is chosen.
4. **Numbers are compared as numbers, and an accepted number is written the shortest way.** The
   documents say a change put back to the profile's value is no change, and are silent on
   "0.30" against "0.3". Chosen: two values of a number setting are the same when their figures
   are equal and both or neither are percentages; "0.20" typed is written "0.2" (never in
   exponent form). To overrule: `sameValue` and `readInput` in `wizard/src/settings.js`.
5. **A value that does not fit is the wizard's own error report `wizard.setting_refused`, with
   the slice service's rules.** The guide says only that a value outside the allowed range is
   refused where it is typed. Chosen: the page checks everything the slice service checks
   (`slice/src/penguin_slice/settings_table.py`: the number forms in ASCII digits, 40
   characters, a C++ int, `min` and `max`, a text's length, control characters and lone
   surrogates, a choice's values), so nothing the page accepts is refused later; the sentences
   follow the mockup's ("Layer height must be between 0.08 and 0.42 mm. Kept 0.3 mm."), under the
   setting in red. A percentage typed without its sign gets it. To overrule: `readInput` and
   `settingRefused` in `wizard/src/sentences.js`.
6. **A stored change the table no longer holds, whose value no longer fits, or that equals the
   profile's value is dropped without a word when the page opens.** The documents are silent.
   Chosen: dropped once the table and the configuration have both arrived, and kept untouched
   until then. Reason: such a change would make the slice service refuse the plate; it happens
   only when the Orca version moves. To overrule: have `settle` in `wizard/src/settings.js`
   return what it dropped and show a notification.
7. **The filament's colour is a small square inside the closed Filament menu's box, for the
   chosen filament only.** The guide wants each filament's colour beside its name in the menu.
   Chosen: the square, since a native menu's open list cannot be relied on to draw colours
   (Chrome on a Mac ignores an option's style), and a menu drawn by hand would leave the
   mockup's look. A colour not of the form `#rgb` or `#rrggbb` draws no square. To overrule: a
   listbox of the page's own in place of the `select`.
8. **An on-and-off setting is a menu of "Off" and "On", not the mockup's box to tick.** The
   details file says each control is drawn from its kind and an on-and-off setting has "Off"
   and "On" (the contract's choices); the mockup ticks a box. Chosen: the menu, so nothing is
   designed by hand for a kind of setting. To overrule: draw a checkbox for a `choice` whose
   values are exactly `"0"` and `"1"` in `control` of `wizard/src/panel/settings-step.js`.
9. **A number that may be a percentage (`decimal_or_percent`) is typed in a text field** in the
   number field's look, with Orca's whole unit ("mm or %") after it, since a number field
   cannot hold "110%". To overrule: two fields, or a unit menu, in `control`.
10. **Reset all asks in the guide's confirmation, placed inside advanced mode,** with "Put all 2
    changed settings back to Structural’s values?", Keep my changes (first and focused) and
    Reset all; the button is disabled with no change, as the mockup's is. The guide names the
    confirmation and not its words. To overrule: `RESET_ALL_QUESTION` and `KEEP_CHANGES` in
    `wizard/src/sentences.js`.
11. **The Settings step's markup comes before the Parts step's in `index.html`,** as in the
    mockup, since the page's test holds every id in the mockup's order; `#advanced` follows
    `#wiz-nav`. Shared files were touched only where needed: `index.html` (that markup),
    `state.js` (one field, `advanced`), `main.js` (the wiring, and reports naming the step
    `advanced` while it is open), `sentences.js` (a block of the step's words, kept apart from
    the end of the file where other builders add theirs), `css/wizard.css` (a block),
    the Makefile (one target).
12. **Advanced mode is open while the store's `advanced` is true, kept as the stored plate's
    `advanced`, and reopened only on the Settings step.** The details file names the stored
    field and says the page reopens in advanced mode if it was open. Chosen: a page opening on
    another step with `advanced` stored clears it. To overrule: `resume` in
    `wizard/src/settings.js`.
13. **Changes are kept and listed in the order they were made**, as the mockup's are; a change
    of an already changed setting keeps its place. To overrule: sort `lines()` by the table's
    order.
14. **Orca's explanation of a setting is its label's tooltip,** followed for a setting with a
    quick change by "Also on the Settings step as Infill." (the mockup's tooltip). The guide
    says advanced mode shows the explanation and not where. To overrule: `settingRow` in
    `wizard/src/panel/settings-step.js`.
15. **Any change of filament or profile clears the changes,** the configuration read again
    without the plate's own profile included, and not the first time the stored names are
    taken up. To overrule: the store listener in `createSettings`.
16. **The pictures beside the mockup give the built page a configuration and a table of
    settings made from the mockup's own sample** (its filament, five profiles and their values,
    its sample of settings), so each pair differs only where the look differs. The contract's example
    table has nine settings and would make every advanced-mode pair differ. To overrule:
    `table_and_configuration` in `wizard/tests_browser/look_settings_step.py`.
17. **Advanced mode's sections are the table's, six at the pinned Orca** (Quality, Strength,
    Speed, Support, Multimaterial, Others, 39 setting groups), where the guide and details said
    five. The documents are corrected to say the table's sections.

## Targets missed

1. **Each filament's colour beside its name in the open Filament menu**: only the chosen
   filament's colour shows, in the closed menu's box (decision 7).
2. **Differences in the pictures beside the mockup**
   ([docs/orchestration/phase-2/look/wizard-5a/index.html](../look/wizard-5a/index.html)), each
   looked at and not removed:
   - No printer-status icon in the header's name line or in advanced mode's (phase 5), so each
     panel's header is 2 px shorter than the mockup's.
   - The plate summary's second line names the filament as the configuration names it ("Bambu
     PETG HF · Structural") where the mockup gives its material ("PETG · Structural"); that line
     is item 4's and was built so before this batch.
   - The configuration's name is plain text, where the mockup's is a link (the guide's
     departure from decision 2, built before this batch).
   - The quick changes have no "Default (…)" entry (decision 2).
   - The filament's colour square inside the Filament menu (decision 7).
   - An on-and-off setting is a menu "Off"/"On" where the mockup ticks a box (decision 8).
   - Reset all asks in a confirmation where the mockup arms its button (decision 10).
   - Below the Settings step's fields the built page sits 1 to 2 px higher than the mockup in
     some rows at 320 px; not traced, under the measure of anything a user would see.
   - A `decimal_or_percent` setting's unit, "mm or %", is wider than the others', so its field
     sits further left than its neighbours'. The mockup's sample has no such setting; the real
     table has 36.
3. **Not measured:** how long advanced mode takes to draw the real table's 338 settings on a
   slow machine; no document sets a target for it.

## Not done

1. **The printer-status icon in advanced mode's name line**: it comes with the icon, in phase 5.
2. **A notification when a stored change is dropped** (decision 6): not built, since no document
   asks for one.

## For the owner to look at

- The pictures of the Settings step and advanced mode beside the mockup at 320, 480, 520 and
  680 px, six states each:
  [docs/orchestration/phase-2/look/wizard-5a/index.html](../look/wizard-5a/index.html). Made by
  `make -C wizard look-settings-step`.
- The tests in Chromium: `make -C wizard test-browser` (the Settings step's are in
  `wizard/tests_browser/test_settings_step.py`, among them advanced mode drawn from the slice
  service's real table of 338 settings).
- The open item [A quick change whose value is not on its menu](../../../../wizard/README.md#a-quick-change-whose-value-is-not-on-its-menu)
  is built as its recommendation and waits for the owner's answer. To see it: choose the
  hand-written configuration's PETG-CF, whose "Stiff bracket" profile has 35 % infill.
