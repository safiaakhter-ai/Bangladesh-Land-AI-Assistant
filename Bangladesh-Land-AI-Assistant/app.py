"""Bangladesh Land AI Assistant API.

Local-first Flask service for documented land-record searches, grounded knowledge,
chat history, and optional digital map integrations. Never treats an unavailable
record source as evidence of ownership or the absence of a legal record.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import re
import sqlite3
import threading
import time
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE development configuration without extra dependencies."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT / ".env")
DATA_DIR = Path(os.getenv("LAND_DATA_DIR", str(ROOT / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("LAND_CHAT_DB", str(DATA_DIR / "chat_history.db"))
KHATIAN_DB = Path(os.getenv("KHATIAN_DB_PATH", str(DATA_DIR / "khatians.db"))).resolve()
SCRAPER_DB = Path(os.getenv("SCRAPER_DB_PATH", str(DATA_DIR / "dlrms_records.db"))).resolve()
SCRAPER_STATE = DATA_DIR / "scraper_state.json"
SCRAPER_LOG = DATA_DIR / "dlrms_scraper.log"
ADMIN_TOKEN = os.getenv("ADMIN_API_TOKEN", "")
SCRAPER_ENABLED = os.getenv("ENABLE_SCRAPER", "false").lower() == "true"
SCRAPER_SOURCE_URL = os.getenv("DLRMS_SOURCE_URL", "")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("land_ai")

app = Flask(__name__)
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

import chat_db  # noqa: E402  - configured data path before import
from rag_engine import LandRecordRAG  # noqa: E402

rag_engine_instance = LandRecordRAG(db_path=str(KHATIAN_DB))
chat_db.init_chat_db()

_scraper_lock = threading.Lock()
_scraper_status = "idle"
_scraper_error = None
_active_scraper = None
_telemetry_cache = {}
_telemetry_time = 0.0
_telemetry_lock = threading.Lock()


def safe_int(name: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(request.args.get(name, default))))
    except (ValueError, TypeError):
        return default


def api_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def admin_allowed() -> bool:
    supplied = request.headers.get("X-Admin-Token", "")
    return bool(ADMIN_TOKEN and hmac.compare_digest(supplied, ADMIN_TOKEN))


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def db_count(path: Path, table: str) -> int:
    if not path.is_file():
        return 0
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if table_exists(conn, table) else 0
    except (sqlite3.Error, OSError) as exc:
        logger.warning("Cannot read %s stats: %s", table, exc)
        return 0


def db_stats() -> dict:
    return {
        "survey_count": db_count(SCRAPER_DB, "survey_records"),
        "namjari_count": db_count(SCRAPER_DB, "namjari_records"),
        "maps_count": db_count(SCRAPER_DB, "mouza_maps"),
        "db_size_kb": round(SCRAPER_DB.stat().st_size / 1024, 1) if SCRAPER_DB.is_file() else 0,
    }


def scraper_state() -> dict:
    default = {
        "survey": {"division": None, "district": None, "upazila": None, "khatian_type": None, "mouza": None},
        "namjari": {"division": None, "district": None, "upazila": None, "mouza": None},
    }
    try:
        return json.loads(SCRAPER_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def get_telemetry() -> dict:
    """Use only actual on-disk measurements; no fictional national scrape counts."""
    global _telemetry_cache, _telemetry_time
    with _telemetry_lock:
        if _telemetry_cache and time.monotonic() - _telemetry_time < 60:
            return _telemetry_cache.copy()
        has_db = KHATIAN_DB.is_file()
        result = {
            "database_connected": has_db,
            "index_khatians_count": db_count(KHATIAN_DB, "khatian_index"),
            "saved_details_count": db_count(KHATIAN_DB, "khatian_details"),
            "mouzas_completed": None,
            "total_mouzas": None,
            "survey_breakdown": {},
            "source": "local_database" if has_db else "not_configured",
        }
        if has_db:
            try:
                with sqlite3.connect(f"file:{KHATIAN_DB}?mode=ro", uri=True, timeout=3) as conn:
                    if table_exists(conn, "khatian_index"):
                        cols = {r[1] for r in conn.execute("PRAGMA table_info(khatian_index)")}
                        if "survey_name" in cols:
                            result["survey_breakdown"] = dict(conn.execute("SELECT survey_name, COUNT(*) FROM khatian_index GROUP BY survey_name"))
            except sqlite3.Error as exc:
                logger.warning("Telemetry breakdown failed: %s", exc)
        _telemetry_cache = result
        _telemetry_time = time.monotonic()
        return result.copy()


@app.after_request
def response_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/chats") else "no-cache"
    return response


@app.errorhandler(413)
def request_too_large(_):
    return api_error("Request body exceeds 64 KB.", 413)


@app.route("/")
def home():
    return jsonify({"name": "Bangladesh Land AI Assistant", "api": "/api/health", "frontend": "http://localhost:3000"})


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "land-ai-api",
        "record_database": "available" if KHATIAN_DB.is_file() else "not_configured",
        "ai_provider": "gemini" if os.getenv("GEMINI_API_KEY") else "offline_knowledge_base",
        "map_provider": "external_optional",
    })


@app.route("/api/telemetry")
def telemetry():
    return jsonify(get_telemetry())


@app.route("/api/status")
def status():
    return jsonify({"status": _scraper_status, "error": _scraper_error, "stats": db_stats(), "state": scraper_state(), "enabled": SCRAPER_ENABLED})


def scraper_worker(task_type: str, headless: bool):
    global _scraper_status, _scraper_error, _active_scraper
    try:
        from dlrms_scraper import DLRMSScraper
        _active_scraper = DLRMSScraper(db_path=str(SCRAPER_DB), headless=headless)
        if not _active_scraper.init_driver():
            raise RuntimeError("Chrome WebDriver could not be initialized")
        _scraper_status = f"scraping_{task_type}"
        handler = {"survey": _active_scraper.scrape_survey_section, "namjari": _active_scraper.scrape_namjari_section, "maps": _active_scraper.scrape_mouza_map_section}[task_type]
        handler()
        _active_scraper.export_to_json(output_dir=str(DATA_DIR / "exports"))
    except Exception as exc:
        _scraper_error = str(exc)
        logger.exception("Scraper job failed")
    finally:
        if _active_scraper:
            _active_scraper.close()
        _active_scraper = None
        with _scraper_lock:
            _scraper_status = "idle"


def scraper_access_error():
    if not SCRAPER_ENABLED:
        return api_error("Scraper is disabled. See README for optional, authorized setup.", 403)
    if not admin_allowed():
        return api_error("Admin token required.", 403)
    if not SCRAPER_SOURCE_URL.startswith("https://"):
        return api_error("A verified HTTPS DLRMS_SOURCE_URL must be configured.", 503)
    return None


@app.route("/api/start", methods=["POST"])
def start_scraper():
    global _scraper_status, _scraper_error
    denied = scraper_access_error()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    task_type = body.get("task_type", "survey")
    if task_type not in {"survey", "namjari", "maps"}:
        return api_error("Invalid task type")
    with _scraper_lock:
        if _scraper_status != "idle":
            return api_error("A scraper job is already running.", 409)
        _scraper_status, _scraper_error = f"starting_{task_type}", None
    threading.Thread(target=scraper_worker, args=(task_type, bool(body.get("headless", True))), daemon=True).start()
    return jsonify({"status": "started", "task": task_type}), 202


@app.route("/api/stop", methods=["POST"])
def stop_scraper():
    global _scraper_status
    denied = scraper_access_error()
    if denied:
        return denied
    if _active_scraper is None:
        return api_error("No active scraper job.", 409)
    _active_scraper.stop_requested = True
    _scraper_status = "stopping"
    return jsonify({"status": "stopping"})


@app.route("/api/reset", methods=["POST"])
def reset_progress():
    denied = scraper_access_error()
    if denied:
        return denied
    if _scraper_status != "idle":
        return api_error("Cannot reset a running job.", 409)
    SCRAPER_STATE.write_text(json.dumps({"survey": {"division": None, "district": None, "upazila": None, "khatian_type": None, "mouza": None}, "namjari": {"division": None, "district": None, "upazila": None, "mouza": None}}, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"status": "reset"})


@app.route("/api/logs")
def logs():
    if not admin_allowed():
        return api_error("Admin token required.", 403)
    if not SCRAPER_LOG.is_file():
        return jsonify([])
    with SCRAPER_LOG.open(encoding="utf-8", errors="replace") as stream:
        return jsonify(list(deque(stream, maxlen=safe_int("limit", 80, 1, 300))))


@app.route("/api/data/<table_name>")
def legacy_data(table_name):
    searchable = {
        "survey_records": ["mauza", "sheet_number", "dag_number", "owner_name", "record_content"],
        "namjari_records": ["mauza", "khatian_number", "dag_number", "from_name", "to_name", "record_content"],
        "mouza_maps": ["district", "upazila", "mauza", "map_data"],
    }
    if table_name not in searchable:
        return api_error("Invalid record type.")
    if not SCRAPER_DB.is_file():
        return jsonify({"records": [], "total": 0})
    page = safe_int("page", 1, 1, 100000)
    per_page = safe_int("per_page", 10, 1, 100)
    term = request.args.get("search", "")[:150]
    try:
        with sqlite3.connect(f"file:{SCRAPER_DB}?mode=ro", uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            if not table_exists(conn, table_name):
                return jsonify({"records": [], "total": 0})
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
            fields = [x for x in searchable[table_name] if x in cols]
            where = " WHERE " + " OR ".join(f"{field} LIKE ?" for field in fields) if term and fields else ""
            args = [f"%{term}%"] * len(fields) if where else []
            total = conn.execute(f"SELECT COUNT(*) FROM {table_name}{where}", args).fetchone()[0]
            rows = conn.execute(f"SELECT * FROM {table_name}{where} ORDER BY id DESC LIMIT ? OFFSET ?", args + [per_page, (page-1)*per_page]).fetchall()
            return jsonify({"records": [dict(x) for x in rows], "total": total})
    except sqlite3.Error:
        logger.exception("Record search failed")
        return api_error("Record store is temporarily unavailable.", 503)


@app.route("/api/khatians/search")
def search_khatians():
    query = request.args.get("q", "").strip()[:200]
    page = safe_int("page", 1, 1, 1000)
    per_page = safe_int("per_page", 12, 1, 40)
    if not KHATIAN_DB.is_file() or not query:
        return jsonify({"records": [], "total": 0, "page": page, "per_page": per_page, "record_database_available": KHATIAN_DB.is_file()})
    params = rag_engine_instance.extract_search_params(query)
    if not any(params.values()):
        params["mouza"] = query
    # The upstream RAG search is bounded; report bounded matches rather than an invented total.
    cap = min(500, page * per_page + per_page)
    records, err = rag_engine_instance.search_records(params, limit=cap)
    if err:
        logger.warning("Record query returned: %s", err)
    return jsonify({
        "records": records[(page-1)*per_page:page*per_page],
        "total": len(records),
        "total_is_estimate": len(records) >= cap,
        "page": page,
        "per_page": per_page,
        "record_database_available": True,
    })


@app.route("/api/chats", methods=["GET", "POST"])
def chats():
    if request.method == "GET":
        return jsonify(chat_db.get_all_sessions())
    body = request.get_json(silent=True) or {}
    title = str(body.get("title") or "নতুন তথ্য অনুসন্ধান")[:100]
    session_id = chat_db.create_session(title)
    return jsonify({"session_id": session_id, "title": title}), 201


@app.route("/api/chats/<session_id>", methods=["GET", "DELETE"])
def chat_session(session_id):
    if not re.fullmatch(r"[a-zA-Z0-9-]{1,64}", session_id):
        return api_error("Invalid conversation identifier")
    if request.method == "DELETE":
        chat_db.delete_session(session_id)
        return jsonify({"status": "deleted", "session_id": session_id})
    return jsonify(chat_db.get_session_messages(session_id))


@app.route("/api/chats/<session_id>/message", methods=["POST"])
def chat_message(session_id):
    if not re.fullmatch(r"[a-zA-Z0-9-]{1,64}", session_id):
        return api_error("Invalid conversation identifier")
    body = request.get_json(silent=True) or {}
    query = body.get("message", "")
    if not isinstance(query, str) or not query.strip():
        return api_error("Message cannot be empty")
    if len(query) > 2500:
        return api_error("Message is too long (max 2,500 characters)")
    chat_db.add_message(session_id, sender="user", content=query.strip())
    history = chat_db.get_session_messages(session_id)[-16:]
    try:
        result = rag_engine_instance.process_query(query.strip(), conversation_history=history)
    except Exception:
        logger.exception("RAG processing error")
        return api_error("Assistant temporarily unavailable. Your message was saved; please retry.", 503)
    metadata = {k: result.get(k) for k in ["is_out_of_scope", "clarification_options", "extracted_params", "records_found", "records"]}
    chat_db.add_message(session_id, sender="ai", content=result["answer"], metadata=metadata)
    return jsonify({"sender": "ai", "content": result["answer"], "metadata": metadata})


@app.route("/api/map-admin")
def map_admin():
    level = request.args.get("level", "forDist")
    if level not in {"forDiv", "forDist", "forThana", "forMauza"}:
        return api_error("Invalid map hierarchy level")
    args = {key: request.args.get(key, "")[:32] for key in ["parent_code", "division_code", "district_code", "thana_code"]}
    if not all(re.fullmatch(r"[0-9a-zA-Z_-]*", value) for value in args.values()):
        return api_error("Invalid administrative code")
    try:
        from land_map_client import LandMapClient
        client = LandMapClient()
        items = client.fetch_admin_hierarchy(level=level, parent_code=args["parent_code"] or "60", division_code=args["division_code"], district_code=args["district_code"], thana_code=args["thana_code"])
        return jsonify({"level": level, "items": items or [], "source": "external_map_service"})
    except Exception:
        logger.exception("Map hierarchy integration failed")
        return api_error("Map service temporarily unavailable.", 503)


@app.route("/api/plot-geometry")
def plot_geometry():
    code = request.args.get("mauza_code", request.args.get("mauza", ""))[:64]
    plot = request.args.get("plot", "")[:32]
    if code and not re.fullmatch(r"[a-zA-Z0-9_-]+", code):
        return api_error("Invalid mouza code")
    if plot and not re.fullmatch(r"[0-9\u09e6-\u09ef/-]+", plot):
        return api_error("Invalid plot number")
    features = []
    if KHATIAN_DB.is_file():
        try:
            with sqlite3.connect(f"file:{KHATIAN_DB}?mode=ro", uri=True, timeout=3) as conn:
                if table_exists(conn, "plot_spatial_info") and table_exists(conn, "plot_polygons"):
                    wheres, values = [], []
                    if code:
                        wheres.append("s.mauza_code = ?")
                        values.append(code)
                    if plot:
                        wheres.append("s.plot_no = ?")
                        values.append(plot)
                    where = " WHERE " + " AND ".join(wheres) if wheres else ""
                    query = ("SELECT s.mauza_code, s.plot_no, s.major_class, s.sub_class, "
                             "s.landuse_zone, s.center_lat, s.center_lon, p.geojson_geometry "
                             "FROM plot_spatial_info s LEFT JOIN plot_polygons p "
                             "ON s.mauza_code = p.mauza_code AND s.plot_no = p.plot_no " + where + " LIMIT 250")
                    for row in conn.execute(query, values):
                        if row[7]:
                            features.append({"type": "Feature", "properties": dict(zip(["mauza_code", "plot_no", "major_class", "sub_class", "landuse_zone", "center_lat", "center_lon"], row[:7])), "geometry": json.loads(row[7])})
        except (sqlite3.Error, json.JSONDecodeError):
            logger.exception("Local plot geometry lookup failed")
    if not features and code:
        try:
            from land_map_client import LandMapClient
            features = (LandMapClient().fetch_mouza_geojson(mauza_code=code).get("features") or [])[:250]
        except Exception:
            logger.warning("Map provider not available for mouza %s", code)
    return jsonify({"type": "FeatureCollection", "features": features, "source": "local_or_external_unverified"})


@app.route("/api/reverse-geocode-plot", methods=["POST"])
def reverse_geocode_plot():
    body = request.get_json(silent=True) or {}
    try:
        lat = float(body["lat"])
        lon = float(body["lon"])
    except (ValueError, TypeError, KeyError):
        return api_error("Valid latitude and longitude are required")
    if not 20 <= lat <= 27 or not 88 <= lon <= 94:
        return api_error("Coordinates must be within the approximate bounds of Bangladesh")
    sid = str(body.get("session_id") or "")
    if not re.fullmatch(r"[a-zA-Z0-9-]{1,64}", sid):
        return api_error("Valid session_id required")
    prompt = str(body.get("custom_prompt") or f"Map location ({lat:.5f}, {lon:.5f})")[:1000]
    extra = {key: str(body.get(key) or "")[:120] for key in ["mauza_code", "plot_no", "district_name", "upazila_name", "mouza_name"]}
    try:
        result = rag_engine_instance.process_spatial_location_query(lat, lon, conversation_history=chat_db.get_session_messages(sid)[-16:], custom_prompt=prompt, **extra)
    except Exception:
        logger.exception("Spatial query failed")
        return api_error("Could not analyze the location.", 503)
    chat_db.add_message(sid, sender="user", content=prompt)
    chat_db.add_message(sid, sender="ai", content=result["answer"], metadata=result)
    return jsonify(result)


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    logger.info("Land AI API: http://%s:%s (frontend: http://localhost:3000)", host, port)
    app.run(host=host, port=port, debug=False, threaded=True)
