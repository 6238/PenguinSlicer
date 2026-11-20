# Owner's feedback on the session summary (working notes)

Temporary file. It collects the owner's feedback on
[the session summary](2026-11-20-penguin-slicer-session-summary.md), given in pieces from
Fri 2026-11-20. Nothing is to be rewritten until the owner says the review is finished.
Delete this file once the changes are made.

## General

- **No running list of decisions.** Once a decision is made, the documents are rewritten
  to state the result. The documents the owner reviews describe the state of affairs at
  the time of review; they do not accumulate decisions and their answers.

## Terms

- **"copy"** is confusing when a part is on the plate once. Owner suggests "placement" or
  another word. Applies to the mockup and the documents.
- **"HTTP face"** is confusing. Owner suggests "interface", perhaps "slice service
  interface".
- **Auto-orient, Arrange** are buttons that may change; remove them from the terms table.
- **"plate job"** does not sound like work being done; it is a configuration. Owner
  suggests "plate configuration", with "slice job" kept for the work. The owner still
  finds the pair a little confusing.

## Decisions

- **D1.** Repository `PenguinSlicer` in the `6238` organization, like `6238/PenguinCAM`,
  using the owner's GitHub account `chondl`.
- **D2.** The description is hard to follow. Leave it out as a decision; keep it as a test
  for the session at the real printer, and understand the real problems then.
- **D3.** Yes, fix the remaining small open items now.
- **D4.** Read Orca's debug log; no patch to Orca. The Orca version is pinned, so the log
  format changes only at an upgrade. The upgrade process gets a scripted test that
  verifies the debug-log reading still works; if it fails, the reading is fixed then.
- **D5.** Stay on Orca 2.4.2. Record the 2.5.x upgrade as known future work.
- **D6.** Daemon telemetry is part of the initial work. A protocol for the daemon to send
  messages back, recorded on the server. It helps development now and is ported when the
  daemon moves to Rust or Go. Why it matters: the daemon runs on a wide variety of
  hardware, and the problems are hard to foresee: network misconfiguration, hardware
  platform capabilities, issues with the UI, the host computer going to sleep, the host
  being overloaded, the daemon timing out because its host runs slowly.
- **D7.** Move Penguin Slicer's specs and plans into the Penguin Slicer repository.
- **D8.** The proposed reference plates are good enough, but the limit of 25 copies is too
  low: as many as 100 small parts in a 10 by 10 grid. Raise the limit, and use a small
  spacer for a 3/8 inch hex shaft, 1/8 inch thick, as the sample for that plate.
- **D9.** Do not worry about the printer's certificate.
- **D10.** Remove the Raspberry Pi installer: never tested, probably never needed.
- **D11.** Not a concern: the workspace `CLAUDE.md` is not generated from anywhere on the
  Mac, as far as the owner knows.

## The owner's answers to four questions

1. "copy" becomes **"instance"**.
2. D1: `6238/PenguinSlicer` is public. Done Fri 2026-11-20: created at
   https://github.com/6238/PenguinSlicer, branch `build/ports-and-hardening` pushed.
   `main` pushed and made the default branch; the build branch merged into it by
   pull request 1 (merge commit `1997432`). From here every change goes through a pull
   request that the agent opens and merges; the rule is in the workspace `CLAUDE.md`.
3. D7: everything moves to the Penguin Slicer repository: the plan, the mockup, the
   wizard research and the orchestration records.
4. D3: hold the fixes until the review is finished.

## Open items

- **S2** is a real design flaw, not an optional low item: an HTTP header must not carry
  10 kB or more. The owner left the design of the HTTP interface to the agent, with no
  need to check back. Chosen: a route `GET /slices/<job>/summary` returns the summary as
  a JSON body, with the file route's error reports for a slice job that failed, was
  cancelled or is not finished; the file route returns only the file and the
  `X-Slice-Summary` header is removed. Built with the other fixes after the review.

- **S4, and the number of interfaces.** The owner's concern: a component should have one
  interface used in all contexts; the slice service appears to have a command line, an
  HTTP interface and direct access to inner functions. Found in the code: three
  documented ways in (the Python function `slice_plate_job`, the command `slice` that
  wraps it, the HTTP interface that also wraps it), plus the internal
  `slicer.slice_plate` that S4 is about. S1 and S10 exist only because the ways in
  differ. **Owner's answer:** the HTTP interface is the slice service's one interface. In
  time there may be several instances of the slice service, possibly on a machine other
  than the web application's, so HTTP is right. The Python function and the internal
  function are not interfaces of the component. **Remove the `slice` command:** there is
  no requirement that a person can slice by hand; for testing and development an agent
  writes throwaway scripts against the HTTP interface. The `serve` command stays, as the
  way the service is started.
- **One interface per component is the default, not a hard rule.** The wizard may exist
  both inside Onshape and as a page reached directly from a browser; the Onshape source
  may likewise be hosted in Onshape and separately. Write it in the repository's notes
  for agents as a default.
- **Consequences to carry into the fixes:** S1 and S10 go away with the `slice` command;
  ruling R3 loses its command-line half; S4 is no longer about a supported way in; S8
  (one process per service) matters more once several instances are planned.

## Scope the owner gave before leaving (Fri 2026-11-20)

Go ahead: record the decisions, update the relevant documents, the plan and the session
summary, and make the code fixes discussed. The owner has reviewed only the terms,
section 2.1, section 3 and section 4.1; the rest of section 4 and the mockup are still to
review, and no other change may start until that review is finished.

The owner writes the name as **PenguinSlicer**, one word.
