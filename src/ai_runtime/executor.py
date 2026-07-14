from __future__ import annotations
import os, platform, subprocess, sys, time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from ai_runtime.models import AIRuntimeActionType, AIRuntimePlanAction, PythonEnvironmentInfo

@dataclass
class CommandResult:
    action_type: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool=False
    cancelled: bool=False

class AIRuntimeCommandExecutor:
    def __init__(self, output_limit:int=12000): self.output_limit=output_limit
    def validate_interpreter(self, interpreter: str|Path) -> PythonEnvironmentInfo:
        path=Path(interpreter).expanduser()
        if not path.exists(): return PythonEnvironmentInfo(str(path), valid=False, message='Interpreter does not exist.')
        try:
            code="import json,os,platform,sys,sysconfig; print(json.dumps({'version':platform.python_version(),'arch':platform.machine() or platform.architecture()[0],'prefix':sys.prefix,'base_prefix':getattr(sys,'base_prefix',sys.prefix),'pip':__import__('importlib.util').util.find_spec('pip') is not None,'purelib':sysconfig.get_paths().get('purelib','')}))"
            p=subprocess.run([str(path),'-c',code], text=True, capture_output=True, timeout=10, shell=False)
            if p.returncode!=0: return PythonEnvironmentInfo(str(path), valid=False, message=(p.stderr or p.stdout)[-500:])
            import json; d=json.loads(p.stdout.strip())
            env_path=d.get('prefix') or str(path.parent); writable=os.access(d.get('purelib') or env_path, os.W_OK)
            env_type='virtualenv' if d.get('prefix') != d.get('base_prefix') else 'system'
            
            version=d.get('version','')
            arch=d.get('arch','')
            major_minor=tuple(int(x) for x in version.split('.')[:2]) if version else (0,0)
            is_64='64' in arch or arch.lower() in ('amd64','x86_64','arm64','aarch64')
            valid=bool(d.get('pip')) and writable and is_64 and (major_minor >= (3,10))
            msg=''
            if not d.get('pip'): msg='pip is not available.'
            elif not writable: msg='Environment package directory is not writable.'
            elif not is_64: msg='Python architecture must be 64-bit.'
            elif major_minor < (3,10): msg='Python 3.10 or newer is required for MobileCLIP.'
            return PythonEnvironmentInfo(str(path), version, arch, env_path, env_type, bool(d.get('pip')), writable, valid, msg)
        except Exception as exc: return PythonEnvironmentInfo(str(path), valid=False, message=str(exc))
    def imports_available(self, interpreter: str|Path, import_names: tuple[str, ...]) -> tuple[str, ...]:
        missing=[]
        path=Path(interpreter).expanduser()
        for name in import_names:
            try:
                p=subprocess.run([str(path),'-c',f'import {name}'], text=True, capture_output=True, timeout=10, shell=False)
                if p.returncode != 0: missing.append(name)
            except Exception:
                missing.append(name)
        return tuple(missing)

    def run_action(self, action: AIRuntimePlanAction, cancel_event: Event|None=None) -> CommandResult:
        start=time.perf_counter()
        if cancel_event and cancel_event.is_set(): return CommandResult(action.action_type.value, -1, '', 'Cancelled before start', 0, cancelled=True)
        if action.action_type == AIRuntimeActionType.CREATE_DIRECTORY:
            Path(action.destination).mkdir(parents=True, exist_ok=True); return CommandResult(action.action_type.value,0,'created','',time.perf_counter()-start)
        if action.action_type in (AIRuntimeActionType.VERIFY_IMPORT, AIRuntimeActionType.INSTALL_PYTHON_PACKAGE, AIRuntimeActionType.CLONE_OR_INSTALL_OFFICIAL_PACKAGE):
            argv=list(action.argv)
            if not argv or any(not isinstance(x,str) or not x for x in argv): raise ValueError('Typed command action requires argv tokens')
            proc=subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False)
            try:
                while proc.poll() is None:
                    if cancel_event and cancel_event.is_set(): proc.terminate(); return CommandResult(action.action_type.value,-1,'','Cancelled',time.perf_counter()-start,cancelled=True)
                    if time.perf_counter()-start > action.timeout_seconds: proc.kill(); out,err=proc.communicate(); return CommandResult(action.action_type.value,-1,out[-self.output_limit:],err[-self.output_limit:],time.perf_counter()-start,timed_out=True)
                    time.sleep(0.05)
                out,err=proc.communicate()
                return CommandResult(action.action_type.value, proc.returncode, out[-self.output_limit:], err[-self.output_limit:], time.perf_counter()-start)
            finally:
                if proc.poll() is None: proc.kill()
        raise NotImplementedError(f'Execution for {action.action_type.value} is intentionally not implemented in MODEL-002A')

def current_environment_info() -> PythonEnvironmentInfo:
    return AIRuntimeCommandExecutor().validate_interpreter(sys.executable)
