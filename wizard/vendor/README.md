# Third-party code kept as files

The wizard loads nothing from another site: the third-party code it uses is kept here as
files, each under a licence that MIT code may include (MIT, BSD or Apache 2.0), never
Orca's or any other AGPL or GPL code
([The project and its tools](../README-details.md#the-project-and-its-tools)). Each file is
kept byte for byte as its release published it, at the same path inside its package, so
that the relative imports between its files still work; a file is never edited here. The
wizard's fast suite checks each file's SHA-256 against the table below, and that every file
in this folder is in the table. The folder's own `.gitignore` (not in the table) undoes a
global rule that ignores folders named `build/`, which would otherwise keep three.js's core
out of every commit; the fast suite checks that git ignores no file in the table.

## three.js 0.170.0

The 3D library, from the npm package `three` at version 0.170.0 (release r170, published
in October 2024; the package's SHA-1 `6087f97aab79e9e9312f9c89fcef6808642dfbb7`, as the
npm registry lists it). The mockup used release 128 as one script that sets a global; the
wizard takes release 170 because it is published as ES modules, which the page loads as
they are, with no bundler. Release 170 is the last whose core is one file
(`build/three.module.min.js`); from release 171 it is split into two.

Besides the core, the files of three.js's examples that the two opening trials of phase 2
are most likely to need are kept, so that neither trial's builder has to add to this folder:
the orbiting camera, the geometry utilities (merging buffers, which the layer preview needs to
draw many lines in few calls), a convex hull and the wide lines. A trial or a later batch
that needs another file of the same release adds it here with its row.

The examples' files import the core by the bare name `three`. A page loads them by mapping
that name to `three/build/three.module.min.js` (an import map in a trial's page; in the
wizard's page, which may have no inline script, the build rewrites the name to the core's
built address).

| File | Release | Licence | SHA-256 |
|---|---|---|---|
| `three/LICENSE` | three.js 0.170.0 | MIT | `4c40a1ef62450b857c3b2aaf294936304cd552d965fbcd9d32d4c5bcf4ba4454` |
| `three/build/three.module.min.js` | three.js 0.170.0 | MIT | `08fd7545d13d2c7fb65ab691530a802dafefd638596501854f267d0fb13c39e7` |
| `three/examples/jsm/controls/OrbitControls.js` | three.js 0.170.0 | MIT | `80efaadea4f8a636a65fb0bd08bfef62f3d93a0bb94e2e7500f23176c5c07f4e` |
| `three/examples/jsm/utils/BufferGeometryUtils.js` | three.js 0.170.0 | MIT | `c25b7930e570e9ec56173cd3b866ec8d2e10016630db3937efb439daf1cedbf6` |
| `three/examples/jsm/math/ConvexHull.js` | three.js 0.170.0 | MIT | `782e7e422c8d308cd686bacfd23356bda884f01727f9fc4a7a75bcff441bd1ad` |
| `three/examples/jsm/lines/Line2.js` | three.js 0.170.0 | MIT | `f926f3c903983abbf10e7a30dc5908df71dc6a20117eb67f0f758344d4a76f93` |
| `three/examples/jsm/lines/LineGeometry.js` | three.js 0.170.0 | MIT | `b7e1952c8891dc7840a9119ce03eeb547825663c831851bd73baf305d4c61c46` |
| `three/examples/jsm/lines/LineMaterial.js` | three.js 0.170.0 | MIT | `4a58808a6e3a48f2a98eb2a410022ae648f801eaae89d457fcd662b077a7cf27` |
| `three/examples/jsm/lines/LineSegments2.js` | three.js 0.170.0 | MIT | `9dcce823f86d7f00c4faa8c80ea3833fa86bf4957f394a1f64f3b126f6eea661` |
| `three/examples/jsm/lines/LineSegmentsGeometry.js` | three.js 0.170.0 | MIT | `213a12e0e1ea878495d4998817cb83b1945441f19194267dba108c3a9e8f31ac` |

## Taking a new release

Download the package from the npm registry, check its digest against the one the registry
lists, copy the same files at the same paths over these, and replace the table's hashes
and the release in one commit; then run the fast suite and the browser tests.
