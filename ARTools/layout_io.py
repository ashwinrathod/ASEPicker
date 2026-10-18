# ARTools/layout_io.py
import json
import os
import getpass
from datetime import datetime
from maya import cmds

class LayoutManager:
    def _inject_metadata(self, data_dict):
        shapes = 0
        scripts = 0
        for tab in data_dict.get("subtabs", []):
            shapes += len(tab.get("items", []))
            scripts += len(tab.get("canvas_scripts", []))
            for item in tab.get("items", []):
                scripts += len(item.get("scripts", []))
                
        author = getpass.getuser() if hasattr(getpass, "getuser") else "Unknown"
        data_dict["_metadata"] = {
            "author": author,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "shape_count": shapes,
            "script_count": scripts
        }
        return data_dict

    def load_from_file(self, filepath):
        if not os.path.exists(filepath):
            return {}
        with open(filepath, "r") as f:
            return json.load(f)

    def save_to_file(self, filepath, data_dict):
        """Saves layout dictionary to a .json file on disk."""
        data_dict = self._inject_metadata(data_dict)
        with open(filepath, "w") as f:
            json.dump(data_dict, f, indent=4)

    def load_from_scene(self, character_name, node_name="ARToolsStorage"):
        attr = f"{node_name}.{character_name}"
        if cmds.objExists(attr):
            raw_data = cmds.getAttr(attr)
            if raw_data:
                return json.loads(raw_data)
        return {}

    def save_to_scene(self, character_name, data_dict, node_name="ARToolsStorage"):
        """Saves layout dictionary directly into a hidden node in the Maya scene."""
        data_dict = self._inject_metadata(data_dict)
        if not cmds.objExists(node_name):
            cmds.createNode("network", name=node_name)
            
        safe_name = character_name.replace(" ", "_")
        attr = f"{node_name}.{safe_name}"
        
        if not cmds.objExists(attr):
            cmds.addAttr(node_name, longName=safe_name, dataType="string")
            
        cmds.setAttr(attr, json.dumps(data_dict), type="string")