"""Immutable, forward-only schema migrations for the managed library database."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        return hashlib.sha256("\n".join(self.statements).encode()).hexdigest()


# DATA-001A migration 1 is deliberately byte-for-byte unchanged.
V1_STATEMENTS = ("""
CREATE TABLE schema_migrations (
 version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, checksum TEXT NOT NULL,
 applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
)
""", """CREATE TABLE libraries (
 library_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, root_path TEXT NOT NULL,
 normalised_root_key TEXT NOT NULL, created_at TEXT NOT NULL, last_opened_at TEXT,
 schema_version INTEGER NOT NULL, status TEXT NOT NULL
)
""")

V2_SQL = r"""
ALTER TABLE schema_migrations ADD COLUMN started_at TEXT;
ALTER TABLE schema_migrations ADD COLUMN status TEXT NOT NULL DEFAULT 'applied' CHECK(status IN ('applying','applied','failed'));
ALTER TABLE schema_migrations ADD COLUMN app_version TEXT;
ALTER TABLE schema_migrations ADD COLUMN error TEXT;
ALTER TABLE libraries ADD COLUMN last_known_available_at TEXT;
ALTER TABLE libraries ADD COLUMN database_identity TEXT;
CREATE INDEX idx_schema_migrations_status ON schema_migrations(status);
CREATE UNIQUE INDEX uq_libraries_normalised_root ON libraries(normalised_root_key);

CREATE TABLE photos (
 photo_id TEXT PRIMARY KEY, library_id TEXT NOT NULL REFERENCES libraries(library_id) ON DELETE RESTRICT,
 preferred_location_id TEXT REFERENCES photo_locations(location_id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
 media_type TEXT NOT NULL DEFAULT 'image' CHECK(media_type IN ('image','video','unknown')),
 width INTEGER CHECK(width IS NULL OR width > 0), height INTEGER CHECK(height IS NULL OR height > 0), orientation INTEGER,
 captured_at TEXT, camera_make TEXT, camera_model TEXT, content_hash TEXT, hash_algorithm TEXT, hash_version INTEGER,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','missing','deleted')),
 deleted_at TEXT, metadata_revision INTEGER NOT NULL DEFAULT 1 CHECK(metadata_revision > 0),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX idx_photos_library_status ON photos(library_id,status);
CREATE INDEX idx_photos_captured_at ON photos(captured_at);
CREATE INDEX idx_photos_content_hash ON photos(content_hash,hash_algorithm,hash_version);
CREATE INDEX idx_photos_updated_at ON photos(updated_at);

CREATE TABLE import_runs (
 import_run_id TEXT PRIMARY KEY, library_id TEXT NOT NULL REFERENCES libraries(library_id) ON DELETE RESTRICT,
 source_root TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT, cancelled_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('running','completed','cancelled','failed','partial')),
 discovered_count INTEGER NOT NULL DEFAULT 0, created_count INTEGER NOT NULL DEFAULT 0,
 reused_count INTEGER NOT NULL DEFAULT 0, changed_count INTEGER NOT NULL DEFAULT 0,
 missing_count INTEGER NOT NULL DEFAULT 0, skipped_count INTEGER NOT NULL DEFAULT 0,
 failed_count INTEGER NOT NULL DEFAULT 0, error_summary TEXT, application_version TEXT, schema_version INTEGER NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 CHECK(discovered_count>=0 AND created_count>=0 AND reused_count>=0 AND changed_count>=0 AND missing_count>=0 AND skipped_count>=0 AND failed_count>=0)
);
CREATE INDEX idx_import_runs_library_started ON import_runs(library_id,started_at);
CREATE INDEX idx_import_runs_status ON import_runs(status);

CREATE TABLE photo_locations (
 location_id TEXT PRIMARY KEY, photo_id TEXT NOT NULL REFERENCES photos(photo_id) ON DELETE RESTRICT,
 library_id TEXT NOT NULL REFERENCES libraries(library_id) ON DELETE RESTRICT,
 source_path TEXT NOT NULL, root_relative_path TEXT NOT NULL, normalised_path_key TEXT NOT NULL,
 filename TEXT NOT NULL, extension TEXT NOT NULL DEFAULT '', file_size INTEGER NOT NULL CHECK(file_size>=0),
 modified_time_ns INTEGER NOT NULL CHECK(modified_time_ns>=0), creation_time TEXT,
 partial_fingerprint TEXT, fingerprint_algorithm TEXT, fingerprint_version INTEGER,
 availability TEXT NOT NULL DEFAULT 'available' CHECK(availability IN ('available','missing','deleted','disconnected')),
 first_seen_run_id TEXT REFERENCES import_runs(import_run_id) ON DELETE SET NULL,
 last_seen_run_id TEXT REFERENCES import_runs(import_run_id) ON DELETE SET NULL,
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, removed_at TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(library_id,normalised_path_key)
);
CREATE INDEX idx_photo_locations_photo ON photo_locations(photo_id);
CREATE INDEX idx_photo_locations_fingerprint ON photo_locations(partial_fingerprint,file_size);
CREATE INDEX idx_photo_locations_last_seen ON photo_locations(last_seen_at);
CREATE INDEX idx_photo_locations_availability ON photo_locations(library_id,availability);

CREATE TABLE embeddings (
 embedding_id TEXT PRIMARY KEY, photo_id TEXT NOT NULL REFERENCES photos(photo_id) ON DELETE CASCADE,
 provider TEXT NOT NULL CHECK(length(trim(provider))>0), model_name TEXT NOT NULL CHECK(length(trim(model_name))>0),
 model_version TEXT NOT NULL DEFAULT '', model_key TEXT NOT NULL, dimension INTEGER NOT NULL CHECK(dimension>0),
 dtype TEXT NOT NULL DEFAULT 'float32' CHECK(dtype='float32'), byte_order TEXT NOT NULL DEFAULT 'little' CHECK(byte_order='little'),
 vector BLOB NOT NULL CHECK(length(vector)>0 AND length(vector)=dimension*4), source_fingerprint TEXT,
 fingerprint_version INTEGER, status TEXT NOT NULL DEFAULT 'valid' CHECK(status IN ('valid','invalidated','invalid','regeneration_required','failed')),
 validation_status TEXT NOT NULL DEFAULT 'validated' CHECK(validation_status IN ('pending','validated','failed')),
 invalidated_at TEXT, regeneration_required INTEGER NOT NULL DEFAULT 0 CHECK(regeneration_required IN (0,1)), error TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), UNIQUE(photo_id,model_key)
);
CREATE INDEX idx_embeddings_model_status ON embeddings(model_key,status);
CREATE INDEX idx_embeddings_source_fingerprint ON embeddings(source_fingerprint);

CREATE TABLE categories (
 category_id TEXT PRIMARY KEY, library_id TEXT NOT NULL REFERENCES libraries(library_id) ON DELETE RESTRICT,
 display_name TEXT NOT NULL, normalised_name TEXT NOT NULL, description TEXT, ai_description TEXT, color TEXT, icon TEXT,
 is_system INTEGER NOT NULL DEFAULT 0 CHECK(is_system IN (0,1)), is_cleanup_candidate INTEGER NOT NULL DEFAULT 0 CHECK(is_cleanup_candidate IN (0,1)),
 is_album_candidate INTEGER NOT NULL DEFAULT 1 CHECK(is_album_candidate IN (0,1)), source TEXT NOT NULL DEFAULT 'user',
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived','deleted')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(library_id,normalised_name)
);
CREATE INDEX idx_categories_flags ON categories(library_id,is_cleanup_candidate,is_album_candidate,status);
CREATE TABLE photo_categories (
 photo_category_id TEXT PRIMARY KEY, photo_id TEXT NOT NULL REFERENCES photos(photo_id) ON DELETE CASCADE,
 category_id TEXT NOT NULL REFERENCES categories(category_id) ON DELETE RESTRICT,
 assignment_type TEXT NOT NULL CHECK(assignment_type IN ('automatic','user','suggestion')),
 assignment_source TEXT NOT NULL, confidence REAL CHECK(confidence IS NULL OR (confidence>=0 AND confidence<=1)), reason TEXT,
 confirmation_state TEXT NOT NULL DEFAULT 'pending' CHECK(confirmation_state IN ('pending','confirmed','rejected','corrected')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), assigned_at TEXT NOT NULL, superseded_at TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), UNIQUE(photo_id,category_id,assignment_type,assigned_at)
);
CREATE UNIQUE INDEX uq_photo_categories_current ON photo_categories(photo_id,assignment_type) WHERE active=1;
CREATE INDEX idx_photo_categories_category ON photo_categories(category_id,active);

CREATE TABLE reviews (
 review_id TEXT PRIMARY KEY, photo_id TEXT NOT NULL REFERENCES photos(photo_id) ON DELETE CASCADE,
 profile_id TEXT, review_type TEXT NOT NULL CHECK(review_type IN ('cleanup','memory','album','category')),
 decision TEXT NOT NULL CHECK(decision IN ('pending','approved','rejected','keep','delete','skipped')),
 source TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL, superseded_at TEXT
);
CREATE UNIQUE INDEX uq_reviews_current ON reviews(photo_id,review_type,COALESCE(profile_id,'')) WHERE superseded_at IS NULL;
CREATE INDEX idx_reviews_type_decision ON reviews(review_type,decision);

CREATE TABLE albums (
 album_id TEXT PRIMARY KEY, library_id TEXT NOT NULL REFERENCES libraries(library_id) ON DELETE RESTRICT,
 title TEXT NOT NULL, album_type TEXT NOT NULL CHECK(album_type IN ('annual','memory','custom')),
 album_year INTEGER, status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','review','complete','archived','deleted')),
 settings_json TEXT, settings_version INTEGER NOT NULL DEFAULT 1 CHECK(settings_version>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX idx_albums_library_status ON albums(library_id,status);
CREATE UNIQUE INDEX uq_albums_annual_year ON albums(library_id,album_type,album_year) WHERE album_type='annual' AND status!='deleted';
CREATE TABLE album_items (
 album_item_id TEXT PRIMARY KEY, album_id TEXT NOT NULL REFERENCES albums(album_id) ON DELETE CASCADE,
 photo_id TEXT NOT NULL REFERENCES photos(photo_id) ON DELETE RESTRICT, position INTEGER CHECK(position IS NULL OR position>=0),
 page_key TEXT, inclusion_reason TEXT, review_state TEXT NOT NULL DEFAULT 'pending' CHECK(review_state IN ('pending','approved','rejected')),
 score REAL, score_provenance TEXT, status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','removed')),
 added_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(album_id,photo_id), UNIQUE(album_id,position)
);
CREATE INDEX idx_album_items_order ON album_items(album_id,position);
CREATE INDEX idx_album_items_photo ON album_items(photo_id);

CREATE TABLE preferences (
 library_id TEXT NOT NULL REFERENCES libraries(library_id) ON DELETE CASCADE, scope TEXT NOT NULL,
 key TEXT NOT NULL, profile_id TEXT NOT NULL DEFAULT '', value_json TEXT NOT NULL, value_type TEXT NOT NULL,
 schema_version INTEGER NOT NULL CHECK(schema_version>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(library_id,scope,key,profile_id)
);

CREATE TABLE import_run_items (
 import_run_item_id TEXT PRIMARY KEY, import_run_id TEXT NOT NULL REFERENCES import_runs(import_run_id) ON DELETE CASCADE,
 photo_id TEXT REFERENCES photos(photo_id) ON DELETE SET NULL, location_id TEXT REFERENCES photo_locations(location_id) ON DELETE SET NULL,
 normalised_path_key TEXT NOT NULL, event TEXT NOT NULL CHECK(event IN ('created','reused','changed','missing','skipped','conflict','failed')),
 fingerprint_evidence TEXT, error_code TEXT, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(import_run_id,normalised_path_key,event)
);
CREATE INDEX idx_import_run_items_event ON import_run_items(import_run_id,event);
CREATE INDEX idx_import_run_items_photo ON import_run_items(photo_id);

CREATE TABLE people (
 person_id TEXT PRIMARY KEY, library_id TEXT NOT NULL REFERENCES libraries(library_id) ON DELETE RESTRICT,
 display_name TEXT NOT NULL, relationship_json TEXT, notes TEXT, representative_face_id TEXT,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','hidden','merged','deleted')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX idx_people_library_status ON people(library_id,status);
CREATE TABLE faces (
 face_id TEXT PRIMARY KEY, photo_id TEXT NOT NULL REFERENCES photos(photo_id) ON DELETE CASCADE,
 person_id TEXT REFERENCES people(person_id) ON DELETE SET NULL, cluster_id TEXT,
 x REAL NOT NULL, y REAL NOT NULL, width REAL NOT NULL CHECK(width>0), height REAL NOT NULL CHECK(height>0),
 detection_provider TEXT NOT NULL, detection_model TEXT NOT NULL, quality REAL CHECK(quality IS NULL OR (quality>=0 AND quality<=1)),
 confirmation_state TEXT NOT NULL DEFAULT 'unconfirmed' CHECK(confirmation_state IN ('unconfirmed','confirmed','rejected')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX idx_faces_photo ON faces(photo_id);
CREATE INDEX idx_faces_person ON faces(person_id);
CREATE TABLE face_embeddings (
 face_embedding_id TEXT PRIMARY KEY, face_id TEXT NOT NULL REFERENCES faces(face_id) ON DELETE CASCADE,
 provider TEXT NOT NULL, model_name TEXT NOT NULL, model_version TEXT NOT NULL DEFAULT '', dimension INTEGER NOT NULL CHECK(dimension>0),
 dtype TEXT NOT NULL DEFAULT 'float32' CHECK(dtype='float32'), byte_order TEXT NOT NULL DEFAULT 'little' CHECK(byte_order='little'),
 vector BLOB NOT NULL CHECK(length(vector)=dimension*4), status TEXT NOT NULL DEFAULT 'valid' CHECK(status IN ('valid','invalidated','failed')),
 created_at TEXT NOT NULL, UNIQUE(face_id,provider,model_name,model_version)
);

CREATE TABLE metadata_migration_history (
 migration_history_id TEXT PRIMARY KEY, library_id TEXT NOT NULL REFERENCES libraries(library_id) ON DELETE RESTRICT,
 migration_type TEXT NOT NULL, source_format TEXT NOT NULL, source_identifier TEXT NOT NULL, source_fingerprint TEXT,
 idempotency_key TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('running','success','partial','failed','skipped')),
 imported_count INTEGER NOT NULL DEFAULT 0, reused_count INTEGER NOT NULL DEFAULT 0, skipped_count INTEGER NOT NULL DEFAULT 0,
 conflict_count INTEGER NOT NULL DEFAULT 0, failed_count INTEGER NOT NULL DEFAULT 0, error_summary TEXT,
 application_version TEXT, schema_version INTEGER NOT NULL,
 CHECK(imported_count>=0 AND reused_count>=0 AND skipped_count>=0 AND conflict_count>=0 AND failed_count>=0),
 UNIQUE(library_id,migration_type,idempotency_key)
);
CREATE INDEX idx_metadata_migration_status ON metadata_migration_history(library_id,migration_type,status);
"""

V2_STATEMENTS = tuple(part.strip() for part in V2_SQL.split(";") if part.strip())
MIGRATIONS = (Migration(1, "data_001a_foundation", V1_STATEMENTS), Migration(2, "data_001b_full_schema", V2_STATEMENTS))
SCHEMA_VERSION = MIGRATIONS[-1].version

REQUIRED_TABLES = frozenset({
    "schema_migrations", "libraries", "photos", "photo_locations", "embeddings", "categories",
    "photo_categories", "reviews", "albums", "album_items", "preferences", "import_runs",
    "import_run_items", "people", "faces", "face_embeddings", "metadata_migration_history",
})
