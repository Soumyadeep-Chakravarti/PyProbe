"""PyProbe exception hierarchy."""


class PyProbeError(Exception):
    """Base exception for all PyProbe errors."""


class PyProbeSecurityError(PyProbeError):
    """Raised when mutation targets an immutable or protected object.

    This is a HARD block — cannot be bypassed.
    Examples: interned strings, live bytecode.
    """


class PyProbeIntegrityError(PyProbeError):
    """Raised when an operation would corrupt memory or internal state.

    This is a HARD block — cannot be bypassed.
    Examples: length mismatch, dict value pointer scan failure.
    """


class PyProbeSafetyError(PyProbeError):
    """Raised when safety checks block a mutation.

    This is a SOFT block — can be bypassed with safe=False.
    Examples: shared objects, immortal objects.
    """


class PyProbeFatalError(PyProbeError):
    """Raised when an operation encounters an unrecoverable state.

    This is a HARD block — cannot be bypassed.
    Indicates CPython internal corruption or a condition
    from which recovery is impossible.
    """


class PyProbeWarning(UserWarning):
    """Warning issued for non-critical PyProbe issues."""
