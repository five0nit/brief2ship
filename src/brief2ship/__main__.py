"""Allow ``python -m brief2ship`` to mirror the console script."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
