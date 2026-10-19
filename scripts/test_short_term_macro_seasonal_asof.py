#!/usr/bin/env python3
import csv, json, math
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ASOF=Path("docs/data/historical_forecast_origin_asof_table.json")
ANNUAL=Path("docs/data/three_year_forecast_core4_historical_reconstructed_predictions.csv")
MONTHLY=Path("docs/data/short_term_monthly_target_lulea.csv")
OUT=Path("docs/data/short_term_macro_seasonal_asof_backtest.json")
PRED=Path("docs/data/short_term_macro_seasonal_asof_predictions.csv")

OFFSETS=["7","10","14"]
WINDOW=6
HORIZONS=[3,6,9,12]

def read_csv(p):
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))

def num(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except:
        return None

def mi(s):
    return int(s[:4])*12+int(s[-2:])

def ym_from_date(s):
    d=datetime.fromisoformat(s)
    return d.year,d.month

def rmse(e):
    return math.sqrt(sum(x*x for x in e)/len(e)) if e else None

def mae(e):
    return sum(abs(x) for x in e)/len(e) if e else None

def bias(e):
    return sum(e)/len(e) if e else None

def pct(a,b):
    return 100*(a/b-1) if a is not None and b not in (None,0) else None

asof=json.loads(ASOF.read_text(encoding="utf-8"))
annual=read_csv(ANNUAL)
monthly=read_csv(MONTHLY)

# Lulea code 2580, frozen 6-year annual core4 only.
annual_lulea={}
for r in annual:
    if r.get("kommun_kod")=="2580" and int(r["window_years"])==WINDOW:
        annual_lulea[int(r["forecast_year"])]=num(r["prediction"])

m={r["month"]:r for r in monthly}
months=sorted(m,key=mi)
idx={mi(x):x for x in months}

# Historical monthly seasonality: shares by calendar month using completed years only.
by_year=defaultdict(dict)
for mm,r in m.items():
    y=int(mm[:4]); mon=int(mm[-2:])
    v=num(r.get("all_inmigrations"))
    if v is not None:
        by_year[y][mon]=v

def seasonal_shares_before(year):
    vals=defaultdict(list)
    for y,obs in by_year.items():
        if y>=year or len(obs)!=12: continue
        total=sum(obs.values())
        if total<=0: continue
        for mon,v in obs.items():
            vals[mon].append(v/total)
    if not vals: return None
    out={}
    for mon in range(1,13):
        xs=vals.get(mon,[])
        out[mon]=sum(xs)/len(xs) if xs else None
    s=sum(v for v in out.values() if v is not None)
    return {k:(v/s if v is not None and s else None) for k,v in out.items()}

def known_population_before_origin(origin_year, origin_month):
    # Latest population observation before forecast month; this is already in the
    # stitched monthly target and is only used as a scale anchor for annual per-1000.
    candidates=[]
    ok=origin_year*12+origin_month
    for mm,r in m.items():
        if mi(mm)<ok:
            v=num(r.get("population"))
            if v is not None:
                candidates.append((mi(mm),v,mm))
    return max(candidates) if candidates else None

rows=[]
summary={}
for off in OFFSETS:
    ors=[]
    for a in asof["rows"]:
        if not a.get("macro_core4_operationally_available_by_offset",{}).get(off):
            continue
        y=a["forecast_year"]
        if y not in annual_lulea:
            continue
        origin=a["forecast_origins_by_offset_days"][off]
        oy,om=ym_from_date(origin)
        shares=seasonal_shares_before(y)
        pop=known_population_before_origin(oy,om)
        if shares is None or pop is None:
            continue
        annual_rate=annual_lulea[y]
        annual_count=annual_rate*pop[1]/1000.0
        origin_key=oy*12+om

        for h in HORIZONS:
            target_months=[idx.get(origin_key+i) for i in range(1,h+1)]
            if any(x is None for x in target_months):
                continue
            actuals=[num(m[x].get("all_inmigrations")) for x in target_months]
            if any(v is None for v in actuals):
                continue
            actual=sum(actuals)

            # seasonal-naive baseline: same future calendar months one year earlier
            sn=[]
            valid=True
            for tm in target_months:
                prev=idx.get(mi(tm)-12)
                if prev is None:
                    valid=False;break
                v=num(m[prev].get("all_inmigrations"))
                if v is None:
                    valid=False;break
                sn.append(v)
            if not valid:
                continue
            seasonal=sum(sn)

            # Macro+seasonal: only current forecast-year months get annual core4 anchor.
            # Months beyond Dec Y remain seasonal-naive; never use Y+1 core4 at origin Y.
            macro_parts=[]
            for tm,naive_v in zip(target_months,sn):
                ty=int(tm[:4]); mon=int(tm[-2:])
                if ty==y:
                    macro_parts.append(annual_count*shares[mon])
                else:
                    macro_parts.append(naive_v)
            macro=sum(macro_parts)

            rec={
              "offset_days":int(off),
              "forecast_year":y,
              "forecast_origin":origin,
              "origin_month":f"{oy:04d}M{om:02d}",
              "horizon_months":h,
              "target_start":target_months[0],
              "target_end":target_months[-1],
              "annual_core4_rate_per_1000":annual_rate,
              "population_scale_month":pop[2],
              "population_scale":pop[1],
              "annual_core4_count_anchor":annual_count,
              "actual":actual,
              "seasonal_naive":seasonal,
              "macro_seasonal":macro,
              "seasonal_error":seasonal-actual,
              "macro_error":macro-actual
            }
            rows.append(rec); ors.append(rec)

    hs={}
    for h in HORIZONS:
        rr=[r for r in ors if r["horizon_months"]==h]
        se=[r["seasonal_error"] for r in rr]
        me=[r["macro_error"] for r in rr]
        sr,sm=rmse(se),mae(se)
        mr,mm=rmse(me),mae(me)
        hs[str(h)]={
          "n_origins":len(rr),
          "forecast_years":[r["forecast_year"] for r in rr],
          "seasonal_naive":{"rmse":sr,"mae":sm,"bias":bias(se)},
          "macro_seasonal":{"rmse":mr,"mae":mm,"bias":bias(me)},
          "delta_rmse_pct_macro_vs_seasonal":pct(mr,sr),
          "delta_mae_pct_macro_vs_seasonal":pct(mm,sm)
        }
    summary[off]=hs

result={
 "status":"short_term_macro_seasonal_asof_backtest_v1",
 "production_changed":False,
 "structural_core4_changed":False,
 "annual_model":{"window_years":WINDOW,"method":"frozen core4 historical reconstructed predictions"},
 "origin_offsets_days":[7,10,14],
 "horizons_months":HORIZONS,
 "method":{
   "forecast_months":"full months after the historical forecast-origin calendar month",
   "seasonality":"mean calendar-month share from complete years strictly before forecast year",
   "annual_scale":"frozen core4 predicted inflow per 1000 multiplied by latest observed population before origin",
   "cross_year_rule":"core4 anchor applies only to months remaining in forecast year Y; months in Y+1 use seasonal-naive values so no Y+1 annual forecast is leaked"
 },
 "limitations":[
   "Historical annual core4 predictions are reconstructed, not exact archived source vintages.",
   "Kolada historical publication dates use a conservative inferred annual pattern.",
   "This v1 tests whether an as-of-compatible annual macro anchor improves the monthly baseline; it does not yet add rates_25_29."
 ],
 "summary":summary
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
cols=list(rows[0].keys()) if rows else []
with PRED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols)
    w.writeheader();w.writerows(rows)
print(json.dumps(result,ensure_ascii=False,indent=2))
