"""The built page loads in Chromium under the contract's content security policy, runs its
code, and reads the version the front server filled in."""
import json


def open_page(page, front_server):
    problems = []
    page.on("console", lambda message: problems.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: problems.append(str(error)))
    page.goto(front_server.url)
    page.wait_for_selector('html[data-started="true"]', state="attached")   # an event, bounded by Playwright's timeout
    return problems


def test_the_page_runs_its_code_with_no_error_under_the_content_security_policy(page, front_server):
    assert open_page(page, front_server) == []


def test_an_inline_script_would_be_seen_as_a_problem(page, front_server):
    """The check above can fail: the policy refuses an inline script, and Chromium says so."""
    problems = open_page(page, front_server)
    with page.expect_console_message(lambda message: message.type == "error"):
        page.evaluate("""() => { const s = document.createElement('script');
                                 s.textContent = 'window.ran = true'; document.head.append(s); }""")
    assert page.evaluate("() => window.ran === undefined")
    assert any("Content Security Policy" in text for text in problems)


def test_the_page_reads_its_version_from_its_meta(page, front_server):
    open_page(page, front_server)
    assert page.evaluate("() => document.documentElement.dataset.version") == front_server.version


def test_the_page_asks_only_for_itself_its_assets_and_what_it_opens_with(page, front_server):
    open_page(page, front_server)
    page.wait_for_selector('html[data-opened="true"]', state="attached")
    assert front_server.requests[0] == "/"
    assert len(front_server.requests) > 1
    others = [path for path in front_server.requests[1:] if not path.startswith("/assets/") and path != "/favicon.ico"]
    assert sorted(others) == ["/api/configuration", "/api/me", "/api/settings-table"]


def test_an_opening_that_throws_is_sent_as_a_page_failed_report_and_marks_the_page_failed(page, front_server):
    """The page's entry point joins the opening's end to the reports: a fault of the page's own
    code while it opens, made here by a structuredClone that throws, reaches the front server."""
    page.add_init_script("globalThis.structuredClone = () => { throw new TypeError('made to fail by the test'); };")
    with page.expect_request(lambda r: r.url.endswith("/api/reports/failure")) as sent:
        page.goto(front_server.url)
        page.wait_for_selector('html[data-opened="failed"]', state="attached")
    body = json.loads(sent.value.post_data)
    assert body["what"] == "page_failed"
    assert body["detail"] == "opening the page: TypeError: made to fail by the test"
