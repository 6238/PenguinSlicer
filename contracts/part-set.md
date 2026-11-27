# Part set

A **part set** is the parts to print, as they are handed to the
[wizard](../wizard/README.md#the-parts-step): each part's name, how many of it to print,
its units and its file. Two things make part sets:

- **a file upload,** in phase 2: the wizard itself makes a part set from the STL files the
  user drops on, or chooses in, the upload area of the Parts step;
- **the Onshape integration,** from phase 4: a part the user clicks in Onshape is exported
  and handed to the wizard as a part set, with the Onshape document's units.

The wizard adds each part of a part set to the plate, uploads it once to be checked (the
part, with its units, passes through the front server to the slice service's part store)
and keeps it in the browser's storage. From there on the part is named by the SHA-256 hash
of its bytes, with its units ([the plate configuration](plate-configuration.md#a-part-in-phase-2)).
The part set itself is not kept: it is the handing over, not a record.

How the Onshape integration divides between the browser and the server, and so whether its
part sets reach the wizard inside the browser or through the front server, is settled by
phase 4's design ([the plan](../docs/plans/penguin-slicer-plan.md)). This contract holds in
both cases.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `format` | integer | yes | The number of the part set's format. This file describes format `1`. |
| `source` | string | yes | What made the part set: `"file"` for a file upload, `"onshape"` for the Onshape integration. |
| `parts` | array | yes | The parts, at least one (see Part), in the order they are to appear in the Parts step's list. |

### Part

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The part's name, as the Parts step shows it and as it names the part's instances and the sliced file. 1 to 200 characters (the plate configuration's limit on a part's name). For a file upload, the file's name less a final `.stl` in any case (`Gusset Plate.STL` gives `Gusset Plate`), cut to 200 characters, and `part` when nothing is left; for a part from Onshape, the part's name in Onshape. |
| `quantity` | integer | yes | How many instances of the part to print, 1 to 150 (the plate's limit on instances). A file upload gives 1 for each file. |
| `units` | string | yes | The units the part's coordinates are in: `"in"` for inches, `"mm"` for millimetres. For a file upload, the setting of the switch beside the upload area when the file was added, which starts at the configuration's `upload_units` ([the configuration](configuration.md)); for a part from Onshape, the units of the Part Studio or Assembly it was picked in. |
| `stl_bytes` | bytes | yes | The part's file, a binary STL, exactly as it was read or exported. |

Inside the browser a part set is an object with these fields and `stl_bytes` holds the
bytes themselves (an `ArrayBuffer`). Where a part set crosses a network as JSON, which
phase 4's design may need, `stl_bytes` is the bytes in base64 (RFC 4648, with padding, no
line breaks); [examples/part-set.json](examples/part-set.json) is that form.

## Rules

- **Binary STL only.** A part's bytes are a binary STL file: an 80-byte header, a count of
  triangles, and 50 bytes for each triangle. The Onshape integration exports binary STL
  and nothing else. A file upload puts a file's bytes into the part set unchanged, whatever
  they are; the slice service's checks on arrival refuse a text STL, or a file that is not
  an STL at all, with their own sentences, and the part is not added
  ([A part that cannot be used](../wizard/README.md#a-part-that-cannot-be-used)).
- **Never changed.** Nothing that makes, passes or keeps a part set changes a part's bytes:
  not to scale it, not to move its origin, not to mend it. Its units travel beside it as a
  label, and only the slice service applies the scale
  ([Units](../slice/README.md#units)). The hash by which the part is known is therefore the
  hash of the bytes the user chose.
- **At most 7.5 MB a part.** A part's bytes are at most 7,500,084 bytes, a binary STL of
  150,000 triangles (the plate configuration's
  [limits](plate-configuration.md#limits)). The wizard checks the size before uploading
  and does not add a larger part; whether the Onshape integration exports such a part again
  more coarsely by itself is for phase 4's design.
- **One part, one row.** The wizard knows a part by its hash and its units together. A part
  of a part set whose hash and units are those of a part already on the plate raises that
  part's quantity by the part set's `quantity` and adds no row; the same bytes under other
  units are another part. This is what makes four clicks on one part in Onshape a part
  with quantity 4.
- **At most 25 different parts on a plate.** A part set's part that would be the plate's
  twenty-sixth is not added, and the wizard says so
  ([The limits on a plate](../wizard/README.md#the-limits-on-a-plate)).

## Example

See [examples/part-set.json](examples/part-set.json): a file upload of one part, the
example [spacer](examples/parts/spacer.stl), read in millimetres.
