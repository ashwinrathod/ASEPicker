# ARTools/anim/anim_context.py
import maya.cmds as cmds
import maya.mel as mel

class AnimContext:
    @staticmethod
    def get_anim_targets():
        """Returns the exact plugs and time context for the Math Engine."""
        current = cmds.currentTime(q=True)
        context = {
            "plugs": [],
            "start": current,
            "end": current,
            "current": current,
            "has_range": False,
            "has_cb_attrs": False,
            "ge_frames": {} 
        }

        sel = cmds.ls(sl=True) or []
        if not sel: return context

        # 1. Check Channel Box Focus
        cb_attrs = []
        try: cb_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
        except: pass
        if cb_attrs: context["has_cb_attrs"] = True 

        # 2. Check Graph Editor Selection
        sel_curves = []
        if cmds.window('graphEditor1Window', q=True, exists=True) and cmds.window('graphEditor1Window', q=True, visible=True):
            sel_curves = cmds.keyframe(q=True, sl=True, name=True) or []

        # 3. Check Timeline Range
        try:
            a_time_slider = mel.eval('$tmpVar=$gPlayBackSlider')
            if cmds.timeControl(a_time_slider, q=True, rangeVisible=True):
                tr = cmds.timeControl(a_time_slider, q=True, rangeArray=True)
                if tr and (tr[1] - tr[0]) > 1:
                    context["start"] = tr[0]
                    context["end"] = tr[1] - 1
                    context["has_range"] = True
        except: pass

        # 4. Resolve Plugs (Penetrating Anim Layers securely)
        for obj in sel:
            attrs = cb_attrs if cb_attrs else (cmds.listAttr(obj, k=True, u=True) or [])
            for a in attrs:
                plug = f"{obj}.{a}"
                if not cmds.objExists(plug): continue

                if sel_curves:
                    # Sync Viewport plug directly to GE curve, bypassing layer obfuscation
                    plug_curves = cmds.keyframe(plug, q=True, name=True) or []
                    if any(c in sel_curves for c in plug_curves):
                        context["plugs"].append(plug)
                        frames = cmds.keyframe(plug, q=True, sl=True, timeChange=True) or []
                        if frames:
                            context["ge_frames"][plug] = list(set(frames))
                            context["has_range"] = True # Force range mode to process these exact frames
                else:
                    context["plugs"].append(plug)

        # 5. Failsafe Fallback
        # If the GE was open but its selection was stale/disconnected, force capture all viewport plugs
        if sel_curves and not context["plugs"]:
            for obj in sel:
                attrs = cb_attrs if cb_attrs else (cmds.listAttr(obj, k=True, u=True) or [])
                for a in attrs:
                    plug = f"{obj}.{a}"
                    if cmds.objExists(plug): context["plugs"].append(plug)

        return context