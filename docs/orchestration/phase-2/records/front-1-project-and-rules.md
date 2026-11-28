# Batch front-1-project-and-rules: the front server's project, fakes, buckets, rules and log writer

The builder's record for items 1 to 4 of the front server's phase 2 list
([By phase](../../../../front/README-details.md#phase-2-one-machine-no-onshape-no-printer)):
the project and its fakes, the bucket interface in its folder form with the format number on
every record, the rules for every request, and the log's writer. What was built is described
in [the front server's details file](../../../../front/README-details.md), and in plain words
in [its guide](../../../../front/README.md#what-is-built-in-which-phase).

## Decisions made

1. **The web framework, the server and the HTTP client.** The documents propose "a WSGI
   server in one process with a fixed pool, such as waitress", and are silent on the
   framework and the client. Chosen: Flask for the application, waitress for serving, and
   httpx for the front server's calls to the slice service (used so far only by the tests;
   the client itself is for items 9 to 12). Reason: the slice service and the relay are
   Flask applications, and the relay joins the front server's process in phase 5; waitress
   gives the fixed pool of threads the design asks for; httpx streams both ways, which the
   progress streams and the 50 MB sliced file need. To overrule: replace `create_app` and
   `server.py`; no contract changes.
2. **How each setting is checked.** The documents give the names and defaults and are
   silent on forms. Chosen: `PENGUIN_DEV_IDENTITY` is `1` (on) or unset, empty or `0` (off),
   anything else stops the start; the two addresses are `http` or `https` with no path; the
   three folders must be absolute; `PENGUIN_FRONT_THREADS` is 1 to 1,000;
   `PENGUIN_GROUPS_REREAD` is `never` or seconds of at least 1; `PENGUIN_FRONT_STOP_S` at
   least 1; a `PENGUIN_VERSION` not of the version's form stops the start. Reason: a
   mistyped setting is found at start, not as a strange answer later. To overrule: change
   `settings.py` and its tests.
3. **An unset folder setting in phase 2.** The table says the hosted default of
   `PENGUIN_STATE_DIR` and `PENGUIN_LOG_DIR` is "unset: R2". Chosen: in phase 2 unset means
   the folder of the table, since there is no R2 form yet; phase 3 changes this. To
   overrule: nothing to undo; phase 3 decides how R2 is chosen.
4. **`OPTIONS` and `HEAD`.** The contract says any path or method not in its table is
   `404` `front.no_such_request`; `HEAD` and `OPTIONS` are in no row. Chosen: `OPTIONS` is
   refused as `front.no_such_request` (Flask would otherwise answer it, with an `Allow`
   header); `HEAD` is answered wherever `GET` is, as HTTP requires. To overrule: one line in
   `app.py`.
5. **Slashes.** Silent. Chosen: a path with a doubled slash anywhere, its start included,
   or differing from an offered one by a trailing slash is `404`, never a redirect; the
   report and the line give the path as sent. Reason: a redirect would be an answer the
   contract does not list. How (changed after the second review): one check before every
   handler reads the path of the request's target as sent (`REQUEST_URI`, which waitress
   and Werkzeug's test client both set, without its query or fragment and, in the absolute
   form `http://host/path`, without scheme and host), and the decoded `PATH_INFO` as well
   (so `/x/%2Fy` is refused). Reading `PATH_INFO` alone was not enough: waitress 3.0.2
   strips a path's leading slashes before the application sees it (`task.py`, `path = "/" +
   path.lstrip("/")`), so `GET //x` and `GET http://h//x` arrived as `/x` and were served;
   a target with no leading slash (`GET x`) was served too. Both are now `404`, as is an
   absolute form with no path (`GET http://h`): the contract's table names paths, and a
   target with none is not one of them. A doubled slash in the query alone is served.
   After the third review, an encoded slash `%2F` (either case) anywhere in the path is
   refused too, since waitress decodes it and would serve `/t%2Fx` as `/t/x`.
   The tests send these request lines through waitress itself (`tests/test_server.py`).
   The router's own `merge_slashes` setting is not used, the check covering what it did.
   To overrule: the check in `create_app` and `_path` in `app.py`.
6. **What counts as JSON.** The rule is "a body that is not JSON is `front.bad_request`".
   Chosen: the body is read as JSON whatever its `Content-Type` says; an empty body, one cut
   short, one not in UTF-8, and one using `NaN` or `Infinity` (which Python's reader would
   otherwise accept) are refused. Reason: the page sends JSON; refusing on the header alone
   would only add a way to fail. Added after review: a body nested too deeply for Python's
   reader (which raises `RecursionError`, whether the body is whole or cut short) is
   `front.bad_request` too, not `front.unexpected`, which the page would retry quietly for
   300 seconds. The depth at which the reader gives up is Python's own limit; no bound of
   the front server's own is set, since no request of the page nests more than a few
   levels. The tests send 50,000 and 100,000 levels.
7. **The web framework's own refusals.** Silent. Chosen: a refusal of Flask's below 500
   (a body too large, a header too long) is `front.bad_request`, one of 500 or more is
   `front.unexpected`. Reason: no answer may be other than an error report of the front
   server's own codes.
8. **What `front.unexpected` tells the page.** The documents say the trace goes to the log.
   Chosen: the report's `detail` names only an incident id, and the log line carries the same
   id and the whole trace. Reason: a support request quoting the page's report finds the
   line, and the answer shows nothing of the code's insides.
9. **One log line for every error report answered.** The documents ask a line for every
   error a user is shown. Chosen: event `error`, with `code`, `status`, `method`, `path`
   (never the query string, which carries Onshape's code from phase 3), `detail` except on a
   `500`, and `page_version` only when `X-PenguinSlicer-Page` has the version's form (a
   header of another form is not written, since it comes from the browser). The user key,
   the group and the slice job join the line when the items that know them are built.
10. **The sentences of the three codes built.** `front.bad_request`: "The server could not
    read this request." / "Reload the page and try again; if it happens again,
    PenguinSlicer needs fixing." `front.no_such_request`: "The server does not offer this
    request." / "Reload the page; if it happens again, PenguinSlicer needs fixing."
    `front.unexpected`: "Something went wrong on the server." / "Your work is kept; try
    again in a moment." To overrule: `errors.py`.
11. **The bucket interface's names and behaviour** (marked *proposed*). Chosen: `open`,
    `get`, `put(if_marker=, if_absent=)`, `delete`, `copy_onto_itself`, `list`; `NotFound`,
    `ConditionFailed`, `BucketUnavailable`, `BadName`; a delete of a file already gone is not
    an error (as R2's is not); a listing is sorted by name; a name is 1 to 1,024 bytes of
    `/`-separated parts, each at most 255 bytes (added after the third review), none empty, `.`, `..` or starting with `.`, with no `\` or NUL; the
    folder form's marker is the SHA-256 of the contents, computed at each open; its store
    time is the file's modification time set from the front server's clock; its temporary
    files are named `.tmp-<random>` and no listing shows them; pieces are at most 1 MiB.
    Reason: the same names and limits must work for R2 in phase 3. To overrule: change
    `buckets.py` and the shared tests together.
12. **The format numbers.** The documents fix `format` counting from 1. Chosen: two kinds so
    far, `configuration` 1 and `sliced_file` 1; `write_record` always writes the front
    server's format for the kind, replacing any `format` the record held; `read_record`
    returns an older format as stored, since no older format exists yet to convert from; a
    missing `format`, a `true`, a string, zero, or a number above the front server's is
    refused with a `record_unreadable` line.
13. **The log's file names and failures** (marked *proposed*). Chosen:
    `<YYYY>/<MM>/<DD>/<HHMMSS>-<8 hex digits>.jsonl` at the moment of writing, created only if
    the name is free, a new random part tried up to 5 times; a minute with no lines writes no
    file; a file that cannot be written keeps its lines for the next minute, at most 100,000
    lines, the oldest dropped first and counted in a `log_lines_dropped` line; the failure is
    said on standard output only (`log_bucket_unwritable`), so a failing log never feeds
    itself. A line's `time` is to the millisecond, as the slice service's lines are.
14. **Gathered lines are not printed again.** Silent. Chosen: the slice service's lines (and
    from phase 5 the relay's and the daemons') are kept for the log bucket but not written
    to the front server's standard output, since they are already in their own component's
    output; the lines the front server writes for the page's reports are printed. To
    overrule: one line in `log.py`.
15. **The start and stop lines.** Chosen: `start` with `version`, `host`, `port`,
    `threads` and `dev_identity`; `stop` when the serving ends, then the gathered lines are
    written. Item 17 adds the asking for the slice jobs.
16. **The fakes are real servers on the loopback address.** The documents ask for stand-ins
    a test controls. Chosen: the stand-ins for the slice service and for Onshape are small
    Flask applications served on a port the system chooses, not fakes inside the client.
    Reason: the front server's real HTTP client, streams and failures (a connection refused,
    a file cut halfway) are then what the tests exercise. The stand-ins announce every change
    so tests wait on events.
17. **The fake clock's interface.** Chosen: the clock gives `now()` and `sleep(seconds,
    stop)`, and whoever sets `stop` calls `wake()`. Reason: a background loop (the log's
    minute, later the sweep and the retries) then sleeps on the fake clock and is woken by
    the test's `advance`, with no thread ever waiting a real duration.
18. **The stand-in's own sentences and figures.** Where the slice service's contract has no
    example (unknown slice job, busy, bad units and so on), the stand-in's sentences are its
    own and are not the slice service's. Its slice jobs' ids are `j` and 16 hexadecimal
    digits unless a test names them; its `expected_s` is 75; it measures a part from the
    binary STL itself. Every answer that has an example is asserted equal to it.
19. **The stand-in for Onshape's shapes.** The documents leave what Onshape answers to
    phase 3. Chosen: `/oauth/authorize` and `/oauth/token` as OAuth 2 has them,
    `GET /api/users/sessioninfo` giving `id` and `name`, and `GET /api/companies` giving
    `items` of `id` and `name`, written down in the stand-in as to be corrected in phase 3.
20. **No network beyond loopback, and no sleeping.** The details file proposes a check that
    fails a test that sleeps or reads the real clock. Chosen: every test has `time.sleep`
    replaced by a failure and name lookups and connections beyond loopback refused; a further
    test reads the package's source and fails if any module but `clock.py` reads the real
    clock or sleeps. Reading the real clock at run time cannot be refused without breaking
    the libraries, which read it themselves.
21. **The table of requests in the tests.** The details file proposes that a test hold the
    contract's table as data. Chosen: the test reads the table from the contract itself, and
    holds the application to `BUILT` in `tests/test_rules.py`, the requests built so far
    (none yet), each of which must be a phase 2 row. Each later item adds its requests to
    `BUILT`.
22. **The make targets' bounds.** Chosen: every target runs pytest from the project's own
    environment under `timeout` (600 seconds) and `prlimit` on its address space (4 GB), and
    each test under pytest-timeout's 30 seconds; `coverage` fails under 100% branch coverage,
    as the slice service's does.
23. **The served test uses four threads.** Under the 4 GB limit on its address space and
    with coverage on, a waitress server of 100 threads ran out of address space: each thread
    reserves memory of its own. The test of the running server sets four threads; the default
    of 100 is checked by the settings' test. The front server's memory at 100 threads is the
    guide's open item [the front server's memory](../../../../front/README.md#the-front-servers-memory).
24. **The folder form's answers for a name that is a folder** (after review). The
    documents say both forms take the same names. Chosen: in the folder form, reading a
    name that is a folder of other files is `NotFound`, deleting it is harmless, and a
    listing under a file is empty, as R2 answers; a write that would make one name both a
    file and a folder (`a` beside `a/b`) stays `BucketUnavailable`, since a folder cannot
    hold both. Reason: the layout of names (state and log) never puts a file where another
    name's folder is, so the remaining difference is never met, and the cheap cases now
    match R2. A second difference, found by the third review, is closed rather than named:
    a part over 255 bytes (a file system's limit on one name) was `BucketUnavailable` in
    the folder form and taken by R2; every form now refuses it as `BadName`, so the one
    difference above is the only one. No name of the layout comes near 255 bytes in a part. To overrule: escape names in the folder form, at the cost of files no longer
    sitting at their names' paths.
25. **Writing any value in a log line** (after review). The details file says a value JSON
    cannot hold is written as its text. Chosen: `NaN` and the infinities are written as
    text (`"nan"`, `"inf"`), keys that are not text as their text, a value met again inside
    itself as a note, and anything past 64 levels as a note; the same for gathered lines.
    Added after the second review: an integer past Python's limit of 4,300 digits, which
    neither `json.dumps` nor `str` can write, is the note `<int of N bits, too long to
    write>`, as a value or a key, and an object whose `__str__` raises is the note `<Type
    that cannot be written as text>`. No request reaches either today (bodies and gathered
    lines are refused at parsing), but the documents say no value can make writing a line
    fail. Added after the third review, which showed that claim still false: a list, tuple
    or mapping whose iteration or `items()` raises is the note `<Type that cannot be
    read>`. Reason: a line must never fail inside the request that writes
    it, and every line must be JSON for the reading command. To overrule: `line_text` in
    `log.py`.
26. **Settings checked for range as well as form** (after review). Chosen: an address with
    a user or password, or a port of 0, past 65535 or not a number, is refused; a
    `PENGUIN_VERSION` whose date or time is not real (month 13, 25 o'clock, 31 November) is
    refused. Reason: as decision 2, found at start. To overrule: `settings.py`.
27. **The line of a refused start** (after review). The details file says a missing secret
    stops the start "with a log line". Chosen: the line `start_refused` with `setting` and
    `detail`, on standard output where every log line goes, plus the same words on
    standard error for whoever typed the command; the line reaches no file of the log
    bucket, whose folder is itself a setting and may be the one refused. To overrule:
    `serve` in `server.py`.
28. **Review findings declined.** The Onshape stand-in answers companies only, no
    classrooms: declined, since decision 19 records its shapes as provisional and what
    Onshape answers for a group is phase 3's to settle with the real interface; adding a
    guessed shape now would be one more thing to correct.
29. **A number too large for a float in a body** (second review, minor). Python's reader
    reads `1e999` as an infinity, which no JSON answer can hold. Chosen: such a body is
    `400` `front.bad_request` ("the number ... is too large for the server to read"), as
    `NaN` and `Infinity` already are. Reason: the body is JSON, but the front server
    cannot keep it as written, and a later handler that echoed or stored it would write
    invalid JSON. To overrule: `finite` in `json_body`.
30. **Fixes of the second review, and nothing declined.** All five findings were checked
    against the code and found real; each has a test that failed for its reason before the
    fix: the leading doubled slash through waitress (decision 5), the integer too long to
    write (decision 25), the kept lines trimmed after a failed write
    (`test_lines_written_while_a_file_fails_stay_within_the_bound`), the stand-in's place
    given up by a replaced slice job
    (`test_every_place_taken_a_changed_plate_of_the_same_user_key_is_accepted`, which fails
    with the reviewer's mutation), and `1e999` (decision 29).
31. **Fixes of the third review.** Both blocking findings were real and fixed, each with a
    test that failed for its reason first: a name part over 255 bytes is `BadName`
    (decision 24, `test_a_name_of_the_wrong_form_is_refused_before_any_file_is_touched`,
    and a 1,024-byte name of 255-byte parts is still written and read), and a container
    that cannot be read is a note (decision 25,
    `test_a_container_that_cannot_be_read_is_written_as_a_note`). Of the minor findings:
    an encoded slash `%2F` anywhere in a path is now `404` `front.no_such_request`
    (decision 5; waitress decodes it, so `/t%2Fx` was served as `/t/x`, and no path of the
    contract holds one); `lines_kept` of `log_bucket_unwritable` no longer counts the
    `log_lines_dropped` line; the mutation of `Log.flush`'s `if not texts and not dropped`
    is now killed by `test_a_count_of_dropped_lines_alone_is_still_written` at
    `max_pending=0`, the code kept as it is since a count of drops with no line must still
    be written; the guide's "the version on every answer" now names waitress's own
    answers to requests it cannot parse. Declined: that `gather` keeps a line that is not
    a JSON object (a string, a number) as a file line. The reviewer names it item 18's to
    settle, and it is: item 18 builds the fetching of the slice service's lines and the
    page's reports, and is where a line of the wrong shape is refused or wrapped, by
    the rules of the slice service's contract for its lines.

## Targets missed

- **The version and `no-store` on every answer.** Waitress answers a request it cannot
  parse at all (a malformed request line, headers over its limit) itself, before the
  application runs, and that answer carries neither `X-PenguinSlicer-Version` nor
  `Cache-Control: no-store`. The page treats an answer without the version as not the front
  server's and retries it quietly, which is the right outcome; but the rule "every answer,
  whatever its status" is not met for those answers. No figure: it is every such answer.
- **Each test seen to fail before its code.** Each test file of the front server's own
  modules (settings, clock, buckets, records, rules, log) was written first and seen to fail
  as a whole, its module not yet there, rather than test by test. For the two stand-ins and
  the serve command, the tests and the code were written before the first run, so those
  tests were never seen to fail. To make up for it, one check was broken by hand (the
  stream's fifteen-second repeat dropped), and the example test failed as it should; the
  reviewer's mutations are the real check.
- **The fixes of the third review were merged without a further review.** That round was
  the last; the fixes of decision 31 were checked only by their builder's tests and the
  fast suite, not by a reviewer who did not write them.

## Not done

- **The R2 form of the buckets and `make -C front test-r2`:** phase 3, as the plan says.
  The shared tests take a new form in their `FORMS` list.
- **The once-a-minute line of how full the front server is** (memory, slice jobs, open
  connections, threads in use): listed among the log's lines, but it reports what items 12,
  13 and the threads' test build; it belongs with them.
- **The gathering of the slice service's lines and the page's reports:** item 18. The writer
  takes them (`gather`, `write_as`); nothing fetches them yet.
- **The check that no log line or answer of the whole suite holds a secret:** item 19, once
  there are secrets in play (the cookie key from item 5).
- **The previous release's stand-in for the slice service and the previous release's page:**
  item 19, from the second release on.
- **The refusal of an id of another form in a path:** no request with an id exists yet; the
  items that build `/api/slices/<slice>` apply it.
- **The client for the slice service:** items 9 to 12, which use it.
- **The development identity's cookie key made at start:** item 5. Until it is built, a
  front server started with the development identity and no key simply has no cookie key.

## For the owner to look at

- The fast suite, in random order: `make -C front install` once, then `make -C front test`.
  Branch coverage: `make -C front coverage` (100%).
- The front server answering on one machine, from the repository's root:
  `PENGUIN_DEV_IDENTITY=1 uv run --project front python -m penguin_front serve --port 27461`,
  then `curl -i http://127.0.0.1:27461/api/me`: a `404` `front.no_such_request` error report,
  with `X-PenguinSlicer-Version` and `Cache-Control: no-store`, since no request of the
  wizard's exists yet. Its lines appear on standard output, and on Ctrl-C a file appears under
  `/var/tmp/penguin-front/log/<year>/<month>/<day>/`.
