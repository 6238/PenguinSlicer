# Lay on face: the faces on the hull, as Orca Slicer finds them

Fri 2026-11-20, Pacific time. What Orca Slicer's "Lay on face" tool does, in our own words, and what the
wizard mockup (version 5, [its decisions](../mockups/print-wizard/DECISIONS.md)) does
with it. Orca Slicer is AGPL and PenguinSlicer is MIT: this note describes the method; the
mockup's code (`docs/mockups/print-wizard/js/hullfaces.js`) was written from this note, and
no Orca code, comment or constant name is in the repository.

**Source read:** OrcaSlicer at tag `v2.4.2`,
`src/slic3r/GUI/Gizmos/GLGizmoFlatten.cpp` (408 lines), with
`src/slic3r/GUI/Gizmos/GLGizmoBase.cpp` (its colours) and `src/slic3r/GUI/Selection.cpp`
(the turn). Line numbers below are in those files at that tag.

## Short answer

Orca wraps the object in its convex hull, joins hull triangles that point the same way into
flat faces, drops faces under 5 mm² or with a corner sharper than 1 degree, keeps the 254
largest, and draws each as a shrunken, rounded, translucent patch; a click turns the object
so that face points straight down. It has no test of whether the object would tip over.
On round parts those filters keep every facet of the round side (96 on the mockup's
pulley), so the mockup adds one rule: **a face is left out when a neighbouring hull face
bends away from it by less than 20 degrees and is at least half its size.** On the seven
mock parts it leaves the pulley and the spacer their two end faces, drops the 40 facets
of the rib's curved edge, and changes nothing on the other four parts. Finding a part's
faces takes 0.2 to 10 ms in the browser.

## How Orca finds the faces

1. **The hull.** Each model part of the object contributes its own convex hull; these
   are merged and the convex hull of the result is taken (`update_planes`, lines 152-163).
   Work is done in the object's own coordinates; the instance's scale and mirror are
   applied when measuring (lines 166, 213-215).
2. **Flat faces from hull triangles.** Starting from a triangle not yet used, Orca spreads
   across shared edges to neighbouring hull triangles whose normal matches **the starting
   triangle's** normal within 0.001 in each component (about 0.06 degrees), and collects
   their corners into one face (lines 173-210). Comparing with the starting triangle, not
   with the neighbour, stops a gently curved strip from creeping into one face.
3. **A quick early drop:** a face that is a single triangle with any side under 1 mm is
   removed at once (lines 217-222).
4. **Measuring each face.** Its corners are turned into the plane of the face and replaced
   by their 2D convex outline (lines 229-250); the area is the shoelace area of that
   outline (lines 252-257).

## How Orca filters them

| Filter | Value | Where |
|---|---|---|
| Lone triangle with a short side | any side under 1 mm | lines 170, 217-222 |
| Minimum area | 5 mm² (in world units, after scaling) | lines 169, 260-261 |
| Sliver corner | any corner of the outline sharper than 1 degree (the comment says it was 10 degrees and caused bugs) | lines 171, 263-276 |
| How many are kept | the 254 largest by area; Orca's own explanation is a limit of its picking pass | lines 338-340 |
| Stability (would it tip over?) | **none** | nowhere in the file |

The wizard research's figures ([its section on Orca's tools](2026-11-19-wizard-layout-and-advanced-mode-research.md))
are right: at least 5 mm², up to 254, in lines 152-340. One small correction: the research
gives the tool's key as F; this file sets its shortcut key to `WXK_CONTROL_F` (line 57),
which is how wxWidgets names Ctrl+F.

## How Orca draws and picks them

- **The patch:** each outline is drawn in by 10% toward the average of its corners
  (lines 284-288), its corners are then rounded by ten passes that pull each corner
  toward points on its two sides (lines 290-327), and it is raised 0.1 mm off the face so
  it does not flicker against it (lines 330-332). It is drawn as a fan of triangles from
  one corner (lines 354-366). Hence the owner's "ovals": the rounding is strong.
- **Colours:** near-white (0.96, 0.93, 0.93) at 50% opacity; white at 75% under the
  pointer (`GLGizmoBase.cpp` lines 41-42; a colour theme can replace them, lines 59-60),
  drawn with blending on (`GLGizmoFlatten.cpp` lines 93-109).
- **Drawn over the object:** Orca clears the depth buffer before drawing the patches
  (line 91), so every patch shows through the object, including those on its far side,
  and the patches are picked before the scene (line 120).
- **Picking:** each patch gets its own ray caster (lines 117-133); the hovered one is
  the one drawn lighter.
- **Clicking** a hovered patch (lines 22-40) turns the instance by the shortest rotation
  that points that face's normal straight down (`Selection.cpp` lines 1435-1463); the
  object's other instances follow, keeping their own turn about the vertical.
- **Only one whole instance** can use the tool (lines 75-80). The faces are worked out
  again when the object, its parts, its scale or mirroring change (lines 384-405), not when
  it is turned, since they are kept in the object's own coordinates and turn with it.

## What the filters offer on the mockup's parts

Counted in the browser on the mockup's seven parts (their own mock meshes):

| Part | Hull faces | Orca's filters offer | Of which round-side facets | The mockup offers |
|---|---|---|---|---|
| L Bracket | 7 | 7 | 0 | 7 |
| HTD Pulley 24T | 98 | 98 | 96 (25.9 mm², 1.4 mm wide, 3.75 degrees apart) | 2 (the ends) |
| Camera Mount | 7 | 7 | 0 | 7 |
| Hex Bore Spacer 1in | 98 | 98 | 96 (18.3 mm², 0.7 mm wide, 3.75 degrees apart) | 2 (the ends) |
| Gusset Plate | 7 | 7 | 0 | 7 |
| Shooter Hood Rib | 45 | 45 | 40 (75.4 mm², 8 mm wide, 1.8 degrees apart) | 5 (two sides, two ends, the face across its inner curve) |
| 1/2in Hex Shaft | 8 | 8 | 0 | 8 |

So Orca's filters alone offer a patch on every sliver of a round side: all are well over
5 mm² and their corners are right angles. Nothing on these parts reaches 254.

## The rule for round parts

**A face is left out when one of its neighbours on the hull (sharing an edge) bends away
from it by less than 20 degrees and is at least half its size.** That is the mark of a
facet of a round side: its neighbours are like it and nearly in line with it. A flat face
beside a shallow chamfer or a fillet's facet keeps its patch (that neighbour is smaller);
the shallow facet loses its own when it bends less than 20 degrees from the larger flat
face. A chamfer at 45 degrees bends too far to be caught and keeps its patch, as in Orca.

Two simpler rules were tried on the numbers above and fail:

- **A minimum share of the largest face's area:** the rib's ends are 1.1% of its sides,
  less than the spacer's slivers (4.8% of its ends); the hex shaft's ends are 9.5% of
  its flats. No one threshold drops the slivers and keeps the ends.
- **A minimum width:** the rib's curved-edge facets are 8 mm wide, as wide as its ends,
  its inner-curve face and wider than the Camera Mount's 4 mm faces.

### What the real wizard would need beyond it

- **Irregular meshes.** An Onshape export does not cut a round side into equal facets.
  A narrow facet between two wide ones is dropped, but the wide ones keep their patches
  because their neighbours are under half their size. The real wizard should treat a
  whole run of facets joined by shallow bends as one round side and drop the run.
- **Coarse round sides.** A cylinder cut into fewer than 18 facets bends more than 20
  degrees between them and is not caught; the hull of a part with a hex or octagon
  outline is rightly kept, so the angle cannot simply rise.
- **A stability test,** which Orca lacks: the mockup still offers faces the part would
  fall off. By hand arithmetic, the L Bracket's base end is 5 mm tall while the bracket's
  centre of mass is about 10 mm up. The mockup's auto-orient already tests this (centre of
  mass over the contact area) and could share it.
- **Several bodies in one part,** as Orca merges its model parts' hulls first.

## What the mockup does

Written afresh in `docs/mockups/print-wizard/js/hullfaces.js` and drawn by
`docs/mockups/print-wizard/js/layout3d.js`:

- **Hull:** an incremental hull of the part's distinct corners (rounded to 0.001 mm): a
  tetrahedron of far-apart corners, then each other corner in a fixed shuffled order; a
  corner more than 0.001 mm outside replaces the triangles it sees with a fan to the edge
  of what it sees.
- **Faces:** hull triangles joined across edges while their normals are within 0.25
  degrees of the first triangle's (looser than Orca's 0.06 degrees to absorb the mock
  meshes' single-precision rounding; no round side here is that fine).
- **Filters:** Orca's four, with Orca's values; then the rule for round parts.
- **Patch:** the outline drawn in 10% toward its centre of area, then rounded by four
  passes of corner cutting (each side replaced by the points a quarter and three quarters
  along it), raised 0.1 mm. Drawn in PenguinCAM's accent blue at 22% opacity, 55% under
  the pointer. Unlike Orca, a patch is hidden behind the part, the face the instance lies
  on has no patch, a drag that starts on a patch moves the instance, and the rotation
  handle moves round the selection to a side where it covers no patch in sight (hidden if
  no side is free), so a click on a patch always lays the instance down.
- **Click:** the instance turns so the face's normal points down, then the Layout step's
  usual follow-up (a free spot if needed, one sentence saying how tall it now stands).

## Time to find the faces

Measured in the browser (Chrome under a virtual display, software WebGL, on an aarch64
Linux machine), the first time each part's faces were asked for after a page load. The
second load asked in the reverse order; the first part asked for on a load also pays for
the browser compiling the code.

| Part | Corners | Hull triangles | Load 1 (ms) | Load 2, reverse order (ms) |
|---|---|---|---|---|
| L Bracket | 302 | 64 | 2.2 | 0.4 |
| HTD Pulley 24T | 792 | 602 | 9.5 | 5.3 |
| Camera Mount | 608 | 80 | 1.1 | 0.8 |
| Hex Bore Spacer 1in | 204 | 380 | 1.9 | 2.0 |
| Gusset Plate | 1,744 | 140 | 2.8 | 3.2 |
| Shooter Hood Rib | 548 | 192 | 1.5 | 3.1 |
| 1/2in Hex Shaft | 12 | 20 | 0.2 | 1.0 |

The hull's cost grows with corners times hull triangles; an exported team part with tens
of thousands of corners would need a faster hull (one that keeps, for each triangle, the
corners outside it) or a Web Worker.
