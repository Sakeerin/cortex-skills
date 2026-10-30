"""Domain errors independent of CLI rendering."""


class DataError(ValueError):
    """Persisted data failed validation; it is not an argument error."""


class AmbiguousModelError(ValueError):
    """A model name resolves to multiple providers and needs disambiguation."""
