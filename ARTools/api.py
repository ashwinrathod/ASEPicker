# ARTools/api.py
from . import main
from maya import cmds

_ACTIVE_MENU_STATE = False
_EXECUTING_CANVAS = None

def MENU_CHECKED():
    """
    Returns True if the checkable menu item that triggered this script is currently checked.
    Can be used instantly inside any Custom Menu script:
    if api.MENU_CHECKED(): ...
    """
    return _ACTIVE_MENU_STATE

def get_menu_state(identifier, label):
    """Returns the check state of a custom menu item by Shape ID and Menu Label."""
    if str(identifier).lower() == "canvas":
        canvas = get_canvas()
        if canvas:
            return getattr(canvas, "_menu_check_states", {}).get(label, False)
            
    for s in get_shapes(identifier):
        return getattr(s, "_menu_check_states", {}).get(label, False)
    return False

def set_menu_state(identifier, label, state):
    """Forcefully sets a menu's checked state in the background."""
    if str(identifier).lower() == "canvas":
        canvas = get_canvas()
        if canvas:
            if not hasattr(canvas, "_menu_check_states"): canvas._menu_check_states = {}
            canvas._menu_check_states[label] = bool(state)
            return
            
    for s in get_shapes(identifier):
        if not hasattr(s, "_menu_check_states"): s._menu_check_states = {}
        s._menu_check_states[label] = bool(state)

def get_canvas():
    """Returns the canvas executing the current script, fallback to currently active canvas."""
    global _EXECUTING_CANVAS
    if _EXECUTING_CANVAS is not None:
        return _EXECUTING_CANVAS
        
    try:
        return main._app_instance.window.main_tabs.currentWidget().sub_tabs.currentWidget().canvas
    except:
        return None

def get_selected_ids():
    """Returns a list of IDs for the currently selected shapes."""
    canvas = get_canvas()
    if not canvas: return []
    return [i.item_id for i in canvas.scene().selectedItems() if hasattr(i, 'item_id')]

def get_shapes(identifier):
    """Finds shapes safely. Prioritizes exact UUID matches, falls back to Label matches."""
    canvas = get_canvas()
    if not canvas: return []
    shapes = []
    for i in canvas.scene().items():
        if not hasattr(i, 'shape_name'): continue
        # 1. Exact ID match (Safest)
        if getattr(i, "item_id", "") == identifier: 
            return [i]
        # 2. Label match (Fallback)
        if getattr(i, "label", "") == identifier: 
            shapes.append(i)
    return shapes

def get_namespace(*args, **kwargs):
    """Returns the current Sub-Tab's custom namespace, with a fallback to Viewport Selection."""
    try:
        from . import main
        if main._app_instance and main._app_instance.window:
            char_tab = main._app_instance.window.main_tabs.currentWidget()
            if char_tab:
                sub_tab = char_tab.sub_tabs.currentWidget()
                if sub_tab:
                    return getattr(sub_tab, "custom_namespace", "")
    except Exception:
        pass
        
    # --- GLOBAL FALLBACK: If Picker is not open, use viewport selection ---
    try:
        from maya import cmds
        sel = cmds.ls(sl=True)
        if sel and ":" in sel[0]:
            return sel[0].rsplit(":", 1)[0]
    except Exception:
        pass
        
    return ""

def get_all_subtabs():
    """
    Returns a list of all SubTab objects in the current active Character Tab.
    Use this to iterate through all canvases of a character (e.g., Main, Fingers, Face).
    """
    try:
        from . import main
        app = main._app_instance
        if not app or not app.window: 
            return []
        
        # Get the currently active Character Tab
        char_tab = app.window.main_tabs.currentWidget()
        if not char_tab or not hasattr(char_tab, "sub_tabs"): 
            return []
        
        # Collect all SubTab widgets
        subtabs = []
        for i in range(char_tab.sub_tabs.count()):
            subtabs.append(char_tab.sub_tabs.widget(i))
        return subtabs
        
    except Exception as e:
        print(f"[ARTools API Error] get_all_subtabs: {e}")
        return []

def set_visibility(identifier, visible):
    """Show (True) or hide (False) individual shapes by ID or Label."""
    for s in get_shapes(identifier): 
        s.setVisible(visible)

def set_layer_visibility(layer_name, visible):
    """Show (True) or hide (False) an entire layer by name."""
    canvas = get_canvas()
    if not canvas: return
    for l in getattr(canvas, "layer_data", []):
        if l.get("name") == layer_name:
            if getattr(canvas, "is_edit_mode", False): l["vis_edit"] = visible
            else: l["vis_pose"] = visible
    if hasattr(canvas, "apply_layer_visibility"): canvas.apply_layer_visibility()

def set_layer_visibility_all(layer_name, state):
    """
    Forcefully hides or unhides a specific layer across ALL sub-tabs
    of the currently active Character Tab simultaneously.
    """
    subtabs = get_all_subtabs()
    for sub in subtabs:
        canvas = getattr(sub, "canvas", None)
        if canvas and hasattr(canvas, "layer_data"):
            for layer in canvas.layer_data:
                # Match case-insensitively
                if str(layer.get("name", "")).lower() == str(layer_name).lower():
                    layer["vis_edit"] = bool(state)
                    layer["vis_pose"] = bool(state)
            
            # Immediately apply and refresh this specific canvas
            if hasattr(canvas, "apply_layer_visibility"):
                canvas.apply_layer_visibility()
                canvas.viewport().update()

def set_color(identifier, hex_color, state="normal"):
    """Change background color by ID or Label. state='normal', 'hover', or 'press'."""
    for s in get_shapes(identifier): 
        if isinstance(s.bg, dict): s.bg[state] = hex_color
        s.update()

def set_text(identifier, text):
    """Change the text of a shape by ID or Label."""
    for s in get_shapes(identifier): 
        s.label = text
        s.update()

def set_text_color(identifier, hex_color, state="normal"):
    """Change text color by ID or Label. state='normal', 'hover', or 'press'."""
    for s in get_shapes(identifier): 
        if isinstance(s.text_color, dict): s.text_color[state] = hex_color
        s.update()

def set_edge_color(identifier, hex_color, state="normal"):
    """Change edge/border color by ID or Label. state='normal', 'hover', or 'press'."""
    for s in get_shapes(identifier): 
        if isinstance(s.edge_color, dict): s.edge_color[state] = hex_color
        s.update()

def set_checkbox(identifier, state):
        for s in get_shapes(identifier):
            if getattr(s, "shape_name", "") == "Checkbox":
                s.is_checked = bool(state)
                s.update()
                if main._app_instance:
                    main._app_instance.window.checkbox_toggled.emit(s)

def get_controls(identifier, *args, **kwargs):
    ctrls = []
    ns = get_namespace()
    
    for s in get_shapes(identifier):
        ctrls.extend(getattr(s, "controls", []))

    try:
        from . import main
        resolved = main._app_instance.core.resolve_control_names(ctrls, ns)
        return resolved
    except Exception:
        return ctrls

def get_all_character_controls(*args, **kwargs):
    """Harvests every unique control from the ACTIVE sub-tab and resolves namespaces."""
    controls = []
    try:
        from . import main
        char_tab = main._app_instance.window.main_tabs.currentWidget()
        if not char_tab: return []
        
        sub_tab = char_tab.sub_tabs.currentWidget()
        if not sub_tab: return []
        
        active_ns = getattr(sub_tab, "custom_namespace", "")
        
        # 1. Gather all raw relative controls from the CURRENT canvas only
        raw_controls = []
        for item in sub_tab.canvas.scene().items():
            if hasattr(item, "controls") and item.controls:
                raw_controls.extend(item.controls)
                
        # 2. Run them through the Phase 1 Smart Rebuilder!
        controls = main._app_instance.core.resolve_control_names(raw_controls, active_ns)
    except Exception:
        pass
    return list(set(controls))

def select_all():
    """Phase 2 Engine: Harvests all controls and seamlessly selects them in Maya."""
    ctrls = get_all_character_controls()
    if ctrls:
        cmds.select(ctrls, replace=True)
        print(f"[ARTools] Successfully selected {len(ctrls)} fully resolved controls.")
    else:
        cmds.select(clear=True)

def match_ikfk(chain_name, target_mode, key=True, time_mode="Current Frame", bake_mode="Existing Keys Only"):
    """
    Executes IK/FK matching from a script. Perfect for Checkbox Scripts.
    target_mode: 'to_ik' (Switch to IK) or 'to_fk' (Switch to FK)
    time_mode: 'Current Frame', 'Time Slider Selection', 'Entire Time Slider'
    bake_mode: 'Existing Keys Only', 'Bake Every Frame', 'Bake on 2s'
    """
    try:
        from .anim import logic_ikfk
        from . import main
        char_tab = main._app_instance.window.main_tabs.currentWidget()
        if not char_tab: return
        
        chains = getattr(char_tab, "ikfk_chains", [])
        ns = get_namespace()
        
        for chain_data in chains:
            if chain_data.get("name") == chain_name:
                chain = {
                    "ik_ctrl": chain_data.get("ik_ctrl", ""),
                    "pv_ctrl": chain_data.get("pv_ctrl", ""),
                    "fk_ctrls": chain_data.get("fk_ctrls", []),
                    "bones": chain_data.get("bones", []),
                    "switch": {
                        "node": chain_data.get("sw_node", ""),
                        "attr": chain_data.get("sw_attr", ""),
                        "ik_val": chain_data.get("ik_val", 1.0),
                        "fk_val": chain_data.get("fk_val", 0.0)
                    }
                }
                
                logic_ikfk.batch_switch([chain], target_mode, ns, key=key, time_mode=time_mode, bake_mode=bake_mode)
                return
                
        from maya import cmds
        cmds.warning(f"[ARTools] Chain '{chain_name}' not found in Rig Settings.")
    except Exception as e:
        from maya import cmds
        cmds.warning(f"[ARTools] match_ikfk Error: {e}")

def reset_selected_shapes():
    """Reads the selected shapes on the canvas and resets only their assigned controls using the AnimBar Snapshot."""
    import ARTools.main
    from ARTools.anim import logic_pose
    from maya import cmds

    app = getattr(ARTools.main, "_app_instance", None)
    if not app or not app.window:
        return

    # 1. Get the active Character Tab
    char_tab = app.window.main_tabs.currentWidget()
    if not char_tab: return

    # 2. Get the active Canvas and selected shapes
    sub_tab = char_tab.sub_tabs.currentWidget()
    if not sub_tab: return
    
    # Fetch the namespace directly from the active Sub-Tab!
    ns = get_namespace()

    selected_items = [i for i in sub_tab.canvas.scene().selectedItems() if hasattr(i, "shape_name")]

    if not selected_items:
        cmds.warning("[ARTools] No shapes selected to reset!")
        return

    # 3. Extract the actual Maya controls assigned to those shapes
    controls_to_reset = []
    for item in selected_items:
        ctrls = getattr(item, "controls", [])
        for c in ctrls:
            # FIX: Stop splitting colons! Pass the raw relative control!
            if c not in controls_to_reset:
                controls_to_reset.append(c)

    if not controls_to_reset:
        cmds.warning("[ARTools] Selected shapes have no controls assigned!")
        return

    # 4. Trigger the AnimBar reset engine, passing ONLY the selected controls!
    logic_pose.reset_pose(ns, target_controls=controls_to_reset)

def match_space(controls, attribute, target_value, key=True):
    """
    Seamlessly switches a space attribute on the given controls while maintaining their exact world position.
    Perfect for Canvas Checkboxes, Dropdowns, or Context Menus.
    """
    ns = get_namespace()
    try:
        from . import main
        resolved_ctrls = main._app_instance.core.resolve_control_names(controls, ns)
    except Exception:
        resolved_ctrls = controls

    if not resolved_ctrls: return

    cmds.undoInfo(openChunk=True, chunkName="ARTools_API_SpaceSwitch")
    try:
        world_states = {}
        
        # 1. Capture Exact World States
        # NOTE: a full world matrix is captured (not just t/ro Euler) so the
        # rotation restore below can go through cmds.xform(matrix=...), which
        # is the only worldspace method that correctly accounts for a
        # non-zero rotateAxis on the control -- cmds.rotate(ws=True) ignores
        # rotateAxis entirely, which is what made this look "weird" on rigs
        # whose controls use a rotateAxis offset.
        for ctrl in resolved_ctrls:
            if not cmds.objExists(ctrl): continue
            t = cmds.xform(ctrl, q=True, ws=True, t=True)
            m = cmds.xform(ctrl, q=True, ws=True, matrix=True)
            world_states[ctrl] = (t, m)
            
        # 2. Change the Space Attribute
        for ctrl in resolved_ctrls:
            # Handle if user passed 'L_Hand.space' vs just 'space'
            attr_path = attribute if "." in attribute else f"{ctrl}.{attribute}"
            
            if cmds.objExists(attr_path) and cmds.getAttr(attr_path, settable=True):
                cmds.setAttr(attr_path, target_value)
                
                # Autokey the space attribute switch
                if key and (cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(attr_path, q=True, keyframeCount=True)):
                    cmds.setKeyframe(attr_path)

        # Force DG Evaluation so the rig calculates the new space before we snap back!
        for ctrl in resolved_ctrls:
            if cmds.objExists(ctrl): cmds.getAttr(f"{ctrl}.worldMatrix[0]")

        # 3. Snap Back to Original World Position
        for ctrl, (t, m) in world_states.items():
            if not cmds.getAttr(f"{ctrl}.tx", l=True):
                cmds.move(t[0], t[1], t[2], ctrl, ws=True)
            if not cmds.getAttr(f"{ctrl}.rx", l=True):
                # Keep whatever translation the control now has (set just
                # above, or its own locked value) and only carry the
                # target rotation through the matrix -- xform(matrix=...)
                # solves the full inverse stack (pivot, rotateOrder AND
                # rotateAxis), unlike cmds.rotate(ws=True).
                cur_t = cmds.xform(ctrl, q=True, ws=True, t=True)
                rot_m = list(m)
                rot_m[12], rot_m[13], rot_m[14] = cur_t[0], cur_t[1], cur_t[2]
                cmds.xform(ctrl, ws=True, matrix=rot_m)
                
            # Autokey the control's new translation/rotation to lock it in place
            if key and (cmds.autoKeyframe(q=True, state=True) or cmds.keyframe(ctrl, at=["translate", "rotate"], q=True, keyframeCount=True)):
                cmds.setKeyframe(ctrl, at=["translate", "rotate"])
                
    except Exception as e:
        cmds.warning(f"[ARTools] API Space Match Error: {e}")
    finally:
        cmds.refresh(force=True)
        cmds.undoInfo(closeChunk=True)