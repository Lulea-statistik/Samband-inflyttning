#!/usr/bin/env python3
"""Nested geographic CV of model-size choice: min RMSE, 1-SE, knee, Jenks.
Exploratory study on previously reviewed years; no production decisions.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
D=Path("docs/data")
read=lambda n:json.loads((D/n).read_text(encoding="utf-8"))
records={r["feature"]:r for r in read("neutral_variable_pool_reboot.json")["records"]}
coverage=read("neutral_80_candidate_data_gate.json")["variables"]
previous={r["feature"] for r in read("fair_variable_inventory.json")["variables"] if r.get("incumbent")}
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p.kommun_kod=p.kommun_kod.str.zfill(4)
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag.kommun_kod=lag.kommun_kod.str.zfill(4)
codes=set(lag.loc[lag.target_year==2024,"kommun_kod"])
assert len(codes)==290
w=lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct").reset_index()
w=w.rename(columns={"target_year":"year","residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct","workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"})
p=p[p.kommun_kod.isin(codes)&p.year.between(2019,2023)].merge(w,on=["year","kommun_kod"],how="left",validate="one_to_one")
assert len(p)==1450
SIZES=[4,6,10,14,20,30,40,60,80]
ALPHA=10.0
def rank(x,y,features):
    z=x[features].to_numpy(float);a=z-z.mean(axis=0);yy=y-y.mean()
    den=np.sqrt((a*a).sum(axis=0)*(yy*yy).sum())
    scores=np.divide(np.abs(a.T@yy),den,out=np.zeros(len(features)),where=den>0)
    return sorted(features,key=lambda f:(-float(scores[features.index(f)]),f))
def predict(tx,ty,vx,features,k):
    chosen=rank(tx,ty,features)[:k]
    m=make_pipeline(StandardScaler(),Ridge(alpha=ALPHA))
    m.fit(tx[chosen],ty)
    return m.predict(vx[chosen]),chosen
def jenks_break_sizes(sizes,loss):
    # Jenks natural breaks 2 classes applied to *positive successive gains*;
    # descending larger gains are split from small gains, not to feature ranks.
    improvements=np.maximum(0,np.array(loss[:-1])-np.array(loss[1:]))
    if len(improvements)<3 or float(np.ptp(improvements))<1e-10:return sizes[int(np.argmin(loss))]
    best=None
    for k in range(1,len(improvements)):
        left,right=improvements[:k],improvements[k:]
        within=((left-left.mean())**2).sum()+((right-right.mean())**2).sum()
        key=(float(within),k)
        if best is None or key<best:best=key
    boundary=best[1]
    return sizes[boundary]
def pick(method,sizes,mean,se):
    if method=="minimum":return sizes[int(np.argmin(mean))]
    if method=="one_se":
        m=int(np.argmin(mean))
        return min(k for k,loss in zip(sizes,mean) if loss<=mean[m]+se[m])
    if method=="knee":
        # maximum vertical improvement over straight line from first to last;
        # fall back to min RMSE if curve has no positive knee.
        xs=(np.array(sizes)-sizes[0])/(sizes[-1]-sizes[0])
        ys=np.array(mean);line=ys[0]+(ys[-1]-ys[0])*xs
        gain=line-ys
        return sizes[int(np.argmax(gain))] if max(gain)>0 else sizes[int(np.argmin(mean))]
    if method=="jenks":return jenks_break_sizes(sizes,mean)
    raise ValueError(method)
out={"status":"exploratory_model_size_method_comparison","sizes":SIZES,"ridge_alpha":ALPHA,
 "methods":["minimum","one_se","knee","jenks"],"results":{},"production_changed":False,
 "limitations":["Reuses previously inspected geographic splits and historical outcomes.",
 "Jenks on marginal RMSE-gain sizes is a heuristic, not model-optimality proof.",
 "Ranking by univariate correlation can miss conditional variables.",
 "One-SE uses three geographic validation-fold errors with limited independence.",
 "No production pipeline reconstruction, as-of source verification or independent future holdout."]}
for window,years in {"five":range(2019,2024),"three":range(2021,2024)}.items():
 q=p[p.year.isin(years)].sort_values(["kommun_kod","year"])
 y=q.inflyttning_per_1000.to_numpy(float);g=q.kommun_kod.to_numpy()
 assert np.isfinite(y).all()
 complete=[n for n in records if all(coverage[n][str(t)]==290 for t in years)]
 for branch in ("blind","forecast"):
  candidates=sorted(n for n in complete if branch=="forecast" or records[n]["blind_model_eligible_subject_to_audit"])
  result={"rows":len(q),"candidate_count":len(candidates),"methods":{}}
  x=q[candidates].astype(float)
  assert np.isfinite(x.to_numpy()).all()
  for method in out["methods"]:
   errors=[];folds=[]
   for fold,(tr,te) in enumerate(GroupKFold(5).split(x,y,g),1):
    tx=x.iloc[tr];ty=y[tr];tg=g[tr]
    sizes=sorted(set(min(k,len(candidates)) for k in SIZES))
    val_errors={k:[] for k in sizes}
    for a,b in GroupKFold(3).split(tx,ty,tg):
     for k in sizes:
      pr,_=predict(tx.iloc[a],ty[a],tx.iloc[b],candidates,k)
      val_errors[k].append(float(np.sqrt(np.mean((ty[b]-pr)**2))))
    mean=np.array([np.mean(val_errors[k]) for k in sizes])
    se=np.array([np.std(val_errors[k],ddof=1)/np.sqrt(3) for k in sizes])
    k=pick(method,sizes,mean,se)
    pr,chosen=predict(tx,ty,x.iloc[te],candidates,k)
    e=y[te]-pr;errors.extend(e.tolist())
    folds.append({"fold":fold,"selected_size":k,"rmse":float(np.sqrt(np.mean(e*e))),"mae":float(np.mean(abs(e))),
      "inner_curve":[{"size":size,"rmse":float(m),"se":float(s)} for size,m,s in zip(sizes,mean,se)]})
   result["methods"][method]={"rmse":float(np.sqrt(np.mean(np.square(errors)))),
    "mae":float(np.mean(np.abs(errors))),"selected_sizes":[f["selected_size"] for f in folds],"folds":folds}
   print(window,branch,method,result["methods"][method]["rmse"],flush=True)
  out["results"][window+"_"+branch]=result
(D/"neutral_model_size_method_comparison.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
