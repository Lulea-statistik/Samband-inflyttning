#!/usr/bin/env python3
"""Research-only thematic registry for equal-footing variable comparison."""
import json
from pathlib import Path
D=Path("docs/data")
def theme(s):
    s=s.removeprefix("lag1_")
    if any(x in s for x in ("arbetslos","langtidsarbetslos","arbetskraft","sysselsatt","utanf_arbetkraft","bas_pensionarer","bas_sjuka","bas_ovriga","bas_studerande")):
        return "arbetsmarknad_och_aktivitet"
    if any(x in s for x in ("inkomst","lonesumma","ekonomisk_standard","smahuspris")):
        return "inkomst_och_bostadsekonomi"
    if any(x in s for x in ("bostad","smahus","fritidshus","hyresratt","bostadsratt","fardigstallda","lediga_allmannytta")):
        return "bostader_och_bestand"
    if any(x in s for x in ("lok_","idrott","forening","kultur_service")):
        return "foreningsliv_och_kultur"
    if any(x in s for x in ("industri","hotell_restaurang","arbetsstalle","fa_arbetsplatser","externa_fa_jobb")):
        return "naringslivsstruktur"
    if any(x in s for x in ("gymnasium","eftergymnasial","studerande")):
        return "utbildning_och_studier"
    if any(x in s for x in ("strand","natur","skogsmark","tatort","regional_centre","anlagd","befolkningstathet","snoskoter","folkmangd")):
        return "geografi_och_mark"
    if "valdeltagande" in s:return "demokrati"
    if "brott" in s:return "trygghet"
    return "oklassificerad_manuell_granskning"
def main():
    audit=json.loads((D/"fair_variable_eligibility_audit.json").read_text(encoding="utf-8"))
    records=[]
    for f in audit["features"]:
        if not f["complete_sample_2022_2024"] or not f["blind_predictor_allowed_by_name"]:
            continue
        records.append({"feature":f["feature"],"theme":theme(f["feature"]),
                        "original_candidate_pool":f["historical_pool"],
                        "newly_discovered":f["newly_discovered"]})
    assert len(records)==73
    themes={}
    for r in records:
        t=themes.setdefault(r["theme"],{"total":0,"original":0,"new":0,"features":[]})
        t["total"]+=1;t["original"]+=int(r["original_candidate_pool"])
        t["new"]+=int(not r["original_candidate_pool"]);t["features"].append(r["feature"])
    output={"status":"thematic_register_manual_review_required","production_changed":False,
      "candidate_count":len(records),"themes":themes,"records":records,
      "limitations":["Thematic assignments are heuristic and must be reviewed manually before use in feature selection.",
      "Some fields span themes; grouping does not imply validity or causal meaning.",
      "Published source timing and comparability are not yet verified."]}
    (D/"fair_variable_thematic_register.json").write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:{"total":v["total"],"old":v["original"],"new":v["new"]} for k,v in themes.items()},ensure_ascii=False))
if __name__=="__main__":main()
