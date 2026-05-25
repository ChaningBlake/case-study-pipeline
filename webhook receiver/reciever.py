from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['POST'])
def reciever():
    data = request.json

    if data:
        print(f"Message received: {data}")
        return jsonify({"status": "success"}), 200

    else:
        return jsonify({"error": "No data received"}), 400
    
if __name__ == "__main__":
    app.run(port=5001)