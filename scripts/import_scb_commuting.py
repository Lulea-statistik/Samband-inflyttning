#!/usr/bin/env python3
"""Download SCB BAS municipality-to-municipality employment flows, 2020-2024.

Standalone data ingestion. Does NOT alter panel or production features.
All 290x290 cells are requested in bounded chunks; missing/suppressed cells
are never interpreted as zero. Data availability is checked strictly.
"""
import csv
import json
import re
import time
from pathlib import Path
import requests

URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210F/ArRegPend2"
DEST = Path("docs/data")
YEARS = [str(y) for y in range(2020, 2025)]
S = requests.Session()
S.headers["User-Agent"] = "Lulea-statistik migration research contact via GitHub"
S.headers["Accept"] = "application/json"


def request(method, url, **kwargs):
    for attempt in range(5):
        try:
            r = S.request(method, url, timeout=90, **kwargs)
            if r.ok:
                return r.json()
            if r.status_code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(f"SCB HTTP {r.status_code}: {r.text[:400]}")
            err = f"HTTP {r.status_code}: {r.text[:200]}"
        except (requests.ConnectionError, requests.Timeout) as e:
            err = str(e)
        if attempt == 4:
            raise RuntimeError(f"SCB request failed after retries: {err}")
        time.sleep(3 * (attempt + 1))


def variable(meta, terms):
    for item in meta["variables"]:
        txt = " ".join([item.get("code",""), item.get("text","")]).lower()
        if any(term in txt for term in terms):
            return item
    raise ValueError(f"Missing variable for {terms}")


def main():
    meta = request("GET", URL)
    residence = variable(meta, ["bostadskommun"])
    workplace = variable(meta, ["arbetsställekommun", "arbetsstallekommun"])
    sex = variable(meta, ["kön", "kon"])
    year = next((v for v in meta["variables"] if v.get("code","").lower() in {"tid","year","år"} or v.get("text","").strip().lower() in {"år","year"}), None)
    if year is None:
        raise RuntimeError("Cannot uniquely identify reference-year dimension")
    measure = next((v for v in meta["variables"] if v["code"].lower() in {"contentscode","contents"}), None)
    codes = [c for c in residence["values"] if re.fullmatch(r"\d{4}", str(c))]
    dest_codes = [c for c in workplace["values"] if re.fullmatch(r"\d{4}", str(c))]
    common = sorted(set(codes) & set(dest_codes))
    if len(common) != 290:
        raise RuntimeError(f"Expected 290 municipality codes, found {len(common)}")
    label_candidates = list(zip(sex["values"], sex["valueTexts"]))
    total_sex = next((code for code, label in label_candidates if "totalt" in label.lower() or "båda" in label.lower() or "samtliga" in label.lower()), None)
    if total_sex is None:
        raise RuntimeError(f"Cannot determine total-sex category: {label_candidates}")
    years_available = sorted(set(YEARS) & set(year["values"]))
    if len(years_available) != 5:
        raise RuntimeError(f"Expected 2020-2024, got {years_available}")
    chosen_measure = measure["values"][0] if measure else None

    # Keep requests under PxWeb's 150,000-cell ceiling and avoid oversized responses.
    records = []
    errors = []
    for yr in years_available:
        for k in range(0, len(common), 15):
            origins = common[k:k+15]
            query = [
                {"code": residence["code"], "selection": {"filter": "item", "values": origins}},
                {"code": workplace["code"], "selection": {"filter": "item", "values": common}},
                {"code": sex["code"], "selection": {"filter": "item", "values": [total_sex]}},
                {"code": year["code"], "selection": {"filter": "item", "values": [yr]}},
            ]
            if measure:
                query.append({"code": measure["code"], "selection": {"filter": "item", "values": [chosen_measure]}})
            res = request("POST", URL, json={"query": query, "response": {"format":"json"}})
            columns = [c["code"] for c in res["columns"] if c.get("type") != "c"]
            expected = {residence["code"], workplace["code"], year["code"]}
            if not expected.issubset(columns):
                raise RuntimeError(f"Unexpected SCB response dimensions: {columns}")
            for observation in res["data"]:
                dims = dict(zip(columns, observation["key"]))
                home, work = str(dims[residence["code"]]).zfill(4), str(dims[workplace["code"]]).zfill(4)
                raw = observation["values"][0]
                if raw in (None, "", "..", ".", "-"):
                    errors.append({"year":yr, "home":home, "work":work, "value":raw})
                    continue
                count = float(str(raw).replace(" ", "").replace(",", "."))
                if count < 0:
                    raise RuntimeError("Negative commuter/employment count")
                records.append({"year":int(yr), "home":home, "work":work, "employed":count})

    # Refuse partial matrices: an absent pair may be confidentiality suppression
    # or missing data. Publish raw records only and mark coverage before aggregation.
    if not records:
        raise RuntimeError("No valid SCB observations")
    out = DEST / "commuting_flows_2020_2024.csv"
    with out.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=["year","home","work","employed"])
        writer.writeheader()
        writer.writerows(records)
    report = {
        "table":"ArRegPend2", "url":URL, "years":years_available,
        "municipalities":len(common), "observations":len(records),
        "missing_or_suppressed_count":len(errors),
        "missing_or_suppressed_examples":errors[:10],
        "sex_category":total_sex,
        "method_notes":[
            "Employed persons 15-74 by residential and work municipality, not observed trip counts.",
            "2024 SCB adjustment to self-employed classification affects comparability.",
            "Persons without attributable workplace may be allocated to home municipality.",
            "Statistical disclosure control can make totals differ from sums of cells.",
            "Raw import only. No prediction models modified.",
        ],
        "aggregation_approved": len(errors)==0,
    }
    (DEST / "commuting_import_status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__=="__main__":
    main()
