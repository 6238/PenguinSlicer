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
5. **Slashes.** Silent. Chosen: a path differing from an offered one by a doubled or a
   trailing slash is `404`, never a redirect. Reason: a redirect would be an answer the
   contract does not list.
6. **What counts as JSON.** The rule is "a body that is not JSON is `front.bad_request`".
   Chosen: the body is read as JSON whatever its `Content-Type` says; an empty body, one cut
   short, one not in UTF-8, and one using `NaN` or `Infinity` (which Python's reader would
   otherwise accept) are refused. Reason: the page sends JSON; refusing on the header alone
   would only add a way to fail.
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
    `/`-separated parts, none empty, `.`, `..` or starting with `.`, with no `\` or NUL; the
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
