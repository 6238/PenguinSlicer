"""The sign-in across a restart of the front server, in a browser. On one machine the front
server may be started with no cookie key, and then makes one at each start, so a restart makes
every cookie unreadable: the open page's next request is answered `front.not_signed_in`, the page
makes the trip, and `/signin` signs the development identity in again at once, so nothing is lost
(front/README-details.md, "The cookie key on one machine"; docs/architecture.md, "The front server
restarts"). The joined suite found the page showing the refusal instead
(docs/orchestration/phase-2/seam-wizard-front.md)."""

import secrets

from joined.plates import CLAMP_PLATE


def test_an_open_page_signs_in_again_by_the_trip_when_the_front_server_restarts_with_a_new_key(
        wizard, wizard_front):
    w = wizard()
    w.add_parts([CLAMP_PLATE])
    w.next("settings")
    w.next("layout")
    w.layout_settled(1)

    wizard_front.stop()
    wizard_front.cookie_key = secrets.token_urlsafe(32)
    wizard_front.restart()
    # Entering the Preview step submits the plate; the answer is front.not_signed_in, the page
    # goes on the trip and comes back to the same step with the plate as it was, and slices.
    with w.page.expect_navigation():
        w.page.click("#btn-next")
    w.wait_opened()
    assert w.step() == "preview"
    details = w.sliced()
    assert details["summary"]["instances"] == 1
    # The first trip is the opening's (`/` with no cookie); the second, the page's own.
    trips = [(method, path) for method, path, status in w.answers if path.startswith("/signin")]
    assert trips == [("GET", "/signin?return=%2F")] * 2
    assert w.run("return sessionStorage.getItem('penguinslicer.sign_in_trip');") == ""
    assert w.problems == []
