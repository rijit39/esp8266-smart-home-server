from flask import Flask, request, jsonify
from datetime import datetime, timezone
import os

app = Flask(__name__)

# ==========================================================
# SERVER INFORMATION
# ==========================================================

SERVER_NAME = "ESP Smart Home Cloud Server"
VERSION = "2.0"

# Device considered offline after this many seconds
OFFLINE_TIMEOUT = 30

# ==========================================================
# DEVICE DATABASE
# ==========================================================

devices = {}

# ==========================================================
# PENDING COMMANDS
# ==========================================================

commands = {}


# ==========================================================
# CURRENT TIME
# ==========================================================

def current_time():

    return datetime.now(
        timezone.utc
    ).isoformat()


# ==========================================================
# UPDATE ONLINE STATUS
# ==========================================================

def update_online_status():

    now = datetime.now(
        timezone.utc
    )

    for device_id, device in devices.items():

        last_seen = device.get(
            "last_seen"
        )

        if not last_seen:
            device["online"] = False
            continue

        try:

            last_time = datetime.fromisoformat(
                last_seen
            )

            difference = (
                now - last_time
            ).total_seconds()

            if difference > OFFLINE_TIMEOUT:

                device["online"] = False

        except Exception:

            device["online"] = False


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    return jsonify({

        "success": True,

        "server":
            SERVER_NAME,

        "status":
            "online",

        "version":
            VERSION

    })


# ==========================================================
# SERVER STATUS
# ==========================================================

@app.route(
    "/status",
    methods=["GET"]
)
def status():

    update_online_status()

    online_count = sum(
        1
        for device in devices.values()
        if device.get("online")
    )

    return jsonify({

        "success":
            True,

        "server":
            SERVER_NAME,

        "status":
            "online",

        "version":
            VERSION,

        "device_count":
            len(devices),

        "online_devices":
            online_count

    })


# ==========================================================
# REGISTER DEVICE
# ==========================================================

@app.route(
    "/register",
    methods=["POST"]
)
def register():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({

            "success":
                False,

            "message":
                "No JSON data received"

        }), 400


    device_id = data.get(
        "device_id"
    )


    if not device_id:

        return jsonify({

            "success":
                False,

            "message":
                "device_id is required"

        }), 400


    # ------------------------------------------------------
    # Create or update device
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
                    "1.0"
                ),

            "online":
                True,

            "last_seen":
                current_time(),

            "light":
                False,

            "fan":
                False

        }

    else:

        devices[device_id]["type"] = \
            data.get(
                "type",
                devices[device_id]["type"]
            )

        devices[device_id]["ip"] = \
            data.get(
                "ip",
                devices[device_id]["ip"]
            )

        devices[device_id]["firmware"] = \
            data.get(
                "firmware",
                devices[device_id]["firmware"]
            )

        devices[device_id]["online"] = True

        devices[device_id]["last_seen"] = \
            current_time()


    # ------------------------------------------------------
    # Create command queue
    # ------------------------------------------------------

    if device_id not in commands:

        commands[device_id] = None


    return jsonify({

        "success":
            True,

        "message":
            "Device registered successfully",

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

            "success":
                False,

            "message":
                "No JSON data received"

        }), 400


    device_id = data.get(
        "device_id"
    )


    if not device_id:

        return jsonify({

            "success":
                False,

            "message":
                "device_id is required"

        }), 400


    # ------------------------------------------------------
    # Automatically create unknown device
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
                    "1.0"
                ),

            "online":
                True,

            "last_seen":
                current_time(),

            "light":
                False,

            "fan":
                False

        }


        commands[device_id] = None


    else:

        device = devices[device_id]

        device["online"] = True

        device["last_seen"] = \
            current_time()


        if "ip" in data:

            device["ip"] = \
                data["ip"]


        if "type" in data:

            device["type"] = \
                data["type"]


        if "firmware" in data:

            device["firmware"] = \
                data["firmware"]


        # --------------------------------------------------
        # Receive actual relay states from ESP
        # --------------------------------------------------

        if "light" in data:

            device["light"] = \
                bool(data["light"])


        if "fan" in data:

            device["fan"] = \
                bool(data["fan"])


    return jsonify({

        "success":
            True,

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

    update_online_status()

    return jsonify({

        "success":
            True,

        "count":
            len(devices),

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

    update_online_status()


    if device_id not in devices:

        return jsonify({

            "success":
                False,

            "message":
                "Device not found"

        }), 404


    return jsonify({

        "success":
            True,

        "device":
            devices[device_id]

    })


# ==========================================================
# SEND COMMAND FROM APP
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

            "success":
                False,

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

            "success":
                False,

            "message":
                "device_id is required"

        }), 400


    if not command:

        return jsonify({

            "success":
                False,

            "message":
                "command is required"

        }), 400


    # ------------------------------------------------------
    # Allowed commands
    # ------------------------------------------------------

    allowed_commands = [

        "LIGHT_ON",
        "LIGHT_OFF",
        "FAN_ON",
        "FAN_OFF"

    ]


    if command not in allowed_commands:

        return jsonify({

            "success":
                False,

            "message":
                "Invalid command"

        }), 400


    # ------------------------------------------------------
    # Device must exist
    # ------------------------------------------------------

    if device_id not in devices:

        return jsonify({

            "success":
                False,

            "message":
                "Device not found"

        }), 404


    # ------------------------------------------------------
    # Put command into this device's queue
    # ------------------------------------------------------

    commands[device_id] = command


    return jsonify({

        "success":
            True,

        "message":
            "Command queued",

        "device_id":
            device_id,

        "command":
            command

    })


# ==========================================================
# ESP CHECKS FOR COMMAND
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

            "success":
                False,

            "message":
                "device_id is required"

        }), 400


    if device_id not in devices:

        return jsonify({

            "success":
                False,

            "message":
                "Device not found"

        }), 404


    command = commands.get(
        device_id
    )


    # ------------------------------------------------------
    # No command waiting
    # ------------------------------------------------------

    if command is None:

        return jsonify({

            "success":
                True,

            "device_id":
                device_id,

            "command":
                None

        })


    # ------------------------------------------------------
    # Save command
    # ------------------------------------------------------

    current_command = command


    # ------------------------------------------------------
    # Remove command from queue
    # ------------------------------------------------------

    commands[device_id] = None


    return jsonify({

        "success":
            True,

        "device_id":
            device_id,

        "command":
            current_command

    })


# ==========================================================
# UPDATE DEVICE STATE
# ==========================================================

@app.route(
    "/state",
    methods=["POST"]
)
def update_state():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify({

            "success":
                False,

            "message":
                "No JSON data received"

        }), 400


    device_id = data.get(
        "device_id"
    )


    if not device_id:

        return jsonify({

            "success":
                False,

            "message":
                "device_id is required"

        }), 400


    if device_id not in devices:

        return jsonify({

            "success":
                False,

            "message":
                "Device not found"

        }), 404


    device = devices[device_id]


    # ------------------------------------------------------
    # Update light state
    # ------------------------------------------------------

    if "light" in data:

        device["light"] = \
            bool(data["light"])


    # ------------------------------------------------------
    # Update fan state
    # ------------------------------------------------------

    if "fan" in data:

        device["fan"] = \
            bool(data["fan"])


    device["online"] = True

    device["last_seen"] = \
        current_time()


    return jsonify({

        "success":
            True,

        "message":
            "Device state updated",

        "device":
            device

    })


# ==========================================================
# REMOVE DEVICE
# ==========================================================

@app.route(
    "/device/<device_id>",
    methods=["DELETE"]
)
def delete_device(device_id):

    if device_id not in devices:

        return jsonify({

            "success":
                False,

            "message":
                "Device not found"

        }), 404


    del devices[device_id]


    if device_id in commands:

        del commands[device_id]


    return jsonify({

        "success":
            True,

        "message":
            "Device removed",

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
        "======================================"
    )

    print(
        "Server starting..."
    )


    app.run(

        host="0.0.0.0",

        port=port

    )
