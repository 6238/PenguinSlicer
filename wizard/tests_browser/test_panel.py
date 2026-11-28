"""The panel as a whole, in Chromium (wizard/README-details.md, "The panel as a whole"): the
widths, the header, the step tabs, the plate summary, Back and Next, the six ways of telling,
the tooltips, and the panel line with retrying. Time is the page's fake clock."""
import pytest

from tests_browser.fake_front_server import error_report

STEPS = ["parts", "settings", "layout", "preview", "send"]
PLATE = {"parts": 1, "instances": 1, "filament": "PETG", "filamentFull": "PETG", "profile": "Structural", "changes": []}
CHANGES = [{"section": "Quality", "label": "Resolution", "value": "0.014 mm", "profile": "0.012 mm"},
           {"section": "Others", "label": "Brim", "value": "Off", "profile": "Auto"}]


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
        if (w.scrollWidth > w.clientWidth) bad.push('panel');
        return bad;
    }""")


def visible(page, selector):
    return page.locator(selector).is_visible()


# ---- the widths

@pytest.mark.parametrize("width", [320, 479, 480, 519, 520, 679, 680])
def test_every_step_at_each_width_has_no_sideways_scroll(wizard, width):
    w = wizard(width)
    w.set({"plate": {**PLATE, "changes": CHANGES, "profile": "Structural with a very long name for a profile"},
           "configName": "6238 (Popcorn Penguins)", "sliced": True})
    for step in STEPS:
        w.set({"step": step})
        assert no_sideways_scroll(w.page) == [], (width, step)
    assert w.problems == []


def test_below_480_px_the_tabs_are_circles_with_the_current_ones_name(wizard):
    w = wizard(479)
    w.set({"step": "layout", "plate": PLATE})
    names = w.page.locator("#stepbar li .sn")
    assert [names.nth(i).is_visible() for i in range(5)] == [False, False, True, False, False]
    assert w.page.locator("#stepbar li.done").count() == 2
    assert w.page.locator("#stepbar li.active").get_attribute("data-step") == "layout"


def test_from_480_px_the_tabs_are_named(wizard):
    w = wizard(480)
    w.set({"step": "layout", "plate": PLATE})
    names = w.page.locator("#stepbar li .sn")
    assert [names.nth(i).is_visible() for i in range(5)] == [True] * 5
    assert w.page.locator("#stepbar li .sn").all_inner_texts() == ["Parts", "Settings", "Layout", "Preview", "Send"]


def test_a_panel_widened_across_480_px_changes_its_tabs_with_no_reload(wizard):
    w = wizard(320)
    assert not w.page.locator("#stepbar li[data-step=send] .sn").is_visible()
    w.width(640)
    assert w.page.locator("#stepbar li[data-step=send] .sn").is_visible()


# ---- the header

def test_the_header_names_the_product_and_the_configuration_with_its_reload_glyph(wizard):
    w = wizard(320)
    assert w.page.locator("#wiz-header .brand").inner_text() == "PenguinSlicer"
    w.set({"configName": None})
    assert not visible(w.page, "#config-status")
    w.set({"configName": "6238 (Popcorn Penguins)"})
    assert w.page.locator("#config-status").inner_text() == "Config: 6238 (Popcorn Penguins)↻"
    w.set({"configName": "PenguinSlicer default"})
    assert w.page.locator("#config-name").inner_text() == "PenguinSlicer default"


def test_the_reload_glyph_asks_its_listener(wizard):
    w = wizard(320)
    w.set({"configName": "6238 (Popcorn Penguins)"})
    w.run("window.reloads = 0; wizard.panel.onReloadConfiguration(() => { window.reloads += 1; });")
    w.page.click("#config-refresh")
    assert w.page.evaluate("window.reloads") == 1


def test_a_hostile_group_name_is_shown_as_text(wizard):
    w = wizard(320)
    w.set({"configName": "<img src=x onerror=\"window.hacked=1\">"})
    assert w.page.locator("#config-name").inner_text() == "<img src=x onerror=\"window.hacked=1\">"
    assert w.page.locator("#config-name img").count() == 0


# ---- the step tabs, the panel line's passing use, Back and Next

def test_a_click_on_a_later_tab_held_by_a_step_says_why_on_the_panel_line(wizard):
    w = wizard(320)
    w.page.click("#stepbar li[data-step=layout]")
    assert w.page.locator("#step-why").inner_text() == "Parts first: add a part."
    assert w.run("return wizard.store.get().step;") == "parts"


def test_the_passing_line_goes_at_the_next_move(wizard):
    w = wizard(320)
    w.page.click("#stepbar li[data-step=layout]")
    w.page.mouse.click(160, 400)
    assert not visible(w.page, "#step-why")


def test_the_passing_line_goes_after_8_s_and_not_before(wizard):
    w = wizard(320)
    w.page.click("#stepbar li[data-step=layout]")
    w.page.clock.run_for(7999)
    assert visible(w.page, "#step-why")
    w.page.clock.run_for(1)
    assert not visible(w.page, "#step-why")


def test_a_click_on_a_tab_goes_there_when_every_step_before_it_allows_it(wizard):
    w = wizard(480)
    w.set({"plate": PLATE})
    w.page.click("#stepbar li[data-step=layout]")
    assert w.run("return wizard.store.get().step;") == "layout"
    w.page.click("#stepbar li[data-step=send]")
    assert w.page.locator("#step-why").inner_text() == "Preview first: the plate is not sliced yet."
    w.page.click("#stepbar li[data-step=parts]")
    assert w.run("return wizard.store.get().step;") == "parts"


def test_a_tab_is_worked_by_keyboard(wizard):
    w = wizard(320)
    w.set({"plate": PLATE})
    w.page.focus("#stepbar li[data-step=settings]")
    w.page.keyboard.press("Enter")
    assert w.run("return wizard.store.get().step;") == "settings"


def test_back_is_off_on_the_parts_step_and_next_is_off_until_the_step_allows_it(wizard):
    w = wizard(320)
    assert w.page.locator("#btn-back").is_disabled()
    assert w.page.locator("#btn-next").is_disabled()
    w.set({"plate": PLATE})
    assert w.page.locator("#btn-next").is_enabled()
    w.page.click("#btn-next")
    assert w.run("return wizard.store.get().step;") == "settings"
    assert w.page.locator("#btn-back").is_enabled()
    w.page.click("#btn-back")
    assert w.run("return wizard.store.get().step;") == "parts"


def test_each_step_shows_only_its_own_body_and_its_title(wizard):
    w = wizard(320)
    w.set({"plate": PLATE, "sliced": True})
    for step, title in zip(STEPS, ["Parts", "Settings", "Layout", "Preview", "Send"]):
        w.set({"step": step})
        assert w.page.locator("section.step:visible h2").all_inner_texts() == [title]


def test_on_the_send_step_the_one_button_is_download_the_sliced_file(wizard):
    w = wizard(320)
    w.set({"plate": PLATE, "sliced": True, "step": "send"})
    assert not visible(w.page, "#btn-next")
    assert w.page.locator("#final-action .btn").all_inner_texts() == ["Download the sliced file"]


# ---- the plate summary

def test_no_summary_on_the_parts_step_and_two_lines_from_the_settings_step(wizard):
    w = wizard(320)
    w.set({"plate": PLATE})
    assert not visible(w.page, "#wiz-summary")
    for step in STEPS[1:]:
        w.set({"step": step, "sliced": True})
        assert w.page.locator("#wiz-summary .sum-line").all_inner_texts() == ["1 part · 1 instance", "PETG · Structural"]


def test_the_summary_updates_at_once(wizard):
    w = wizard(320)
    w.set({"plate": PLATE, "step": "settings"})
    w.set({"plate": {**PLATE, "parts": 3, "instances": 16, "changes": CHANGES}})
    assert w.page.locator("#wiz-summary .sum-line").first.inner_text() == "3 parts · 16 instances"
    assert w.page.locator("#chg-chip").inner_text() == "+2 changes"


def test_a_long_profile_name_is_cut_with_an_ellipsis_and_has_its_tooltip(wizard):
    w = wizard(320)
    long = "Structural, strong and slow, for the parts that hold the robot together"
    w.set({"plate": {**PLATE, "profile": long, "changes": CHANGES}, "step": "settings"})
    text = w.page.locator("#wiz-summary .sum-text")
    assert text.evaluate("e => e.scrollWidth > e.clientWidth")
    assert text.evaluate("e => getComputedStyle(e).textOverflow") == "ellipsis"
    assert w.page.locator("#chg-chip").evaluate("e => e.scrollWidth <= e.clientWidth")
    text.hover()
    w.page.clock.run_for(150)
    assert w.page.locator("#wiz-tip").inner_text() == f"PETG · {long}"


def test_nothing_below_the_summary_moves_when_the_pill_comes_or_goes(wizard):
    w = wizard(320)
    w.set({"plate": PLATE, "step": "settings"})
    before = w.page.locator("section.step[data-step=settings] h2").bounding_box()["y"]
    w.set({"plate": {**PLATE, "changes": CHANGES}})
    assert w.page.locator("section.step[data-step=settings] h2").bounding_box()["y"] == before


@pytest.mark.parametrize("close", ["elsewhere", "escape", "pill"])
def test_the_pill_opens_the_change_details_and_each_of_three_ways_closes_them(wizard, close):
    w = wizard(320)
    w.set({"plate": {**PLATE, "changes": CHANGES}, "step": "settings"})
    w.page.click("#chg-chip")
    assert w.page.locator("#chg-pop li").all_inner_texts() == [
        "Quality › Resolution: 0.014 mm (profile 0.012 mm)", "Others › Brim: Off (profile Auto)"]
    assert w.page.locator("#chg-chip").get_attribute("aria-expanded") == "true"
    if close == "elsewhere":
        w.page.mouse.click(160, 500)
    elif close == "escape":
        w.page.keyboard.press("Escape")
    else:
        w.page.click("#chg-chip")
    assert not visible(w.page, "#chg-pop")
    assert w.page.locator("#chg-chip").get_attribute("aria-expanded") == "false"


def test_the_change_details_stay_inside_a_320_px_panel(wizard):
    w = wizard(320)
    w.set({"plate": {**PLATE, "changes": CHANGES}, "step": "settings"})
    w.page.click("#chg-chip")
    box = w.page.locator("#chg-pop").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 320


# ---- the tooltips

def test_a_step_circles_tooltip_shows_at_150_ms_of_rest_and_not_at_149(wizard):
    w = wizard(320)
    w.page.hover("#stepbar li[data-step=layout]")
    w.page.clock.run_for(149)
    assert not visible(w.page, "#wiz-tip")
    w.page.clock.run_for(1)
    assert visible(w.page, "#wiz-tip")
    assert w.page.locator("#wiz-tip").inner_text() == "3. Layout"


def test_the_current_circle_and_the_named_tabs_have_no_tooltip(wizard):
    w = wizard(320)
    w.page.hover("#stepbar li[data-step=parts]")
    w.page.clock.run_for(1000)
    assert not visible(w.page, "#wiz-tip")
    w.width(480)
    w.page.hover("#stepbar li[data-step=layout]")
    w.page.clock.run_for(1000)
    assert not visible(w.page, "#wiz-tip")


def test_a_tooltip_shows_at_once_on_keyboard_focus_of_a_step_circle(wizard):
    w = wizard(320)
    w.page.keyboard.press("Tab")            # the reload glyph is hidden: the first stop is a circle
    w.page.focus("#stepbar li[data-step=parts]")
    w.page.keyboard.press("Tab")
    assert w.page.evaluate("document.activeElement.dataset.step") == "settings"
    assert visible(w.page, "#wiz-tip")
    assert w.page.locator("#wiz-tip").inner_text() == "2. Settings"


@pytest.mark.parametrize("end", ["leave", "press", "escape"])
def test_a_tooltip_goes_on_leave_press_and_escape(wizard, end):
    w = wizard(320)
    w.page.hover("#stepbar li[data-step=layout]")
    w.page.clock.run_for(150)
    assert visible(w.page, "#wiz-tip")
    if end == "leave":
        w.page.mouse.move(160, 600)
    elif end == "press":
        w.page.mouse.down()
        w.page.mouse.up()
    else:
        w.page.keyboard.press("Escape")
    assert not visible(w.page, "#wiz-tip")


def test_at_the_panels_edge_a_tooltip_stays_6_px_inside_a_320_px_panel(wizard):
    w = wizard(320)
    w.page.hover("#stepbar li[data-step=send]")
    w.page.clock.run_for(150)
    box = w.page.locator("#wiz-tip").bounding_box()
    assert box["x"] >= 6 - 0.01
    assert box["x"] + box["width"] <= 320 - 6 + 0.01


def test_the_tooltip_is_the_panels_own_white_box_at_14_px(wizard):
    w = wizard(320)
    w.page.hover("#stepbar li[data-step=layout]")
    w.page.clock.run_for(150)
    style = w.page.locator("#wiz-tip").evaluate(
        "e => { const s = getComputedStyle(e); return [s.fontSize, s.backgroundColor, s.borderTopColor, s.borderTopLeftRadius]; }")
    assert style == ["14px", "rgb(255, 255, 255)", "rgb(208, 215, 222)", "8px"]


def test_an_element_whose_text_shows_in_full_has_no_tooltip(wizard):
    w = wizard(320)
    w.set({"plate": {**PLATE, "changes": CHANGES}, "step": "settings"})
    w.page.hover("#wiz-summary .sum-text")
    w.page.clock.run_for(1000)
    assert not visible(w.page, "#wiz-tip")


# ---- the six ways of telling

def test_a_notification_sits_under_the_summary_and_closes_with_its_cross(wizard):
    w = wizard(320)
    w.set({"plate": PLATE, "step": "settings"})
    w.run("wizard.panel.notify({kind: 'error', what: 'Bracket was not added.', todo: 'Upload it again.', key: 'k'});")
    assert w.page.locator("#notices .notice.error .n-what").inner_text() == "Bracket was not added."
    assert w.page.locator("#notices .notice .n-todo").inner_text() == "Upload it again."
    w.page.click("#notices .notice .n-x")
    assert w.page.locator("#notices .notice").count() == 0


def test_a_notification_goes_when_the_user_leaves_its_step_or_it_stops_being_true(wizard):
    w = wizard(320)
    w.set({"plate": PLATE, "step": "settings"})
    w.run("wizard.panel.notify({kind: 'ok', what: 'One.', key: 'one'}); wizard.panel.notify({kind: 'ok', what: 'Two.', key: 'two'});")
    w.run("wizard.panel.dropNotice('one');")
    assert w.page.locator("#notices .n-what").all_inner_texts() == ["Two."]
    w.set({"step": "layout"})
    assert w.page.locator("#notices .notice").count() == 0


def test_a_message_in_each_of_its_colours_with_its_buttons_and_details(wizard):
    w = wizard(320)
    w.set({"plate": PLATE, "step": "settings"})
    for kind in ["error", "warn", "info", "ok"]:
        w.run("""document.querySelector('section.step[data-step=settings]').append(wizard.panel.tell.message({
            kind: arg, what: 'What happened.', todo: 'What to do.', details: 'Orca Slicer: a sentence.',
            actions: [{label: 'Back to Layout', onClick: () => { window.pressed = arg; }}]}));""", kind)
        message = w.page.locator(f".msg.{kind}")
        assert message.locator(".what").inner_text() == "What happened."
        assert message.locator(".todo").inner_text() == "What to do."
        message.locator("summary").click()
        assert message.locator("details div").inner_text() == "Orca Slicer: a sentence."
        message.locator(".acts button").click()
        assert w.page.evaluate("window.pressed") == kind


def test_a_card_and_a_line(wizard):
    w = wizard(320)
    w.run("""const s = document.querySelector('section.step[data-step=parts]');
             s.append(wizard.panel.tell.card('A state that lasts.'), wizard.panel.tell.line('A consequence the user cannot see.'));""")
    assert w.page.locator("section.step .card").inner_text() == "A state that lasts."
    assert w.page.locator("section.step[data-step=parts] p.hint").last.inner_text() == "A consequence the user cannot see."


@pytest.mark.parametrize("answer, expected", [("go", True), ("keep", False), ("escape", False), ("elsewhere", False)])
def test_a_confirmation_goes_ahead_only_on_its_button(wizard, answer, expected):
    w = wizard(320)
    w.run("""const b = document.createElement('button'); b.id = 'new-plate'; b.className = 'btn small'; b.textContent = 'New plate';
             document.querySelector('section.step[data-step=parts]').append(b);
             window.answer = wizard.panel.tell.confirm(b, {question: 'Start a new plate? The parts on this plate are dropped.',
                                                            go: 'New plate', keep: 'Keep this plate'});""")
    assert w.page.locator(".confirm-pop p").inner_text() == "Start a new plate? The parts on this plate are dropped."
    box = w.page.locator(".confirm-pop").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 320
    if answer == "go":
        w.page.click(".confirm-pop .btn.primary")
    elif answer == "keep":
        w.page.click(".confirm-pop .btn:not(.primary)")
    elif answer == "escape":
        w.page.keyboard.press("Escape")
    else:
        w.page.mouse.click(160, 600)
    assert w.page.evaluate("window.answer") is expected
    assert w.page.locator(".confirm-pop").count() == 0


def test_a_confirmation_puts_its_keep_button_first_and_focused_so_enter_keeps_things(wizard):
    w = wizard(320)
    w.run("""const b = document.createElement('button'); b.id = 'new-plate'; b.className = 'btn small'; b.textContent = 'New plate';
             document.querySelector('section.step[data-step=parts]').append(b);
             window.answer = wizard.panel.tell.confirm(b, {question: 'Start a new plate? The parts and layout of this one are cleared.',
                                                            go: 'New plate', keep: 'Keep this plate'});""")
    assert w.page.locator(".confirm-pop .acts button").all_inner_texts() == ["Keep this plate", "New plate"]
    assert w.page.evaluate("document.activeElement.textContent") == "Keep this plate"
    assert w.page.evaluate("document.activeElement.closest('.confirm-pop') !== null") is True
    w.page.keyboard.press("Enter")
    assert w.page.evaluate("window.answer") is False
    assert w.page.locator(".confirm-pop").count() == 0


def test_hostile_sentences_are_shown_as_text(wizard):
    w = wizard(320)
    w.set({"plate": PLATE, "step": "settings"})
    w.run("wizard.panel.notify({kind: 'error', what: '<img src=x onerror=\"window.hacked=1\">', todo: '<b>bold</b>'});")
    assert w.page.locator("#notices .n-what").inner_text() == '<img src=x onerror="window.hacked=1">'
    assert w.page.locator("#notices img, #notices b").count() == 0


# ---- the panel line's lasting use: retrying

def attempt(w, path, run_ms):
    """Once the page is waiting to retry, moves its clock on by run_ms and waits for its next
    request to `path` to fail: events, not durations."""
    w.until("return wizard.api.waiting() === 1;")
    with w.page.expect_event("requestfailed", predicate=lambda r: r.url.endswith(path)):
        w.page.clock.run_for(run_ms)


def test_the_retry_messages_on_the_panel_line(wizard):
    w = wizard(320)
    w.page.route("**/api/me", lambda route: route.abort())
    with w.page.expect_event("requestfailed"):
        w.run("window.me = wizard.api.get('/api/me');")
    for wait in [1000, 2000, 4000, 8000]:                    # attempts at 1, 3, 7, 15 s
        attempt(w, "/api/me", wait)
    w.until("return wizard.api.waiting() === 1;")
    w.page.clock.run_for(4999)                               # 19.999 s
    assert not visible(w.page, "#step-why")
    w.page.clock.run_for(1)                                  # 20 s
    line = w.page.locator("#step-why")
    assert line.evaluate("e => e.firstChild.textContent") == "The server is being slow. Your browser is retrying in 11 s. "
    assert line.locator("button").inner_text() == "Retry now"
    assert line.evaluate("e => getComputedStyle(e).color") == "rgb(154, 103, 0)"       # amber, #9a6700
    w.page.clock.run_for(1000)
    assert "retrying in 10 s." in line.inner_text()
    with w.page.expect_event("requestfailed"):
        line.locator("button").click()                     # Retry now, at 21 s: at once
    w.until("return wizard.api.waiting() === 1;")
    assert "retrying in 30 s." in line.inner_text()
    for _ in range(9):                                       # attempts at 51, 81 … 291 s
        attempt(w, "/api/me", 30000)
    w.until("return wizard.api.waiting() === 1;")
    assert "retrying in 9 s." in line.inner_text()           # 291 s: counting down to the last attempt, at 300 s
    w.page.clock.run_for(8000)                               # 299 s
    assert "retrying in 1 s." in line.inner_text()
    with w.page.expect_event("requestfailed"):
        w.page.clock.run_for(1000)                           # 300 s: the last attempt
    w.until("return wizard.api.waiting() === 1;")
    assert line.evaluate("e => e.firstChild.textContent") == "The server could not be reached. "
    assert line.locator("button").inner_text() == "Try again"
    assert line.evaluate("e => getComputedStyle(e).color") == "rgb(209, 36, 47)"       # red
    w.page.unroute("**/api/me")
    line.locator("button").click()
    w.page.wait_for_function("() => !document.getElementById('step-why').textContent.includes('reached')")
    assert w.page.evaluate("window.me.then(r => r.ok)") is True
    assert not visible(w.page, "#step-why")


def test_while_the_retry_message_shows_a_held_click_shows_no_passing_line(wizard):
    w = wizard(320)
    w.page.route("**/api/me", lambda route: route.abort())
    with w.page.expect_event("requestfailed"):
        w.run("wizard.api.get('/api/me');")
    for wait in [1000, 2000, 4000, 8000]:
        attempt(w, "/api/me", wait)
    w.until("return wizard.api.waiting() === 1;")
    w.page.clock.run_for(5000)
    w.page.click("#stepbar li[data-step=layout]")
    assert "The server is being slow." in w.page.locator("#step-why").inner_text()


def test_every_request_carries_the_page_version_and_every_change_the_mark(wizard):
    w = wizard(320)
    w.run("await wizard.api.get('/api/me'); await wizard.store.set({group: 'g-1'}); await wizard.api.post('/api/slices', {json: {}});")
    sent = [(m, p, h) for (m, p, h) in w.server.request_headers[w.opening_requests:] if p.startswith("/api/")]
    assert [(m, p) for m, p, _ in sent] == [("GET", "/api/me"), ("POST", "/api/slices")]
    for _, _, headers in sent:
        assert headers["x-penguinslicer-page"] == w.server.version
    assert "x-penguinslicer-wizard" not in sent[0][2]
    assert sent[1][2]["x-penguinslicer-wizard"] == "1"
    assert sent[1][2]["x-penguinslicer-group"] == "g-1"


def test_a_refusal_with_sentences_reaches_the_caller_as_they_are(wizard):
    w = wizard(320)
    w.server.script("POST", "/api/slices", (503, error_report("slice.busy", retryable=True)))
    result = w.run("return await wizard.api.post('/api/slices', {json: {}});")
    assert result == {"ok": False, "status": 503, "report": error_report("slice.busy", retryable=True)}
