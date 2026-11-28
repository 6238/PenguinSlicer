"""The log across the seam: the front server gathers the slice service's lines
(`GET /log?after=<n>`) into the log folder, each placed in its group, none twice."""

from joined.plates import clamp_plate


def test_the_gathered_log_holds_the_slice_services_lines_in_their_group(page, slice_service, front_server):
    accepted = page.submit(clamp_plate(page))
    assert page.stream(accepted["id"]).wait_closed().final["state"] == "done"

    # The front server gathers once at start and then once a minute. A front server started
    # now gathers at once, from where the one before it stopped; it is stopped once the
    # slice service has answered its request, and its stop writes what it gathered.
    front_server.stop()
    since = slice_service.running.mark()
    front_server.restart()
    slice_service.running.wait_for_line(lambda line: '"GET /log?after=' in line.text,
                                        "the new front server asking for the log", since=since)
    front_server.stop()

    gathered = sorted((line for line in front_server.gathered() if line.get("component") == "slice"),
                      key=lambda line: line["n"])
    own = slice_service.lines()
    assert [line["n"] for line in gathered] == list(range(1, len(gathered) + 1)), "each line once"
    assert len(gathered) >= len([line for line in own if line.get("event") == "slice_job"])
    of_the_job = [line for line in gathered if line.get("job") == accepted["id"]]
    states = [line["state"] for line in of_the_job if line["event"] == "slice_job"]
    assert states[0] == "queued" and "done" in states and "file_deleted" in states
    for line in of_the_job:
        assert (line["user_key"], line["group"]) == ("dev-user", "dev-group")
        assert line["time"].endswith("Z") and len(line["time"]) == len("2026-11-27T22:14:05.123Z")
    # Each gathered line is the slice service's line as it wrote it, with `n` and the group.
    written = {(line.get("event"), line.get("state"), line.get("job")) for line in own}
    assert all((line.get("event"), line.get("state"), line.get("job")) in written for line in gathered)
