import json
import os
import serial
import time
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None


def resolve_service_account_path():
    env_path = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate

    base_dir = Path(__file__).resolve().parent
    search_roots = [
        base_dir,
        base_dir.parent,
        Path.home() / "Downloads",
    ]
    seen = set()

    for root in search_roots:
        if not root.exists():
            continue

        for pattern in [
            "serviceAccount.json",
            "firebase-adminsdk.json",
            "*firebase-adminsdk*.json",
            "*rfid-balance-reader*.json",
        ]:
            for candidate in sorted(root.glob(pattern)):
                if not candidate.is_file() or candidate in seen:
                    continue
                seen.add(candidate)
                try:
                    with candidate.open("r", encoding="utf-8") as file:
                        data = json.load(file)
                    if isinstance(data, dict) and data.get("type") == "service_account" and "private_key" in data:
                        return candidate
                except (json.JSONDecodeError, OSError, TypeError, ValueError):
                    continue
    return None


def load_service_account(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_arduino_port():
    env_port = os.getenv("ARDUINO_PORT")
    if env_port:
        port = str(env_port).strip()
        try:
            with serial.Serial(port, baudrate=9600, timeout=1):
                return port
        except (serial.SerialException, OSError):
            print(f"ERROR_ARDUINO_PORT_INVALID: {port} is not available. Check Device Manager > Ports (COM & LPT).")

    port_candidates = []
    if list_ports is not None:
        for port_info in list_ports.comports():
            port_name = getattr(port_info, "device", None) or str(port_info)
            desc = (getattr(port_info, "description", "") or "").lower()
            if "arduino" in desc or "wchusb" in desc or "usb serial" in desc:
                port_candidates.append(port_name)

    preferred = [
        "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "COM10", "COM11",
        "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"
    ]
    for port in port_candidates + preferred:
        try:
            with serial.Serial(port, baudrate=9600, timeout=1):
                return port
        except (serial.SerialException, OSError):
            continue
    return None


def connect_arduino(max_retries=25, retry_delay=5):
    for attempt in range(1, max_retries + 1):
        port = get_arduino_port()
        if port is None:
            print(f"ERROR_ARDUINO_NOT_FOUND: Waiting for Arduino connection (attempt {attempt}/{max_retries}).")
            if attempt < max_retries:
                time.sleep(retry_delay)
            continue

        try:
            arduino = serial.Serial(port=port, baudrate=9600, timeout=1)
            time.sleep(2)
            print(f"Connected to Arduino on {port}.")
            return arduino
        except serial.SerialException as exc:
            print(f"Serial connection error on {port}: {exc}")
            if attempt < max_retries:
                time.sleep(retry_delay)

    print("ERROR_ARDUINO_NOT_FOUND: Arduino not detected after retries. Set ARDUINO_PORT=COMx or check Device Manager > Ports (COM & LPT).")
    return None


def send_lcd_message(arduino, message: str):
    if arduino is None:
        return False

    text = str(message or "").replace("\r", "").strip()
    if not text:
        return False

    text = text.replace("\n", "|")
    try:
        arduino.write(f"{text}\n".encode("utf-8"))
        return True
    except (OSError, serial.SerialException):
        print("LCD write failed; serial connection may be lost.")
        return False


def mask_name_for_display(name: str):
    safe_name = (name or "STUDENT").strip()
    if not safe_name:
        return "STUDENT"

    parts = safe_name.split()
    if len(parts) == 1:
        first = parts[0]
        visible = first[:2] if len(first) > 2 else first[:1]
        return f"{visible}***"

    first = parts[0]
    last = parts[-1]
    visible = first[:2] if len(first) > 2 else first[:1]
    return f"{visible}*** {last}"


def format_lcd_message(name: str, scanned_rfid: str, balance):
    if balance is None:
        return f"UNKNOWN|{str(scanned_rfid)[:16]}"

    safe_name = mask_name_for_display(name)
    short_name = safe_name[:16]
    if len(short_name) < 2:
        short_name = "STUDENT"

    return f"{short_name[:16]}|PHP {float(balance):.2f}"


def display_card_on_lcd(arduino, uid: str, card_data):
    if not uid:
        return

    uid = str(uid).strip().upper()
    card = card_data or {}
    name = str(card.get("name") or "STUDENT")
    balance = card.get("balance", 0.00)

    try:
        balance = float(balance)
    except (TypeError, ValueError):
        balance = 0.00

    msg = format_lcd_message(name, uid, balance)
    print(f"LCD sync: {name} | UID {uid} | Balance: ₱{balance:.2f}")
    send_lcd_message(arduino, msg)


def main():
    key_path = resolve_service_account_path()
    if key_path is None:
        raise FileNotFoundError(
            "Firebase service account file not found. Create a service account JSON or set FIREBASE_SERVICE_ACCOUNT to its path."
        )

    load_service_account(key_path)

    try:
        cred = credentials.Certificate(str(key_path))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(
                cred,
                {
                    "databaseURL": "https://rfid-balance-reader-default-rtdb.asia-southeast1.firebasedatabase.app"
                },
            )
        print("Connected to Firebase Realtime Database!")
    except Exception as exc:
        raise RuntimeError(f"Firebase initialization failed: {exc}") from exc

    db_ref = db.reference("padua_rfid_db")
    sync_ref = db.reference("padua_rfid_sync")

    arduino = connect_arduino()
    if arduino is None:
        print("ERROR_ARDUINO_START_FAILED: The RFID reader could not connect to an Arduino. It will keep retrying on startup.")
        while True:
            time.sleep(10)
            arduino = connect_arduino()
            if arduino is not None:
                break

    print("=========================================")
    print("  RFID CLOUD LCD SYSTEM ACTIVE (Ctrl+C)   ")
    print("=========================================")

    def refresh_from_last_activity(event):
        payload = event.data or {}
        source = payload.get("source")
        if source is not None and source != "kiosk":
            return

        uid = payload.get("uid") or payload.get("card_uid") or payload.get("rfid_uid")
        if not uid:
            return

        card_data = db_ref.child(str(uid)).get()
        if card_data:
            display_card_on_lcd(arduino, uid, card_data)
        else:
            print(f"LCD sync: unknown UID {uid}")
            send_lcd_message(arduino, f"UNKNOWN|{str(uid)[:16]}")

    try:
        last_activity = sync_ref.child("last_activity").get()
        if last_activity:
            refresh_from_last_activity(type("Evt", (), {"data": last_activity})())

        sync_ref.child("last_activity").listen(refresh_from_last_activity)
    except Exception as exc:
        print(f"Firebase listener warning: {exc}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n=========================================")
        print("        SCANNER SHUTDOWN CLEANLY         ")
        print("=========================================")
        if arduino is not None:
            send_lcd_message(arduino, "System Offline")
            arduino.close()


if __name__ == "__main__":
    main()