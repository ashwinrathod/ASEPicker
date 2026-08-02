import maya.cmds as cmds

def launch(module=None):
    """
    COMPILED Smart Router. 
    Handles modular launching, license verification, and duplicate prevention securely.
    """
    from . import security
    from PySide6 import QtWidgets
    
    # 1. Auto-Detect Mode
    if not module:
        if security.enforce_license("picker"): module = "picker"
        elif security.enforce_license("animbar"): module = "animbar"
        elif security.enforce_license("library"): module = "library"
        else:
            cmds.warning("[ARTools] No valid modules found in your current license.")
            return

    # --- NEW: SINGLETON "BRING TO FRONT" SCANNER ---
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
    # -----------------------------------------------

    # 2. Route: Picker
    if module == "picker":
        if security.enforce_license("picker"):
            from . import main
            main._app_instance = main.PickerController()
            main._app_instance.window.show()
            main._app_instance.window.raise_()
        else:
            cmds.warning("// Warning: The Picker module is not included in your current license. //")
    
    # 3. Route: AnimBar
    elif module == "animbar":
        if security.enforce_license("animbar"):
            try:
                from PySide6 import QtCore
                from .anim import anim_bar
                from .ui import get_maya_main_window
                ab = anim_bar.AnimBar(parent=get_maya_main_window())
                ab.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
                ab.show()
            except Exception as e:
                cmds.warning(f"[ARTools] AnimBar Launch Error: {e}")
        else:
            cmds.warning("// Warning: The AnimBar module is not included in your current license. //")
    
    # 4. Route: Library
    elif module == "library":
        if security.enforce_license("library"):
            try:
                from .library import browser
                browser.LibraryBrowser(toggle=False)
            except Exception as e:
                cmds.warning(f"[ARTools] Library Launch Error: {e}")
        else:
            cmds.warning("// Warning: The Animation Library module is not included in your current license. //")