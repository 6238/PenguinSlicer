# Error report

The one shape in which every component reports a failure. A failure that reaches a caller
in any other shape (a bare exception, an exit code, a log line only) is a bug.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `code` | string | yes | A stable name for this failure, `component.what`, for example `slice.empty_layers`. Tests and support refer to it. It never changes once released. |
| `message` | string | yes | What happened, in one sentence a user understands. No codes, no jargon. |
| `where` | object | no | What the failure is about, when known. Any of `part` (name), `instance` (name), `other_instance` (the second instance's name, for a failure about two instances, such as two too close together), `height_mm`, `stage`, `missing_parts` (from phase 2, on a plate configuration naming parts the part store does not hold: one object for each missing part, as the plate configuration's contract defines it). |
| `remedy` | string | yes | What to do next, in one sentence. |
| `action` | string | no | The name of the single action that fixes it, when one exists, for example `enable_supports`. A user interface may offer it as a button. |
| `retryable` | boolean | yes | Whether the same request may succeed if sent again unchanged. |
| `detail` | string | yes | The underlying evidence for the server log: the tool's own words, the exit code, the printer's status. Never shown to a user. May be empty only when there is truly none. |
| `orca_sentence` | string | no | From phase 2: Orca Slicer's own sentence about the failure, exactly as Orca wrote it, as a quotation a user may read ("Object can't be printed for empty layer between 9.9 and 11.34."). Present on `slice.empty_layers` and `slice.empty_layers_with_supports` only, the two failures about a gap with nothing under it, and on those only when Orca wrote such a sentence. At most 300 characters. |

The missing parts of `missing_parts` are defined under
[Parts missing from the part store](plate-configuration.md#parts-missing-from-the-part-store).

## Actions

The names an error report's `action` may carry, and what a user interface does with each. An
action's name is never renamed once released; a new one is added here in the commit that
makes a component send it. A user interface that does not know an action offers no button for
it and shows the report as it would without one.

| Action | Sent by | Means | What the wizard does |
|---|---|---|---|
| `enable_supports` | The slice service | Turning supports on would fix it | Offers **Turn on Supports and slice again** |
| `refresh_parts` | The slice service | The parts must be sent again | On `slice.part_missing` with `missing_parts`, uploads the listed parts again and submits again, showing nothing; on any other code it offers no button of its own |
| `arrange` | The slice service | Moving the instances apart, or onto the plate, would fix it | No button of its own: its Back to Layout, where Arrange is |
| `choose_orientation` | The slice service | Laying the part another way would fix it | No button of its own: its Back to Layout |
| `choose_profiles` | The slice service | Choosing other profiles or settings would fix it | No button of its own: its Back to Settings |
| `lower_quantities` | The slice service | Fewer instances on the plate would fix it | No button of its own: its buttons for the code, below |
| `slice_again` | Printer delivery, from phase 5 | The plate must be sliced again before it can be sent | Offers **Slice again** |

## Codes a user interface acts on

A user interface shows any code's `message` and `remedy`, and never acts on a code it does
not know beyond showing it. The wizard chooses its buttons, and whether it submits again by
itself, by these codes, so each is never renamed once released
([When a slice fails](../wizard/README-details.md#when-a-slice-fails)):

| Code | What the wizard does |
|---|---|
| `slice.part_missing` | With `where.missing_parts`: uploads those parts and submits again, showing nothing. Without: a fault of the page, shown as a failure |
| `slice.busy` | An amber message with Slice again; never submits again by itself |
| `slice.stopping` | Shows the slice as waiting while the slicer restarts and submits again by itself, for up to 300 seconds |
| `slice.empty_layers` | Turn on Supports and slice again; Back to Layout; Orca's sentence under Details |
| `slice.empty_layers_with_supports` | Back to Parts; Orca's sentence under Details |
| `slice.timeout` | Slice again; Back to Parts |
| `slice.orca_failed` | Slice again; Back to Layout |
| `slice.rests_on_an_edge` | Back to Layout, as its action `choose_orientation` asks, and no Slice again, since the same plate would fail the same way. The wizard never offers a face on which a part rests on no face of its own, so this comes from a plate laid out by another page version |
| `slice.out_of_memory`, `slice.output_too_large` | Back to Parts, and no Slice again, since the same plate would fail the same way |
| `slice.placement_off_plate`, `slice.placement_too_tall`, `slice.placement_too_close`, `slice.orca_too_close`, `slice.crosses_edge`, `slice.nothing_on_plate`, `slice.left_off_plate`, `slice.too_many_instances`, `slice.too_many_parts`, `slice.part_too_large`, `slice.bad_plate_configuration` | Back to Layout |
| `slice.unknown_printer`, `slice.profiles_not_offered`, `slice.bad_overrides`, `slice.profile_unreadable` | Back to Settings |
| `slice.no_layers`, `slice.print_empty` | Back to Parts |
| `front.sliced_file_too_large` | As `slice.output_too_large` |

## Rules

- `message` and `remedy` are complete sentences and never blame the user.
- `remedy` never proposes an action that cannot help.
- `detail` is captured before any cleanup removes its source.
- No field ever holds a secret: no token, access code or pairing code.
- **Orca's words reach a user in one place only.** `detail` is never shown to a user; a
  user interface shows `message`, `remedy` and the button for `action`. The one exception
  is `orca_sentence`: on the two failures that carry it, a user interface may show it
  under the folded Details of the failure, marked as Orca's ("Orca Slicer: Object can't be
  printed for empty layer between 9.9 and 11.34."), as text, and nowhere else
  ([Orca's own sentence under Details](../wizard/README.md#orcas-own-sentence-under-details)).
  No other field and no other code carries words of Orca's for a user. The slice service's
  check against the real Orca pins the wording of that sentence, so a new Orca version that
  changes it is noticed before any user sees the change.
- Every `code` a component can produce is listed in that component's guide, and each has a
  test that produces it on purpose; each of the two codes that carry `orca_sentence` has a
  test that it carries it, and the other codes a test that they do not.

## Examples

See [examples/error-report.json](examples/error-report.json), as built;
[examples/error-report-orca-sentence.json](examples/error-report-orca-sentence.json), the
same failure as phase 2 reports it, with Orca's own sentence; and
[examples/error-report-parts-missing.json](examples/error-report-parts-missing.json), a
plate configuration naming parts the part store no longer holds; and, from phase 2, the two
refusals for size that the front server makes itself with the slice service's words,
[examples/error-report-part-over-size.json](examples/error-report-part-over-size.json) and
[examples/error-report-plate-configuration-over-size.json](examples/error-report-plate-configuration-over-size.json):
the slice service's suite and the front server's each assert that their answer equals the
file. [examples/error-report-rests-on-an-edge.json](examples/error-report-rests-on-an-edge.json)
is the slice service's answer when the real Orca refuses the bracket laid on the face of its
hull across the L's open corner; the slice service's real-Orca suite asserts that its report
equals the file but for Orca's own lines of the detail, and its fast suite that every field but
the instance's name and the detail is what its code gives.
