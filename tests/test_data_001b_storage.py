from __future__ import annotations
import sqlite3
import struct
from pathlib import Path
from uuid import uuid4

import pytest
from core.application_data import ApplicationDataPathService
from storage.errors import BackupDestinationConflictError, ChecksumMismatchError, InvalidBackupError
from storage.library_registry import LibraryRegistry
from storage.metadata_store import MetadataStore, SCHEMA_VERSION
from storage.schema import REQUIRED_TABLES

@pytest.fixture
def opened(tmp_path):
    source=tmp_path/'photos'; source.mkdir()
    paths=ApplicationDataPathService(tmp_path/'app'); registry=LibraryRegistry(paths)
    record=registry.register(source, 'Test'); store=MetadataStore(paths,registry); store.open_library(record.library_id)
    yield store,record,paths
    store.close()

def test_complete_schema_indexes_and_history(opened):
    store,record,_=opened
    with store.work_unit() as c:
        tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
        indexes={r[0] for r in c.execute("select name from sqlite_master where type='index'")}
        history=c.execute('select version,name,length(checksum) from schema_migrations order by version').fetchall()
        row=c.execute('select library_id,schema_version from libraries').fetchone()
    assert REQUIRED_TABLES <= tables
    assert {'uq_photo_categories_current','uq_reviews_current','idx_photo_locations_fingerprint'} <= indexes
    assert history == [(1,'data_001a_foundation',64),(2,'data_001b_full_schema',64),
                       (3,'data_001c_import_registration',64),
                       (4,'data_001d_incremental_photo_sync',64),
                       (5,'data_001d_classification_snapshot',64)]
    assert row == (record.library_id,SCHEMA_VERSION)

def add_photo(c, library_id, photo_id='photo'):
    c.execute("insert into photos(photo_id,library_id) values (?,?)",(photo_id,library_id))

def test_constraints_embeddings_and_library_isolation(opened):
    store,record,_=opened
    with store.work_unit() as c:
        add_photo(c,record.library_id)
        blob=struct.pack('<3f',1,2,3)
        c.execute("insert into embeddings(embedding_id,photo_id,provider,model_name,model_key,dimension,vector) values ('e','photo','mobileclip','s0','mobileclip:s0',3,?)",(blob,))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("insert into embeddings(embedding_id,photo_id,provider,model_name,model_key,dimension,vector) values ('bad','photo','','s0','bad',4,?)",(blob,))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("insert into photos(photo_id,library_id,status) values ('bad',?,'gone')",(record.library_id,))

def test_location_import_and_domain_constraints(opened):
    store,record,_=opened
    with store.work_unit() as c:
        add_photo(c,record.library_id)
        values=('loc','photo',record.library_id,'/x/a.jpg','a.jpg','a.jpg','a.jpg',1,2,'2026-01-01','2026-01-01')
        c.execute("insert into photo_locations(location_id,photo_id,library_id,source_path,root_relative_path,normalised_path_key,filename,file_size,modified_time_ns,first_seen_at,last_seen_at) values (?,?,?,?,?,?,?,?,?,?,?)",values)
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("insert into photo_locations(location_id,photo_id,library_id,source_path,root_relative_path,normalised_path_key,filename,file_size,modified_time_ns,first_seen_at,last_seen_at) values ('loc2','photo',?,'/x/a.jpg','a.jpg','a.jpg','a.jpg',1,2,'x','x')",(record.library_id,))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("insert into import_runs(import_run_id,library_id,source_root,started_at,status,schema_version) values ('r',?,'/x','x','oops',2)",(record.library_id,))

def test_checksum_mismatch_rejected(opened):
    store,record,paths=opened; store.close()
    with sqlite3.connect(paths.library_database_path(record.library_id)) as c:
        c.execute("update schema_migrations set checksum='tampered' where version=1")
    with pytest.raises(ChecksumMismatchError): store.open_library(record.library_id)

def test_backup_validate_restore(opened,tmp_path):
    store,record,_=opened
    with store.work_unit() as c:
        add_photo(c,record.library_id)
    backup=tmp_path/'backup'/'family.db'
    result=store.backup(backup); assert result.schema_version == SCHEMA_VERSION
    assert store.validate_backup(backup).integrity == 'ok'
    with pytest.raises(BackupDestinationConflictError): store.backup(backup)
    with store.work_unit() as c: c.execute("delete from photos")
    restored=store.restore(backup); assert Path(restored.safety_copy_path).exists()
    with store.work_unit() as c: assert c.execute("select count(*) from photos").fetchone()[0] == 1
    bad=tmp_path/'bad.db'; bad.write_text('bad')
    with pytest.raises(InvalidBackupError): store.validate_backup(bad)

def test_health_report_shape(opened):
    report=opened[0].health_check()
    assert report['healthy'] and report['schema_version']==report['expected_schema_version']==SCHEMA_VERSION
    assert report['integrity_check']=='ok' and report['foreign_key_check']=='ok'
    assert report['missing_required_tables']==[] and report['migration_history_consistent']
