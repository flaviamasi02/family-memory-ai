"""Domain-specific errors for application-owned metadata storage."""

class StorageError(RuntimeError):
    """Base error for managed storage operations."""
class InvalidLibraryRootError(StorageError): pass
class DuplicateLibraryError(StorageError): pass
class LibraryNotFoundError(StorageError): pass
class UnavailableLibraryError(StorageError): pass
class RegistryCorruptionError(StorageError): pass
class UnsupportedSchemaVersionError(StorageError): pass
class DatabaseInitialisationError(StorageError): pass
class SchemaMigrationError(DatabaseInitialisationError): pass
class ChecksumMismatchError(SchemaMigrationError): pass
class DatabaseHealthCheckError(StorageError): pass
class MissingRequiredTableError(DatabaseHealthCheckError): pass
class IntegrityCheckError(DatabaseHealthCheckError): pass
class ForeignKeyCheckError(DatabaseHealthCheckError): pass
class DatabaseBusyError(StorageError): pass
class DatabaseCorruptionError(StorageError): pass
class BackupError(StorageError): pass
class BackupDestinationConflictError(BackupError): pass
class InvalidBackupError(BackupError): pass
class RestorePreconditionError(StorageError): pass
class RestoreError(StorageError): pass
