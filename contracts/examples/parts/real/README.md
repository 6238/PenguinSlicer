# Real parts of the Popcorn Penguins' robot

Eight parts of the robot of the Popcorn Penguins (FRC Team 6238), exported from Onshape as
binary STL, each exported once. They are copies, byte for byte, of the slice service's
[real parts](../../../../slice/tests/fixtures/frc-parts/README.md), kept here so that a
component other than the slice service can use them without reading the slice service's
folder. The wizard's geometry is tried and tested on them
([How the trials and measurements are run](../../../../wizard/README-details.md#how-the-trials-and-measurements-are-run)).

| File | Original file name | Triangles | Size (mm) | SHA-256 |
|---|---|---|---|---|
| `clamp-plate-inner.stl` | Clamp Plate Inner.stl | 8,756 | 4.762 x 50.8 x 50.8 | `19e59b003a77568599cbcd85e31a2ac74f6df3bbedf57f3ac5bf0c0f00b2827b` |
| `elevator-block-bottom-inner.stl` | Elevator Block Bottom Inner.stl | 39,054 | 88.9 x 63.5 x 82.55 | `db902cd519da10b6385371a0527157173ff4dbc2e708a549854dd827fd76144a` |
| `elevator-block-carriage.stl` | Elevator Block Carriage.stl | 23,580 | 88.9 x 31.75 x 57.15 | `d49c63d0cb761a9ce6f0658ace43428c376f1af1fc09ae397dd1fe884c10532b` |
| `elevator-block-top.stl` | Elevator Block Top.stl | 34,998 | 88.9 x 31.75 x 82.55 | `6a25d7cb3bc9059207c8be4abfbf172dc877c1d5cd263dfcf289284f9980a629` |
| `elevator-top-inner.stl` | Elevator Top Inner.stl | 19,392 | 50.8 x 25.4 x 57.15 | `0b5c9685e3f59a711d06ce9d0f6c60ff7ff5351d707d9f050545dddeb2f0448e` |
| `inner-spacer.stl` | Inner Spacer.stl | 2,908 | 1.262 x 50.8 x 50.8 | `7f155e29cb33cb18b1dd33b40db99445e416d108b18f9bc6290a896ff4f200bb` |
| `outer-clamp.stl` | Outer Clamp.stl | 8,724 | 4.762 x 50.8 x 50.8 | `8e005120bcc415a62f13f6343172af0dee2347d8f11a9e2fdac7cdb596619d7e` |
| `pulley-v3.stl` | Pulley v3.stl | 4,608 | 17.78 x 19.05 x 19.05 | `24d2932b43e72e50a2186757a4bbc405df65f19e7e0270346c357478d5fa4a98` |

Every file is a closed surface of one piece, wound outwards. The wizard's fast suite checks
each file's hash and triangle count against this table. A file is never edited here: a
part exported again from Onshape is a new file with a new row. The round parts exported
from Onshape at its coarse and fine settings, which the wizard's second trial would be
better for, are to be added here when the owner supplies them.

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
