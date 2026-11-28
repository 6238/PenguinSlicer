# Batch slice-2-settings: the table of settings and every setting that is a parameter

The builder's record of items 5 and 6 of
[the slice service's details, Phase 2](../../../../slice/README-details.md#phase-2-one-machine):
the table of settings, generated from the pinned Orca 2.4.2's source with every process
setting classified and served by the slice service, and every setting of it accepted in a
plate configuration under Orca's own name, built to
[the table of settings](../../../../contracts/settings-table.md),
[Settings in phase 2](../../../../contracts/plate-configuration.md#settings-in-phase-2) and
[the slice service's HTTP interface](../../../../contracts/slice-http-interface.md#get-settings-table).
What was built is described in
[The table of settings](../../../../slice/README-details.md#the-table-of-settings) and in
[the guide](../../../../slice/README.md#accept-settings).

## Decisions made

1. **A third class of process setting: not offered.** The documents classify every setting
   "as a parameter or as programmatic". Orca 2.4.2 has 355 process settings; 13 of them are
   on no page of Orca's process settings (among them the profile's own bookkeeping:
   `inherits`, `compatible_printers`, `print_extruder_variant` and the like), so they have
   no `section` or `group`, which the contract requires of every entry, and one,
   `small_area_infill_flow_compensation_model`, is a list of strings that no `kind` can
   describe. None of the 14 runs a program, names a file or is G-code, so calling them
   programmatic would be wrong. Chosen: a third list, `not_offered`, each with its reason,
   refused like a programmatic setting. The contract's and the guide's wording now says
   so. To overrule: move a setting from `not_offered` to `parameters` in
   `src/penguin_slice/settings/classification.json` (a setting on no page would also need a
   page and group the generator does not have, so the contract's required `section` would
   have to become optional).
2. **`filename_format` is programmatic.** The documents name the three kinds, not the
   settings. Of the 355, three are programmatic: `post_process` (runs a program),
   `process_change_extrusion_role_gcode` (custom G-code) and `filename_format`, the name
   Orca gives the sliced file, taken as "names a file on the server" since the slice service
   names the sliced file itself. Everything else on Orca's pages is a parameter, including
   the G-code output switches (`gcode_label_objects`, `exclude_object`, `gcode_comments`),
   the timelapse mode, printing by object and the multi-filament settings, since each only
   chooses among things Orca does. To overrule: move a name between the lists and run
   `make -C slice settings-table`.
3. **No setting is `per_variant` at Orca 2.4.2, and a profile's list gives its first
   value.** The contract's example marks `outer_wall_speed` `per_variant` with the High
   Flow value 500. Orca 2.4.2's source keeps only `print_extruder_id` and
   `print_extruder_variant` for each variant (`print_options_with_variant`; the speeds are
   commented out) and declares the speeds as single values, whose reader takes the first of
   a list. A real slice of the 0.30 mm Standard profile for the 0.6 mm nozzle (lists
   `["120", "500"]`) on the High Flow printer used 120. Chosen: `per_variant` as Orca's
   source says (false everywhere), and `process_values` the value Orca really slices with,
   the list's first; the upstream check slices two profiles and finds all 338 values in the
   settings Orca wrote into the sliced file. The writing of one value for every variant is
   built and tested on a table that marks a setting `per_variant`. The contract now says
   this beside `per_variant` and under Process values. To overrule: nothing to change in
   PenguinSlicer unless Orca changes; see "For the owner to look at" for what it means for
   prints.
4. **Where the source comes from and how it is verified.** The details proposed that
   `make upgrade-orca` download the source and verify it against a checksum beside
   `ORCA_VERSION`. Chosen: `SHA_SOURCE` in `scripts/install-orca.sh` (the SHA-256 of
   GitHub's archive of the tag, 131 MB), fetched by a separate script,
   `scripts/fetch_orca_source.py` (`make orca-source`), which keeps only the three files the
   generator reads (1.2 MB) in `slice/tools/orca-source/`; `install-orca.sh` does not
   download it, so `make install` costs no more. GitHub publishes no checksum of a tag's
   archive, so `make upgrade-orca` pins the checksum of the archive it downloaded (trust on
   first use over HTTPS); every later fetch is verified against it. `make test-upstream`
   runs `make orca-source` first, so the upstream check needs the network once. To
   overrule: fetch in `install-orca.sh`, or pin a checksum taken some other way.
5. **How the generator reads Orca's C++.** The details said reading the definitions "has
   not been tried". Chosen: regular expressions over the text with comments removed; a
   definition runs from `def = this->add("<name>", <type>)` to the next assignment of `def`,
   so the lines of options added in a loop are nobody's; `min`/`max` may be a literal or a
   named constant of the file; choices may be pushed, listed in braces or taken from another
   definition's variable; defaults are read from `set_default_value` and enum defaults
   turned into keys through `s_keys_map_<Type>`. A line it cannot read fails the generator
   only for a setting the table needs. A setting with no `min` or `max` line has no bound
   (Orca 2.4.2 writes no `INT_MIN`/`INT_MAX` bound, and the filter once kept for them acted
   on nothing, so it was removed in review). It worked
   on the whole of 2.4.2; the upstream check holds the result to what Orca slices with. To
   overrule: a different reader; the tests on the hand-written stand-in source say what it
   must do.
6. **The label.** Orca's `label`, or `full_label` where there is no `label`. The four
   overhang speeds sit on one line of Orca's page under the line's own label "Overhang
   speed", so their labels are "10%", "25%", "50%", "75%" and their explanation is empty
   (Orca's tooltip is on the line, not the setting). Their group, "Overhang speed", says
   what they are. To overrule: take a multi-option line's label and tooltip in
   `read_pages` and prefix them.
7. **The forms of a number, exactly.** The contract says "a number must be of its form"
   without a grammar. Chosen, as Orca writes numbers in profiles: the digits 0 to 9 only,
   `-?[0-9]+` for a whole number and within a C++ int, `-?[0-9]+(\.[0-9]+)?` for a decimal
   (no `+`, no space, no exponent, no `.5`, no `nan`), a percentage the same with `%`,
   at most 40 characters; then `min` and `max` on the figure, a `decimal_or_percent`'s
   bounds applying to whichever form it is written in. Every value of every catalog
   profile passes. A test found that Python's `\d` let an Arabic-Indic digit through; fixed.
   To overrule: change `settings_table.FORMS`.
8. **A text may hold no control character.** The contract gives only the length. Chosen:
   also refuse `\x00` to `\x1f` and `\x7f`, so no line break can reach the G-code header
   Orca writes the settings into. To overrule: drop `_CONTROL` in `settings_table.py`.
9. **A text's `max_length` over the process values.** "The length of its longest value in
   the profile catalog, never less than 1": taken over each process profile's value, its
   own or Orca's default. No catalog profile gives the four text settings a value, so each
   takes at most one character. Followed as written; see "Targets missed".
10. **The sentences of `slice.bad_overrides`.** The setting is named by its label, page and
    group ("Wall loops (Strength, Walls) must be at most 1000, not 1001."), since labels
    alone repeat ("Type", "10%"); one the table does not hold by its name, with the
    classification's reason, "belongs to the filament or printer profile" (known from the
    default set's filament and printer profiles' names) or "is not a print setting the
    slicer knows". The sentence names the first problem; the detail lists up to 20. The
    remedy became "Change that setting to a value it takes, or back to the profile's, and
    slice again.", with the action `choose_profiles` kept. A value must be a JSON string;
    `3` for `wall_loops` is refused. To overrule: the messages are constants at the top of
    `settings_table.py`, the remedy in `errors.CODES`.
11. **A table that cannot be read.** Not decided by the documents. Chosen: the code
    `slice.profile_unreadable` (the server's own files), with the sentence "The slicer
    could not read its table of settings.": HTTP 500 at `GET /settings-table`, and 422 at
    `POST /slices`, as for the other checking-stage codes, both logged. To overrule: a code
    of its own in `errors.CODES` and the details' code table.
12. **The route.** It serves the checked-in file's bytes as they are (`application/json`),
    gzip-compressed once per process when `Accept-Encoding` allows `gzip` or `*` with a
    quality above 0, with `Vary: Accept-Encoding` and the usual `Cache-Control: no-store`,
    and does not look at the user key, as the contract says. A method other than GET is
    `slice.bad_request` 405 as for every route.
13. **Names the details marked proposed.** Kept: `scripts/make_settings_table.py`,
    `src/penguin_slice/settings/table.json`, `src/penguin_slice/settings/classification.json`,
    `test_every_setting_of_the_pinned_orca_is_classified`. New: the module
    `settings_table.py` (not `settings.py`, which would sit beside the `settings/` folder
    and be confused with the service's environment settings), `scripts/fetch_orca_source.py`,
    `SHA_SOURCE`, `make orca-source`, `make settings-table`, the stand-in source
    `tests/fixtures/orca_source/` and catalog `tests/fixtures/settings_catalog/`.
14. **The old four overrides in tests and scripts.** Their "supports on" meant
    `enable_support` 1 with `support_type` `tree(auto)`; `scripts/measure_plate.py` and the
    upstream check keep that meaning (`measure_plate.SUPPORTS_ON`) so the measured rows
    stay comparable. The contract's pre-phase-2 example keeps its four overrides; its
    section is marked as no longer read, and the tests send them under Orca's names.
15. **The wizard's guide and details said "about 295".** They now say 338 (one line each).
    The mockup's DECISIONS.md, which is never edited, still says 295.
16. **A changed archive in the cache (from review).** The details said the cache keeps
    "each verified archive" but not what happens when one changes there. Chosen: it is
    verified against the pin like a download; on a mismatch the fetch fails with "checksum
    mismatch for the cached archive <path> ... remove it to download the source again",
    keeps nothing and leaves the cached file in place, so nothing the operator put there is
    deleted silently. To overrule: delete the cached file and download again in
    `fetch_orca_source.fetch`.
17. **Review finding declined: the `slice.profile_unreadable` remedy says "Ask a
    mentor".** Real, but the wording is in `errors.CODES` from before this batch, the same
    words stand in eight of the slice service's remedies, and the details file defers the
    rewording of the old remedies; changing one here would leave the rest inconsistent. Left
    for the batch that rewords the remedies. To overrule: reword all of them in one change.
18. **Review finding declined: text settings take one character.** The contract's rule
    gives that; changing the rule is the owner's decision (see "Targets missed").

## Targets missed

1. **"About 295 settings."** The pinned Orca has 338 parameters of 355 process settings;
   the documents' figure was an estimate and is corrected. The table is 378,740 bytes,
   34,716 compressed ("a few hundred kilobytes" holds).
2. **Text settings take one character.** By the rule of decision 9, each of the four text
   settings (`notes`, `extra_solid_infills`, `sparse_infill_rotate_template`,
   `solid_infill_rotate_template`) accepts at most one character, so "insert solid layers
   at 5,10,15" or a rotation template cannot be given. The requirement "keep every slicing
   setting reachable" is met for these only in name.
3. **The contract's example differs from the real table** in `per_variant` and in
   `outer_wall_speed`'s 0.30 mm value (500 in the example, 120 in the table), and in some
   labels and groups ("Sparse infill" in the example, "Infill" in Orca). The example is
   written by hand "of the kind Orca gives"; the test holds it to the real table's kinds,
   forms, fields and names only.

## Not done

None.

## For the owner to look at

- **The High Flow speeds that Orca does not use.** Five of the sixteen process profiles
  (the "Standard" ones of 0.16, 0.20, 0.24, 0.30 and 0.40 mm) give some walls and infill a
  faster speed for the High Flow nozzle, and the pinned Orca prints them at the standard
  nozzle's speed even on the default High Flow printer (outer wall 120 mm/s, not 500, for
  the 0.30 mm profile). The default set's 0.24 mm Balanced Quality profile is not affected.
  Whether PenguinSlicer should write the High Flow values itself is a decision of its own;
  nothing does today.
- **The classification**, setting by setting:
  [classification.json](../../../../slice/src/penguin_slice/settings/classification.json).
  The three programmatic and fourteen not offered settings are at its top.
- **The table itself**: `slice/src/penguin_slice/settings/table.json`; regenerate and
  compare with `make -C slice settings-table` then `git diff`.
- **The route**, from a checkout with `make -C slice install` done:
  `uv run --project slice python -m penguin_slice serve --work /var/tmp/penguin-slice --port 8640`,
  then `curl -s --compressed http://127.0.0.1:8640/settings-table | head -c 600` and
  `curl -s -o /dev/null -w '%{size_download}\n' -H 'Accept-Encoding: gzip' http://127.0.0.1:8640/settings-table`
  (about 35 kB).
- **A refusal's sentence**: submit a plate with `"overrides": {"wall_loops": "1001"}` or
  `{"post_process": "x"}` and read the `message`.
