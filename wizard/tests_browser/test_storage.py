"""The browser's storage in Chromium, with the real IndexedDB, sessionStorage and Web Locks
(wizard/README-details.md, "What the browser keeps" and "Which plate a tab shows"): several tabs of
one browser, each with its own plate; a refresh keeping the tab's plate; a closed tab's plate
taken up by the next tab; `owner` stored from the start; a cleared storage reported once; a full
plate of 25 parts of 7.5 MB stored and back after a refresh. And the opening's requests and the
header's name, with the reload glyph. These tests leave the page on the real clock: the 12 hours
are the fast suite's, on its fake clock."""
import json

from tests_browser.conftest import Wizard
from tests_browser.fake_front_server import example

DEFAULT = example("configuration-default.json")
HAND = example("configuration-hand-written.json")


# stlOf(i): the bytes of a binary STL of 150,000 triangles, 7,500,084 bytes, a 20 by 10 by 5 mm
# box's twelve triangles over and over, its header's first byte and its last byte `i`.
STL_OF = """
    const BOX = [[0,0,0, 20,10,0, 20,0,0], [0,0,0, 0,10,0, 20,10,0], [0,0,5, 20,0,5, 20,10,5], [0,0,5, 20,10,5, 0,10,5],
                 [0,0,0, 20,0,0, 20,0,5], [0,0,0, 20,0,5, 0,0,5], [0,10,0, 20,10,5, 20,10,0], [0,10,0, 0,10,5, 20,10,5],
                 [0,0,0, 0,0,5, 0,10,5], [0,0,0, 0,10,5, 0,10,0], [20,0,0, 20,10,0, 20,10,5], [20,0,0, 20,10,5, 20,0,5]];
    const stlOf = (i) => {
        const bytes = new Uint8Array(84 + 50 * 150000);
        const view = new DataView(bytes.buffer);
        view.setUint32(80, 150000, true);
        for (let t = 0; t < 150000; t += 1) {
            const tri = BOX[t % 12];
            for (let k = 0; k < 9; k += 1) view.setFloat32(84 + 50 * t + 12 + 4 * k, tri[k], true);
        }
        bytes[0] = i;
        bytes[bytes.length - 1] = i;
        return bytes;
    };
"""


def open_tab(page, server):
    return Wizard(page, server, fake_clock=False)


def plate_id(w):
    return w.run("return wizard.store.get().plateId;")


def stored(w, key):
    """A record of the browser's storage, read by the test through IndexedDB itself."""
    return w.page.evaluate("""(key) => new Promise((resolve, reject) => {
        const open = indexedDB.open('penguinslicer', 1);
        open.onsuccess = () => {
            const get = open.result.transaction('records').objectStore('records').get(key);
            get.onsuccess = () => { open.result.close(); resolve(get.result ?? null); };
            get.onerror = () => reject(get.error);
        };
        open.onerror = () => reject(open.error);
    })""", key)


def test_each_tab_works_with_its_own_plate_kept_through_a_refresh(page, front_server):
    a = open_tab(page, front_server)
    first = plate_id(a)
    b = open_tab(page.context.new_page(), front_server)
    second = plate_id(b)
    assert first != second
    a.set({"step": "settings"})
    a.run("await wizard.storage.written();")
    a.reload()
    assert plate_id(a) == first
    assert a.run("return wizard.store.get().step;") == "settings"
    assert plate_id(b) == second
    assert stored(a, f"plates/{second}")["step"] == "parts"
    assert a.problems == [] and b.problems == []


def test_a_closed_tab_releases_its_plate_and_the_next_tab_takes_it_up(page, front_server):
    a = open_tab(page, front_server)
    first = plate_id(a)
    a.set({"step": "layout"})
    a.run("await wizard.storage.written();")
    other = page.context.new_page()
    page.close()                                               # the browser releases the tab's lock
    c = open_tab(other, front_server)
    assert plate_id(c) == first
    assert c.run("return wizard.store.get().step;") == "layout"
    held = c.page.evaluate("async () => (await navigator.locks.query()).held.map((l) => l.name)")
    assert held == [f"penguinslicer-plate/{first}"]


def test_a_tab_opened_beside_an_open_one_does_not_take_its_plate(page, front_server):
    a = open_tab(page, front_server)
    c = open_tab(page.context.new_page(), front_server)
    d = open_tab(page.context.new_page(), front_server)
    assert len({plate_id(a), plate_id(c), plate_id(d)}) == 3


def test_a_duplicated_tab_begins_a_plate_of_its_own_and_never_waits_for_the_original(page, front_server):
    # Chrome copies a tab's sessionStorage when it duplicates the tab: the copy names the plate
    # the open original holds. Asking for that plate's lock must never wait (the original would
    # hold it until it closed, and the copy would never open). That the seam never queues for a
    # held lock is proved exactly, on an event, by the fast suite (tests/locks.test.js); here the
    # real browser shows the copy opening with a plate of its own.
    a = open_tab(page, front_server)
    first = plate_id(a)
    a.set({"step": "layout"})
    a.run("await wizard.storage.written();")
    before = stored(a, f"plates/{first}")
    copy = page.context.new_page()
    copy.add_init_script(
        "try { sessionStorage.setItem('penguinslicer.plate_id', %s); } catch (e) {}" % json.dumps(first))
    c = open_tab(copy, front_server)
    assert c.page.evaluate("() => sessionStorage.getItem('penguinslicer.plate_id')") != first
    second = plate_id(c)
    assert second != first
    assert c.run("return wizard.store.get().step;") == "parts"
    assert stored(a, f"plates/{first}") == before
    held = sorted(a.page.evaluate("async () => (await navigator.locks.query()).held.map((l) => l.name)"))
    assert held == sorted([f"penguinslicer-plate/{first}", f"penguinslicer-plate/{second}"])
    assert a.problems == [] and c.problems == []


def test_the_owner_is_stored_from_the_start(page, front_server):
    a = open_tab(page, front_server)
    assert stored(a, "owner") == example("wizard-front/me.json")["user"]["id"]
    assert stored(a, f"plates/{plate_id(a)}")["user"] == example("wizard-front/me.json")["user"]["id"]


def test_a_storage_the_browser_cleared_opens_an_empty_plate_and_reports_it_once(page, front_server):
    a = open_tab(page, front_server)
    first = plate_id(a)
    # The browser clears the site's storage: the page lets its database go when asked.
    a.page.evaluate("""() => new Promise((resolve, reject) => {
        const r = indexedDB.deleteDatabase('penguinslicer');
        r.onsuccess = () => resolve(); r.onerror = () => reject(r.error); })""")
    a.reload()
    assert plate_id(a) != first
    reports = [json.loads(body) for (method, path, body) in front_server.bodies if path == "/api/reports/failure"]
    assert [r["what"] for r in reports] == ["storage_cleared"]
    assert reports[0]["step"] == "parts"
    assert reports[0]["browser"] == "Chrome"
    a.reload()
    reports = [path for (_, path, _) in front_server.bodies if path == "/api/reports/failure"]
    assert len(reports) == 1


def test_a_full_plate_of_25_parts_of_7_5_mb_is_stored_and_back_after_a_refresh(page, front_server):
    a = open_tab(page, front_server)
    # Each part is a binary STL of 150,000 triangles (a box's twelve over and over), told apart by
    # its header's first byte and its last byte, stored with its record as an uploaded part is,
    # so that the page opening again takes all 25 up as parts that have arrived.
    added = a.run(STL_OF + """
        const saved = [];
        for (let i = 0; i < 25; i += 1) {
            const bytes = stlOf(i);
            const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
            const sha256 = Array.from(digest, (b) => b.toString(16).padStart(2, '0')).join('');
            const record = {sha256, units: 'mm', measurements: {triangles: 150000, size_mm: [20, 10, 5], volume_mm3: 1000}, warnings: []};
            saved.push((await wizard.storage.addPart({sha256, units: 'mm', name: 'part ' + i, record, quantity: 1}, bytes.buffer)).saved);
        }
        return saved;""")
    assert added == [True] * 25
    a.reload()
    back = a.run(STL_OF + """
        const parts = wizard.storage.plate().parts;
        const checks = [];
        for (let i = 0; i < parts.length; i += 1) {
            const bytes = new Uint8Array(await wizard.storage.partBytes(parts[i].sha256, parts[i].units));
            const made = stlOf(i);
            let same = bytes.length === 7500084;
            for (let j = 0; same && j < bytes.length; j += 4096) same = bytes[j] === made[j];
            checks.push(same && bytes[0] === i && bytes[bytes.length - 1] === i);
        }
        await wizard.parts.idle();
        return {count: parts.length, checks, refused: parts.filter((p) => !p.saved).length,
                rows: wizard.parts.rows().filter((r) => !r.arriving && r.drawn).length};""")
    assert back == {"count": 25, "checks": [True] * 25, "refused": 0, "rows": 25}
    assert [path for (_, path, _) in front_server.bodies if path.startswith("/api/parts")] == []
    assert [path for (_, path, _) in front_server.bodies if path == "/api/reports/failure"] == []


# ---- who the user is and the configuration

def test_the_opening_asks_me_and_the_table_without_a_group_and_the_configuration_for_the_first_group(page, front_server):
    open_tab(page, front_server)
    sent = {p.split("?")[0]: h for (m, p, h) in front_server.request_headers if p.startswith("/api/")}
    group = example("wizard-front/me.json")["groups"][0]["id"]
    assert "x-penguinslicer-group" not in sent["/api/me"]
    assert "x-penguinslicer-group" not in sent["/api/settings-table"]
    assert sent["/api/configuration"]["x-penguinslicer-group"] == group


def test_the_header_names_the_configuration_in_use(page, front_server):
    a = open_tab(page, front_server)
    assert a.page.locator("#config-status").inner_text() == "Config: PenguinSlicer default↻"
    front_server.script("GET", "/api/configuration",
                        (200, {"configuration": HAND, "source": "group", "name": "6238 (Popcorn Penguins)", "revision": "r-1"}))
    a.reload()
    assert a.page.locator("#config-name").inner_text() == "6238 (Popcorn Penguins)"


def test_the_reload_glyph_reads_the_configuration_again_and_says_which_choice_went(page, front_server):
    front_server.script("GET", "/api/configuration",
                        (200, {"configuration": HAND, "source": "group", "name": "6238 (Popcorn Penguins)", "revision": "r-1"}))
    a = open_tab(page, front_server)
    a.set({"step": "settings"})
    assert a.page.locator("#wiz-summary .sum-text").inner_text() == "Black PETG · Structural"
    asked = len([p for p in front_server.requests if p == "/api/configuration"])
    a.page.click("#config-refresh")                            # the default now: no Black PETG
    a.page.wait_for_selector("#notices .notice.warn")
    assert len([p for p in front_server.requests if p == "/api/configuration"]) == asked + 1
    assert a.page.locator("#notices .n-what").inner_text() == "Black PETG is no longer in the configuration."
    assert a.page.locator("#notices .n-todo").inner_text() == "The plate now uses PETG · Standard."
    assert a.page.locator("#config-name").inner_text() == "PenguinSlicer default"
    assert a.page.locator("#wiz-summary .sum-text").inner_text() == "PETG · Standard"
    assert a.problems == []
