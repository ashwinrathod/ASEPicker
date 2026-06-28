import sys
import math
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

# --- CONFIGURATION ---
PLUGIN_NAME = "HyperTrail"
NODE_NAME = "hyperTrailMesh" 
NODE_ID = om.MTypeId(0x87310)
COMMAND_NAME = "spHyperTrail" 

_CALLBACKS = []

def maya_useNewAPI():
    pass

class HyperTrailNode(om.MPxNode):
    in_time = None
    in_matrix = None
    in_cam_matrix = None
    in_mode = None
    in_points = None
    in_cam_data = None
    in_source = None
    in_start_time = None
    in_pre = None
    in_post = None
    in_width = None
    in_color_pre = None
    in_color_post = None
    in_style = None
    in_show_keys = None
    in_spacing = None
    in_taper = None
    in_speed = None
    
    out_mesh = None

    def __init__(self):
        om.MPxNode.__init__(self)

    @classmethod
    def creator(cls):
        return cls()

    @classmethod
    def initialize(cls):
        tAttr = om.MFnTypedAttribute()
        mAttr = om.MFnMessageAttribute()
        nAttr = om.MFnNumericAttribute()
        uAttr = om.MFnUnitAttribute()
        matAttr = om.MFnMatrixAttribute()
        eAttr = om.MFnEnumAttribute()
        
        # --- ATTRIBUTES ---
        cls.in_style = eAttr.create("lineStyle", "ls", 0)
        eAttr.addField("Solid", 0)
        eAttr.addField("Dash", 1)
        eAttr.addField("Dot", 2)
        eAttr.keyable = True
        
        cls.in_show_keys = nAttr.create("showKeys", "sk", om.MFnNumericData.kBoolean, 0)
        nAttr.keyable = True
        
        cls.in_spacing = nAttr.create("spacingMode", "spc", om.MFnNumericData.kBoolean, 0)
        nAttr.keyable = True

        cls.in_taper = nAttr.create("taper", "tpr", om.MFnNumericData.kBoolean, 0)
        nAttr.keyable = True
        
        cls.in_speed = nAttr.create("speedColors", "spd", om.MFnNumericData.kBoolean, 0)
        nAttr.keyable = True
        
        cls.in_time = uAttr.create("time", "tm", om.MFnUnitAttribute.kTime, 0.0)
        cls.in_matrix = matAttr.create("inputMatrix", "imat")
        matAttr.storable = False; matAttr.connectable = True
        
        cls.in_cam_matrix = matAttr.create("cameraMatrix", "cmat")
        matAttr.storable = False; matAttr.connectable = True
        
        cls.in_mode = eAttr.create("trailMode", "mode", 0)
        eAttr.addField("World", 0); eAttr.addField("Camera", 1); eAttr.keyable = True

        cls.in_points = tAttr.create("trailData", "td", om.MFnData.kVectorArray)
        tAttr.storable = True; tAttr.hidden = True
        cls.in_cam_data = tAttr.create("camData", "cd", om.MFnData.kMatrixArray)
        tAttr.storable = True; tAttr.hidden = True
        
        cls.in_source = mAttr.create("sourceLink", "sl")
        cls.in_start_time = nAttr.create("startTime", "st", om.MFnNumericData.kDouble, 0.0)
        
        cls.in_pre = nAttr.create("preFrame", "pre", om.MFnNumericData.kInt, 0)
        nAttr.setMin(0); nAttr.keyable = True
        cls.in_post = nAttr.create("postFrame", "post", om.MFnNumericData.kInt, 0)
        nAttr.setMin(0); nAttr.keyable = True
        cls.in_width = nAttr.create("width", "w", om.MFnNumericData.kDouble, 0.3)
        nAttr.setMin(0.01); nAttr.keyable = True

        cls.in_color_pre = nAttr.create("colorPre", "cpre", om.MFnNumericData.k3Float)
        nAttr.usedAsColor = True; nAttr.default = (0.0, 0.0, 1.0); nAttr.keyable = True
        cls.in_color_post = nAttr.create("colorPost", "cpost", om.MFnNumericData.k3Float)
        nAttr.usedAsColor = True; nAttr.default = (1.0, 1.0, 0.0); nAttr.keyable = True

        cls.out_mesh = tAttr.create("outputMesh", "out", om.MFnData.kMesh)
        tAttr.writable = False; tAttr.storable = False

        cls.addAttribute(cls.in_style); cls.addAttribute(cls.in_show_keys)
        cls.addAttribute(cls.in_spacing); cls.addAttribute(cls.in_taper); cls.addAttribute(cls.in_speed)
        cls.addAttribute(cls.in_time); cls.addAttribute(cls.in_matrix); cls.addAttribute(cls.in_cam_matrix)
        cls.addAttribute(cls.in_mode); cls.addAttribute(cls.in_points); cls.addAttribute(cls.in_cam_data)
        cls.addAttribute(cls.in_source); cls.addAttribute(cls.in_start_time)
        cls.addAttribute(cls.in_pre); cls.addAttribute(cls.in_post); cls.addAttribute(cls.in_width)
        cls.addAttribute(cls.in_color_pre); cls.addAttribute(cls.in_color_post); cls.addAttribute(cls.out_mesh)
        
        cls.attributeAffects(cls.in_style, cls.out_mesh)
        cls.attributeAffects(cls.in_show_keys, cls.out_mesh)
        cls.attributeAffects(cls.in_spacing, cls.out_mesh)
        cls.attributeAffects(cls.in_taper, cls.out_mesh)
        cls.attributeAffects(cls.in_speed, cls.out_mesh)
        cls.attributeAffects(cls.in_time, cls.out_mesh)
        cls.attributeAffects(cls.in_matrix, cls.out_mesh)
        cls.attributeAffects(cls.in_cam_matrix, cls.out_mesh)
        cls.attributeAffects(cls.in_mode, cls.out_mesh)
        cls.attributeAffects(cls.in_points, cls.out_mesh)
        cls.attributeAffects(cls.in_pre, cls.out_mesh)
        cls.attributeAffects(cls.in_post, cls.out_mesh)
        cls.attributeAffects(cls.in_width, cls.out_mesh)
        cls.attributeAffects(cls.in_color_pre, cls.out_mesh)
        cls.attributeAffects(cls.in_color_post, cls.out_mesh)

    def compute(self, plug, data):
        if plug != self.out_mesh: return None
 
        # --- GATHER DATA ---
        h_pts = data.inputValue(self.in_points)
        pts_data = h_pts.data()
        full_points = om.MFnVectorArrayData(pts_data).array() if not pts_data.isNull() else om.MVectorArray()
 
        if len(full_points) < 2: data.setClean(plug); return
 
        full_cams = []
        mode = data.inputValue(self.in_mode).asShort()
        if mode == 1:
            h_cams = data.inputValue(self.in_cam_data)
            m_obj = h_cams.data()
            if not m_obj.isNull():
                full_cams = om.MFnMatrixArrayData(m_obj).array()
 
        cur_time_val = data.inputValue(self.in_time).asTime().value
        start_time = data.inputValue(self.in_start_time).asDouble()
        cur_idx = int(cur_time_val - start_time)
 
        # Live Inject — MDataHandle.asMatrix() is valid; no guard needed here
        if 0 <= cur_idx < len(full_points):
            mat_obj = data.inputValue(self.in_matrix).asMatrix()
            full_points[cur_idx] = om.MVector(mat_obj[12], mat_obj[13], mat_obj[14])
            if mode == 1 and cur_idx < len(full_cams):
                full_cams[cur_idx] = data.inputValue(self.in_cam_matrix).asMatrix()
 
        pre = data.inputValue(self.in_pre).asInt()
        post = data.inputValue(self.in_post).asInt()
        
        start_idx = max(0, min(cur_idx - pre if pre > 0 else 0, len(full_points)-1))
        end_idx = max(start_idx, min(cur_idx + post + 1 if post > 0 else len(full_points), len(full_points)))
        
        # --- KEYFRAME DETECTION (Deep Scan) ---
        show_keys = data.inputValue(self.in_show_keys).asBool()
        key_frames = set() 
        
        if show_keys:
            this_node = self.thisMObject()
            fn_this = om.MFnDependencyNode(this_node)
            p_src = fn_this.findPlug("sourceLink", False)
            
            if p_src.isConnected:
                src_node = p_src.source().node()
                fn_src = om.MFnDependencyNode(src_node)
                keys = cmds.keyframe(fn_src.name(), q=True, tc=True) or []
                for k in keys:
                    key_frames.add(int(round(k)))
 
        # --- SPACE CALC ---
        final_points = []
        final_indices = []
        
        if mode == 1 and len(full_cams) >= len(full_points):
            current_cam_mat = data.inputValue(self.in_cam_matrix).asMatrix()
            inv_cams = [m.inverse() for m in full_cams]
            
            for i in range(start_idx, end_idx):
                pt_world = om.MPoint(full_points[i])
                if i < len(inv_cams):
                    pt_local = pt_world * inv_cams[i]
                    final_points.append(pt_local * current_cam_mat)
                else: final_points.append(pt_world)
                final_indices.append(i)
        else:
            for i in range(start_idx, end_idx):
                final_points.append(om.MPoint(full_points[i])); final_indices.append(i)
 
        if len(final_points) < 2: data.setClean(plug); return
 
        # --- MESH GENERATION ---
        width = data.inputValue(self.in_width).asDouble()
        style = data.inputValue(self.in_style).asShort() 
 
        radius = width * 0.5
        vertices = om.MPointArray()
        p_counts = om.MIntArray()
        p_connects = om.MIntArray()
        
        c_pre = om.MColor(data.inputValue(self.in_color_pre).asFloat3())
        c_post = om.MColor(data.inputValue(self.in_color_post).asFloat3())
        c_white = om.MColor((1.0, 1.0, 1.0)) 
        
        v_colors = om.MColorArray()
        v_color_ids = om.MIntArray()
        up = om.MVector(0,1,0)
 
        stride = 8 if style == 2 else 4
 
        is_spacing = data.inputValue(self.in_spacing).asBool()
        is_taper = data.inputValue(self.in_taper).asBool()
        is_speed = data.inputValue(self.in_speed).asBool()
 
        # 1. VERTICES
        for i, p in enumerate(final_points):
            if i < len(final_points) - 1: t = final_points[i+1] - final_points[i]
            elif i > 0: t = final_points[i] - final_points[i-1]
            else: t = om.MVector(1,0,0)
            
            if t.length() > 0.0001: t.normalize()
            else: t = om.MVector(1,0,0)
 
            real_idx = final_indices[i]
 
            # --- ADVANCED: Comet Tapering Math ---
            current_radius = radius
            if is_taper:
                dist_from_cur = abs(real_idx - cur_idx)
                max_d = max(pre, post)
                if max_d == 0: max_d = 1.0 # Prevent div zero
                fade = 1.0 - (dist_from_cur / float(max_d))
                fade = max(0.01, min(1.0, fade))
                fade = fade * fade * (3.0 - 2.0 * fade) # Smoothstep curve
                current_radius = radius * fade
 
            side = (t ^ up)
            if side.length() < 0.001: side = om.MVector(1,0,0)
            side = side.normal() * current_radius
            norm = (t ^ side).normal() * current_radius
 
            # --- ADVANCED: Color Processing ---
            if is_speed:
                # Velocity mapping: Blue (Slow) -> Red (Fast)
                speed = 0.0
                if i > 0: speed = (p - final_points[i-1]).length()
                ratio = max(0.0, min(speed / 3.0, 1.0)) # 3.0 is the hot speed threshold
                this_color = om.MColor((ratio, 0.0, 1.0 - ratio))
            elif is_spacing:
                # Zebra Pattern Modulo
                this_color = c_pre if (real_idx % 2 == 0) else c_post
            else:
                # Default Timeline Split
                this_color = c_pre if real_idx <= cur_idx else c_post
 
            if style == 2: # Dot (Box)
                fwd = t * current_radius 
                p_b = p - fwd
                vertices.append(p_b + norm); vertices.append(p_b + side)
                vertices.append(p_b - norm); vertices.append(p_b - side)
                p_f = p + fwd
                vertices.append(p_f + norm); vertices.append(p_f + side)
                vertices.append(p_f - norm); vertices.append(p_f - side)
                for _ in range(8): v_colors.append(this_color); v_color_ids.append(len(v_colors)-1)
            else: # Tube
                vertices.append(p + norm); vertices.append(p + side)
                vertices.append(p - norm); vertices.append(p - side)
                for _ in range(4): v_colors.append(this_color); v_color_ids.append(len(v_colors)-1)
 
        # 2. TOPOLOGY
        loop_end = len(final_points) if style == 2 else len(final_points) - 1
        
        for i in range(loop_end):
            base = i * stride
            
            if style == 2: # DOT (Box)
                # Reordered Quad vertices so normals point OUTWARD for X-Ray
                p_counts.append(4); p_connects.append(base+4); p_connects.append(base+5); p_connects.append(base+6); p_connects.append(base+7) 
                p_counts.append(4); p_connects.append(base+3); p_connects.append(base+2); p_connects.append(base+1); p_connects.append(base+0)
                p_counts.append(4); p_connects.append(base+0); p_connects.append(base+1); p_connects.append(base+5); p_connects.append(base+4)
                p_counts.append(4); p_connects.append(base+1); p_connects.append(base+2); p_connects.append(base+6); p_connects.append(base+5)
                p_counts.append(4); p_connects.append(base+2); p_connects.append(base+3); p_connects.append(base+7); p_connects.append(base+6)
                p_counts.append(4); p_connects.append(base+3); p_connects.append(base+0); p_connects.append(base+4); p_connects.append(base+7)
                continue
 
            if style == 1: # DASH
                if (i % 2 != 0): continue
                next_b = (i+1) * stride
                for j in range(4):
                    nj = (j+1)%4
                    p_counts.append(4)
                    # Reordered Quad vertices so normals point OUTWARD for X-Ray
                    p_connects.append(base+j); p_connects.append(next_b+j)
                    p_connects.append(next_b+nj); p_connects.append(base+nj)
                continue
 
            # SOLID (Standard Tube)
            next_b = (i+1) * stride
            for j in range(4):
                nj = (j+1)%4
                p_counts.append(4)
                # Reordered Quad vertices so normals point OUTWARD for X-Ray
                p_connects.append(base+j); p_connects.append(next_b+j)
                p_connects.append(next_b+nj); p_connects.append(base+nj)
 
        # 3. KEYFRAME MARKERS
        if show_keys:
            for i, p in enumerate(final_points):
                abs_frame = int(round(start_time + final_indices[i]))
                
                if abs_frame in key_frames:
                    # Dynamically shrink keys alongside taper, but keep at least 25% size
                    local_radius = radius
                    if is_taper:
                        dist_from_cur = abs(final_indices[i] - cur_idx)
                        max_d = max(pre, post) if max(pre, post) > 0 else 1.0
                        fade = max(0.25, 1.0 - (dist_from_cur / float(max_d))) 
                        local_radius = radius * fade
                        
                    key_radius = local_radius * 4.0
                    base_k = len(vertices)
                    
                    t = om.MVector(1,0,0) 
                    if i < len(final_points)-1: t = final_points[i+1] - p
                    elif i > 0: t = p - final_points[i-1]
                    if t.length() > 0.001: t.normalize()
 
                    side = (t ^ up)
                    if side.length() < 0.001: side = om.MVector(0,0,1)
                    side = side.normal() * key_radius
                    norm = (t ^ side).normal() * key_radius
                    fwd = t * key_radius
                    
                    # Box 8 Verts
                    p_b = p - fwd
                    vertices.append(p_b + norm); vertices.append(p_b + side)
                    vertices.append(p_b - norm); vertices.append(p_b - side)
                    p_f = p + fwd
                    vertices.append(p_f + norm); vertices.append(p_f + side)
                    vertices.append(p_f - norm); vertices.append(p_f - side)
                    
                    for _ in range(8): v_colors.append(c_white); v_color_ids.append(len(v_colors)-1)
                    
                    # Reordered Box vertices so normals point OUTWARD for X-Ray
                    p_counts.append(4); p_connects.append(base_k+4); p_connects.append(base_k+5); p_connects.append(base_k+6); p_connects.append(base_k+7)
                    p_counts.append(4); p_connects.append(base_k+3); p_connects.append(base_k+2); p_connects.append(base_k+1); p_connects.append(base_k+0)
                    p_counts.append(4); p_connects.append(base_k+0); p_connects.append(base_k+1); p_connects.append(base_k+5); p_connects.append(base_k+4)
                    p_counts.append(4); p_connects.append(base_k+1); p_connects.append(base_k+2); p_connects.append(base_k+6); p_connects.append(base_k+5)
                    p_counts.append(4); p_connects.append(base_k+2); p_connects.append(base_k+3); p_connects.append(base_k+7); p_connects.append(base_k+6)
                    p_counts.append(4); p_connects.append(base_k+3); p_connects.append(base_k+0); p_connects.append(base_k+4); p_connects.append(base_k+7)
 
        new_mesh = om.MFnMeshData().create()
        fn_mesh = om.MFnMesh()
        fn_mesh.create(vertices, p_counts, p_connects, parent=new_mesh)
        fn_mesh.setVertexColors(v_colors, v_color_ids)
        
        out_h = data.outputValue(self.out_mesh)
        out_h.setMObject(new_mesh)
        data.setClean(plug)

def update_neighbors_live(trail_node, window=5):
    fn = om.MFnDependencyNode(trail_node)
    p_data = fn.findPlug("trailData", False)
    p_mat = fn.findPlug("inputMatrix", False)
    p_start = fn.findPlug("startTime", False)
    
    obj_data = p_data.asMObject()
    points = om.MFnVectorArrayData(obj_data).array()
    if len(points) == 0: return
 
    start_t = p_start.asDouble()
    cur_t = oma.MAnimControl.currentTime().value
    cur_idx = int(cur_t - start_t)
    
    w_start = max(0, cur_idx - window)
    w_end = min(len(points), cur_idx + window + 1)
    
    src_plug = None
    if p_mat.isConnected: src_plug = p_mat.source()
 
    for i in range(w_start, w_end):
        mat = None
        if i == cur_idx:
            m_obj = p_mat.asMObject()
            if not m_obj.isNull():
                mat = om.MFnMatrixData(m_obj).matrix()
        else:
            frame_time = start_t + i
            ctx = om.MDGContext(om.MTime(float(frame_time)))
            if src_plug:
                m_obj = src_plug.asMObject(ctx)
                if not m_obj.isNull():
                    mat = om.MFnMatrixData(m_obj).matrix()
            else:
                m_obj = p_mat.asMObject(ctx)
                if not m_obj.isNull():
                    mat = om.MFnMatrixData(m_obj).matrix()
 
        if mat is not None:
            points[i] = om.MVector(mat[12], mat[13], mat[14])
 
    p_data.setMObject(om.MFnVectorArrayData().create(points))
    plug_out = fn.findPlug("outputMesh", False)
    plug_out.asMObject()

def bake_full(trail_mobj, src_dag):
    fn = om.MFnDependencyNode(trail_mobj)
    s = int(oma.MAnimControl.minTime().value)
    e = int(oma.MAnimControl.maxTime().value)

    p_st = fn.findPlug("startTime", False)
    if not p_st.isLocked:
        p_st.setDouble(float(s))

    points = om.MVectorArray()
    cams = om.MMatrixArray()
    p_mat = fn.findPlug("inputMatrix", False)
    
    p_cam = None
    has_cam = False
    if fn.hasAttribute("cameraMatrix"):
        p_cam = fn.findPlug("cameraMatrix", False)
        if p_cam.isConnected: has_cam = True

    for t_val in range(s, e + 1):
        ctx = om.MDGContext(om.MTime(float(t_val)))
 
        m_obj = p_mat.asMObject(ctx)
        if not m_obj.isNull():
            mat = om.MFnMatrixData(m_obj).matrix()
            points.append(om.MVector(mat[12], mat[13], mat[14]))
        else:
            points.append(om.MVector(0, 0, 0))
 
        if has_cam:
            c_obj = p_cam.asMObject(ctx)
            if not c_obj.isNull():
                c_mat = om.MFnMatrixData(c_obj).matrix()
                cams.append(c_mat)
            else:
                cams.append(om.MMatrix.kIdentity)
        else:
            cams.append(om.MMatrix.kIdentity)
 
    fn.findPlug("trailData", False).setMObject(om.MFnVectorArrayData().create(points))
    fn.findPlug("camData", False).setMObject(om.MFnMatrixArrayData().create(cams))

class Manager:
    @staticmethod
    def on_live_update(msg, plug, other, clientData):
        if oma.MAnimControl.isPlaying(): return
        if (msg & om.MNodeMessage.kAttributeSet):
            n = plug.partialName(useLongNames=True)
            if "matrix" in n or "translate" in n or "rotate" in n or "scale" in n:
                if clientData.isValid():
                    update_neighbors_live(clientData.object(), window=5)
    
    @staticmethod
    def on_global(clientData=None):
        if clientData and clientData.isValid():
            node = clientData.object()
            fn = om.MFnDependencyNode(node)
            src = fn.findPlug("sourceLink", False)
            if src.isConnected:
                bake_full(node, om.MDagPath.getAPathTo(src.source().node()))

class HyperTrailCmd(om.MPxCommand):
    def __init__(self): om.MPxCommand.__init__(self)
    @classmethod
    def creator(cls): return cls()
    
    def doIt(self, args):
        # 1. Capture current selection
        sel = om.MGlobal.getActiveSelectionList()
        if sel.isEmpty(): om.MGlobal.displayError("Select Object."); return
        target_dag = sel.getDagPath(0)
        
        dg_mod = om.MDGModifier()
        trail_node = dg_mod.createNode(NODE_NAME)
        dg_mod.doIt()
        
        dag_mod = om.MDagModifier()
        t_grp = dag_mod.createNode("transform")
        safe = target_dag.partialPathName().replace(':','_')
        dag_mod.renameNode(t_grp, f"Trail_{safe}_Mesh")
        mesh_shape = dag_mod.createNode("mesh", t_grp)
        dag_mod.doIt()

        fn_tr = om.MFnDependencyNode(trail_node)
        fn_tgt = om.MFnDependencyNode(target_dag.node())
        fn_mesh = om.MFnDependencyNode(mesh_shape)
        
        dg = om.MDGModifier()
        dg.connect(fn_tgt.findPlug("message", False), fn_tr.findPlug("sourceLink", False))
        dg.connect(fn_tr.findPlug("outputMesh", False), fn_mesh.findPlug("inMesh", False))
        dg.connect(fn_tgt.findPlug("worldMatrix", False).elementByLogicalIndex(0), fn_tr.findPlug("inputMatrix", False))
        
        time_list = om.MGlobal.getSelectionListByName("time1")
        if not time_list.isEmpty():
            dg.connect(om.MFnDependencyNode(time_list.getDependNode(0)).findPlug("outTime", False), fn_tr.findPlug("time", False))

        if omui.M3dView.numberOf3dViews() > 0:
            view = omui.M3dView.active3dView()
            cam_dag = view.getCamera()
            fn_cam = om.MFnDependencyNode(cam_dag.node())
            dg.connect(fn_cam.findPlug("worldMatrix", False).elementByLogicalIndex(0), fn_tr.findPlug("cameraMatrix", False))
 
        dg.doIt()
        bake_full(trail_node, target_dag)
        
        h = om.MObjectHandle(trail_node)
        _CALLBACKS.append(om.MNodeMessage.addAttributeChangedCallback(target_dag.node(), Manager.on_live_update, h))
        _CALLBACKS.append(om.MEventMessage.addEventCallback("Undo", lambda *a: Manager.on_global(h)))
        _CALLBACKS.append(om.MEventMessage.addEventCallback("Redo", lambda *a: Manager.on_global(h)))
        
        # 2. Restore original selection (Do not leave Trail selected)
        om.MGlobal.setActiveSelectionList(sel)
        om.MGlobal.displayInfo("HyperTrail Created.")

def initializePlugin(obj):
    p = om.MFnPlugin(obj, "ARTools", "1.0.0", "Any")
    p.registerNode(NODE_NAME, NODE_ID, HyperTrailNode.creator, HyperTrailNode.initialize, om.MPxNode.kDependNode)
    p.registerCommand(COMMAND_NAME, HyperTrailCmd.creator)

def uninitializePlugin(obj):
    p = om.MFnPlugin(obj) 
    for c in _CALLBACKS: om.MMessage.removeCallback(c)
    _CALLBACKS.clear()
    p.deregisterCommand(COMMAND_NAME)
    p.deregisterNode(NODE_ID)


