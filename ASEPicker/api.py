# ASEPicker/api.py
from . import main
from maya import cmds

def get_canvas():
    """Returns the currently active character canvas."""
    try:
        return main._app_instance.window.main_tabs.currentWidget().sub_tabs.currentWidget().canvas
    except:
        return None

def get_selected_ids():
    """Returns a list of IDs for the currently selected shapes."""
    canvas = get_canvas()
    if not canvas: return []
    return [i.item_id for i in canvas.scene.selectedItems() if hasattr(i, 'item_id')]

def get_shapes(identifier):
    """Finds shapes safely. Prioritizes exact UUID matches, falls back to Label matches."""
    canvas = get_canvas()
    if not canvas: return []
    shapes = []
    for i in canvas.scene.items():
        if not hasattr(i, 'shape_name'): continue
        # 1. Exact ID match (Safest)
        if getattr(i, "item_id", "") == identifier: 
            return [i]
        # 2. Label match (Fallback)
        if getattr(i, "label", "") == identifier: 
            shapes.append(i)
    return shapes

def get_namespace():
    """Returns the current character's namespace."""
    try:
        return main._app_instance.window.main_tabs.currentWidget().namespace
    except:
        return ""

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

def get_controls(identifier):
    """Returns the assigned Maya controls for a shape, automatically applying the namespace."""
    ctrls = []
    ns = get_namespace()
    ns_prefix = f"{ns}:" if ns else ""
    for s in get_shapes(identifier):
        for c in getattr(s, "controls", []):
            if ":" in c: ctrls.append(c)
            else: ctrls.append(f"{ns_prefix}{c}")
    return ctrls