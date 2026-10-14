#!/usr/bin/env python3
"""Research-only nonlinear LOK test with held-out municipalities and fixed controls."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data
D=Path("docs/data")
L="lag1_kolada_langtidsarbetslosa_pct"
C="lag1_kolada_utbetalt_lok_stod_kr_per_inv"
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km","lag1_inkomst_tkr","lag1_andel_eftergymnasial","lag1_andel_studerande","lag1_andel_fa_arbetsplatser_i_egen_kommun","lag1_kolada_arbetslosa_18_65_pct"]
BLOCK=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
VARIANTS={"reference":[],"long_term":[L],"linear_lok":[L,C],"quadratic_lok":[L,C,"lok_quadratic"],"hinge_lok":[L,C,"lok_hinge"]}
def run():
    sources,fair,target=source_data();d=sources["BAS"].copy()
    fields=CONTROLS+[L,C,target]
    if d[fields].isna().any().any():raise RuntimeError("Missing complete-case data")
    ids=sorted(d.loc[d.year.eq(2024),"kommun_kod"].unique())
    if len(ids)!=290:raise RuntimeError("Expected 290 municipalities")
    pool=[v for v in fair["eligible_pool"] if v not in (L,C) and not any(z in v for z in BLOCK)]
    obs=[];folds=[]
    for fold in range(5):
        held={code for code in ids if int(hashlib.sha256(("validation-140:"+code).encode()).hexdigest()[:12],16)%5==fold}
        tr=d[(d.year<2024)&(~d.kommun_kod.isin(held))].copy()
        te=d[(d.year==2024)&d.kommun_kod.isin(held)].copy()
        selected=_select_features(tr,[v for v in pool if v in tr and tr[v].notna().all() and te[v].notna().all()],target)["selected"]
        base=list(dict.fromkeys(selected+CONTROLS))
        if C in base or L in base:raise RuntimeError("Candidate leaked into baseline")
        mean=float(tr[C].mean());sd=float(tr[C].std());med=float(tr[C].median())
        if sd<=0:raise RuntimeError("Constant LOK")
        for frame in (tr,te):
            frame["lok_quadratic"]=((frame[C]-mean)/sd)**2
            frame["lok_hinge"]=np.maximum(0,(frame[C]-med)/sd)
        preds={}
        for name,extra in VARIANTS.items():
            cols=list(dict.fromkeys(base+extra))
            est=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
            est.fit(tr[cols],tr[target]);preds[name]=est.predict(te[cols])
        for i,(_,r) in enumerate(te.iterrows()):
            obs.append({"code":r.kommun_kod,"actual":float(r[target]),"fold":fold,**{key:float(v[i]) for key,v in preds.items()}})
        folds.append({"fold":fold,"n_test":len(te),"lok_median_from_training":med})
        print("fold",fold,"done",flush=True)
    p=pd.DataFrame(obs).sort_values("code")
    if len(p)!=290 or p.code.nunique()!=290:raise RuntimeError("Holdout incomplete")
    report={"status":"research_only_nonlinear_lok","year":2024,"n":290,"training_years":[2022,2023],
       "controls":CONTROLS,"forms":VARIANTS,"folds":folds,
       "metrics":{name:_geographic_error_metrics(p.actual,p[name]) for name in VARIANTS},
       "lulea":p.loc[p.code=="2580"].to_dict("records"),
       "production_model_changed":False,
       "limitations":["LOK nonlinear shapes tested on previously inspected 2024: selection bias.",
                      "Municipal income and local-job share are proxies, not validated municipal fiscal accounts or full industry structure.",
                      "This comparison does not include new external civic or financial sources.",
                      "Municipal relationships are not causal; independent future validation needed."]}
    (D/"blind_lok_nonlinear_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":run()
