import sys
import os

def launch():
    # 1. Get the current directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Detect the operating system
    plat = sys.platform
    os_name = "win" if plat == "win32" else "mac" if plat == "darwin" else "linux"
    
    # 3. Detect the Major.Minor Python version (e.g., "3.7" -> "37")
    py_ver = f"{sys.version_info.major}{sys.version_info.minor}"
    
    # 4. Construct the path to the correct compiled binary folder
    # Example: ASEPicker/build/win/py37
    binary_path = os.path.join(current_dir, "build", os_name, f"py{py_ver}")
    
    # 5. Inject it into Maya's path so it can read the .pyd files
    if binary_path not in sys.path:
        sys.path.insert(0, binary_path)
        
    # 6. Now that the path is set, it is safe to import your compiled code!
    from . import main
    
    # Example of how you might trigger your UI to open:
    # main._app_instance = main.PickerController()