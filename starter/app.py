from flask import Flask, request, jsonify
import logging
import sys

app = Flask(__name__)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
if __name__ == "__main__":
    app.run(port=5000)