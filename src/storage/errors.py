"""Domain-specific errors for application-owned metadata storage."""


class StorageError(RuntimeError):
    """Base error for managed storage operations."""


class InvalidLibraryRootError(StorageError):
    pass


class DuplicateLibraryError(StorageError):
    pass


class LibraryNotFoundError(StorageError):
    pass


class UnavailableLibraryError(StorageError):
    pass


class RegistryCorruptionError(StorageError):
    pass


class UnsupportedSchemaVersionError(StorageError):
    pass


class DatabaseInitialisationError(StorageError):
    pass


class DatabaseHealthCheckError(StorageError):
    pass
