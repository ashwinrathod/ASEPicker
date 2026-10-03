bl_info = {
    "name": "ARTools",
    "author": "Ashwin",
    "version": (1, 6, 3),
    "blender": (4, 0, 0),
    "location": "View3D > Header",
    "category": "Animation",
}

import bpy
import bpy.utils.previews
import os

custom_icons = None

# --- VIEWPORT HEADER OPERATORS ---

class ARTOOLS_OT_launch_picker(bpy.types.Operator):
    bl_idname = "artools.launch_picker"
    bl_label = "ARTools Picker"
    bl_description = "Launch ARTools Picker"
    
    def execute(self, context):
        launch("picker")
        return {'FINISHED'}


class ARTOOLS_OT_launch_animbar(bpy.types.Operator):
    bl_idname = "artools.launch_animbar"
    bl_label = "ARTools AnimBar"
    bl_description = "Launch ARTools AnimBar"
    
    def execute(self, context):
        launch("animbar")
        return {'FINISHED'}


class ARTOOLS_OT_launch_library(bpy.types.Operator):
    bl_idname = "artools.launch_library"
    bl_label = "ARTools Library"
    bl_description = "Launch ARTools Library"
    
    def execute(self, context):
        launch("library")
        return {'FINISHED'}

class ARTOOLS_OT_launch_link_manager(bpy.types.Operator):
    bl_idname = "artools.launch_link_manager"
    bl_label = "ARTools Link Manager"
    bl_description = "Launch ARTools Maya-style Link Manager"
    
    def execute(self, context):
        launch("link_manager")
        return {'FINISHED'}


def draw_artools_header(self, context):
    """Injects the ARTools buttons precisely after the Viewport menus."""
    layout = self.layout
    # A small spacer makes it look native next to the menus
    layout.separator() 
    row = layout.row(align=True)
    
    global custom_icons
    
    def get_icon(name, fallback):
        if custom_icons and name in custom_icons:
            return {"icon_value": custom_icons[name].icon_id}
        return {"icon": fallback}
    
    row.operator(ARTOOLS_OT_launch_picker.bl_idname, text="", **get_icon("picker", "ARMATURE_DATA")) 
    row.operator(ARTOOLS_OT_launch_animbar.bl_idname, text="", **get_icon("animbar", "ACTION_TWEAK")) 
    row.operator(ARTOOLS_OT_launch_library.bl_idname, text="", **get_icon("library", "ASSET_MANAGER"))
    row.operator(ARTOOLS_OT_launch_link_manager.bl_idname, text="", **get_icon("link_manager", "LINKED"))


_classes = (
    ARTOOLS_OT_launch_picker,
    ARTOOLS_OT_launch_animbar,
    ARTOOLS_OT_launch_library,
    ARTOOLS_OT_launch_link_manager
)


def launch(module=None):
    """Open the requested ARTools module from Blender."""
    from . import router
    router.launch(module)


def register():
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    if not os.path.exists(icons_dir):
        icons_dir = os.path.join(os.path.dirname(__file__), "Icons")
        
    picker_icon = os.path.join(icons_dir, "artools.png")
    animbar_icon = os.path.join(icons_dir, "animbar.png")
    library_icon = os.path.join(icons_dir, "library.png")
    link_manager_icon = os.path.join(icons_dir, "link_manager.png")
    
    if os.path.exists(picker_icon):
        custom_icons.load("picker", picker_icon, 'IMAGE')
    if os.path.exists(animbar_icon):
        custom_icons.load("animbar", animbar_icon, 'IMAGE')
    if os.path.exists(library_icon):
        custom_icons.load("library", library_icon, 'IMAGE')
    if os.path.exists(link_manager_icon):
        custom_icons.load("link_manager", link_manager_icon, 'IMAGE')

    for cls in _classes:
        bpy.utils.register_class(cls)
    
    # --- CRITICAL FIX: Append exactly after Editor Menus instead of far right header ---
    bpy.types.VIEW3D_MT_editor_menus.append(draw_artools_header)


def unregister():
    global custom_icons
    
    bpy.types.VIEW3D_MT_editor_menus.remove(draw_artools_header)
    
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
        
    if custom_icons is not None:
        bpy.utils.previews.remove(custom_icons)
        custom_icons = None