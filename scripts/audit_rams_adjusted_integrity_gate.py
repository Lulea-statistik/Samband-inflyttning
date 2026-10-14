#!/usr/bin/env python3
"""Research-only gate: historical RAMS/BAS adjusted series integrity and factor stability."""
import csv,json,math,statistics
from pathlib import Path
from collections import defaultdict
D=Path("docs/data")
def load(path):
    with (D/path).open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
raw=load("employment_historical_regime_research.csv")
adj=load("rams_bas_calibrated_research.csv")
index={(r["regime"],int(r["year"]),r["kommun_kod"]):r for r in raw}
adjusted={(r["dimension"],int(r["year"]),r["kommun_kod"]):r for r in adj}
if len(index)!=len(raw) or len(adjusted)!=len(adj):raise RuntimeError("Duplicate historical records")
if len(raw)!=6670 or len(adj)!=10440:raise RuntimeError(f"Unexpected row count: raw {len(raw)}, adjusted {len(adj)}")
report={"status":"research_gate_review","production_changed":False,"checks":{},"dimensions":{},"failures":[]}
for dimension in ("residence","workplace"):
    keys=sorted({r["kommun_kod"] for r in raw if r["regime"]=="BAS_2020_2024"})
    if len(keys)!=290:raise RuntimeError("Expected 290 municipalities")
    drift=[];details=[];level_factor=[]
    for municipality in keys:
        ratios=[]
        for year in (2020,2021):
            a=float(index[("RAMS_2019_2021",year,municipality)]["employed_"+dimension])
            b=float(index[("BAS_2020_2024",year,municipality)]["employed_"+dimension])
            if min(a,b)<=0:raise RuntimeError("Non-positive employment "+municipality)
            ratios.append(b/a)
        relative_change_pct=100*(ratios[1]/ratios[0]-1)
        drift.append(abs(relative_change_pct))
        factor=float(adjusted[(dimension,2018,municipality)]["adjustment_factor"])
        level_factor.append(factor)
        for y in range(2004,2022):
            r=adjusted[(dimension,y,municipality)]
            expected=float(r["raw_rams"])*factor
            if not math.isclose(float(r["bas_calibrated_rams"]),expected,rel_tol=1e-10):
                raise RuntimeError("Nonconstant factor or incorrect multiplication")
            regime=("RAMS_2004_2018" if y<=2018 else "RAMS_2019_2021")
            original=float(index[(regime,y,municipality)]["employed_"+dimension])
            if not math.isclose(original,float(r["raw_rams"]),rel_tol=1e-10):
                raise RuntimeError("Raw employment mismatch")
            if int(r["method_break_2011"])!=int(y==2011) or int(r["method_break_2019"])!=int(y==2019):
                raise RuntimeError("Break flag mismatch")
        details.append({"kommun_kod":municipality,"overlap_ratio_2020":ratios[0],
            "overlap_ratio_2021":ratios[1],"ratio_drift_abs_pct":abs(relative_change_pct),
            "calibration_factor":factor})
    s=sorted(drift)
    unstable=[x for x in details if x["ratio_drift_abs_pct"]>1]
    report["dimensions"][dimension]={
      "median_abs_overlap_ratio_drift_pct":statistics.median(s),
      "p90_abs_overlap_ratio_drift_pct":s[int(.9*(len(s)-1))],
      "n_ratio_drift_gt_1pct":len(unstable),
      "n_ratio_drift_gt_2pct":sum(v>2 for v in drift),
      "factor_min":min(level_factor),"factor_max":max(level_factor),
      "lulea":next(x for x in details if x["kommun_kod"]=="2580"),
      "top_ratio_drift":sorted(details,key=lambda x:-x["ratio_drift_abs_pct"])[:20],
      "municipalities_with_gt_1pct_drift":unstable}
report["checks"]={
 "records_and_uniqueness":"pass","no_cross_regime_splicing":"pass",
 "constant_factor_within_rams":"pass","raw_values_preserved":"pass",
 "method_break_flags":"pass"}
report["decision"]={
 "integrity_gate":"pass",
 "calibration_reliability_gate":"requires_review",
 "experimental_regression_gate":"blocked_pending_source_asof_and_break_policy",
 "production_gate":"blocked"}
report["limitations"]=[
 "Two overlap years cannot establish stability for 2004-2018.",
 "Constant factors preserve within-regime percentage growth exactly; they do not correct true methodology breaks.",
 "Large ratio drifts warrant sensitivity analysis, not automatic suppression of municipalities.",
 "No historical time-as-of audit, regression, model selection, or production change is included."]
(D/"rams_bas_adjusted_integrity_gate.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({"checks":report["checks"],"stability":{k:{"median_abs_ratio_drift_pct":v["median_abs_overlap_ratio_drift_pct"],"n_gt_1":v["n_ratio_drift_gt_1pct"]} for k,v in report["dimensions"].items()}},ensure_ascii=False))
