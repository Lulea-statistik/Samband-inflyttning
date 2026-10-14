#!/usr/bin/env python3
"""Compare zero, linear and preregistered interaction of commuting and labor market.

Train-only feature selection for dynamic baseline; fixed linear/interaction additions.
RAMS and BAS remain separate. No production mutation.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import RidgeCV
from build_analysis import _select_features,_geographic_error_metrics
from test_commuting_annual_paired import source_data

OUT=Path("docs/data")
CONTROL="lag1_andel_fa_arbetsplatser_i_egen_kommun"
def main():
    sources,fair,target=source_data()
    baseline=list(fair["incumbent_features"])
    pool=list(fair["eligible_pool"])
    report={"status":"exploratory_interaction_comparison","moderator":CONTROL,
        "definition":"Centered lagged outcommuting share times centered lagged fraction of FA-region jobs located in the municipality; centering from train only.",
        "method_regimes_separate":True,"feature_selection_train_only":True,
        "production_model_changed":False,"results":{}}
    for source,full in sources.items():
        results={}
        years=sorted(full.year.unique())
        for yr in years[1:]:
            train=full.loc[full.year<yr].copy()
            test=full.loc[full.year==yr].copy()
            if not (len(train)>=280 and len(test)==290):raise RuntimeError(f"Invalid {source} {yr} sample")
            if train[CONTROL].isna().any() or test[CONTROL].isna().any():raise RuntimeError("Moderator unavailable")
            # Product term uses training centers. This avoids scale-induced shortcut in fitting.
            c0=float(train.commuting.mean())
            m0=float(train[CONTROL].mean())
            for frame in (train,test):
                frame["commuting_centered"]=frame.commuting-c0
                frame["market_centered"]=frame[CONTROL]-m0
                frame["commuting_market_interaction"]=frame.commuting_centered*frame.market_centered
            allowed=[c for c in pool if c in train and train[c].notna().all() and test[c].notna().all()]
            selected=_select_features(train,allowed,target)["selected"]
            specs={"incumbent":baseline,"incumbent_linear":baseline+["commuting_centered"],
                "incumbent_interaction":baseline+["commuting_centered","commuting_market_interaction"],
                "dynamic":selected,"dynamic_linear":selected+["commuting_centered"],
                "dynamic_interaction":selected+["commuting_centered","commuting_market_interaction"]}
            preds={}
            for name,features in specs.items():
                model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
                model.fit(train[features],train[target])
                preds[name]=model.predict(test[features])
            scores={name:_geographic_error_metrics(test[target],p) for name,p in preds.items()}
            lulea=np.flatnonzero(test.kommun_kod.to_numpy()=="2580")
            results[str(yr)]={"train_years":sorted(int(y) for y in train.year.unique()),
                "n_train":len(train),"n_test":len(test),"selected_dynamic":selected,
                "scores":scores,
                "lulea":[{"actual":float(test.iloc[i][target]),"commuting_share":float(test.iloc[i].commuting),
                    "market_control":float(test.iloc[i][CONTROL]),**{name:float(p[i]) for name,p in preds.items()}} for i in lulea],
                "quartiles":[]}
            ranks=pd.qcut(test.commuting.rank(method="first"),4,labels=["Q1","Q2","Q3","Q4"])
            for group in ["Q1","Q2","Q3","Q4"]:
                mask=(ranks==group).to_numpy()
                results[str(yr)]["quartiles"].append({"group":group,"n":int(mask.sum()),
                     "mean_commuting_share":float(test.commuting.to_numpy()[mask].mean()),
                     "rmse":{name:_geographic_error_metrics(test[target].to_numpy()[mask],p[mask])["rmse"] for name,p in preds.items()}})
            print(json.dumps({"source":source,"year":int(yr),"rmse":{name:round(v["rmse"],3) for name,v in scores.items()}},ensure_ascii=False),flush=True)
        report["results"][source]=results
    report["caution"]="Repeated retrospective years; interactions chosen after prior analyses. Correlation not causation. No unseen future-year evaluation."
    (OUT/"commuting_interaction_test.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
