from flask import Flask, request, jsonify
from pathlib import Path
import json
import logging
import sys

app = Flask(__name__)
BASE_DIR = Path(__file__).parents[1] # ../../.

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

ASSETS = []
PLATFORMS = []

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

if __name__ == "__main__":
    load_seed_data()
    app.run(port=5000)