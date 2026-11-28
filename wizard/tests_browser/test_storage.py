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
    added = a.run("""
        const saved = [];
        for (let i = 0; i < 25; i += 1) {
            const bytes = new Uint8Array(7500084);
            for (let j = 0; j < bytes.length; j += 4096) bytes[j] = (i + j) & 0xff;
            bytes[bytes.length - 1] = i;
            saved.push((await wizard.storage.addPart({sha256: 'h' + i, units: 'mm', name: 'part ' + i}, bytes.buffer)).saved);
        }
        return saved;""")
    assert added == [True] * 25
    a.reload()
    back = a.run("""
        const parts = wizard.storage.plate().parts;
        const checks = [];
        for (let i = 0; i < parts.length; i += 1) {
            const bytes = new Uint8Array(await wizard.storage.partBytes(parts[i].sha256, parts[i].units));
            let same = bytes.length === 7500084 && bytes[bytes.length - 1] === i;
            for (let j = 0; same && j < bytes.length; j += 4096) same = bytes[j] === ((i + j) & 0xff);
            checks.push(same);
        }
        return {count: parts.length, checks, refused: parts.filter((p) => !p.saved).length};""")
    assert back == {"count": 25, "checks": [True] * 25, "refused": 0}
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
