# ARTools/router.py
from PySide6 import QtCore, QtWidgets

# --- Prevent Garbage Collection ---
# Anchors tools in memory so they don't instantly close!
_active_windows = {}

def launch(module=None):
    """
    COMPILED Smart Router. 
    Handles modular launching, license verification, and duplicate prevention securely.
    """
    from . import security
    global _active_windows
    
    # 1. Auto-Detect Mode
    if not module:
        if security.enforce_license("picker"): module = "picker"
        elif security.enforce_license("animbar"): module = "animbar"
        elif security.enforce_license("library"): module = "library"
        else:
            print("[ARTools] No valid modules found in your current license.")
            return

    # --- SINGLETON "BRING TO FRONT" SCANNER ---
    tool_name = module.lower()
    for widget in QtWidgets.QApplication.topLevelWidgets():
        # Check for Picker
        if tool_name == "picker" and type(widget).__name__ == "PickerWindow":
            widget.showNormal()
            widget.raise_()
            widget.activateWindow()
            print("[ARTools] Picker is already open. Bringing to front.")
            return
            
        # Check for AnimBar
        elif tool_name == "animbar" and widget.objectName() == "AnimBar":
            widget.showNormal()
            widget.raise_()
            widget.activateWindow()
            print("[ARTools] AnimBar is already open. Bringing to front.")
            return
            
        # Check for Library
        elif tool_name == "library" and type(widget).__name__ == "RibbonBrowser":
            widget.showNormal()
            widget.raise_()
            widget.activateWindow()
            print("[ARTools] Library is already open. Bringing to front.")
            return

        # Check for Link Manager
        elif tool_name == "link_manager" and type(widget).__name__ == "LinkManagerWindow":
            widget.showNormal()
            widget.raise_()
            widget.activateWindow()
            print("[ARTools] Link Manager is already open. Bringing to front.")
            return
    # -----------------------------------------------

    # 2. Route: Picker
    if module == "picker":
        if security.enforce_license("picker"):
            from . import main
            main._app_instance = main.PickerController()
            main._app_instance.window.show()
            main._app_instance.window.raise_()
        else:
            print("[ARTools] The Picker module is not included in your current license.")
    
    # 3. Route: AnimBar
    elif module == "animbar":
        if security.enforce_license("animbar"):
            from .anim import anim_bar
            _active_windows["animbar"] = anim_bar.AnimBar()
            _active_windows["animbar"].setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
            _active_windows["animbar"].show()
        else:
            print("[ARTools] The AnimBar module is not included in your current license.")
    
    # 4. Route: Library
    elif module == "library":
        if security.enforce_license("library"):
            from .library import browser
            _active_windows["library"] = browser.LibraryBrowser(toggle=False)
        else:
            print("[ARTools] The Animation Library module is not included in your current license.")

    # 5. Route: Link Manager
    elif module == "link_manager":
        from .link import link_manager_ui
        _active_windows["link_manager"] = link_manager_ui.LinkManagerWindow()
        _active_windows["link_manager"].show()