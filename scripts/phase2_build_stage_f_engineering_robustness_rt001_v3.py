#!/usr/bin/env python3
"""Build source-closed Stage-F engineering sensitivity on lossless RT-001 V3 timetables."""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
from typing import Mapping

from src.phase2_final_operational_robustness_v2 import (
    ExactTrip,
    plan_bus_to_rail_connections,
    plan_rail_to_bus_connections,
)
from src.phase2_stage_f_engineering_robustness_rt001_v3 import (
    EPS,
    HUB_ID,
    RouteStressMeta,
    audit_stressed_blocks,
    retained_count_from_sorted_slacks,
)
import scripts.phase2_build_final_operational_robustness_v2 as stage_e
import scripts.phase2_run_final_operational_robustness_rt001_v3 as adapter

STATUS = "PASS_PHASE2_STAGE_F_ENGINEERING_SENSITIVITY_RT001_V3"
CONTRACT = "PHASE2_STAGE_F_CERTIFIED_ENGINEERING_SENSITIVITY_RT001_V3"
STAGE_D_STATUS = "PASS_PHASE2_STAGE_D_EXACT_TIMETABLE_RT001_V3"
STAGE_E_STATUS = "PASS_PHASE2_FINAL_OPERATIONAL_ROBUSTNESS_RT001_V3"

SURFACE_FIELDS = [
    "selected_timetable_id","scenario_id","topology_family","runtime_multiplier",
    "dwell_per_nonhub_public_stop_occurrence_min","rail_event_clock_shift_min","profile_id",
    "bus_to_rail_lecco_source_count","bus_to_rail_lecco_planned_count","bus_to_rail_lecco_retained_count","bus_to_rail_lecco_retention_share_engineering",
    "bus_to_rail_milano_source_count","bus_to_rail_milano_planned_count","bus_to_rail_milano_retained_count","bus_to_rail_milano_retention_share_engineering",
    "rail_to_bus_lecco_source_count","rail_to_bus_lecco_planned_count","rail_to_bus_lecco_retained_count","rail_to_bus_lecco_retention_share_engineering",
    "rail_to_bus_milano_source_count","rail_to_bus_milano_planned_count","rail_to_bus_milano_retained_count","rail_to_bus_milano_retention_share_engineering",
    "bidirectional_worst_retention_share_engineering","planned_connection_identity_preserved",
    "next_target_rebinding_used_as_success","sensitivity_is_empirical_probability",
    "primary_selected","runner_up_selected","weighted_composite_score"
]
BLOCK_FIELDS = [
    "selected_timetable_id","scenario_id","topology_family","runtime_multiplier",
    "dwell_per_nonhub_public_stop_occurrence_min","recovery_min","nominal_stage_d_fleet",
    "minimum_vehicle_requirement","minimum_additional_vehicle_requirement",
    "vehicle_conflict_count_on_nominal_blocks","nominal_block_assignment_infeasible_under_case",
    "minimum_block_slack_min","median_block_slack_min","maximum_block_slack_min",
    "recovery_selected","sensitivity_is_empirical_probability"
]
SUMMARY_FIELDS = [
    "selected_timetable_id","scenario_id","topology_family","profile_id",
    "bus_to_rail_worst_retention_share_engineering","rail_to_bus_worst_retention_share_engineering",
    "bidirectional_worst_retention_share_engineering","maximum_vehicle_requirement_across_engineering_cases",
    "maximum_additional_vehicle_requirement_across_engineering_cases","any_nominal_block_infeasibility",
    "full_gjt_calculated","missed_connection_probability_inferred","passenger_route_weights_inferred",
    "primary_selected","runner_up_selected","weighted_composite_score"
]


def sha256_path(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        yield from csv.DictReader(f)


def read_gzip(path: Path):
    with gzip.open(path,"rt",encoding="utf-8-sig",newline="") as f:
        yield from csv.DictReader(f)


def writer(path: Path, fields: list[str]):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=path.open("wb")
    gz=gzip.GzipFile(filename="",mode="wb",fileobj=raw,compresslevel=9,mtime=0)
    text=io.TextIOWrapper(gz,encoding="utf-8",newline="")
    w=csv.DictWriter(text,fieldnames=fields,lineterminator="\n",extrasaction="raise")
    w.writeheader()
    return raw,text,w


def close(raw,text):
    text.flush(); text.close(); raw.close()


def fmt(v):
    if v is None: return ""
    if isinstance(v,bool): return str(v).lower()
    if isinstance(v,int): return str(v)
    x=float(v)
    if not math.isfinite(x): raise ValueError("non-finite output")
    return f"{x:.9f}"


def validate_inputs(args):
    d=load_json(args.stage_d_validation)
    e=load_json(args.stage_e_validation)
    f=load_json(args.stage_f_sensitivity)
    if d.get("status")!=STAGE_D_STATUS or d.get("contract")!="PHASE2_BUDGET_LOSSLESS_EXHAUSTIVE_EXACT_CLOCKFACE_TIMETABLE_RT001_V3":
        raise ValueError("Stage D RT001 V3 not certified")
    if e.get("status")!=STAGE_E_STATUS or e.get("stage_d_fixture_is_final_selection_lineage") is not True:
        raise ValueError("Stage E RT001 V3 not certified on final-selection lineage")
    if e.get("stage_d_cross_implementation_audit_pass") is not True:
        raise ValueError("Stage D independent cross-audit not bound into Stage E")
    if f.get("contract")!="PHASE2_STAGE_F_ENGINEERING_SENSITIVITY_RT001_V3" or f.get("status")!="ASSUMPTION_SENSITIVITY_GRID_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("unexpected Stage F sensitivity contract")
    if f.get("source_grid_sha256") != sha256_path(args.source_sensitivity_grid):
        raise ValueError("historical certified sensitivity grid hash mismatch")
    source=load_json(args.source_sensitivity_grid)
    if source.get("contract")!="PHASE2_ROBUSTNESS_TOURNAMENT_V2" or source.get("status")!="ASSUMPTION_SENSITIVITY_GRID_NOT_EMPIRICAL_INTERVAL":
        raise ValueError("source sensitivity grid is not certified assumption grid")
    for key in ("runtime_multiplier","dwell_per_nonhub_public_stop_occurrence_min","rail_event_clock_shift_min"):
        if [float(x) for x in f[key]] != [float(x) for x in source[key]]:
            raise ValueError(f"Stage F grid drift: {key}")
    if int(f["expected_stress_case_count_per_timetable"])!=81:
        raise ValueError("Stage F factorial must contain 81 cells")
    for key,path in (
        ("timetable_output_sha256",args.stage_d_timetables),
        ("trip_output_sha256",args.stage_d_trips),
        ("route_inputs_sha256",args.route_input),
        ("s8_events_sha256",args.s8_events),
        ("s8_sensitivity_config_sha256",args.s8_sensitivity),
    ):
        if d.get("lineage",{}).get(key)!=sha256_path(path):
            raise ValueError(f"Stage D source hash mismatch {key}")
    if e.get("lineage",{}).get("stage_d_v3_validation_sha256")!=sha256_path(args.stage_d_validation):
        raise ValueError("Stage E does not bind supplied Stage D validation")
    if any(e.get(k) is not False for k in ("budget_selected","calendar_selected","recovery_values_selected","primary_selected","runner_up_selected","weighted_composite_score","passenger_weighting_applied","municipal_od_downscaled","ridership_forecast","random_search")):
        raise ValueError("Stage E selection/epistemic boundary violated")
    return d,e,f


def load_timetables(path: Path, expected: int):
    out={}
    for r in read_csv(path):
        tid=str(r["selected_timetable_id"])
        if not tid or tid in out: raise ValueError("duplicate/blank selected_timetable_id")
        out[tid]=r
    if len(out)!=expected: raise ValueError(f"timetable count {len(out)} != {expected}")
    return out


def load_route_meta(path: Path):
    out={}
    for r in read_csv(path):
        rid=str(r["route_id"])
        anchors=json.loads(r["anchors_json"])
        if not isinstance(anchors,list) or len(anchors)<2 or str(anchors[0])!=HUB_ID:
            raise ValueError(f"invalid anchors {rid}")
        nonhub=sum(str(a)!=HUB_ID for a in anchors[1:])
        meta=RouteStressMeta(
            route_id=rid,
            public_runtime_min=float(r["public_runtime_min"]),
            cycle_runtime_min=float(r["cycle_runtime_min"]),
            nonhub_public_stop_occurrences=nonhub,
            bus_to_rail_passenger_event_supported=stage_e.strict_bool(r["bus_to_rail_passenger_event_supported"]),
        )
        meta.validate()
        if rid in out: raise ValueError(f"duplicate route {rid}")
        out[rid]=meta
    return out


def load_trips(path: Path,tables: Mapping[str,dict[str,str]],meta: Mapping[str,RouteStressMeta],recoveries=(5,10,15)):
    out=defaultdict(list); seen=set(); n=0
    for r in read_gzip(path):
        tid=str(r["selected_timetable_id"]); rid=str(r["route_id"]); ordinal=int(r["trip_ordinal"])
        if tid not in tables or rid not in meta: raise ValueError("trip references unknown timetable/route")
        key=(tid,rid,ordinal)
        if key in seen: raise ValueError(f"duplicate trip {key}")
        seen.add(key)
        start=float(tables[tid]["span_start_min"]); end=float(tables[tid]["span_end_min"])
        physical_public=float(r["public_service_end_min"])
        public_return=(physical_public if meta[rid].bus_to_rail_passenger_event_supported and start <= physical_public < end else None)
        trip=ExactTrip(
            stage_d_input_id=tid,scenario_id=str(tables[tid]["scenario_id"]),route_id=rid,trip_ordinal=ordinal,
            hub_departure_min=float(r["departure_min"]),public_hub_return_min=public_return,
            vehicle_hub_return_min=float(r["vehicle_return_hub_min"]),
            block_by_recovery={rec:adapter.parse_vehicle_id(r[f"vehicle_id_recovery{rec}"],field=f"vehicle_id_recovery{rec}") for rec in recoveries},
        )
        trip.validate(); out[tid].append(trip); n+=1
    for rows in out.values(): rows.sort(key=lambda t:(t.hub_departure_min,t.route_id,t.trip_ordinal))
    if set(out)!=set(tables): raise ValueError("trip/timetable universe mismatch")
    return dict(out),n


def planned_groups(trips,rail_events,profiles,table):
    candidates=plan_bus_to_rail_connections(trips,rail_events,profiles)+plan_rail_to_bus_connections(
        trips,rail_events,profiles,span_start_min=float(table["span_start_min"]),span_end_min=float(table["span_end_min"])
    )
    source=defaultdict(int); slacks=defaultdict(list)
    for c in candidates:
        key=(c.profile_id,c.connection_type,c.direction,c.route_id if c.connection_type=="BUS_TO_RAIL" else "ALL")
        source[key]+=1
        if c.planned_connection_exists:
            if c.nominal_slack_min is None: raise ValueError("planned connection without slack")
            slacks[key].append(float(c.nominal_slack_min))
    for values in slacks.values(): values.sort()
    return source,slacks,len(candidates),sum(len(v) for v in slacks.values())


def counts(source,slacks,profile,ctype,direction,meta,runtime,dwell,shift):
    if ctype=="BUS_TO_RAIL":
        source_count=sum(v for (p,c,d,r),v in source.items() if p==profile and c==ctype and d==direction)
        planned=retained=0
        for (p,c,d,rid),vals in slacks.items():
            if p!=profile or c!=ctype or d!=direction: continue
            planned+=len(vals)
            delta=meta[rid].public_runtime_delta(runtime,dwell)-shift
            retained+=retained_count_from_sorted_slacks(vals,delta)
        return source_count,planned,retained
    key=(profile,ctype,direction,"ALL")
    vals=slacks.get(key,[])
    return source.get(key,0),len(vals),retained_count_from_sorted_slacks(vals,shift)


def share(planned,retained): return None if planned==0 else retained/planned


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("stage_d_validation","stage_d_timetables","stage_d_trips","route_input","s8_events","s8_sensitivity","stage_e_validation","stage_f_sensitivity","source_sensitivity_grid","output_dir"):
        p.add_argument("--"+name.replace("_","-"),dest=name,type=Path,required=True)
    a=p.parse_args()
    for path in (a.stage_d_validation,a.stage_d_timetables,a.stage_d_trips,a.route_input,a.s8_events,a.s8_sensitivity,a.stage_e_validation,a.stage_f_sensitivity,a.source_sensitivity_grid):
        if not path.is_file(): raise FileNotFoundError(path)
    d,e,f=validate_inputs(a)
    tables=load_timetables(a.stage_d_timetables,int(d["unique_selected_exact_timetable_count"]))
    meta=load_route_meta(a.route_input)
    trips_by_tid,trip_count=load_trips(a.stage_d_trips,tables,meta)
    if trip_count!=int(d["selected_exact_trip_row_count"]): raise ValueError("trip count mismatch")
    profiles=stage_e.load_profiles(a.s8_sensitivity); rail_events=stage_e.load_rail_events(a.s8_events)
    runtimes=[float(v) for v in f["runtime_multiplier"]]; dwells=[float(v) for v in f["dwell_per_nonhub_public_stop_occurrence_min"]]; shifts=[float(v) for v in f["rail_event_clock_shift_min"]]
    recoveries=[int(v) for v in f["recovery_values_min"]]
    if len(list(itertools.product(runtimes,dwells,shifts,profiles)))!=81: raise ValueError("factorial mismatch")
    out=a.output_dir; surface_path=out/"stage_f_engineering_connection_surface_rt001_v3.csv.gz"; block_path=out/"stage_f_engineering_block_surface_rt001_v3.csv.gz"; summary_path=out/"stage_f_engineering_timetable_summary_rt001_v3.csv.gz"; validation_path=out/"stage_f_engineering_robustness_rt001_v3_validation.json"
    sraw,stext,sw=writer(surface_path,SURFACE_FIELDS); braw,btext,bw=writer(block_path,BLOCK_FIELDS); qraw,qtext,qw=writer(summary_path,SUMMARY_FIELDS)
    surface_rows=block_rows=summary_rows=connection_candidates=planned_connections=0; any_target_rebind=False; technical_return_connections=0
    block_infeasible=additional_vehicle_cases=0
    try:
        for tid in sorted(tables):
            table=tables[tid]; trips=trips_by_tid[tid]
            source,slacks,candidate_n,planned_n=planned_groups(trips,rail_events,profiles,table)
            connection_candidates+=candidate_n; planned_connections+=planned_n
            # Candidate construction only receives in-span public_hub_return_min; technical closures therefore cannot create B2R.
            technical_routes={rid for rid,m in meta.items() if not m.bus_to_rail_passenger_event_supported}
            technical_return_connections += sum(
                v for (p,c,d,rid),v in source.items() if c=="BUS_TO_RAIL" and rid in technical_routes
            )
            per_profile_values={p.profile_id:{"b2r":[],"r2b":[],"bi":[]} for p in profiles}
            for runtime,dwell,shift,profile in itertools.product(runtimes,dwells,shifts,profiles):
                row={
                    "selected_timetable_id":tid,"scenario_id":table["scenario_id"],"topology_family":table["topology_family"],
                    "runtime_multiplier":fmt(runtime),"dwell_per_nonhub_public_stop_occurrence_min":fmt(dwell),"rail_event_clock_shift_min":fmt(shift),"profile_id":profile.profile_id,
                    "planned_connection_identity_preserved":"true","next_target_rebinding_used_as_success":"false","sensitivity_is_empirical_probability":"false",
                    "primary_selected":"false","runner_up_selected":"false","weighted_composite_score":"false",
                }
                shares=[]
                for ctype,prefix in (("BUS_TO_RAIL","bus_to_rail"),("RAIL_TO_BUS","rail_to_bus")):
                    ctype_shares=[]
                    for direction,label in (("LECCO","lecco"),("MILANO","milano")):
                        src,pln,ret=counts(source,slacks,profile.profile_id,ctype,direction,meta,runtime,dwell,shift)
                        sh=share(pln,ret)
                        row[f"{prefix}_{label}_source_count"]=src; row[f"{prefix}_{label}_planned_count"]=pln; row[f"{prefix}_{label}_retained_count"]=ret; row[f"{prefix}_{label}_retention_share_engineering"]=fmt(sh)
                        if sh is not None: ctype_shares.append(sh); shares.append(sh)
                    if ctype_shares: per_profile_values[profile.profile_id]["b2r" if ctype=="BUS_TO_RAIL" else "r2b"].append(min(ctype_shares))
                bi=min(shares) if shares else None; row["bidirectional_worst_retention_share_engineering"]=fmt(bi)
                if bi is not None: per_profile_values[profile.profile_id]["bi"].append(bi)
                sw.writerow(row); surface_rows+=1
            block_stats=[]
            for runtime,dwell,recovery in itertools.product(runtimes,dwells,recoveries):
                stats=audit_stressed_blocks(trips,meta,runtime_multiplier=runtime,dwell_per_stop_min=dwell,recovery_min=recovery)
                stated=int(table[f"exact_fleet_recovery{recovery}"])
                if abs(runtime-1.0)<=EPS and abs(dwell)<=EPS and int(stats["minimum_vehicle_requirement"])!=stated:
                    raise ValueError(f"{tid}: nominal fleet reproduction failed recovery {recovery}")
                block_infeasible+=int(bool(stats["nominal_block_assignment_infeasible_under_case"])); additional_vehicle_cases+=int(int(stats["minimum_additional_vehicle_requirement"])>0)
                row={"selected_timetable_id":tid,"scenario_id":table["scenario_id"],"topology_family":table["topology_family"],"runtime_multiplier":fmt(runtime),"dwell_per_nonhub_public_stop_occurrence_min":fmt(dwell),"recovery_min":recovery,
                     "nominal_stage_d_fleet":stats["nominal_stage_d_fleet"],"minimum_vehicle_requirement":stats["minimum_vehicle_requirement"],"minimum_additional_vehicle_requirement":stats["minimum_additional_vehicle_requirement"],"vehicle_conflict_count_on_nominal_blocks":stats["vehicle_conflict_count_on_nominal_blocks"],"nominal_block_assignment_infeasible_under_case":str(stats["nominal_block_assignment_infeasible_under_case"]).lower(),"minimum_block_slack_min":fmt(stats["minimum_block_slack_min"]),"median_block_slack_min":fmt(stats["median_block_slack_min"]),"maximum_block_slack_min":fmt(stats["maximum_block_slack_min"]),"recovery_selected":"false","sensitivity_is_empirical_probability":"false"}
                bw.writerow(row); block_rows+=1; block_stats.append(stats)
            for profile in profiles:
                pv=per_profile_values[profile.profile_id]
                qw.writerow({"selected_timetable_id":tid,"scenario_id":table["scenario_id"],"topology_family":table["topology_family"],"profile_id":profile.profile_id,
                    "bus_to_rail_worst_retention_share_engineering":fmt(min(pv["b2r"]) if pv["b2r"] else None),"rail_to_bus_worst_retention_share_engineering":fmt(min(pv["r2b"]) if pv["r2b"] else None),"bidirectional_worst_retention_share_engineering":fmt(min(pv["bi"]) if pv["bi"] else None),
                    "maximum_vehicle_requirement_across_engineering_cases":max(int(x["minimum_vehicle_requirement"]) for x in block_stats),"maximum_additional_vehicle_requirement_across_engineering_cases":max(int(x["minimum_additional_vehicle_requirement"]) for x in block_stats),"any_nominal_block_infeasibility":str(any(bool(x["nominal_block_assignment_infeasible_under_case"]) for x in block_stats)).lower(),"full_gjt_calculated":"false","missed_connection_probability_inferred":"false","passenger_route_weights_inferred":"false","primary_selected":"false","runner_up_selected":"false","weighted_composite_score":"false"}); summary_rows+=1
    finally:
        close(sraw,stext); close(braw,btext); close(qraw,qtext)
    expected_surface=len(tables)*81; expected_blocks=len(tables)*len(runtimes)*len(dwells)*len(recoveries); expected_summary=len(tables)*len(profiles)
    if surface_rows!=expected_surface or block_rows!=expected_blocks or summary_rows!=expected_summary: raise ValueError("output cardinality mismatch")
    if technical_return_connections!=0: raise ValueError("technical return leaked into passenger connection universe")
    validation={
        "status":STATUS,"contract":CONTRACT,"stage_d_status":d["status"],"stage_e_status":e["status"],"selected_exact_timetable_count":len(tables),"represented_plan_context_count":int(d["stage_c_plan_context_count"]),"exact_public_trip_count":trip_count,
        "stress_case_count_per_timetable":81,"connection_surface_row_count":surface_rows,"block_surface_row_count":block_rows,"summary_row_count":summary_rows,"connection_candidate_count_nominal":connection_candidates,"planned_connection_count_nominal":planned_connections,
        "runtime_multiplier":runtimes,"dwell_per_nonhub_public_stop_occurrence_min":dwells,"rail_event_clock_shift_min":shifts,"transfer_profile_ids":[p.profile_id for p in profiles],"recovery_minutes":recoveries,
        "planned_connection_identity_preserved":True,"next_target_rebinding_used_as_success":False,"technical_return_used_as_passenger_service":False,"technical_return_connection_count":technical_return_connections,
        "sensitivity_is_empirical_probability":False,"runtime_multiplier_is_empirical_interval":False,"dwell_is_empirical_distribution":False,"rail_shift_is_empirical_delay_distribution":False,"missed_connection_probability_inferred":False,"full_gjt_calculated":False,"passenger_route_weights_inferred":False,"municipal_od_downscaled":False,"ridership_forecast":False,"random_search":False,
        "nominal_block_assignment_infeasible_case_count":block_infeasible,"cases_requiring_additional_vehicle_count":additional_vehicle_cases,
        "decision_budget_selected":False,"calendar_selected":False,"recovery_selected":False,"primary_selected":False,"runner_up_selected":False,"weighted_composite_score":False,"final_selection_authorized":False,
        "remaining_stage_f_limitations":["NO_EMPIRICAL_DELAY_PROBABILITY_DISTRIBUTION","NO_ROUTE_LEVEL_DEMAND_WEIGHT_PERTURBATION_WITHOUT_AUTHORISED_SPATIAL_ALLOCATION","NO_FULL_DEMAND_WEIGHTED_GJT","CURRENT_SERVICE_BASELINE_REMAINS_CERTIFIED_LOCALIZABLE_LOWER_BOUND"],
        "lineage":{"stage_d_validation_sha256":sha256_path(a.stage_d_validation),"stage_e_validation_sha256":sha256_path(a.stage_e_validation),"stage_f_sensitivity_sha256":sha256_path(a.stage_f_sensitivity),"source_sensitivity_grid_sha256":sha256_path(a.source_sensitivity_grid),"stage_d_timetables_sha256":sha256_path(a.stage_d_timetables),"stage_d_trips_sha256":sha256_path(a.stage_d_trips),"route_input_sha256":sha256_path(a.route_input),"s8_events_sha256":sha256_path(a.s8_events),"s8_sensitivity_sha256":sha256_path(a.s8_sensitivity),"connection_surface_sha256":sha256_path(surface_path),"block_surface_sha256":sha256_path(block_path),"summary_sha256":sha256_path(summary_path)}
    }
    validation_path.parent.mkdir(parents=True,exist_ok=True); validation_path.write_text(json.dumps(validation,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:validation[k] for k in ("status","selected_exact_timetable_count","stress_case_count_per_timetable","connection_surface_row_count","block_surface_row_count","nominal_block_assignment_infeasible_case_count","cases_requiring_additional_vehicle_count")},indent=2,sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
