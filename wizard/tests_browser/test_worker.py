"""The worker in Chromium (wizard/README-details.md, "The geometry, in a worker"): the page's own
worker, started from its built files under the contract's content security policy, reads a binary
STL and draws the part's picture; a malformed file ends in the worker's error report. The page is
left on the real clock, and its heartbeat measures the longest hold of the main thread while the
test waits for the worker's answer, an event: it stays under the 250 ms of the guide."""
from pathlib import Path

import pytest

from tests_browser.conftest import Wizard

WIZARD = Path(__file__).resolve().parent.parent
REAL = WIZARD.parent / "contracts" / "examples" / "parts" / "real"
MADE = WIZARD / "trials" / "parts"
MAIN_THREAD_HOLD_MS = 250


def open_page(page, server, files):
    for name, path in files.items():
        server.files[f"/test-files/{name}"] = path.read_bytes()
    return Wizard(page, server, fake_clock=False)


DRAW = """
    const bytes = await (await fetch('/test-files/' + arg.name)).arrayBuffer();
    const { partPicture } = await import(arg.picture);
    wizard.holdMeter.start();
    const read = await wizard.geometry.read(arg.name, bytes, 'mm');
    let picture = null;
    if (read.ok) {
        picture = await partPicture({ geometry: wizard.geometry, key: arg.name, colour: 0x9fb4c8, pixelRatio: 2, document });
        if (picture.ok) { picture.canvas.id = 'picture-' + arg.name.replace('.', '-'); document.body.append(picture.canvas); }
    }
    const held = wizard.holdMeter.stop();
    let drawn = 0;
    if (picture && picture.ok) {
        const data = picture.canvas.getContext('2d').getImageData(0, 0, picture.canvas.width, picture.canvas.height).data;
        for (let i = 3; i < data.length; i += 4) if (data[i] > 0) drawn += 1;
    }
    return { read: read.ok ? read.result.triangles : read.error, picture: picture && picture.ok ? [picture.canvas.width, picture.canvas.className] : null, drawn, held, bytes: bytes.byteLength };
"""


def assets(w, prefix):
    """The built address of a page module, `prefix.<hash>.js` in wizard/dist/assets/."""
    (found,) = (WIZARD / "dist" / "assets").glob(f"{prefix}.????????????.js")
    return f"/assets/{found.name}"


@pytest.mark.parametrize("name, folder, triangles", [("pulley-v3.stl", REAL, 4608), ("hub-150k.stl", MADE, 150_000)])
def test_the_worker_reads_a_binary_stl_and_draws_its_picture_without_holding_the_page(page, front_server, name, folder, triangles):
    w = open_page(page, front_server, {name: folder / name})
    result = w.run(DRAW, {"name": name, "picture": assets(w, "part-picture")})
    assert result["read"] == triangles
    assert result["picture"] == [88, "thumb"]
    assert result["drawn"] > 88 * 88 * 0.1
    assert result["held"] < MAIN_THREAD_HOLD_MS, result
    assert w.problems == []


def test_a_malformed_stl_ends_in_the_worker_report_without_holding_the_page(page, front_server):
    # A file of the largest size whose header claims more triangles than its length holds.
    bad = bytearray(7_500_084)
    bad[80:84] = (150_001).to_bytes(4, "little")
    front_server.files["/test-files/bad.stl"] = bytes(bad)
    w = Wizard(page, front_server, fake_clock=False)
    result = w.run(DRAW, {"name": "bad.stl", "picture": assets(w, "part-picture")})
    assert result["read"]["code"] == "wizard.part_not_drawable"
    assert result["read"]["message"] == "PenguinSlicer could not show this part, so it cannot be imported."
    assert result["picture"] is None
    assert result["held"] < MAIN_THREAD_HOLD_MS, result
    assert w.problems == []
