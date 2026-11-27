# What the owner has decided that bears on the slice service's guide (Fri 2026-11-27)

Gathered from the owner's reviews of the wizard's and the front server's guides and from
answers about the slice service itself. It adds to
[the decisions of the same day](decisions-2026-11-27.md) and wins over them and over every
other document where they differ. [The guide](../../../slice/README.md) states each as the
design, without saying who decided or when.

## Settings

1. The slice service accepts every setting Orca allows that is a parameter with a value,
   and refuses the programmatic ones: those that run a program, those that name a file on
   the server, and custom G-code.
2. A setting may replace a value of the process profile only. The filament's and the
   printer's values are not replaced.
3. Each time an Orca version is integrated, the table of settings is taken from Orca's
   source for that version: each setting's name, kind and permitted values, and Orca's own
   label, group and explanation for it. Taking a new Orca version therefore needs that
   version's source as well as its release.
4. Whether each setting is a parameter or programmatic is decided by the agent doing the
   work: for every setting in the first version, and for each new setting as part of
   taking a new Orca version. The programmatic settings are listed in the repository by
   name, each with its reason. Taking a new version is not finished until every new
   setting is classified, and the check against a new Orca version fails when it finds a
   setting classified nowhere.
5. The slice service holds that table and supplies it, with the profile catalog's names,
   to the front server, which passes it to the wizard. The wizard's advanced mode is drawn
   from it and shows Orca's labels, groups and explanations.
6. Each value is checked against its setting's kind and permitted values before Orca runs.
   The longest text a text setting may hold is set from the longest text value in the
   profile catalog.
7. An implementer may read Orca's source to understand its algorithms and methods, and
   never copies its code. The licence covers the code as written, not the idea behind it.

## Slice jobs

8. There is no limit of one unfinished slice job for each user. A user may have several
   under way, and everyone shares the places (one running and two waiting, as settings).
   One user can hold every place; that is accepted, and capacity is added if it proves too
   little.
9. Within one plate, a changed plate's new slice replaces that plate's own earlier
   unfinished slice job. The page makes an id for each plate, and a plate configuration
   carries it.
10. A plate configuration submitted twice: the page makes a value for each submission, and
    a repeat that carries the same value is answered with the first attempt's slice job.
11. A slice is not cancelled by hand. Neither the wizard nor the front server asks the
    slice service to cancel a slice job. Stopping Orca stays as the slice service's own
    ability, for four uses: the time limit, the memory ceiling, a plate's later slice
    replacing its earlier one, and being asked to stop. The cancel request it has as built
    stays as built, unused by the front server, and is not extended. A slice job that ends
    without a result says which of two reasons a page can meet: replaced by the same
    plate's later slice, or stopped because the slice service was asked to stop.
12. Asked to stop, the slice service finishes the slice it is running and answers new
    submissions with an answer of its own. The front server holds nothing; the wizard
    shows the slice as waiting, says the slicer is restarting, and tries again by itself
    for up to 300 seconds.
13. A sliced file is at most 50 MB. The slice service ends a slice whose file would be
    larger, with its own sentence.
14. On the two failures about a gap with nothing under it (with supports off, and with
    supports already on), the error report carries Orca's own sentence, which the wizard
    quotes under Details, marked as Orca's. Nowhere else are Orca's words shown.

## Parts

15. Units travel beside a part as a label; only the slice service applies the scale; the
    same file under different units is a different part. (As the guide has it.)
16. The wizard's placement check and the slice service's are kept in agreement by one
    shared set of plates, some just passing and some just failing, run by both components'
    tests.

## Left open

17. Who notices a configuration that names a profile the profile catalog has lost is an
    open question, to be settled the first time Orca is upgraded. Until then the catalog
    does not change, so no configuration can lose a profile.
18. The hosted memory ceiling of 6,000 MB stays a proposal that is the owner's to change.
19. The small rules the guide proposes and nobody has ruled on stay marked as proposals,
    gathered in one short list for the owner: the fit test on arrival using the largest
    printer in the profile catalog; refusing a part that arrives without a units label; no
    "every side under 5 mm" warning for a part labelled in inches; 1 MB for a plate
    configuration without its files.

## The log and the tests

20. The slice service's log lines are fetched by the front server and written, with every
    other component's, into one file each minute; every line carries the component that
    wrote it.
21. A test never sleeps and never waits a number of seconds to see whether something
    happened: time is moved through a fake clock, and a test waits on an event.

## The shape of the guide

22. Items about trials and things unmeasured say what is to be learned, why it matters and
    what decision depends on it. How the measuring or the building is done belongs in
    `README-details.md`. Mechanics that only a builder needs leave the guide.
23. Everything above that was an open item or a proposal in the guide leaves those lists
    and is stated in the body as the design.
