"""Support ``python -m vtwin`` as well as the installed command."""

from vtwin.adapters.cli import main

raise SystemExit(main())
