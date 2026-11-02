"""
Digital Mouza Map API Integration Client for map.land.gov.bd
Connects RAG engine to official Bangladesh Digital Land Map endpoints.
"""

import requests
import json
import re
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://map.land.gov.bd"


def parse_wkt_geometry(wkt: str):
    """Convert WKT POLYGON/MULTIPOLYGON string to GeoJSON geometry object."""
    if not wkt:
        return None
    wkt = wkt.strip()
    try:
        if wkt.startswith("MULTIPOLYGON"):
            # Format: MULTIPOLYGON(((x1 y1, x2 y2, ...)))
            rings = re.findall(r'\(\((.*?)\)\)', wkt)
            coordinates = []
            for ring in rings:
                pts = []
                for pt in ring.split(','):
                    pt_clean = pt.replace('(', '').replace(')', '').strip()
                    parts = pt_clean.split()
                    if len(parts) >= 2:
                        pts.append([float(parts[0]), float(parts[1])])
                if pts:
                    coordinates.append([pts])
            return {"type": "MultiPolygon", "coordinates": coordinates} if coordinates else None

        elif wkt.startswith("POLYGON"):
            # Format: POLYGON((x1 y1, x2 y2, ...))
            rings = re.findall(r'\((.*?)\)', wkt)
            coordinates = []
            for ring in rings:
                pts = []
                for pt in ring.split(','):
                    pt_clean = pt.replace('(', '').replace(')', '').strip()
                    parts = pt_clean.split()
                    if len(parts) >= 2:
                        pts.append([float(parts[0]), float(parts[1])])
                if pts:
                    coordinates.append(pts)
            return {"type": "Polygon", "coordinates": coordinates} if coordinates else None
    except Exception as e:
        logger.error("WKT parse error: %s", e)
    return None


class LandMapClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,bn;q=0.7",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/"
        })
        self.csrf_token = None
        self._init_session()

    def _init_session(self):
        """Fetch main page to initialize CSRF token and Laravel session cookies."""
        try:
            r = self.session.get(f"{BASE_URL}/", timeout=12)
            meta_match = re.search(r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', r.text, re.I)
            if meta_match:
                self.csrf_token = meta_match.group(1)
            else:
                input_match = re.search(r'name=["\']_token["\']\s+value=["\']([^"\']+)["\']', r.text, re.I)
                if input_match:
                    self.csrf_token = input_match.group(1)
            if self.csrf_token:
                self.session.headers["X-CSRF-TOKEN"] = self.csrf_token
        except Exception as e:
            logger.error("Failed to initialize LandMapClient CSRF session: %s", e)

    def fetch_admin_hierarchy(self, level="forDist", parent_code="60", division_code=None, district_code=None, thana_code=None):
        """Fetch administrative units (forDiv, forDist, forThana, forMauza) from map.land.gov.bd."""
        if not self.csrf_token:
            self._init_session()

        url = f"{BASE_URL}/getAdminByCode"
        payload = {
            "_token": self.csrf_token or ""
        }

        if level == "forDiv":
            payload["level"] = "forDiv"
            payload["column"] = "division_n"
        elif level == "forDist":
            payload["level"] = "forDist"
            payload["division_code"] = str(division_code or parent_code)
        elif level in ("forThana", "forUpazila"):
            payload["level"] = "forThana"
            if division_code: payload["division_code"] = str(division_code)
            payload["district_code"] = str(district_code or parent_code)
        elif level in ("forMauza", "forMouza"):
            payload["level"] = "forMauza"
            if division_code: payload["division_code"] = str(division_code)
            if district_code: payload["district_code"] = str(district_code)
            payload["thana_code"] = str(thana_code or parent_code)

        try:
            resp = self.session.post(url, data=payload, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            # Normalize response items
            items = []
            if isinstance(data, list):
                for item in data:
                    code = item.get("code") or item.get("district_code") or item.get("thana_code") or item.get("mauza_code") or item.get("id")
                    name_en = item.get("name_en") or item.get("title_en") or item.get("name") or str(code)
                    name_bn = item.get("name_bn") or item.get("title_bn") or name_en
                    items.append({
                        "code": str(code),
                        "name_en": name_en,
                        "name_bn": name_bn,
                        "division_code": item.get("division_code"),
                        "district_code": item.get("district_code"),
                        "thana_code": item.get("thana_code")
                    })
            return items
        except Exception as e:
            logger.error("Error fetching admin hierarchy (%s, %s): %s", level, parent_code, e)
            return []

    def fetch_mouza_geojson(self, mauza_code, table_name="syl_hab", sheet_val="000"):
        """Fetch vector plot polygons for a Mouza and convert to GeoJSON FeatureCollection."""
        if not self.csrf_token:
            self._init_session()

        url = f"{BASE_URL}/getGeomByCode"
        payload = {
            "level": "forSheet",
            "tableName": table_name,
            "mauzaVal": str(mauza_code),
            "sheetVal": str(sheet_val),
            "plotOrLanduse": "plot",
            "_token": self.csrf_token or ""
        }

        try:
            resp = self.session.post(url, data=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            plots = data.get("plots") or []
            features = []

            for p in plots:
                wkt = p.get("geom")
                geom_obj = parse_wkt_geometry(wkt)
                if not geom_obj:
                    continue

                # Calculate center bbox coordinate for pinning
                center_lat, center_lon = None, None
                if geom_obj["type"] == "MultiPolygon" and geom_obj["coordinates"]:
                    first_ring = geom_obj["coordinates"][0][0]
                    lons = [pt[0] for pt in first_ring]
                    lats = [pt[1] for pt in first_ring]
                    center_lon = sum(lons) / len(lons)
                    center_lat = sum(lats) / len(lats)

                features.append({
                    "type": "Feature",
                    "properties": {
                        "plot_no": str(p.get("plot_no_en") or p.get("label") or ""),
                        "label": p.get("label") or "",
                        "mauza_code": str(mauza_code),
                        "jl_no": str(p.get("jl_no_en") or ""),
                        "sheet_no": str(p.get("sht_no_en") or ""),
                        "center_lat": center_lat,
                        "center_lon": center_lon
                    },
                    "geometry": geom_obj
                })

            return {"type": "FeatureCollection", "features": features}

        except Exception as e:
            logger.error("Error fetching mouza vector geometry: %s", e)
            return {"type": "FeatureCollection", "features": []}

    def fetch_plot_info(self, upazila_code="603605", jl_no="003", plot_no="167", table_name="syl_hab", lat=None, lon=None):
        """Fetch spatial plot details by coordinates or plot numbers live from official government map."""
        if not self.csrf_token:
            self._init_session()

        url = f"{BASE_URL}/GetPlotInfo"
        payload = {
            "table": table_name,
            "plot": str(plot_no),
            "sht": "000",
            "jl": str(jl_no).zfill(3),
            "upazila": str(upazila_code),
            "_token": self.csrf_token or ""
        }
        if lat and lon:
            payload["lat"] = str(lat)
            payload["lon"] = str(lon)

        try:
            resp = self.session.post(url, data=payload, timeout=12)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Error fetching plot info: %s", e)
            return None


if __name__ == "__main__":
    client = LandMapClient()
    print("LandMapClient initialized with CSRF Token:", client.csrf_token)
    fc = client.fetch_mouza_geojson("603605413003")
    print("Features parsed:", len(fc["features"]))
