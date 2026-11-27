"""wizard/trials/serve.py: serves wizard/trials/ at /, wizard/vendor/ at /vendor/ and the real
parts at /parts/real/, and nothing outside them."""
import http.client
import threading
from pathlib import Path

import pytest

from trials import serve

WIZARD = Path(__file__).resolve().parents[2]
REAL = WIZARD.parent / "contracts" / "examples" / "parts" / "real"


@pytest.fixture(scope="module")
def server():
    httpd = serve.make_server("127.0.0.1", 0)        # a port the system chooses
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def get(port, path, method="GET"):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        connection.close()


def test_the_trials_folder_is_served_at_the_root(server):
    status, _, body = get(server, "/parts/hex-spacer.stl")
    assert status == 200
    assert body == (WIZARD / "trials" / "parts" / "hex-spacer.stl").read_bytes()


def test_the_vendored_code_is_served_as_javascript(server):
    status, content_type, body = get(server, "/vendor/three/build/three.module.min.js")
    assert status == 200
    assert content_type.split(";")[0] == "text/javascript"
    assert body == (WIZARD / "vendor" / "three" / "build" / "three.module.min.js").read_bytes()


def test_the_real_parts_are_served(server):
    status, _, body = get(server, "/parts/real/pulley-v3.stl")
    assert status == 200
    assert body == (REAL / "pulley-v3.stl").read_bytes()


@pytest.mark.parametrize("path", ["/../Makefile", "/vendor/../Makefile", "/vendor/../../CLAUDE.md",
                                  "/parts/real/../README.md", "/parts/real/../../part-set.json",
                                  "/%2e%2e/Makefile", "/vendor/%2e%2e/%2e%2e/CLAUDE.md",
                                  "/vendor/../make_parts.py", "/parts/real/%2e%2e/hex-spacer.stl",
                                  "/parts/", "/vendor/three/"])
def test_nothing_outside_the_three_folders_is_served(server, path):
    status, _, _ = get(server, path)
    assert status == 404


def test_a_missing_file_is_404(server):
    assert get(server, "/no-such-file.html")[0] == 404


def test_only_get_and_head_are_answered(server):
    assert get(server, "/parts/hex-spacer.stl", method="HEAD")[0] == 200
    assert get(server, "/parts/hex-spacer.stl", method="POST")[0] == 501


def test_answers_are_never_cached(server):
    connection = http.client.HTTPConnection("127.0.0.1", server, timeout=30)
    try:
        connection.request("GET", "/parts/hex-spacer.stl")
        response = connection.getresponse()
        response.read()
        assert response.getheader("Cache-Control") == "no-store"
    finally:
        connection.close()


def test_the_command_line_names_the_address(capsys):
    args = serve.parse_args(["--host", "0.0.0.0", "--port", "21234"])
    assert (args.host, args.port) == ("0.0.0.0", 21234)
    assert serve.parse_args([]).port == 8610
    assert serve.parse_args([]).host == "127.0.0.1"
