import hmac
import hashlib
import base64
import json
import uuid
import datetime
import socket
import getpass
import os
import time
import platform
from maya import cmds

from PySide6 import QtWidgets, QtCore

# --- CRITICAL PERFORMANCE CACHE ---
# Prevents Maya from freezing by avoiding repetitive API/File checks during the session.
_SESSION_IS_VALID = None
_SESSION_TIER = None

# --- BUILDING ARTools MODE POWERFULL ---
SECRET_KEY = bytes([66, 117, 105, 108, 100, 105, 110, 103, 95, 65, 83, 69, 80, 105, 99, 107, 101, 114, 95, 77, 111, 114, 101, 95, 80, 111, 119, 101, 114, 102, 117, 108, 108, 95, 65, 78, 68, 95, 80, 114, 111, 100, 117, 116, 105, 118, 101, 95, 70, 111, 108, 108, 111, 119, 95, 67, 111, 100, 101, 95, 35, 49, 55, 49, 49, 49, 57, 56, 54])
_URL_BYTES = bytes([104, 116, 116, 112, 115, 58, 47, 47, 97, 115, 101, 45, 108, 105, 99, 101, 110, 115, 101, 45, 115, 101, 114, 118, 101, 114, 46, 97, 115, 101, 112, 105, 99, 107, 101, 114, 46, 119, 111, 114, 107, 101, 114, 115, 46, 100, 101, 118, 47])

def _cipher_data(data_bytes):
    """Applies an XOR cipher using the hidden SECRET_KEY to scramble/unscramble data."""
    key_len = len(SECRET_KEY)
    return bytes([b ^ SECRET_KEY[i % key_len] for i, b in enumerate(data_bytes)])

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
    """Returns (is_valid, tier_bitmask). Supports both new tiered keys and legacy keys."""
    if not license_b64: return False, 0
    
    try:
        clean_b64 = license_b64.replace("OFF-", "")
        decoded_bytes = base64.b64decode(clean_b64)
        data = json.loads(decoded_bytes.decode('utf-8'))
        
        sys_id = data.get("sys_id", "")
        exp = data.get("exp", "")
        tier = data.get("tier", 7) # Default to 7 for legacy keys
        sig = data.get("sig", "")
        
        if sys_id != get_system_id(): return False, 0
        
        # 1. Try New Tiered Signature Payload
        payload = f"{sys_id}|{exp}|{tier}"
        expected_sig = hmac.new(SECRET_KEY, payload.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(sig, expected_sig):
            # 2. Fallback to Legacy Signature Payload
            legacy_payload = f"{sys_id}|{exp}"
            legacy_sig = hmac.new(SECRET_KEY, legacy_payload.encode('utf-8'), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, legacy_sig):
                return False, 0
        
        today = datetime.date.today()
        exp_date = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
        if today > exp_date: return False, 0
        
        return True, tier
    except Exception:
        return False, 0

def activate_online_key(parent_window, license_key):
    """Queries Worker. Shielded urllib for offline users. Returns (is_valid, tier_bitmask)."""
    import urllib.request
    import urllib.error

    system_id = get_system_id()
    online_url = _URL_BYTES.decode('utf-8')
    
    payload = json.dumps({"license_key": license_key, "system_id": system_id}).encode('utf-8')
    req = urllib.request.Request(online_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    try:
        response = urllib.request.urlopen(req, timeout=10)
        
        if response.status != 200:
            error_data = json.loads(response.read().decode('utf-8'))
            QtWidgets.QMessageBox.critical(parent_window, "Activation Failed", error_data.get("error", "Unknown Error"))
            return False, 0
            
        data = json.loads(response.read().decode('utf-8'))
        if data.get("status") == "success":
            tier = data.get("tier", 7)
            # Store the Tier alongside the expiration date in the local dat file!
            save_license(f"{license_key}|{data.get('expiration_date')}|{tier}")
            
            QtWidgets.QMessageBox.information(
                parent_window, 
                "Success", 
                f"Activated Successfully!\nSeats Used: {data.get('seats_used')}/{data.get('seats_total')}"
            )
            return True, tier
            
        return False, 0
        
    except urllib.error.URLError:
        QtWidgets.QMessageBox.critical(parent_window, "Connection Error", "No internet connection to activation server.")
        return False, 0
    except Exception:
        return False, 0

def get_saved_license():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ARTools_Data")
    lic_file = os.path.join(data_dir, "license.dat")
    if not os.path.exists(lic_file): return ""
    
    try:
        # Read the scrambled bytes, decode Base64, and reverse the XOR cipher
        with open(lic_file, "rb") as f:
            encrypted_bytes = f.read()
        decrypted_bytes = _cipher_data(base64.b64decode(encrypted_bytes))
        return decrypted_bytes.decode('utf-8').strip()
    except Exception:
        # If the user tampers with the garbage text, it fails safely and asks for reactivation
        return ""

def save_license(license_str):
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ARTools_Data")
    if not os.path.exists(data_dir): os.makedirs(data_dir)
    lic_file = os.path.join(data_dir, "license.dat")
    
    # Apply the XOR cipher and encode to Base64 to make it look like pure garbage
    encrypted_bytes = base64.b64encode(_cipher_data(license_str.encode('utf-8')))
    with open(lic_file, "wb") as f:
        f.write(encrypted_bytes)

def _check_time_tamper():
    """
    AAA Anti-Cheat: 4-Layer Cryptographically signed time tracking.
    Uses distinct, obfuscated filenames per directory to prevent global searches.
    """
    current_time = int(time.time())
    
    # --- PATH RESOLUTION ---
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ARTools_Data")
    
    # 1. Local App File (Looks like a harmless tool cache)
    time_file = os.path.join(data_dir, ".time.db") 
    
    home = os.path.expanduser("~")
    system = platform.system()
    
    # 2. Deep OS Ghost File (Looks like an important OS system file)
    if system == "Windows":
        # Hiding it slightly deeper in the Microsoft folder
        ghost_dir = os.path.join(home, "AppData", "Local", "Microsoft", "Windows")
    elif system == "Darwin": # Mac
        ghost_dir = os.path.join(home, "Library", "Application Support", "System")
    else: # Linux
        ghost_dir = os.path.join(home, ".config", "systemd")
        
    if not os.path.exists(ghost_dir):
        try: os.makedirs(ghost_dir)
        except: ghost_dir = home
        
    ghost_file = os.path.join(ghost_dir, ".sys_uuid.db")
    
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
    if cmds.optionVar(exists="ARTools_SysCache"):
        maya_time = cmds.optionVar(q="ARTools_SysCache")
        
    # --- LAYER 2: Local Installation File ---
    file_time = read_secure_time(time_file)
    if file_time == -1: return True
    
    # --- LAYER 3: The OS Ghost File ---
    ghost_time = read_secure_time(ghost_file)
    if ghost_time == -1: return True
        
    last_recorded_time = max(maya_time, file_time, ghost_time)
    
    if current_time < (last_recorded_time - 7200):
        return True # TIME ROLLBACK CAUGHT!
        
    new_time = max(current_time, last_recorded_time)
    
    cmds.optionVar(intValue=("ARTools_SysCache", new_time))
    
    t_str = str(new_time)
    sig = hmac.new(SECRET_KEY, t_str.encode('utf-8'), hashlib.sha256).hexdigest()
    secure_payload = f"{t_str}|{sig}"
    
    try:
        if not os.path.exists(data_dir): os.makedirs(data_dir)
        with open(time_file, "w") as f: f.write(secure_payload)
        if system == 'Windows':
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(time_file, 2)
    except: pass
    
    try:
        with open(ghost_file, "w") as f: f.write(secure_payload)
        if system == 'Windows':
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(ghost_file, 2)
    except: pass
    
    return False

def enforce_license(target_module="picker", parent_window=None):
    """
    Validates license, checks Anti-Cheat, uses Session Caching, and verifies Bitmask Tiers.
    """
    global _SESSION_IS_VALID, _SESSION_TIER
    
    # Smart Fallback for older UI files
    if isinstance(target_module, QtWidgets.QWidget):
        parent_window = target_module
        target_module = "picker" 
    elif target_module is None:
        target_module = "picker"

    # 1. Anti-Cheat Check FIRST
    if _check_time_tamper():
        QtWidgets.QMessageBox.critical(parent_window, "Security Violation", "System clock tampering or rollback detected!\n\nLicense temporarily suspended to protect against expiration fraud.")
        return False

    is_valid = False
    tier = 0

    # 2. Check Session Cache (Prevents Lag)
    if _SESSION_IS_VALID is True:
        is_valid = True
        tier = _SESSION_TIER
    else:
        # 3. Read Local File if no cache
        saved_lic = get_saved_license()
        if saved_lic:
            if saved_lic.startswith("OFF-"):
                valid_check, t_check = verify_offline_key(saved_lic)
                if valid_check:
                    is_valid = True
                    tier = t_check
                    
            elif saved_lic.startswith("ONL-"):
                parts = saved_lic.split("|")
                if len(parts) >= 2:
                    today = datetime.date.today()
                    exp_date = datetime.datetime.strptime(parts[1], "%Y-%m-%d").date()
                    if today <= exp_date:
                        is_valid = True
                        tier = int(parts[2]) if len(parts) >= 3 else 7

        if is_valid:
            _SESSION_IS_VALID = True
            _SESSION_TIER = tier

    # 4. Show Activation UI if License is Missing/Expired
    if not is_valid:
        # Clear Cache
        _SESSION_IS_VALID = None
        _SESSION_TIER = None
        
        sys_id = get_system_id()
        
        dialog = QtWidgets.QDialog(parent_window)
        dialog.setWindowTitle("ARTools Activation")
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
                valid_check, t_check = verify_offline_key(key)
                if valid_check:
                    save_license(key)
                    _SESSION_IS_VALID = True
                    _SESSION_TIER = t_check
                    is_valid = True
                    tier = t_check
                    QtWidgets.QMessageBox.information(parent_window, "Success", "ARTools Activated Offline!")
            
            elif key.startswith("ONL-"):
                valid_check, t_check = activate_online_key(parent_window, key)
                if valid_check:
                    _SESSION_IS_VALID = True
                    _SESSION_TIER = t_check
                    is_valid = True
                    tier = t_check
        
        if not is_valid:
            # Reached if they hit activate with a bad key
            if ok and text.strip() and key.startswith("OFF-"):
                QtWidgets.QMessageBox.critical(parent_window, "Failed", "Invalid or Expired Offline Key.")
            return False

    # 5. Modular Bitmask Routing 
    if is_valid:
        module_bits = {
            "picker": 1,
            "animbar": 2,
            "library": 4
        }
        required_bit = module_bits.get(target_module.lower(), 1)
        
        if (tier & required_bit) == required_bit:
            from . import layout_io
            io_manager = layout_io.LayoutManager()
            io_manager._ase_secure_stamp = "JAY_SHREE_KRISHNA_1986" 
            return io_manager
            
    # Valid License, but they do not own this tier
    return False

def get_license_info():
    """Reads the current license.dat and returns parsed status info."""
    import datetime, json, base64
    info = {"status": "De-activated", "exp": "N/A", "tier": 0, "key": "None"}
    lic = get_saved_license()
    if not lic: return info

    info["key"] = lic.split("|")[0]
    
    if lic.startswith("OFF-"):
        # For offline, we scrape the payload directly to show the date
        info["status"] = "Activated"
        try:
            clean_b64 = lic.replace("OFF-", "")
            data = json.loads(base64.b64decode(clean_b64).decode('utf-8'))
            info["exp"] = data.get("exp", "N/A")
            info["tier"] = data.get("tier", 7)
        except: pass
        
    elif lic.startswith("ONL-"):
        parts = lic.split("|")
        if len(parts) >= 2:
            exp = parts[1]
            try:
                today = datetime.date.today()
                exp_date = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
                if today <= exp_date:
                    info["status"] = "Activated"
                else:
                    info["status"] = "Expired"
                info["exp"] = exp
                info["tier"] = int(parts[2]) if len(parts) >= 3 else 7
            except: pass
            
    return info

def show_license_status_ui(parent_window=None):
    """Displays the Universal License Dashboard with direct key input and validation."""
    from PySide6 import QtWidgets, QtCore
    from functools import partial
    import datetime, os
    
    info = get_license_info()
    
    dialog = QtWidgets.QDialog(parent_window)
    dialog.setWindowTitle("ARTools - License Status")
    dialog.resize(400, 320)
    layout = QtWidgets.QVBoxLayout(dialog)
    
    # 1. Status Header
    status_color = "#4CAF50" if info['status'] == "Activated" else "#F44336"
    lbl_status = QtWidgets.QLabel(f"Status: {info['status']}")
    lbl_status.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {status_color};")
    layout.addWidget(lbl_status)
    
    # 2. Expiration
    if info['status'] == 'Activated':
        exp = info['exp']
        if exp == "2099-12-31":
            exp_text = "Expiration: Permanent"
        else:
            exp_d = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
            days_left = (exp_d - datetime.date.today()).days
            exp_text = f"Expiration: {exp} ({days_left} Days Remaining)"
        layout.addWidget(QtWidgets.QLabel(exp_text))
    
    layout.addWidget(QtWidgets.QLabel("<b>Active Modules:</b>"))
    mod_layout = QtWidgets.QHBoxLayout()
    tier = info['tier']
    
    def make_badge(name, bit):
        is_active = (tier & bit) == bit and info['status'] == 'Activated'
        lbl = QtWidgets.QLabel(name)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        bg = "#4CAF50" if is_active else "#333333"
        fg = "#FFFFFF" if is_active else "#777777"
        lbl.setStyleSheet(f"background-color: {bg}; color: {fg}; padding: 6px; border-radius: 4px; font-weight: bold;")
        return lbl
        
    mod_layout.addWidget(make_badge("Picker", 1))
    mod_layout.addWidget(make_badge("AnimBar", 2))
    mod_layout.addWidget(make_badge("Library", 4))
    layout.addLayout(mod_layout)
    
    layout.addSpacing(15)
    layout.addWidget(QtWidgets.QLabel("<b>Update License Key:</b>"))
    
    # 3. New Input Box
    key_input = QtWidgets.QLineEdit()
    key_input.setPlaceholderText("Paste your new key here...")
    layout.addWidget(key_input)
    
    # 4. Update Button Logic
    btn_update = QtWidgets.QPushButton("Update License")
    btn_update.setStyleSheet("background-color: #5285a6; color: white; padding: 8px; font-weight: bold; border-radius: 4px;")
    
    def _perform_update(input_field, win, *args):
        key = input_field.text().strip()
        
        # Validation
        if not key:
            QtWidgets.QMessageBox.warning(win, "Empty Key", "Key box is empty. Please add License Key to procced.")
            return

        # Attempt Activation
        success = False
        new_tier = 0
        
        if key.startswith("OFF-"):
            valid, t = verify_offline_key(key)
            if valid:
                save_license(key)
                success = True
                new_tier = t
        elif key.startswith("ONL-"):
            valid, t = activate_online_key(win, key)
            if valid:
                success = True
                new_tier = t
        elif key.startswith("NET-"):
            valid, msg = install_network_master(key)
            if valid:
                success = True
                new_tier = 7
                QtWidgets.QMessageBox.information(win, "Network Setup", msg)
            else:
                QtWidgets.QMessageBox.critical(win, "Setup Failed", msg)
                return
        
        if success:
            global _SESSION_IS_VALID, _SESSION_TIER
            _SESSION_IS_VALID = True
            _SESSION_TIER = new_tier
            QtWidgets.QMessageBox.information(win, "Success", "License updated successfully!")
            win.accept()
        else:
            QtWidgets.QMessageBox.critical(win, "Error", "Invalid or expired key. License not updated.")

    btn_update.clicked.connect(partial(_perform_update, key_input, dialog))
    layout.addWidget(btn_update)
    
    # 5. Activate by Network Button
    btn_network = QtWidgets.QPushButton("Activate via Network")
    btn_network.setStyleSheet("background-color: #3c6e71; color: white; padding: 8px; font-weight: bold; border-radius: 4px; margin-top: 10px;")
    
    def _do_network_activate():
        valid, tier, msg = activate_by_network()
        if valid:
            global _SESSION_IS_VALID, _SESSION_TIER
            _SESSION_IS_VALID = True
            _SESSION_TIER = tier
            QtWidgets.QMessageBox.information(dialog, "Success", "Network Seat Claimed!")
            dialog.accept()
        else:
            QtWidgets.QMessageBox.warning(dialog, "Network Error", msg)
            
    btn_network.clicked.connect(_do_network_activate)
    layout.addWidget(btn_network)
    
    dialog.exec_()

# ==============================================================================
# ENTERPRISE NETWORK LICENSE ENGINE (SERVERLESS FLOATING SEATS)
# ==============================================================================
import threading

_NETWORK_HEARTBEAT_TIMER = None
_ACTIVE_SEAT_FILE = None

def _get_mac_address():
    import uuid
    return ''.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])

def _get_network_pool_dir():
    """Dynamically finds the network server folder where ARTools is installed."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pool_dir = os.path.join(base_dir, "ARTools_Data", ".sys_net_pool")
    if not os.path.exists(pool_dir):
        try: os.makedirs(pool_dir)
        except: pass
    return pool_dir

def get_network_request_id():
    """Generates a secure ID based on the server path so the license locks to the studio."""
    pool_dir = _get_network_pool_dir()
    master_uuid_file = os.path.join(pool_dir, ".server_anchor.sys")
    
    if not os.path.exists(master_uuid_file):
        server_uuid = str(uuid.uuid4())
        try:
            with open(master_uuid_file, 'w') as f: f.write(server_uuid)
        except: return None
    else:
        with open(master_uuid_file, 'r') as f: server_uuid = f.read().strip()
        
    return hashlib.sha256(f"SERVER_ANCHOR_{server_uuid}".encode('utf-8')).hexdigest()[:16]

def install_network_master(net_key):
    """(TD ONLY) Installs the NET- key onto the server."""
    if not net_key.startswith("NET-"): return False, "Invalid Network Key format."
    
    try:
        decoded_bytes = base64.b64decode(net_key[4:])
        data = json.loads(decoded_bytes.decode('utf-8'))
        
        payload_str = f"{data['net_id']}|{data['seats']}|{data['exp']}|{data['tier']}|{data['c_t']}"
        expected_sig = hmac.new(SECRET_KEY, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(str(data.get("sig", "")), expected_sig):
            return False, "License signature corrupted or tampered!"
            
        server_id = get_network_request_id()
        if data['net_id'] != server_id:
            return False, "This license key is not assigned to this server path!"
            
        pool_dir = _get_network_pool_dir()
        master_db = os.path.join(pool_dir, "master.db")
        with open(master_db, 'w') as f: json.dump(data, f)
        
        return True, f"Network License installed successfully. ({data['seats']} Seats)"
    except Exception as e:
        return False, str(e)

def activate_by_network():
    """(ARTIST) Reads the server, checks seats, and claims one if available."""
    pool_dir = _get_network_pool_dir()
    master_db = os.path.join(pool_dir, "master.db")
    
    if not os.path.exists(master_db): return False, 0, "No Network License found on server."
    
    try:
        with open(master_db, 'r') as f: master_data = json.load(f)
        
        # 1. Verification
        payload_str = f"{master_data['net_id']}|{master_data['seats']}|{master_data['exp']}|{master_data['tier']}|{master_data['c_t']}"
        expected_sig = hmac.new(SECRET_KEY, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(master_data.get("sig", "")), expected_sig):
            return False, 0, "Server License Tampered!"
            
        # 2. Expiration Check
        exp_date = datetime.datetime.strptime(master_data['exp'], "%Y-%m-%d").date()
        if datetime.date.today() > exp_date:
            return False, 0, "Network Subscription Expired!"
            
        # 3. The Reaper (Clean up crashes)
        _run_network_reaper(pool_dir)
        
        # 4. Seat Allocation
        max_seats = int(master_data['seats'])
        my_mac = _get_mac_address()
        my_seat_file = os.path.join(pool_dir, f".seat_{my_mac}.db")
        
        active_seats = [f for f in os.listdir(pool_dir) if f.startswith(".seat_")]
        
        if not os.path.exists(my_seat_file) and len(active_seats) >= max_seats:
            return False, 0, f"All {max_seats} Network Seats are currently in use."
            
        # 5. Claim Seat & Start Heartbeat
        _pulse_seat_heartbeat(my_seat_file)
        global _ACTIVE_SEAT_FILE
        _ACTIVE_SEAT_FILE = my_seat_file
        _start_heartbeat_timer()
        
        return True, int(master_data['tier']), ""
        
    except Exception as e:
        return False, 0, f"Network Error: {str(e)}"

def _pulse_seat_heartbeat(seat_file):
    """Cryptographically writes the current time to the seat file."""
    t = int(time.time())
    sig = hmac.new(SECRET_KEY, str(t).encode('utf-8'), hashlib.sha256).hexdigest()
    try:
        with open(seat_file, 'w') as f: json.dump({"t": t, "sig": sig}, f)
    except: pass

def _run_network_reaper(pool_dir):
    """Scans all seat files. Deletes any that haven't pulsed in 3 minutes (180s)."""
    current_time = int(time.time())
    for file in os.listdir(pool_dir):
        if file.startswith(".seat_"):
            seat_path = os.path.join(pool_dir, file)
            try:
                with open(seat_path, 'r') as f: data = json.load(f)
                sig = hmac.new(SECRET_KEY, str(data['t']).encode('utf-8'), hashlib.sha256).hexdigest()
                
                # If signature is faked, or time is older than 3 minutes -> KILL IT
                if not hmac.compare_digest(sig, str(data.get("sig", ""))) or (current_time - data['t'] > 180):
                    os.remove(seat_path)
            except:
                try: os.remove(seat_path) # Corrupt file, delete it
                except: pass

def _start_heartbeat_timer():
    """Silent QTimer that pulses every 60 seconds to keep the seat alive."""
    global _NETWORK_HEARTBEAT_TIMER, _ACTIVE_SEAT_FILE
    if _NETWORK_HEARTBEAT_TIMER is None:
        _NETWORK_HEARTBEAT_TIMER = QtCore.QTimer()
        _NETWORK_HEARTBEAT_TIMER.timeout.connect(lambda: _pulse_seat_heartbeat(_ACTIVE_SEAT_FILE) if _ACTIVE_SEAT_FILE else None)
        _NETWORK_HEARTBEAT_TIMER.start(60000) # 60 Seconds