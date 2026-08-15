from flask import Flask, request, jsonify
from datetime import datetime, timezone
import os

app = Flask(__name__)

# ==========================================================
# ESP8266 SMART HOME CLOUD SERVER
# VERSION 2.1
# ==========================================================

SERVER_NAME = "ESP Smart Home Cloud Server"
VERSION = "2.1"


# ==========================================================
# DEVICE DATABASE
# ==========================================================

devices = {}


# ==========================================================
# PENDING COMMANDS
# ==========================================================

commands = {}


# ==========================================================
# CURRENT UTC TIME
# ==========================================================

def current_time():
    return datetime.now(timezone.utc).isoformat()


# ==========================================================
# HOME
# ==========================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "success": True,
        "server": SERVER_NAME,
        "version": VERSION,
        "status": "online",
        "device_count": len(devices)
    })


# ==========================================================
# SERVER STATUS
# ==========================================================

@app.route("/status", methods=["GET"])
def status():

    return jsonify({
        "success": True,
        "server": SERVER_NAME,
        "status": "online",
        "version": VERSION,
        "device_count": len(devices)
    })


# ==========================================================
# REGISTER DEVICE
# ==========================================================

@app.route("/register", methods=["POST"])
def register():

    data = request.get_json(silent=True)

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


    # ------------------------------------------------------
    # NEW DEVICE
    # ------------------------------------------------------

    if device_id not in devices:

        devices[device_id] = {

            "device_id": device_id,

            "type": data.get(
                "type",
                "ESP8266"
            ),

            "ip": data.get(
                "ip",
                "unknown"
            ),

            "firmware": data.get(
                "firmware",
                "unknown"
            ),

            "online": True,

            "light": bool(
                data.get(
                    "light",
                    False
                )
            ),

            "fan": bool(
                data.get(
                    "fan",
                    False
                )
            ),

            "last_seen": current_time()
        }

        commands[device_id] = None

        message = (
            "New device registered successfully"
        )


    # ------------------------------------------------------
    # EXISTING DEVICE
    # ------------------------------------------------------

    else:

        device = devices[device_id]


        if "type" in data:

            device["type"] = data["type"]


        if "ip" in data:

            device["ip"] = data["ip"]


        if "firmware" in data:

            device["firmware"] = data["firmware"]


        if "light" in data:

            device["light"] = bool(
                data["light"]
            )


        if "fan" in data:

            device["fan"] = bool(
                data["fan"]
            )


        device["online"] = True

        device["last_seen"] = current_time()


        if device_id not in commands:

            commands[device_id] = None


        message = (
            "Existing device updated successfully"
        )


    return jsonify({

        "success": True,

        "message": message,

        "device": devices[device_id]

    })


# ==========================================================
# HEARTBEAT
# ==========================================================

@app.route("/heartbeat", methods=["POST"])
def heartbeat():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({

            "success": False,

            "message": (
                "No JSON data received"
            )

        }), 400


    device_id = data.get(
        "device_id"
    )


    if not device_id:

        return jsonify({

            "success": False,

            "message": (
                "device_id is required"
            )

        }), 400


    # ------------------------------------------------------
    # UNKNOWN DEVICE
    # ------------------------------------------------------

    if device_id not in devices:

        devices[device_id] = {

            "device_id": device_id,

            "type": data.get(
                "type",
                "ESP8266"
            ),

            "ip": data.get(
                "ip",
                "unknown"
            ),

            "firmware": data.get(
                "firmware",
                "unknown"
            ),

            "online": True,

            "light": bool(
                data.get(
                    "light",
                    False
                )
            ),

            "fan": bool(
                data.get(
                    "fan",
                    False
                )
            ),

            "last_seen": current_time()
        }

        commands[device_id] = None


    # ------------------------------------------------------
    # EXISTING DEVICE
    # ------------------------------------------------------

    else:

        device = devices[device_id]


        device["online"] = True

        device["last_seen"] = current_time()


        if "ip" in data:

            device["ip"] = data["ip"]


        if "type" in data:

            device["type"] = data["type"]


        if "firmware" in data:

            device["firmware"] = data["firmware"]


        if "light" in data:

            device["light"] = bool(
                data["light"]
            )


        if "fan" in data:

            device["fan"] = bool(
                data["fan"]
            )


    return jsonify({

        "success": True,

        "message": "Heartbeat received",

        "device_id": device_id,

        "online": True

    })


# ==========================================================
# GET ALL DEVICES
# ==========================================================

@app.route("/devices", methods=["GET"])
def get_devices():

    return jsonify({

        "success": True,

        "count": len(devices),

        "devices": list(
            devices.values()
        )

    })


# ==========================================================
# GET ONE DEVICE
# ==========================================================

@app.route(
    "/device/<device_id>",
    methods=["GET"]
)
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


# ==========================================================
# SEND COMMAND TO DEVICE
# ==========================================================

@app.route(
    "/command",
    methods=["POST"]
)
def send_command():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify({

            "success": False,

            "message": (
                "No JSON data received"
            )

        }), 400


    device_id = data.get(
        "device_id"
    )

    command = data.get(
        "command"
    )


    if not device_id:

        return jsonify({

            "success": False,

            "message": (
                "device_id is required"
            )

        }), 400


    if not command:

        return jsonify({

            "success": False,

            "message": (
                "command is required"
            )

        }), 400


    # ------------------------------------------------------
    # ALLOWED COMMANDS
    # ------------------------------------------------------

    allowed_commands = [

        "LIGHT_ON",

        "LIGHT_OFF",

        "FAN_ON",

        "FAN_OFF"

    ]


    if command not in allowed_commands:

        return jsonify({

            "success": False,

            "message": "Invalid command"

        }), 400


    # ------------------------------------------------------
    # CHECK DEVICE
    # ------------------------------------------------------

    if device_id not in devices:

        return jsonify({

            "success": False,

            "message": "Device not found"

        }), 404


    # ------------------------------------------------------
    # STORE COMMAND
    # ------------------------------------------------------

    commands[device_id] = command


    return jsonify({

        "success": True,

        "message": "Command queued",

        "device_id": device_id,

        "command": command

    })


# ==========================================================
# ESP8266 CHECKS FOR COMMAND
# ==========================================================

@app.route(
    "/command",
    methods=["GET"]
)
def get_command():

    device_id = request.args.get(
        "device_id"
    )


    if not device_id:

        return jsonify({

            "success": False,

            "message": (
                "device_id is required"
            )

        }), 400


    # ------------------------------------------------------
    # CHECK DEVICE
    # ------------------------------------------------------

    if device_id not in devices:

        return jsonify({

            "success": False,

            "message": "Device not found"

        }), 404


    # ------------------------------------------------------
    # GET COMMAND
    # ------------------------------------------------------

    command = commands.get(
        device_id
    )


    # ------------------------------------------------------
    # NO COMMAND
    # ------------------------------------------------------

    if command is None:

        return jsonify({

            "success": True,

            "device_id": device_id,

            "command": None

        })


    # ------------------------------------------------------
    # DELIVER COMMAND
    # ------------------------------------------------------

    current_command = command


    # Remove command after delivery
    commands[device_id] = None


    return jsonify({

        "success": True,

        "device_id": device_id,

        "command": current_command

    })


# ==========================================================
# MARK DEVICE OFFLINE
# ==========================================================

@app.route(
    "/device/<device_id>/offline",
    methods=["POST"]
)
def mark_offline(device_id):

    if device_id not in devices:

        return jsonify({

            "success": False,

            "message": "Device not found"

        }), 404


    devices[device_id]["online"] = False


    return jsonify({

        "success": True,

        "message": "Device marked offline",

        "device_id": device_id

    })


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )


    print(
        "======================================"
    )

    print(
        " ESP8266 SMART HOME SERVER"
    )

    print(
        " VERSION 2.1"
    )

    print(
        "======================================"
    )

    print(
        "Server starting..."
    )

    print(
        "Port:",
        port
    )


    app.run(

        host="0.0.0.0",

        port=port

    )
