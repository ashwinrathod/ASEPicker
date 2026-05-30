from setuptools import setup
from Cython.Build import cythonize
import os

def run_setup():
    files_to_compile = ["core.py", "security.py", "api.py", "layout_io.py", "main.py"]
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