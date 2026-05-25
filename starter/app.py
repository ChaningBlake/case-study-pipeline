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
def get_asset_by_id(asset_id):
    logger.info(f"Getting Asset by ID: {asset_id}")
    asset = next(filter(lambda x: x["id"] == asset_id, ASSETS), None)

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
    return

@app.route("/api/jobs/<job_id>/status", methods=["PUT"])
def update_job_status(job_id):
    return

@app.route("/api/stats", methods=["GET"])
def get_stats():
    return

if __name__ == "__main__":
    load_seed_data()
    app.run(port=5000)