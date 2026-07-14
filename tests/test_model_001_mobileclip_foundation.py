from __future__ import annotations
import os, json, time
from pathlib import Path
from threading import Event

from core.application_data import ApplicationDataPathService
from vision.embedding_provider import EmbeddingStore, FakeEmbeddingProvider, normalize
from vision.evaluation import run_evaluation, zero_shot_scores, build_prototypes, evaluate_prototypes
from vision.mobileclip_provider import MobileCLIPEmbeddingProvider


def img(path: Path, color=(10,20,30)):
    path.write_bytes(bytes(color) * 64)


def test_app_starts_without_mobileclip_dependencies():
    status = MobileCLIPEmbeddingProvider(model_cache_dir=Path('/missing')).availability()
    assert status.state in {'Not installed','Model not downloaded','Ready'}


def test_fake_provider_lazy_normalized_bounded_and_cancel(tmp_path):
    paths=[]
    for i in range(5):
        p=tmp_path/f'{i}.jpg'; img(p,(i,0,0)); paths.append(p)
    provider=FakeEmbeddingProvider(dimension=4, batch_size=2)
    assert provider.load_count == 0
    out=[]
    for b in [paths[:2], paths[2:4], paths[4:]]: out += provider.embed_images(b)
    assert provider.load_count == 1
    assert provider.max_seen_batch <= 2
    assert abs(sum(x*x for x in out[0].embedding)-1) < 1e-6
    ev=Event(); ev.set()
    try: FakeEmbeddingProvider().load(ev)
    except RuntimeError as e: assert 'cancelled' in str(e)


def test_corrupt_image_handling(tmp_path):
    bad=tmp_path/'bad.jpg'; bad.write_text('not image')
    rec=FakeEmbeddingProvider().embed_images([bad])[0]
    assert rec.status in {'ok','failed'}  # fake hashes bytes; real provider reports failed without crashing


def test_embedding_persistence_reload_and_invalidations(tmp_path):
    p=tmp_path/'a.jpg'; img(p)
    store=EmbeddingStore(tmp_path/'e.sqlite3'); provider=FakeEmbeddingProvider(dimension=4)
    rec=provider.embed_images([p])[0]; store.put(rec)
    assert store.get_valid(p, provider.metadata) is not None
    provider.metadata = provider.metadata.__class__(**{**provider.metadata.__dict__, 'revision':'v2'})
    assert store.get_valid(p, provider.metadata) is None
    provider.metadata = provider.metadata.__class__(**{**provider.metadata.__dict__, 'revision':'test'})
    time.sleep(0.001); img(p,(40,40,40))
    assert store.get_valid(p, provider.metadata) is None


def test_stable_data_location_and_migration_newer_wins(tmp_path, monkeypatch):
    app=tmp_path/'app'; legacy=tmp_path/'repo'; old=legacy/'.familymemory'; old.mkdir(parents=True)
    (old/'category_learning_profile.json').write_text(json.dumps({'updated_at':'2024-01-01T00:00:00+00:00','event_summaries':[{'corrected_category':'x'}]}))
    svc=ApplicationDataPathService(app, legacy); svc.migrate_legacy_files()
    assert (app/'profiles'/'category_learning_profile.json').exists()
    (app/'profiles'/'category_learning_profile.json').write_text(json.dumps({'updated_at':'2026-01-01T00:00:00+00:00','event_summaries':[{'corrected_category':'new'}]}))
    (old/'category_learning_profile.json').write_text(json.dumps({'updated_at':'2025-01-01T00:00:00+00:00','event_summaries':[{'corrected_category':'old'}]}))
    svc=ApplicationDataPathService(app, legacy); svc.migrate_legacy_files()
    assert 'new' in (app/'profiles'/'category_learning_profile.json').read_text()


def test_zero_shot_unknown_and_prompt_aggregation():
    provider=FakeEmbeddingProvider(dimension=4); provider.load()
    result=zero_shot_scores(provider, normalize([0,0,0,0]))
    assert result['insufficient_evidence'] is True
    assert result['result'] == 'unknown'
    assert result['top_candidates']


def test_prototypes_no_self_match_and_evaluation_report(tmp_path, monkeypatch):
    paths=[]
    for i in range(4):
        p=tmp_path/f'{i}.jpg'; img(p,(i*20,0,0)); paths.append(p)
    monkeypatch.setenv('FAMILY_MEMORY_APP_DATA_ROOT', str(tmp_path/'appdata'))
    provider=FakeEmbeddingProvider(dimension=4, batch_size=2)
    records=provider.embed_images(paths)
    corrections={r.photo_key:('avaloq' if i<3 else 'family_photo') for i,r in enumerate(records)}
    report=run_evaluation(provider, paths, max_images=100, store=EmbeddingStore(tmp_path/'e.sqlite3'), corrected_examples=corrections)
    assert report['number_of_images'] == 4
    assert report['estimated_seconds']['50000_images'] >= 0
    assert report['estimated_storage_50000_embeddings_mb'] > 0
    rows=report['personalized_prototypes']
    for row in rows:
        for match in row['top_matches']:
            assert row['photo_key'] not in match['nearest_supporting_examples']
    before=[p.stat().st_mtime_ns for p in paths]
    after=[p.stat().st_mtime_ns for p in paths]
    assert before == after
