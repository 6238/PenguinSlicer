# Small real sliced files for the layer preview

Sliced files Orca 2.4.2 made through the slice service's phase 2 HTTP interface, small enough to
commit, which the layer preview's tests read: its tests on Node's runner and its tests in
Chromium. The first trial's three plates (8.8 to 14.1 MB) are not committed; they are for
measuring, as [the trial's README](../../trials/preview/README.md) says.

| File | What it is | Bytes | SHA-256 |
|---|---|---|---|
| `spacer-1.gcode.3mf` | One hex spacer (`wizard/trials/parts/hex-spacer.stl`), flat on its base, supports off: 13 layers, walls, infill and surfaces, no supports | 40,151 | `e6c882fac86113521fe2e2564ccc61675d8f308dbd4ca8136ea5338609b753d3` |
| `pair-supports.gcode.3mf` | An Elevator Block Top and an Elevator Block Carriage, 120 mm apart, supports on: 132 layers, every one of the four groups | 2,025,890 | `f5adcb474f7702d7560bcaf50f6e39f0f72279d18b661ba18f4650e776a93742` |

Each has its plate configuration beside it (`<name>.json`, the parts named by the keys the
trial's plates use) and the summary the slice service gave (`<name>.summary.json`). The fast
suite checks the sizes and hashes above and that the plate configurations are what
[make_sliced.py](make_sliced.py) writes.

Making them again needs the slice service with the real Orca, started by hand under the shared
real-Orca lock as the trial's README says, then:

```
wizard/.venv/bin/python wizard/tests/sliced/make_sliced.py --write-plates
wizard/.venv/bin/python wizard/tests/sliced/make_sliced.py --url http://127.0.0.1:<its port>
```

A file made again differs in a few bytes (the time in its name and metadata), so the table
above is written again with it.
