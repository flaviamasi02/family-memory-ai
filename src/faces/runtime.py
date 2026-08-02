"""Windows-safe managed environment for local face detection."""
from __future__ import annotations
import json, subprocess, sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from core.application_data import get_app_data_service

OPENCV_PACKAGE = "opencv-python-headless==4.10.0.84"
NUMPY_PACKAGE = "numpy==1.26.4"
PILLOW_PACKAGE = "Pillow==10.4.0"
CONFLICTS = ("cv2", "opencv-python", "opencv-python-headless", "opencv-contrib-python", "opencv-contrib-python-headless")

def _now(): return datetime.now(timezone.utc).isoformat()

DIAGNOSTIC_SCRIPT = r'''
import importlib.metadata as md, json, pathlib, site, sys
names = ['cv2','opencv-python','opencv-python-headless','opencv-contrib-python','opencv-contrib-python-headless','numpy']
out={'executable':sys.executable,'prefix':sys.prefix,'python_version':sys.version,'cwd':str(pathlib.Path.cwd()),'distributions':{}}
for n in names:
 try: out['distributions'][n]=md.version(n)
 except md.PackageNotFoundError: pass
try:
 import cv2
 out.update(cv2_file=getattr(cv2,'__file__',None),cv2_version=getattr(cv2,'__version__',None),has_data=hasattr(cv2,'data'),has_cascade=hasattr(cv2,'CascadeClassifier'))
 p=pathlib.Path(getattr(cv2,'__file__','')).resolve(); roots=[pathlib.Path(x).resolve() for x in site.getsitepackages()]
 out['in_site_packages']=any(p.is_relative_to(r) for r in roots)
except Exception as e: out['import_error']=type(e).__name__+': '+str(e)
print(json.dumps(out))
'''
VERIFY_SCRIPT = DIAGNOSTIC_SCRIPT + r'''
out=json.loads(json.dumps(out))
try:
 import cv2
 if not getattr(cv2,'__version__',None): raise RuntimeError('CV2_VERSION_MISSING')
 if not out.get('in_site_packages'): raise RuntimeError('CV2_SHADOWED:'+str(out.get('cv2_file')))
 if not hasattr(cv2,'data') or not getattr(cv2.data,'haarcascades',None): raise RuntimeError('CV2_DATA_MISSING')
 p=pathlib.Path(cv2.data.haarcascades)/'haarcascade_frontalface_default.xml'
 if not p.is_file(): raise RuntimeError('CASCADE_XML_MISSING')
 if not hasattr(cv2,'CascadeClassifier'): raise RuntimeError('CASCADE_API_MISSING')
 c=cv2.CascadeClassifier(str(p))
 if c.empty(): raise RuntimeError('CASCADE_EMPTY')
 out.update(ok=True,cascade_path=str(p))
except Exception as e: out.update(ok=False,verification_error=str(e))
print(json.dumps(out))
'''

@dataclass
class FaceRuntimeStatus:
 state:str='Not installed'; installed_version:str='not installed'; detector_backend:str='OpenCV Haar (managed local CPU)'; model_version:str='haarcascade_frontalface_default v1'; install_location:str=''; interpreter_path:str=''; last_verification:str='never'; last_error:str='none'
 @property
 def ready(self): return self.state=='Ready'

class FaceRuntimeManager:
 def __init__(self,root:Path|None=None,runner=None):
  self.root=Path(root or (get_app_data_service().root/'runtimes'/'.venv-face-runtime')); self.root.parent.mkdir(parents=True,exist_ok=True)
  self.state_path=self.root.parent/'face-runtime.json'; self.log_path=self.root.parent/'face-runtime.log'; self.runner=runner or subprocess.run
 @property
 def interpreter_path(self): return self.root/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
 def status(self):
  if not self.state_path.exists(): return FaceRuntimeStatus(install_location=str(self.root),interpreter_path=str(self.interpreter_path))
  try:
   status=FaceRuntimeStatus(**json.loads(self.state_path.read_text(encoding='utf-8')))
   if status.ready and (not status.interpreter_path or not Path(status.interpreter_path).is_file()):
    status.state='Needs repair'; status.last_error='The previous runtime was not isolated. Repair will create a dedicated Face Recognition environment.'
   return status
  except (OSError,ValueError,TypeError): return FaceRuntimeStatus('Needs repair',install_location=str(self.root),interpreter_path=str(self.interpreter_path),last_error='Runtime state is damaged. Repair will recreate the managed environment.')
 def diagnose(self,interpreter=None):
  result=self._run([str(interpreter or self.interpreter_path),'-c',DIAGNOSTIC_SCRIPT]); return self._json(result)
 def install(self,progress=None): return self._install(progress)
 def repair(self,progress=None): return self._install(progress)
 def _install(self,progress=None):
  if progress: progress(5,'Preparing a separate Face Recognition environment…')
  if not self.interpreter_path.exists():
   result=self._run([sys.executable,'-m','venv',str(self.root)])
   if result.returncode: return self._fail('environment',result.stderr)
  if progress: progress(20,'Diagnosing existing OpenCV packages…')
  diagnosis=self.diagnose()
  installed=set(diagnosis.get('distributions',{})); conflicts=[x for x in CONFLICTS if x in installed]
  if conflicts:
   result=self._run([str(self.interpreter_path),'-m','pip','uninstall','-y',*conflicts])
   if result.returncode: return self._fail('permission',result.stderr)
  if progress: progress(40,'Installing the supported local detector…')
  result=self._run([str(self.interpreter_path),'-m','pip','install','--upgrade','--force-reinstall',OPENCV_PACKAGE,NUMPY_PACKAGE,PILLOW_PACKAGE])
  if result.returncode: return self._fail('package',result.stderr)
  if progress: progress(80,'Verifying OpenCV API and detector model…')
  return self.verify(progress)
 def verify(self,progress=None):
  if not self.interpreter_path.exists(): return self._fail('environment','Managed face interpreter is missing.')
  result=self._run([str(self.interpreter_path),'-c',VERIFY_SCRIPT]); data=self._json(result)
  if result.returncode or not data.get('ok'): return self._fail('verification',data.get('verification_error') or data.get('import_error') or result.stderr)
  distributions=data.get('distributions',{}); active=[x for x in CONFLICTS if x in distributions]
  if active != ['opencv-python-headless']: return self._fail('conflict','Multiple or unsupported OpenCV distributions are active: '+', '.join(active))
  status=FaceRuntimeStatus('Ready',data['cv2_version'],install_location=str(self.root),interpreter_path=str(self.interpreter_path),last_verification=_now())
  self._save(status)
  if progress: progress(100,'Face recognition runtime is ready.')
  return status
 def remove(self,progress=None):
  import shutil
  if progress: progress(20,'Removing the separate Face Recognition environment…')
  shutil.rmtree(self.root,ignore_errors=True); status=FaceRuntimeStatus(install_location=str(self.root),interpreter_path=str(self.interpreter_path)); self._save(status)
  if progress: progress(100,'Face recognition runtime removed.')
  return status
 def _fail(self,kind,detail):
  messages={'package':'Package download or installation failed. Check the connection and try Repair.','permission':'Windows denied access to the managed runtime. Close other Python processes and try Repair.','environment':'The managed Face Recognition Python environment is missing or invalid. Choose Repair.','conflict':'Conflicting OpenCV packages were detected. Repair will remove them and reinstall one supported package.','verification':'The OpenCV installation is invalid or incomplete. Repair will clean and reinstall it.'}
  message=messages[kind]+' Technical detail: '+str(detail or 'unknown error').strip().splitlines()[-1]
  status=FaceRuntimeStatus(kind.title()+' failed',install_location=str(self.root),interpreter_path=str(self.interpreter_path),last_verification=_now(),last_error=message); self._save(status); raise RuntimeError(message)
 def _run(self,args):
  try: result=self.runner(args,capture_output=True,text=True,timeout=1800,cwd=str(self.root.parent))
  except (OSError,subprocess.SubprocessError) as exc: result=type('Result',(),{'returncode':1,'stdout':'','stderr':str(exc)})()
  with self.log_path.open('a',encoding='utf-8') as f: f.write(f"[{_now()}] {' '.join(args)}\n{result.stdout}\n{result.stderr}\n")
  return result
 @staticmethod
 def _json(result):
  for line in reversed((result.stdout or '').splitlines()):
   try: return json.loads(line)
   except json.JSONDecodeError: continue
  return {'import_error':result.stderr or 'Diagnostic produced no JSON output'}
 def _save(self,status): self.state_path.write_text(json.dumps(asdict(status),indent=2),encoding='utf-8')
