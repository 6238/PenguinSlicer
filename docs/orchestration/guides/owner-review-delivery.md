# What the owner has decided that bears on printer delivery's guide (Fri 2026-11-27)

Gathered from the owner's reviews of the wizard's and the front server's guides. The owner
has not yet read [printer delivery's guide](../../../delivery/README.md) itself. This adds
to [the decisions of the same day](decisions-2026-11-27.md) and wins over them and over
every other document where they differ. The guide states each as the design, without
saying who decided or when.

## Pairing and unpairing

1. Any user of a group pairs its printer, by typing the code the daemon shows into
   PenguinSlicer. The form is in the printer details and nowhere else; when the Send step
   finds no printer paired, its message links to the printer details.
2. The printer's display name is the one the printer itself reports, sent by the daemon
   when it is paired. Nobody types it.
3. Unpair is only in the printer details. Any user of the group may unpair. Unpair is off
   while a print is being followed.

## A print

4. "Stop following" is offered to, and accepted from, the sender of the print only. If the
   sender is away, a print that has gone stale holds the printer until the daemon reports
   again or the relay gives the print up by its own rule after a day without word.
5. A sliced file is kept until two hours after its slice ended or two hours after its last
   print ended, whichever is later, so the same plate can be sent again after a print of
   any length. A delivery job's record names the sliced file it used, which is how the
   front server knows when a sliced file's last print ended. A send whose sliced file has
   gone is answered that the sliced file has expired and that the plate must be sliced
   again. A sliced file is at most 50 MB.
6. The relay notes, in the paired-printer record, the time of a daemon's last sync when
   that daemon goes offline: one write at that moment, not one a minute. The wizard can
   then say how long a printer has been silent, even after a restart of the front server,
   where a paired daemon not heard from within two minutes is shown as silent "for at
   least" the time since the front server started. Whether the recorded time is cleared
   when the daemon returns stays an open item, with its recommendation.
7. A printer not yet heard from shows a grey dot and "…" in the wizard.
8. Progress streams are kept for following a print; the front server limits the streams
   one user may hold.
9. The Send step exists in the wizard from phase 2 with the download as its one button;
   phase 5 adds sending to the printer, the print card and the printer-status icon.

## The log and the tests

10. Printer delivery's log lines and the daemons' telemetry are written by the front
    server, with every other component's lines, into one file each minute; every line
    carries the component that wrote it.
11. A test never sleeps and never waits a number of seconds to see whether something
    happened: time is moved through a fake clock, and a test waits on an event. Code that
    talks over a network or depends on the order of events is tested with fakes that put
    the events in an exact order. Six of printer delivery's tests wait on the real clock
    (two in the fast suite, two in the suite that uses the simulated printer, two in the
    run that joins the relay and the daemon); rewriting them is the first piece of phase
    5's work on printer delivery, and that phase's new work is built on those fakes.
12. The thirteen design rulings an agent made in the guide's older text stand; they may be
    revisited when more is known.

## Left open

13. The guide's own open items that nobody has ruled on stay open, each with its backing
    and a recommendation: unpairing while a delivery job has not ended; a group that pairs
    again (its three cases); printed files left on the printer; daemons of different
    versions; which printers are supported; a delivery job's deadlines across a restart;
    the mode the printer must be in for pairing and what it gives up in that mode; whether
    progress arrives as it is sent through Cloudflare and Railway; what daemon telemetry
    holds; a send repeated while its delivery job is live being answered with that
    delivery job; the limits on the rate of requests.

## The shape of the guide

14. Items about trials and things unmeasured say what is to be learned, why it matters and
    what decision depends on it. How the measuring or the building is done belongs in
    `README-details.md`. Mechanics that only a builder needs leave the guide.
15. Everything above that was an open item or a proposal in the guide leaves those lists
    and is stated in the body as the design.
