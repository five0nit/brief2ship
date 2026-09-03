"""Typed Brief2Ship failures used by the CLI and library."""


class Brief2ShipError(Exception):
    """Base class for expected product failures."""


class PolicyError(Brief2ShipError):
    """A target or operation is blocked by the safety policy."""


class RobotsDenied(PolicyError):
    """robots.txt denies the requested page."""


class RobotsUnavailable(PolicyError):
    """robots.txt could not be checked safely."""


class FetchError(Brief2ShipError):
    """The remote response could not be fetched within configured limits."""


class ExtractionError(Brief2ShipError):
    """Content was fetched but no usable text could be extracted."""


class OutputError(Brief2ShipError):
    """A requested output artifact could not be written."""
