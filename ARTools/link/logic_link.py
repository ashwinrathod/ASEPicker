# ARTools/link/logic_link.py
import bpy
import os
import re

def _safe_execute(message, purge_orphans=False):
    """Safely executes strict Viewport/Outliner operations and absorbs undo errors."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with bpy.context.temp_override(window=window, area=area, region=region):
                            if purge_orphans:
                                try:
                                    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
                                except Exception:
                                    pass
                            try:
                                bpy.ops.ed.undo_push(message=message)
                            except Exception:
                                pass 
                        return

def peek_file(filepath):
    """Opens a .blend file in read-only mode to extract its collection list."""
    if not os.path.exists(filepath):
        return []
    
    try:
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            return [col for col in data_from.collections if col]
    except Exception as e:
        print(f"[ARTools Link] Peek Error: {e}")
        return []

def generate_unique_namespace(base_name):
    """Generates a clean, incremented namespace (.01, .02) protecting original names."""
    clean_name = re.sub(r'\.\d+$', '', base_name)
        
    existing_names = set(c.name for c in bpy.data.collections)
    
    if clean_name not in existing_names:
        return clean_name
        
    idx = 1
    while f"{clean_name}.{idx:02d}" in existing_names:
        idx += 1
    return f"{clean_name}.{idx:02d}"

def link_collection(filepath, collection_name, custom_namespace="", push_undo=True):
    """Instantiates an Empty and executes Blender's native Override operator safely."""
    if not os.path.exists(filepath):
        print(f"[ARTools Link] File not found: {filepath}")
        return False
        
    try:
        with bpy.data.libraries.load(filepath, link=True) as (data_from, data_to):
            if collection_name in data_from.collections:
                data_to.collections = [collection_name]
            else:
                return False
                
        linked_col = data_to.collections[0]
        if not linked_col: return False
        
        # Take a snapshot of existing collections so we only rename the brand new one
        pre_collections = set(bpy.data.collections.keys())
        
        ns = custom_namespace if custom_namespace else collection_name
        empty_obj = bpy.data.objects.new(ns, None)
        empty_obj.instance_type = 'COLLECTION'
        empty_obj.instance_collection = linked_col
        
        bpy.context.scene.collection.objects.link(empty_obj)
        
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = empty_obj
        empty_obj.select_set(True)
        
        override_success = False
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            with bpy.context.temp_override(window=window, area=area, region=region):
                                try:
                                    bpy.ops.object.make_override_library()
                                    override_success = True
                                except Exception:
                                    pass
                            if override_success: break
                    if override_success: break
            if override_success: break

        # Rename ONLY the root collection. Leave internal rigs/bones alone!
        if override_success and custom_namespace:
            post_collections = set(bpy.data.collections.keys())
            new_collections = post_collections - pre_collections
            
            for c_name in new_collections:
                col = bpy.data.collections.get(c_name)
                if col and getattr(col, "override_library", None):
                    if getattr(col.override_library, "hierarchy_root", col) == col:
                        col.name = custom_namespace
                        break
                        
        bpy.context.view_layer.update()
        if hasattr(bpy.context, "evaluated_depsgraph_get"):
            bpy.context.evaluated_depsgraph_get().update()
            
        if push_undo:
            _safe_execute("ARTools_LinkCollection")
        return override_success
    except Exception as e:
        print(f"[ARTools Link] Process Error: {e}")
        return False

def scan_scene_links():
    """Universally scans for overrides, catching both script-generated and manually linked characters."""
    scene_links = []
    
    for col in bpy.data.collections:
        if getattr(col, "override_library", None):
            root_override = getattr(col.override_library, "hierarchy_root", None)
            if root_override and root_override != col:
                continue
                
            ref = col.override_library.reference
            if ref and getattr(ref, "library", None):
                lib = ref.library
                filepath = bpy.path.abspath(lib.filepath)
                is_missing = not os.path.exists(filepath)
                
                scene_links.append({
                    "name": col.name,             
                    "source_col": ref.name,       
                    "lib_name": lib.name,         
                    "filepath": lib.filepath,     
                    "abs_filepath": filepath,     
                    "is_missing": is_missing,
                    "is_unloaded": col.hide_viewport
                })
                
    return scene_links

def remove_override(collection_name, push_undo=True):
    """Recursively deletes an override collection safely."""
    target_col = bpy.data.collections.get(collection_name)
    if not target_col or not getattr(target_col, "override_library", None):
        return False

    # Force rename immediately to prevent namespace collisions if linking a new rig instantly
    target_col.name = target_col.name + "_PURGE"

    def get_all_children(col, col_list):
        col_list.append(col)
        for child in col.children:
            get_all_children(child, col_list)
            
    cols_to_remove = []
    get_all_children(target_col, cols_to_remove)
    
    objs_to_remove = set()
    for c in cols_to_remove:
        for obj in c.objects:
            objs_to_remove.add(obj)
            
    for obj in objs_to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)
        
    for c in cols_to_remove:
        bpy.data.collections.remove(c)
        
    bpy.context.view_layer.update()
    if push_undo:
        _safe_execute("ARTools_OverrideRemoved", purge_orphans=True)
    return True

def toggle_unload(collection_name):
    """Mutes or unmutes the rig to save Viewport performance."""
    col = bpy.data.collections.get(collection_name)
    if col:
        new_state = not col.hide_viewport
        col.hide_viewport = new_state
        col.hide_render = new_state
        bpy.context.view_layer.update()
        _safe_execute("ARTools_ToggleUnload")
        return True
    return False

def reload_library(lib_name):
    """Forces an immediate refresh of the external library data."""
    lib = bpy.data.libraries.get(lib_name)
    if lib:
        lib.reload()
        bpy.context.view_layer.update()
        return True
    return False

def make_local(collection_name):
    """Severs the external link and bakes the rig entirely into the current scene."""
    col = bpy.data.collections.get(collection_name)
    if not col: return False

    objs_to_localize = set(col.all_objects)
        
    cols_to_localize = []
    def get_all_children(c):
        for child in c.children:
            get_all_children(child)
        cols_to_localize.append(c)
    get_all_children(col)

    for obj in objs_to_localize:
        if getattr(obj, "animation_data", None) and getattr(obj.animation_data, "action", None):
            act = obj.animation_data.action
            if getattr(act, "override_library", None):
                act.make_local()
            
        if getattr(obj, "data", None) and getattr(obj.data, "override_library", None):
            obj.data.make_local()
                
        if getattr(obj, "override_library", None):
            obj.make_local()

    for c in cols_to_localize:
        if getattr(c, "override_library", None):
            c.make_local()

    bpy.context.view_layer.update()
    if hasattr(bpy.context, "evaluated_depsgraph_get"):
        bpy.context.evaluated_depsgraph_get().update()
            
    _safe_execute("ARTools_MakeLocal", purge_orphans=True)
    return True

def toggle_path_relativity(lib_name, make_relative=True):
    """Converts a library's filepath between Absolute and Relative."""
    lib = bpy.data.libraries.get(lib_name)
    if not lib: return False
    
    if make_relative:
        lib.filepath = bpy.path.relpath(lib.filepath)
    else:
        lib.filepath = bpy.path.abspath(lib.filepath)
        
    _safe_execute("ARTools_PathToggled")
    return True