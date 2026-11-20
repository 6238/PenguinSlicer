# Ledger of the review-feedback run

The coordinator's record of the run that applies the owner's feedback of Fri 2026-11-20
on the session summary. All times Pacific, read from the clock. The feedback itself is in
[the feedback notes](../../handoffs/2026-11-20-session-summary-feedback.md) until the
run ends; the briefs are in [briefs/](briefs/standing-rules.md) and each agent's result
in `results/`.

## Scope given by the owner

Reviewed so far: the terms, the decisions (section 2.1), section 3 and section 4.1 of the
summary. Allowed now: record those decisions in the documents, update the plan and the
summary, and make the code fixes discussed. Not allowed until the review is finished:
any other change. The owner still has to review section 2.2 onward, section 4.2 and the
mockup.

## Rulings by the coordinator

- **Daemon telemetry is not built in this run.** The owner made it part of the initial
  work; it is new behaviour and gets its own design first, so it is recorded in the plan
  and held with the other new work.
- **The printer delivery fixes P3 to P9 are built now**, although section 4.2 is not yet
  reviewed, because the owner's answer on the small open items named them.
- **The mockup changes terms only.** Nothing else in it is touched before the owner
  reviews it.
- **The old records under `docs/orchestration/penguin-slicer/` keep the old terms.** They
  are dated records of the first build.
- **The spacer's outside shape** is assumed round, 5/8 inch across.
- **The local folder stays `penguin-slicer`** although the repository is `PenguinSlicer`:
  renaming it under running agents would break their environments.

- **Orca's reason for the thin, tall needle is not in its debug log** (found by the slice
  builder in Orca 2.4.2's source: the reason is thrown, collected and lost). The
  debug-log reading is built and finds "floating regions" for another part; the needle
  keeps the general sentence. This goes back to the owner as a fact, since only a patch
  to Orca would surface that reason and the owner ruled out patches.

- **The whole-plate triangle cap the slice builder added is removed** unless a
  measurement justifies it: the reviewer found it rests on none and never decided a
  measured plate. The memory watchdog protects the machine.
- **The debug-log sentence must never blame a part that only warned** for another
  part's failure; where the log cannot tell, the error report says less.

- **A running slice service is a "slice service process", never an "instance".** The
  second slice review found "instance" used both for a placement of a part and for a
  running slice service (the coordinator's own wording in the brief). Also: a plate
  configuration is never "queued"; a student is told to print the rest "on a second
  plate", not "in a second job".

## Events

| Time | Event |
|---|---|
| Fri 11-20, morning | `6238/PenguinSlicer` created, public. Pull request 1 merged the build branch into `main`. |
| Fri 11-20 09:31 (GitHub's time; first written here as 09:15 by guess) | Pull request 2 merged: the plan, research, mockup, old orchestration records and summary moved into `docs/`. The notes repository no longer holds them. |
| Fri 11-20 09:32 | Dispatched three Opus builders on branch `work/review-feedback`: slice service, printer delivery, mockup terms. |
| Fri 11-20 10:05 | Delivery builder returned DONE_WITH_CONCERNS ([result](results/delivery.md)); review 1 dispatched. |
| Fri 11-20 10:10 | Slice builder returned DONE_WITH_CONCERNS ([result](results/slice.md)): `MAX_INSTANCES` 150; the needle's reason is not in Orca's debug log. Review 1 dispatched. |
| Fri 11-20 10:18 | [Delivery review 1](results/delivery-review-1.md): FIX, 2 medium and 3 low. Fix round 1 dispatched. |
| Fri 11-20 10:25 | [Slice review 1](results/slice-review-1.md): FIX, 1 medium and 3 low. Fix round 1 dispatched. Times in these four rows are approximate, taken from the status ticks. |
| Fri 11-20 10:45 to 11:05 | Delivery review 2: FIX, 4 low; fix 2 returned DONE. Slice review 2: FIX, 1 medium and 2 low; fix 2 returned DONE. Third reviews of both dispatched on Fable. |
| Fri 11-20 about 11:20 | Both third reviews stopped on the Fable usage limit. |
| Fri 11-20 11:46 | The owner said to use Opus wherever Fable was planned. Both third reviews dispatched again on Opus, and the document writer dispatched in parallel, writing from the latest results, so the owner gets the rewritten summary sooner. The documents moved in pull request 2, so the old viewer addresses under `PenguinCAM-notes/` give 404; the owner was given the new ones. |
| Fri 11-20 11:50 | The owner: stay on Opus until the Fable usage resets next week; back in about 2 hours (about 13:50), and wants the rewritten summary ready by then. |
| Fri 11-20 about 12:00 | [Delivery review 3](results/delivery-review-3.md): FIX, 2 low; the reviewer judges the change fit to merge. Fix 3 dispatched for both, since each is a few lines. Ruling: the daemon's computer has one name, "the daemon's computer", defined once (the coordinator's earlier two-name ruling broke the one-name rule). After fix 3 the change merges on the suites' evidence, with no fourth review. |
| Fri 11-20 about 12:10 | Document writer returned DONE_WITH_CONCERNS ([result](results/documents.md)). The coordinator corrected its section 6 claim that the workspace `CLAUDE.md` is out of date (it was read before the coordinator's edit), and sent the delivery guide's "owner's choice" wording to fix round 3. Document review 1 dispatched on Opus; it corrects as well as reviews. |
| Fri 11-20 about 12:15 | [Slice review 3](results/slice-review-3.md): FIX, 2 low; the reviewer judges the change fit to merge. Fix 3 dispatched (a real-Orca test of an interleaved plate, true memory figures). After fix 3 the change merges on the suites' evidence, with no fourth review. |
| Fri 11-20 about 12:25 | Delivery fix 3 returned DONE ([result](results/delivery-fix-3.md)), including the guide's wording on the timed rule. The coordinator ran `make -C delivery test` once: 1,123 passed in 5.8 s on one worker; its 12 warnings are a deprecation in the printer library's own code (`paho` using `ssl.PROTOCOL_TLS`), not ours. Delivery's tests read `contracts/`, whose renames belong to the slice change, so the slice service merges first and printer delivery second. |
| Fri 11-20 about 12:30 | Document review 1 returned: both documents corrected ([review](results/documents-review-1.md)). Slice fix 3 returned DONE ([result](results/slice-fix-3.md)): the interleaved-plate test, a cap of two malloc arenas, and a timer race in the Orca runner found in the repeat runs. |
| Fri 11-20 about 12:35 | The coordinator reran `make -C slice test` (925 passed in 6.3 s) and merged pull request 4 (slice service, `contracts/`, notes for agents), then pull request 5 (printer delivery). |
| Fri 11-20 12:40 | The coordinator brought the summary and the plan up to the merges and the last fix round, and merged them with this run's records as pull request 6. The feedback notes stay until the owner's review ends. |
| Fri 11-20 09:45 | Mockup builder returned DONE: a plain swap of terms (440 lines changed, 440 replaced), walked in a browser with no console errors; three sentences reworded, listed in [its result](results/mockup.md). Not sent to a reviewer: terms only, in a throwaway mockup. Merged as pull request 3. Note for the owner's mockup review: Onshape's own word "Instances" appears in the mockup's Assembly context, beside the new term. |
