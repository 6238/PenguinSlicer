# Real parts of the Popcorn Penguins' robot

Eight parts of the robot of the Popcorn Penguins (FRC Team 6238), exported from Onshape as
binary STL. The team printed every one of them and uses them on the robot, so the slice
service must accept, place and slice each of them: a refusal, an untrue warning or a failed
slice of one is a defect in the slice service, not in the part. The tests that use them
are `tests/test_frc_parts.py` (the fast suite) and `tests_orca/test_frc_parts.py` (the
real Orca); the figures measured from them are in `tests/frc_parts.py` and in the slice
service's detailed guide, [Plate limits](../../../README-details.md#plate-limits).

| File | Original file name | Triangles | Size (mm) |
|---|---|---|---|
| `clamp-plate-inner.stl` | Clamp Plate Inner.stl | 8,756 | 4.762 x 50.8 x 50.8 |
| `elevator-block-bottom-inner.stl` | Elevator Block Bottom Inner.stl | 39,054 | 88.9 x 63.5 x 82.55 |
| `elevator-block-carriage.stl` | Elevator Block Carriage.stl | 23,580 | 88.9 x 31.75 x 57.15 |
| `elevator-block-top.stl` | Elevator Block Top.stl | 34,998 | 88.9 x 31.75 x 82.55 |
| `elevator-top-inner.stl` | Elevator Top Inner.stl | 19,392 | 50.8 x 25.4 x 57.15 |
| `inner-spacer.stl` | Inner Spacer.stl | 2,908 | 1.262 x 50.8 x 50.8 |
| `outer-clamp.stl` | Outer Clamp.stl | 8,724 | 4.762 x 50.8 x 50.8 |
| `pulley-v3.stl` | Pulley v3.stl | 4,608 | 17.78 x 19.05 x 19.05 |

Every file is a closed surface of one piece, wound outwards. The files are byte for byte
the team's own; only the names were changed, to lower case with hyphens.

## Licence

These parts are offered under the MIT licence, the licence of this repository:

```
MIT License

Copyright (c) 2026 Popcorn Penguins, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
