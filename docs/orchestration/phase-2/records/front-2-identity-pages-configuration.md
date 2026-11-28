# Batch front-2-identity-pages-configuration: the record

The batch builds items 5 to 9 of the front server's phase 2 list
([By phase](../../../../front/README-details.md#phase-2-one-machine-no-onshape-no-printer)):
the development identity and the cookie with one cookie key, serving the wizard's pages,
the current group's check and `GET /api/me`, the configuration, and the table of settings
passed from the slice service. Written Fri 2026-11-27, Pacific time.

## Decisions made

1. **How the cookie is sealed.** The details file proposes AES-GCM or Fernet and is silent on
   the rest. Chosen: AES-256-GCM (the `cryptography` package, a new dependency), the key
   derived from the cookie key's text by HKDF-SHA256, a fresh 12-byte nonce each time, the
   whole written as unpadded base64url; the fields are one JSON object with `format` 1.
   Reason: authenticated encryption in one standard step, and a cookie key of any text gives
   a full-length key. To overrule: change `penguin_front/cookie.py`; every cookie then set is
   unreadable and each user signs in again once.
2. **What a cookie key may be.** Silent. Chosen: any non-empty text, as the settings already
   built accept; its strength is the owner's to choose. To overrule: add a form check in
   `settings.py` (for example 32 random bytes in base64).
3. **The cookie key on one machine is made in memory.** The guide says the cookie key is a
   setting and not made up in memory; the details file says that with the development
   identity on and no key, a key is made at start. Chosen: the details file's one-machine
   exception, since the guide's sentence is about the hosted service and the development
   identity signs in again at once. The `cookie_key_made` line is written just after the
   `start` line, so that `start` stays the first line of every start. To overrule: require
   `PENGUIN_COOKIE_KEY` always.
4. **When the cookie is extended.** The details file proposes "more than a day". Chosen:
   more than 86,400 s since its last use, on every answer to a request that read the cookie,
   an error included; an answer that read no cookie (a path not offered) carries none. A
   cookie is unread when 2,592,000 s or more have passed since its last use. The Set-Cookie
   carries `Max-Age` of thirty days. To overrule: `COOKIE_EXTEND_AFTER_S` and
   `COOKIE_LIFETIME_S` in `cookie.py`.
5. **"Hosted" is told by the address.** The documents say the cookie is `Secure;
   SameSite=None` and the policy's `frame-ancestors` Onshape's address "hosted", without
   saying how the code knows. Chosen: `PENGUIN_BASE_URL` starting `https://`. Reason: the
   one setting that differs hosted, and a cookie marked `Secure` cannot be set over plain
   HTTP anyway. To overrule: a setting of its own.
6. **`/signin` with the development identity off.** Silent for phase 2. Chosen: `404`
   `front.no_such_request`, its detail saying that signing in with Onshape is built in
   phase 3. To overrule: phase 3 replaces it with the trip to Onshape.
7. **Which `return` is a path of this site.** The contract says it must start with a single
   `/`. Chosen, beyond that: a `\` anywhere or a control character anywhere also makes it
   `/`, since browsers read `/\host` as `//host` and a control character could split a
   header. To overrule: `identity.safe_return`.
8. **The return address from `GET /`.** Chosen: the path and query as sent, percent-encoded
   whole into `return`, so `/signin` gives back exactly what was asked.
9. **The page files are read whole at start, assets included.** The details file says
   `index.html` is read once at start and the assets served "as it finds them". Chosen: every
   asset's bytes are read at start too, so that `make -C wizard build` run while the server
   runs changes nothing it serves until it is restarted, which is what the details file says
   happens. Cost: the assets' size in memory (a few megabytes). Files in folders inside
   `assets/` and names starting with `.` are not served. To overrule: serve from disk in
   `pages.asset`.
10. **The kinds of the assets.** Silent. Chosen: a fixed table for the kinds a build makes
    (`.js` `text/javascript`, `.css`, `.woff2`, `.woff`, `.svg`, `.png`, `.json`, `.wasm`,
    `.map`), the machine's table otherwise, and `X-Content-Type-Options: nosniff`.
11. **The refusal of a current group.** The details file asks for "a refusal line". Chosen:
    a `refused` line (`reason` `group_not_allowed`, `why`, `user_key`, `method`, `path`, the
    header and query named, each cut to 200 characters) before the `error` line; the `error`
    line of every report now also carries `user_key` and `group` once known. A changing
    request naming its group in the query alone names none, since the contract allows the
    query on a `GET` only.
12. **The configuration's canonical form, and the repeat.** The contract says a repeat is
    recognised when the saved document is "byte for byte the one this request carries"; the
    details file proposes comparing a canonical form. Chosen: every write stores
    `records.record_bytes` of the document (its JSON with `format` first), and a write whose
    condition fails answers `200` when the saved bytes equal the bytes it would write. A
    write based on a revision whose document is gone answers `409`. To overrule: the
    comparison in `configuration._repeated`.
13. **The rules are checked on the document as sent.** `write_record` always writes the front
    server's own format; checking after that would let a document of `format` 2 through.
    Chosen: the six rules are checked on the request's document as it is, then the canonical
    form is written.
14. **"The first rule broken".** Chosen: the lowest-numbered rule the document breaks, and
    among that rule's mistakes the first in the document's order. A `note` is held to the
    contract's 2,000 characters under rule 4; a colour's hexadecimal digits may be of either
    case; names are compared exactly. No rule was added beyond the contract's.
15. **The sentences of `front.configuration_invalid`.** The contract says its sentence names
    the first rule broken. Chosen: "The configuration was not saved, because <why>.", with
    the rule's number and the field's path in `detail`. `error_report` gained an optional
    `message` for this.
16. **What an edit's line holds.** Proposed in the details file: the paths of the fields that
    changed, with old and new values. Built so, each leaf of the document (an empty list or
    object counts as a leaf), null standing for a field not there; an old document that cannot
    be read counts as empty. A repeat writes no second line.
17. **The sentences of the six new codes.** Written plainly, with "your parts, layout and
    settings are kept in this browser" on `front.not_signed_in`; none says Onshape, team,
    student or mentor.
18. **The table of settings' compression.** Proposed: the slice service's compressed answer
    passed through. Built so: the front server asks for `gzip` when the browser's
    `Accept-Encoding` names `gzip` or `*` with a weight above zero, and `identity` otherwise,
    and passes the bytes and `Content-Encoding` as sent, with `Vary: Accept-Encoding`. A
    failure carrying the slice service's own report (`slice.*`, not compressed) is passed
    byte for byte with its status; any other failure answer is `500` `front.unexpected`.
19. **The client for the slice service.** Chosen: one httpx client, its answers read as raw
    bytes, `SLICE_TIMEOUT_S` 30 s (*proposed*) for a connection or the next bytes. Later items
    build on `SliceClient.get_raw` or add to it.
20. **A module of their own for what requests share.** `page_file`, `json_body` and the path
    as sent moved from `app.py` to `answers.py` (still importable from `app.py`), and the
    application's context to `context.py`, so that the request modules do not import
    `app.py`. The page's endpoints are named `wizard_page` and `wizard_asset`.
21. **Tests written after the code, for item 7.** The group check was written with item 5's
    code; its tests in `tests/test_groups.py` came after and were seen to fail by breaking
    the check by hand (four failures), which stands in for seeing them fail first.

## Targets missed

- **The cookie's size for a user in many groups.** A user in sixty groups with
  80-character names (the details file's proposed figures) and two 40-character tokens gets
  a cookie of 10,360 bytes, against browsers' limit of about 4,096; such a user could not
  sign in. The `cookie_large` line is written. The guide leaves this open for phase 3
  ([Whether the cookie fits](../../../../front/README.md#whether-the-cookie-fits)); a real
  account's tokens and group count decide it.
- **The fast suite's time.** 588 tests in about 11 seconds on two of eight shared
  processors, from about 2 seconds before the batch; each test builds the application on
  fresh folders (about 15 ms). Still "seconds", but no longer "a few".

## Not done

- The tests marked phase 3 and phase 4 in the sections built (the Safari page, the Connect
  page, the previous cookie key, the hosted policy beyond the one test of `https`): their
  phases build them.
- "A cookie of the previous format is read by the new front server": only format 1 exists;
  the test reads every format up to the current one and refuses a newer one, and gains its
  meaning with the first change of format.
- Nothing calls Onshape in phase 2, so the tests that the stand-in for Onshape receives no
  call hold trivially until phase 3 gives the front server a client for Onshape.
- The wizard's own build was not run through `make -C wizard build` (its install fetches a
  browser); its `build.py` was run with the system's Python into a scratch folder for the
  check below.

## For the owner to look at

- Start the front server on one machine as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says, after `make -C wizard build`, and open `http://127.0.0.1:8600/?plate=2`: the browser
  goes to `/signin` and comes back to `/?plate=2` signed in, and the page source shows the
  version in its `meta`. `curl -b <jar> http://127.0.0.1:8600/api/me` answers the development
  identity, and `curl -b <jar> -H 'X-PenguinSlicer-Group: dev-group'
  http://127.0.0.1:8600/api/configuration` the built-in default. Done once in this batch on a
  port above 20,000, with the wizard's current skeleton.
- Place a document written by hand at `/var/tmp/penguin-front/state/config/dev-group.json`
  with one mistake in it (a colour without its `#`), read the configuration again, and look
  for the `configuration_invalid` line on standard output: it names the rule and the field.
