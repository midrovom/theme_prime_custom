"""Weight-based scenarios, grouped by source, company, origin warehouse and city.

These are capacity estimates, not road routing or lowest-cost quotations.
Vehicles assigned to each lane operate in parallel and cannot be shared with
another lane during the scenario. A trip includes the configured return cycle.
"""
from collections import defaultdict
import math

from .engine import EPS, normalize

DEFAULT_VEHICLES = (
    ("REF_3_5", "Camión 3,5 t", 3.5),
    ("REF_5", "Camión 5 t", 5.0),
    ("REF_10", "Camión 10 t", 10.0),
    ("REF_15", "Camión 15 t", 15.0),
    ("REF_28", "Tráiler 28 t", 28.0),
)
DEFAULT_SETTINGS = {"target_days": 3, "available_vehicles": 1, "trips_per_day": 1.0}


def relation_id(value):
    return value[0] if isinstance(value, (tuple, list)) and value else value


def _ceil(value):
    return math.ceil(value - 1e-9)


def validate_settings(settings):
    for key in ("target_days", "available_vehicles"):
        value = settings[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
            raise ValueError("Los días y vehículos deben ser enteros.")
    if not 1 <= settings["target_days"] <= 3650 or not 0 <= settings["available_vehicles"] <= 100000:
        raise ValueError("Plazo objetivo o cantidad de vehículos fuera de rango.")
    trips = settings["trips_per_day"]
    if isinstance(trips, bool) or not isinstance(trips, (int, float)) or not math.isfinite(trips) or not 0 < trips <= 100:
        raise ValueError("Los viajes diarios deben ser mayores a cero y hasta 100.")


def vehicle_estimate(weight_kg, vehicle, settings):
    validate_settings(settings)
    capacity, utilization = float(vehicle["capacity_tons"]), float(vehicle["utilization_pct"])
    if not math.isfinite(capacity) or capacity <= 0 or not math.isfinite(utilization) or not 0 < utilization <= 100:
        raise ValueError("Revise la capacidad y utilización del vehículo.")
    if not math.isfinite(weight_kg) or weight_kg < 0:
        raise ValueError("Peso pendiente inválido.")
    useful_tons = capacity * utilization / 100
    trips = _ceil(weight_kg / (useful_tons * 1000)) if weight_kg > EPS else 0
    slots = math.floor(settings["target_days"] * settings["trips_per_day"] + 1e-9)
    required = _ceil(trips / slots) if slots else (0 if not trips else None)
    fleet = settings["available_vehicles"]
    # Each truck must finish a whole cycle: 3 trips / 2 trucks / 0.4 trips
    # per day needs two waves, or 5 days, not ceil(3/0.8) = 4 days.
    days = _ceil(_ceil(trips / fleet) / settings["trips_per_day"]) if fleet and trips else (0 if not trips else None)
    required_days = _ceil(_ceil(trips / required) / settings["trips_per_day"]) if required and trips else (0 if not trips else None)
    return {
        "vehicle_id": vehicle["id"], "vehicle_name": vehicle["name"],
        "capacity_tons": capacity, "useful_tons": useful_tons,
        "utilization_pct": utilization, "trips": trips,
        "required_vehicles": required,
        "additional_vehicles": max(0, required - fleet) if required is not None else None,
        "available_vehicles": fleet, "days_current_fleet": days,
        "days_required_fleet": required_days,
        "target_days": settings["target_days"], "trips_per_day": settings["trips_per_day"],
        "trips_per_vehicle_in_target": slots,
        "spare_trip_capacity_tons": trips * useful_tons - weight_kg / 1000,
    }


def _route_settings(pack, city, warehouse_code):
    settings = {**DEFAULT_SETTINGS, **pack.get("settings", {})}
    candidates = [r for r in pack.get("routes", []) if normalize(r["city"]) == city
                  and (not normalize(r.get("warehouse_code")) or normalize(r["warehouse_code"]) == warehouse_code)]
    candidates.sort(key=lambda r: bool(normalize(r.get("warehouse_code"))), reverse=True)
    route = candidates[0] if candidates else {}
    settings.update({key: route[key] for key in DEFAULT_SETTINGS if key in route})
    validate_settings(settings)
    return settings, route.get("vehicle_id") or None


def _group_destination_lanes(lanes, packs):
    """Optional multi-origin scenario; never override an origin-specific rule."""
    groups = defaultdict(list)
    for lane in lanes:
        groups[(lane["company_id"], lane["source_id"], lane["city"])].append(lane)
    result = []
    for (company, source, city), origins in groups.items():
        origin_codes = {lane["warehouse_code"] for lane in origins}
        specific_rule = any(normalize(r["city"]) == city and normalize(r.get("warehouse_code")) in origin_codes - {""}
                            for r in packs.get(company, {}).get("routes", []))
        missing_origin = any(lane["missing_detail"] or lane["warehouse"] == "SIN BODEGA" for lane in origins)
        if len(origins) < 2 or specific_rule or missing_origin or city == "SIN CIUDAD":
            for lane in origins:
                if len(origins) > 1 and specific_rule:
                    lane["grouping_note"] = "Se mantiene una salida por bodega: hay una regla específica de origen."
            result.extend(origins)
            continue
        combined = {**origins[0], "key": f"{company}|{source}|*|{city}", "warehouse_code": "",
                    "warehouse": "%s bodegas agrupadas" % len(origins), "grouped_origins": True,
                    "origins": [origin for lane in origins for origin in lane["origins"]]}
        for field in ("weight_kg", "pending_pallets", "unknown_weight_lines", "unknown_pallet_lines"):
            combined[field] = sum(lane[field] for lane in origins)
        for field in ("invoices", "review_ids"):
            combined[field] = set().union(*(lane[field] for lane in origins))
        result.append(combined)
    return result


def build_transport_plan(invoices, lines, packs, scope="transcash", grouping="warehouse"):
    if scope not in ("transcash", "filtered"):
        raise ValueError("Alcance del plan no permitido.")
    if grouping not in ("warehouse", "destination"):
        raise ValueError("Forma de agrupar la carga no permitida.")
    invoices = [r for r in invoices if r.get("pending")]
    selected = {r["id"]: r for r in invoices if scope == "filtered" or normalize(r.get("delivery")) == "ENTREGA TRANSCASH"}
    lanes, covered = {}, set()

    def lane_for(invoice, warehouse_code, warehouse, missing_detail=False):
        company = relation_id(invoice.get("company_id"))
        source = relation_id(invoice.get("source_id"))
        city = normalize(invoice.get("city")) or "SIN CIUDAD"
        warehouse_key = normalize(warehouse_code or warehouse)
        key = (company, source, warehouse_key, city)
        if key not in lanes:
            source_ref = invoice.get("source_id")
            source_name = source_ref[1] if isinstance(source_ref, (list, tuple)) else str(source or "")
            lanes[key] = {"key": "|".join(str(x) for x in key), "company_id": company, "source_id":source,
                "source": source_name, "city": city, "warehouse_code": normalize(warehouse_code),
                "warehouse": warehouse or warehouse_code or "SIN BODEGA",
                "weight_kg": 0.0, "pending_pallets": 0.0, "invoices": set(), "review_ids": set(),
                "unknown_weight_lines": 0, "unknown_pallet_lines": 0, "missing_detail": missing_detail,
                "grouped_origins": False, "grouping_note": ""}
        return lanes[key]

    for line in lines:
        invoice_id = relation_id(line.get("invoice_id"))
        if invoice_id not in selected or line.get("pending_qty", 0) <= EPS:
            continue
        invoice = selected[invoice_id]
        lane = lane_for(invoice, line.get("warehouse_code"), line.get("warehouse"))
        covered.add(invoice_id)
        lane["invoices"].add(invoice_id)
        if invoice.get("quality_issue") or invoice.get("has_adjustment"):
            lane["review_ids"].add(invoice_id)
        weight = float(line.get("pending_weight") or 0)
        if math.isfinite(weight) and weight > EPS:
            lane["weight_kg"] += weight
        else:
            lane["unknown_weight_lines"] += 1
        lane["pending_pallets"] += max(0, float(line.get("pending_pallets") or 0))
        lane["unknown_pallet_lines"] += int(line.get("pending_pallets_available") is False)
    for invoice_id in selected.keys() - covered:
        lane = lane_for(selected[invoice_id], "", "SIN DETALLE DE BODEGA", True)
        lane["invoices"].add(invoice_id)
        lane["unknown_weight_lines"] += 1
        lane["unknown_pallet_lines"] += 1

    for lane in lanes.values():
        lane["origins"] = [{"warehouse": lane["warehouse"], "warehouse_code": lane["warehouse_code"],
                            "pending_tons": lane["weight_kg"] / 1000, "pending_pallets": lane["pending_pallets"],
                            "invoice_count": len(lane["invoices"])}]
    work_lanes = _group_destination_lanes(lanes.values(), packs) if grouping == "destination" else lanes.values()

    results = []
    for lane in work_lanes:
        pack = packs.get(lane["company_id"], {})
        settings, preferred = _route_settings(pack, lane["city"], lane["warehouse_code"])
        vehicles = [v for v in pack.get("vehicles", []) if not preferred or v["id"] == preferred]
        alternatives = [vehicle_estimate(lane["weight_kg"], v, settings) for v in vehicles]
        alternatives.sort(key=lambda a: (a["required_vehicles"] if a["required_vehicles"] is not None else math.inf,
                                          a["trips"], a["spare_trip_capacity_tons"], a["capacity_tons"]))
        issues = []
        if lane["city"] == "SIN CIUDAD": issues.append("Falta ciudad de destino")
        if lane["missing_detail"] or lane["warehouse"] == "SIN BODEGA": issues.append("Falta bodega de origen")
        if lane["unknown_weight_lines"]: issues.append("Falta peso válido en %s registro(s) pendiente(s)" % lane["unknown_weight_lines"])
        if lane["review_ids"]: issues.append("Revisar ajustes o datos en %s factura(s)" % len(lane["review_ids"]))
        if not vehicles: issues.append("Configure un tipo de vehículo activo")
        blocked = lane["city"] == "SIN CIUDAD" or lane["missing_detail"] or lane["warehouse"] == "SIN BODEGA" or lane["weight_kg"] <= EPS
        chosen = alternatives[0] if alternatives and not blocked else None
        if chosen and chosen["required_vehicles"] is None:
            issues.append("El plazo objetivo no permite completar un ciclo; aumente los días")
        results.append({**{k:v for k,v in lane.items() if k not in ("invoices", "review_ids")},
            "company_name": pack.get("company_name", ""), "invoice_count": len(lane["invoices"]),
            "review_count": len(lane["review_ids"]), "pending_tons": lane["weight_kg"] / 1000,
            "estimate": chosen, "alternatives": alternatives if not blocked else [],
            "issues": issues, "complete": not issues})
    results.sort(key=lambda r: (-r["weight_kg"], r["city"], r["warehouse"]))
    estimates = [r["estimate"] for r in results if r["estimate"]]
    plan_possible = all(r["estimate"] and r["estimate"]["required_vehicles"] is not None for r in results)
    days_available = all(r["estimate"] and r["estimate"]["days_current_fleet"] is not None for r in results)
    known_plan_possible = bool(estimates) and all(e["required_vehicles"] is not None for e in estimates)
    known_days_available = bool(estimates) and all(e["days_current_fleet"] is not None for e in estimates)
    destinations = {}
    for lane in results:
        key = (lane["company_id"],lane["source_id"],lane["city"])
        group=destinations.setdefault(key,{"key":"|".join(str(x) for x in key),"city":lane["city"],
            "source":lane["source"],"company_name":lane["company_name"],"pending_tons":0,"trips":0,
            "required_vehicles":0,"additional_vehicles":0,"days_current_fleet":0,"days_required_fleet":0,
            "available_vehicles":0,"pending_pallets":0,"unknown_pallet_lines":0,"vehicle_types":{},
            "origin_count":0,"lanes":[],"issues":[],"target_days":[],
            "complete":True,"route_count":0,"invoice_count":sum(1 for r in selected.values()
                if relation_id(r.get("company_id"))==key[0] and relation_id(r.get("source_id"))==key[1]
                and (normalize(r.get("city")) or "SIN CIUDAD")==key[2])})
        group["pending_tons"]+=lane["pending_tons"]
        group["route_count"]+=1
        group["origin_count"]+=len(lane["origins"])
        group["pending_pallets"]+=lane["pending_pallets"]
        group["unknown_pallet_lines"]+=lane["unknown_pallet_lines"]
        group["lanes"].append(lane)
        group["issues"]=list(dict.fromkeys([*group["issues"],*lane["issues"]]))
        group["complete"] &= lane["complete"]
        estimate=lane["estimate"]
        if not estimate:
            group["complete"]=False
            group["days_current_fleet"]=group["days_required_fleet"]=None
            continue
        group["trips"]+=estimate["trips"]
        group["required_vehicles"]+=estimate["required_vehicles"] or 0
        group["additional_vehicles"]+=estimate["additional_vehicles"] or 0
        group["available_vehicles"]+=estimate["available_vehicles"]
        group["target_days"].append(estimate["target_days"])
        if estimate["days_required_fleet"] is None:
            group["days_required_fleet"]=None
        elif group["days_required_fleet"] is not None:
            group["days_required_fleet"]=max(group["days_required_fleet"],estimate["days_required_fleet"])
        if estimate["days_current_fleet"] is None:
            group["days_current_fleet"]=None
        elif group["days_current_fleet"] is not None:
            group["days_current_fleet"]=max(group["days_current_fleet"],estimate["days_current_fleet"])
        if estimate["required_vehicles"] is not None:
            name=estimate["vehicle_name"]
            group["vehicle_types"][name]=group["vehicle_types"].get(name,0)+estimate["required_vehicles"]
        else:group["complete"]=False
    for group in destinations.values():
        group["vehicle_types"]=[{"name":name,"count":count} for name,count in group["vehicle_types"].items()]
        group["target_days"]=sorted(set(group["target_days"]))
        if not group["vehicle_types"]:
            group["required_vehicles"]=group["additional_vehicles"]=group["days_current_fleet"]=group["days_required_fleet"]=None
    return {
        "scope": scope, "scope_label": "Entrega Transcash" if scope == "transcash" else "Todas las modalidades filtradas",
        "grouping": grouping,
        "grouping_label": "Una salida por bodega" if grouping == "warehouse" else "Agrupar bodegas para el mismo destino",
        "lanes": results, "pending_invoices": len(selected), "excluded_invoices": len(invoices) - len(selected),
        "destinations":sorted(destinations.values(),key=lambda g:(-g["pending_tons"],g["city"])),
        "weight_kg": sum(r["weight_kg"] for r in results), "pending_tons": sum(r["pending_tons"] for r in results),
        "pending_pallets": sum(r["pending_pallets"] for r in results),
        "unknown_pallet_lines": sum(r["unknown_pallet_lines"] for r in results),
        "trips": sum(e["trips"] for e in estimates),
        "required_vehicles": sum(e["required_vehicles"] for e in estimates) if plan_possible else None,
        "additional_vehicles": sum(e["additional_vehicles"] for e in estimates) if plan_possible else None,
        "days_current_fleet": max((e["days_current_fleet"] for e in estimates), default=0) if days_available else None,
        "days_required_fleet": max((e["days_required_fleet"] for e in estimates), default=0) if plan_possible else None,
        "known_required_vehicles": sum(e["required_vehicles"] for e in estimates) if known_plan_possible else None,
        "known_additional_vehicles": sum(e["additional_vehicles"] for e in estimates) if known_plan_possible else None,
        "known_days_current_fleet": max(e["days_current_fleet"] for e in estimates) if known_days_available else None,
        "known_days_required_fleet": max(e["days_required_fleet"] for e in estimates) if known_plan_possible else None,
        "calculated_lanes": len(estimates), "total_lanes": len(results),
        "available_vehicles": sum(e["available_vehicles"] for e in estimates),
        "complete": all(r["complete"] for r in results),
        "unknown_weight_lines": sum(r["unknown_weight_lines"] for r in results),
        "settings": [{"company_id": key, "company_name": pack.get("company_name", ""),
                      **DEFAULT_SETTINGS, **pack.get("settings", {})} for key,pack in packs.items()],
    }
