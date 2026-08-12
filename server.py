from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# ==========================================
# Server information
# ==========================================

SERVER_NAME = "ESP Smart Home Cloud Server"
VERSION = "1.0"

# ==========================================
# Device storage
# ==========================================

devices = {}

# ==========================================
# Home page
# ==========================================

@app.route("/")
def home():

    return jsonify({
        "success": True,
        "server": SERVER_NAME,
        "status": "online",
        "version": VERSION,
        "device_count": len(devices)
    })


# ==========================================
# Register ESP8266
# ==========================================

@app.route("/register", methods=["POST"])
def register():

    data = request.get_json(silent=True) or {}

    device_id = data.get("device_id")

    if not device_id:

        return jsonify({
            "success": False,
            "message": "device_id is required"
        }), 400

    devices[device_id] = {

        "device_id": device_id,

        "type": data.get(
            "type",
            "ESP8266"
        ),

        "ip": data.get(
            "ip",
            ""
        ),

        "firmware": data.get(
            "firmware",
            "1.0"
        ),

        "online": True,

        "last_seen":
            datetime.utcnow().isoformat(),

        "command": None
    }

    return jsonify({

        "success": True,

        "message":
            "Device registered successfully",

        "device":
            devices[device_id]
    })


# ==========================================
# Heartbeat
# ==========================================

@app.route("/heartbeat", methods=["POST"])
def heartbeat():

    data = request.get_json(silent=True) or {}

    device_id = data.get("device_id")

    if not device_id:

        return jsonify({
            "success": False,
            "message": "device_id is required"
        }), 400

    if device_id not in devices:

        return jsonify({
            "success": False,
            "message": "Device not registered"
        }), 404

    devices[device_id]["online"] = True

    devices[device_id]["last_seen"] = \
        datetime.utcnow().isoformat()

    if "ip" in data:

        devices[device_id]["ip"] = data["ip"]

    return jsonify({

        "success": True,

        "message":
            "Heartbeat received",

        "device_id":
            device_id
    })


# ==========================================
# Send command to device
# ==========================================

@app.route("/command", methods=["POST"])
def send_command():

    data = request.get_json(silent=True) or {}

    device_id = data.get("device_id")

    command = data.get("command")

    if not device_id:

        return jsonify({
            "success": False,
            "message": "device_id is required"
        }), 400

    if not command:

        return jsonify({
            "success": False,
            "message": "command is required"
        }), 400

    if device_id not in devices:

        return jsonify({
            "success": False,
            "message": "Device not registered"
        }), 404

    allowed_commands = [

        "LIGHT_ON",
        "LIGHT_OFF",
        "FAN_ON",
        "FAN_OFF"

    ]

    if command not in allowed_commands:

        return jsonify({

            "success": False,

            "message":
                "Invalid command",

            "allowed_commands":
                allowed_commands

        }), 400

    devices[device_id]["command"] = command

    return jsonify({

        "success": True,

        "message":
            "Command queued",

        "device_id":
            device_id,

        "command":
            command
    })


# ==========================================
# Get command for ESP8266
# ==========================================

@app.route("/command/<device_id>", methods=["GET"])
def get_command(device_id):

    if device_id not in devices:

        return jsonify({

            "success": False,

            "message":
                "Device not registered"

        }), 404

    command = devices[device_id].get(
        "command"
    )

    # Clear command after sending it
    devices[device_id]["command"] = None

    return jsonify({

        "success": True,

        "device_id":
            device_id,

        "command":
            command
    })


# ==========================================
# Device list
# ==========================================

@app.route("/devices", methods=["GET"])
def device_list():

    return jsonify({

        "success": True,

        "count":
            len(devices),

        "devices":
            list(devices.values())
    })


# ==========================================
# Device status
# ==========================================

@app.route("/device/<device_id>", methods=["GET"])
def device_status(device_id):

    if device_id not in devices:

        return jsonify({

            "success": False,

            "message":
                "Device not registered"

        }), 404

    return jsonify({

        "success": True,

        "device":
            devices[device_id]
    })


# ==========================================
# Run locally
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
