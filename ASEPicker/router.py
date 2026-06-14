# ASEPicker/router.py
import maya.cmds as cmds

def launch(module=None):
    """
    COMPILED Smart Router. 
    Handles modular launching and license verification securely.
    """
    from . import security
    
    # 1. Auto-Detect Mode
    if not module:
        if security.enforce_license("picker"): module = "picker"
        elif security.enforce_license("animbar"): module = "animbar"
        elif security.enforce_license("library"): module = "library"
        else:
            cmds.warning("[ASEPicker] No valid modules found in your current license.")
            return

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
                cmds.warning(f"[ASEPicker] AnimBar Launch Error: {e}")
        else:
            cmds.warning("// Warning: The AnimBar module is not included in your current license. //")
    
    # 4. Route: Library
    elif module == "library":
        if security.enforce_license("library"):
            try:
                from .library import browser
                browser.LibraryBrowser(toggle=True)
            except Exception as e:
                cmds.warning(f"[ASEPicker] Library Launch Error: {e}")
        else:
            cmds.warning("// Warning: The Animation Library module is not included in your current license. //")