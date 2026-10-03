# ARTools/anim/anim_math.py
import bpy
import math
from ..blender_host import object_by_name

class AnimMath:
    _F_PATHS = {
        "tx": ("location", 0), "ty": ("location", 1), "tz": ("location", 2),
        "rx": ("rotation_euler", 0), "ry": ("rotation_euler", 1), "rz": ("rotation_euler", 2),
        "rw": ("rotation_quaternion", 0), "rqx": ("rotation_quaternion", 1), "rqy": ("rotation_quaternion", 2), "rqz": ("rotation_quaternion", 3),
        "sx": ("scale", 0), "sy": ("scale", 1), "sz": ("scale", 2),
    }

    @staticmethod
    def _get_fcurves(anim_data):
        if not anim_data or not anim_data.action:
            return []
        if hasattr(anim_data.action, "fcurves"):
            return anim_data.action.fcurves
        if hasattr(anim_data, "action_slot"):
            from bpy_extras import anim_utils
            cb = anim_utils.action_get_channelbag_for_slot(anim_data.action, anim_data.action_slot)
            if cb and hasattr(cb, "fcurves"):
                return cb.fcurves
        return []

    @staticmethod
    def _get_fcurve(b_obj, attr):
        anim_host = getattr(b_obj, "id_data", b_obj)
        fcurves = AnimMath._get_fcurves(anim_host.animation_data)
        if not fcurves:
            return None
        
        prefix = f'pose.bones["{b_obj.name}"].' if hasattr(b_obj, "bone") else ""
        
        path_info = AnimMath._F_PATHS.get(attr)
        if path_info:
            data_path, index = path_info
            data_path = prefix + data_path
        else:
            data_path = f'{prefix}["{attr}"]'
            index = 0
            
        for fc in fcurves:
            if fc.data_path == data_path and fc.array_index == index:
                return fc
        return None

    @staticmethod
    def _ensure_fcurve(b_obj, attr):
        fc = AnimMath._get_fcurve(b_obj, attr)
        if fc: return fc
        
        # Instantly and safely initialize Blender's new Slotted Action system
        # by letting native C-code generate the action, slots, and curves
        from ..blender_host import set_property, get_property
        val = get_property(b_obj, attr, 0.0)
        set_property(b_obj, attr, val, keyframe=True)
        
        return AnimMath._get_fcurve(b_obj, attr)

    @staticmethod
    def build_cache(context, active_tool):
        cache = {}
        plugs = context.get("plugs", [])
        if not plugs: return cache

        anim_layer = context.get("anim_layer")
        cache["__anim_layer__"] = anim_layer

        namespaces = set()
        for plug in plugs:
            node = plug.split('.')[0]
            if ':' in node: namespaces.add(node.rsplit(':', 1)[0])
            else: namespaces.add("")

        from . import snapshot
        snaps = {ns: (snapshot.load_snapshot(ns) or {}) for ns in namespaces}

        for plug in plugs:
            try:
                node, attr = plug.split('.', 1)
                short_node = node.split(':')[-1]
                ns = node.rsplit(':', 1)[0] if ':' in node else ""
                
                ns_data = snaps.get(ns) or {}
                snap = ns_data.get("controls", {}).get(short_node, {})

                if context.get("ge_frames") and plug in context["ge_frames"]:
                    frames = context["ge_frames"][plug]
                elif context["has_range"]:
                    b_obj = object_by_name(node)
                    if b_obj:
                        fc = AnimMath._get_fcurve(b_obj, attr)
                        if fc:
                            frames = [kp.co.x for kp in fc.keyframe_points if context["start"] <= kp.co.x <= context["end"]]
                        else:
                            frames = []
                    else:
                        frames = []
                else:
                    if context.get("has_cb_attrs") and active_tool in ["Smooth", "Linearize", "Scale Avg", "Ease In/Out", "Blend to Default", "Mirror Blend"]:
                        b_obj = object_by_name(node)
                        if b_obj:
                            fc = AnimMath._get_fcurve(b_obj, attr)
                            frames = [kp.co.x for kp in fc.keyframe_points] if fc else []
                        else:
                            frames = []
                    else:
                        frames = [context["current"]]

                if not frames:
                    if not context["has_range"]: frames = [context["current"]]
                    else: continue

                frames = sorted(list(set(frames)))
                b_obj = object_by_name(node)
                if not b_obj: continue
                
                curve = AnimMath._ensure_fcurve(b_obj, attr)
                if not curve: continue
                
                # --- Ensure keys exist at evaluated frames ---
                existing_keys = {kp.co.x: kp for kp in curve.keyframe_points}
                for f in frames:
                    if f not in existing_keys:
                        curve.keyframe_points.insert(f, curve.evaluate(f))
                
                existing_keys = {kp.co.x: kp for kp in curve.keyframe_points}
                all_times = sorted(list(existing_keys.keys()))

                f_data = {}
                for f in frames:
                    orig_v = curve.evaluate(f)
                    
                    pkv_t = f
                    nkv_t = f
                    idx = all_times.index(f) if f in all_times else -1
                    if idx > 0: pkv_t = all_times[idx - 1]
                    if idx != -1 and idx < len(all_times) - 1: nkv_t = all_times[idx + 1]
                    
                    pkv = curve.evaluate(pkv_t)
                    nkv = curve.evaluate(nkv_t)
                    pfv = curve.evaluate(f - 1)
                    nfv = curve.evaluate(f + 1)
                    
                    target_v = orig_v

                    if active_tool == "Blend to Default":
                        if snap and "defaults" in snap and attr in snap["defaults"]:
                            target_v = snap["defaults"][attr]
                        else:
                            target_v = 1.0 if attr in ["sx", "sy", "sz", "scaleX", "scaleY", "scaleZ", "rw"] else 0.0

                    elif active_tool == "Mirror Blend":
                        partner_short = snap.get("mirror")
                        side = snap.get("side", "Center")
                        
                        t_rules = snap.get("mirror_rules", {}).get("translate", [[0, 1.0], [1, 1.0], [2, 1.0]])
                        r_rules = snap.get("mirror_rules", {}).get("rotate", [[0, 1.0], [1, 1.0], [2, 1.0]])
                        if t_rules and isinstance(t_rules[0], (int, float)):
                            t_rules = [[0, t_rules[0]], [1, t_rules[1]], [2, t_rules[2]]]
                            r_rules = [[0, r_rules[0]], [1, r_rules[1]], [2, r_rules[2]]]

                        is_rot = "rotate" in attr or attr in ["rx", "ry", "rz"]
                        is_trans = "translate" in attr or attr in ["tx", "ty", "tz"]
                        is_short = attr in ["tx", "ty", "tz", "rx", "ry", "rz"]

                        src_axis = -1
                        if "X" in attr or "x" in attr: src_axis = 0
                        elif "Y" in attr or "y" in attr: src_axis = 1
                        elif "Z" in attr or "z" in attr: src_axis = 2

                        mult = 1.0
                        mapped_attr = attr

                        if (is_rot or is_trans) and src_axis != -1:
                            active_rules = r_rules if is_rot else t_rules
                            mapped_axis = src_axis
                            for tgt_idx, rule in enumerate(active_rules):
                                if rule[0] == src_axis:
                                    mapped_axis = tgt_idx
                                    mult = rule[1]
                                    break
                            
                            base_name = "rotate" if is_rot else "translate"
                            mapped_attr = f"{base_name[0]}{['x','y','z'][mapped_axis]}" if is_short else f"{base_name}{['X','Y','Z'][mapped_axis]}"

                        partner_node = node
                        if side != "Center" and partner_short:
                            partner_node = f"{ns}:{partner_short}" if ns else partner_short
                        
                        p_b_obj = object_by_name(partner_node)
                        if p_b_obj:
                            p_fc = AnimMath._get_fcurve(p_b_obj, mapped_attr)
                            if p_fc:
                                target_v = p_fc.evaluate(f) * mult
                            else:
                                target_v = orig_v

                    f_data[f] = {
                        "v": orig_v, "pkv": pkv, "nkv": nkv, 
                        "pfv": pfv, "nfv": nfv, "target_v": target_v,
                        "pkv_t": pkv_t, "nkv_t": nkv_t,
                        "curve": curve, "b_obj": b_obj, "attr": attr
                    }

                cache[plug] = {"frames": frames, "data": f_data}
            except Exception: pass
            
        return cache

    @staticmethod
    def apply_tool(tool_name, cache, percentage, autokey=False):
        pct = percentage / 100.0
        abs_pct = abs(pct)
        
        for plug, cdata in cache.items():
            if plug == "__anim_layer__": continue
            frames = cdata["frames"]
            fdata = cdata["data"]
            if not frames: continue

            values = [fdata[f]["v"] for f in frames]
            avg = sum(values) / len(values) if values else 0

            dur = 0
            if tool_name in ["Linearize", "Ease In/Out"] and len(frames) > 1:
                start_f, end_f = frames[0], frames[-1]
                start_v, end_v = fdata[start_f]["v"], fdata[end_f]["v"]
                dur = end_f - start_f

            for f in frames:
                orig_v = fdata[f]["v"]
                new_v = orig_v

                if tool_name == "Tweener":
                    target = fdata[f]["nkv"] if pct > 0 else fdata[f]["pkv"]
                    new_v = orig_v + (target - orig_v) * abs_pct
                elif tool_name == "Neighbor":
                    global_pkv = fdata[frames[0]]["pkv"]
                    global_nkv = fdata[frames[-1]]["nkv"]
                    target = global_nkv if pct > 0 else global_pkv
                    new_v = orig_v + (target - orig_v) * abs_pct
                elif tool_name == "Push / Pull":
                    velocity = orig_v - fdata[f]["pfv"]
                    if abs(velocity) < 0.0001:
                        velocity = orig_v - fdata[f]["pkv"]
                    new_v = orig_v + (velocity * pct * 4.0)
                elif tool_name == "Scale Avg":
                    new_v = avg + ((orig_v - avg) * (1.0 + pct))
                elif tool_name == "Linearize":
                    if len(frames) > 1 and dur > 0:
                        ratio = (f - start_f) / float(dur)
                        linear_val = start_v + ((end_v - start_v) * ratio)
                        new_v = orig_v + ((linear_val - orig_v) * max(0, pct))
                    elif len(frames) == 1:
                        p_t, n_t = fdata[f]["pkv_t"], fdata[f]["nkv_t"]
                        if p_t != f and n_t != f and n_t > p_t:
                            ratio = (f - p_t) / float(n_t - p_t)
                            linear_val = fdata[f]["pkv"] + ((fdata[f]["nkv"] - fdata[f]["pkv"]) * ratio)
                            new_v = orig_v + ((linear_val - orig_v) * max(0, pct))
                elif tool_name == "Ease In/Out":
                    if len(frames) > 1 and dur > 0:
                        ratio = (f - start_f) / float(dur)
                        if pct < 0: target_v = start_v + (end_v - start_v) * (ratio ** 3)
                        else:       target_v = start_v + (end_v - start_v) * (1.0 - ((1.0 - ratio) ** 3))
                        new_v = orig_v + ((target_v - orig_v) * abs_pct)
                    elif len(frames) == 1:
                        p_t, n_t = fdata[f]["pkv_t"], fdata[f]["nkv_t"]
                        if p_t != f and n_t != f and n_t > p_t:
                            ratio = (f - p_t) / float(n_t - p_t)
                            if pct < 0: target_v = fdata[f]["pkv"] + ((fdata[f]["nkv"] - fdata[f]["pkv"]) * (ratio ** 3))
                            else:       target_v = fdata[f]["pkv"] + ((fdata[f]["nkv"] - fdata[f]["pkv"]) * (1.0 - ((1.0 - ratio) ** 3)))
                            new_v = orig_v + ((target_v - orig_v) * abs_pct)
                elif tool_name == "Smooth":
                    if len(frames) > 1:
                        idx = frames.index(f)
                        val_prev = values[idx-1] if idx > 0 else fdata[f]["pkv"]
                        val_next = values[idx+1] if idx < len(frames)-1 else fdata[f]["nkv"]
                        smoothed = (val_prev + orig_v + val_next) / 3.0
                        new_v = orig_v + ((smoothed - orig_v) * max(0, pct))
                    elif len(frames) == 1:
                        smoothed = (fdata[f]["pkv"] + orig_v + fdata[f]["nkv"]) / 3.0
                        new_v = orig_v + ((smoothed - orig_v) * max(0, pct))
                elif tool_name in ["Blend to Default", "Mirror Blend"]:
                    new_v = orig_v + ((fdata[f]["target_v"] - orig_v) * max(0, pct))

                curve = fdata[f]["curve"]
                if curve:
                    for kp in curve.keyframe_points:
                        if abs(kp.co.x - f) < 0.001:
                            kp.co.y = new_v
                            kp.handle_left.y = new_v
                            kp.handle_right.y = new_v
                            break
                    curve.update()

    @staticmethod
    def action_euler_filter(cache):
        """Native Blender Euler Filter implementation to prevent Gimbal Lock."""
        for plug, cdata in cache.items():
            if plug == "__anim_layer__": continue
            if "rx" in plug or "ry" in plug or "rz" in plug or "rotate" in plug.lower():
                frames = cdata["frames"]
                if not frames: continue
                
                curve = cdata["data"][frames[0]]["curve"]
                if curve:
                    prev_y = None
                    for kp in sorted(curve.keyframe_points, key=lambda k: k.co.x):
                        if prev_y is not None:
                            diff = kp.co.y - prev_y
                            if abs(diff) > math.pi:
                                kp.co.y -= round(diff / (2 * math.pi)) * 2 * math.pi
                                kp.handle_left.y -= round(diff / (2 * math.pi)) * 2 * math.pi
                                kp.handle_right.y -= round(diff / (2 * math.pi)) * 2 * math.pi
                        prev_y = kp.co.y
                    curve.update()