# ARTools/layout_io.py
import json
import os
from maya import cmds

class LayoutManager:
    def load_from_file(self, filepath):
        if not os.path.exists(filepath):
            return {}
        with open(filepath, "r") as f:
            return json.load(f)

    def save_to_file(self, filepath, data_dict):
        """Saves layout dictionary to a .json file on disk."""
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
        # 1. Ensure the storage node exists
        if not cmds.objExists(node_name):
            cmds.createNode("network", name=node_name)
            
        # 2. Maya attributes can't have spaces, so we sanitize the character name
        safe_name = character_name.replace(" ", "_")
        attr = f"{node_name}.{safe_name}"
        
        # 3. Add the attribute if it doesn't exist, then save the data
        if not cmds.objExists(attr):
            cmds.addAttr(node_name, longName=safe_name, dataType="string")
            
        cmds.setAttr(attr, json.dumps(data_dict), type="string")