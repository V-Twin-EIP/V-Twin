"""Support ``python -m vtwin`` as well as the installed command."""

from vtwin.adapters.cli import main

if __name__ == "__main__":  # Guard: spawned workers re-import the main module.
    raise SystemExit(main())
