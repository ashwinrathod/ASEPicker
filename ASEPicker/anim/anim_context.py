# ASEPicker/anim/anim_context.py
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
            "ge_frames": {} # Graph editor specific frames
        }
        
        # 1. GRAPH EDITOR PRIORITY
        if cmds.window('graphEditor1Window', q=True, exists=True) and cmds.window('graphEditor1Window', q=True, visible=True):
            sel_curves = cmds.keyframe(q=True, sl=True, name=True) or []
            if sel_curves:
                for c in sel_curves:
                    plugs = cmds.listConnections(c + ".output", plugs=True) or []
                    if plugs:
                        frames = cmds.keyframe(c, q=True, sl=True, timeChange=True) or []
                        if frames:
                            context["plugs"].append(plugs[0])
                            context["ge_frames"][plugs[0]] = list(set(frames))
                if context["plugs"]:
                    context["has_range"] = True
                    return context

        # 2. VIEWPORT / TIMELINE
        sel = cmds.ls(sl=True) or []
        if not sel: return context

        try:
            a_time_slider = mel.eval('$tmpVar=$gPlayBackSlider')
            if cmds.timeControl(a_time_slider, q=True, rangeVisible=True):
                tr = cmds.timeControl(a_time_slider, q=True, rangeArray=True)
                context["start"] = tr[0]
                context["end"] = tr[1] - 1
                context["has_range"] = True
        except: pass

        # Find attributes
        cb_attrs = []
        try: cb_attrs = cmds.channelBox('mainChannelBox', q=True, selectedMainAttributes=True) or []
        except: pass

        for obj in sel:
            attrs = cb_attrs
            if not attrs:
                keyable = cmds.listAttr(obj, k=True, u=True) or []
                attrs = [a for a in keyable if a.startswith('translate') or a.startswith('rotate')]
                if not attrs: attrs = keyable

            for a in attrs: context["plugs"].append(f"{obj}.{a}")

        return context