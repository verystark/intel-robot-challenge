"""Read-only health check of an SO-101 arm's six Feetech STS3215 motors.

Reads supply voltage, temperature, load, current, error flags and the settings
that make a motor slow or weak (speed limit, torque limit, acceleration, PID).
Writes nothing, so torque and positions are left exactly as they are.

Close every Studio session that uses the arm first: two programs talking on
the motor bus at once can garble commands. The script refuses to run if the
port is in use.

    physical-ai-studio/application/backend/.venv/bin/python tools/servo_check.py           # follower
    physical-ai-studio/application/backend/.venv/bin/python tools/servo_check.py leader
"""

from __future__ import annotations

import subprocess
import sys
import time

import scservo_sdk as scs

PORTS = {
    "follower": "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B3E090516-if00",
    "leader": "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AA9024537-if00",
}
JOINTS = {1: "shoulder_pan", 2: "shoulder_lift", 3: "elbow_flex", 4: "wrist_flex", 5: "wrist_roll", 6: "gripper"}
STATUS_BITS = {0: "VOLTAGE", 1: "SENSOR", 2: "OVERHEAT", 3: "OVERCURRENT", 5: "OVERLOAD"}

# name: (address, bytes) from the STS3215 control table
SETTINGS = {
    "max_torque": (16, 2),  # EEPROM, 0-1000 (0.1 %)
    "torque_limit": (48, 2),  # RAM, what the motor may use right now; drops after overload protection
    "goal_speed": (46, 2),  # 0 = no limit; a small number makes the motor crawl
    "goal_time": (44, 2),  # 0 = no limit
    "accel": (41, 1),  # 0 = no limit, else 1-254 (lower = gentler)
    "max_accel": (85, 1),
    "P": (21, 1),
    "D": (22, 1),
    "I": (23, 1),
    "mode": (33, 1),  # 0 = position
    "min_volt": (15, 1),  # 0.1 V
    "max_temp": (13, 1),
    "prot_torque": (34, 1),  # % torque allowed after overload protection trips
    "overload_torque": (36, 1),
    "prot_current": (28, 2),
    "torque_on": (40, 1),
}
LIVE = {
    "volt": (62, 1),
    "temp": (63, 1),
    "load": (60, 2),
    "current": (69, 2),
    "speed": (58, 2),
    "pos": (56, 2),
    "status": (65, 1),
    "moving": (66, 1),
}


def signed(value: int, sign_bit: int) -> int:
    """STS sign-magnitude: the given bit is the direction, the bits below it the size."""
    return -(value & ((1 << sign_bit) - 1)) if value & (1 << sign_bit) else value


def main() -> None:
    arm = sys.argv[1] if len(sys.argv) > 1 else "follower"
    port_path = PORTS[arm]
    users = subprocess.run(["fuser", port_path], capture_output=True, text=True).stdout.strip()
    if users:
        sys.exit(f"{arm} port is in use by process {users}. Close the Studio session using the arm first.")

    port = scs.PortHandler(port_path)
    packets = scs.PacketHandler(0)
    if not port.openPort() or not port.setBaudRate(1_000_000):
        sys.exit(f"Cannot open {port_path}")

    def read(servo_id: int, address: int, size: int) -> int | None:
        fn = packets.read1ByteTxRx if size == 1 else packets.read2ByteTxRx
        value, comm, error = fn(port, servo_id, address)
        return value if comm == scs.COMM_SUCCESS else None

    try:
        print(f"{arm} ({port_path.rsplit('_', 1)[-1]})\n")
        settings = {}
        for sid, joint in JOINTS.items():
            settings[sid] = {name: read(sid, a, s) for name, (a, s) in SETTINGS.items()}

        print(f"{'joint':14} {'volt':>5} {'temp':>5} {'load%':>6} {'mA':>6} {'speed':>6} {'pos':>5}  status")
        for sample in range(3):
            for sid, joint in JOINTS.items():
                live = {name: read(sid, a, s) for name, (a, s) in LIVE.items()}
                if live["volt"] is None:
                    print(f"{joint:14} NO RESPONSE")
                    continue
                flags = [n for bit, n in STATUS_BITS.items() if live["status"] & (1 << bit)] or ["ok"]
                print(
                    f"{joint:14} {live['volt'] / 10:5.1f} {live['temp']:4d}C {signed(live['load'], 10) / 10:6.1f}"
                    f" {live['current'] * 6.5:6.0f} {signed(live['speed'], 15):6d} {live['pos']:5d}  {' '.join(flags)}"
                )
            if sample < 2:
                print()
                time.sleep(0.5)

        print(f"\n{'joint':14} " + " ".join(f"{n:>9}" for n in SETTINGS))
        for sid, joint in JOINTS.items():
            print(f"{joint:14} " + " ".join(f"{'-' if v is None else v:>9}" for v in settings[sid].values()))
    finally:
        port.closePort()


if __name__ == "__main__":
    main()
