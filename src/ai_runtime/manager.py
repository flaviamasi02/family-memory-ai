from __future__ import annotations
import importlib.util, sys, urllib.request
from pathlib import Path
from threading import Event
from core.application_data import ApplicationDataPathService, get_app_data_service
from vision.embedding_provider import now_iso
from ai_runtime.executor import AIRuntimeCommandExecutor, CommandResult
from ai_runtime.models import *
from ai_runtime.registry import AIRuntimeRegistry
from ai_runtime.storage import AIRuntimeStorage

class AIRuntimeManager:
    def __init__(self, registry: AIRuntimeRegistry|None=None, app_data: ApplicationDataPathService|None=None, executor: AIRuntimeCommandExecutor|None=None):
        self.registry=registry or AIRuntimeRegistry(); self.app_data=app_data or get_app_data_service(); self.storage=AIRuntimeStorage(self.app_data); self.executor=executor or AIRuntimeCommandExecutor()
    def inspect_environment(self, interpreter: str|Path|None=None) -> PythonEnvironmentInfo: return self.executor.validate_interpreter(interpreter or sys.executable)
    def installation_record(self, provider_id:str) -> AIRuntimeInstallationRecord:
        rec=self.storage.installations().get(provider_id)
        if rec: return rec
        d=self.registry.require(provider_id); cache=self.storage.cache_dir_for(provider_id)
        return AIRuntimeInstallationRecord(provider_id=provider_id, local_model_cache_path=str(cache), local_installation_path=str(cache), checkpoint_id=d.checkpoint_id, revision=d.revision)
    def save_environment_selection(self, provider_id:str, interpreter:str|Path) -> PythonEnvironmentInfo:
        env=self.inspect_environment(interpreter); rec=self.installation_record(provider_id)
        rec.interpreter_path=env.interpreter_path; rec.python_version=env.python_version; rec.environment_path=env.environment_path; rec.environment_type=env.environment_type; rec.last_validation_result=env.message or ('valid' if env.valid else 'invalid'); self.storage.save_installation(rec); return env
    def status(self, provider_id:str) -> AIRuntimeStatus:
        d=self.registry.get(provider_id)
        if not d: return AIRuntimeStatus(provider_id,AIRuntimeState.NOT_REGISTERED.value,False,False,False,last_status_check=now_iso())
        rec=self.installation_record(provider_id); cache=Path(rec.local_model_cache_path or self.storage.cache_dir_for(provider_id))
        env=self.inspect_environment(rec.interpreter_path) if rec.interpreter_path else self.inspect_environment(sys.executable)
        if rec.interpreter_path:
            missing_deps=self.executor.imports_available(rec.interpreter_path, tuple(dep.import_name for dep in d.required_python_packages))
        else:
            missing_deps=tuple(dep.import_name for dep in d.required_python_packages if importlib.util.find_spec(dep.import_name) is None)
        missing_files=tuple(f.relative_path for f in d.required_model_files if not (cache/f.relative_path).exists())
        verified=rec.last_validation_result == 'provider verification passed'
        if not verified and d.verifier and not d.required_python_packages:
            try:
                verified=bool(d.verifier(cache))
            except Exception as exc:
                rec.last_error=str(exc)
        state=AIRuntimeState.READY.value if verified else AIRuntimeState.VERIFYING.value
        if d.planned: state=AIRuntimeState.UNSUPPORTED.value
        elif not env.valid: state=AIRuntimeState.DEPENDENCIES_MISSING.value
        elif missing_deps: state=AIRuntimeState.DEPENDENCIES_MISSING.value
        elif missing_files: state=AIRuntimeState.MODEL_NOT_DOWNLOADED.value
        elif not verified: state=AIRuntimeState.VERIFYING.value
        rec.installation_state=state; rec.last_status_check=now_iso(); rec.installed_disk_usage_bytes=self.storage.disk_usage(cache); self.storage.save_installation(rec)
        return AIRuntimeStatus(provider_id,state,state==AIRuntimeState.READY.value,not missing_deps,not missing_files,'Unknown',rec.last_error,rec.last_status_check,missing_deps,missing_files,env)
    def build_installation_plan(self, provider_id:str, interpreter:str|Path|None=None, device:str='CPU') -> AIRuntimeInstallationPlan:
        d=self.registry.require(provider_id); env=self.inspect_environment(interpreter or self.installation_record(provider_id).interpreter_path or sys.executable); cache=self.storage.cache_dir_for(provider_id)
        packages=tuple((dep.package_name or dep.import_name)+(dep.version_spec or '') for dep in d.required_python_packages)
        actions=[AIRuntimePlanAction(AIRuntimeActionType.CREATE_DIRECTORY, f'Create model cache for {d.display_name}', destination=str(cache))]
        actions += [AIRuntimePlanAction(AIRuntimeActionType.INSTALL_PYTHON_PACKAGE, f'Install {pkg}', argv=(env.interpreter_path,'-m','pip','install',pkg), package_name=pkg, timeout_seconds=1800) for pkg in packages]
        actions += [AIRuntimePlanAction(AIRuntimeActionType.DOWNLOAD_MODEL_FILE, f'Download {f.relative_path}', destination=str(cache/f.relative_path), url='https://huggingface.co/apple/MobileCLIP-S0/resolve/main/mobileclip_s0.pt', sha256=f.sha256, timeout_seconds=1800) for f in d.required_model_files]
        actions += [AIRuntimePlanAction(AIRuntimeActionType.VERIFY_IMPORT, f'Verify import {dep.import_name}', argv=(env.interpreter_path,'-c',f'import {dep.import_name}')) for dep in d.required_python_packages]
        actions += [AIRuntimePlanAction(AIRuntimeActionType.VERIFY_PROVIDER, f'Verify {d.display_name} provider'), AIRuntimePlanAction(AIRuntimeActionType.RECORD_INSTALLATION, 'Record installation metadata')]
        warns=['No action runs until the Product Owner confirms this plan.','The active application environment is not modified; every package command uses the selected interpreter explicitly.','CPU-only inference is used; no NVIDIA GPU is required.','If no authoritative checksum is published, verification uses file size plus model load and embedding checks.']
        if not env.valid: warns.append(env.message or 'Selected Python environment is not valid or pip is unavailable.')
        if env.environment_path and Path(env.environment_path).resolve() == Path(sys.prefix).resolve(): warns.append('Selected environment appears to be the active application environment; choose .venv-mobileclip to avoid modifying the app runtime.')
        return AIRuntimeInstallationPlan(d.provider_id,d.display_name,d.checkpoint_id,packages,tuple(f.relative_path for f in d.required_model_files),d.expected_download_size,str(cache),{'code':d.code_license,'model':d.model_license},device,env,False,True,'~750 MB to 1.5 GB including CPU PyTorch, torchvision, Pillow, MobileCLIP code, and checkpoint',tuple(warns),tuple(actions),False)
    def _download(self, action:AIRuntimePlanAction, cancel_event:Event|None=None) -> CommandResult:
        import time
        start=time.perf_counter(); dst=Path(action.destination); dst.parent.mkdir(parents=True, exist_ok=True); part=dst.with_suffix(dst.suffix+'.partial')
        if dst.exists(): return CommandResult(action.action_type.value,0,'already exists; no silent redownload','',time.perf_counter()-start)
        try:
            with urllib.request.urlopen(action.url, timeout=30) as r, part.open('wb') as f:
                while True:
                    if cancel_event and cancel_event.is_set(): part.unlink(missing_ok=True); return CommandResult(action.action_type.value,-1,'','Cancelled',time.perf_counter()-start,cancelled=True)
                    chunk=r.read(1024*1024)
                    if not chunk: break
                    f.write(chunk)
            part.replace(dst); return CommandResult(action.action_type.value,0,f'downloaded {dst.stat().st_size} bytes','',time.perf_counter()-start)
        except Exception as exc:
            part.unlink(missing_ok=True); return CommandResult(action.action_type.value,1,'',str(exc),time.perf_counter()-start)
    def verify_provider(self, provider_id:str, cancel_event:Event|None=None) -> CommandResult:
        rec=self.installation_record(provider_id); interp=rec.interpreter_path or sys.executable; cache=Path(rec.local_model_cache_path or self.storage.cache_dir_for(provider_id))
        script="""
import json, math, pathlib, sys
import torch, torchvision, mobileclip
from PIL import Image
ckpt=pathlib.Path(sys.argv[1])/'mobileclip_s0.pt'
assert ckpt.exists(), ckpt
model,_,preprocess=mobileclip.create_model_and_transforms('mobileclip_s0', pretrained=str(ckpt))
model.eval(); tok=mobileclip.get_tokenizer('mobileclip_s0')
img=Image.new('RGB',(224,224),(128,128,128)); tensor=preprocess(img).unsqueeze(0)
with torch.no_grad(): vec=model.encode_image(tensor).squeeze(0).cpu().tolist()
assert vec and all(math.isfinite(float(x)) for x in vec)
print(json.dumps({'embedding_dimension':len(vec),'tokenizer':bool(tok)}))
"""
        action=AIRuntimePlanAction(AIRuntimeActionType.VERIFY_PROVIDER,'Verify provider end-to-end',argv=(interp,'-c',script,str(cache)),timeout_seconds=900)
        res=self.executor.run_action(action,cancel_event); rec.last_status_check=now_iso(); rec.installed_disk_usage_bytes=self.storage.disk_usage(cache)
        if res.returncode==0:
            rec.last_validation_result='provider verification passed'; rec.installation_state=AIRuntimeState.READY.value; rec.last_error=''
            if not rec.install_date: rec.install_date=now_iso()
            self.storage.append_history(AIRuntimeHistoryRecord(provider_id,now_iso(),'verification completed','passed',interpreter_path=interp,message=res.stdout))
        else:
            rec.last_validation_result='provider verification failed'; rec.installation_state=AIRuntimeState.FAILED.value; rec.last_error=res.stderr or res.stdout
            self.storage.append_history(AIRuntimeHistoryRecord(provider_id,now_iso(),'verification completed','failed',interpreter_path=interp,error_summary=rec.last_error))
        self.storage.save_installation(rec); return res
    def execute_installation_plan(self, plan:AIRuntimeInstallationPlan, cancel_event:Event|None=None):
        if not plan.confirmed: raise PermissionError('Installation plan must be explicitly confirmed before execution.')
        results=[]; self.storage.append_history(AIRuntimeHistoryRecord(plan.provider_id,now_iso(),'installation started','started',interpreter_path=plan.python_environment.interpreter_path))
        for action in plan.actions:
            if action.action_type == AIRuntimeActionType.RECORD_INSTALLATION: continue
            if action.action_type == AIRuntimeActionType.DOWNLOAD_MODEL_FILE: res=self._download(action,cancel_event)
            elif action.action_type == AIRuntimeActionType.VERIFY_PROVIDER: res=self.verify_provider(plan.provider_id,cancel_event)
            else: res=self.executor.run_action(action,cancel_event)
            results.append(res)
            if res.returncode != 0: self.storage.append_history(AIRuntimeHistoryRecord(plan.provider_id,now_iso(),action.action_type.value,'failed',interpreter_path=plan.python_environment.interpreter_path,error_summary=res.stderr)); break
        if results and all(r.returncode==0 for r in results): self.storage.append_history(AIRuntimeHistoryRecord(plan.provider_id,now_iso(),'installation completed','passed',interpreter_path=plan.python_environment.interpreter_path))
        return results
    def removal_plan(self, provider_id:str, include_packages:bool=False) -> AIRuntimeInstallationPlan:
        d=self.registry.require(provider_id); rec=self.installation_record(provider_id); cache=Path(rec.local_model_cache_path)
        warnings=['Removal deletes only manager-owned checkpoint/cache files. Photos, thumbnails, categories, learning profiles, and source images are never removed. Provider-generated embeddings require explicit selection.']
        if include_packages: warnings.append('Optional package removal can affect shared packages and requires a separate explicit warning/confirmation.')
        actions=(AIRuntimePlanAction(AIRuntimeActionType.REMOVE_OWNED_PATH, 'Remove owned MobileCLIP checkpoint/cache', destination=str(cache)), AIRuntimePlanAction(AIRuntimeActionType.RECORD_REMOVAL,'Record removal metadata'))
        return AIRuntimeInstallationPlan(provider_id,d.display_name,d.checkpoint_id,(),(), '0 B', str(cache), {'code':d.code_license,'model':d.model_license}, 'CPU', self.inspect_environment(rec.interpreter_path or sys.executable), False, False, '0 B', tuple(warnings), actions, False)
    def diagnostics(self) -> dict[str,int]:
        statuses=[self.status(pid).state for pid in self.registry.provider_ids()]; hist=self.storage.history()
        return {'providers_registered':len(statuses),'ready':statuses.count(AIRuntimeState.READY.value),'not_installed':statuses.count(AIRuntimeState.MODEL_NOT_DOWNLOADED.value)+statuses.count(AIRuntimeState.NOT_INSTALLED.value),'failed':statuses.count(AIRuntimeState.FAILED.value),'installations_started':sum(1 for h in hist if h.action=='installation started'),'installations_completed':sum(1 for h in hist if h.action=='installation completed'),'installations_failed':sum(1 for h in hist if 'failed' in h.outcome),'verifications_completed':sum(1 for h in hist if h.action=='verification completed'),'removals_completed':sum(1 for h in hist if h.action=='removal completed')}

def create_default_runtime_manager(app_data:ApplicationDataPathService|None=None) -> AIRuntimeManager:
    from ai_runtime.mobileclip_registration import register_mobileclip_runtime
    m=AIRuntimeManager(app_data=app_data); register_mobileclip_runtime(m.registry); return m
