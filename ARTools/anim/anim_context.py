# ARTools/anim/anim_context.py
import bpy
from bpy_extras import anim_utils
from ..blender_host import selected_object_names, object_by_name

def _get_fcurves(anim_data):
    if not anim_data or not anim_data.action:
        return []
    if hasattr(anim_data.action, "fcurves"):
        return anim_data.action.fcurves
    if hasattr(anim_data, "action_slot"):
        cb = anim_utils.action_get_channelbag_for_slot(anim_data.action, anim_data.action_slot)
        if cb and hasattr(cb, "fcurves"):
            return cb.fcurves
    return []

class AnimContext:
    @staticmethod
    def get_anim_targets():
        """Returns the exact plugs and time context for the Math Engine."""
        scene = bpy.context.scene
        current = scene.frame_current
        
        context = {
            "plugs": [],
            "start": current,
            "end": current,
            "current": current,
            "has_range": False,
            "has_cb_attrs": False,
            "ge_frames": {},
            "anim_layer": None # Blender NLA overrides aren't mapped exactly like Maya AnimLayers here
        }

        # 1. Check Timeline Range (Preview Range in Blender)
        if scene.use_preview_range:
            context["start"] = scene.frame_preview_start
            context["end"] = scene.frame_preview_end
            context["has_range"] = True

        sel = selected_object_names()
        if not sel: return context

        # Data path mapper to convert Blender F-Curves to ARTools plugs
        fcurve_map = {
            ("location", 0): "tx", ("location", 1): "ty", ("location", 2): "tz",
            ("rotation_euler", 0): "rx", ("rotation_euler", 1): "ry", ("rotation_euler", 2): "rz",
            ("rotation_quaternion", 0): "rw", ("rotation_quaternion", 1): "rqx", ("rotation_quaternion", 2): "rqy", ("rotation_quaternion", 3): "rqz",
            ("scale", 0): "sx", ("scale", 1): "sy", ("scale", 2): "sz"
        }

        # 2. Resolve Plugs (Graph Editor selection vs Default)
        for obj_name in sel:
            b_obj = object_by_name(obj_name)
            if not b_obj: continue

            ge_plugs = []
            anim_host = getattr(b_obj, "id_data", b_obj)
            prefix = f'pose.bones["{b_obj.name}"].' if hasattr(b_obj, "bone") else ""
            
            # Check Graph Editor / Dope Sheet F-Curve selection
            if anim_host.animation_data and anim_host.animation_data.action:
                for fcurve in _get_fcurves(anim_host.animation_data):
                    if fcurve.select:
                        if prefix and not fcurve.data_path.startswith(prefix): continue
                        clean_path = fcurve.data_path[len(prefix):] if prefix else fcurve.data_path
                        
                        attr = fcurve_map.get((clean_path, fcurve.array_index))
                        if not attr:
                            # Custom property fallback: data_path is usually '["prop_name"]'
                            if clean_path.startswith('["') and clean_path.endswith('"]'):
                                attr = clean_path[2:-2]
                            else:
                                attr = clean_path
                        
                        plug = f"{obj_name}.{attr}"
                        ge_plugs.append(plug)
                        context["plugs"].append(plug)
                        
                        # Gather selected keyframes for this specific curve
                        sel_frames = []
                        for kp in fcurve.keyframe_points:
                            if kp.select_control_point:
                                sel_frames.append(kp.co.x)
                        
                        if sel_frames:
                            context["ge_frames"][plug] = list(set(sel_frames))
                            context["has_range"] = True

            # 3. Failsafe Fallback: If no specific curves are selected, default to all keyable transforms
            if not ge_plugs:
                attrs_to_save = ["tx", "ty", "tz", "rx", "ry", "rz", "rw", "rqx", "rqy", "rqz", "sx", "sy", "sz"]
                for k in b_obj.keys():
                    if not k.startswith("_"): attrs_to_save.append(k)
                    
                for a in attrs_to_save:
                    context["plugs"].append(f"{obj_name}.{a}")

        # Deduplicate
        context["plugs"] = list(set(context["plugs"]))
        return context