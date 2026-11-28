"""The Settings step and advanced mode, in Chromium (wizard/README-details.md, "The Settings step",
"Advanced mode"): the Filament and Profile menus, the quick changes, the caution, the changes box
and its lines, advanced mode drawn from the table of settings (the contract's example, and the
slice service's real table), its accordion and its rail, what it remembers, its keyboard, a value
refused where it is typed, Reset all, and the changes kept through a refresh. Time is the page's
fake clock; each wait is on an event."""
import json
from pathlib import Path

import pytest

from tests_browser.fake_front_server import example
from tests_browser.test_panel import no_sideways_scroll

REAL_TABLE = Path(__file__).resolve().parents[2] / "slice" / "src" / "penguin_slice" / "settings" / "table.json"
HAND = example("configuration-hand-written.json")


def configuration(body=HAND, name="6238 (Popcorn Penguins)"):
    return (200, {"configuration": body, "source": "group", "name": name, "revision": "r1"})


@pytest.fixture
def settings_page(front_server, wizard):
    """The page opened at a width on the Settings step, with the hand-written configuration unless
    another is given, and the contract's example table unless another is given."""
    def open_at(width=320, config=HAND, table=None):
        front_server.script("GET", "/api/configuration", configuration(config), configuration(config), configuration(config))
        if table is not None:
            front_server.script("GET", "/api/settings-table", (200, table), (200, table), (200, table))
        w = wizard(width)
        w.set({"step": "settings"})
        w.until("return document.querySelector('#p-filament').options.length > 0;")
        return w
    return open_at


def changes(w):
    return w.run("return wizard.settings.changes();")


def open_advanced(w):
    """By the Advanced mode button that shows: alone, or in the changes box."""
    w.page.click("#btn-advanced:visible, #adv-effect-btn:visible")
    w.page.wait_for_selector("#advanced:not([hidden])")


def width(w, px):
    """The panel at a new width, once advanced mode has followed it."""
    w.width(px)
    w.page.wait_for_selector("#advanced.wide" if px >= 480 else "#advanced:not(.wide)", state="attached")


# ---- the Filament and Profile menus

def test_the_filament_menu_shows_the_chosen_filaments_colour_and_the_profiles_their_purposes(settings_page):
    w = settings_page()
    page = w.page
    assert page.locator("#p-filament option").all_inner_texts() == ["Black PETG", "Orange PETG", "PETG-CF"]
    assert page.locator(".filament-swatch").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(32, 32, 32)"
    assert page.locator("#p-profile option").all_inner_texts() == ["Structural", "Draft"]
    assert page.locator("#p-profile option").first.get_attribute("title") == "For strong brackets and plates"
    page.select_option("#p-filament", "Orange PETG")
    assert page.locator(".filament-swatch").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(232, 116, 42)"
    assert w.problems == []


def test_picking_a_filament_picks_its_first_profile_and_clears_the_changes_and_the_caution(settings_page):
    w = settings_page()
    page = w.page
    assert not page.locator("#p-profile-clears").is_visible()
    page.select_option("#ov-walls", "6")
    assert page.locator("#p-profile-clears").text_content() == "⚠Changing the filament or the profile clears your change."
    page.select_option("#ov-brim", "no_brim")
    assert page.locator("#p-profile-clears").inner_text().endswith("clears your 2 changes.")
    page.select_option("#p-filament", "PETG-CF")
    assert page.locator("#p-profile").input_value() == "Stiff bracket"
    assert changes(w) == []
    assert not page.locator("#p-profile-clears").is_visible()
    assert page.locator("#wiz-summary .sum-text").inner_text() == "PETG-CF · Stiff bracket"


# ---- the quick changes

def test_the_quick_changes_show_the_profiles_values_and_write_into_the_shared_changes(settings_page):
    w = settings_page()
    page = w.page
    assert [page.locator(f"#ov-{q} option").all_inner_texts() for q in ("infill", "walls", "supports", "brim")] == [
        ["15 %", "25 %", "40 %", "60 %", "100 %"], ["2", "3", "4", "6"], ["Off", "On (tree, auto)"], ["Auto", "Off", "Outer only"]]
    # Structural: 4 walls and 40 % infill of its own
    assert page.locator("#ov-walls").input_value() == "4"
    assert page.locator("#ov-infill").input_value() == "40%"
    page.select_option("#ov-supports", "1")
    assert changes(w) == [{"name": "enable_support", "value": "1"}]
    assert "changed" in page.locator("#ov-supports").get_attribute("class")
    page.select_option("#ov-supports", "0")
    assert changes(w) == []


def test_a_profile_value_off_a_menus_list_is_its_top_entry_and_chosen(settings_page):
    w = settings_page()
    w.page.select_option("#p-filament", "PETG-CF")      # Stiff bracket: 35 % infill
    assert w.page.locator("#ov-infill option").all_inner_texts() == ["35 %", "15 %", "25 %", "40 %", "60 %", "100 %"]
    assert w.page.locator("#ov-infill").input_value() == "35%"


def test_below_480_px_one_quick_change_to_a_row_and_two_from_480_px(settings_page):
    w = settings_page(479)
    tops = lambda: w.page.locator("#p-overrides label").evaluate_all("ls => ls.map((l) => Math.round(l.getBoundingClientRect().top))")
    assert len(set(tops())) == 4
    w.width(480)
    assert len(set(tops())) == 2


# ---- the changes box

def test_the_changes_box_takes_the_buttons_place_and_its_line_opens_advanced_mode_at_its_setting(settings_page):
    w = settings_page()
    page = w.page
    assert page.locator("#adv-entry").is_visible()
    assert not page.locator("#adv-effect").is_visible()
    page.select_option("#ov-brim", "no_brim")
    assert not page.locator("#adv-entry").is_visible()
    assert page.locator("#adv-effect strong").inner_text() == "1 setting changed from Structural"
    assert page.locator("#adv-effect li").all_inner_texts() == ["Others › Brim: Off (profile Auto)"]
    # its section and setting group closed first, so that the line must open them
    open_advanced(w)
    page.click("#adv-grp-Others-Brim")
    assert page.locator("#adv-grp-Others-Brim").get_attribute("aria-expanded") == "false"
    page.click("#adv-sec-Others")
    page.click("#adv-done")
    page.click("#chg-line-brim_type")
    page.wait_for_selector("#advanced:not([hidden])")
    assert page.locator("#adv-sec-Others").get_attribute("aria-expanded") == "true"
    assert page.locator("#adv-grp-Others-Brim").get_attribute("aria-expanded") == "true"
    assert "flash" in page.locator("#adv-row-brim_type").get_attribute("class")
    assert page.evaluate("() => document.activeElement.id") == "adv-brim_type"
    page.click("#adv-done")
    assert page.evaluate("() => document.activeElement.id") == "chg-line-brim_type"


# ---- advanced mode

def test_advanced_mode_draws_a_control_for_each_kind_and_number_form_of_the_example_table(settings_page):
    w = settings_page()
    open_advanced(w)
    page = w.page
    kinds = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#adv-body .adv-row')].map((r) => {
        const c = r.querySelector('.ctl input, .ctl select');
        return [r.id.slice(8), [c.tagName.toLowerCase(), c.type, c.step || '', c.min || '', c.max || '', r.querySelector('.unit').textContent]];
    }))""")
    assert kinds == {
        "layer_height": ["input", "number", "any", "0", "", "mm"],
        "initial_layer_line_width": ["input", "text", "", "", "", "mm or %"],
        "wall_loops": ["input", "number", "1", "0", "1000", ""],
        "sparse_infill_density": ["input", "number", "any", "0", "100", "%"],
        "sparse_infill_pattern": ["select", "select-one", "", "", "", ""],
        "outer_wall_speed": ["input", "number", "any", "0", "", "mm/s"],
        "enable_support": ["select", "select-one", "", "", "", ""],
        "support_type": ["select", "select-one", "", "", "", ""],
        "brim_type": ["select", "select-one", "", "", "", ""],
    }
    assert page.locator("#adv-enable_support option").all_inner_texts() == ["Off", "On"]
    assert page.locator("#adv-sparse_infill_density").input_value() == "40"
    assert page.locator("label[for=adv-layer_height]").get_attribute("data-tip") or page.locator("label[for=adv-layer_height]").get_attribute("title")
    assert w.problems == []


def test_advanced_mode_draws_every_setting_of_the_real_table(settings_page):
    table = json.loads(REAL_TABLE.read_text(encoding="utf-8"))
    config = example("configuration-default.json")
    w = settings_page(320, config=config, table=table)
    open_advanced(w)
    assert w.page.locator("#adv-body .adv-row").count() == len(table["settings"]) == 338
    assert w.page.locator("#adv-body .adv-sec-btn .nm").all_inner_texts() == list(dict.fromkeys(s["section"] for s in table["settings"]))
    width(w, 680)
    assert w.page.locator("#adv-body .adv-rail button").count() == 6
    assert no_sideways_scroll(w.page) == []
    assert w.problems == []


def test_opening_puts_focus_on_the_first_sections_heading_and_covers_the_panel(settings_page):
    w = settings_page()
    open_advanced(w)
    page = w.page
    assert page.evaluate("() => document.activeElement.id") == "adv-sec-Quality"
    assert page.evaluate("() => ['#wiz-header', '#wiz-body', '#wiz-nav'].every((s) => document.querySelector(s).inert)")
    assert page.locator("#adv-sub").inner_text() == "Structural, no changes"
    assert page.locator("#adv-reset-all").is_disabled()
    page.click("#adv-done")
    assert page.evaluate("() => document.activeElement.id") == "btn-advanced"
    assert page.evaluate("() => ['#wiz-header', '#wiz-body', '#wiz-nav'].every((s) => !document.querySelector(s).inert)")


def test_a_report_sent_while_advanced_mode_is_open_names_the_step_advanced(settings_page, front_server):
    w = settings_page()
    open_advanced(w)
    w.run("await wizard.reports.failure('page_failed', {detail: 'a test'});")
    w.page.click("#adv-done")
    w.run("await wizard.reports.failure('page_failed', {detail: 'a test'});")
    steps = [json.loads(body)["step"] for method, path, body in front_server.bodies if path == "/api/reports/failure"]
    assert steps == ["advanced", "settings"]


def test_escape_does_not_close_advanced_mode(settings_page):
    w = settings_page()
    open_advanced(w)
    w.page.keyboard.press("Escape")
    assert w.page.locator("#advanced").is_visible()


def test_a_value_out_of_range_is_refused_where_it_is_typed(settings_page):
    w = settings_page()
    open_advanced(w)
    page = w.page
    page.fill("#adv-wall_loops", "1001")
    page.locator("#adv-wall_loops").dispatch_event("change")
    assert page.locator("#adv-row-wall_loops .bad").inner_text() == "Wall loops must be between 0 and 1000. Kept 4."
    assert "invalid" in page.locator("#adv-wall_loops").get_attribute("class")
    assert changes(w) == []
    page.fill("#adv-wall_loops", "5")
    page.locator("#adv-wall_loops").dispatch_event("change")
    assert page.locator("#adv-row-wall_loops .bad").count() == 0
    assert changes(w) == [{"name": "wall_loops", "value": "5"}]


def test_a_changed_setting_is_marked_with_the_profiles_value_and_reset(settings_page):
    w = settings_page()
    open_advanced(w)
    page = w.page
    page.fill("#adv-layer_height", "0.2")
    page.locator("#adv-layer_height").dispatch_event("change")
    row = page.locator("#adv-row-layer_height")
    assert "changed" in row.get_attribute("class")
    assert row.locator(".was").inner_text() == "Profile 0.24 mm Reset"
    assert page.locator("#adv-sec-Quality .ct").inner_text() == "· 1 changed"
    assert page.locator("#adv-grp-Quality-Layer-height .ct").inner_text() == "· 1 changed"
    assert page.locator("#adv-sub").inner_text() == "Structural, 1 changed"
    page.click("#adv-reset-layer_height")
    assert changes(w) == []
    assert row.locator(".was").count() == 0
    assert page.evaluate("() => document.activeElement.id") == "adv-layer_height"


def test_reset_all_asks_first_and_then_puts_every_setting_back(settings_page):
    w = settings_page()
    open_advanced(w)
    page = w.page
    page.select_option("#adv-brim_type", "brim_ears")
    page.select_option("#adv-sparse_infill_pattern", "cubic")
    page.click("#adv-reset-all")
    page.wait_for_selector(".confirm-pop")
    assert page.locator(".confirm-pop p").inner_text() == "Put all 2 changed settings back to Structural’s values?"
    assert page.evaluate("() => document.activeElement.textContent") == "Keep my changes"
    page.keyboard.press("Escape")
    assert len(changes(w)) == 2
    assert page.locator("#advanced").is_visible()
    assert page.evaluate("() => document.activeElement.id") == "adv-reset-all"
    page.click("#adv-reset-all")
    page.click(".confirm-pop .btn.primary")
    assert changes(w) == []
    assert page.locator("#adv-body .adv-row.changed").count() == 0
    # Reset all is disabled now, so the focus goes where opening puts it, never to the page's body
    assert page.locator("#adv-reset-all").is_disabled()
    assert page.evaluate("() => document.activeElement.id") == "adv-sec-Quality"


def test_reset_all_drops_a_refusal_whose_kept_value_it_changed_and_keeps_one_whose_value_stays(settings_page):
    w = settings_page()
    open_advanced(w)
    page = w.page
    page.fill("#adv-wall_loops", "5")
    page.locator("#adv-wall_loops").dispatch_event("change")
    page.fill("#adv-wall_loops", "1001")
    page.locator("#adv-wall_loops").dispatch_event("change")
    assert page.locator("#adv-row-wall_loops .bad").inner_text() == "Wall loops must be between 0 and 1000. Kept 5."
    # a refusal on a setting the reset leaves as it is: its sentence stays true, so it stays
    page.fill("#adv-layer_height", "-1")
    page.locator("#adv-layer_height").dispatch_event("change")
    assert page.locator("#adv-row-layer_height .bad").count() == 1
    page.click("#adv-reset-all")
    page.click(".confirm-pop .btn.primary")
    assert changes(w) == []
    assert page.locator("#adv-wall_loops").input_value() == "4"
    assert "invalid" not in (page.locator("#adv-wall_loops").get_attribute("class") or "")
    assert page.locator("#adv-row-wall_loops .bad").count() == 0
    assert page.locator("#adv-layer_height").input_value() == "-1"
    assert page.locator("#adv-row-layer_height .bad").inner_text().endswith("Kept 0.24 mm.")


def test_closed_sections_survive_leaving_and_a_resize_across_480_px_and_are_open_after_a_reload(settings_page):
    w = settings_page(320)
    open_advanced(w)
    page = w.page
    page.click("#adv-sec-Strength")
    page.click("#adv-grp-Quality-Layer-height")
    page.click("#adv-done")
    w.set({"step": "parts"})
    w.set({"step": "settings"})
    open_advanced(w)
    assert page.locator("#adv-sec-Strength").get_attribute("aria-expanded") == "false"
    width(w, 600)
    assert page.locator("#adv-grp-Quality-Layer-height").get_attribute("aria-expanded") == "false"
    width(w, 320)
    assert page.locator("#adv-sec-Strength").get_attribute("aria-expanded") == "false"
    w.reload()
    w.until("return document.querySelector('#advanced') && !document.querySelector('#advanced').hidden;")
    assert page.locator("#adv-sec-Strength").get_attribute("aria-expanded") == "true"
    assert page.locator("#adv-grp-Quality-Layer-height").get_attribute("aria-expanded") == "true"


def test_from_480_px_a_rail_of_sections_with_their_changed_counts(settings_page):
    w = settings_page(520)
    page = w.page
    page.select_option("#ov-walls", "6")
    open_advanced(w)
    assert page.locator("#adv-tab-Strength .n").inner_text() == "1"
    assert page.locator("#adv-tab-Quality .n").is_hidden()
    assert page.evaluate("() => document.activeElement.id") == "adv-tab-Quality"
    page.click("#adv-tab-Strength")
    assert page.locator(".adv-col-name").inner_text() == "Strength"
    page.click("#adv-expand-Strength")
    assert page.locator("#adv-body .adv-grp.open").count() == 0
    page.click("#adv-expand-Strength")
    assert page.locator("#adv-body .adv-grp.open").count() == 2


def test_the_changes_survive_a_refresh_and_advanced_mode_reopens(settings_page):
    w = settings_page()
    page = w.page
    page.select_option("#ov-walls", "6")
    open_advanced(w)
    page.fill("#adv-layer_height", "0.2")
    page.locator("#adv-layer_height").dispatch_event("change")
    w.run("await wizard.storage.written();")
    w.reload()
    w.until("return !document.querySelector('#advanced').hidden;")
    assert changes(w) == [{"name": "wall_loops", "value": "6"}, {"name": "layer_height", "value": "0.2"}]
    page.click("#adv-done")
    assert page.locator("#adv-effect li").count() == 2
    assert page.locator("#wiz-summary #chg-chip").inner_text() == "+2 changes"


@pytest.mark.parametrize("width", [320, 479, 480, 519, 520, 679, 680])
def test_the_step_and_advanced_mode_have_no_sideways_scroll(settings_page, width):
    w = settings_page(width)
    w.page.select_option("#ov-walls", "6")
    w.page.select_option("#ov-brim", "no_brim")
    assert no_sideways_scroll(w.page) == []
    open_advanced(w)
    assert no_sideways_scroll(w.page) == []
    assert w.problems == []


def test_hostile_words_of_the_table_and_configuration_are_shown_as_text(settings_page):
    table = example("settings-table.json")
    table["settings"][0]["label"] = "<img src=x onerror=alert(1)>"
    table["settings"][0]["section"] = "<b>Quality</b>"
    config = json.loads(json.dumps(HAND))
    config["filaments"][0]["name"] = "<i>PETG</i>"
    config["filaments"][0]["colour"] = "red; background-image: url(x)"
    w = settings_page(config=config, table=table)
    open_advanced(w)
    assert w.page.locator("#adv-body img, #adv-body b, #p-filament i").count() == 0
    assert w.page.locator("label[for=adv-layer_height]").inner_text() == "<img src=x onerror=alert(1)>"
    w.page.click("#adv-done")
    assert w.page.locator(".filament-swatch").is_hidden()
    assert w.problems == []


def test_a_text_field_takes_its_greatest_length_in_characters_outside_the_basic_plane_and_refuses_one_more(settings_page):
    table = example("settings-table.json")
    table["settings"].append({"name": "filename_format", "kind": "text", "label": "Name", "section": "Others",
                              "group": "Output", "explanation": "", "per_variant": False, "max_length": 4})
    w = settings_page(table=table)
    open_advanced(w)
    page = w.page
    # four penguins are eight UTF-16 units: the field lets all four in, and they are accepted
    page.click("#adv-filename_format")
    page.keyboard.insert_text("\U0001f427" * 4)
    assert page.locator("#adv-filename_format").input_value() == "\U0001f427" * 4
    page.locator("#adv-filename_format").dispatch_event("change")
    assert changes(w) == [{"name": "filename_format", "value": "\U0001f427" * 4}]
    # five plain characters get into the field, and the wizard refuses them in its own words
    page.fill("#adv-filename_format", "")
    page.keyboard.type("abcde")
    assert page.locator("#adv-filename_format").input_value() == "abcde"
    page.locator("#adv-filename_format").dispatch_event("change")
    assert page.locator("#adv-row-filename_format .bad").inner_text().startswith("Name can be at most 4 characters long.")


def test_sections_and_setting_groups_whose_words_fold_to_the_same_id_stay_apart(settings_page):
    table = example("settings-table.json")
    for i, (section, group) in enumerate([("A|B", "C"), ("A", "B|C"), ("A B", "X"), ("A/B", "X")]):
        table["settings"][i]["section"] = section
        table["settings"][i]["group"] = group
    w = settings_page(table=table)
    open_advanced(w)
    page = w.page
    ids = page.evaluate("() => [...document.querySelectorAll('#advanced [id]')].map((e) => e.id)")
    assert len(ids) == len(set(ids))
    groups = page.locator("#adv-body .adv-sub")
    assert groups.nth(0).get_attribute("aria-expanded") == "true"
    groups.nth(1).click()
    assert groups.nth(1).get_attribute("aria-expanded") == "false"
    assert groups.nth(0).get_attribute("aria-expanded") == "true"
    page.locator("#adv-body .adv-sec-btn").nth(3).click()
    assert page.locator("#adv-body .adv-sec-btn").nth(3).get_attribute("aria-expanded") == "false"
    assert page.locator("#adv-body .adv-sec-btn").nth(2).get_attribute("aria-expanded") == "true"
