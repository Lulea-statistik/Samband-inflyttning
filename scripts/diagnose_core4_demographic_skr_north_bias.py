#!/usr/bin/env python3
"""Demographic, SKR-group and north-coordinate bias diagnostic for frozen core-4.

Research-only. No model changes.

Bias sign:
  residual = prediction - actual
  positive => core-4 overpredicts (overvalues expected inflow)
  negative => core-4 underpredicts

Evaluation years: 2019-2024, six-year rolling-origin core-4 forecasts.

Demographic dimensions (lagged, pre-outcome):
- share age 20-34
- mean age of in-movers
- share students
- share post-secondary educated
- population growth

External classification/geography:
- SKR municipality group classification 2023 (official SKR PDF)
- SCB municipality polygons; centroid northing in SWEREF 99 TM

No correction is fitted here.
"""
import io, json, re, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import geopandas as gpd
from pypdf import PdfReader

D=Path("docs/data")
PRED=D/"three_year_forecast_core4_historical_reconstructed_predictions.csv"
PANEL=D/"panel.csv"
OUT=D/"three_year_forecast_core4_demographic_skr_north_bias.json"
OUTCSV=D/"three_year_forecast_core4_demographic_skr_north_bias_rows.csv"
SRC=D/"geographic_bias_sources"
SRC.mkdir(parents=True,exist_ok=True)

YEARS=list(range(2019,2025))
DEMOS=[
 "lag1_andel_20_34",
 "lag1_inflyttare_medelalder",
 "lag1_andel_studerande",
 "lag1_andel_eftergymnasial",
 "lag1_befolkningstillvaxt_pct"
]

SKR_PDF="https://extra.skr.se/download/18.ef4ba7d1849a2f55db2898a/1669978414789/Kommungruppsindelning-2023.pdf"
SCB_ZIP="https://www.scb.se/contentassets/3443fea3fa6640f7a57ea15d9a372d33/shape_svenska_260225.zip"

pred=pd.read_csv(PRED,dtype={"kommun_kod":str})
pred["kommun_kod"]=pred["kommun_kod"].astype(str).str.zfill(4)
pred=pred[(pred["window_years"].eq(6)) & pred["forecast_year"].isin(YEARS)].copy()
pred=pred.rename(columns={"forecast_year":"year"})
pred["residual"]=pred["prediction"]-pred["actual"]
pred["abs_error"]=pred["residual"].abs()
pred["overpredicted"]=pred["residual"]>0

panel=pd.read_csv(PANEL,dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)
missing=[c for c in DEMOS if c not in panel.columns]
if missing: raise SystemExit(f"Missing demographic fields: {missing}")
demo=panel[["kommun_kod","year"]+DEMOS].copy()
for c in DEMOS:
    demo[c]=pd.to_numeric(demo[c],errors="coerce")
pred=pred.merge(demo,on=["kommun_kod","year"],how="left",validate="one_to_one")
for c in DEMOS:
    if pred[c].isna().any():
        raise SystemExit(f"Missing demographic field {c}: {int(pred[c].isna().sum())}")

# --- SKR 2023 municipality groups from official PDF ---
pdf=requests.get(SKR_PDF,timeout=90)
pdf.raise_for_status()
(SRC/"skr_kommungrupp_2023.pdf").write_bytes(pdf.content)
reader=PdfReader(io.BytesIO(pdf.content))
text="\n".join((p.extract_text() or "") for p in reader.pages)
(SRC/"skr_kommungrupp_2023_extracted.txt").write_text(text,encoding="utf-8")

group_names={
 "A1":"Storstäder",
 "A2":"Pendlingskommun nära storstad",
 "B3":"Större stad",
 "B4":"Pendlingskommun nära större stad",
 "B5":"Lågpendlingskommun nära större stad",
 "C6":"Mindre stad/tätort",
 "C7":"Pendlingskommun nära mindre stad/tätort",
 "C8":"Landsbygdskommun",
 "C9":"Landsbygdskommun med besöksnäring"
}

# PDF extraction may separate columns unpredictably. Find every group code and
# nearby 4-digit municipality code; retain one group per municipality.
matches=[]
lines=[re.sub(r"\s+"," ",x).strip() for x in text.splitlines() if x.strip()]
for i,line in enumerate(lines):
    combo=" ".join(lines[i:i+3])
    for m in re.finditer(r"\b(A1|A2|B3|B4|B5|C6|C7|C8|C9)\b\s+(\d{4})\b",combo):
        matches.append((m.group(2),m.group(1)))
# fallback: code may precede group due extraction order
for i,line in enumerate(lines):
    combo=" ".join(lines[i:i+3])
    for m in re.finditer(r"\b(\d{4})\b.*?\b(A1|A2|B3|B4|B5|C6|C7|C8|C9)\b",combo):
        matches.append((m.group(1),m.group(2)))
skr=pd.DataFrame(matches,columns=["kommun_kod","skr_group"]).drop_duplicates()
conf=skr.groupby("kommun_kod")["skr_group"].nunique()
bad=conf[conf>1]
if len(bad):
    # keep only exact line-level unambiguous pair where possible
    exact=[]
    for line in lines:
        m=re.search(r"\b(A1|A2|B3|B4|B5|C6|C7|C8|C9)\b\s+(\d{4})\b",line)
        if m: exact.append((m.group(2),m.group(1)))
    e=pd.DataFrame(exact,columns=["kommun_kod","skr_group"]).drop_duplicates("kommun_kod")
    skr=skr[~skr["kommun_kod"].isin(bad.index)]
    skr=pd.concat([skr,e[e["kommun_kod"].isin(bad.index)]],ignore_index=True)
skr=skr.drop_duplicates("kommun_kod")
if skr["kommun_kod"].nunique()!=290:
    raise SystemExit(f"Could not parse all 290 SKR groups, got {skr['kommun_kod'].nunique()}")
skr["skr_group_name"]=skr["skr_group"].map(group_names)
skr.to_csv(SRC/"skr_kommungrupp_2023.csv",index=False)

# --- SCB municipality centroids / northing ---
z=requests.get(SCB_ZIP,timeout=120)
z.raise_for_status()
(SRC/"scb_shape_svenska_260225.zip").write_bytes(z.content)
with zipfile.ZipFile(io.BytesIO(z.content)) as zz:
    names=zz.namelist()
    shp_candidates=[n for n in names if n.lower().endswith(".shp") and ("kommun" in n.lower() or "kn" in n.lower())]
    if not shp_candidates:
        shp_candidates=[n for n in names if n.lower().endswith(".shp")]
    if not shp_candidates: raise SystemExit("No shapefile found in SCB zip")
    extract_dir=SRC/"scb_shape"
    zz.extractall(extract_dir)

# Try candidate shapefiles until one has 290-ish municipality records and a 4-digit code field.
gdf=None; codecol=None; chosen=None
for rel in shp_candidates:
    path=extract_dir/rel
    try:
        g=gpd.read_file(path)
    except Exception:
        continue
    for col in g.columns:
        if col=="geometry": continue
        s=g[col].astype(str).str.extract(r"(\d{4})",expand=False)
        n=s.dropna().nunique()
        if 285 <= n <= 295:
            gdf=g.copy(); codecol=col; chosen=rel; break
    if gdf is not None: break
if gdf is None:
    raise SystemExit("Could not identify municipality shapefile/code field")

gdf["kommun_kod"]=gdf[codecol].astype(str).str.extract(r"(\d{4})",expand=False)
gdf=gdf[gdf["kommun_kod"].notna()].copy()
gdf=gdf.drop_duplicates("kommun_kod")
# SCB file is documented as SWEREF99 TM. Reproject defensively if CRS differs.
if gdf.crs is None:
    gdf=gdf.set_crs(3006)
elif gdf.crs.to_epsg()!=3006:
    gdf=gdf.to_crs(3006)
cent=gdf.geometry.centroid
coords=pd.DataFrame({
 "kommun_kod":gdf["kommun_kod"].values,
 "easting_sweref99tm":cent.x.values,
 "northing_sweref99tm":cent.y.values
})
if coords["kommun_kod"].nunique()!=290:
    raise SystemExit(f"Expected 290 municipality centroids, got {coords['kommun_kod'].nunique()}")
coords.to_csv(SRC/"scb_kommun_centroids_sweref99tm.csv",index=False)

pred=pred.merge(skr,on="kommun_kod",how="left",validate="many_to_one")
pred=pred.merge(coords,on="kommun_kod",how="left",validate="many_to_one")
if pred[["skr_group","northing_sweref99tm"]].isna().any().any():
    raise SystemExit("Missing SKR group or northing after merge")

def metrics(g):
    e=g["residual"].to_numpy(); ae=np.abs(e)
    return {
      "n":int(len(g)),
      "municipalities":int(g["kommun_kod"].nunique()),
      "mean_residual_prediction_minus_actual":float(np.mean(e)),
      "interpretation":"overpredicted" if np.mean(e)>0 else "underpredicted",
      "rmse":float(np.sqrt(np.mean(e*e))),
      "mae":float(np.mean(ae)),
      "median_residual":float(np.median(e)),
      "share_overpredicted":float(np.mean(e>0)),
      "p95_abs_error":float(np.quantile(ae,.95))
    }

def decile_analysis(df,col):
    q=df.copy()
    bname=col+"_decile"
    q[bname]=0
    for y,g in q.groupby("year"):
        bins=pd.qcut(g[col].rank(method="first"),10,labels=False)+1
        q.loc[g.index,bname]=bins.astype(int)
    out=[]
    for d,g in q.groupby(bname):
        rec={"decile":int(d),"mean_feature":float(g[col].mean()),**metrics(g)}
        out.append(rec)
    return out

demographic={c:decile_analysis(pred,c) for c in DEMOS}

skr_results=[]
for code,g in pred.groupby("skr_group"):
    skr_results.append({
      "skr_group":code,
      "skr_group_name":group_names.get(code,code),
      **metrics(g)
    })
skr_results=sorted(skr_results,key=lambda x:x["skr_group"])

# Northing deciles: 1=south, 10=north. Static coordinate, but binning globally.
north_map=coords.copy()
north_map["north_decile"]=pd.qcut(north_map["northing_sweref99tm"].rank(method="first"),10,labels=False)+1
pred=pred.merge(north_map[["kommun_kod","north_decile"]],on="kommun_kod",how="left",validate="many_to_one")
north_results=[]
for d,g in pred.groupby("north_decile"):
    north_results.append({
      "north_decile":int(d),
      "mean_northing_sweref99tm":float(g["northing_sweref99tm"].mean()),
      **metrics(g)
    })

# Simple monotonic diagnostic slopes (not causal, not model correction).
def residual_slope(col):
    x=pred[col].to_numpy(dtype=float)
    y=pred["residual"].to_numpy(dtype=float)
    slope=float(np.polyfit((x-x.mean())/x.std(ddof=0),y,1)[0])
    corr=float(np.corrcoef(x,y)[0,1])
    return {"residual_change_per_1sd_feature":slope,"correlation":corr}

slopes={c:residual_slope(c) for c in DEMOS}
slopes["northing_sweref99tm"]=residual_slope("northing_sweref99tm")

# Lulea profile and contextual percentile/deciles.
l=pred[pred["kommun_kod"].eq("2580")].copy()
lulea={
 "skr_group":l["skr_group"].iloc[0],
 "skr_group_name":l["skr_group_name"].iloc[0],
 "northing_sweref99tm":float(l["northing_sweref99tm"].iloc[0]),
 "north_decile":int(l["north_decile"].iloc[0]),
 "mean_residual_2019_2024":float(l["residual"].mean()),
 "mae_2019_2024":float(l["abs_error"].mean()),
 "share_years_overpredicted":float(l["overpredicted"].mean()),
 "annual":[
   {"year":int(r.year),"actual":float(r.actual),"prediction":float(r.prediction),
    "residual":float(r.residual)}
   for _,r in l.iterrows()
 ]
}

# Overall strongest systematic over/under segments for convenient reporting.
segments=[]
for c,rows in demographic.items():
    for r in rows:
        segments.append({"dimension":c,"segment":f"decile_{r['decile']}",**r})
for r in skr_results:
    segments.append({"dimension":"skr_group","segment":r["skr_group"],**r})
for r in north_results:
    segments.append({"dimension":"northing","segment":f"decile_{r['north_decile']}",**r})
over=sorted(segments,key=lambda x:x["mean_residual_prediction_minus_actual"],reverse=True)[:15]
under=sorted(segments,key=lambda x:x["mean_residual_prediction_minus_actual"])[:15]

result={
 "status":"core4_demographic_skr_north_bias_diagnostic",
 "production_changed":False,
 "structural_core4_changed":False,
 "variable_selection_reopened":False,
 "evaluation_years":YEARS,
 "bias_definition":"prediction - actual; positive=overprediction, negative=underprediction",
 "sources":{
   "skr":{"classification":"2023","url":SKR_PDF,"municipalities":int(skr["kommun_kod"].nunique())},
   "scb_geography":{"url":SCB_ZIP,"crs":"EPSG:3006 SWEREF99 TM","shapefile":chosen}
 },
 "overall":metrics(pred),
 "demographic_deciles":demographic,
 "demographic_residual_slopes":slopes,
 "skr_groups":skr_results,
 "north_deciles":north_results,
 "strongest_overprediction_segments":over,
 "strongest_underprediction_segments":under,
 "lulea":lulea,
 "interpretation_guardrail":"Associations describe where frozen core4 errors concentrate. They are not causal effects and must not be used as a correction without separate out-of-time validation."
}
pred.to_csv(OUTCSV,index=False)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({
 "overall":result["overall"],
 "slopes":slopes,
 "skr_groups":skr_results,
 "north_deciles":north_results,
 "over":over[:8],
 "under":under[:8],
 "lulea":lulea
},ensure_ascii=False,indent=2))
