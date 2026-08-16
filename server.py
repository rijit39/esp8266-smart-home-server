from flask import Flask, request, jsonify
from datetime import datetime, timezone
import os

app = Flask(__name__)


# ==========================================================
# SERVER VERSION
# ==========================================================

SERVER_VERSION = "2.1"


# ==========================================================
# DEVICE OFFLINE TIMEOUT
# ==========================================================
# If the ESP does not send a heartbeat within this time,
# the server considers it OFFLINE.
#
# We use 30 seconds.
# ==========================================================

OFFLINE_TIMEOUT_SECONDS = 30


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

def current_datetime():
    return datetime.now(timezone.utc)


def current_time():
    return current_datetime().isoformat()


# ==========================================================
# UPDATE DEVICE ONLINE STATUS
# ==========================================================

def update_online_status(device):

    try:

        last_seen_text = device.get("last_seen")

        if not last_seen_text:
            device["online"] = False
            return False

        last_seen = datetime.fromisoformat(
            last_seen_text
        )

        # Make sure timezone exists
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(
                tzinfo=timezone.utc
            )

        age = (
            current_datetime() - last_seen
        ).total_seconds()

        if age > OFFLINE_TIMEOUT_SECONDS:

            device["online"] = False

            # Remove any old command when device goes offline
            device_id = device.get("device_id")

            if device_id in commands:
                commands[device_id] = None

            return False

        else:

            device["online"] = True
            return True

    except Exception as e:

        print(
            "Online status error:",
            e
        )

        device["online"] = False

        return False


# ==========================================================
# UPDATE ALL DEVICE STATUSES
# ==========================================================

def update_all_online_status():

    for device in devices.values():

        update_online_status(device)


# ==========================================================
# HOME
# ==========================================================

@app.route("/", methods=["GET"])
def home():

    update_all_online_status()

    online_count = sum(
        1
        for device in devices.values()
        if device.get("online") is True
    )

    return jsonify({

        "success": True,

        "server":
            "ESP8266 Smart Home Cloud Server",

        "version":
            SERVER_VERSION,

        "status":
            "online",

        "device_count":
            len(devices),

        "online_devices":
            online_count
    })


# ==========================================================
# SERVER STATUS
# ==========================================================

@app.route("/status", methods=["GET"])
def status():

    update_all_online_status()

    online_count = sum(
        1
        for device in devices.values()
        if device.get("online") is True
    )

    return jsonify({

        "success": True,

        "server":
            "ESP Smart Home Cloud Server",

        "status":
            "online",

        "version":
            SERVER_VERSION,

        "device_count":
            len(devices),

        "online_devices":
            online_count
    })


# ==========================================================
# REGISTER DEVICE
# ==========================================================

@app.route("/register", methods=["POST"])
def register():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({

            "success": False,

            "message":
                "No JSON data received"

        }), 400


    device_id = data.get(
        "device_id"
    )


    if not device_id:

        return jsonify({

            "success": False,

            "message":
                "device_id is required"

        }), 400


    # ------------------------------------------------------
    # NEW DEVICE
    # ------------------------------------------------------

    if device_id not in devices:

        devices[device_id] = {

            "device_id":
                device_id,

            "type":
                data.get(
                    "type",
                    "ESP8266"
                ),

            "ip":
                data.get(
                    "ip",
                    "unknown"
                ),

            "firmware":
                data.get(
                    "firmware",
                    "unknown"
                ),

            "online":
                True,

            "light":
                bool(
                    data.get(
                        "light",
                        False
                    )
                ),

            "fan":
                bool(
                    data.get(
                        "fan",
                        False
                    )
                ),

            "last_seen":
                current_time()
        }


        commands[device_id] = None


        message = (
            "New device registered successfully"
        )


    # ------------------------------------------------------
    # EXISTING DEVICE
    # ------------------------------------------------------

    else:

        device = devices[
            device_id
        ]


        if "type" in data:

            device["type"] = data[
                "type"
            ]


        if "ip" in data:

            device["ip"] = data[
                "ip"
            ]


        if "firmware" in data:

            device["firmware"] = data[
                "firmware"
            ]


        if "light" in data:

            device["light"] = bool(
                data["light"]
            )


        if "fan" in data:

            device["fan"] = bool(
                data["fan"]
            )


        device["online"] = True

        device["last_seen"] = (
            current_time()
        )


        if device_id not in commands:

            commands[device_id] = None


        message = (
            "Existing device updated successfully"
        )


    return jsonify({

        "success": True,

        "message":
            message,

        "device":
            devices[device_id]
    })


# ==========================================================
# HEARTBEAT
# ==========================================================

@app.route(
    "/heartbeat",
    methods=["POST"]
)
def heartbeat():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify({

            "success": False,

            "message":
                "No JSON data received"

        }), 400


    device_id = data.get(
        "device_id"
    )


    if not device_id:

        return jsonify({

            "success": False,

            "message":
                "device_id is required"

        }), 400


    # ------------------------------------------------------
    # UNKNOWN DEVICE
    # ------------------------------------------------------

    if device_id not in devices:

        devices[device_id] = {

            "device_id":
                device_id,

            "type":
                data.get(
                    "type",
                    "ESP8266"
                ),

            "ip":
                data.get(
                    "ip",
                    "unknown"
                ),

            "firmware":
                data.get(
                    "firmware",
                    "unknown"
                ),

            "online":
                True,

            "light":
                bool(
                    data.get(
                        "light",
                        False
                    )
                ),

            "fan":
                bool(
                    data.get(
                        "fan",
                        False
                    )
                ),

            "last_seen":
                current_time()
        }


        commands[device_id] = None


    # ------------------------------------------------------
    # EXISTING DEVICE
    # ------------------------------------------------------

    else:

        device = devices[
            device_id
        ]


        device["online"] = True


        device["last_seen"] = (
            current_time()
        )


        if "ip" in data:

            device["ip"] = data[
                "ip"
            ]


        if "type" in data:

            device["type"] = data[
                "type"
            ]


        if "firmware" in data:

            device["firmware"] = data[
                "firmware"
            ]


        if "light" in data:

            device["light"] = bool(
                data["light"]
            )


        if "fan" in data:

            device["fan"] = bool(
                data["fan"]
            )


        if device_id not in commands:

            commands[device_id] = None


    return jsonify({

        "success": True,

        "message":
            "Heartbeat received",

        "device_id":
            device_id,

        "online":
            True
    })


# ==========================================================
# GET ALL DEVICES
# ==========================================================

@app.route(
    "/devices",
    methods=["GET"]
)
def get_devices():

    # IMPORTANT:
    # Check heartbeat age before returning devices.

    update_all_online_status()


    online_count = sum(

        1

        for device in devices.values()

        if device.get("online") is True
    )


    return jsonify({

        "success": True,

        "count":
            len(devices),

        "online_devices":
            online_count,

        "devices":
            list(
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

            "message":
                "Device not found"

        }), 404


    device = devices[
        device_id
    ]


    update_online_status(
        device
    )


    return jsonify({

        "success": True,

        "device":
            device
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

            "message":
                "No JSON data received"

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

            "message":
                "device_id is required"

        }), 400


    if not command:

        return jsonify({

            "success": False,

            "message":
                "command is required"

        }), 400


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
                "Invalid command"

        }), 400


    if device_id not in devices:

        return jsonify({

            "success": False,

            "message":
                "Device not found"

        }), 404


    # ------------------------------------------------------
    # CHECK DEVICE ONLINE STATUS
    # ------------------------------------------------------

    device = devices[
        device_id
    ]


    is_online = update_online_status(
        device
    )


    if not is_online:

        return jsonify({

            "success": False,

            "message":
                "Device is offline",

            "device_id":
                device_id,

            "online":
                False

        }), 409


    # ------------------------------------------------------
    # STORE COMMAND
    # ------------------------------------------------------

    commands[
        device_id
    ] = command


    return jsonify({

        "success": True,

        "message":
            "Command queued",

        "device_id":
            device_id,

        "command":
            command,

        "online":
            True
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

            "message":
                "device_id is required"

        }), 400


    if device_id not in devices:

        return jsonify({

            "success": False,

            "message":
                "Device not found"

        }), 404


    device = devices[
        device_id
    ]


    # ------------------------------------------------------
    # CHECK ONLINE STATUS
    # ------------------------------------------------------

    is_online = update_online_status(
        device
    )


    if not is_online:

        return jsonify({

            "success": False,

            "device_id":
                device_id,

            "online":
                False,

            "command":
                None,

            "message":
                "Device is offline"

        })


    command = commands.get(
        device_id
    )


    # ------------------------------------------------------
    # NO COMMAND
    # ------------------------------------------------------

    if command is None:

        return jsonify({

            "success": True,

            "device_id":
                device_id,

            "online":
                True,

            "command":
                None
        })


    # ------------------------------------------------------
    # DELIVER COMMAND
    # ------------------------------------------------------

    current_command = command


    commands[
        device_id
    ] = None


    return jsonify({

        "success": True,

        "device_id":
            device_id,

        "online":
            True,

        "command":
            current_command
    })


# ==========================================================
# MANUALLY MARK DEVICE OFFLINE
# ==========================================================

@app.route(
    "/device/<device_id>/offline",
    methods=["POST"]
)
def mark_offline(device_id):

    if device_id not in devices:

        return jsonify({

            "success": False,

            "message":
                "Device not found"

        }), 404


    devices[
        device_id
    ]["online"] = False


    # Clear pending command

    commands[
        device_id
    ] = None


    return jsonify({

        "success": True,

        "message":
            "Device marked offline",

        "device_id":
            device_id
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

    print(
        "Offline timeout:",
        OFFLINE_TIMEOUT_SECONDS,
        "seconds"
    )


    app.run(

        host="0.0.0.0",

        port=port
    )
