import bpy
import os
import sys

# Global reference to keep PySide6 window alive
_link_manager_window = None

class ARTOOLS_OT_launch_link_manager(bpy.types.Operator):
    """Launch the ARTools Maya-style Link Manager"""
    bl_idname = "artools.launch_link_manager"
    bl_label = "ARTools Link Manager"

    def execute(self, context):
        global _link_manager_window
        from PySide6 import QtWidgets
        
        # Ensure QApplication exists
        app = QtWidgets.QApplication.instance()
        if not app:
            app = QtWidgets.QApplication(sys.argv)
            
        from ARTools.link.link_manager_ui import LinkManagerWindow
        
        if _link_manager_window is None or not _link_manager_window.isVisible():
            _link_manager_window = LinkManagerWindow()
            _link_manager_window.show()
        else:
            _link_manager_window.raise_()
            _link_manager_window.activateWindow()
            
        return {'FINISHED'}

# --- Viewport Header Injection ---

def draw_link_manager_button(self, context):
    layout = self.layout
    
    # Path to your custom icon
    current_dir = os.path.dirname(os.path.abspath(__file__)) 
    icons_dir = os.path.join(current_dir, "icons")
    icon_path = os.path.join(icons_dir, "link_manager.png")
    
    custom_icon_id = 0
    if os.path.exists(icon_path):
        import bpy.utils.previews
        pcoll = bpy.utils.previews.new()
        pcoll.load("link_manager_icon", icon_path, 'IMAGE')
        custom_icon_id = pcoll["link_manager_icon"].icon_id

    # Append right next to your existing buttons
    if custom_icon_id != 0:
        layout.operator(ARTOOLS_OT_launch_link_manager.bl_idname, text="", icon_value=custom_icon_id)
    else:
        layout.operator(ARTOOLS_OT_launch_link_manager.bl_idname, text="", icon='LINKED')


# Registration (Run this alongside your other classes)
def register():
    bpy.utils.register_class(ARTOOLS_OT_launch_link_manager)
    # Append to the right side of the 3D Viewport Header
    bpy.types.VIEW3D_HT_header.append(draw_link_manager_button)

def unregister():
    bpy.utils.unregister_class(ARTOOLS_OT_launch_link_manager)
    bpy.types.VIEW3D_HT_header.remove(draw_link_manager_button)