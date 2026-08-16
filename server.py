from flask import Flask, request, jsonify
from datetime import datetime, timezone
import os
import threading

app = Flask(__name__)


# ==========================================================
# SERVER VERSION
# ==========================================================

SERVER_VERSION = "2.2"


# ==========================================================
# DEVICE OFFLINE TIMEOUT
# ==========================================================

OFFLINE_TIMEOUT_SECONDS = 30


# ==========================================================
# COMMAND TIMEOUT
#
# A command that is not confirmed within this time is removed.
# This prevents old commands from remaining forever.
# ==========================================================

COMMAND_TIMEOUT_SECONDS = 15


# ==========================================================
# DEVICE DATABASE
# ==========================================================

devices = {}


# ==========================================================
# COMMAND QUEUE
#
# Structure:
#
# commands = {
#
#   "ESP8266-123456": {
#
#       "LIGHT": {
#           "command": "LIGHT_ON",
#           "created": "...",
#           "delivered": False
#       },
#
#       "FAN": {
#           "command": "FAN_ON",
#           "created": "...",
#           "delivered": False
#       }
#   }
# }
#
# Light and Fan now have separate command slots.
# ==========================================================

commands = {}


# ==========================================================
# THREAD LOCK
#
# Protects the dictionaries from simultaneous requests.
# ==========================================================

data_lock = threading.RLock()


# ==========================================================
# CURRENT UTC TIME
# ==========================================================

def current_datetime():

    return datetime.now(timezone.utc)


def current_time():

    return current_datetime().isoformat()


# ==========================================================
# COMMAND TYPE
# ==========================================================

def command_type(command):

    if command.startswith("LIGHT_"):
        return "LIGHT"

    if command.startswith("FAN_"):
        return "FAN"

    return None


# ==========================================================
# CREATE COMMAND STORAGE FOR DEVICE
# ==========================================================

def ensure_command_storage(device_id):

    if device_id not in commands:

        commands[device_id] = {

            "LIGHT": None,

            "FAN": None
        }


# ==========================================================
# CLEAR ALL COMMANDS FOR DEVICE
# ==========================================================

def clear_device_commands(device_id):

    ensure_command_storage(device_id)

    commands[device_id]["LIGHT"] = None
    commands[device_id]["FAN"] = None


# ==========================================================
# CLEAN EXPIRED COMMANDS
# ==========================================================

def cleanup_commands(device_id=None):

    now = current_datetime()

    device_ids = (

        [device_id]
        if device_id is not None
        else list(commands.keys())
    )

    for current_device_id in device_ids:

        ensure_command_storage(current_device_id)

        for control in ["LIGHT", "FAN"]:

            item = commands[current_device_id][control]

            if item is None:
                continue

            try:

                created_text = item.get("created")

                if not created_text:
                    commands[current_device_id][control] = None
                    continue

                created = datetime.fromisoformat(
                    created_text
                )

                if created.tzinfo is None:

                    created = created.replace(
                        tzinfo=timezone.utc
                    )

                age = (
                    now - created
                ).total_seconds()

                if age > COMMAND_TIMEOUT_SECONDS:

                    print(
                        "Command expired:",
                        current_device_id,
                        control,
                        item.get("command")
                    )

                    commands[
                        current_device_id
                    ][control] = None

            except Exception as e:

                print(
                    "Command cleanup error:",
                    e
                )

                commands[
                    current_device_id
                ][control] = None


# ==========================================================
# UPDATE DEVICE ONLINE STATUS
# ==========================================================

def update_online_status(device):

    try:

        last_seen_text = device.get(
            "last_seen"
        )

        if not last_seen_text:

            device["online"] = False

            return False


        last_seen = datetime.fromisoformat(
            last_seen_text
        )


        if last_seen.tzinfo is None:

            last_seen = last_seen.replace(
                tzinfo=timezone.utc
            )


        age = (
            current_datetime() - last_seen
        ).total_seconds()


        if age > OFFLINE_TIMEOUT_SECONDS:

            device["online"] = False

            device_id = device.get(
                "device_id"
            )

            if device_id:

                clear_device_commands(
                    device_id
                )

            return False


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

    with data_lock:

        for device in devices.values():

            update_online_status(
                device
            )

        cleanup_commands()


# ==========================================================
# CONFIRM COMMANDS USING HEARTBEAT
#
# If ESP reports the desired state, remove that command.
# ==========================================================

def confirm_commands_from_state(
    device_id,
    light_state,
    fan_state
):

    ensure_command_storage(
        device_id
    )


    # ------------------------------------------------------
    # LIGHT
    # ------------------------------------------------------

    light_command = commands[
        device_id
    ]["LIGHT"]


    if light_command is not None:

        command = light_command.get(
            "command"
        )


        if (
            command == "LIGHT_ON"
            and light_state is True
        ):

            print(
                "Confirmed LIGHT_ON:",
                device_id
            )

            commands[
                device_id
            ]["LIGHT"] = None


        elif (
            command == "LIGHT_OFF"
            and light_state is False
        ):

            print(
                "Confirmed LIGHT_OFF:",
                device_id
            )

            commands[
                device_id
            ]["LIGHT"] = None


    # ------------------------------------------------------
    # FAN
    # ------------------------------------------------------

    fan_command = commands[
        device_id
    ]["FAN"]


    if fan_command is not None:

        command = fan_command.get(
            "command"
        )


        if (
            command == "FAN_ON"
            and fan_state is True
        ):

            print(
                "Confirmed FAN_ON:",
                device_id
            )

            commands[
                device_id
            ]["FAN"] = None


        elif (
            command == "FAN_OFF"
            and fan_state is False
        ):

            print(
                "Confirmed FAN_OFF:",
                device_id
            )

            commands[
                device_id
            ]["FAN"] = None


# ==========================================================
# HOME
# ==========================================================

@app.route(
    "/",
    methods=["GET"]
)
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

@app.route(
    "/status",
    methods=["GET"]
)
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


    with data_lock:

        # --------------------------------------------------
        # NEW DEVICE
        # --------------------------------------------------

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


            ensure_command_storage(
                device_id
            )


            message = (
                "New device registered successfully"
            )


        # --------------------------------------------------
        # EXISTING DEVICE
        # --------------------------------------------------

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


            ensure_command_storage(
                device_id
            )


            # ------------------------------------------------
            # IMPORTANT
            #
            # Confirm states reported during registration.
            # ------------------------------------------------

            confirm_commands_from_state(

                device_id,

                device.get(
                    "light",
                    False
                ),

                device.get(
                    "fan",
                    False
                )
            )


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


    with data_lock:

        # --------------------------------------------------
        # UNKNOWN DEVICE
        # --------------------------------------------------

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


            ensure_command_storage(
                device_id
            )


        # --------------------------------------------------
        # EXISTING DEVICE
        # --------------------------------------------------

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


            ensure_command_storage(
                device_id
            )


        # --------------------------------------------------
        # CONFIRM REAL ESP STATE
        # --------------------------------------------------

        device = devices[
            device_id
        ]


        confirm_commands_from_state(

            device_id,

            device.get(
                "light",
                False
            ),

            device.get(
                "fan",
                False
            )
        )


        # --------------------------------------------------
        # CLEAN OLD COMMANDS
        # --------------------------------------------------

        cleanup_commands(
            device_id
        )


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

    with data_lock:

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


        cleanup_commands(
            device_id
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


    control = command_type(
        command
    )


    if control is None:

        return jsonify({

            "success": False,

            "message":
                "Invalid control"

        }), 400


    with data_lock:

        if device_id not in devices:

            return jsonify({

                "success": False,

                "message":
                    "Device not found"

            }), 404


        device = devices[
            device_id
        ]


        # --------------------------------------------------
        # CHECK DEVICE ONLINE
        # --------------------------------------------------

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


        ensure_command_storage(
            device_id
        )


        # --------------------------------------------------
        # CLEAN OLD COMMANDS
        # --------------------------------------------------

        cleanup_commands(
            device_id
        )


        # --------------------------------------------------
        # STORE NEW COMMAND
        #
        # IMPORTANT:
        #
        # Only the same control is replaced.
        #
        # LIGHT command does NOT replace FAN command.
        # FAN command does NOT replace LIGHT command.
        # --------------------------------------------------

        commands[
            device_id
        ][control] = {

            "command":
                command,

            "created":
                current_time(),

            "delivered":
                False
        }


        print(
            "Command queued:",
            device_id,
            control,
            command
        )


    return jsonify({

        "success": True,

        "message":
            "Command queued",

        "device_id":
            device_id,

        "command":
            command,

        "control":
            control,

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


    with data_lock:

        if device_id not in devices:

            return jsonify({

                "success": False,

                "message":
                    "Device not found"

            }), 404


        device = devices[
            device_id
        ]


        # --------------------------------------------------
        # CHECK ONLINE STATUS
        # --------------------------------------------------

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


        # --------------------------------------------------
        # REMOVE EXPIRED COMMANDS
        # --------------------------------------------------

        cleanup_commands(
            device_id
        )


        ensure_command_storage(
            device_id
        )


        # --------------------------------------------------
        # PRIORITY:
        #
        # Return Light first if available.
        # Otherwise return Fan.
        #
        # The other command remains queued.
        # --------------------------------------------------

        selected_control = None
        selected_item = None


        if commands[
            device_id
        ]["LIGHT"] is not None:

            selected_control = "LIGHT"

            selected_item = commands[
                device_id
            ]["LIGHT"]


        elif commands[
            device_id
        ]["FAN"] is not None:

            selected_control = "FAN"

            selected_item = commands[
                device_id
            ]["FAN"]


        # --------------------------------------------------
        # NO COMMAND
        # --------------------------------------------------

        if selected_item is None:

            return jsonify({

                "success": True,

                "device_id":
                    device_id,

                "online":
                    True,

                "command":
                    None
            })


        # --------------------------------------------------
        # MARK AS DELIVERED
        #
        # IMPORTANT:
        #
        # DO NOT DELETE IT YET.
        #
        # The heartbeat must confirm the actual
        # relay state first.
        # --------------------------------------------------

        commands[
            device_id
        ][selected_control]["delivered"] = True


        current_command = selected_item[
            "command"
        ]


        print(
            "Command delivered:",
            device_id,
            selected_control,
            current_command
        )


        return jsonify({

            "success": True,

            "device_id":
                device_id,

            "online":
                True,

            "command":
                current_command,

            "control":
                selected_control
        })


# ==========================================================
# COMMAND STATUS
#
# Useful for debugging and future Android improvements.
# ==========================================================

@app.route(
    "/command/status",
    methods=["GET"]
)
def command_status():

    device_id = request.args.get(
        "device_id"
    )


    if not device_id:

        return jsonify({

            "success": False,

            "message":
                "device_id is required"

        }), 400


    with data_lock:

        if device_id not in devices:

            return jsonify({

                "success": False,

                "message":
                    "Device not found"

            }), 404


        cleanup_commands(
            device_id
        )


        ensure_command_storage(
            device_id
        )


        result = {}


        for control in [
            "LIGHT",
            "FAN"
        ]:

            item = commands[
                device_id
            ][control]


            if item is None:

                result[
                    control.lower()
                ] = None

            else:

                result[
                    control.lower()
                ] = {

                    "command":
                        item.get(
                            "command"
                        ),

                    "created":
                        item.get(
                            "created"
                        ),

                    "delivered":
                        item.get(
                            "delivered",
                            False
                        )
                }


        return jsonify({

            "success": True,

            "device_id":
                device_id,

            "commands":
                result
        })


# ==========================================================
# MANUALLY MARK DEVICE OFFLINE
# ==========================================================

@app.route(
    "/device/<device_id>/offline",
    methods=["POST"]
)
def mark_offline(device_id):

    with data_lock:

        if device_id not in devices:

            return jsonify({

                "success": False,

                "message":
                    "Device not found"

            }), 404


        devices[
            device_id
        ]["online"] = False


        clear_device_commands(
            device_id
        )


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
        " VERSION 2.2"
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

    print(
        "Command timeout:",
        COMMAND_TIMEOUT_SECONDS,
        "seconds"
    )


    app.run(

        host="0.0.0.0",

        port=port
    )
