#!/usr/bin/env python3
"""Compare unrestricted versus train-only correlation-family representative selection."""
import json
from collections import Counter
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
D=Path("docs/data")
read=lambda p:json.loads((D/p).read_text(encoding="utf8"))
pool={r["feature"]:r for r in read("neutral_variable_pool_reboot.json")["records"]}
coverage=read("neutral_80_candidate_data_gate.json")["variables"]
panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel.kommun_kod=panel.kommun_kod.str.zfill(4)
emp=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
emp.kommun_kod=emp.kommun_kod.str.zfill(4)
codes=set(emp.loc[emp.target_year==2024,"kommun_kod"]);assert len(codes)==290
extra=emp.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct").reset_index().rename(columns={"target_year":"year","residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct","workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"})
p=panel[panel.kommun_kod.isin(codes)&panel.year.between(2019,2023)].merge(extra,on=["year","kommun_kod"],how="left",validate="one_to_one")
SIZES=[4,6,10,14,20,30,40,60,80]
THRESHOLD=.85
def ordering(frame,y,candidates,strategy):
 z=frame[candidates].to_numpy(float)
 a=z-z.mean(axis=0);yy=y-y.mean()
 den=np.sqrt((a*a).sum(axis=0)*np.dot(yy,yy))
 scores=np.divide(np.abs(a.T@yy),den,out=np.zeros(len(candidates)),where=den>0)
 ranked=sorted(range(len(candidates)),key=lambda j:(-scores[j],candidates[j]))
 if strategy=="free":return [candidates[j] for j in ranked],0
 # Construct connected components on *training-only* absolute Pearson rho;
 # winner of each component is the best train-only target-correlated candidate.
 corr=np.corrcoef(z,rowvar=False);corr=np.nan_to_num(corr)
 parent=list(range(len(candidates)))
 def find(v):
  while parent[v]!=v:
   parent[v]=parent[parent[v]];v=parent[v]
  return v
 for j in range(len(candidates)):
  for k in range(j):
   if abs(corr[j,k])>=THRESHOLD:
    aa,bb=find(j),find(k)
    if aa!=bb:parent[bb]=aa
 seen=set();chosen=[]
 for j in ranked:
  root=find(j)
  if root not in seen:
   seen.add(root);chosen.append(candidates[j])
 return chosen,len(candidates)-len(chosen)
def evaluate(train,y,valid,names,k):
 selected=names[:k]
 m=make_pipeline(StandardScaler(),Ridge(alpha=10))
 m.fit(train[selected],y)
 return m.predict(valid[selected]),selected
out={"status":"research_only_two_strategy_selection","correlation_threshold":THRESHOLD,"correlation_metric":"abs Pearson on training rows","strategy_definitions":{"free":"train-only univariate target correlation ranking across all features","representative":"training-only |rho| >= .85 graph connected components; first best target-correlated feature per component"},"results":{},"production_changed":False,
"cautions":["Geographic nested validation, NOT untouched future-year temporal validation.","Connected components may chain variables that are not directly correlated.","Representative screening prohibits backup variables in same family; a later conditional re-search is needed.","Prior year/fold evaluations have been inspected repeatedly.","Fixed Ridge alpha=10; family construction and ranking occur only in current training fold.","No historical source-vintage approval."]}
for window,years in {"five":range(2019,2024),"three":range(2021,2024)}.items():
 q=p[p.year.isin(years)].sort_values(["kommun_kod","year"])
 y=q.inflyttning_per_1000.to_numpy(float);g=q.kommun_kod.to_numpy()
 candidates0=sorted(n for n in pool if n in q and all(coverage[n][str(t)]==290 for t in years))
 for branch in ("blind","forecast"):
  candidates=[n for n in candidates0 if branch=="forecast" or pool[n]["blind_model_eligible_subject_to_audit"]]
  x=q[candidates].astype(float);assert np.isfinite(x.to_numpy()).all()
  res={"n_candidates":len(candidates),"strategies":{}}
  for strategy in ("free","representative"):
   errors=[];selections=Counter();folds=[]
   for fold,(a,b) in enumerate(GroupKFold(5).split(x,y,g),1):
    tr=x.iloc[a];te=x.iloc[b];yt=y[a];gt=g[a]
    losses={};family_excluded=[]
    for i,j in GroupKFold(3).split(tr,yt,gt):
     ranked,excluded=ordering(tr.iloc[i],yt[i],candidates,strategy)
     family_excluded.append(excluded)
     for cap in SIZES:
      k=min(cap,len(ranked))
      pred,_=evaluate(tr.iloc[i],yt[i],tr.iloc[j],ranked,k)
      losses.setdefault(cap,[]).append(float(np.sqrt(np.mean((yt[j]-pred)**2))))
    means={k:np.mean(v) for k,v in losses.items()}
    ses={k:np.std(v,ddof=1)/np.sqrt(len(v)) for k,v in losses.items()}
    best=min(means,key=lambda k:means[k])
    acceptable=[k for k in SIZES if means[k]<=means[best]+ses[best]]
    budget=min(acceptable)
    ranked,excluded=ordering(tr,yt,candidates,strategy)
    n=min(budget,len(ranked))
    predictions,selected=evaluate(tr,yt,te,ranked,n)
    err=y[b]-predictions
    errors.extend(err.tolist());selections.update(selected)
    folds.append({"fold":fold,"budget":budget,"actual_selected":n,"excluded_by_correlation":excluded,
      "selected_features":selected,"rmse":float(np.sqrt(np.mean(err*err))),
      "inner_rmse_by_cap":{str(k):float(v) for k,v in means.items()}})
   res["strategies"][strategy]={"rmse":float(np.sqrt(np.mean(np.square(errors)))),"mae":float(np.mean(np.abs(errors))),"folds":folds,"selection_frequency":dict(selections.most_common())}
   print(window,branch,strategy,res["strategies"][strategy]["rmse"],flush=True)
  out["results"][window+"_"+branch]=res
(D/"neutral_two_strategy_model_selection.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
