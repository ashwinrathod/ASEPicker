from setuptools import setup
from Cython.Build import cythonize
import os

def run_setup():
    # Notice that hyper_trail_plugin.py is INTENTIONALLY MISSING!
    # It must remain a raw .py file so Maya can load it as a plugin.
    files_to_compile = [
        "core.py", 
        "security.py", 
        "api.py", 
        "layout_io.py", 
        "main.py",
        "alignment_panel.py",
        "editor_panel.py",
        "picker_shapes.py",
        "preferences.py",
        "script_editor.py",
        "ui.py",
        "anim/anim_bar.py",
        "anim/clipboard.py",
        "anim/logic_anim.py",
        "anim/logic_ikfk.py",
        "anim/logic_pose.py",
        "anim/snapshot.py",
        "anim/trail.py"
    ]
    target_files = []
    
    for f in files_to_compile:
        if os.path.exists(f):
            target_files.append(f)
        elif os.path.exists("ASEPicker/" + f):
            target_files.append("ASEPicker/" + f)
            
    if not target_files:
        print("ERROR: Could not find Python files to compile!")
        return
        
    exts = cythonize(target_files)
    setup(ext_modules=exts)

run_setup()