# ARTools/anim/logic_ikfk.py
import bpy
import mathutils
import math
from ..blender_host import object_by_name, set_property

def _resolve(node, ns):
    """Safely applies the namespace, automatically cleaning old hardcoded namespaces."""
    if not node: return ""
    clean_node = node.split(":")[-1]
    if ns: return f"{ns}:{clean_node}"
    return clean_node

def _get_matrix_world(b_obj):
    if hasattr(b_obj, "matrix_world"):
        return b_obj.matrix_world.copy()
    return b_obj.id_data.matrix_world @ b_obj.matrix.copy()

def _set_matrix_world_respecting_locks(b_obj, mat):
    """Safely applies a world matrix while rigorously enforcing Blender transform locks."""
    if hasattr(b_obj, "matrix_world"):
        old_loc = b_obj.location.copy()
        old_rot_e = getattr(b_obj, "rotation_euler", mathutils.Euler()).copy()
        old_rot_q = getattr(b_obj, "rotation_quaternion", mathutils.Quaternion()).copy()
        old_scale = b_obj.scale.copy()
        
        b_obj.matrix_world = mat
        
        for i in range(3):
            if getattr(b_obj, "lock_location", [False]*3)[i]: b_obj.location[i] = old_loc[i]
            if getattr(b_obj, "lock_scale", [False]*3)[i]: b_obj.scale[i] = old_scale[i]
            
        if getattr(b_obj, "rotation_mode", 'QUATERNION') == 'QUATERNION':
            if getattr(b_obj, "lock_rotations_4d", False):
                new_rot_q = b_obj.rotation_quaternion.copy()
                lock_xyz = getattr(b_obj, "lock_rotation", [False, False, False])
                if getattr(b_obj, "lock_rotation_w", False): new_rot_q.w = old_rot_q.w
                if lock_xyz[0]: new_rot_q.x = old_rot_q.x
                if lock_xyz[1]: new_rot_q.y = old_rot_q.y
                if lock_xyz[2]: new_rot_q.z = old_rot_q.z
                new_rot_q.normalize()
                b_obj.rotation_quaternion = new_rot_q
        else:
            for i in range(3):
                if getattr(b_obj, "lock_rotation", [False]*3)[i]: b_obj.rotation_euler[i] = old_rot_e[i]
    else:
        old_loc = b_obj.location.copy()
        old_rot_e = getattr(b_obj, "rotation_euler", mathutils.Euler()).copy()
        old_rot_q = getattr(b_obj, "rotation_quaternion", mathutils.Quaternion()).copy()
        old_scale = b_obj.scale.copy()
        
        b_obj.matrix = b_obj.id_data.matrix_world.inverted_safe() @ mat
        
        for i in range(3):
            if getattr(b_obj, "lock_location", [False]*3)[i]: b_obj.location[i] = old_loc[i]
            if getattr(b_obj, "lock_scale", [False]*3)[i]: b_obj.scale[i] = old_scale[i]
            
        if getattr(b_obj, "rotation_mode", 'QUATERNION') == 'QUATERNION':
            if getattr(b_obj, "lock_rotations_4d", False):
                new_rot_q = b_obj.rotation_quaternion.copy()
                lock_xyz = getattr(b_obj, "lock_rotation", [False, False, False])
                if getattr(b_obj, "lock_rotation_w", False): new_rot_q.w = old_rot_q.w
                if lock_xyz[0]: new_rot_q.x = old_rot_q.x
                if lock_xyz[1]: new_rot_q.y = old_rot_q.y
                if lock_xyz[2]: new_rot_q.z = old_rot_q.z
                new_rot_q.normalize()
                b_obj.rotation_quaternion = new_rot_q
        else:
            for i in range(3):
                if getattr(b_obj, "lock_rotation", [False]*3)[i]: b_obj.rotation_euler[i] = old_rot_e[i]


# ---------------------------------------------------------------------
# Robust matrix helpers: prefer control objects and blend constraint targets
# ---------------------------------------------------------------------
def _slerp_quat(q1, q2, t):
    """Slerp between two mathutils.Quaternion objects."""
    try:
        return q1.slerp(q2, max(0.0, min(1.0, t)))
    except Exception:
        q = q1.copy()
        q.w = (1.0 - t) * q1.w + t * q2.w
        q.x = (1.0 - t) * q1.x + t * q2.x
        q.y = (1.0 - t) * q1.y + t * q2.y
        q.z = (1.0 - t) * q1.z + t * q2.z
        q.normalize()
        return q

def _blend_transforms(mat_a, mat_b, t):
    """Blend two world matrices: lerp translation/scale, slerp rotation."""
    t = max(0.0, min(1.0, t))
    loc_a = mat_a.translation
    loc_b = mat_b.translation
    rot_a = mat_a.to_quaternion()
    rot_b = mat_b.to_quaternion()
    scale_a = mat_a.to_scale()
    scale_b = mat_b.to_scale()

    loc = loc_a.lerp(loc_b, t)
    rot = _slerp_quat(rot_a, rot_b, t)
    scale = scale_a.lerp(scale_b, t)
    return mathutils.Matrix.LocRotScale(loc, rot, scale)

def _get_constraint_target_world_matrix(constraint):
    """Return the world matrix of a constraint's target if resolvable, else None."""
    try:
        tgt_obj = getattr(constraint, "target", None)
        sub = getattr(constraint, "subtarget", None)
        if tgt_obj:
            if sub:
                if hasattr(tgt_obj, "pose") and sub in tgt_obj.pose.bones:
                    pb = tgt_obj.pose.bones[sub]
                    return tgt_obj.matrix_world @ pb.matrix
            else:
                return _get_matrix_world(tgt_obj)

        if getattr(constraint, "type", "") == 'DAMPED_TRACK':
            tgt = getattr(constraint, "target", None)
            sub = getattr(constraint, "subtarget", None)
            if tgt:
                if sub and hasattr(tgt, "pose") and sub in tgt.pose.bones:
                    pb = tgt.pose.bones[sub]
                    return tgt.matrix_world @ pb.matrix
                return _get_matrix_world(tgt)
    except Exception:
        pass
    return None

def _get_effective_world_matrix_for_bone(b_obj):
    """Compute an effective world matrix for a bone/object by blending its
    evaluated matrix with constraint target matrices according to influence.
    Handles common constraint types: COPY_ROTATION, COPY_LOCATION, COPY_SCALE,
    COPY_TRANSFORMS, DAMPED_TRACK. Falls back to evaluated matrix.
    """
    base_mat = _get_matrix_world(b_obj)
    cons = getattr(b_obj, "constraints", None)
    if not cons:
        return base_mat

    result = base_mat
    for c in cons:
        try:
            inf = getattr(c, "influence", 1.0)
            if inf <= 0.0:
                continue
            tgt_mat = _get_constraint_target_world_matrix(c)
            if tgt_mat is None:
                continue

            if c.type == 'COPY_ROTATION':
                base_loc = result.translation
                base_scale = result.to_scale()
                base_rot = result.to_quaternion()
                tgt_rot = tgt_mat.to_quaternion()
                new_rot = _slerp_quat(base_rot, tgt_rot, inf)
                result = mathutils.Matrix.LocRotScale(base_loc, new_rot, base_scale)
            elif c.type == 'COPY_LOCATION':
                base_rot = result.to_quaternion()
                base_scale = result.to_scale()
                base_loc = result.translation
                tgt_loc = tgt_mat.translation
                new_loc = base_loc.lerp(tgt_loc, inf)
                result = mathutils.Matrix.LocRotScale(new_loc, base_rot, base_scale)
            elif c.type == 'COPY_SCALE':
                base_loc = result.translation
                base_rot = result.to_quaternion()
                base_scale = result.to_scale()
                tgt_scale = tgt_mat.to_scale()
                new_scale = base_scale.lerp(tgt_scale, inf)
                result = mathutils.Matrix.LocRotScale(base_loc, base_rot, new_scale)
            elif c.type in ('COPY_TRANSFORMS',):
                result = _blend_transforms(result, tgt_mat, inf)
            elif c.type == 'DAMPED_TRACK':
                tgt_pos = tgt_mat.translation
                src_pos = result.translation
                direction = (tgt_pos - src_pos)
                if direction.length_squared > 1e-8:
                    aim = mathutils.Vector((0.0, 1.0, 0.0))
                    rot = aim.rotation_difference(direction.normalized())
                    base_scale = result.to_scale()
                    result = mathutils.Matrix.LocRotScale(result.translation, rot, base_scale)
            else:
                continue
        except Exception:
            continue
    return result

def _resolve_preferred_world_matrix(chain, bone_name):
    """Return the best world matrix for a bone used as IK proxy:
       1) Prefer the chain's ik_ctrl only for the end effector (last bone).
       2) Compute an effective matrix for the bone by blending constraint targets.
       3) Fallback to the bone's evaluated matrix.
    """
    try:
        if chain and chain.get("ik_ctrl") and "bones" in chain:
            bones = chain.get("bones", [])
            # prefer ik_ctrl only if this bone is the last (end effector)
            if bones and bone_name == bones[-1]:
                ik_obj = object_by_name(chain["ik_ctrl"])
                if ik_obj:
                    return _get_matrix_world(ik_obj)
    except Exception:
        pass

    b_obj = object_by_name(bone_name)
    if b_obj:
        return _get_effective_world_matrix_for_bone(b_obj)
    return None


# =====================================================================
# THE BATCH MATCHING ENGINE (CONCURRENT, HIGHSPEED, TANGENT-SAFE)
# =====================================================================

def batch_switch(chains, target_mode, ns, key=True, time_mode="Current Frame", bake_mode="Existing Keys Only"):
    all_nodes = set()
    resolved_chains = []
    for chain in chains:
        ik_ctrl = _resolve(chain.get("ik_ctrl", ""), ns)
        pv_ctrl = _resolve(chain.get("pv_ctrl", ""), ns)
        fk_ctrls = [_resolve(x, ns) for x in chain.get("fk_ctrls", [])]
        bones = [_resolve(x, ns) for x in chain.get("bones", [])]
        solver_mode = chain.get("solver_mode", "Advanced (Virtual Proxy)")
        
        sw_node = _resolve(chain["switch"]["node"], ns)
        sw_attr = chain["switch"]["attr"].split(".")[-1]
        attr_path = f"{sw_node}.{sw_attr}"
        
        if target_mode == "to_ik":
            if not ik_ctrl or not fk_ctrls or not object_by_name(sw_node): continue
            all_nodes.update([ik_ctrl])
            if pv_ctrl: all_nodes.add(pv_ctrl)
            all_nodes.update(fk_ctrls)
        else:
            if not fk_ctrls or not bones or not object_by_name(sw_node): continue
            all_nodes.update(fk_ctrls)
            all_nodes.update([ik_ctrl])
            if pv_ctrl: all_nodes.add(pv_ctrl)
            
        all_nodes.add(sw_node)
        
        resolved_chains.append({
            "ik_ctrl": ik_ctrl, "pv_ctrl": pv_ctrl, "fk_ctrls": fk_ctrls, "bones": bones,
            "sw_node": sw_node, "sw_attr": sw_attr, "attr_path": attr_path,
            "ik_val": chain["switch"]["ik_val"], "fk_val": chain["switch"]["fk_val"],
            "solver_mode": solver_mode
        })
        
    if not resolved_chains: return
    valid_nodes = [n for n in all_nodes if object_by_name(n)]
    
    scene = bpy.context.scene
    start_t = end_t = scene.frame_current
    is_range = False
    
    if time_mode == "Time Slider Selection":
        if scene.use_preview_range:
            start_t, end_t = scene.frame_preview_start, scene.frame_preview_end
            is_range = True
    elif time_mode == "Entire Time Slider":
        start_t, end_t = scene.frame_start, scene.frame_end
        is_range = True

    frames = []
    if not is_range:
        frames = [float(start_t)]
    elif bake_mode == "Existing Keys Only":
        key_times = set()
        for node in valid_nodes:
            b_obj = object_by_name(node)
            if b_obj:
                anim_host = b_obj.id_data if hasattr(b_obj, "id_data") else b_obj
                if anim_host.animation_data and anim_host.animation_data.action:
                    for fc in anim_host.animation_data.action.fcurves:
                        for kp in fc.keyframe_points:
                            if start_t <= kp.co.x <= end_t:
                                key_times.add(kp.co.x)
        if key_times: frames = sorted(list(key_times))
        else: frames = [float(start_t)]
    elif bake_mode == "Bake on 2s":
        frames = [float(f) for f in range(int(start_t), int(end_t) + 1, 2)]
    else:
        frames = [float(f) for f in range(int(start_t), int(end_t) + 1)]

    try:
        for f in frames:
            if is_range: scene.frame_set(int(f))
            bpy.context.view_layer.update()
            
            for chain in resolved_chains:
                if target_mode == "to_ik": 
                    _process_ik_frame(chain, key, is_range)
                else: 
                    if "Advanced" in chain["solver_mode"]:
                        _process_fk_frame_advanced(chain, key, is_range)
                    else:
                        _process_fk_frame(chain, key, is_range)

        if key and is_range:
            for node in valid_nodes:
                b_obj = object_by_name(node)
                if not b_obj: continue
                anim_host = b_obj.id_data if hasattr(b_obj, "id_data") else b_obj
                if not anim_host.animation_data or not anim_host.animation_data.action:
                    continue
                    
                rot_path = b_obj.path_from_id("rotation_euler") if hasattr(b_obj, "path_from_id") else "rotation_euler"
                for fc in anim_host.animation_data.action.fcurves:
                    if fc.data_path == rot_path:
                        prev_y = None
                        for kp in sorted(fc.keyframe_points, key=lambda k: k.co.x):
                            if prev_y is not None:
                                diff = kp.co.y - prev_y
                                if abs(diff) > math.pi:
                                    offset_val = round(diff / (2 * math.pi)) * 2 * math.pi
                                    kp.co.y -= offset_val
                                    kp.handle_left.y -= offset_val
                                    kp.handle_right.y -= offset_val
                            prev_y = kp.co.y
                        fc.update()

    except Exception as e:
        print(f"[ARTools] IK/FK Match Error: {e}")
    finally:
        if is_range:
            scene.frame_set(int(start_t))
            bpy.context.view_layer.update()
        
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    with bpy.context.temp_override(window=window, area=area):
                        bpy.ops.ed.undo_push(message="ARTools_IKFKBake")
                    break
        
        def _show_msg():
            try:
                if is_range:
                    bpy.context.workspace.status_text_set(f"ARTools: IK/FK Baked ({len(frames)} frames)")
                else:
                    bpy.context.workspace.status_text_set("ARTools: IK/FK Matched")
            except: pass
        _show_msg()


# =====================================================================
# THE ADVANCED VIRTUAL PROXY SOLVER (HIGH-SPEED WORLD CASCADE)
# =====================================================================

def _process_fk_frame_advanced(chain, key, is_range):
    fk_ctrls = chain["fk_ctrls"]
    bones = chain["bones"]
    sw_obj = object_by_name(chain["sw_node"])

    # Ensure FK switch initially
    if sw_obj:
        set_property(sw_obj, chain["sw_attr"], chain["fk_val"], keyframe=False)
        bpy.context.view_layer.update()

    # Conservative passes (keeps correctness). You can lower MAX_PASSES later if you need speed.
    MAX_PASSES = 6
    CONVERGED_ANGLE = 0.01    # radians
    CONVERGED_POS = 0.0005

    # Resolve controls / deform bones once (they do not change during the solve)
    c_objs = [object_by_name(c) for c in fk_ctrls]
    b_objs = [object_by_name(b) for b in bones]

    for _pass in range(MAX_PASSES):
        worst_gap = 0.0
        worst_pos_gap = 0.0

        # Snapshot of control channels (used to detect a pass that changed nothing)
        start_vals = [tuple(o.location) + tuple(o.rotation_quaternion) + tuple(o.rotation_euler) for o in c_objs if o]

        # Read IK world matrices for the whole chain ONCE per pass
        if sw_obj:
            set_property(sw_obj, chain["sw_attr"], chain["ik_val"], keyframe=False)
            bpy.context.view_layer.update()
        ik_mats = [
            (_resolve_preferred_world_matrix(chain, bones[i]) or _get_matrix_world(b_objs[i])) if (c_objs[i] and b_objs[i]) else None
            for i in range(len(fk_ctrls))
        ]
        # Restore FK switch so offsets are computed in FK-space
        if sw_obj:
            set_property(sw_obj, chain["sw_attr"], chain["fk_val"], keyframe=False)
            bpy.context.view_layer.update()

        for i in range(len(fk_ctrls)):
            ctrl = fk_ctrls[i]
            bone = bones[i]
            c_obj = c_objs[i]
            b_obj = b_objs[i]
            if not c_obj or not b_obj:
                continue

            ik_world_mat = ik_mats[i]

            # Recompute current bone/control matrices each pass (ensures corrections propagate)
            curr_b_mat = _get_effective_world_matrix_for_bone(b_obj) or _get_matrix_world(b_obj)
            curr_c_mat = _get_matrix_world(c_obj)

            # Compute offset from bone to control in FK pose
            offset = curr_b_mat.inverted_safe() @ curr_c_mat

            # Detect deform bone not driven by FK (zero-influence copy constraints)
            use_direct_ik_for_control = False
            try:
                for c in getattr(b_obj, "constraints", []):
                    if c.type in ("COPY_ROTATION", "COPY_TRANSFORMS", "COPY_LOCATION") and getattr(c, "influence", 1.0) == 0.0:
                        use_direct_ik_for_control = True
                        break
            except Exception:
                use_direct_ik_for_control = False

            if use_direct_ik_for_control:
                target_c_mat = ik_world_mat.copy()
            else:
                target_c_mat = ik_world_mat @ offset

            # Apply transform respecting locks
            _set_matrix_world_respecting_locks(c_obj, target_c_mat)
            if getattr(c_obj, "rotation_mode", "") != 'QUATERNION':
                bpy.context.view_layer.update()

            # Compute target rotation in local (armature) space and apply
            target_pose_mat = c_obj.id_data.matrix_world.inverted_safe() @ target_c_mat
            target_pose_q = target_pose_mat.to_quaternion().normalized()

            if getattr(c_obj, "rotation_mode", "") == 'QUATERNION':
                c_obj.rotation_quaternion = target_pose_q
                bpy.context.view_layer.update()
            else:
                _solve_driven_rotation_axis(c_obj, target_pose_q)

            final_q = c_obj.matrix.to_quaternion().normalized()
            worst_gap = max(worst_gap, final_q.rotation_difference(target_pose_q).angle)

            final_world_pos = _get_matrix_world(c_obj).translation
            worst_pos_gap = max(worst_pos_gap, (target_c_mat.translation - final_world_pos).length)

            # Shoulder correction: if we changed shoulder, recompute downstream bones immediately
            if i == 1 and len(fk_ctrls) > 0:
                shoulder = object_by_name(fk_ctrls[0])
                if shoulder:
                    actual_pose_q = c_obj.matrix.to_quaternion().normalized()
                    missing_pose_q = target_pose_q @ actual_pose_q.inverted()

                    if abs(missing_pose_q.w) < 0.9999:
                        s_pose_mat = shoulder.matrix.copy()
                        new_s_pose_rot = missing_pose_q @ s_pose_mat.to_quaternion().normalized()
                        new_s_pose_mat = mathutils.Matrix.LocRotScale(s_pose_mat.translation, new_s_pose_rot, s_pose_mat.to_scale())

                        new_s_world = shoulder.id_data.matrix_world @ new_s_pose_mat
                        _set_matrix_world_respecting_locks(shoulder, new_s_world)
                        bpy.context.view_layer.update()

                        # Recompute downstream bones' matrices so forearm/wrist use fresh data
                        downstream = bones[i:]  # from current bone to end
                        if sw_obj:
                            set_property(sw_obj, chain["sw_attr"], chain["ik_val"], keyframe=False)
                            bpy.context.view_layer.update()
                        for db in downstream:
                            db_obj = object_by_name(db)
                            # recompute ik_world for downstream and effective bone mat
                            ik_val = _resolve_preferred_world_matrix(chain, db) or (_get_matrix_world(db_obj) if db_obj else mathutils.Matrix())
                            # update local caches by directly writing back to variables used below
                            # (we simply re-evaluate when needed in the next loop iteration)
                            # no explicit cache here; next loop iteration will call _get_effective_world_matrix_for_bone/_get_matrix_world again
                        if sw_obj:
                            set_property(sw_obj, chain["sw_attr"], chain["fk_val"], keyframe=False)
                            bpy.context.view_layer.update()

                        # Recompute target for this control using fresh matrices
                        curr_b_mat_2 = _get_effective_world_matrix_for_bone(b_obj) or _get_matrix_world(b_obj)
                        curr_c_mat_2 = _get_matrix_world(c_obj)
                        offset_2 = curr_b_mat_2.inverted_safe() @ curr_c_mat_2
                        ik_world_mat_2 = _resolve_preferred_world_matrix(chain, bone) or _get_matrix_world(b_obj)
                        target_c_mat_2 = ik_world_mat_2 @ offset_2

                        _set_matrix_world_respecting_locks(c_obj, target_c_mat_2)
                        if getattr(c_obj, "rotation_mode", "") != 'QUATERNION':
                            bpy.context.view_layer.update()

                        target_pose_mat_2 = c_obj.id_data.matrix_world.inverted_safe() @ target_c_mat_2
                        target_pose_q_2 = target_pose_mat_2.to_quaternion().normalized()
                        if getattr(c_obj, "rotation_mode", "") == 'QUATERNION':
                            c_obj.rotation_quaternion = target_pose_q_2
                            bpy.context.view_layer.update()
                        else:
                            _solve_driven_rotation_axis(c_obj, target_pose_q_2)

        # End of pass: check convergence
        if worst_gap < CONVERGED_ANGLE and worst_pos_gap < CONVERGED_POS:
            break

        # Stop early if this pass changed nothing (the next pass would be identical)
        end_vals = [tuple(o.location) + tuple(o.rotation_quaternion) + tuple(o.rotation_euler) for o in c_objs if o]
        if all(abs(a - b) < 1e-6 for s, e in zip(start_vals, end_vals) for a, b in zip(s, e)):
            break

    # Finalize: set switch to FK and key if requested
    if sw_obj:
        set_property(sw_obj, chain["sw_attr"], chain["fk_val"], keyframe=False)
        bpy.context.view_layer.update()

    if key:
        for ctrl in fk_ctrls:
            c_obj = object_by_name(ctrl)
            if not c_obj: continue
            try:
                c_obj.keyframe_insert(data_path="location")
                if getattr(c_obj, "rotation_mode", 'QUATERNION') == 'QUATERNION':
                    c_obj.keyframe_insert(data_path="rotation_quaternion")
                else:
                    c_obj.keyframe_insert(data_path="rotation_euler")
            except Exception:
                pass

# =====================================================================
# THE STANDARD MATH CASCADE SOLVER
# =====================================================================

def _solve_driven_rotation_axis(c_obj, target_q, samples=24, refine_iters=10):
    if getattr(c_obj, "rotation_mode", "") == 'QUATERNION': return
    anim = c_obj.id_data.animation_data
    if not anim: return
    path = f'pose.bones["{c_obj.name}"].rotation_euler'
    driven = {d.array_index for d in anim.drivers if d.data_path == path}
    free_idx = [i for i in range(3) if i not in driven]
    if len(free_idx) != 1: return
    idx = free_idx[0]

    def angular_dist(q):
        return 1.0 - abs(q.dot(target_q))

    best_val = c_obj.rotation_euler[idx]
    best_dist = None
    for i in range(samples):
        a = -math.pi + (2 * math.pi) * (i / float(samples - 1))
        c_obj.rotation_euler[idx] = a
        bpy.context.view_layer.update()
        d = angular_dist(c_obj.matrix.to_quaternion())
        if best_dist is None or d < best_dist:
            best_dist, best_val = d, a

    lo, hi = best_val - (2 * math.pi / samples), best_val + (2 * math.pi / samples)
    for _ in range(refine_iters):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        c_obj.rotation_euler[idx] = m1
        bpy.context.view_layer.update()
        d1 = angular_dist(c_obj.matrix.to_quaternion())
        c_obj.rotation_euler[idx] = m2
        bpy.context.view_layer.update()
        d2 = angular_dist(c_obj.matrix.to_quaternion())
        if d1 < d2: hi = m2
        else: lo = m1

    c_obj.rotation_euler[idx] = (lo + hi) / 2.0
    bpy.context.view_layer.update()

def _process_fk_frame(chain, key, is_range):
    fk_ctrls = chain["fk_ctrls"]
    bones = chain["bones"]
    
    sw_obj = object_by_name(chain["sw_node"])
    if sw_obj:
        set_property(sw_obj, chain["sw_attr"], chain["fk_val"], keyframe=False)
        bpy.context.view_layer.update()

    # Simpler solver: recompute per-control each pass (keeps correctness)
    for i, (ctrl, bone) in enumerate(zip(fk_ctrls, bones)):
        c_obj = object_by_name(ctrl)
        b_obj = object_by_name(bone)
        if not c_obj or not b_obj: continue

        # Read effective bone matrix (blended constraints) fresh
        b_mat = _get_effective_world_matrix_for_bone(b_obj) or _get_matrix_world(b_obj)

        _set_matrix_world_respecting_locks(c_obj, b_mat)
        bpy.context.view_layer.update()

        target_pose_mat = c_obj.id_data.matrix_world.inverted_safe() @ b_mat
        target_pose_q = target_pose_mat.to_quaternion().normalized()

        if getattr(c_obj, "rotation_mode", "") == 'QUATERNION':
            c_obj.rotation_quaternion = target_pose_q
            bpy.context.view_layer.update()
        else:
            _solve_driven_rotation_axis(c_obj, target_pose_q)

    if key:
        for ctrl in fk_ctrls:
            c_obj = object_by_name(ctrl)
            if not c_obj: continue
            try:
                c_obj.keyframe_insert(data_path="location")
                if getattr(c_obj, "rotation_mode", 'QUATERNION') == 'QUATERNION':
                    c_obj.keyframe_insert(data_path="rotation_quaternion")
                else:
                    c_obj.keyframe_insert(data_path="rotation_euler")
            except Exception:
                pass

def _process_ik_frame(chain, key, is_range):
    ik_ctrl = chain["ik_ctrl"]
    pv_ctrl = chain["pv_ctrl"]
    fk_ctrls = chain["fk_ctrls"]
    
    fk_objs = [object_by_name(c) for c in fk_ctrls]
    if not fk_objs or not fk_objs[-1] or not fk_objs[0] or len(fk_objs) < 2: return
    
    # Base IK math on the FK controls, NOT the deform bones, to ensure perfect visual snapping!
    goal_mat = _get_matrix_world(fk_objs[-1])
    start_pos = _get_matrix_world(fk_objs[0]).translation.copy()
    
    if len(fk_objs) >= 3:
        mid_pos = _get_matrix_world(fk_objs[1]).translation.copy()
        end_pos = _get_matrix_world(fk_objs[-1]).translation.copy()
    else:
        end_pos = _get_matrix_world(fk_objs[-1]).translation.copy()
        mid_pos = (start_pos + end_pos) / 2.0

    sw_obj = object_by_name(chain["sw_node"])
    if sw_obj:
        set_property(sw_obj, chain["sw_attr"], chain["ik_val"], keyframe=key)
        bpy.context.view_layer.update()

    ik_obj = object_by_name(ik_ctrl)
    if ik_obj:
        _set_matrix_world_respecting_locks(ik_obj, goal_mat)
        if key:
            ik_obj.keyframe_insert(data_path="location")
            if getattr(ik_obj, "rotation_mode", 'QUATERNION') == 'QUATERNION':
                ik_obj.keyframe_insert(data_path="rotation_quaternion")
            else:
                ik_obj.keyframe_insert(data_path="rotation_euler")

    if pv_ctrl:
        pv_obj = object_by_name(pv_ctrl)
        if pv_obj:
            v1 = (start_pos - mid_pos).normalized()
            v2 = (end_pos - mid_pos).normalized()
            bisector = (v1 + v2).normalized()
            pv_dir = -bisector
            
            if pv_dir.length < 0.001: 
                pv_dir = mathutils.Vector((0, 0, 1))
                
            current_pv_mat = _get_matrix_world(pv_obj)
            current_pv = current_pv_mat.translation.copy()
            current_dist = (current_pv - mid_pos).length
            if current_dist < 0.1: current_dist = 5.0
                
            pv_final_pos = mid_pos + (pv_dir * current_dist)
            current_pv_mat.translation = pv_final_pos
            _set_matrix_world_respecting_locks(pv_obj, current_pv_mat)
            
            if key:
                pv_obj.keyframe_insert(data_path="location")

# =====================================================================
# UI HELPER: AUTO-FIND JOINTS
# =====================================================================

def find_driven_joint(ctrl):
    c_obj = object_by_name(ctrl)
    if not c_obj: return None
    
    armature = c_obj.id_data
    if armature and armature.type == 'ARMATURE':
        for bone in armature.pose.bones:
            for const in bone.constraints:
                if hasattr(const, "subtarget") and const.subtarget == ctrl.split(":")[-1]:
                    return f"{armature.name}:{bone.name}"
                if hasattr(const, "target") and const.target == c_obj:
                    return f"{armature.name}:{bone.name}"
    return None

def auto_find_chain(fk_list):
    bones = []
    for fk in fk_list:
        b = find_driven_joint(fk)
        if b: bones.append(b)
    return bones