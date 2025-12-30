"""
KHOA OceanGrid API client for tide observations.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import urllib.parse
import urllib.request
from typing import Any, Optional

from dotenv import load_dotenv


BASE_URL = "http://www.khoa.go.kr/api/oceangrid"


@dataclass
class StationInfo:
    obs_code: str
    obs_name: Optional[str]
    latitude: float
    longitude: float
    distance_km: float


class KhoaClient:
    def __init__(self, service_key: Optional[str] = None) -> None:
        load_dotenv()
        self.service_key = service_key or os.getenv("BADA_NURI_OPENAPI_SERVICE_KEY")
        if not self.service_key:
            raise ValueError("Missing BADA_NURI_OPENAPI_SERVICE_KEY environment variable")

    def get_nearest_station(
        self,
        data_type: str,
        latitude: float,
        longitude: float,
        required_terms: Optional[list[str]] = None,
        required_data_types: Optional[list[str]] = None,
        required_prefixes: Optional[list[str]] = None,
    ) -> StationInfo:
        payload = self._fetch_json(
            data_type,
            {
                "ServiceKey": self.service_key,
                "ResultType": "json",
            },
        )
        stations = _extract_items(payload)
        if not stations:
            error_msg = _extract_error_message(payload)
            if error_msg:
                raise ValueError(f"No station data returned from KHOA API: {error_msg}")
            raise ValueError("No station data returned from KHOA API")

        nearest = None
        for item in stations:
            if not isinstance(item, dict):
                continue
            obs_code = _get_first_value(
                item,
                ["ObsCode", "obsCode", "obs_code", "obs_post_id", "obsPostId"],
            )
            lat = _get_first_value(
                item,
                ["ObsLat", "obsLat", "obs_lat", "latitude", "lat", "obs_lat", "obsLat"],
            )
            lon = _get_first_value(
                item,
                ["ObsLon", "obsLon", "obs_lon", "longitude", "lon", "obs_lon", "obsLon"],
            )
            if not obs_code or lat is None or lon is None:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (TypeError, ValueError):
                continue
            distance_km = _haversine_km(latitude, longitude, lat_f, lon_f)
            obs_name = _get_first_value(
                item,
                ["ObsName", "obsName", "obs_name", "name", "obs_post_name", "obsPostName"],
            )
            obs_object = _get_first_value(item, ["obs_object", "obsObject", "obsobject"])
            obs_data_type = _get_first_value(item, ["data_type", "dataType"])
            if required_data_types and obs_data_type:
                if str(obs_data_type) not in required_data_types:
                    continue
            if required_prefixes and obs_code:
                if not any(str(obs_code).startswith(prefix) for prefix in required_prefixes):
                    continue
            if required_terms and obs_object:
                obs_object_text = str(obs_object)
                if not all(term in obs_object_text for term in required_terms):
                    continue
            if nearest is None or distance_km < nearest.distance_km:
                nearest = StationInfo(
                    obs_code=str(obs_code),
                    obs_name=str(obs_name) if obs_name else None,
                    latitude=lat_f,
                    longitude=lon_f,
                    distance_km=distance_km,
                )

        if not nearest:
            raise ValueError("No station with coordinates found in KHOA response")
        return nearest

    def get_tide_data(self, data_type: str, obs_code: str, date: str) -> Any:
        payload = self._fetch_json(
            data_type,
            {
                "ServiceKey": self.service_key,
                "ObsCode": obs_code,
                "Date": date,
                "ResultType": "json",
            },
        )
        return payload

    def _fetch_json(self, data_type: str, params: dict[str, Any]) -> Any:
        query = urllib.parse.urlencode(params)
        url = f"{BASE_URL}/{data_type}/search.do?{query}"
        print(f"[KHOA DEBUG] Request URL: {url}")
        with urllib.request.urlopen(url, timeout=10) as response:
            raw = response.read().decode("utf-8")
        print(f"[KHOA DEBUG] Raw response: {raw[:1000]}")
        return json.loads(raw)


def _get_first_value(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return _unwrap_value(item[key])
    normalized_map = {_normalize_key(k): k for k in item.keys()}
    for key in keys:
        normalized = _normalize_key(key)
        if normalized in normalized_map:
            raw_value = item[normalized_map[normalized]]
            if raw_value not in (None, ""):
                return _unwrap_value(raw_value)
    return None


def _unwrap_value(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("value", "Value", "val"):
            if key in value and value[key] not in (None, ""):
                return value[key]
    return value


def _normalize_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _extract_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if _looks_like_station(payload):
            return [payload]
        for key in ("data", "Data", "result", "Result", "item", "items", "list", "List"):
            if key in payload:
                items = _extract_items(payload[key])
                if items:
                    return items
        for value in payload.values():
            items = _extract_items(value)
            if items:
                return items
    return []


def _extract_error_message(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    for key in ("error", "Error", "message", "Message"):
        if key in payload and payload[key]:
            return str(payload[key])
    result = payload.get("result") or payload.get("Result")
    if isinstance(result, dict):
        for key in ("msg", "message", "error", "Error", "code", "resultCode"):
            if key in result and result[key]:
                return str(result[key])
    return None


def _looks_like_station(payload: dict[str, Any]) -> bool:
    keys = {_normalize_key(k) for k in payload.keys()}
    if {"obspostid", "obscode"} & keys:
        return True
    if {"obslat", "obslon"} <= keys:
        return True
    return False


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c
