# ARTools/anim/anim_math.py
import maya.cmds as cmds

class AnimMath:
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

        q_args = {}
        if anim_layer: q_args["animLayer"] = anim_layer

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
                    frames = cmds.keyframe(plug, time=(context["start"], context["end"]), q=True, timeChange=True) or []
                else:
                    if context.get("has_cb_attrs") and active_tool in ["Smooth", "Linearize", "Scale Avg", "Ease In/Out", "Blend to Default", "Mirror Blend"]:
                        frames = cmds.keyframe(plug, q=True, timeChange=True) or []
                    else:
                        frames = [context["current"]]

                if not frames:
                    if not context["has_range"]: frames = [context["current"]]
                    else: continue

                frames = sorted(list(set(frames)))
                
                # STRICT LAYER ISOLATION: Initialize a curve on the layer if it doesn't exist yet
                crvs = cmds.keyframe(plug, q=True, name=True, **q_args)
                if not crvs:
                    try:
                        cmds.setKeyframe(plug, time=(context["current"], context["current"]), **q_args)
                        crvs = cmds.keyframe(plug, q=True, name=True, **q_args)
                    except: pass
                    
                if not crvs: continue 
                curve = crvs[0]
                
                f_data = {}
                for f in frames:
                    try: orig_v = cmds.keyframe(curve, q=True, time=(f, f), eval=True)[0]
                    except: orig_v = 0.0
                    
                    try: pkv_t = cmds.findKeyframe(curve, time=(f, f), which="previous")
                    except: pkv_t = f
                    try: nkv_t = cmds.findKeyframe(curve, time=(f, f), which="next")
                    except: nkv_t = f
                    
                    if pkv_t is None: pkv_t = f
                    if nkv_t is None: nkv_t = f
                    
                    try: pkv = cmds.keyframe(curve, q=True, time=(pkv_t, pkv_t), eval=True)[0]
                    except: pkv = orig_v
                    try: nkv = cmds.keyframe(curve, q=True, time=(nkv_t, nkv_t), eval=True)[0]
                    except: nkv = orig_v
                    try: pfv = cmds.keyframe(curve, q=True, time=(f-1, f-1), eval=True)[0]
                    except: pfv = orig_v
                    try: nfv = cmds.keyframe(curve, q=True, time=(f+1, f+1), eval=True)[0]
                    except: nfv = orig_v

                    target_v = orig_v

                    if active_tool == "Blend to Default":
                        is_override_layer = bool(anim_layer) and cmds.animLayer(anim_layer, q=True, override=True)
                        if anim_layer and not is_override_layer:
                            target_v = 0.0 # Additive layers blend back to "no contribution"
                        elif snap and "defaults" in snap and attr in snap["defaults"]:
                            target_v = snap["defaults"][attr]
                        else:
                            default_list = cmds.attributeQuery(attr, node=node, listDefault=True) or []
                            if default_list:
                                target_v = default_list[0]
                            else:
                                target_v = 1.0 if attr in ["sx", "sy", "sz", "scaleX", "scaleY", "scaleZ"] else 0.0

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
                        
                        partner_plug = f"{partner_node}.{mapped_attr}"
                        if cmds.objExists(partner_plug):
                            p_crvs = cmds.keyframe(partner_plug, q=True, name=True, **q_args)
                            if p_crvs:
                                try: target_v = cmds.keyframe(p_crvs[0], q=True, time=(f, f), eval=True)[0] * mult
                                except: pass
                            else:
                                target_v = 0.0 if anim_layer else orig_v

                    f_data[f] = {
                        "v": orig_v, "pkv": pkv, "nkv": nkv, 
                        "pfv": pfv, "nfv": nfv, "target_v": target_v,
                        "pkv_t": pkv_t, "nkv_t": nkv_t,
                        "curve": curve
                    }

                cache[plug] = {"frames": frames, "data": f_data}
            except Exception: pass
            
        return cache

    @staticmethod
    def apply_tool(tool_name, cache, percentage, autokey=False):
        pct = percentage / 100.0
        abs_pct = abs(pct)
        current_time = cmds.currentTime(q=True)
        
        anim_layer = cache.get("__anim_layer__")
        k_set_args = {}
        if anim_layer: k_set_args["animLayer"] = anim_layer

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
                    # Write the math directly to the isolated layer curve.
                    # Do NOT also setKeyframe() the plug afterwards -- with an
                    # anim layer active, Maya re-derives the curve value from
                    # the blended plug value and overwrites what we just wrote.
                    cmds.keyframe(curve, edit=True, time=(f, f), absolute=True, valueChange=new_v)

                    if f == current_time:
                        cmds.dgdirty(plug)

    @staticmethod
    def action_euler_filter(cache):
        anim_layer = cache.get("__anim_layer__")
        curves_to_filter = [plug for plug in cache.keys() if plug != "__anim_layer__" and 'rotate' in plug.lower()]
        
        if curves_to_filter:
            try: 
                sel_curves = cmds.keyframe(q=True, sl=True, name=True) or []
                sel_keys = {}
                for c in sel_curves:
                    times = cmds.keyframe(c, q=True, sl=True, timeChange=True)
                    if times:
                        sel_keys[c] = list(set(times))

                target_curves = []
                q_args = {}
                if anim_layer: q_args["animLayer"] = anim_layer
                
                for plug in curves_to_filter:
                    crvs = cmds.keyframe(plug, q=True, name=True, **q_args)
                    if crvs: target_curves.extend(crvs)

                if target_curves:
                    cmds.filterCurve(list(set(target_curves)))
                
                cmds.selectKey(clear=True)
                for c in sel_curves:
                    if c in sel_keys and sel_keys[c]:
                        for t in sel_keys[c]:
                            try: cmds.selectKey(c, add=True, time=(t, t))
                            except: pass
                    else:
                        try: cmds.selectKey(c, add=True)
                        except: pass
            except Exception: 
                pass