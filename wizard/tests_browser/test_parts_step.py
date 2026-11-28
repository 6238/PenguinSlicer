"""The Parts step in Chromium (wizard/README-details.md, "The Parts step"): the upload area by a
chosen file, a drop and the keyboard, the switch and its kept choice, a row with its picture, name,
size, quantity and remove button, the line under the list, the red message past 150 instances, each
kind of notification, a warning on its row, the amber line of a part the browser could not save, a
part whose upload is slow, a part the page cannot draw, New plate with its confirmation, hostile
names, and no sideways scroll at each width. Time is the page's fake clock; the uploads reach the
fake front server."""
import hashlib
import json
import struct

import pytest

from tests_browser.fake_front_server import error_report, example

PARTS = "section.step[data-step=parts]"


def box_stl(header=b"box", size=(20.0, 10.0, 5.0)):
    """A binary STL of a box, its header `header`, so that two files of one box differ."""
    x, y, z = size
    corners = [(0, 0, 0), (x, 0, 0), (x, y, 0), (0, y, 0), (0, 0, z), (x, 0, z), (x, y, z), (0, y, z)]
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    data = header.ljust(80, b" ")[:80] + struct.pack("<I", len(faces))
    for face in faces:
        data += struct.pack("<3f", 0, 0, 0)
        for i in face:
            data += struct.pack("<3f", *corners[i])
        data += b"\x00\x00"
    return data


def choose(w, *files):
    """Chooses files in the upload area's file chooser, as the user does: (name, bytes) each."""
    w.page.set_input_files("#f-upload", [{"name": n, "mimeType": "application/octet-stream", "buffer": b} for n, b in files])


def uploads(server):
    return [(path, body) for (method, path, body) in server.bodies if method == "POST" and path.startswith("/api/parts")]


def reports(server):
    return [json.loads(body) for (method, path, body) in server.bodies if path == "/api/reports/failure"]


def rows_settled(w, count):
    w.until(f"return wizard.parts.rows().length === {count} && wizard.parts.rows().every((r) => !r.arriving && r.drawn) "
            f"&& document.querySelectorAll('#parts-list canvas.thumb').length === {count};")


def no_sideways_scroll(page):
    return page.evaluate("""() => {
        const w = document.getElementById('wizard');
        const bad = [];
        if (document.documentElement.scrollWidth > document.documentElement.clientWidth) bad.push('page');
        for (const el of w.querySelectorAll('*')) {
            if (el.offsetParent === null) continue;
            const r = el.getBoundingClientRect();
            if (r.right > w.getBoundingClientRect().right + 0.5) bad.push(el.id || el.className || el.tagName);
        }
        return bad;
    }""")


# ---- the upload area and a row

def test_an_empty_parts_step_has_the_upload_area_its_switch_and_no_parts(wizard):
    w = wizard(320)
    assert w.page.locator("#dropzone").inner_text() == "Drop STL files here, or click to choose"
    assert w.page.locator("#f-upload").get_attribute("accept") == ".stl"
    assert w.page.locator("#upload-units").inner_text() == "Read STL files in:  inches /  millimetres"
    assert w.page.locator("#upload-units input[value=in]").is_checked()
    assert w.page.locator("#parts-total").inner_text() == "No parts yet."
    assert w.page.locator("#btn-next").is_disabled()


def test_a_chosen_file_becomes_a_row_with_its_picture_name_size_and_quantity_and_is_uploaded_byte_for_byte(wizard):
    w = wizard(320)
    data = box_stl(b"gusset")
    choose(w, ("Gusset Plate.STL", data))
    rows_settled(w, 1)
    row = w.page.locator("#parts-list .part-item")
    assert row.locator(".name").inner_text() == "Gusset Plate"
    # the fake front server's record measures the example's part, 50.8 by 50.8 by 4.775 mm
    assert row.locator(".dims").inner_text() == "2.000 × 2.000 × 0.188 in"
    # every title in the panel becomes the panel's own tooltip
    assert row.locator(".dims").get_attribute("data-tip") == "Size as modelled, in inches (this file was read in inches)"
    assert row.locator(".part-qty").input_value() == "1"
    assert row.locator(".remove").get_attribute("aria-label") == "Remove Gusset Plate"
    assert row.locator("canvas.thumb").count() == 1
    assert w.page.locator("#parts-total").inner_text() == "1 part, 1 instance on one plate."
    assert not w.page.locator("#btn-next").is_disabled()
    [(path, body)] = uploads(w.server)
    assert path == "/api/parts?units=in"
    assert body == data
    assert w.problems == []


def test_the_upload_area_opens_the_file_chooser_on_a_click_and_on_enter(wizard):
    w = wizard(320)
    with w.page.expect_file_chooser() as chooser:
        w.page.click("#dropzone")
    assert chooser.value.is_multiple()
    w.page.focus("#dropzone")
    with w.page.expect_file_chooser():
        w.page.keyboard.press("Enter")


def test_files_dropped_on_the_upload_area_are_added(wizard):
    w = wizard(320)
    w.run("""const t = new DataTransfer();
             t.items.add(new File([new Uint8Array(arg.a)], 'a.stl'));
             t.items.add(new File([new Uint8Array(arg.b)], 'b.stl'));
             document.getElementById('dropzone').dispatchEvent(new DragEvent('drop', {dataTransfer: t, bubbles: true, cancelable: true}));""",
          {"a": list(box_stl(b"a")), "b": list(box_stl(b"b"))})
    rows_settled(w, 2)
    assert w.page.locator("#parts-list .name").all_inner_texts() == ["a", "b"]


def test_the_same_file_twice_is_one_row_with_quantity_2_and_the_other_units_another_row(wizard):
    w = wizard(320)
    data = box_stl(b"twice")
    choose(w, ("twice.stl", data))
    rows_settled(w, 1)
    choose(w, ("twice.stl", data))
    w.until("return wizard.parts.rows()[0].quantity === 2;")
    assert w.page.locator("#parts-list .part-qty").input_value() == "2"
    w.page.check("#upload-units input[value=mm]")
    choose(w, ("twice.stl", data))
    rows_settled(w, 2)
    assert w.page.locator("#parts-list .dims").nth(1).inner_text() == "50.8 × 50.8 × 4.8 mm"
    assert [p for p, _ in uploads(w.server)] == ["/api/parts?units=in", "/api/parts?units=mm"]


def test_the_switch_is_kept_through_a_refresh(wizard):
    w = wizard(320)
    w.page.check("#upload-units input[value=mm]")
    w.until("return wizard.parts.units() === 'mm';")
    w.reload()
    assert w.page.locator("#upload-units input[value=mm]").is_checked()


def test_a_quantity_cannot_be_typed_past_150_and_parts_past_150_give_the_red_message_and_next_off(wizard):
    w = wizard(320)
    choose(w, ("a.stl", box_stl(b"a")), ("b.stl", box_stl(b"b")))
    rows_settled(w, 2)
    first = w.page.locator("#parts-list .part-qty").nth(0)
    first.fill("200")
    assert first.input_value() == "150"
    first.press("Tab")
    w.until("return wizard.parts.rows()[0].quantity === 150;")
    total = w.page.locator("#parts-total")
    assert total.locator(".msg.error .what").inner_text() == "This plate would hold 151 instances."
    assert total.locator(".msg.error .todo").inner_text() == "Up to 150 instances per plate; print the rest on a new plate."
    assert w.page.locator("#btn-next").is_disabled()
    first.fill("149")
    first.press("Tab")
    w.until("return wizard.parts.rows()[0].quantity === 149;")
    assert total.locator(".msg").count() == 0
    assert not w.page.locator("#btn-next").is_disabled()


def test_removing_a_part_drops_its_row(wizard):
    w = wizard(320)
    choose(w, ("gone.stl", box_stl(b"gone")))
    rows_settled(w, 1)
    w.page.click("#parts-list .remove")
    w.until("return wizard.parts.rows().length === 0;")
    assert w.page.locator("#parts-list .part-item").count() == 0
    assert w.page.locator("#parts-total").inner_text() == "No parts yet."


# ---- the notifications

def test_a_file_over_the_size_limit_is_refused_by_the_page_with_nothing_sent(wizard):
    w = wizard(320)
    choose(w, ("bracket.stl", b"\x00" * 7_500_085))
    w.page.wait_for_selector("#notices .notice.error")
    assert w.page.locator("#notices .n-what").inner_text() == \
        "bracket.stl is 7.6 MB. PenguinSlicer takes parts up to 7.5 MB (150,000 triangles), so it was not added."
    assert w.page.locator("#notices .n-todo").inner_text() == "Export it again from your CAD program at a coarser resolution."
    assert uploads(w.server) == []
    assert w.page.locator("#parts-list .part-item").count() == 0


def test_a_file_the_browser_cannot_read_is_a_notification_and_the_others_are_added_and_an_over_size_file_is_never_read(wizard):
    w = wizard(320)
    # Chromium's own failure of a file moved or deleted after it was chosen, for two of the files;
    # the over-size one must be refused by its size before anything reads it.
    w.page.evaluate("""() => {
        const read = File.prototype.arrayBuffer;
        File.prototype.arrayBuffer = function () {
            if (this.name === 'gone.stl' || this.name === 'huge.stl') {
                window.unreadable = (window.unreadable || 0) + 1;
                return Promise.reject(new DOMException('A requested file or directory could not be found.', 'NotReadableError'));
            }
            return read.call(this);
        };
    }""")
    choose(w, ("good.stl", box_stl(b"good")), ("gone.stl", box_stl(b"gone")))
    rows_settled(w, 1)
    assert w.page.locator("#parts-list .name").all_inner_texts() == ["good"]
    notice = w.page.locator("#notices .notice.error")
    assert notice.locator(".n-what").inner_text() == "gone.stl could not be read, so it was not added."
    assert notice.locator(".n-todo").inner_text() == "Your other parts are fine. Check that the file is still there, then add it again."
    assert w.run("return window.unreadable;") == 1
    choose(w, ("huge.stl", b"\x00" * 7_500_085))
    w.page.wait_for_selector("#notices .n-what:text-is('huge.stl is 7.6 MB. PenguinSlicer takes parts up to 7.5 MB (150,000 triangles), so it was not added.')")
    assert w.run("return window.unreadable;") == 1
    assert [p for p, _ in uploads(w.server)] == ["/api/parts?units=in"]
    assert w.problems == []


def test_a_part_the_slice_service_refuses_is_a_notification_naming_it_and_no_row(wizard):
    w = wizard(320)
    choose(w, ("kept.stl", box_stl(b"kept")))
    rows_settled(w, 1)
    w.server.script("POST", "/api/parts", (422, error_report("slice.part_too_large")))
    choose(w, ("Shooter Hood Rib.stl", box_stl(b"rib")))
    w.page.wait_for_selector("#notices .notice.error")
    report = error_report("slice.part_too_large")
    assert w.page.locator("#notices .n-what").inner_text() == f"Shooter Hood Rib: {report['message']}"
    assert w.page.locator("#notices .n-todo").inner_text() == \
        f"Your other parts are fine. {report['remedy']} STL files are being read in inches."
    assert "fake detail" not in w.page.locator("#notices").inner_text()
    w.until("return wizard.parts.rows().length === 1;")
    assert w.page.locator("#parts-list .name").all_inner_texts() == ["kept"]


def test_a_warning_stays_on_its_row_in_amber_and_next_stays_on(wizard):
    w = wizard(320)
    data = box_stl(b"leaky")
    record = {**example("wizard-front/part-record.json"), "sha256": hashlib.sha256(data).hexdigest(), "units": "in"}
    w.server.script("POST", "/api/parts", (201, record))
    choose(w, ("Gusset Plate.stl", data))
    rows_settled(w, 1)
    warning = w.page.locator("#parts-list .part-item .sub .msg.warn")
    assert warning.locator(".what").inner_text() == "This part is not watertight: its mesh has 14 open edges in 2 places."
    assert warning.locator(".todo").inner_text().startswith("It may still slice and print.")
    assert not w.page.locator("#btn-next").is_disabled()


def test_a_part_the_page_cannot_draw_is_not_added_with_the_wizards_notification_and_one_report(wizard):
    w = wizard(320)
    data = b"\x00" * 84
    choose(w, ("broken.stl", data))
    w.page.wait_for_selector("#notices .notice.error")
    assert w.page.locator("#notices .n-what").inner_text() == "broken: PenguinSlicer could not show this part, so it cannot be imported."
    assert w.page.locator("#notices .n-todo").inner_text() == "Export the part again as a binary STL and add it again."
    w.until("return wizard.parts.rows().length === 0;")
    sent = reports(w.server)
    assert [(r["what"], r["part_sha256"]) for r in sent] == [("part_not_drawable", hashlib.sha256(data).hexdigest())]


def test_a_part_whose_upload_is_slow_says_so_on_its_row_at_4_s(wizard):
    w = wizard(320)
    w.page.route("**/api/parts*", lambda route: route.abort())
    choose(w, ("far.stl", box_stl(b"far")))
    w.page.wait_for_selector("#parts-list .part-item.arriving")
    assert w.page.locator("#parts-list .dims").inner_text() == "Uploading…"
    assert w.page.locator("#parts-list .arrive-bar").is_visible()
    w.until("return wizard.api.waiting() === 1;")
    w.page.clock.run_for(3900)
    assert w.page.locator("#parts-list .dims").inner_text() == "Uploading…"
    w.page.clock.run_for(100)
    w.page.wait_for_selector("#parts-list .dims.slow")
    assert w.page.locator("#parts-list .dims").inner_text() == "Taking longer than usual; still trying…"
    assert w.page.locator("#parts-list .part-qty").is_disabled()
    assert w.page.locator("#parts-total").inner_text() == "0 parts, 0 instances on one plate; 1 more arriving."
    assert not w.page.locator("#btn-next").is_disabled()


def test_a_part_the_browser_could_not_save_has_the_amber_line(page, front_server):
    page.add_init_script("""
        const put = IDBObjectStore.prototype.put;
        IDBObjectStore.prototype.put = function (value, key) {
            if (typeof key === 'string' && key.startsWith('part-bytes/')) throw new DOMException('The quota has been exceeded.', 'QuotaExceededError');
            return put.call(this, value, key);
        };""")
    from tests_browser.conftest import Wizard
    w = Wizard(page, front_server, 320)
    choose(w, ("unsaved.stl", box_stl(b"unsaved")))
    rows_settled(w, 1)
    assert w.page.locator("#parts-list .sub .not-saved").inner_text() == \
        "This part could not be saved in this browser, so a refresh will lose it."


# ---- New plate

def test_new_plate_with_parts_asks_first_and_keeping_changes_nothing(wizard):
    w = wizard(320)
    choose(w, ("a.stl", box_stl(b"a")))
    rows_settled(w, 1)
    assert w.page.locator(f"{PARTS} .new-plate .btn").inner_text() == "New plate"
    w.page.click(f"{PARTS} .new-plate .btn")
    assert w.page.locator(".confirm-pop p").inner_text() == "Start a new plate? The parts and layout of this one are cleared."
    assert w.page.locator(".confirm-pop .btn").all_inner_texts() == ["Keep this plate", "New plate"]
    w.page.keyboard.press("Escape")
    assert w.page.locator(".confirm-pop").count() == 0
    assert w.page.locator("#parts-list .part-item").count() == 1


def test_new_plate_under_a_long_list_asks_above_itself_inside_the_panel(wizard):
    w = wizard(320, 600)
    choose(w, *[(f"p{i}.stl", box_stl(f"p{i}".encode())) for i in range(6)])
    rows_settled(w, 6)
    w.page.evaluate("() => { const b = document.getElementById('wiz-body'); b.scrollTop = b.scrollHeight; }")
    w.page.click(f"{PARTS} .new-plate .btn")
    box = w.page.locator(".confirm-pop").bounding_box()
    button = w.page.locator(f"{PARTS} .new-plate .btn").bounding_box()
    panel = w.page.locator("#wizard").bounding_box()
    assert box["y"] + box["height"] <= button["y"]
    assert box["y"] >= panel["y"] and box["y"] + box["height"] <= panel["y"] + panel["height"]
    assert w.page.evaluate("document.documentElement.scrollTop") == 0


def test_new_plate_confirmed_empties_the_plate_with_a_new_plate_id_and_keeps_the_filament_and_profile(wizard):
    w = wizard(320)
    choose(w, ("a.stl", box_stl(b"a")))
    rows_settled(w, 1)
    before = w.run("return {plate: wizard.store.get().plateId, settings: wizard.storage.plate().settings};")
    w.page.click(f"{PARTS} .new-plate .btn")
    w.page.click(".confirm-pop .btn.primary")
    w.until("return wizard.parts.rows().length === 0 && wizard.store.get().plateId !== arg;", before["plate"])
    assert w.page.locator("#parts-list .part-item").count() == 0
    assert w.run("return wizard.storage.plate().settings;") == before["settings"]
    assert w.page.locator("#btn-next").is_disabled()


def test_new_plate_shows_only_while_the_plate_holds_parts(wizard):
    w = wizard(320)
    assert not w.page.locator(f"{PARTS} .new-plate .btn").is_visible()
    choose(w, ("a.stl", box_stl(b"a")))
    w.page.wait_for_selector(f"{PARTS} .new-plate .btn", state="visible")
    w.page.click("#parts-list .remove")
    w.page.wait_for_selector(f"{PARTS} .new-plate .btn", state="hidden")


# ---- hostile names and the widths

def test_a_hostile_file_name_is_shown_as_text(wizard):
    w = wizard(320)
    name = '<img src=x onerror="window.hacked=1">.stl'
    choose(w, (name, box_stl(b"hostile")))
    rows_settled(w, 1)
    assert w.page.locator("#parts-list .name").inner_text() == '<img src=x onerror="window.hacked=1">'
    assert w.page.locator("#parts-list .name img").count() == 0
    assert w.page.evaluate("window.hacked") is None


@pytest.mark.parametrize("width", [320, 479, 480, 519, 520, 679, 680])
def test_the_parts_step_with_long_names_a_warning_and_the_red_message_has_no_sideways_scroll(wizard, width):
    w = wizard(width)
    data = box_stl(b"leaky")
    record = {**example("wizard-front/part-record.json"), "sha256": hashlib.sha256(data).hexdigest(), "units": "in"}
    w.server.script("POST", "/api/parts", (201, record))
    choose(w, ("A part with a very long name that goes on and on without stopping anywhere.stl", data),
           ("Averyveryverylongnamewithnospacesatallthatcannotwrapanywhereatall.stl", box_stl(b"b")))
    rows_settled(w, 2)
    w.page.locator("#parts-list .part-qty").nth(0).fill("150")
    w.page.locator("#parts-list .part-qty").nth(0).press("Tab")
    w.page.wait_for_selector("#parts-total .msg.error")
    assert no_sideways_scroll(w.page) == []
    columns = w.page.evaluate("getComputedStyle(document.getElementById('parts-list')).gridTemplateColumns.split(' ').length")
    assert (columns == 2) == (width >= 680)
    assert w.problems == []
