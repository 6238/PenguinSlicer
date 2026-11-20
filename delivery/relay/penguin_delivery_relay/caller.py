"""What the caller hands the relay.

The caller is the application that runs the relay and asks it to deliver sliced files: it
signs its users in, knows their team's pairing code, and has the sliced file. The relay
knows nothing of how any of that works. The caller answers two questions through the
functions it gives create_app:

- `identify(request)` -- who is asking? It returns a Team, or None when the request carries
  no identity the caller vouches for (the relay answers 401). The relay calls it on both
  caller routes, `GET /printer/status` and `POST /printer/jobs`, so a caller that caches
  identity can refresh it there. If it raises, the relay logs the exception; a status poll
  reads as a team with no pairing code (an unpaired status: a stale cookie must not turn a
  poll into a 500), and a send is refused with `delivery.identity_unreadable`.
- `find_sliced_file(token, team)` -- which sliced file does this send mean? `token` is the
  non-empty string posted as `{"token": ...}` (anything else is refused as not found
  without asking). It returns a SlicedFile, or None when the token names nothing (the
  relay answers 404). If it raises, the send is refused with
  `delivery.sliced_file_unreadable`.

  **The caller must return None for a token that belongs to another team.** The relay
  cannot know who owns a token: it hands over the `team` that `identify` answered for this
  request and trusts the answer, so this check is the only thing that keeps one team from
  printing another team's sliced file.

Both run on the request's thread, outside the relay's lock.
"""

from dataclasses import dataclass
from typing import BinaryIO, Optional


@dataclass(frozen=True)
class Team:
    """The team a request speaks for.

    `pairing_code` is the only field the relay trusts; it may be in display form
    (`7k3m-q9xw`) or anything normalize_code accepts, or None when the team has no printer.
    `team_number` and `user` are passed through to events only."""

    pairing_code: Optional[str]
    team_number: Optional[int] = None
    user: Optional[str] = None


@dataclass(frozen=True)
class SlicedFile:
    """A sliced file the caller wants printed.

    Exactly one of `path` and `stream` is set:

    - `path`: a file the CALLER owns. The relay serves it to the daemon as it is and never
      deletes it, so the caller must keep it until the job is finished or expired (at most
      eighteen minutes after the send: three to be picked up, fifteen to be confirmed). A
      path that is not a file at the send is refused as not found.
    - `stream`: a readable binary file object. The relay copies it once, at the send, into
      its own spool directory and deletes that copy when the relay no longer holds the job.

    `filename` is what the daemon names the file on the printer, with the job id added
    (`sample_part.gcode.3mf` -> `sample_part-j8f3a2c1.gcode.3mf`).

    `sliced_at` is when the file was made, in seconds on the relay's clock (wall-clock time
    by default). A send more than forty minutes after it is refused with "slice again". It
    is optional: None skips the check."""

    filename: str
    path: Optional[str] = None
    stream: Optional[BinaryIO] = None
    sliced_at: Optional[float] = None

    def __post_init__(self):
        if (self.path is None) == (self.stream is None):
            raise ValueError('a SlicedFile needs exactly one of path and stream')
