import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
load=lambda n:json.loads((D/n).read_text())
inv=load("neutral_variable_pool_reboot.json")["records"]
coverage=load("neutral_80_candidate_data_gate.json")["variables"]
old={r["feature"] for r in load("fair_variable_inventory.json")["variables"] if r.get("incumbent")}
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str})
p.kommun_kod=p.kommun_kod.str.zfill(4)
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag.kommun_kod=lag.kommun_kod.str.zfill(4)
codes=set(lag.loc[lag.target_year==2024,"kommun_kod"])
wide=lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct").reset_index()
wide=wide.rename(columns={"target_year":"year","residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct","workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"})
p=p[p.kommun_kod.isin(codes)&p.year.between(2019,2023)].merge(wide,on=["year","kommun_kod"],how="left")
assert len(codes)==290 and len(p)==1450
families=[
["lag1_log_smahuspris_medel","lag1_smahuspris_medel_tkr"],
["lag1_fritidshus_per_1000_inv","lag1_log_fritidshus_per_1000_inv"],
["lag1_regional_centre_distance_km","lag1_log_regional_centre_distance_km"],
["lag1_arbetskraftsdeltagande","lag1_utanf_arbetkraften_andel_pct"],
["lag1_snoskoterandel_alla_fordon_pct","lag1_snoskoterandel_exkl_dragfordon_pct"],
["lag1_gymnasium_hogskoleforberedande_pct","lag1_gymnasium_yrkesprogram_pct"]]
grid=[(.03,.8),(.3,.8),(3.,.8),(10.,.8),(.03,1.),(.3,1.),(3.,1.),(10.,1.)]
def shortlist(x,y,features):
    z=x[features].to_numpy(float);v=y-y.mean();a=z-z.mean(axis=0)
    scale=np.sqrt((a*a).sum(axis=0)*(v*v).sum())
    corr=np.divide(np.abs(a.T@v),scale,out=np.zeros(len(features)),where=scale>0)
    rank=dict(zip(features,corr));keep=set(features)
    for fam in families:
        members=set(fam)&keep
        if len(members)>1:
            winner=sorted(members,key=lambda n:(-rank[n],n))[0]
            keep-=members-{winner}
    return sorted(keep)
def fit(trx,try_,vax,features,alpha,l1):
    chosen=shortlist(trx,try_,features)
    m=make_pipeline(StandardScaler(),ElasticNet(alpha=alpha,l1_ratio=l1,max_iter=15000,random_state=13))
    m.fit(trx[chosen],try_)
    return m.predict(vax[chosen]),chosen,m
def tune(x,y,g,features):
    scored=[]
    for alpha,l1 in grid:
        errs=[]
        for tr,te in GroupKFold(n_splits=3).split(x,y,g):
            pr,_,_=fit(x.iloc[tr],y[tr],x.iloc[te],features,alpha,l1)
            errs.extend(((y[te]-pr)**2).tolist())
        scored.append((np.mean(errs),alpha,l1))
    return min(scored)[1:]
out={"status":"exploratory_family_aware_cv","grid":grid,"production_changed":False,"results":{}}
for key,years in {"five":range(2019,2024),"three":range(2021,2024)}.items():
    q=p[p.year.isin(years)].sort_values(["kommun_kod","year"])
    y=q.inflyttning_per_1000.to_numpy(float);g=q.kommun_kod.to_numpy()
    all_features=[v["feature"] for v in inv if all(coverage[v["feature"]][str(yr)]==290 for yr in years)]
    for branch in ("blind","forecast"):
        pool=sorted(v for v in all_features if branch=="forecast" or next(r for r in inv if r["feature"]==v)["blind_model_eligible_subject_to_audit"])
        result={}
        for arm,features in (("incumbent",sorted(set(pool)&old)),("neutral",pool)):
            x=q[features].astype(float);assert np.isfinite(x.to_numpy()).all()
            errors=[];folds=[]
            for i,(tr,te) in enumerate(GroupKFold(n_splits=5).split(x,y,g),1):
                alpha,l1=tune(x.iloc[tr],y[tr],g[tr],features)
                pr,chosen,m=fit(x.iloc[tr],y[tr],x.iloc[te],features,alpha,l1)
                e=y[te]-pr;errors.extend(e.tolist())
                folds.append({"fold":i,"rmse":float(np.sqrt(np.mean(e*e))),"features":len(chosen),"nonzero":int(np.sum(abs(m[-1].coef_)>1e-8)),"alpha":alpha})
            result[arm]={"rmse":float(np.sqrt(np.mean(np.square(errors)))),"mae":float(np.mean(np.abs(errors))),"folds":folds}
            print(key,branch,arm,result[arm]["rmse"],flush=True)
        out["results"][key+"_"+branch]=result
(D/"neutral_family_aware_cv_results.json").write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
