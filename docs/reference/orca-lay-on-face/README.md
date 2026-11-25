# Orca Slicer's Lay on face: the reference for laying an instance down

[orca-lay-on-face.png](orca-lay-on-face.png), sent by the owner on Sat 2026-11-21, shows
Orca Slicer's "Lay on face" tool on an L-shaped part. Orca builds a closed convex
polyhedron around the object (its convex hull), finds the hull's flat faces, and draws
each as a translucent rounded patch (the ovals). A click on a patch lays the object on
that face. Some faces, such as the diagonal one across the inside of the L, are faces of
the hull, not of the part.

The owner's direction:

- The Layout step's way of laying an instance on a face should copy what Orca does. The
  mockup shows it from version 5.
- A round part, such as a pulley, is not a box. The user should be offered the faces
  that make sense (a pulley's end faces), not a patch on each thin facet round its rim.
  The mockup need not solve this fully; the real wizard must.
- Orca Slicer is AGPL and PenguinSlicer is MIT: copy the method, never the code.
