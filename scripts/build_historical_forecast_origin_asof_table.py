#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timedelta

REG=Path("docs/data/scb_publication_calendar_registry.json")
OUT=Path("docs/data/historical_forecast_origin_asof_table.json")

reg=json.loads(REG.read_text(encoding="utf-8"))

# Actual annual SCB projection publication dates are the anchor.
proj=reg["national_population_projection"]["observed"]
pop={x["reference_year"]:x for x in reg["annual_population_final"]["observed"]}
housing={x["reference_year"]:x for x in reg["housing_stock"]["observed"]}

rows=[]
for p in proj:
    pub=datetime.fromisoformat(p["published"])
    year=pub.year
    origin=(pub+timedelta(days=10)).date().isoformat()

    prev=year-1
    # Population/final migration: use actual date when registered, else infer Feb window conservatively.
    if prev in pop:
        pop_pub=pop[prev]["published"]
        pop_quality="observed"
        pop_source="SCB Befolkningsstatistik"
    else:
        pop_pub=f"{year}-03-01"
        pop_quality="conservative_fallback"
        pop_source="SCB annual population fallback"
    pop_available=pop_pub <= origin

    # Housing: exact only if known; otherwise conservative end-April availability rule.
    if prev in housing:
        housing_pub=housing[prev]["published"]
        housing_quality="observed"
        housing_source="SCB Bostadsbestånd"
    else:
        housing_pub=f"{year}-04-30"
        housing_quality="conservative_fallback"
        housing_source="SCB housing fallback"
    housing_available=housing_pub <= origin

    # Kolada N03937 is an annual mean for year T. Current KPI metadata shows
    # publication in January of T+1 (2026 period -> 2027-01-19).
    # For historical years without archived exact publication dates, use this only
    # as an inferred annual pattern and conservatively place availability at March 1 Y.
    kolada_pub=f"{year}-03-01"
    kolada_available=kolada_pub <= origin
    kolada_quality="inferred_annual_pattern"
    kolada_note="Current Kolada metadata shows annual N03937 period T published in January T+1; historical exact dates are not archived here, so March 1 Y is used as a conservative inferred cutoff for Y-1."

    rows.append({
      "forecast_year":year,
      "scb_national_projection_published":p["published"],
      "forecast_origin":origin,
      "origin_rule":"SCB national projection publication + 10 days",
      "population_final_reference_year":prev,
      "population_final_published":pop_pub,
      "population_final_quality":pop_quality,
      "population_final_available":pop_available,
      "housing_reference_year":prev,
      "housing_published":housing_pub,
      "housing_quality":housing_quality,
      "housing_available":housing_available,
      "kolada_unemployment_reference_year":prev,
      "kolada_unemployment_published_assumed":kolada_pub,
      "kolada_unemployment_available":kolada_available,
      "kolada_unemployment_quality":kolada_quality,
      "kolada_unemployment_note":kolada_note,
      "rates_25_29_realtime_policy":"use latest BAS month available with 1-2 month conservative lag",
      "macro_core4_operationally_available": bool(pop_available and housing_available and kolada_available),
      "macro_core4_fully_certified": bool(
          pop_available and housing_available and kolada_available
          and pop_quality=="observed"
          and housing_quality=="observed"
          and kolada_quality=="observed"
      )
    })

result={
  "status":"historical_forecast_origin_asof_table_initial",
  "generated_from":"docs/data/scb_publication_calendar_registry.json",
  "default_origin_offset_days":10,
  "rows":rows,
  "important_note":"Core4 cannot be called fully as-of certified until source-specific timing for Kolada unemployment is documented. Housing uses conservative fallback where exact historical publication dates are not registered."
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
