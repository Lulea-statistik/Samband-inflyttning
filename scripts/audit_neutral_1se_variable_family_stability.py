#!/usr/bin/env python3
"""Train-only variable stability and fixed-selection family ablation for 1-SE models."""
import json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
D=Path("docs/data")
def load(s):return json.loads((D/s).read_text(encoding="utf8"))
pool={r["feature"]:r for r in load("neutral_variable_pool_reboot.json")["records"]}
sizes=load("neutral_model_size_method_comparison.json")["results"]
panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel.kommun_kod=panel.kommun_kod.str.zfill(4)
emp=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
emp.kommun_kod=emp.kommun_kod.str.zfill(4)
codes=set(emp.loc[emp.target_year==2024,"kommun_kod"]);assert len(codes)==290
emp=emp.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct").reset_index().rename(columns={"target_year":"year","workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct","residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct"})
p=panel[panel.kommun_kod.isin(codes)&panel.year.between(2019,2023)].merge(emp,on=["year","kommun_kod"],how="left",validate="one_to_one")
out={"status":"exploratory_1se_stability_and_family_drop","design":"same geographic outer folds and selected budgets as prior experiment; within-fold univariate ranking, fixed Ridge alpha 10","scenarios":{},"production_changed":False,
"limitations":["Family ablation removes a family from already selected predictors and refits Ridge. It does NOT rerun candidate search; not an unbiased causal or marginal R2 contribution.","Test years and outer geography splits already repeatedly reviewed; diagnostics are exploratory.","Themes taken verbatim from inventory; unclassified theme is not substantive family.","High correlation and interactions may make family drop results unstable; not as-of validated."]}
for key,prior in sizes.items():
 years=range(2019,2024) if key.startswith("five") else range(2021,2024)
 blind=key.endswith("blind")
 names=sorted(n for n,r in pool.items() if (not blind or r["blind_model_eligible_subject_to_audit"]) and n in p.columns and p.loc[p.year.isin(years),n].notna().all())
 q=p[p.year.isin(years)].sort_values(["kommun_kod","year"])
 x=q[names].to_numpy(float);y=q.inflyttning_per_1000.to_numpy(float);g=q.kommun_kod.to_numpy()
 frequencies=Counter();bytheme=defaultdict(list);folds=[]
 for idx,(a,b) in enumerate(GroupKFold(5).split(x,y,g)):
  k=prior["methods"]["one_se"]["folds"][idx]["selected_size"]
  z=x[a];t=y[a];center=z-z.mean(0);yc=t-t.mean();den=np.sqrt((center**2).sum(0)*(yc**2).sum())
  corr=np.divide(np.abs(center.T@yc),den,out=np.zeros(len(names)),where=den>0)
  choice=sorted(range(len(names)),key=lambda j:(-corr[j],names[j]))[:k]
  selected=[names[j] for j in choice]
  frequencies.update(selected)
  def rmse(cols):
   model=make_pipeline(StandardScaler(),Ridge(alpha=10))
   model.fit(q.iloc[a][cols],y[a])
   v=model.predict(q.iloc[b][cols])
   return float(np.sqrt(np.mean((y[b]-v)**2)))
  baseline=rmse(selected)
  themes=sorted({pool[n].get("theme","unknown") for n in selected})
  losses={}
  for theme in themes:
   kept=[n for n in selected if pool[n].get("theme","unknown")!=theme]
   if not kept:continue
   diff=rmse(kept)-baseline
   losses[theme]=diff;bytheme[theme].append(diff)
  folds.append({"fold":idx+1,"selected_budget":k,"selected":selected,"baseline_rmse":baseline,"drop_theme_delta_rmse":losses})
 out["scenarios"][key]={"n_candidates":len(names),"folds":folds,"variable_selection_frequency":dict(frequencies.most_common()),
 "theme_drop_mean_delta_rmse":{t:float(np.mean(vals)) for t,vals in sorted(bytheme.items())},
 "theme_drop_fold_counts":{t:len(vals) for t,vals in sorted(bytheme.items())}}
 print(key, len(names),"selected", [f["selected_budget"] for f in folds],flush=True)
(D/"neutral_1se_variable_family_stability.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
