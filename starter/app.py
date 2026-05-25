from flask import Flask, request, jsonify
from pathlib import Path
import json
import logging
import sys
from uuid import uuid4
from datetime import datetime, timezone

app = Flask(__name__)
BASE_DIR = Path(__file__).parents[1] # ../../.

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

ASSETS = []
PLATFORMS = []
DELIVERY_JOBS = []

# --- HElPER FUNCTIONS ---
def load_seed_data():
    logger.info("Loading seed data")
    try:
        with open(BASE_DIR / "data" / "assets_seed.json") as f:
            ASSETS.extend(json.load(f))
        
        with open(BASE_DIR / "data" / "platforms.json") as f:
            PLATFORMS.extend(json.load(f))

    except Exception as e:
        logger.error(f"Error loading seed data: {str(e)}")
        raise e

def filter_assets(assets, status, territory, search):
    result = assets
    if status:
        result = [asset for asset in result 
            if asset["status"] == status
        ]
    if territory:
        result = [asset for asset in result
            if asset["territory"] == territory
        ]
    if search:
        result = [asset for asset in result
            if search in asset["title"].lower()
        ]
    return result

def get_missing_fields(asset):
    required_fields = set(["title", "format", "codec", "resolution", "duration_sec", "file_size_gb", "territory", "languages", "has_captions"])
    missing_fields = []
    for field in required_fields:
        if field not in asset:
            missing_fields.append(field)
    return missing_fields

def build_asset(asset):
    asset["id"] = str(uuid4())
    asset["status"] = "ingested"

    now = get_timestamp()
    asset["created_at"] = now
    asset["updated_at"] = now

    return asset

def get_timestamp():
    return datetime.now(timezone.utc).isoformat()

def create_skip(reason, platform):
    return {
        "platform_id": platform.get("id"),
        "platform_name": platform.get("name"),
        "reason": reason
    }

def is_resolution_compatible(asset, platform):
    res_map = {
        "4K": 3,
        "1080p": 2,
        "720p": 1
    }

    # Not a valid resolution
    if asset["resolution"] not in res_map:
        logger.warning(f"{asset['resolution']} is not a valid resolution")
        return False

    return res_map[asset["resolution"]] <= res_map[platform["max_resolution"]]

def territory_is_valid(asset, platform):
    return asset["territory"] == "GLOBAL" \
        or "GLOBAL" in platform["territories"] \
        or asset["territory"] in platform["territories"]

def get_platform_matches(asset):
    matches = []
    skips = []
    
    for platform in PLATFORMS:
        # Only append first failing rule
        if asset["format"] not in platform["accepted_formats"]:
            skips.append(create_skip(
                f"Format {asset['format']} not accepted (platform requires {platform['accepted_formats']})",
                platform
            ))
            continue
        if not is_resolution_compatible(asset, platform):
            skips.append(create_skip(
                f"Resolution {asset['resolution']} not accepted (platform supports a max resolution of {platform['max_resolution']})",
                platform
            ))
            continue
        if platform["requires_captions"] and not asset["has_captions"]:
            skips.append(create_skip(
                f"Platform requires captions",
                platform
            ))
            continue
        if not territory_is_valid(asset, platform):
            skips.append(create_skip(
                f"Territory {asset['territory']} not accepted (platform requires {platform['territories']})",
                platform
            ))
            continue

        # Asset is compatible with platform
        matches.append(platform["id"])
    return matches, skips

def create_delivery_job(asset_id, platform_id):
    now = get_timestamp()
    job = {
        "id": str(uuid4()),
        "asset_id": asset_id,
        "platform_id": platform_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now
    }

    DELIVERY_JOBS.append(job)
    return job["id"] 

def get_asset_by_id(asset_id):
    return next(filter(lambda x: x["id"] == asset_id, ASSETS), None)

# --- ROUTES ---
@app.route("/api/assets", methods=["GET"])
def get_assets():
    logger.info("Retrieving assets")

    # Get query params
    status = request.args.get('status')
    territory = request.args.get('territory')
    search = request.args.get('search')

    assets = filter_assets(ASSETS, status, territory, search)

    return jsonify({"assets": assets, "total": len(assets)}), 200

@app.route("/api/assets/<asset_id>", methods=["GET"])
def get_asset(asset_id):
    logger.info(f"Getting Asset by ID: {asset_id}")
    asset = get_asset_by_id(asset_id)

    if asset:
        return jsonify({"asset": asset}), 200
    else:
        return jsonify({"error": "Asset not found"}), 404

@app.route("/api/assets", methods=["POST"])
def register_asset():
    body = request.get_json()

    missing_fields = get_missing_fields(body) 
    if missing_fields:
        return jsonify({"missing_fields": missing_fields}), 400

    if body.get("has_captions") and not body.get("caption_format"):
        return jsonify({"error": "has_captions is True but caption_format is not present"}), 400

    asset = build_asset(body)
    ASSETS.append(asset)
    return jsonify(asset), 201

@app.route("/api/assets/<asset_id>/route", methods=["POST"])
def route_asset(asset_id):
    asset = get_asset_by_id(asset_id)
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
    if asset.get("status") != "qc_passed":
        return jsonify({"error": "Asset must have status 'qc_passed' to be routed"}), 400

    jobs = []   
    matches, skips = get_platform_matches(asset)
    for match in matches:
        jobs.append(create_delivery_job(asset_id, platform_id=match))
    
    return jsonify({"jobs": jobs, "platforms_matched": len(matches), "platforms_skipped": skips}), 200

@app.route("/api/jobs/<job_id>/status", methods=["PUT"])
def update_job_status(job_id):
    return

@app.route("/api/stats", methods=["GET"])
def get_stats():
    return

if __name__ == "__main__":
    load_seed_data()
    app.run(port=5000)