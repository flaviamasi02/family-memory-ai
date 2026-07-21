from __future__ import annotations
from pathlib import Path
from threading import Event

from core.application_data import get_app_data_service
from vision.embedding_provider import EmbeddingRecord, ModelMetadata, ProviderStatus, VisionEmbeddingProvider, normalize, now_iso, source_identity

MOBILECLIP_S0 = ModelMetadata(
    provider_id='mobileclip', checkpoint_id='apple/MobileCLIP-S0', revision='main', license='Apple ML Research Model Terms (model); MIT for official code', source_url='https://huggingface.co/apple/MobileCLIP-S0', parameters='~50M class lightweight MobileCLIP family; checkpoint file 216 MB', download_size='216 MB checkpoint on Hugging Face', disk_usage='Approximately 216 MB plus package/cache overhead', embedding_dimension=512)

class MobileCLIPEmbeddingProvider:
    def __init__(self, model_cache_dir: str | Path | None = None, batch_size:int=4):
        self.metadata=MOBILECLIP_S0; self.batch_size=max(1,min(16,int(batch_size)))
        self.requires_image_decode_validation=True
        self.model_cache_dir=Path(model_cache_dir) if model_cache_dir else get_app_data_service().cache_dir('models') / 'mobileclip-s0'
        self._model=None; self._preprocess=None; self._tokenizer=None; self._torch=None; self.device='cpu'
    def availability(self):
        missing=[]
        for name in ('torch','torchvision','mobileclip'):
            try: __import__(name)
            except Exception: missing.append(name)
        if missing: return ProviderStatus('Not installed', 'Optional MobileCLIP dependencies are missing.', tuple(missing))
        if not any(self.model_cache_dir.glob('*.pt')): return ProviderStatus('Model not downloaded', f'Expected explicit checkpoint download under {self.model_cache_dir}')
        return ProviderStatus('Ready','MobileCLIP dependencies and local checkpoint are present.')
    def load(self, cancel_event: Event | None=None):
        if cancel_event and cancel_event.is_set(): raise RuntimeError('Cancelled')
        if self._model is not None: return
        import torch, mobileclip
        self._torch=torch
        ckpts=list(self.model_cache_dir.glob('*.pt'))
        if not ckpts: raise FileNotFoundError(f'MobileCLIP checkpoint not found in {self.model_cache_dir}')
        model, _, preprocess = mobileclip.create_model_and_transforms('mobileclip_s0', pretrained=str(ckpts[0]))
        model.eval(); model.to('cpu')
        self._model=model; self._preprocess=preprocess; self._tokenizer=mobileclip.get_tokenizer('mobileclip_s0')
    def embed_images(self, paths:list[Path], cancel_event:Event|None=None):
        self.load(cancel_event); out=[]
        from PIL import Image, ImageOps
        for path in paths[:self.batch_size]:
            if cancel_event and cancel_event.is_set(): break
            try:
                key,mt,sz,fp=source_identity(Path(path))
                with Image.open(path) as img:
                    tensor=self._preprocess(ImageOps.exif_transpose(img).convert('RGB')).unsqueeze(0)
                with self._torch.no_grad(): vec=self._model.encode_image(tensor).squeeze(0).cpu().tolist()
                emb=normalize(vec)
                out.append(EmbeddingRecord(key,fp,mt,sz,self.metadata.provider_id,self.metadata.checkpoint_id,self.metadata.revision,len(emb),emb,now_iso()))
            except Exception as e:
                out.append(EmbeddingRecord(str(path),'',0,0,self.metadata.provider_id,self.metadata.checkpoint_id,self.metadata.revision,self.metadata.embedding_dimension,[],now_iso(),'failed',str(e)))
        return out
    def embed_texts(self, prompts:list[str], cancel_event:Event|None=None):
        self.load(cancel_event)
        tokens=self._tokenizer(prompts)
        with self._torch.no_grad(): arr=self._model.encode_text(tokens).cpu().tolist()
        return [normalize(v) for v in arr]
    def release(self):
        self._model=None; self._preprocess=None; self._tokenizer=None
