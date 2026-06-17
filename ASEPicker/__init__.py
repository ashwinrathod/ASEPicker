# ASEPicker/__init__.py

def launch(module=None):
    """Passes the launch command into the compiled router binary."""
    try:
        from . import router
        router.launch(module)
    except ImportError:
        import maya.cmds as cmds
        cmds.error("[ASEPicker] Core routing binary is missing or corrupted.")