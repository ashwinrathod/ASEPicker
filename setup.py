from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# Files we absolutely DO NOT want to compile
IGNORE_FILES = [
    "__init__.py", 
    "hyper_trail_plugin.py"
]

extensions = []

# Walk through all folders and subfolders inside ARTools
for root, dirs, files in os.walk("ARTools"):
    for file in files:
        if file.endswith(".py") and file not in IGNORE_FILES:
            
            # Get the exact file path (e.g., ARTools/anim/logic_anim.py)
            file_path = os.path.join(root, file)
            
            # Convert the file path into a strict Python module name
            # 1. Remove .py
            module_name = file_path.replace(".py", "")
            # 2. Replace BOTH Windows and Mac/Linux slashes with dots
            module_name = module_name.replace("\\", ".").replace("/", ".")
            
            # Create the exact Extension target
            extensions.append(Extension(module_name, [file_path]))

if not extensions:
    print("ERROR: Could not find Python files to compile!")
else:
    setup(
        ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"})
    )
