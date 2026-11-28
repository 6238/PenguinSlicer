"""Serving the wizard's pages (README-details.md, "Serving the wizard's pages"; contracts/
wizard-front-server.md, "The page files and the version" and "The wizard's built files")."""

import io
import json
import re

import pytest

from front_helpers import ASSETS, PLACEHOLDER, VERSION, environ, front, make_dist, sign_in
from penguin_front.pages import CSP_HOSTED, CSP_ONE_MACHINE, PagesUnusable, load_pages
from penguin_front.server import serve
from penguin_front.__main__ import parse_args

#: The contract's whole content security policy, as it stands in the contract.
CONTRACT_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
                "worker-src 'self' blob:; object-src 'none'; base-uri 'none'; "
                "form-action 'self'; frame-ancestors 'self'")
ASSET = "panel.3f9a1c2b7e04.js"


@pytest.fixture
def app(tmp_path, clock):
    return front(tmp_path, clock)


@pytest.fixture
def client(app):
    return app.test_client()


def wizard_bytes():
    """Byte strings that occur only in the wizard's built files."""
    return [b"/assets/panel.3f9a1c2b7e04.js", b"penguinslicer-version"] + \
        [data for data in ASSETS.values()]


# Not signed in.

@pytest.mark.parametrize("target, back", [
    ("/", "/"), ("/?plate=2", "/?plate=2"), ("/?in=x&a=%2F", "/?in=x&a=%2F"),
])
def test_the_page_without_a_cookie_sends_the_browser_to_signin_with_return(client, target,
                                                                         back):
    answer = client.get(target)
    assert answer.status_code == 302
    location = answer.headers["Location"]
    assert location.startswith("/signin?return=")
    followed = client.get(location)
    assert followed.headers["Location"] == back
    assert not any(part in answer.data for part in wizard_bytes())
    assert answer.headers["Cache-Control"] == "no-store"


def test_raw_bytes_in_the_query_are_kept_as_sent_through_the_sign_in(client):
    # A client that is not a browser may send "é" as its two UTF-8 bytes, unencoded; the
    # server gives them as the Latin-1 text WSGI uses for bytes.
    answer = client.get("/", environ_overrides={"QUERY_STRING": "q=\xc3\xa9"})
    assert answer.headers["Location"] == "/signin?return=%2F%3Fq%3D%C3%A9"
    assert client.get(answer.headers["Location"]).headers["Location"] == "/?q=%C3%A9"


def test_the_trip_from_the_page_comes_back_signed_in_to_the_page(client):
    first = client.get("/?plate=2")
    back = client.get(first.headers["Location"]).headers["Location"]
    page = client.get(back)
    assert page.status_code == 200 and b"/assets/panel.3f9a1c2b7e04.js" in page.data


def test_an_asset_without_a_cookie_is_front_not_signed_in(client):
    answer = client.get(f"/assets/{ASSET}")
    assert answer.status_code == 401
    assert answer.get_json()["code"] == "front.not_signed_in"
    assert ASSETS[ASSET] not in answer.data


# Signed in.

def test_the_page_carries_its_version_in_its_meta_and_is_private_no_cache(client):
    sign_in(client)
    answer = client.get("/")
    assert answer.status_code == 200 and answer.mimetype == "text/html"
    text = answer.get_data(as_text=True)
    assert f'<meta name="penguinslicer-version" content="{VERSION}">' in text
    assert "__PENGUINSLICER_VERSION__" not in text
    assert answer.headers["Cache-Control"] == "private, no-cache"
    assert answer.headers["X-PenguinSlicer-Version"] == VERSION


def test_a_head_of_the_page_is_answered(client):
    sign_in(client)
    answer = client.head("/")
    assert answer.status_code == 200 and answer.data == b""


@pytest.mark.parametrize("name", sorted(ASSETS))
def test_an_asset_is_served_as_built_and_kept_for_a_year(client, name):
    sign_in(client)
    answer = client.get(f"/assets/{name}")
    assert answer.status_code == 200 and answer.data == ASSETS[name]
    assert answer.headers["Cache-Control"] == "private, max-age=31536000, immutable"
    assert answer.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("name, kind", [
    ("panel.3f9a1c2b7e04.js", "text/javascript"), ("panel.0a1b2c3d4e5f.css", "text/css"),
    ("plex-sans.9f8e7d6c5b4a.woff2", "font/woff2"),
])
def test_an_asset_is_served_with_its_kind(client, name, kind):
    sign_in(client)
    assert client.get(f"/assets/{name}").mimetype == kind


@pytest.mark.parametrize("name", ["panel.000000000000.js", "index.html", "..", ".hidden",
                                  "panel.3F9A1C2B7E04.js", "sub", "%2e%2e"])
def test_an_asset_this_release_does_not_have_is_404(client, name):
    sign_in(client)
    answer = client.get(f"/assets/{name}")
    assert answer.status_code == 404
    assert answer.get_json()["code"] == "front.no_such_request"


def test_an_asset_path_with_a_folder_is_404(client):
    sign_in(client)
    assert client.get("/assets/sub/x.js").get_json()["code"] == "front.no_such_request"


def test_the_assets_are_read_at_start_and_a_rebuild_changes_nothing_served(tmp_path, clock):
    app = front(tmp_path, clock)
    client = app.test_client()
    sign_in(client)
    (tmp_path / "dist" / "assets" / ASSET).write_bytes(b"rebuilt")
    (tmp_path / "dist" / "assets" / "new.111111111111.js").write_bytes(b"new")
    (tmp_path / "dist" / "index.html").write_text("rebuilt " + PLACEHOLDER)
    assert client.get(f"/assets/{ASSET}").data == ASSETS[ASSET]
    assert client.get("/assets/new.111111111111.js").status_code == 404
    assert b"rebuilt" not in client.get("/").data


# The content security policy.

def test_every_page_answer_carries_the_contracts_whole_policy_on_one_machine(client):
    assert CSP_ONE_MACHINE == CONTRACT_CSP
    sign_in(client)
    assert client.get("/").headers["Content-Security-Policy"] == CONTRACT_CSP


def test_the_policy_names_onshape_alone_as_frame_ancestor_hosted(tmp_path, clock):
    assert CSP_HOSTED == CONTRACT_CSP.replace("frame-ancestors 'self'",
                                              "frame-ancestors https://cad.onshape.com")
    app = front(tmp_path, clock, PENGUIN_BASE_URL="https://penguinslicer.popcornpenguins.com")
    client = app.test_client()
    sign_in(client)
    assert client.get("/").headers["Content-Security-Policy"] == CSP_HOSTED


def test_the_contract_states_the_policy_this_file_checks():
    from test_rules import CONTRACT

    assert f"Content-Security-Policy: {CONTRACT_CSP}" in CONTRACT.read_text()


# Starting without the page files.

def test_a_folder_without_index_html_cannot_be_loaded(tmp_path):
    folder = make_dist(tmp_path / "dist", index=False)
    with pytest.raises(PagesUnusable, match=re.escape(str(folder))):
        load_pages(folder, VERSION)


def test_an_index_html_without_the_placeholder_cannot_be_loaded(tmp_path):
    folder = make_dist(tmp_path / "dist", placeholder=False)
    with pytest.raises(PagesUnusable, match="placeholder"):
        load_pages(folder, VERSION)


def test_a_folder_that_is_not_there_cannot_be_loaded(tmp_path):
    with pytest.raises(PagesUnusable, match="index.html"):
        load_pages(tmp_path / "nothing", VERSION)


def test_a_folder_without_assets_serves_the_page_and_no_asset(tmp_path):
    folder = tmp_path / "dist"
    folder.mkdir()
    (folder / "index.html").write_text(PLACEHOLDER)
    pages = load_pages(folder, VERSION)
    assert pages.assets == {} and VERSION.encode() in pages.index


def test_an_index_html_that_is_not_utf8_cannot_be_loaded(tmp_path):
    folder = make_dist(tmp_path / "dist")
    (folder / "index.html").write_bytes(b"\xff\xfe" + PLACEHOLDER.encode())
    with pytest.raises(PagesUnusable, match="UTF-8"):
        load_pages(folder, VERSION)


def test_folders_inside_assets_are_not_served(tmp_path):
    folder = make_dist(tmp_path / "dist")
    (folder / "assets" / "sub").mkdir()
    (folder / "assets" / "sub" / "x.js").write_bytes(b"x")
    assert "sub" not in load_pages(folder, VERSION).assets


@pytest.mark.parametrize("index, placeholder", [(False, True), (True, False)])
def test_a_start_without_usable_page_files_stops_with_a_line_naming_the_folder(tmp_path, clock,
                                                                             index,
                                                                             placeholder):
    folder = make_dist(tmp_path / "dist", index=index, placeholder=placeholder)
    stdout, stderr = io.StringIO(), io.StringIO()
    status = serve(parse_args(["serve", "--port", "0"]), environ=environ(tmp_path),
                   stdout=stdout, stderr=stderr, clock=clock)
    assert status == 2
    [line] = [json.loads(text) for text in stdout.getvalue().splitlines()]
    assert line["event"] == "start_refused" and line["setting"] == "PENGUIN_WIZARD_DIST"
    assert str(folder) in line["detail"] and str(folder) in stderr.getvalue()


def test_with_the_version_unset_the_page_carries_the_start_moment(tmp_path, clock):
    app = front(tmp_path, clock, version=None, PENGUIN_VERSION=None)
    client = app.test_client()
    sign_in(client)
    assert 'content="20261127T221405Z-0000000"' in client.get("/").get_data(as_text=True)
