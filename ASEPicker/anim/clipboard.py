# ASEPicker/anim/clipboard.py
import json
import os
import shutil

# --- Path Helpers ---
def _get_clipboard_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    data_dir = os.path.join(root, "ASEPicker_Data", "clipboard")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return data_dir

def _get_file_path(file_type):
    # file_type: 'pose_local', 'pose_global', 'anim_local', 'anim_global'
    return os.path.join(_get_clipboard_dir(), f"{file_type}.json")

# --- IO Functions ---

def save_data(data, file_type):
    """
    Saves generic dictionary data to the clipboard folder.
    Overwrites previous copy of that type.
    """
    path = _get_file_path(file_type)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[ASEPicker] Copied {file_type} to clipboard.")

def load_data(file_type):
    """
    Loads dictionary data from the clipboard folder.
    Returns None if file doesn't exist.
    """
    path = _get_file_path(file_type)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def has_data(file_type):
    """Checks if a clipboard file exists."""
    path = _get_file_path(file_type)
    return os.path.exists(path)

def clear_clipboard():
    """Removes all clipboard files (optional cleanup)."""
    d = _get_clipboard_dir()
    if os.path.exists(d):
        shutil.rmtree(d)
        os.makedirs(d)