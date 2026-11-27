# What the owner decided on Fri 2026-11-27

A working record for the writers and reviewers of the guides. Every item is the owner's
decision of Fri 2026-11-27, Pacific time, unless marked "proposed", which means the
coordinator proposed it and the owner has not objected. The living documents state these as
the design, without saying who decided or when; only
[the decision map](../hosted-architecture/decision-map.md) records that.

## What a guide is

1. A component's guide (`README.md`) is for the person who decides: a product manager and an
   engineering manager or CTO at once. It holds "everything a human needs to make the class
   of decisions" made in the design sessions: architectural decisions, user-interface
   decisions, and requirements, functional and non-functional. A product manager must be
   able to assess from it whether the component is being built correctly. An engineering
   manager looks for the algorithms (as approaches, not code), the performance requirements,
   the security requirements, and whether the software is well composed into components.
2. It is prose, written for a person. It has no line limit. It carries no code-level names:
   no make targets, route paths, setting names, constant names, error codes, function or
   class names, file paths inside the code, or test names. Key limits (memory, time, how
   many at once, sizes, durations) belong in it, each in plain words with its figure.
3. `README-details.md` beside it is the builder's document and holds the code-level names.
   The roughly 110 details marked *proposed* there (route names, setting names, error codes)
   are the builder's to settle while building and stay out of the guides.
4. Once the four guides are reviewed, they, their details files and the contracts must be
   enough to write the software.

## The slice service

5. It accepts every setting Orca allows that is a parameter with a value (a choice from a
   list, a number, a piece of text), and all of them are available in the wizard's advanced
   mode. It refuses settings that are programmatic: those that run a program, those that
   name a file on the server, and custom G-code.
6. Units. The browser reads a part to draw it and lay it out, and never changes its bytes.
   The units of a part (inches or millimetres) travel beside it as a label. Only the slice
   service applies the scale, and it uses the units in its checks when the part arrives. The
   same file under different units is a different part in the part store. The plate
   configuration's contract gains units for each part.
7. The thirteen design rulings an agent made in the two older guides (R1 to R3, R5 to R12,
   R14, R18) stand; they may be revisited when more is known.

## The configuration

8. The profiles the wizard offers for each filament are in the configuration. Until the edit
   screens exist there is a fixed set of configurations.
9. The configuration keeps a colour for each filament, shown where the user chooses a
   filament so that two filaments of one material can be told apart. That colour is never
   used in the layer preview, which uses four fixed colours for groups of line types.

## The sliced file

10. A sliced file is kept until two hours after its slice ended or two hours after its last
    print ended, whichever is later, so the same plate can be sent again after a print of
    any length.
11. The backstop rule at Cloudflare R2 is three days. A file the front server failed to
    delete can rest there up to about four days after it was stored.
12. Proposed: sending a sliced file stores it afresh, which restarts R2's count, so the
    backstop runs from the last send. A send whose file has gone answers that the sliced
    file has expired and that the plate must be sliced again.
13. Proposed: a delivery job's record names the sliced file it used, which is how the front
    server knows when a sliced file's last print ended.

## The wizard

14. Retrying. The page retries a failed request quietly at first. After 20 seconds of failed
    retries it shows a message that the server is being slow and the browser is retrying,
    with a countdown to the next attempt, as Gmail's "retrying in 28s" does; the waits
    between attempts grow. It keeps retrying for up to 300 seconds in all. Then it stops,
    says the server could not be reached and offers to try again. Nothing of the user's work
    is dropped. The exact waits and words are the builder's.
15. Every recommendation on where the mockup and the design differed is confirmed. They are
    already stated as the design in the wizard's guide on `main`, with a table of where the
    guide departs from the mockup's numbered decisions. In short: a refresh restores parts,
    layout and settings from the browser's storage; the browser keeps its slice job's id and
    work does not follow to another browser; the two hours of a sliced file start when the
    slice ended; any user of the group pairs the printer by typing the code into
    PenguinSlicer; the paired-printer record links the group to its daemon and the
    configuration names the printer's Orca profile, from which the plate's size and height
    come; a part that cannot be used is a notification and is not added; a returning page
    opens on the Send step while its plate is still stored and has a delivery job, running
    or ended, and on the Parts step once the plate is gone; the page outside Onshape gets
    its configuration from the signed-in user's group; each profile has the group's own name
    and purpose; the mockup's invented "plate too large" error is left out.
16. The mockup's open questions are all answered. M1: lay on face uses faces on the hull.
    M2: the mouse works like Onshape. M3: parts arrive lying their best way. M6: Arrange and
    Auto-orient stay two buttons, and Arrange never turns an instance (the mockup's decision
    64). M16: no layout tools beyond those the final mockup shows. M17: leaving the Preview
    step does not stop the slice. M18: see item 10. M29: the bounding-box patches keep their
    rule, end patches included and the 30-degree angle unchanged; it is a starting point to
    be tuned on real parts. M7, M11, M21, M22, M23, M25, M26 and the 11 px pointer line: as
    the mockup has them.
17. The twelve screens the design needs and the mockup never showed are designed in words in
    the wizard's guide, following the patterns the mockup established. No mockups first.
18. The Preview step. The guide says what must be achieved: Orca makes the sliced file; the
    user inspects it layer by layer at a stated frame rate, in a stated browser, on a stated
    machine, with the appearance the mockup's decision 33 requires. The method is found
    during implementation and is not in the guide.

## Printer delivery

19. The relay notes a time in the paired-printer record when a daemon goes offline, one
    write at that moment and not one a minute, so that the wizard can say how long a printer
    has been silent even after a restart of the front server. Proposed: the time noted is
    that of the daemon's last sync; after a restart of the front server, a paired daemon not
    heard from within two minutes is shown as silent "for at least" the time since the
    front server started.
20. A work item: printer delivery's tests that wait on the wall clock are rewritten to use a
    fake clock and fakes that put network events in an exact order. It is the first piece of
    phase 5's work on printer delivery, and the new work of that phase is built on those
    fakes.

## The project as a whole

21. The component formerly called the Onshape source is **the Onshape integration**, in
    `onshape/`: the component that makes PenguinSlicer work inside Onshape. It covers the
    Onshape app and its panel, the exchange with Onshape's page that tells the wizard which
    document and element it is in and what is selected, and the export of the selected parts
    and the document's units, delivered to the wizard as a part set. Signing in is not part
    of it; that is the front server's. How it divides between the browser and the server is
    for phase 4's design.
22. Where the code came from (the print branch of PenguinCAM) leaves the plan. One mention
    stays, in phase 4, where that branch holds code for selecting and exporting parts in
    Onshape that may be ported.
23. Returning to PenguinCAM is a possible direction, not decided, that the design must not
    close off: hence PenguinCAM's stack and components joined only through contracts.
24. Patching upstream code. The strong preference is not to patch. A workaround that avoids
    a patch is almost always preferred. A small patch is reasonable when it is needed to
    reach a goal, whether for an error, for progress or for a minor feature. Every patch is
    paid for again at each new upstream version.
25. Tests. A test never sleeps and never waits a number of seconds to see whether something
    has happened: time passes through a fake clock that the test moves, and a test waits on
    an event, never on a duration. Code that talks over a network or depends on the order of
    events is tested with fakes that let the test put the events in an exact order.
26. The plan holds what is needed to be understood by someone who has read nothing else, and
    nothing that duplicates a decision recorded elsewhere: no figures, defaults or
    mechanisms that another document owns, unless the plan's own point needs one.
27. The Layout step's risk. Placing instances by direct manipulation at 320 px is shown to
    work by the mockup. What is unproven is laying on a face, orienting and arranging on
    real exported parts, which are written fresh.
28. The README opens: PenguinSlicer is 3D printing from Onshape, with FRC teams as its first
    users.
