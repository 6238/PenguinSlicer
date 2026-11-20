"""The slice service: takes a plate configuration, runs Orca Slicer headless, returns a sliced file.

Its one interface is the HTTP interface (web.py), started with

    uv run --project slice python -m penguin_slice serve --work <dir>

See slice/README.md and contracts/plate-configuration.md, contracts/sliced-file.md.
"""
