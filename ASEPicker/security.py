import hmac
import hashlib
import base64
import json
import uuid
import datetime
import socket
import getpass
import os
import urllib.request

# --- MASTER SECRET FOR OFFLINE KEYS ---
SECRET_KEY = b"ASEPicker_Ultimate_Secret_Key_2026_X981"
ONLINE_URL = "https://asepicker-license-server.asepicker.workers.dev"

def get_system_id():
    mac = uuid.getnode()
    user = getpass.getuser().strip().lower()
    host = socket.gethostname().strip().lower()
    
    raw = f"{user}|{host}|{format(mac, '012x')}"
    digest = hashlib.sha256()
    digest.update(raw.encode("utf-8"))
    hexv = digest.hexdigest().upper()
    
    short = hexv[:20]
    parts = [short[i:i+4] for i in range(0, 20, 4)]
    return "-".join(parts)

def verify_offline_key(license_b64):
    if not license_b64: return False
    
    clean_b64 = license_b64.replace("OFF-", "")
    decoded_bytes = base64.b64decode(clean_b64)
    data = json.loads(decoded_bytes.decode('utf-8'))
    
    sys_id = data.get("sys_id", "")
    exp = data.get("exp", "")
    sig = data.get("sig", "")
    
    if sys_id != get_system_id(): return False
    
    payload = f"{sys_id}|{exp}"
    expected_sig = hmac.new(SECRET_KEY, payload.encode('utf-8'), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(sig, expected_sig): return False
    
    today = datetime.date.today()
    exp_date = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
    if today > exp_date: return False
    
    return True

def activate_online_key(parent_window, license_key):
    from PySide2 import QtWidgets
    system_id = get_system_id()
    
    payload = json.dumps({"license_key": license_key, "system_id": system_id}).encode('utf-8')
    req = urllib.request.Request(ONLINE_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    
    response = urllib.request.urlopen(req, timeout=10)
    
    if response.status != 200:
        error_data = json.loads(response.read().decode('utf-8'))
        QtWidgets.QMessageBox.critical(parent_window, "Activation Failed", error_data.get("error", "Unknown Error"))
        return False
        
    data = json.loads(response.read().decode('utf-8'))
    if data.get("status") == "success":
        save_license(f"{license_key}|{data.get('expiration_date')}")
        QtWidgets.QMessageBox.information(
            parent_window, 
            "Success", 
            f"Activated Successfully!\nSeats Used: {data.get('seats_used')}/{data.get('seats_total')}"
        )
        return True
    return False

def get_saved_license():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ASEPicker_Data")
    lic_file = os.path.join(data_dir, "license.dat")
    if not os.path.exists(lic_file): return ""
    with open(lic_file, "r") as f:
        return f.read().strip()

def save_license(license_str):
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ASEPicker_Data")
    if not os.path.exists(data_dir): os.makedirs(data_dir)
    lic_file = os.path.join(data_dir, "license.dat")
    with open(lic_file, "w") as f:
        f.write(license_str)

def enforce_license(parent_window):
    from PySide2 import QtWidgets
    
    saved_lic = get_saved_license()
    if saved_lic:
        if saved_lic.startswith("OFF-") and verify_offline_key(saved_lic): return True
        if saved_lic.startswith("ONL-"):
            parts = saved_lic.split("|")
            if len(parts) == 2:
                today = datetime.date.today()
                exp_date = datetime.datetime.strptime(parts[1], "%Y-%m-%d").date()
                if today <= exp_date: return True
        
    sys_id = get_system_id()
    text, ok = QtWidgets.QInputDialog.getMultiLineText(
        parent_window, 
        "ASEPicker Activation Required", 
        f"Your System ID:\n{sys_id}\n\nPlease enter your Activation Key (Starts with OFF- or ONL-):"
    )
    
    if ok and text.strip():
        key = text.strip()
        if key.startswith("OFF-"):
            if verify_offline_key(key):
                save_license(key)
                QtWidgets.QMessageBox.information(parent_window, "Success", "ASEPicker Activated Offline!")
                return True
        elif key.startswith("ONL-"):
            if activate_online_key(parent_window, key):
                return True
            
    QtWidgets.QMessageBox.critical(parent_window, "Failed", "Invalid or Expired License Key.")
    return False
