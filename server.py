from flask import Flask, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)

devices = {}


@app.route("/")
def home():
    return "ESP8266 Smart Home Server is running!"


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "success": True,
        "server": "ESP Smart Home Cloud Server",
        "status": "online",
        "version": "1.0",
        "device_count": len(devices)
    })


@app.route("/register", methods=["POST"])
def register():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "No JSON data received"
        }), 400

    device_id = data.get("device_id")

    if not device_id:
        return jsonify({
            "success": False,
            "message": "device_id is required"
        }), 400

    devices[device_id] = {
        "device_id": device_id,
        "type": data.get("type", "unknown"),
        "ip": data.get("ip", "unknown"),
        "firmware": data.get("firmware", "unknown"),
        "online": True,
        "last_seen": datetime.now().isoformat()
    }

    return jsonify({
        "success": True,
        "message": "Device registered successfully",
        "device": devices[device_id]
    })


@app.route("/heartbeat", methods=["POST"])
def heartbeat():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "No JSON data received"
        }), 400

    device_id = data.get("device_id")

    if not device_id:
        return jsonify({
            "success": False,
            "message": "device_id is required"
        }), 400

    if device_id not in devices:
        devices[device_id] = {
            "device_id": device_id,
            "type": data.get("type", "unknown"),
            "ip": data.get("ip", "unknown"),
            "firmware": data.get("firmware", "unknown"),
            "online": True,
            "last_seen": datetime.now().isoformat()
        }
    else:
        devices[device_id]["online"] = True
        devices[device_id]["last_seen"] = datetime.now().isoformat()

        if "ip" in data:
            devices[device_id]["ip"] = data["ip"]

    return jsonify({
        "success": True,
        "message": "Heartbeat received",
        "device_id": device_id
    })


@app.route("/devices", methods=["GET"])
def get_devices():

    return jsonify({
        "success": True,
        "count": len(devices),
        "devices": list(devices.values())
    })


@app.route("/device/<device_id>", methods=["GET"])
def get_device(device_id):

    if device_id not in devices:
        return jsonify({
            "success": False,
            "message": "Device not found"
        }), 404

    return jsonify({
        "success": True,
        "device": devices[device_id]
    })


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    print("======================================")
    print(" ESP8266 SMART HOME SERVER")
    print("======================================")
    print("Server starting...")

    app.run(
        host="0.0.0.0",
        port=port
    )