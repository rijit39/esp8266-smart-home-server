from flask import Flask, request, jsonify
from datetime import datetime, timezone
import os
import threading


app = Flask(__name__)


# ==========================================================
# SERVER
# ==========================================================

SERVER_VERSION = "3.0"

OFFLINE_TIMEOUT_SECONDS = 30
COMMAND_TIMEOUT_SECONDS = 15


# ==========================================================
# DATABASE
# ==========================================================

devices = {}

# Command queue:
#
# commands = {
#     "ESP8266-123456": {
#         "relay_1": {
#             "command": "RELAY_ON",
#             "created": "...",
#             "delivered": False
#         }
#     }
# }

commands = {}


# ==========================================================
# THREAD LOCK
# ==========================================================

data_lock = threading.RLock()


# ==========================================================
# TIME
# ==========================================================

def current_datetime():
    return datetime.now(timezone.utc)


def current_time():
    return current_datetime().isoformat()


# ==========================================================
# DEVICE COMMAND STORAGE
# ==========================================================

def ensure_command_storage(device_id):

    if device_id not in commands:
        commands[device_id] = {}


def clear_device_commands(device_id):

    ensure_command_storage(device_id)

    commands[device_id].clear()


# ==========================================================
# COMMAND CONTROL NAME
# ==========================================================

def get_control_from_command(command, data=None):

    data = data or {}

    # ------------------------------------------------------
    # NEW GENERIC RELAY COMMAND
    # ------------------------------------------------------

    if command in ["RELAY_ON", "RELAY_OFF"]:

        relay_id = data.get("relay")

        if relay_id is None:
            relay_id = data.get("channel")

        if relay_id is None:
            relay_id = 1

        return "relay_" + str(relay_id)


    # ------------------------------------------------------
    # OLD COMMANDS
    # ------------------------------------------------------

    if command.startswith("LIGHT_"):
        return "light"

    if command.startswith("FAN_"):
        return "fan"


    return None


# ==========================================================
# COMMAND TIMEOUT CLEANUP
# ==========================================================

def cleanup_commands(device_id=None):

    now = current_datetime()

    if device_id is not None:
        device_ids = [device_id]
    else:
        device_ids = list(commands.keys())


    for current_device_id in device_ids:

        ensure_command_storage(current_device_id)

        controls = list(
            commands[current_device_id].keys()
        )


        for control in controls:

            item = commands[
                current_device_id
            ].get(control)


            if item is None:
                continue


            try:

                created_text = item.get("created")


                if not created_text:

                    commands[
                        current_device_id
                    ].pop(control, None)

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
                    ].pop(control, None)


            except Exception as e:

                print(
                    "Command cleanup error:",
                    e
                )


                commands[
                    current_device_id
                ].pop(control, None)


# ==========================================================
# ONLINE STATUS
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
# UPDATE ALL ONLINE STATUS
# ==========================================================

def update_all_online_status():

    with data_lock:

        for device in devices.values():

            update_online_status(
                device
            )


        cleanup_commands()


# ==========================================================
# NORMALIZE RELAYS
# ==========================================================

def normalize_relays(data):

    relays = data.get("relays")


    # ------------------------------------------------------
    # NEW FORMAT
    # ------------------------------------------------------

    if isinstance(relays, list):

        result = []


        for index, relay in enumerate(
            relays,
            start=1
        ):

            if isinstance(relay, dict):

                relay_id = relay.get(
                    "id",
                    index
                )

                name = relay.get(
                    "name",
                    "Relay " + str(relay_id)
                )

                state = bool(
                    relay.get(
                        "state",
                        False
                    )
                )

            else:

                relay_id = index

                name = (
                    "Relay " +
                    str(relay_id)
                )

                state = bool(relay)


            result.append({

                "id": relay_id,

                "name": name,

                "state": state

            })


        return result


    # ------------------------------------------------------
    # CURRENT 2-RELAY SYSTEM
    # ------------------------------------------------------

    return [

        {
            "id": 1,
            "name": "Light",
            "state": bool(
                data.get(
                    "light",
                    False
                )
            )
        },

        {
            "id": 2,
            "name": "Fan",
            "state": bool(
                data.get(
                    "fan",
                    False
                )
            )
        }

    ]


# ==========================================================
# UPDATE RELAY STATE
# ==========================================================

def update_relay_state(
    device,
    relay_id,
    state
):

    relays = device.setdefault(
        "relays",
        []
    )


    found = False


    for relay in relays:

        if str(relay.get("id")) == str(
            relay_id
        ):

            relay["state"] = bool(state)

            found = True

            break


    if not found:

        relays.append({

            "id": relay_id,

            "name":
                "Relay " +
                str(relay_id),

            "state": bool(state)

        })


    # ------------------------------------------------------
    # BACKWARD COMPATIBILITY
    # ------------------------------------------------------

    if str(relay_id) == "1":

        device["light"] = bool(state)


    if str(relay_id) == "2":

        device["fan"] = bool(state)


# ==========================================================
# FIND RELAY
# ==========================================================

def get_relay_state(
    device,
    relay_id
):

    relays = device.get(
        "relays",
        []
    )


    for relay in relays:

        if str(
            relay.get("id")
        ) == str(relay_id):

            return bool(
                relay.get(
                    "state",
                    False
                )
            )


    return False


# ==========================================================
# CONFIRM COMMAND FROM DEVICE STATE
# ==========================================================

def confirm_commands_from_state(
    device_id,
    device
):

    ensure_command_storage(
        device_id
    )


    controls = list(
        commands[device_id].keys()
    )


    for control in controls:

        item = commands[
            device_id
        ].get(control)


        if item is None:
            continue


        command = item.get(
            "command"
        )


        confirmed = False


        # --------------------------------------------------
        # OLD LIGHT COMMAND
        # --------------------------------------------------

        if control == "light":

            state = bool(
                device.get(
                    "light",
                    False
                )
            )


            if (
                command == "LIGHT_ON"
                and state
            ):

                confirmed = True


            elif (
                command == "LIGHT_OFF"
                and not state
            ):

                confirmed = True


        # --------------------------------------------------
        # OLD FAN COMMAND
        # --------------------------------------------------

        elif control == "fan":

            state = bool(
                device.get(
                    "fan",
                    False
                )
            )


            if (
                command == "FAN_ON"
                and state
            ):

                confirmed = True


            elif (
                command == "FAN_OFF"
                and not state
            ):

                confirmed = True


        # --------------------------------------------------
        # GENERIC RELAY
        # --------------------------------------------------

        elif control.startswith(
            "relay_"
        ):

            relay_id = control.replace(
                "relay_",
                ""
            )


            state = get_relay_state(
                device,
                relay_id
            )


            if (
                command == "RELAY_ON"
                and state
            ):

                confirmed = True


            elif (
                command == "RELAY_OFF"
                and not state
            ):

                confirmed = True


        # --------------------------------------------------
        # REMOVE CONFIRMED COMMAND
        # --------------------------------------------------

        if confirmed:

            print(
                "Command confirmed:",
                device_id,
                control,
                command
            )


            commands[
                device_id
            ].pop(
                control,
                None
            )


# ==========================================================
# CREATE / UPDATE DEVICE
# ==========================================================

def build_device(data):

    relays = normalize_relays(
        data
    )


    device = {

        "device_id":
            data.get(
                "device_id"
            ),

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

        # ----------------------------------------------
        # BACKWARD COMPATIBLE
        # ----------------------------------------------

        "light":
            bool(
                data.get(
                    "light",
                    get_relay_state(
                        {
                            "relays": relays
                        },
                        1
                    )
                )
            ),

        "fan":
            bool(
                data.get(
                    "fan",
                    get_relay_state(
                        {
                            "relays": relays
                        },
                        2
                    )
                )
            ),

        # ----------------------------------------------
        # GENERIC RELAYS
        # ----------------------------------------------

        "relays":
            relays,

        # ----------------------------------------------
        # SENSORS
        # ----------------------------------------------

        "sensors":
            data.get(
                "sensors",
                {}
            ),

        # ----------------------------------------------
        # ENERGY
        # ----------------------------------------------

        "energy":
            data.get(
                "energy",
                {}
            ),

        "last_seen":
            current_time()
    }


    return device


# ==========================================================
# UPDATE DEVICE FROM ESP DATA
# ==========================================================

def update_device_from_data(
    device,
    data
):

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


    # ------------------------------------------------------
    # GENERIC RELAYS
    # ------------------------------------------------------

    if "relays" in data:

        device["relays"] = (
            normalize_relays(data)
        )


    # ------------------------------------------------------
    # OLD LIGHT / FAN
    # ------------------------------------------------------

    if "light" in data:

        device["light"] = bool(
            data["light"]
        )


        update_relay_state(
            device,
            1,
            data["light"]
        )


    if "fan" in data:

        device["fan"] = bool(
            data["fan"]
        )


        update_relay_state(
            device,
            2,
            data["fan"]
        )


    # ------------------------------------------------------
    # SENSORS
    # ------------------------------------------------------

    if "sensors" in data:

        device["sensors"] = (
            data.get(
                "sensors",
                {}
            )
        )


    # ------------------------------------------------------
    # ENERGY
    # ------------------------------------------------------

    if "energy" in data:

        device["energy"] = (
            data.get(
                "energy",
                {}
            )
        )


    device["online"] = True

    device["last_seen"] = (
        current_time()
    )


# ==========================================================
# HOME
# ==========================================================

@app.route("/", methods=["GET"])
def home():

    update_all_online_status()


    online_count = sum(

        1

        for device in devices.values()

        if device.get(
            "online"
        ) is True
    )


    return jsonify({

        "success": True,

        "server":
            "ESP Smart Home Cloud Server",

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

        if device.get(
            "online"
        ) is True
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

            devices[device_id] = (
                build_device(data)
            )


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


            update_device_from_data(
                device,
                data
            )


            ensure_command_storage(
                device_id
            )


            confirm_commands_from_state(
                device_id,
                device
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
        # AUTOMATIC REGISTRATION
        # --------------------------------------------------

        if device_id not in devices:

            devices[device_id] = (
                build_device(data)
            )


            ensure_command_storage(
                device_id
            )


            print(
                "Auto-registered device:",
                device_id
            )


        # --------------------------------------------------
        # EXISTING DEVICE
        # --------------------------------------------------

        else:

            device = devices[
                device_id
            ]


            update_device_from_data(
                device,
                data
            )


        device = devices[
            device_id
        ]


        # --------------------------------------------------
        # CONFIRM COMMANDS
        # --------------------------------------------------

        confirm_commands_from_state(
            device_id,
            device
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
            True,

        "device":
            device
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


    with data_lock:

        online_count = sum(

            1

            for device in devices.values()

            if device.get(
                "online"
            ) is True
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
# SEND COMMAND
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
        "FAN_OFF",

        "RELAY_ON",
        "RELAY_OFF"
    ]


    if command not in allowed_commands:

        return jsonify({

            "success": False,

            "message":
                "Invalid command"

        }), 400


    control = get_control_from_command(
        command,
        data
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
        # CHECK ONLINE
        # --------------------------------------------------

        if not update_online_status(
            device
        ):

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


        cleanup_commands(
            device_id
        )


        # --------------------------------------------------
        # STORE COMMAND
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
# ESP GET COMMAND
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
        # CHECK ONLINE
        # --------------------------------------------------

        if not update_online_status(
            device
        ):

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


        cleanup_commands(
            device_id
        )


        ensure_command_storage(
            device_id
        )


        # --------------------------------------------------
        # FIND FIRST AVAILABLE COMMAND
        # --------------------------------------------------

        selected_control = None

        selected_item = None


        for control, item in (
            commands[
                device_id
            ].items()
        ):

            if item is not None:

                selected_control = control

                selected_item = item

                break


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
        # MARK DELIVERED
        # --------------------------------------------------

        selected_item[
            "delivered"
        ] = True


        current_command = (
            selected_item[
                "command"
            ]
        )


        print(
            "Command delivered:",
            device_id,
            selected_control,
            current_command
        )


        response = {

            "success": True,

            "device_id":
                device_id,

            "online":
                True,

            "command":
                current_command,

            "control":
                selected_control
        }


        # --------------------------------------------------
        # GENERIC RELAY ID
        # --------------------------------------------------

        if selected_control.startswith(
            "relay_"
        ):

            relay_id = (
                selected_control.replace(
                    "relay_",
                    ""
                )
            )


            response[
                "relay"
            ] = relay_id


        return jsonify(response)


# ==========================================================
# COMMAND STATUS
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


        for control, item in (
            commands[
                device_id
            ].items()
        ):

            if item is None:

                result[
                    control
                ] = None

            else:

                result[
                    control
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
# MANUALLY MARK OFFLINE
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
# RESET DEVICE COMMANDS
# ==========================================================

@app.route(
    "/device/<device_id>/clear-commands",
    methods=["POST"]
)
def clear_commands(device_id):

    with data_lock:

        if device_id not in devices:

            return jsonify({

                "success": False,

                "message":
                    "Device not found"

            }), 404


        clear_device_commands(
            device_id
        )


        return jsonify({

            "success": True,

            "message":
                "All commands cleared",

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
        " ESP SMART HOME CLOUD SERVER"
    )

    print(
        " VERSION 3.0"
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
