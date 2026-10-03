"""Blender host services shared by ARTools modules.

Keep Blender API access in this module so the picker UI remains independent from
the DCC host and Blender 4.x/5.x API changes are isolated in one place.
"""

import bpy


_TRANSFORM_PROPERTIES = {
    "tx": ("location", 0),
    "ty": ("location", 1),
    "tz": ("location", 2),
    "translateX": ("location", 0),
    "translateY": ("location", 1),
    "translateZ": ("location", 2),
    "rx": ("rotation_euler", 0),
    "ry": ("rotation_euler", 1),
    "rz": ("rotation_euler", 2),
    "rotateX": ("rotation_euler", 0),
    "rotateY": ("rotation_euler", 1),
    "rotateZ": ("rotation_euler", 2),
    "rw": ("rotation_quaternion", 0),
    "rqx": ("rotation_quaternion", 1),
    "rqy": ("rotation_quaternion", 2),
    "rqz": ("rotation_quaternion", 3),
    "sx": ("scale", 0),
    "sy": ("scale", 1),
    "sz": ("scale", 2),
    "scaleX": ("scale", 0),
    "scaleY": ("scale", 1),
    "scaleZ": ("scale", 2),
}


def object_by_name(name):
    """Return a scene object or PoseBone for an ARTools control name, if it exists."""
    if not name:
        return None
        
    name_str = str(name)
    
    # Bridge Maya Namespace syntax to Blender Bones (Object:Bone)
    if ":" in name_str:
        obj_name, bone_name = name_str.rsplit(":", 1)
        obj = bpy.data.objects.get(obj_name)
        if obj and obj.type == 'ARMATURE':
            return obj.pose.bones.get(bone_name)

    return bpy.data.objects.get(name_str)


def active_view_layer():
    """Return the current window view layer, including timer callback contexts."""
    window = bpy.context.window
    if window:
        return window.view_layer

    return bpy.context.scene.view_layers[0]

def _get_bone_selected(pose_bone):
    """Return whether a bone is selected.

    Blender 5.0 moved bone selection state from ``Bone.select`` onto
    ``PoseBone.select`` and removed the old property entirely. Checking
    for the attribute first keeps this working on both the pre-5.0 and
    5.0+ layouts without hardcoding a version number.
    """
    if hasattr(pose_bone, "select"):
        return pose_bone.select

    return pose_bone.bone.select


def _set_bone_selected(pose_bone, state):
    """Set whether a bone is selected, matching the same 5.0 API change."""
    if hasattr(pose_bone, "select"):
        pose_bone.select = state
        return

    pose_bone.bone.select = state


def selected_object_names():
    """Return selected controls using the same string form stored by layouts.

    Reads bone selection through ``_get_bone_selected()`` and the
    per-object ``obj.mode`` instead of ``bpy.context.selected_pose_bones``
    / ``bpy.context.mode``. Those context members are only populated when a
    VIEW_3D area is considered active, which is not guaranteed when this
    runs from a PySide6 callback or QTimer poll -- exactly how ARTools calls
    it. Data-block flags are accurate no matter who calls this.
    """
    names = []
    view_layer = active_view_layer()

    for obj in view_layer.objects:
        if obj.type == 'ARMATURE' and obj.mode == 'POSE':
            for pose_bone in obj.pose.bones:
                if _get_bone_selected(pose_bone):
                    names.append(f"{obj.name}:{pose_bone.name}")
            continue

        if obj.select_get(view_layer=view_layer):
            names.append(obj.name)

    return names


def select_objects(names, replace=True):
    """Select existing controls and make the final selected control active."""
    view_layer = active_view_layer()

    if replace:
        for obj in view_layer.objects:
            obj.select_set(False)

        # Deselect bones on every armature currently in Pose Mode, not just
        # bpy.context.object -- that context member is not reliable when
        # this runs from a Qt callback.
        for obj in view_layer.objects:
            if obj.type == 'ARMATURE' and obj.mode == 'POSE':
                for pose_bone in obj.pose.bones:
                    _set_bone_selected(pose_bone, False)

    selected = []
    active_obj = None

    for name in names or []:
        name_str = str(name)

        if ":" in name_str:
            obj_name, bone_name = name_str.rsplit(":", 1)
            obj = bpy.data.objects.get(obj_name)
            if obj:
                obj.select_set(True)
                active_obj = obj

                if obj.type == 'ARMATURE':
                    if view_layer.objects.active != obj:
                        view_layer.objects.active = obj
                    if obj.mode != 'POSE':
                        bpy.ops.object.mode_set(mode='POSE')

                    pose_bone = obj.pose.bones.get(bone_name)
                    if pose_bone:
                        _set_bone_selected(pose_bone, True)
                        obj.data.bones.active = pose_bone.bone
                        selected.append(name_str)
        else:
            obj = bpy.data.objects.get(name_str)
            if obj and obj.name in view_layer.objects:
                obj.select_set(True)
                active_obj = obj
                selected.append(name_str)

    if active_obj:
        view_layer.objects.active = active_obj

    return selected


def _is_registered_property(obj, name):
    """Return True if ``name`` is a real bpy.props property on ``obj``
    (built-in, or added by an addon/rig script), as opposed to a plain
    ad-hoc custom property stored via ``obj[name] = value``.

    This matters because Blender rejects setting an ID-property with the
    same name as an already-registered property, so the two have to be
    written through different APIs (setattr vs. bracket syntax).
    """
    return name in obj.bl_rna.properties


def get_enum_items(obj, name):
    """Return (identifier, label) pairs for a registered EnumProperty.

    Returns an empty list if ``name`` is not a registered Enum property on
    ``obj``. Only static enum item lists are supported -- an Enum whose
    items are generated by a Python callback needs live UI context and
    can't be listed this way.
    """
    if not _is_registered_property(obj, name):
        return []

    rna_prop = obj.bl_rna.properties[name]
    if rna_prop.type != 'ENUM':
        return []

    return [(item.identifier, item.name) for item in rna_prop.enum_items]


def get_property(obj, name, default=None):
    """Read an ARTools control property from a Blender object."""
    transform = _TRANSFORM_PROPERTIES.get(name)
    if transform:
        return getattr(obj, transform[0])[transform[1]]

    if _is_registered_property(obj, name):
        return getattr(obj, name, default)

    return obj.get(name, default)


def set_property(obj, name, value, keyframe=False):
    """Set a transform, registered rig property, or custom property, and
    optionally insert a keyframe.

    A registered property (built-in, or added by an addon/rig via
    bpy.props -- e.g. a Rigify-style IK/FK EnumProperty) must be set with
    setattr(), never with obj[name].

    Built-in transform properties carry an internal Blender update
    callback that automatically flags the dependency graph and viewport
    as dirty. A custom or addon-registered property does not -- Blender
    has no way to know a driver, constraint, or shape key might read it,
    so the value changes but nothing downstream re-evaluates and the
    viewport never redraws. obj.id_data.update_tag() tells the depsgraph
    this ID needs re-evaluating; id_data resolves correctly whether obj
    is an Object or a PoseBone.
    """
    transform = _TRANSFORM_PROPERTIES.get(name)
    if transform:
        property_name, index = transform
        setattr_value = getattr(obj, property_name)
        setattr_value[index] = value
        if keyframe:
            obj.keyframe_insert(data_path=property_name, index=index)
        obj.id_data.update_tag()
        return

    if _is_registered_property(obj, name):
        setattr(obj, name, value)
        if keyframe:
            obj.keyframe_insert(data_path=name)
        obj.id_data.update_tag()
        return

    obj[name] = value
    if keyframe:
        obj.keyframe_insert(data_path='["%s"]' % name)
    obj.id_data.update_tag()


def keyframe_property(obj, name):
    """Insert a keyframe for a transform, registered rig property, or
    Blender custom property."""
    transform = _TRANSFORM_PROPERTIES.get(name)
    if transform:
        obj.keyframe_insert(data_path=transform[0], index=transform[1])
        return

    if _is_registered_property(obj, name):
        obj.keyframe_insert(data_path=name)
        return

    obj.keyframe_insert(data_path='["%s"]' % name)


def resolve_plug(plug):
    """Split an ARTools ``object.property`` reference into (obj, property_name).

    Returns (None, None) if the plug has no property segment, or the
    object/bone it points at can't be found. Shared by get_plug, set_plug,
    and anything that needs to inspect the property itself -- such as
    reading a Dropdown's Enum items -- rather than just its value.
    """
    if "." not in plug:
        return None, None

    object_name, property_name = plug.rsplit(".", 1)
    obj = object_by_name(object_name)
    if not obj:
        return None, None

    return obj, property_name


def get_plug(plug, default=None):
    """Read an ARTools ``object.property`` reference from Blender."""
    obj, property_name = resolve_plug(plug)
    if not obj:
        return default

    return get_property(obj, property_name, default)


def set_plug(plug, value, keyframe=False):
    """Set an ARTools ``object.property`` reference in Blender."""
    obj, property_name = resolve_plug(plug)
    if not obj:
        return False

    set_property(obj, property_name, value, keyframe=keyframe)
    return True


def get_plug_enum_items(plug):
    """Return (identifier, label) options for a plug pointing at a
    registered EnumProperty. Empty list if the plug doesn't resolve, or
    doesn't point at an Enum.
    """
    obj, property_name = resolve_plug(plug)
    if not obj:
        return []

    return get_enum_items(obj, property_name)


def scene_store(name="ARToolsStorage"):
    """Return the scene ID-property group used for saved picker layouts."""
    scene = bpy.context.scene
    storage = scene.get(name)

    if storage is None:
        scene[name] = {}
        storage = scene[name]

    return storage


def add_timer(callback, interval=0.1):
    """Register a persistent Blender timer when it is not already registered."""
    if not bpy.app.timers.is_registered(callback):
        bpy.app.timers.register(callback, first_interval=interval, persistent=True)


def _wake_main_loop():
    """No-op timer body. Registering this is what matters -- Blender
    processes pending window redraws as part of the same main-loop pass
    that runs registered timers, so scheduling one wakes that pass up
    almost immediately instead of waiting for a native window event.
    """
    return None


def refresh_blender_viewports(update_depsgraph=True):
    """Force Blender's dependency graph and all 3D Viewports to refresh.

    Property changes made from a PySide6 callback happen outside Blender's
    own operator/modal execution, so a plain area.tag_redraw() only queues
    a redraw for the next time Blender's window-manager loop wakes up --
    which may not happen until the user clicks a Blender window or changes
    frame. Scheduling a near-immediate bpy.app.timers callback wakes that
    loop up right away, silently and cheaply.

    bpy.ops.wm.redraw_timer can also force a redraw, but it always prints
    a benchmark report to the console when called from Python (hardcoded
    into the operator itself, not something an addon can silence) and was
    found here to stop reliably swapping after being called repeatedly
    from outside a real operator/modal context -- not safe to call on
    every Checkbox press or Slider drag tick.
    """
    if update_depsgraph:
        active_view_layer().update()

    for window in bpy.context.window_manager.windows:
        screen = window.screen
        if not screen:
            continue

        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

    if not bpy.app.timers.is_registered(_wake_main_loop):
        bpy.app.timers.register(_wake_main_loop, first_interval=0.0)


def remove_timer(callback):
    """Remove a previously registered Blender timer."""
    if bpy.app.timers.is_registered(callback):
        bpy.app.timers.unregister(callback)
