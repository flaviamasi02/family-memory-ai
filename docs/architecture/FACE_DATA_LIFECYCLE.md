# Face analysis data lifecycle

FACE-001 reads but never modifies source photos. EXIF-oriented geometry, cache crops, versioned descriptors, advisory clusters, and owner-confirmed assignments live in application-managed storage. Inactive Trash records are not processed. Relocation retains logical photo IDs; a changed source fingerprint makes prior vectors stale. The Settings reset removes all biometric-like analysis and assignments while preserving photos, categories, cleanup history, and albums.
