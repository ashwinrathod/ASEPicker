# ARTools/anim/fake_parent.py
import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import math
from PySide6 import QtCore

class FakeParentManager:
    def __init__(self, button):
        self.button = button
        self.parent_node = None
        self.children_data = {}
        self.job_id = None
        
    def toggle(self, modifiers=0):
        is_shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        if self.is_active():
            self.apply(bake=is_shift)
        else:
            self.capture()
            
    def is_active(self):
        return self.parent_node is not None and len(self.children_data) > 0
        
    def _get_matrix(self, node):
        return om.MMatrix(cmds.xform(node, q=True, matrix=True, ws=True))
        
    def _set_matrix(self, node, mat):
        try:
            # Direct matrix application is the fastest and most accurate
            cmds.xform(node, matrix=list(mat), ws=True)
        except Exception:
            # Safe Fallback for controls with locked scales/shears
            trans = om.MTransformationMatrix(mat)
            pos = trans.translation(om.MSpace.kWorld)
            rot = trans.rotation(asQuaternion=False)
            rot.reorderIt(cmds.getAttr(f"{node}.rotateOrder"))
            rot_deg = [math.degrees(rot.x), math.degrees(rot.y), math.degrees(rot.z)]
            try: cmds.move(pos.x, pos.y, pos.z, node, ws=True, absolute=True)
            except: pass
            try: cmds.rotate(rot_deg[0], rot_deg[1], rot_deg[2], node, ws=True, absolute=True)
            except: pass

    def capture(self):
        sel = cmds.ls(sl=True)
        if len(sel) < 2:
            cmds.warning("[ARTools] Fake Parent: Select the Parent first, then one or more Children.")
            return
            
        self.parent_node = sel[0]
        self.children_data = {}
        
        # Calculate Offset: LocalOffset = ChildWorld * ParentWorld.inverse
        p_inv = self._get_matrix(self.parent_node).inverse()
        for child in sel[1:]:
            c_mat = self._get_matrix(child)
            offset = c_mat * p_inv
            self.children_data[child] = offset
            
        self._set_active_ui(True)
        
        if self.job_id:
            try: cmds.scriptJob(kill=self.job_id, force=True)
            except: pass
            
        # Hook into Maya to track selection validation
        self.job_id = cmds.scriptJob(e=["SelectionChanged", self.on_selection_changed], protected=True)
        cmds.inViewMessage(amg=f"<span style='color:#4CAF50; font-size:16px;'>Fake Parent Armed</span><br>Parent: {self.parent_node.split(':')[-1]}", pos="midCenter", fade=True)
        
    def apply(self, bake=False):
        if not self.is_active(): return
        
        if bake:
            self._bake_timeline()
        else:
            cmds.undoInfo(openChunk=True, chunkName="ARTools_FakeParent")
            try:
                p_mat = self._get_matrix(self.parent_node)
                autokey = cmds.autoKeyframe(q=True, state=True)
                for child, offset in self.children_data.items():
                    if cmds.objExists(child):
                        new_mat = offset * p_mat
                        self._set_matrix(child, new_mat)
                        if autokey or cmds.keyframe(child, at=["translate", "rotate"], q=True, keyframeCount=True):
                            cmds.setKeyframe(child, at=["translate", "rotate"])
            finally:
                cmds.undoInfo(closeChunk=True)
            cmds.inViewMessage(amg="<span style='color:#5285a6; font-size:16px;'>Fake Parent Applied</span>", pos="midCenter", fade=True)
    
    def _bake_timeline(self):
        start_t = end_t = cmds.currentTime(q=True)
        
        try:
            a_time_slider = mel.eval('$tmpVar=$gPlayBackSlider')
            if cmds.timeControl(a_time_slider, q=True, rangeVisible=True):
                tr = cmds.timeControl(a_time_slider, q=True, rangeArray=True)
                if tr and (tr[1] - tr[0]) > 1:
                    start_t = tr[0]
                    end_t = tr[1] - 1
        except: pass
        
        if start_t == end_t:
            start_t = cmds.playbackOptions(q=True, minTime=True)
            end_t = cmds.playbackOptions(q=True, maxTime=True)
            
        frames = [float(f) for f in range(int(start_t), int(end_t) + 1)]
        
        cmds.undoInfo(openChunk=True, chunkName="ARTools_FakeParentBake")
        
        # Suspend UI for extreme calculation speed
        cmds.refresh(suspend=True)
        current_eval_mode = cmds.evaluationManager(q=True, mode=True)[0]
        if current_eval_mode != "off": cmds.evaluationManager(mode='off')
        
        try:
            for f in frames:
                cmds.currentTime(f)
                p_mat = self._get_matrix(self.parent_node)
                for child, offset in self.children_data.items():
                    if cmds.objExists(child):
                        new_mat = offset * p_mat
                        self._set_matrix(child, new_mat)
                        cmds.setKeyframe(child, at=["translate", "rotate"])
                        
            # Dynamic Euler Filter to prevent Gimbal Flips across the newly baked range
            for child in self.children_data.keys():
                if cmds.objExists(child):
                    rot_curves = [f"{child}.rotate{x}" for x in "XYZ"]
                    valid = [c for c in rot_curves if cmds.objExists(c) and not cmds.getAttr(c, lock=True)]
                    if valid:
                        try: cmds.filterCurve(valid)
                        except: pass
        finally:
            if current_eval_mode != "off": cmds.evaluationManager(mode=current_eval_mode)
            cmds.refresh(suspend=False)
            cmds.refresh(force=True)
            cmds.undoInfo(closeChunk=True)
            
        cmds.inViewMessage(amg=f"<span style='color:#5285a6; font-size:16px;'>Fake Parent Baked</span><br>{len(frames)} Frames", pos="midCenter", fade=True)
            
    def on_selection_changed(self):
        if not self.is_active(): return
        sel = cmds.ls(sl=True)
        
        # Rule: Any foreign selection wipes the tool
        if not sel:
            self.clear()
            return
            
        valid_nodes = set(self.children_data.keys())
        valid_nodes.add(self.parent_node)
        
        for s in sel:
            if s not in valid_nodes:
                self.clear()
                return
                
    def clear(self):
        self.parent_node = None
        self.children_data = {}
        if self.job_id:
            try: cmds.scriptJob(kill=self.job_id, force=True)
            except: pass
            self.job_id = None
        self._set_active_ui(False)
        
    def _set_active_ui(self, is_active):
        if not self.button: return
        if is_active:
            self.button.setStyleSheet("background: rgba(79, 184, 167, 100); border: 2px solid #4CAF50;")
        else:
            self.button.setStyleSheet("")