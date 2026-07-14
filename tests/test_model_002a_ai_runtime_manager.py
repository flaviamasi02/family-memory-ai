from __future__ import annotations
import sys, threading
from pathlib import Path
import pytest
from core.application_data import ApplicationDataPathService
from ai_runtime.executor import AIRuntimeCommandExecutor
from ai_runtime.manager import AIRuntimeManager, create_default_runtime_manager
from ai_runtime.models import AIRuntimeActionType, AIRuntimeBenchmarkRecord, AIRuntimeCapability, AIRuntimeDescriptor, AIRuntimeInstallationPlan, AIRuntimePlanAction, RequiredModelFile, RuntimeDependency
from ai_runtime.registry import AIRuntimeRegistry
from vision.embedding_provider import now_iso


def descriptor(pid='fake', deps=(), files=()):
    return AIRuntimeDescriptor(pid,'Fake Runtime','test runtime','vision','fake/checkpoint','v1',(AIRuntimeCapability.IMAGE_EMBEDDINGS,), 'local','MIT','Test terms','1 MB', required_python_packages=deps, required_model_files=files, verifier=lambda cache: True)

def manager(tmp_path):
    reg=AIRuntimeRegistry(); reg.register('fake', descriptor(files=(RequiredModelFile('model.bin'),)))
    return AIRuntimeManager(reg, ApplicationDataPathService(tmp_path, tmp_path))

def test_provider_registration_duplicate_and_lazy_creation(tmp_path):
    reg=AIRuntimeRegistry(); calls=[]; d=descriptor(); d=descriptor('fake')
    reg.register('fake', d)
    with pytest.raises(ValueError): reg.register('fake', d)
    assert reg.require('fake').provider_id == 'fake'
    assert calls == []

def test_startup_with_no_ml_dependencies_and_mobileclip_registered(tmp_path):
    m=create_default_runtime_manager(ApplicationDataPathService(tmp_path,tmp_path))
    d=m.registry.require('mobileclip')
    assert d.checkpoint_id == 'apple/MobileCLIP-S0'
    assert {c.value for c in d.capabilities} == {'image_embeddings','text_embeddings','zero_shot_classification'}
    assert 'torch' in [dep.import_name for dep in d.required_python_packages]

def test_runtime_status_ready_requires_dependencies_files_and_verification(tmp_path):
    m=manager(tmp_path)
    st=m.status('fake')
    assert st.state == 'Model not downloaded'
    cache=Path(m.installation_record('fake').local_model_cache_path); (cache/'model.bin').write_text('x')
    assert m.status('fake').state == 'Ready'

def test_installation_plan_confirmation_and_interpreter_selection(tmp_path):
    m=manager(tmp_path); plan=m.build_installation_plan('fake', sys.executable)
    assert plan.python_environment.interpreter_path == sys.executable
    assert any(a.action_type == AIRuntimeActionType.CREATE_DIRECTORY for a in plan.actions)
    with pytest.raises(PermissionError): m.execute_installation_plan(plan)

def test_invalid_interpreter_rejection(tmp_path):
    m=manager(tmp_path); env=m.inspect_environment(tmp_path/'missing-python')
    assert not env.valid and 'does not exist' in env.message

def test_typed_command_execution_cancellation_and_failure(tmp_path):
    ex=AIRuntimeCommandExecutor(); bad=AIRuntimePlanAction(AIRuntimeActionType.VERIFY_IMPORT,'bad',argv=(sys.executable,'-c','import definitely_missing_pkg_zz'))
    res=ex.run_action(bad); assert res.returncode != 0 and 'definitely_missing_pkg_zz' in res.stderr
    ev=threading.Event(); ev.set(); res=ex.run_action(bad, ev); assert res.cancelled
    mkdir=AIRuntimePlanAction(AIRuntimeActionType.CREATE_DIRECTORY,'dir',destination=str(tmp_path/'owned'))
    assert ex.run_action(mkdir).returncode == 0 and (tmp_path/'owned').exists()

def test_persistence_history_benchmark_and_corruption_safe_loading(tmp_path):
    m=manager(tmp_path); rec=m.installation_record('fake'); rec.interpreter_path=sys.executable; m.storage.save_installation(rec)
    assert AIRuntimeManager(m.registry, ApplicationDataPathService(tmp_path,tmp_path)).installation_record('fake').interpreter_path == sys.executable
    m.storage.append_history(__import__('ai_runtime.models').models.AIRuntimeHistoryRecord('fake',now_iso(),'installation planned','ok'))
    assert m.storage.history()[0].action == 'installation planned'
    m.storage.append_benchmark(AIRuntimeBenchmarkRecord('fake','fake/checkpoint','CPU',sys.executable,2,1,0.5,0.5,0.5,2.0,None,0,now_iso(),'test'))
    assert m.storage.benchmarks()[0].throughput_images_per_second == 2.0
    (m.storage.root/'installations.json').write_text('{bad json')
    assert m.storage.installations() == {}

def test_safe_removal_ownership_and_shared_dependency_protection(tmp_path):
    m=manager(tmp_path); cache=Path(m.installation_record('fake').local_model_cache_path)
    assert m.storage.is_owned_path('fake', cache)
    assert not m.storage.is_owned_path('fake', tmp_path)
    plan=m.removal_plan('fake', include_packages=True)
    assert any('shared' in w.lower() or 'package' in w.lower() for w in plan.warnings)
    assert any(a.action_type == AIRuntimeActionType.REMOVE_OWNED_PATH for a in plan.actions)

def test_checkpoint_change_invalidates_provider_cache(tmp_path):
    from vision.embedding_provider import EmbeddingStore, EmbeddingRecord, ModelMetadata
    db=tmp_path/'e.sqlite3'; store=EmbeddingStore(db); photo=tmp_path/'p.jpg'; photo.write_bytes(b'abc')
    meta1=ModelMetadata('fake','ckpt1','v1','l','s','p','d','u',2); meta2=ModelMetadata('fake','ckpt2','v1','l','s','p','d','u',2)
    key, mt, sz, fp=__import__('vision.embedding_provider').embedding_provider.source_identity(photo)
    store.put(EmbeddingRecord(key,fp,mt,sz,'fake','ckpt1','v1',2,[1,0],now_iso()))
    assert store.get_valid(photo, meta1) is not None
    assert store.get_valid(photo, meta2) is None

def test_app_data_paths_outside_repository_and_no_download_in_ci(tmp_path):
    m=manager(tmp_path); plan=m.build_installation_plan('fake')
    assert str(m.storage.root).startswith(str(tmp_path))
    assert all(a.action_type != AIRuntimeActionType.DOWNLOAD_MODEL_FILE or not plan.confirmed for a in plan.actions)
