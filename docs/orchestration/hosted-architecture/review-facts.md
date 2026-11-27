# Fact-check: the hosted architecture's claims about outside systems

Reviewed: [the hosted architecture spec](../../specs/2026-11-25-hosted-architecture-design.md),
against [the plan](../../plans/penguin-slicer-plan.md). Every page below was read on
Wed 2026-11-25 (Pacific). This review checks facts about Railway, Cloudflare, Onshape and
browsers; it does not review the design's internal logic.

Verdicts: **confirmed** (an official page states it), **wrong** (an official page or a named
employee contradicts it), **unconfirmed** (no official page settles it; the evidence found is
given). "Smallest change" is the least edit to the spec that makes it true or safe.

Where the vendor's documentation was silent, the next best evidence is named as such: a
Railway employee's post on Railway's forum, the running PenguinCAM code, or Onshape's
published OpenAPI file.

## Summary

| # | Claim | Verdict |
|---|---|---|
| 1 | Phase 4: "Nothing here changes; the panel uses the same sign-in" (the cookie reaches Onshape's panel) | Wrong for Safari; conditional in Firefox and Chrome |
| 2 | Parts in the browser's storage survive in Onshape's panel | Wrong for Safari across a browser quit; unconfirmed where third-party cookies are blocked |
| 3 | A read-only credential for one Railway bucket | Wrong: Railway cannot issue one |
| 4 | The log bucket "keeps them ninety days" | Risky: Railway buckets have no lifecycle rules |
| 5 | Configuration is written "on the condition that it has not changed" | Unconfirmed on a Railway bucket; confirmed on R2 |
| 6 | "A disk that is emptied whenever the container restarts" | Unconfirmed for a restart; holds for a redeploy |
| 7 | The custom-header CSRF defence | Sound, with conditions the spec does not state |
| 8 | Progress streams pass Cloudflare and Railway unbuffered | Unconfirmed; timeouts confirmed |
| 9 | Onshape sign-in for every user costs nothing | Risky: a private app's calls count against the app owner's annual limit |
| 10 | The cookie holds the Onshape tokens for thirty days | Risky: refresh tokens rotate; cookie size; terms not readable |
| 11 | The slice container "accepts requests only from the front container" and a flaw there "exposes ... nothing else" | Mostly confirmed; outbound internet is open |
| 12 to 25 | The remaining claims | Confirmed, or confirmed by inference (see below) |

## Wrong or seriously risky

### 1. The session cookie in Onshape's panel

**Claim.** "Phase 4, inside Onshape. Nothing here changes; the panel uses the same sign-in."
The cookie is `SameSite=None; Secure`, as PenguinCAM's is
(`/repos/popcornpenguins/PenguinCAM/frc_cam_gui_app.py` lines 222 to 239).

**Verdict: wrong for Safari, conditional elsewhere.**

- **Safari.** "ITP by default blocks all third-party cookies. There are no exceptions to this
  blocking. Third-party cookie access can only be granted through the Storage Access API and
  the temporary compatibility fix for popups." A `SameSite=None; Secure` cookie does not reach
  a cross-site iframe. https://webkit.org/tracking-prevention/
  Partitioned cookies (CHIPS) are reported back in Safari 26.2 after being switched off in
  18.5 (WebKit bug 292975, Google's CHIPS status page); I did not find Safari's release notes
  for it, so treat Safari's CHIPS support as unconfirmed.
  https://bugs.webkit.org/show_bug.cgi?id=292975 ,
  https://privacysandbox.google.com/cookies/chips
- **Firefox.** Cookies in a cross-site iframe are partitioned by top-level site by default
  since Firefox 103. A cookie set by the OAuth popup (a top-level page) is not in the panel's
  partitioned jar. It reaches the panel only through the popup heuristic ("the third-party is
  granted storage access to its embedder for 30 days"), which Mozilla calls transitional, or
  through the Storage Access API.
  https://developer.mozilla.org/en-US/docs/Web/Privacy/Guides/State_Partitioning
- **Chrome.** Third-party cookies stay on by default (Google dropped the phase-out in April
  2025), so the cookie reaches the panel in a default Chrome profile. Incognito and a user who
  chose "Block third-party cookies" do not send it. Sources here are news reports, not a
  Chrome document: https://www.theregister.com/2025/04/22/google_privacy_sandbox/ .
- PenguinCAM's own guide lists "Browser blocking third-party cookies" as a known cause of a
  failed sign-in (`/repos/popcornpenguins/PenguinCAM/docs/AUTHENTICATION_GUIDE.md` line 366).
  So "the app already runs in Onshape's panel" is evidence for default Chrome only.

**Smallest change.** Replace the phase 4 sentence with: the panel needs its own way to hold the
session where third-party cookies are blocked (a cookie with the `Partitioned` attribute set by
a response inside the panel's frame, which the OAuth popup cannot set itself, so the popup must
hand the sign-in to the panel; or the Storage Access API), and phase 4's spec designs it. Name
the browsers the panel supports. Add the cookie to "To confirm before building on it" next to
the browser's storage, for Chrome, Safari and Firefox.

### 2. The browser's storage inside Onshape's panel

**Claim.** "Parts and the layout live in the browser's own storage"; "A page embedded in
another site gets storage of its own, and browsers differ in how long they keep it."

**Verdict: confirmed for Chrome and Firefox; wrong for Safari across a browser quit.**

- **Chrome.** Third-party storage, IndexedDB included, is partitioned by top-level site "for
  all users on Chrome 115 and later". The panel's storage is separate from the standalone
  page's. https://privacysandbox.google.com/cookies/storage-partitioning
- **Firefox.** IndexedDB in a cross-site iframe is statically partitioned by top-level site.
  https://developer.mozilla.org/en-US/docs/Web/Privacy/Guides/State_Partitioning
- **Safari.** "Third-party LocalStorage and IndexedDB are partitioned per first-party website
  and also made ephemeral", and ephemeral means "the storage does not persist to disk and goes
  away with the application, for instance when the user quits the browser or reboots their
  device." Parts in the panel survive a reopened panel but not a quit of Safari.
  https://webkit.org/tracking-prevention/
- **Safari's seven-day cap** ("ITP deletes ... all other script-writeable storage after 7 days
  of no user interaction with the website", IndexedDB listed) is longer than the spec's two
  hours, so it does not bite. Same page.
- **Quota for about 190 MB.** Chrome: up to 60% of the disk per origin. Firefox: the smaller
  of 10% of the disk or 10 GiB. Safari: about 60% of the disk per origin, and "cross-origin
  frames" get "a separate quota of roughly 1/10 of their parent's". All are far above 190 MB
  on a normal disk. The page gives no figure for private windows.
  https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria
- **Unconfirmed.** Whether IndexedDB opens at all in the panel when the user blocks
  third-party cookies (Chrome setting, Incognito). No page read here states it.

**Smallest change.** In "Where each piece of state lives", add to the first row's "When it is
lost": "in Safari inside Onshape's panel, also when the browser quits". In "Coming back", say
the wizard works with the parts held in memory when the browser's storage cannot be opened.

### 3. A read-only credential for one Railway bucket

**Claim.** "The owner's coding agents read the log bucket with a credential that can read that
bucket and do nothing else"; listed under "To confirm", with Cloudflare R2 as the fallback.

**Verdict: wrong for Railway; the fallback is confirmed.**

- Railway employee "brody", Thu 2026-10-15: "there is no supported way to issue a separate
  read-only or prefix-scoped credential for a bucket today." Each bucket has one credential
  with full read and write access.
  https://station.railway.com/questions/storage-buckets-read-only-prefix-scope-34f1f33d
- Railway's bucket page describes one credential set per bucket and no scopes.
  https://docs.railway.com/storage-buckets
- R2: the "Object Read only" permission can "read and list objects in specific buckets", and
  with it "you can scope your token to a set of buckets".
  https://developers.cloudflare.com/r2/api/tokens/

**Smallest change.** State that the log bucket is a Cloudflare R2 bucket, and remove the item
from "To confirm". The secrets count stays five. See items 4 and 5: the same move settles both.

### 4. Ninety days in the log bucket

**Claim.** "The log bucket keeps them ninety days."

**Verdict: risky.** Railway buckets list "Bucket lifecycle configuration" under "Not yet
supported" (https://docs.railway.com/storage-buckets), so nothing deletes a file after ninety
days unless PenguinSlicer does. R2 implements `PutBucketLifecycleConfiguration`
(https://developers.cloudflare.com/r2/api/s3/api/).

**Smallest change.** Say what deletes files older than ninety days: a lifecycle rule on the R2
bucket.

### 5. Writing the configuration only if unchanged

**Claim.** "An edit writes the whole document on the condition that it has not changed since it
was read."

**Verdict: unconfirmed on a Railway bucket; confirmed on R2.**

- Railway's page lists Put, Get, Head, Delete, List, Copy, presigned URLs, tagging and
  multipart, and does not mention conditional writes. https://docs.railway.com/storage-buckets
- Railway buckets run on Tigris, and Tigris documents `If-Match` and `If-None-Match: "*"` on
  writes, returning 412. https://www.tigrisdata.com/docs/objects/conditionals/
- A Railway employee, Tue 2026-09-29, on exactly this: "Our documentation makes no separate
  guarantee about them", and advised against treating them as guaranteed.
  https://station.railway.com/questions/railway-buckets-consistency-and-create-d83ae29c
- R2: "The conditional headers on `PutObject` (such as `If-Match` and `If-None-Match`) are
  evaluated atomically". https://developers.cloudflare.com/r2/api/s3/api/

**Smallest change.** Either put the state bucket on R2 as well (one object store, documented
conditional writes), or add "a conditional write to a Railway bucket" to "To confirm" with a
test that two writers with the same `If-Match` get one 200 and one 412. The folder that stands
in for a bucket in phase 2 must implement the same condition.

### 6. "A disk that is emptied whenever the container restarts"

**Claim.** Used three times, once as a privacy property ("on a disk that is emptied at every
restart").

**Verdict: holds for a redeploy; unconfirmed for a restart.**

- Railway: "Every service deployment has access to 1GB of ephemeral storage on the Free plan
  and 100GB on a paid plan", and a deployment that exceeds it "can be forcefully stopped and
  redeployed". The page does not say the disk is emptied.
  https://docs.railway.com/deployments/reference
- Forum answers say a redeploy creates a new container with a fresh filesystem. A thread
  asking Railway whether a manual restart or a crash restart keeps the writable filesystem,
  opened Mon 2026-08-31, has no employee answer.
  https://station.railway.com/questions/clarification-does-manual-restart-prese-4486eb4e

**Smallest change.** Make the slice service empty the part store and the sliced-file folder
when it starts, and word the spec as "emptied by the slice service whenever it starts", so the
property does not depend on Railway. Record the 100 GB limit beside the "Disk" item in "To
confirm": exceeding it stops the container.

### 7. The custom-header CSRF defence

**Claim.** "Requests that change something must also carry a header that only the wizard's own
page can set, since the cookie alone would let another site's page act for a signed-in user."

**Verdict: sound, on conditions the spec should state.** OWASP calls a custom request header
"particularly well suited for AJAX or API endpoints": a cross-site form cannot add one, and a
cross-site script that adds one triggers a CORS preflight that the server does not approve.
https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
With `SameSite=None` there is no SameSite protection behind it, so the header check is the
only defence and each condition matters:

1. The front container sends no `Access-Control-Allow-Origin` (with credentials) for any other
   origin, on any route, and answers no preflight from one. One permissive CORS header undoes
   the defence.
2. Every route that changes anything checks the header, including the part upload (a
   multipart POST is a "simple" request a foreign form can send) and sign-out. No `GET` changes
   state. The OAuth callback is a `GET` that signs a user in, so it needs the OAuth `state`
   value checked against the browser that began the sign-in (login CSRF).
3. The progress streams cannot carry the header (`EventSource` sets none). They must be
   read-only `GET`s; the same-origin policy then keeps another site from reading them.
4. Also check `Origin` (and `Sec-Fetch-Site` where present) on changing requests. OWASP treats
   Fetch Metadata as "the primary signal" and the custom header as one layer.
5. **Framing.** The wizard must be framed by Onshape, so it cannot send
   `X-Frame-Options: DENY`. Without `Content-Security-Policy: frame-ancestors` limited to
   Onshape's origins, any site can frame the wizard and trick clicks from a signed-in user
   (clickjacking), which the header does not stop. The standalone page is the same origin and
   gets the same policy.
6. The cookie is `HttpOnly`, so page script cannot read the Onshape tokens in it.

The sentence "a header that only the wizard's own page can set" is loose: any non-browser
client can set it. The property is that another site's page, in the user's browser, cannot.

**Smallest change.** Add one paragraph to "Sign-in" with conditions 1 to 6, and reword the
sentence to "a header that another site's page cannot add".

### 8. Progress streams and the held sync through Cloudflare and Railway

**Claims.** "50 seconds ... inside the 125 seconds Cloudflare allows a request"; "Railway closes
a request after fifteen minutes, or after five without data, and Cloudflare after 125 seconds
without data"; a comment line every fifteen seconds keeps a stream open.

**Verdict: timeouts confirmed; buffering unconfirmed.**

- Cloudflare's table: Proxy Read Timeout 125 s, error 524, configurable "for Enterprise zones"
  only. https://developers.cloudflare.com/fundamentals/reference/connection-limits/
- Cloudflare defines it as "a timeout value between two successive read operations to your
  origin server", an idle limit, not a total.
  https://developers.cloudflare.com/cache/how-to/cache-rules/settings/
  The 524 page words it as "the origin did not provide an HTTP response before the default 125
  seconds", which covers the wait for the first byte.
  https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/
  A held sync answered at 50 s and a stream with a comment every 15 s pass on the Free plan
  under either reading.
- Railway: "HTTP requests can run for up to 15 minutes if data keeps transferring" and "are
  otherwise closed after 5 minutes with no data transferred."
  https://docs.railway.com/networking/public-networking/specs-and-limits
- **Buffering.** Cloudflare's default response body buffering is "Standard": "Cloudflare can
  inspect a prefix of the response body for enabled functionality". A Configuration Rule can
  set it to "None". The page does not say how `text/event-stream` is treated.
  https://developers.cloudflare.com/changelog/post/2026-01-27-body-buffering-settings/
  No Cloudflare page read here promises that server-sent events pass unbuffered. A user on
  Railway's forum (Sat 2025-07-26) found Cloudflare buffered a stream until the response
  carried `Content-Type: text/event-stream`; another (Sun 2026-08-02) had one Railway service
  whose stream arrived only at its end, never explained by Railway.
  https://station.railway.com/questions/django-streaming-responses-stopped-worki-93b58a20 ,
  https://station.railway.com/questions/edge-proxy-buffers-streaming-responses-4084b96c
- **Private network.** The 15 and 5 minute limits are on the page for public networking; no
  page says whether they apply to the front container's calls to the slice container. By
  inference they do not (those calls do not pass Railway's edge). Unconfirmed.

**Smallest change.** Add to "To confirm": "a progress stream through Cloudflare and Railway
delivers each event as it is written (measure the arrival times); if not, a Cloudflare
Configuration Rule sets response body buffering to None for the stream routes." Require
`Content-Type: text/event-stream` and no compression on the streams.

### 9. Onshape API calls made for sign-in

**Claim.** "Onshape tells the front container who the user is and which companies they belong
to", for every user, with an OAuth app registered in phase 3.

**Verdict: the calls work; their cost is not stated.**

- `GET /companies`: "Get all companies to which the specified user belongs. If no user is
  specified, will return all companies associated with the current user." Onshape's OpenAPI
  file lists no scope for it. PenguinCAM calls it in production with the scopes
  `OAuth2Read OAuth2ReadPII` (`/repos/popcornpenguins/PenguinCAM/onshape_integration.py` lines
  118 and 1867) and treats its `items` as the user's classrooms. https://cad.onshape.com/api/openapi
- `GET /users/sessioninfo`: "Returned information depends on caller's `OAuth2ReadPII` scope."
  Same file.
- **What a free or education account returns: unconfirmed.** No Onshape page says. PenguinCAM
  has a branch for "isn't a member of any classroom or company" (same file, line 1915), so an
  empty list occurs in practice, and the spec's "group of one" covers it.
- **The cost.** "Calls made with OAuth2 via private applications (any applications that are NOT
  publicly available in the Onshape App Store)" count, and "count toward the app owner's API
  limits, not the end user's." The limits are yearly: 2,500 per user on Free, Standard and EDU
  Student; 2,500 per company on EDU Educator; 5,000 per user on Professional. Past the limit,
  "requests are rejected with a 402". Calls from apps "publicly available in the Onshape App
  Store" do not count. https://onshape-public.github.io/docs/auth/limits/
  A sign-in makes two calls. Until the app is public in the App Store, every user's sign-in
  and every later Onshape call spends the app owner's yearly allowance.

**Smallest change.** Add to "Sign-in": the number of Onshape calls per sign-in (two), that
group membership is read only at sign-in, and that the app owner's yearly limit bounds
sign-ins until the app is public in the App Store. Add the limit to "To confirm". Give a group
id a prefix by kind (`company:` or `user:`) so a user's id can never equal a company's.

### 10. The Onshape tokens in a thirty-day cookie

**Claim.** "The cookie holds the user's identity, groups and Onshape tokens, and is encrypted";
thirty days; "Nothing about a session is kept on the server".

**Verdict: lifetimes confirmed; three risks.**

- An access token "can be used for the next 60 minutes". "Refresh tokens are valid for the
  lifetime of the user's grant." "Refreshing the access token also provides you with an
  updated refresh token to use in the next refresh access token request."
  https://onshape-public.github.io/docs/auth/oauth/
- **Risk: rotation with no server state.** Each refresh returns a new refresh token that must
  replace the old one in the cookie. Two requests that refresh at once, or a refresh whose
  response the browser never receives (a progress stream cannot set a cookie reliably), can
  leave the cookie with a stale refresh token. Whether Onshape rejects the older refresh token
  is not documented. Unconfirmed.
- **Risk: size.** Browsers hold about 4 KB in one cookie. Identity, a list of groups, two
  tokens, encryption overhead and base64 must fit. The length of Onshape's tokens is not
  documented. Unconfirmed.
- **Risk: terms.** Onshape's API agreement is shown on first entry to the Developer Portal and
  I could not read it. Onshape's OAuth page keeps tokens on the server in its example and
  states no rule against a cookie. Whether the terms or the App Store's rules restrict it is
  unconfirmed.
- A consequence that follows from the documented facts: groups frozen in a thirty-day cookie
  mean a user removed from an Onshape company keeps that group's printer and configuration for
  up to thirty days, and nothing on the server can end a session.

**Smallest change.** Keep the Onshape tokens out of the cookie until a feature calls Onshape
after sign-in (the Onshape source, phase 4); phases 2 and 3 need only identity and groups. Then
state how a refreshed token reaches the cookie, and read groups again more often than every
thirty days. Add the API agreement and the cookie's size to "To confirm".

### 11. What a flaw in the slice container can reach

**Claims.** The slice container "is reachable only from the front container"; "accepts requests
only from the front container"; a flaw "exposes the parts and sliced files of the last two
hours, and nothing else."

**Verdict: reachability confirmed; "nothing else" needs two qualifications.**

- "Railway services don't obtain a domain automatically"; a service is exposed only by
  generating a domain or a TCP proxy. https://docs.railway.com/networking/domains/working-with-domains
- "Private networks are isolated at the project and environment level"; "Traffic never leaves
  Railway's infrastructure and is not exposed to the public internet"; "Client-side requests
  from browsers cannot reach the private network".
  https://docs.railway.com/networking/private-networking/how-it-works
- **Qualification 1.** The private network is a mesh "between all services within an
  environment": the slice container can call the front container directly, behind Cloudflare,
  and any service later added to the environment can call the slice container. Nothing on
  Railway restricts which service calls which.
- **Qualification 2.** Outbound internet is open from every service (the outbound page
  restricts only SMTP on the cheaper plans and makes IPv6 opt-in), so a compromised slice
  container can send parts out. https://docs.railway.com/networking/outbound-networking

**Smallest change.** Word the claim as "reachable only from services in the same Railway
environment, which holds the front container and nothing else", and add: the front container
treats a request arriving over the private network like any other (no route trusts the caller's
address), and the slice container's outbound access to the internet is not blocked.

## Confirmed, with notes

### 12. Private networking: protocol, address and binding

Confirmed. Services talk over "encrypted Wireguard tunnels" at
`<service-name>.railway.internal`, plain `http://`. "New environments (created after October
16, 2025): DNS names resolve to both internal IPv4 and IPv6 addresses"; legacy environments
resolve to IPv6 only. A new project is a new environment, so a Flask server bound to `0.0.0.0`
is reachable; binding `::` serves both families and is safe in either kind of environment.
Private networking exists "only ... at runtime, not during the build phase".
https://docs.railway.com/networking/private-networking/how-it-works ,
https://docs.railway.com/networking/private-networking/library-configuration

Smallest change: none needed; optionally say the slice service binds `::`.

### 13. 8 GB per container on the cheaper plan

Confirmed by inference. Hobby allows 6 replicas, 48 GB and 48 vCPU per service, and "these are
maximum values and include replica multiplication", so 8 GB and 8 vCPU per replica. The scaling
page gives the same division for Pro (24 GB per replica). No page states "8 GB" outright.
https://docs.railway.com/pricing/plans , https://docs.railway.com/deployments/scaling

### 14. Billing by use, and the $7 to $40 estimate

Confirmed. "You are only charged for the resources you actually use": RAM $10 per GB-month,
CPU $20 per vCPU-month, egress $0.05 per GB; Hobby is $5 a month including $5 of use. Bucket
storage is $0.015 per GB-month with free operations and egress; a service's uploads to a bucket
count as service egress. https://docs.railway.com/pricing/plans ,
https://docs.railway.com/storage-buckets

### 15. Railway's limit on a request body

Confirmed as the spec states it: none is published. The page adds "Request bodies must finish
uploading within 5 minutes" and "Max 32 KB combined header size".
https://docs.railway.com/networking/public-networking/specs-and-limits
The spec's "To confirm" item stands.

### 16. Storage Buckets are S3-compatible

Confirmed: "Buckets are fully S3-compatible." Not supported: server-side encryption,
versioning, object locks, lifecycle configuration. "Buckets are currently only accessible via
public networking", and public buckets are not supported, so the log bucket is private as the
spec requires. There are no automatic backups of a bucket, which matters for the state bucket
as "the durable record". https://docs.railway.com/storage-buckets

### 17. Log retention of seven days

Confirmed for Hobby (Pro: 30 days). Also: "a logging rate limit of 500 log lines per second per
replica", excess dropped, and "Railway does not have a log drain setting", which supports the
spec's own log bucket. https://docs.railway.com/observability/logs

### 18. Redeploys and in-flight requests

Confirmed that a redeploy ends them. The old deployment gets SIGTERM and "By default, it is
given 0 seconds to gracefully shutdown before being forcefully stopped with a SIGKILL";
`RAILWAY_DEPLOYMENT_DRAINING_SECONDS` lengthens that and
`RAILWAY_DEPLOYMENT_OVERLAP_SECONDS` runs old and new together. The page does not say what
happens to open requests; with 0 seconds they are cut. Held syncs, progress streams and a
running slice job all end at a redeploy, as the spec's table already allows.
https://docs.railway.com/deployments/reference
Note for phase 3: with an overlap, two front containers briefly exist and the relay's memory is
in only one, so the overlap should stay 0.

### 19. Railway's machines are x86_64

Confirmed by an employee only (Tue 2024-12-31): "we don't have any plans to support arm64 at
this time, we are fully invested into x86 hardware." No documentation page states the
architecture. The spec's "To confirm" item on measuring Orca again stands.
https://station.railway.com/questions/supported-architectures-06e77576

### 20. Outbound internet from the front container

Confirmed by implication: the outbound page describes IPv4 as working, IPv6 as "disabled by
default", and restricts only SMTP on Free, Trial and Hobby. The front container can reach
Onshape and the buckets. https://docs.railway.com/networking/outbound-networking

### 21. Cloudflare's 100 MB request body limit

Confirmed: Free 100 MB, Pro 100 MB, Business 200 MB, Enterprise up to 5 GB.
https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-413/
A 7.5 MB part passes.

### 22. Cloudflare in front of Railway

Not a claim in the spec, but needed for "Cloudflare proxies it": with the orange cloud on,
Railway requires SSL/TLS mode "Full", and "Full (Strict) will not work as intended". Hobby
allows 2 custom domains per service.
https://docs.railway.com/networking/domains/working-with-domains

### 23. One OAuth app for the panel and the standalone page

Confirmed. An extension is added to an OAuth application ("You must first create an application
before adding an extension"), and the same application's redirect URL serves a page opened
directly. PenguinCAM does both with one app today. Onshape has no page that states it in one
sentence. https://onshape-public.github.io/docs/app-dev/extensions/ ,
https://onshape-public.github.io/docs/auth/oauth/
Note: an Enterprise user signs in at the enterprise's own address and Onshape documents a
`company_id` parameter for it; behaviour for such users is unconfirmed.

### 24. "Registering the app for sign-in does not need the panel work of phase 4"

Confirmed: the application is created first and extensions are added later (same extensions
page).

### 25. R2 as the fallback for the log bucket

Confirmed: see item 3. R2 also has lifecycle rules (item 4) and atomic conditional writes
(item 5).

## Not checked

- Whether Cloudflare's bot protections on the Free plan challenge a daemon's requests (a
  non-browser client holding a request for 50 seconds). No page was read for it.
- Chrome's quota in an Incognito window.
- Onshape's API agreement and App Store rules (item 10).
