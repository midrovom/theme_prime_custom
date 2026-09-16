import json
import math


def parse_gps_payload(payload):
    """Return (lat, lon, accuracy) from the browser JSON payload."""
    if not payload:
        return None
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data.get("accuracy") or 0.0)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return None
    return latitude, longitude, max(accuracy, 0.0)


def haversine_distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters."""
    radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * radius_m * math.asin(math.sqrt(a))
