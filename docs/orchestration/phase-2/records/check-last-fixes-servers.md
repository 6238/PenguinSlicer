# Batch check-last-fixes-servers: a second look at the last fixes of the servers

Each batch of phase 2 had up to three review rounds, and the fixes for the third round's
blocking findings merged without anyone looking again. This batch looks again at those
fixes for the front server (`front/`), the slice service (`slice/`) and the joined suite
(`together/`). For each finding: the fix found on `main`, the check undone by hand to see a
test fail, then restored, and the documents and the batch's record read against the code.
Where a fix was missing, wrong or untested, it is fixed here, test first. Nothing else is
rebuilt.

## The findings

1. **Pull request 25 (front-1-project-and-rules), the 255-byte name part:** fixed and
   tested as found. With the check of a part's length removed, three cases of
   `test_a_name_of_the_wrong_form_is_refused_before_any_file_is_touched` fail. Looking
   further at the names found a gap the fix had left, **fixed in this batch**: a name
   holding a lone surrogate (which JSON's `\udc80` gives) raised `UnicodeEncodeError` out of
   `check_name` instead of `BadName`. Such a name never comes from the front server itself,
   but a user key read from the slice service's `GET /slices` or a log line of its
   `GET /log` can hold one: one entry of that kind kept the collection at start from ever
   ending ("the collection never ended"), and one gathered line ended the gathering with
   the exception. Now `BadName`, so the entry or line is skipped as one of another form;
   three tests (`test_buckets.py`, `test_collecting.py`, `test_gathering.py`) failed first.
2. **Pull request 25, "no value in a line can make writing it fail":** fixed and tested as
   found. With the `except` of `_jsonable` narrowed to `ZeroDivisionError`,
   `test_a_container_that_cannot_be_read_is_written_as_a_note` and
   `test_gathered_lines_that_cannot_be_read_are_kept_as_notes` fail.
3. **Pull request 28 (front-2-identity-pages-configuration), the slice service's time
   limit:** fixed in this batch. The test the record names,
   `test_the_slice_client_waits_slice_timeout_s_for_the_next_bytes`, builds a `SliceClient`
   itself, so it holds the client's default and not the front server's requests: with the
   application building its client with `timeout_s=None`, the whole fast suite passed
   (1,061 tests). The new
   `test_the_front_servers_own_requests_to_the_slice_service_carry_slice_timeout_s` wraps
   the network of the client the application builds for itself and sees each request carry
   30 s for connecting, reading, writing and the pool; under that mutation it fails
   (`None` for all four). The details file names it.
4. **Pull request 30 (slice-2-settings), a lone surrogate in a text value:** fixed and
   tested as found. With the check of `_SURROGATE` removed, the three cases of
   `test_a_text_with_a_lone_surrogate` fail. Only the overrides reach the process profile
   that is written as UTF-8 (`print_config.write_process_with_overrides`), and choices and
   numbers cannot hold a surrogate, so no other path needs the check.
5. **Pull request 30, the checksum half of the source's VERSION stamp:** fixed and tested
   as found. With the stamp compared by `.startswith(version)`, both
   `test_a_stamp_of_the_same_version_with_another_checksum_downloads_again` and
   `..._is_verified_again` fail.
6. **Pull request 34 (front-4-streams-files-two-hours), one malformed record stopping the
   sweep:** the fix for a field missing or malformed holds, and is tested as found (with its
   `except` narrowed, the four cases of
   `test_a_record_with_a_missing_or_malformed_field_fails_alone_and_the_sweep_goes_on`
   fail, and the six new cases below as well). Of the other malformed records tried, one
   still stopped the sweep, **fixed in this batch**: a record nested deeper than Python's
   reader goes (100,000 nested lists, whole or as one field's value) raised
   `RecursionError` out of `records.read_record`, which caught only `ValueError`, so the
   sweep stopped at it at every run, as the finding described for a missing field. It is
   now unreadable ("not JSON: nested deeper than the reader goes"), with its
   `record_unreadable` line, like any other record the front server cannot read; this also
   holds for every other reader of records (the asking, the collecting, the gathering's
   cursor). The other records tried already passed: not JSON, empty, not UTF-8, a JSON list,
   a JSON string, no format, a future format number, a format given as text, a `state` that
   is a list or an object, a `slice_ended_at` that is a list, a number or past the year 9999,
   a due record with no `slice`, a folder at a record's name and at a sliced file's name, and
   a file where a user's folder is. Each is now a test
   (`test_a_record_that_cannot_be_read_is_left_alone_and_the_sweep_goes_on`,
   `test_a_record_of_other_wrong_types_fails_alone_and_the_sweep_goes_on`,
   `test_a_folder_where_a_record_or_a_sliced_file_is_expected_is_passed_over`); the nested
   cases failed first.
7. **Pull request 36 (slice-5-stop-log-restarts), the face-area condition:** fixed and
   tested as found. With `contact_area_mm2(...) < REST_AREA_MM2` replaced by `True`, both
   cases of
   `test_a_part_on_a_face_of_its_own_narrower_than_a_line_is_not_said_to_rest_on_an_edge`
   fail; the details file's sentence is true.
8. **Pull request 38 (front-5-start-log-whole), the record on the slice service's
   `GET /log`:** the record is fixed as found (decision 8 and "Not done" no longer say the
   route is unbuilt). Two of its sentences were stale and are corrected here: "Not done"
   still called the joined suite a later batch (batch together-1 built its first half), and
   "see ... below" pointed to a section above. The gathering is exercised against the real
   route by `together/tests/test_log.py`: with the front server asking `?since=` in place of
   `?after=`, that test fails. The front server's stand-in for the route did not answer as
   the real one does, **fixed in this batch**: an `after` left out was refused `400`, where
   the contract and the real route take it as 0; an `after` of 5,000 digits raised past
   Python's limit on digits, where the real route answers `200` with no lines; leading zeros
   were taken, as the real route takes them; its refusal's sentence differed from the slice
   service's. The stand-in now reads `after` as the real route does, tested in
   `test_slice_standin.py` (eight cases failed first, including `+1`, `1.0`, a leading space
   and `²`, which were already refused, now with the slice service's sentence). `process`,
   `lines`, `dropped` and `more` were already computed alike.
9. **Pull request 41 (together-1-front-slice-seam), the `slice_ended_at` check:** fixed and
   tested as found. With `collecting._ended_at` refusing every value, the joined test
   `test_a_slice_that_ended_while_the_front_server_was_down_is_collected_at_start` fails
   (`assert 1 == 0` on `ended_at_refused`), and with the count never raised three cases of
   `test_an_end_time_of_another_form_counts_the_two_hours_from_when_it_is_heard` fail. The
   test's comment, the record of the seam and the batch's record say what the check shows.

## Decisions made

1. **A name with a lone surrogate is `BadName`.** The documents say both forms take the same
   names and are silent on text that cannot be encoded. Chosen: refused like every other name
   of the wrong form, since no form can encode it (R2's keys are UTF-8), and the callers that
   read user keys from the slice service already skip a `BadName` as an entry of another
   form. To overrule: `check_name` in `penguin_front/buckets.py`.
2. **The test of the front server's time limit reads httpx's private `_transport`.** The
   documents are silent on how. Chosen: wrap the network of the application's own client,
   so that the time limits seen are those httpx hands each request the front server sends,
   at the cost of a test that reaches into httpx's private attribute. Reason: a new
   argument for tests to `create_app` would again test a client the test chose rather than
   the one the application builds. To overrule: a test hook on `SliceClient` that reports its
   time limits.
3. **A record nested too deep is unreadable, not malformed.** The documents say a file that
   is not a JSON object is refused as unreadable and are silent on nesting. Chosen: Python's
   reader cannot read it at all, so it is "not JSON", as front-2 decided for a configuration
   document. To overrule: the `except RecursionError` in `records.read_record`.
4. **The stand-in's `GET /log` copies the slice service's reading of `after`, and its
   sentence.** The contract fixes only that left out it is 0 and anything not a whole number
   is `400` `slice.bad_request`; the 18-digit bound and the sentence are the slice service's
   own. Chosen: copy both, so that a front server test of the gathering meets what the real
   route answers. The stand-in's remedy stays its own, since the slice service's says "Ask a
   mentor". To overrule: `SliceStandIn._log` in `front/tests/slice_standin.py`.
5. **The front server's fast suite is not made faster.** The plan says "finishes in
   seconds"; the earlier records carried 5 to 12 s on a loaded machine as open. Measured
   here, the suite (1,084 tests) takes 7.3 to 7.7 s on one worker and 4.6 to 4.8 s on two
   at a load average of 2.5 to 5 on the container's 8 processors (8.9 s at 1.4 on the first
   run, which included a cold start), and 11.8 s and once 27.9 s on one worker while other
   builders ran. No test takes more than 0.6 s: the time is spread over about 1,100 tests,
   of which 752 build the application (2.8 ms each, of which 1.6 ms is werkzeug compiling
   the URL builders of its 15 routes) and about 700 start a stand-in server. The one
   cheap cut found is to memoize werkzeug's private `Rule._compile_builder` in the
   suite's `conftest.py`, worth about 1.2 s on one worker for the application's routes and
   about as much for the stand-ins'; it was not made, since it replaces the framework's
   routing code under every test with code of the suite's own, against a library's
   private interface that may change at any release. Before and after are therefore the
   same figures. To overrule: add the memo, or build the stand-ins' Flask applications
   once per test session.
6. **The slice service's sentences that say "mentor".** Every sentence a user reads that
   says "mentor" is a remedy in `slice/src/penguin_slice/errors.py`, unchanged since
   Fri 11-20 (before phase 2); no commit of phase 2 changed or added one (`git log -G` over
   `slice/src` and `slice/scripts` since Thu 11-26 finds none), and the sentences phase 2's
   batches added (`slice.no_user_key`, `slice.bad_units`, `slice.stopping`,
   `slice.rests_on_an_edge`, `slice.output_too_large`) do not use the word. They are the
   plan's known future work ("The words the components write") and are not rewritten here.
   They are: `SERVER_REMEDY` ("Slice again; if it fails again, ask a mentor to check the
   print server.", the remedy of `slice.unexpected`, `slice.orca_killed`, `slice.no_output`,
   `slice.unreadable_output`, `slice.no_gcode`); `slice.unknown_printer`;
   `slice.profile_unreadable`; `slice.scratch_unwritable`; `slice.orca_missing`;
   `slice.orca_unstartable`; `slice.orca_crashed`; `slice.output_unwritable`; and
   `slice.bad_request`. Phase 2 newly reaches two of them: `slice.profile_unreadable` is
   the answer of `GET /settings-table` when the table cannot be read (batch slice-2,
   decision 11), which the front server passes to the page as it is, and
   `slice.bad_request` answers an `after` of `GET /log` that is not a whole number (batch
   slice-5), which only the front server sees. The words "student" and "team" appear only
   in comments of `limits.py`, `plate.py` and `slicer.py`, which no user reads. To
   overrule: reword all of them in one change, as batch slice-2's decisions 17 and 30 say.

## Targets missed

1. **The front server's fast suite "finishes in seconds"** holds at 7.3 to 7.7 s on one
   worker and 4.6 to 4.8 s on two on a machine shared by four builders, and not at 11.8 s
   or 27.9 s while they ran (decision 5). No figure of the plan's is sharper than
   "seconds".
2. **The fixes of this batch were checked only by their builder** until this pull request
   is reviewed.

## Not done

1. **A slice service answer nested too deep.** `slice_client.json_object` and the
   following's reading of a progress stream's events (`following.py`) catch `ValueError`
   only, so an answer of the slice service nested past Python's reader would raise
   `RecursionError` there. It is outside this batch's findings (the slice service is a
   component on the private network that never writes such an answer) and is left for
   whoever next changes those readers.

## For the owner to look at

- The fast suites: `make -C front test`, `make -C slice test`, and the joined suite
  `make -C together test`, from the repository's root.
- The new tests of this batch: `front/tests/test_two_hours.py` (the malformed records),
  `front/tests/test_settings_table.py`
  (`test_the_front_servers_own_requests_to_the_slice_service_carry_slice_timeout_s`),
  `front/tests/test_slice_standin.py` (the stand-in's `after`) and the lone surrogate cases
  in `front/tests/test_buckets.py`, `test_collecting.py` and `test_gathering.py`.
