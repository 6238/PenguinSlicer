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
   exponent form, and never rounded: see decision 24). To overrule: `sameValue` and `readInput`
   in `wizard/src/settings.js`.
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

Decided while fixing the review's findings (pull request #42):

18. **After Reset all goes ahead, the focus goes where opening advanced mode puts it**, the
    first section's heading (the first rail tab from 480 px), since Reset all is then disabled
    and a disabled button cannot hold the focus; after Keep my changes it returns to Reset all.
    The documents are silent. To overrule: the Reset all handler in
    `wizard/src/panel/settings-step.js`.
19. **A text's length is counted by code points, as the slice service counts it**, so an emoji
    is one character, and the field's own `maxlength` (which counts UTF-16 units) is twice
    `max_length` so that the field never refuses before `readInput` does. The documents said
    "characters" without saying which. To overrule: `readInput` in `wizard/src/settings.js` and
    `control` in `wizard/src/panel/settings-step.js`, together with the slice service's check.
20. **Sections and setting groups whose words fold to the same id get `-2`, `-3` after it**, in
    the table's order, and which ones are closed is kept by their words (a key no two pairs of
    words share), never by their ids. The real table has no such pair; the case is hostile words.
    To overrule: `uniqueId` and `groupKey` in `wizard/src/panel/settings-step.js`.
21. **A quick change takes only a value its menu offers**; any other value is ignored, so the
    shared changes can reach a value outside the menus only through advanced mode, which reads and
    refuses it. To overrule: `setQuick` in `wizard/src/settings.js`.
22. **The review's finding that a changed value redraws every drawn row, where the details file
    said only its row, was settled in the document, not the code**: each drawn row is brought up
    to date in place, at most the real table's 338, which costs nothing a user sees, and a Reset
    all changes every row at once. The details file now says so.

Decided while fixing the second review's findings (pull request #42):

23. **A refusal lasts only while the value it names as kept is the setting's value.** The guide
    says a refusal shows "the value it keeps" and that Reset all puts every setting back; it is
    silent on a refusal standing when the value changes under it. Before this fix, Reset all left
    a refused field showing the refused text over a "Kept 5." that was no longer true. Chosen:
    each drawn row remembers the value its refusal names; `refreshRow` drops the refusal and
    shows the new value when the setting's value differs from it, whatever changed it (today
    only Reset all can, since advanced mode covers the rest of the panel and is drawn afresh
    each time it opens). A refusal whose value is left as it was keeps the text refused, so the
    user still sees what they typed and why it was not taken. Reason: this keeps every sentence
    on the page true without clearing refusals that Reset all did not touch. To overrule:
    `refreshRow` and `dropRefusal` in `wizard/src/panel/settings-step.js` (for example, clear
    every refusal on Reset all whatever its value).
24. **An accepted number keeps all its digits.** `shortest` dropped digits a double cannot hold
    ("12345678901234567890" became "12345678901234567000"). Chosen: the figure is shortened by
    its own text, dropping only leading zeros of the whole part, trailing zeros of the fraction
    and the sign of a zero, so the value sent is the number typed. Its bounds are still checked
    as a double, as the slice service checks them with Python's `float`. To overrule: `shortest`
    in `wizard/src/settings.js`.
25. **A stored change that fits but is written another way is written again, not dropped.** A
    stored `sparse_infill_density` of "35" or " 35 " passed `settle` and would have gone to the
    slice service, which refuses a percentage without its sign. Chosen: `settle` replaces the
    stored value by `readInput`'s ("35%") and then drops it if that is the profile's value.
    Reason: the user's change is kept, and only storage the wizard did not write can hold such a
    value. To overrule: drop such a change in `settle` instead.

Findings of the second review declined:

- **Two mutations that change nothing a user sees** (dropping `!configProfile()` from `settle`'s
  guard; dropping `changes = {}` from `chooseProfile`). Both are equivalent mutants and the code
  stays: with no configuration profile, every profile value is undefined and `sameValue` never
  calls a stored value equal to undefined, so nothing is dropped either way, but the guard is what
  the details file says (stored changes kept "until both the table and the configuration have
  arrived") and keeps `settle` from resting on that accident; `chooseProfile` clears its own
  changes before it writes the stored plate, so the written plate never holds the old profile's
  changes under the new profile's name, whatever order the store's listeners run in, the same as
  `chooseFilament`. No test can tell either apart through the page, so none was added.

Findings of the first review declined: none. The finding on the pictures' heights (747 px against
760 px) is recorded under "Targets missed" rather than removed: making them equal would mean
taking the 24 built pictures again for 13 px of panel at the bottom.

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
   - The `*-reset-all` pairs: the built picture still shows the Layer height row refused (0.9
     in red, "Kept 0.3 mm."), and the mockup's shows 0.3 with no refusal. The mockup arms its
     button and draws its list again at the first press, so its refusal goes; the wizard's
     picture is taken with its confirmation open, before anything is reset. Even once the user
     resets all, this refusal stays and stays true: Layer height was never changed, so its value
     is still the 0.3 its sentence names (decision 23). A refusal whose value Reset all does
     change goes with the reset. The pictures were not taken again: the built state they show
     is unchanged by the fix.
   - The pictures are 747 px tall for the mockup and 760 px for the wizard at every width, as
     in wizard-4: the mockup's frame gives its panel 747 px, the wizard's picture is taken in a
     760 px window. The wizard's picture shows 13 px more of the panel's scrolling content
     above its bottom bar; everything else lines up.
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
