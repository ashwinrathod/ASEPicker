# ASEPicker/anim/anim_math.py
import maya.cmds as cmds

class AnimMath:
    @staticmethod
    def build_cache(context, active_tool):
        cache = {}
        plugs = context.get("plugs", [])
        if not plugs: return cache

        for plug in plugs:
            try:
                if context.get("ge_frames") and plug in context["ge_frames"]:
                    frames = context["ge_frames"][plug]
                elif context["has_range"]:
                    frames = cmds.keyframe(plug, time=(context["start"], context["end"]), q=True, timeChange=True) or []
                else:
                    if active_tool in ["Smooth", "Linearize", "Scale Avg", "Ease In/Out"]:
                        frames = cmds.keyframe(plug, q=True, timeChange=True) or []
                    else:
                        frames = [context["current"]]

                if not frames:
                    if not context["has_range"]: frames = [context["current"]]
                    else: continue

                frames = sorted(list(set(frames)))
                f_data = {}
                
                for f in frames:
                    orig_v = cmds.getAttr(plug, time=f)

                    try: pkv_t = cmds.findKeyframe(plug, time=(f, f), which="previous")
                    except: pkv_t = f
                    try: nkv_t = cmds.findKeyframe(plug, time=(f, f), which="next")
                    except: nkv_t = f

                    pkv = cmds.getAttr(plug, time=pkv_t) if pkv_t != f else orig_v
                    nkv = cmds.getAttr(plug, time=nkv_t) if nkv_t != f else orig_v

                    pfv = cmds.getAttr(plug, time=f-1)
                    nfv = cmds.getAttr(plug, time=f+1)

                    f_data[f] = {"v": orig_v, "pkv": pkv, "nkv": nkv, "pfv": pfv, "nfv": nfv}

                cache[plug] = {"frames": frames, "data": f_data}
            except Exception: pass
            
        return cache

    @staticmethod
    def apply_tool(tool_name, cache, percentage):
        pct = percentage / 100.0
        abs_pct = abs(pct)
        
        # --- CRITICAL FIX 1: Fetch the Current Time ---
        current_time = cmds.currentTime(q=True)
        # ----------------------------------------------

        for plug, cdata in cache.items():
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
                    d = orig_v - fdata[f]["pfv"]
                    new_v = orig_v + (d * pct)

                elif tool_name == "Scale Avg":
                    d = orig_v - avg
                    new_v = avg + (d * (1.0 + pct))

                elif tool_name == "Linearize":
                    if len(frames) > 1 and dur > 0:
                        ratio = (f - start_f) / float(dur)
                        linear_val = start_v + ((end_v - start_v) * ratio)
                        new_v = orig_v + ((linear_val - orig_v) * max(0, pct))

                elif tool_name == "Ease In/Out":
                    if len(frames) > 1 and dur > 0:
                        ratio = (f - start_f) / float(dur)
                        if pct < 0: 
                            target_v = start_v + (end_v - start_v) * (ratio ** 3)
                        else:       
                            target_v = start_v + (end_v - start_v) * (1.0 - ((1.0 - ratio) ** 3))
                        new_v = orig_v + ((target_v - orig_v) * abs_pct)

                elif tool_name == "Smooth":
                    idx = frames.index(f)
                    if 0 < idx < len(frames) - 1:
                        smoothed = (values[idx-1] + values[idx] + values[idx+1]) / 3.0
                        new_v = orig_v + ((smoothed - orig_v) * max(0, pct))

                # --- CRITICAL FIX 2: Live Viewport Push ---
                try: 
                    cmds.setKeyframe(plug, time=(f, f), value=new_v)
                except: pass
                
                # If we are parked on this exact frame, FORCE the rig to evaluate the new value!
                if f == current_time:
                    try: cmds.setAttr(plug, new_v)
                    except: pass
                # ------------------------------------------

    @staticmethod
    def action_euler_filter(cache):
        curves_to_filter = [plug for plug in cache.keys() if 'rotate' in plug.lower()]
        if curves_to_filter:
            try: cmds.filterCurve(curves_to_filter)
            except: pass