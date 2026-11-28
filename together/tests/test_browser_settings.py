"""The settings a user changes, across both seams: the real table of settings, which the front
server passes from the slice service to the wizard, read by the wizard's advanced mode and by
the slice service's check of a plate configuration's overrides. Neither half can show this
alone: the wizard's own tests read a hand-written table of nine settings, and the HTTP half of
the joined suite sends only the configuration's own overrides
(docs/orchestration/phase-2/seam-wizard-front.md, "Which scenarios the joined suite adds").

- A user changes settings in advanced mode and slices: the slice service receives each in
  Orca's form.
- For every setting of the real table, at its bounds and just past them: what the wizard lets
  a user set is what the slice service accepts, and what it refuses the slice service refuses.
"""

import json

from joined.plates import CLAMP_PLATE, Placed, first_profile, plate

NOT_HELD = {"sha256": "0" * 64, "units": "mm"}


def test_settings_changed_in_advanced_mode_reach_the_slice_service_in_orcas_form(wizard, slice_service):
    # At 320 px advanced mode lists every section in one column (from 480 px, one at a time).
    w = wizard(width=320, height=900)
    w.add_parts([CLAMP_PLATE])
    w.next("settings")
    w.page.click("#btn-advanced:visible, #adv-effect-btn:visible")
    w.page.wait_for_selector("#advanced:not([hidden])")
    # A number typed as a user types it, a percentage without its sign, and a choice picked.
    w.page.fill("#adv-layer_height", "0.20")
    w.page.locator("#adv-layer_height").dispatch_event("change")
    w.page.fill("#adv-sparse_infill_density", "35")
    w.page.locator("#adv-sparse_infill_density").dispatch_event("change")
    pattern = w.page.locator("#adv-sparse_infill_pattern")
    choices = pattern.locator("option").evaluate_all("(os) => os.map((o) => o.value)")
    chosen = next(c for c in choices if c != pattern.input_value())
    pattern.select_option(chosen)
    assert w.page.locator("#advanced .bad").count() == 0
    w.page.click("#adv-done")
    w.next("layout")
    w.layout_settled(1)
    w.next("preview")
    details = w.sliced()

    [queued] = [line for line in slice_service.lines("slice_job")
                if line["state"] == "queued" and line["job"] == details["slice"]]
    assert queued["overrides"]["layer_height"] == "0.2"
    assert queued["overrides"]["sparse_infill_density"] == "35%"
    assert queued["overrides"]["sparse_infill_pattern"] == chosen
    assert w.problems == []


#: For each setting of the table the page holds, the texts a user may type or pick at its
#: bounds and just past them, each with the wizard's own verdict (advanced mode's check, the
#: one its field applies) and the value it would send.
VERDICTS = """
const table = wizard.store.get().settingsTable;
const asNumber = (e, n) => (e.number_form === 'percent' ? `${n}%` : String(n));
const out = [];
for (const e of table.settings) {
  const tries = [];
  if (e.kind === 'choice') {
    tries.push(...e.choices.map((c) => c.value), 'not-one-of-its-choices');
  } else if (e.kind === 'text') {
    tries.push('x'.repeat(e.max_length), 'x'.repeat(e.max_length + 1), 'a\\nb');
  } else {
    if ('min' in e) tries.push(asNumber(e, e.min), asNumber(e, e.min - 1));
    if ('max' in e) tries.push(asNumber(e, e.max), asNumber(e, e.max + 1));
    if (!('min' in e) && !('max' in e)) tries.push(asNumber(e, 1));
    tries.push(e.number_form === 'integer' ? '1.5' : '1e3');
  }
  for (const text of tries) {
    const read = wizard.settings.set(e.name, text);
    out.push({ name: e.name, text, ok: read.ok, value: read.ok ? read.value : null });
    wizard.settings.reset(e.name);
  }
}
return out;
"""


def test_every_setting_at_its_bounds_is_accepted_by_the_slice_service_exactly_when_the_wizard_takes_it(
        wizard, slice_service):
    w = wizard()
    verdicts = w.run(VERDICTS)
    table = w.run("return wizard.store.get().settingsTable;")
    assert len({v["name"] for v in verdicts}) == len(table["settings"]) == 338
    profile = first_profile(w.run("return wizard.store.get().configuration;"))
    # A plate naming a part the part store does not hold: the slice service checks the
    # overrides first, so a setting it accepts is answered `slice.part_missing` and one it
    # refuses `slice.bad_overrides`, and no slice job starts either way.
    unheld = Placed("p1", "Not held", NOT_HELD, [("+z", 0, 100.0, 100.0)])
    disagree = []
    for verdict in verdicts:
        sent = verdict["value"] if verdict["ok"] else verdict["text"]
        configuration = plate([unheld], profile, overrides={verdict["name"]: sent})
        configuration["overrides"] = {verdict["name"]: sent}
        answer = slice_service.request("POST", "/slices", content=json.dumps(configuration).encode(),
                                       headers={"Content-Type": "application/json"})
        code = answer.json()["code"]
        assert code in ("slice.part_missing", "slice.bad_overrides"), (verdict, answer.text)
        if (code == "slice.part_missing") != verdict["ok"]:
            disagree.append((verdict, answer.json()["message"]))
    assert disagree == [], f"{len(disagree)} of {len(verdicts)} disagree: {disagree[:10]}"
    assert slice_service.lines("slice_job") == [line for line in slice_service.lines("slice_job")
                                                if line["state"] == "refused"]
