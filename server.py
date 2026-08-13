from flask import Flask, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)

# ==========================================================
# DEVICE DATABASE
# ==========================================================

devices = {}

# ==========================================================
# PENDING COMMANDS
# ==========================================================

commands = {}


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    return "ESP8266 Smart Home Server is running!"


# ==========================================================
# SERVER STATUS
# ==========================================================

@app.route("/status", methods=["GET"])
def status():

    return jsonify({

        "success": True,

        "server":
            "ESP Smart Home Cloud Server",

        "status":
            "online",

        "version":
            "1.0",

        "device_count":
            len(devices)

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


    devices[device_id] = {

        "device_id":
            device_id,

        "type":
            data.get(
                "type",
                "unknown"
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

        "last_seen":
            datetime.now().isoformat()

    }


    # Make sure device starts with no command

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

@app.route("/heartbeat", methods=["POST"])
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
                datetime.now().isoformat()

        }

    else:

        devices[device_id]["online"] = True

        devices[device_id]["last_seen"] = \
            datetime.now().isoformat()


        if "ip" in data:

            devices[device_id]["ip"] = \
                data["ip"]


    return jsonify({

        "success":
            True,

        "message":
            "Heartbeat received",

        "device_id":
            device_id

    })


# ==========================================================
# GET ALL DEVICES
# ==========================================================

@app.route("/devices", methods=["GET"])
def get_devices():

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


    if device_id not in devices:

        return jsonify({

            "success":
                False,

            "message":
                "Device not found"

        }), 404


    # Store command

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


    # No command waiting

    if command is None:

        return jsonify({

            "success":
                True,

            "device_id":
                device_id,

            "command":
                None

        })


    # Save command temporarily

    current_command = command


    # Clear command after delivering it

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
