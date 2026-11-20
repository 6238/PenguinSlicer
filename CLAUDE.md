# Penguin Slicer: notes for agents

Read [README.md](README.md) first: four components, each its own project, depending only
on [contracts/](contracts/README.md).

## Working here

- Work on a branch; `main` holds only the skeleton commit until the owner decides where
  the repository lives. Nothing has a remote yet.
- Each component is its own `uv` project. Run its commands with `make -C <component> ...`.

| Component | Fast suite | Other suites |
|---|---|---|
| `slice/` | `make -C slice test` | `make -C slice test-orca` (real Orca Slicer; also the upstream check), `make -C slice test-flakes RUNS=20 WORKERS=2` |
| `delivery/` | `make -C delivery test` | `make -C delivery test-sim` (simulated printer), `make -C delivery test-upstream`, `make -C delivery together` |

## The quality bar

- The fast suites use no real Orca, no real printer, no real waiting and no fixed ports,
  and must pass in any order, any number of times. A test that fails once is fixed at its
  cause, never retried or skipped.
- Every failure a caller can see is an error report
  ([contracts/error-report.md](contracts/error-report.md)) with a test that produces it on
  purpose. Every long job sends progress reports and can be cancelled.
- A change to a component is checked by someone who did not write it: rerun the suites in
  random order, mutate the changed checks by hand, and try hostile inputs.

## Gotchas learned the hard way

- **One real Orca at a time.** A slice can take 1 to 2 GB; never run the real-Orca suite
  in parallel workers.
- **Bound anything that might hang, and bound the right process.** Run pytest directly
  from the project's environment under a time limit and a memory limit. A timeout placed
  on a wrapper such as `uv run` kills the wrapper and leaves pytest running; a test that
  loops on a fake clock can then grow to gigabytes.
- **Orca reports progress through its `--pipe` option**, one message per stage with a
  percentage. Its real reason for a failed slice is in `result.json` (`error_string`),
  which must be read before the scratch folder is removed.
- **Orca's peak memory is a spike shorter than a tenth of a second.** Sampling current
  memory misses it; the kernel's high-water mark (`VmHWM`) does not.
- **Orca 2.5.x packs the Bambu profiles in `BBL.opc`,** which the profile catalog script
  cannot read yet. The pin stays at 2.4.2 until it can.
- **The printer status sequences in the simulated printer are invented** from one recorded
  status document. `python -m penguin_delivery_daemon record` saves real ones; replace the
  scenarios when recordings exist.
