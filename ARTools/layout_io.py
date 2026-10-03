# ARTools/layout_io.py

import json
import os

import bpy

from .blender_host import scene_store


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
        storage = bpy.context.scene.get(node_name)
        if storage is None:
            return {}

        safe_name = character_name.replace(" ", "_")
        raw_data = storage.get(safe_name, "")

        if raw_data:
            return json.loads(raw_data)

        return {}

    def save_to_scene(self, character_name, data_dict, node_name="ARToolsStorage"):
        """Saves layout dictionary directly into Blender scene custom properties."""
        storage = scene_store(node_name)

        safe_name = character_name.replace(" ", "_")
        storage[safe_name] = json.dumps(data_dict)

