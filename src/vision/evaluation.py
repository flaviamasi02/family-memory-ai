from __future__ import annotations
import json, statistics, time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event
from typing import Any
from core.application_data import get_app_data_service, atomic_write_json
from core.category_registry import get_category_registry
from vision.embedding_provider import EmbeddingStore, VisionEmbeddingProvider, cosine, now_iso

PROMPTS={
 'family_photo':['a personal family photograph containing people','a family memory photo with relatives or friends'],
 'personal_photo':['a personal photograph from everyday life','a private personal camera photo'],
 'screenshot':['a screenshot of a computer or phone interface','a captured software screen or app interface'],
 'document':['a scanned paper document with text','a photographed paper document or scan'],
 'advertisement':['a promotional advertisement or marketing graphic','an image designed as an advertisement'],
 'meme':['a meme or humorous internet graphic','a graphic with text intended as a meme'],
 'object_photo':['a photo focused on an object or product','a close up object photograph'],
 'natural_photograph':['a natural camera photograph of a real scene','an outdoor or indoor real-world photograph'],
}
UNKNOWN_THRESHOLD=.24
@dataclass
class EvaluationProgress:
    state:str; processed:int=0; total:int=0; message:str=''

def batched(items, n):
    for i in range(0,len(items),n): yield items[i:i+n]

def zero_shot_scores(provider, image_embedding):
    cats=[]
    for cid, prompts in PROMPTS.items():
        text_embs=provider.embed_texts(prompts)
        score=max(cosine(image_embedding, t) for t in text_embs) if text_embs else 0.0
        cats.append({'category_id':cid,'label':get_category_registry().label_for(cid),'score':score,'prompts':prompts})
    cats.sort(key=lambda x:x['score'], reverse=True)
    top=cats[0] if cats else {'score':0,'category_id':'unknown'}
    result='unknown' if top['score'] < UNKNOWN_THRESHOLD else top['category_id']
    return {'result':result,'insufficient_evidence':result=='unknown','top_candidates':cats[:5]}

def build_prototypes(corrections, embeddings):
    bycat={}
    for key, cat in corrections.items():
        if key in embeddings: bycat.setdefault(cat,[]).append((key,embeddings[key]))
    protos={}
    for cat, vals in bycat.items():
        if len(vals)<2: continue
        dim=len(vals[0][1]); avg=[sum(v[i] for _,v in vals)/len(vals) for i in range(dim)]
        from vision.embedding_provider import normalize
        protos[cat]={'training_examples':len(vals),'embedding':normalize(avg),'supporting_examples':[k for k,_ in vals[:5]]}
    return protos

def evaluate_prototypes(corrections, embeddings):
    rows=[]
    for eval_key, true_cat in corrections.items():
        train={k:v for k,v in corrections.items() if k!=eval_key}
        protos=build_prototypes(train, embeddings)
        if eval_key not in embeddings: continue
        scored=[]
        for cat,p in protos.items(): scored.append({'category_id':cat,'similarity':cosine(embeddings[eval_key], p['embedding']),'training_examples':p['training_examples'],'nearest_supporting_examples':p['supporting_examples']})
        scored.sort(key=lambda x:x['similarity'], reverse=True)
        rows.append({'photo_key':eval_key,'true_category':true_cat,'top_matches':scored[:3],'conservative': not scored or scored[0]['similarity']<0.30})
    return rows

def run_evaluation(provider: VisionEmbeddingProvider, paths:list[Path], max_images:int=100, store:EmbeddingStore|None=None, cancel_event:Event|None=None, progress=None, corrected_examples:dict[str,str]|None=None):
    max_images=max(1,min(300,int(max_images))); sample=[Path(p) for p in paths[:max_images]]; store=store or EmbeddingStore()
    status=provider.availability(); started=time.perf_counter(); load_started=time.perf_counter(); cache_hits=cache_misses=0; errors=[]; times=[]; records=[]
    provider.load(cancel_event); load_time=time.perf_counter()-load_started
    total=len(sample)
    for batch in batched(sample, getattr(provider,'batch_size',4)):
        if cancel_event and cancel_event.is_set(): break
        pending=[]
        for p in batch:
            rec=store.get_valid(p, provider.metadata)
            if rec: cache_hits+=1; records.append(rec)
            else: cache_misses+=1; pending.append(p)
        if pending:
            t=time.perf_counter(); new=provider.embed_images(pending, cancel_event); elapsed=(time.perf_counter()-t)/max(1,len(pending)); times.extend([elapsed]*len(pending))
            for rec in new:
                if rec.status=='ok': store.put(rec)
                else: errors.append({'photo_key':rec.photo_key,'error':rec.error})
                records.append(rec)
        if progress: progress(EvaluationProgress('Processing', len(records), total, f'{len(records)}/{total} images'))
    total_time=time.perf_counter()-started; ok=[r for r in records if r.status=='ok' and r.embedding]
    zs=[]
    for r in ok[:20]: zs.append({'photo_key':r.photo_key, **zero_shot_scores(provider, r.embedding)})
    emb_map={r.photo_key:r.embedding for r in ok}; proto=evaluate_prototypes(corrected_examples or {}, emb_map)
    mean=statistics.mean(times) if times else 0.0; med=statistics.median(times) if times else 0.0; p95=statistics.quantiles(times,n=20)[18] if len(times)>=20 else (max(times) if times else 0.0)
    per_min=(len(ok)/total_time*60) if total_time>0 else 0.0
    est=lambda n: (n/per_min*60) if per_min else 0.0
    report={'schema_version':1,'generated_at':now_iso(),'provider':asdict(provider.metadata),'status':status.state,'device':getattr(provider,'device','cpu'),'model_load_time_seconds':load_time,'number_of_images':total,'successful_images':len(ok),'failed_images':len(records)-len(ok),'total_processing_time_seconds':total_time,'mean_embedding_time_seconds':mean,'median_embedding_time_seconds':med,'p95_embedding_time_seconds':p95,'images_per_minute':per_min,'cache_hits':cache_hits,'cache_misses':cache_misses,'embedding_dimension':provider.metadata.embedding_dimension,'estimated_seconds':{'1000_images':est(1000),'10000_images':est(10000),'50000_images':est(50000)},'estimated_storage_50000_embeddings_mb':round((provider.metadata.embedding_dimension*4*50000)/(1024*1024),2),'projections_are_estimates':True,'zero_shot':zs,'personalized_prototypes':proto,'errors':errors[:50]}
    out=get_app_data_service().reports_dir()/f'mobileclip_evaluation_{int(time.time())}.json'; atomic_write_json(out, report); report['report_path']=str(out)
    return report
