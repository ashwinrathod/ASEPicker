import hmac
import hashlib
import base64
import json
import uuid
import datetime
import socket
import getpass
import os

try:
    from PySide2 import QtWidgets
except ImportError:
    from PySide6 import QtWidgets

# --- BUILDING ASEPICKER MODE POWERFULL ---
SECRET_KEY = bytes([66, 117, 105, 108, 100, 105, 110, 103, 95, 65, 83, 69, 80, 105, 99, 107, 101, 114, 95, 77, 111, 114, 101, 95, 80, 111, 119, 101, 114, 102, 117, 108, 108, 95, 65, 78, 68, 95, 80, 114, 111, 100, 117, 116, 105, 118, 101, 95, 70, 111, 108, 108, 111, 119, 95, 67, 111, 100, 101, 95, 35, 49, 55, 49, 49, 49, 57, 56, 54])
_URL_BYTES = bytes([104, 116, 116, 112, 115, 58, 47, 47, 97, 115, 101, 45, 108, 105, 99, 101, 110, 115, 101, 45, 115, 101, 114, 118, 101, 114, 46, 97, 115, 101, 112, 105, 99, 107, 101, 114, 46, 119, 111, 114, 107, 101, 114, 115, 46, 100, 101, 118, 47])

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
    import urllib.request

    system_id = get_system_id()
    
    # Decode the hidden URL right before we use it!
    online_url = _URL_BYTES.decode('utf-8')
    
    payload = json.dumps({"license_key": license_key, "system_id": system_id}).encode('utf-8')
    req = urllib.request.Request(online_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
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

# Place this right above enforce_license(parent_window):

def _check_time_tamper():
    """
    AAA Anti-Cheat: 4-Layer Cryptographically signed time tracking.
    Includes a 'Ghost File' outside of Maya's installation to survive uninstalls.
    """
    import time
    from maya import cmds
    import platform
    
    current_time = int(time.time())
    
    # --- PATH RESOLUTION ---
    # 1. Standard Hidden File (Inside Maya scripts)
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ASEPicker_Data")
    time_file = os.path.join(data_dir, ".sys_uuid.db") 
    
    # 2. The Ghost File (Deep in OS User AppData - No Admin Required)
    home = os.path.expanduser("~")
    system = platform.system()
    
    if system == "Windows":
        ghost_dir = os.path.join(home, "AppData", "Local", "Microsoft")
    elif system == "Darwin": # Mac
        ghost_dir = os.path.join(home, "Library", "Application Support")
    else: # Linux
        ghost_dir = os.path.join(home, ".config")
        
    # Safe fallback if the OS-specific user folder doesn't exist
    if not os.path.exists(ghost_dir):
        try: os.makedirs(ghost_dir)
        except: ghost_dir = home
        
    ghost_file = os.path.join(ghost_dir, ".sys_time_cache")
    
    # --- HELPER: Read and Verify Hashes ---
    def read_secure_time(path):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    content = f.read().strip()
                if "|" in content:
                    t_str, sig = content.split("|", 1)
                    expected_sig = hmac.new(SECRET_KEY, t_str.encode('utf-8'), hashlib.sha256).hexdigest()
                    if hmac.compare_digest(sig, expected_sig):
                        return int(t_str)
                    else:
                        return -1 # TAMPERED HASH CAUGHT!
            except: pass
        return 0

    # --- LAYER 1: Maya OptionVars ---
    maya_time = 0
    if cmds.optionVar(exists="ASEPicker_SysCache"):
        maya_time = cmds.optionVar(q="ASEPicker_SysCache")
        
    # --- LAYER 2: Local Installation File ---
    file_time = read_secure_time(time_file)
    if file_time == -1: return True
    
    # --- LAYER 3: The OS Ghost File ---
    ghost_time = read_secure_time(ghost_file)
    if ghost_time == -1: return True
        
    # Find the absolute highest time recorded across all 3 backups
    last_recorded_time = max(maya_time, file_time, ghost_time)
    
    # --- THE CHECK ---
    # Allow a small 2-hour (7200 seconds) buffer for daylight savings time changes
    if current_time < (last_recorded_time - 7200):
        return True # TIME ROLLBACK CAUGHT!
        
    # --- UPDATE ALL TRACKERS ---
    new_time = max(current_time, last_recorded_time)
    
    # 1. Write to Maya memory
    cmds.optionVar(intValue=("ASEPicker_SysCache", new_time))
    
    # Prepare the encrypted payload
    t_str = str(new_time)
    sig = hmac.new(SECRET_KEY, t_str.encode('utf-8'), hashlib.sha256).hexdigest()
    secure_payload = f"{t_str}|{sig}"
    
    # 2. Write Local File
    try:
        if not os.path.exists(data_dir): os.makedirs(data_dir)
        with open(time_file, "w") as f: f.write(secure_payload)
        # Force OS Hidden attribute on Windows
        if system == 'Windows':
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(time_file, 2)
    except: pass
    
    # 3. Write Ghost File
    try:
        with open(ghost_file, "w") as f: f.write(secure_payload)
        # Force OS Hidden attribute on Windows
        if system == 'Windows':
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(ghost_file, 2)
    except: pass
    
    return False

def enforce_license(parent_window):
    # 1. Anti-Cheat Check FIRST
    if _check_time_tamper():
        QtWidgets.QMessageBox.critical(parent_window, "Security Violation", "System clock tampering or rollback detected!\n\nLicense temporarily suspended to protect against expiration fraud.")
        return False

    saved_lic = get_saved_license()
    if saved_lic:
        if saved_lic.startswith("OFF-") and verify_offline_key(saved_lic): 
            from . import layout_io
            return layout_io.LayoutManager()
            
        if saved_lic.startswith("ONL-"):
            parts = saved_lic.split("|")
            if len(parts) == 2:
                today = datetime.date.today()
                exp_date = datetime.datetime.strptime(parts[1], "%Y-%m-%d").date()
                if today <= exp_date: 
                    from . import layout_io
                    return layout_io.LayoutManager()
        
    sys_id = get_system_id()
    
    dialog = QtWidgets.QDialog(parent_window)
    dialog.setWindowTitle("ASEPicker Activation")
    layout = QtWidgets.QVBoxLayout(dialog)
    
    layout.addWidget(QtWidgets.QLabel("Your System ID (Copy below for Offline Activation):"))
    sys_field = QtWidgets.QLineEdit(sys_id)
    sys_field.setReadOnly(True)
    layout.addWidget(sys_field)
    
    layout.addWidget(QtWidgets.QLabel("Enter Activation Key (OFF-... or ONL-...):"))
    key_field = QtWidgets.QLineEdit()
    layout.addWidget(key_field)
    
    btns = QtWidgets.QHBoxLayout()
    btn_ok = QtWidgets.QPushButton("Activate")
    btn_ok.clicked.connect(dialog.accept)
    btn_cancel = QtWidgets.QPushButton("Cancel")
    btn_cancel.clicked.connect(dialog.reject)
    btns.addWidget(btn_ok)
    btns.addWidget(btn_cancel)
    layout.addLayout(btns)
    
    sys_field.selectAll()
    
    ok = dialog.exec_()
    text = key_field.text()
    
    if ok and text.strip():
        key = text.strip()
        if key.startswith("OFF-"):
            if verify_offline_key(key):
                save_license(key)
                QtWidgets.QMessageBox.information(parent_window, "Success", "ASEPicker Activated Offline!")
                from . import layout_io
                return layout_io.LayoutManager()
                
        elif key.startswith("ONL-"):
            if activate_online_key(parent_window, key):
                from . import layout_io
                return layout_io.LayoutManager()
            
    QtWidgets.QMessageBox.critical(parent_window, "Failed", "Invalid or Expired License Key.")
    return False