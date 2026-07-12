# ARTools/picker_shapes.py
from PySide6 import QtWidgets, QtGui, QtCore

class PickerBaseShape(QtWidgets.QGraphicsObject):
    def __init__(self, label="Ctrl", controls=None, parent=None):
        QtWidgets.QGraphicsObject.__init__(self, parent)
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        import uuid
        self.item_id = str(uuid.uuid4())
        self.label = label
        self.controls = controls or []
        
        self.parent_links = []
        self.child_links = []
        self.scripts = []
        
        self.movable_edit = True
        self.locked = False
        self.locked_edit = False
        self.selectable_pose = True
        self._visual_state = "normal"
        self.maya_selection_state = "none" 

        self.placement_mode = "world"
        self.screen_anchor = "center"
        self.width = 60.0
        self.height = 30.0
        
        self.bg = {"normal": "#3c6e71", "hover": "#4d8c90", "press": "#2a4d4f"}
        self.edge_color = {"normal": "#111111", "hover": "#ffffff", "press": "#000000"}
        self.text_color = {"normal": "#ffffff", "hover": "#ffffff", "press": "#cccccc"}
        
        self.edge_visible = True
        self.edge_thickness = {"normal": 1.5, "hover": 2.0, "press": 1.5}
        self.font_point_size = 10
        self.font_bold = False
        self.font_italic = False
        self.text_align_h = "center"
        self.text_align_v = "center"

        self.command_type = "python"
        self.command_left = ""
        self.command_right = ""
        self.thumb_path = ""
        self.thumb_scale_mode = "fit"

    def box_rect(self): return QtCore.QRectF(-self.width/2.0, -self.height/2.0, self.width, self.height)
    def boundingRect(self): return self.box_rect().adjusted(-200, -200, 200, 200)
    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.box_rect())
        return path

    def get_color(self, color_dict, fallback):
        if getattr(self, "maya_selection_state", "none") == "full": state = "press"
        elif getattr(self, "maya_selection_state", "none") == "partial": state = "hover"
        else: state = self._visual_state
        col = color_dict.get(state, color_dict.get("normal", fallback))
        return col if isinstance(col, QtGui.QColor) else QtGui.QColor(col)

    def get_bg_color(self): return self.get_color(self.bg, "#3c6e71")
    def get_edge_color(self): return self.get_color(self.edge_color, "#111111")
    def get_text_color(self): return self.get_color(self.text_color, "#ffffff")

    def get_edge_thickness(self):
        if not isinstance(self.edge_thickness, dict): return float(self.edge_thickness)
        if getattr(self, "maya_selection_state", "none") == "full": state = "press"
        elif getattr(self, "maya_selection_state", "none") == "partial": state = "hover"
        else: state = self._visual_state
        return float(self.edge_thickness.get(state, self.edge_thickness.get("normal", 1.5)))

    def _draw_text(self, painter, rect):
        if not getattr(self, "label", ""): return
        font = painter.font()
        font.setPointSize(int(getattr(self, "font_point_size", 10)))
        font.setBold(bool(getattr(self, "font_bold", False)))
        font.setItalic(bool(getattr(self, "font_italic", False)))
        painter.setFont(font)
        painter.setPen(self.get_text_color())

        h_align = QtCore.Qt.AlignLeft if self.text_align_h == "left" else (QtCore.Qt.AlignRight if self.text_align_h == "right" else QtCore.Qt.AlignHCenter)
        v_align = QtCore.Qt.AlignTop if self.text_align_v == "up" else (QtCore.Qt.AlignBottom if self.text_align_v == "down" else QtCore.Qt.AlignVCenter)
        flags = h_align | v_align | QtCore.Qt.TextDontClip

        if self.text_align_v == "center":
            fm = QtGui.QFontMetricsF(font)
            tight = fm.tightBoundingRect(self.label)
            error = (fm.ascent() - fm.descent()) / 2.0 + tight.y() + tight.height() / 2.0
            draw_rect = rect.adjusted(0, -error, 0, -error)
            painter.drawText(draw_rect, flags, self.label)
        else:
            painter.drawText(rect, flags, self.label)

    def _draw_edit_selection(self, painter):
        scene = self.scene()
        is_edit = getattr(scene.views()[0], "is_edit_mode", False) if scene and scene.views() else False
        if self.isSelected() and is_edit:
            painter.save()
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 220), 2.0, QtCore.Qt.DashLine))
            painter.setBrush(QtCore.Qt.NoBrush)
            sx = (self.width + 6.0) / max(self.width, 1.0)
            sy = (self.height + 6.0) / max(self.height, 1.0)
            painter.scale(sx, sy)
            painter.drawPath(self.shape())
            painter.restore()

    def _draw_lock_tag(self, painter, box_rect):
        scene = self.scene()
        is_edit = getattr(scene.views()[0], "is_edit_mode", False) if scene and scene.views() else False
        if is_edit and self.locked_edit:
            painter.save()
            size = 12
            pad = 2
            x = box_rect.right() - size - pad
            y = box_rect.top() + pad
            
            painter.setBrush(QtGui.QColor(220, 50, 50))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(x, y + 4, size, size - 4)
            
            painter.setPen(QtGui.QPen(QtGui.QColor(220, 50, 50), 2))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawArc(x + 2, y, size - 4, 8, 0, 180 * 16)
            painter.restore()


class PickerRectangleItem(PickerBaseShape):
    shape_name = "Rectangle"
    def __init__(self, label="Ctrl", controls=None, parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
    
    def paint(self, painter, option, widget):
        box_rect = self.box_rect()
        painter.setBrush(self.get_bg_color())
        
        if getattr(self, "edge_visible", True):
            painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else:
            painter.setPen(QtCore.Qt.NoPen)
            
        painter.drawRect(box_rect)
        self._draw_text(painter, box_rect)
        self._draw_edit_selection(painter)

        self._draw_lock_tag(painter, box_rect)

class PickerSliderItem(PickerBaseShape):
    shape_name = "Slider"
    def __init__(self, label="Slider", controls=None, parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
        self.attribute = ""
        self.inside_text = False
        self.min_value = 0.0
        self.max_value = 1.0
        self.value = 0.0
        self.handle_scale = 1.0
        self.handle_color = QtGui.QColor("#bfbfbf")

    def paint(self, painter, option, widget):
        box_rect = self.box_rect()
        
        # Turn on Antialiasing for buttery smooth UI curves!
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        
        # 1. THE PILL BACKGROUND
        painter.setBrush(self.get_bg_color())
        if getattr(self, "edge_visible", True): 
            painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else: 
            painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(box_rect, 6, 6)
        
        # Math Setup
        rng = self.max_value - self.min_value
        pct = 0.0 if rng == 0 else (self.value - self.min_value) / rng
        pct = max(0.0, min(1.0, pct))
        hc = self.handle_color if isinstance(self.handle_color, QtGui.QColor) else QtGui.QColor(self.handle_color)

        # 2. THE STUDIO TRACK (Groove & Fill)
        track_pad = 10.0
        track_h = 6.0
        track_w = max(0.0, box_rect.width() - (track_pad * 2))
        track_rect = QtCore.QRectF(box_rect.left() + track_pad, box_rect.center().y() - (track_h / 2.0), track_w, track_h)
        
        # Dark Groove Background
        painter.setBrush(QtGui.QColor(15, 15, 15, 180))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(track_rect, track_h / 2.0, track_h / 2.0)
        
        # --- NEW: BI-DIRECTIONAL ZERO-ORIGIN FILL ---
        # Find exactly where "0" lives on this specific slider
        zero_val = max(self.min_value, min(self.max_value, 0.0))
        zero_pct = 0.0 if rng == 0 else (zero_val - self.min_value) / rng
        
        # Calculate the distance between Zero and the Handle
        fill_start_pct = min(zero_pct, pct)
        fill_width_pct = abs(pct - zero_pct)
        fill_w = track_w * fill_width_pct
        
        if fill_w > 0:
            fill_x = track_rect.left() + (track_w * fill_start_pct)
            fill_rect = QtCore.QRectF(fill_x, track_rect.top(), fill_w, track_h)
            
            fill_color = QtGui.QColor(hc)
            fill_color.setAlpha(180) # Slightly transparent so the handle pops
            painter.setBrush(fill_color)
            painter.drawRoundedRect(fill_rect, track_h / 2.0, track_h / 2.0)
        # --------------------------------------------

        # 3. THE TACTILE GRIP HANDLE
        hw = box_rect.height() * 0.3 * self.handle_scale
        hw = max(hw, 12.0) # Ensure handle is wide enough for the grip lines
        hh = box_rect.height() * 1.1 * self.handle_scale
        hx = box_rect.left() + track_pad + (track_w * pct) - (hw / 2)
        hy = box_rect.center().y() - (hh / 2)
        
        # Handle Body
        painter.setBrush(hc)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.5)) # Crisp dark outline
        handle_rect = QtCore.QRectF(hx, hy, hw, hh)
        painter.drawRoundedRect(handle_rect, 3, 3)
        
        # Handle Grip Lines (The tactile physical feel)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 100), 1.0))
        center_hx = hx + (hw / 2.0)
        grip_y1 = hy + (hh * 0.25)
        grip_y2 = hy + (hh * 0.75)
        # Draw 3 vertical rib lines
        painter.drawLine(QtCore.QPointF(center_hx, grip_y1), QtCore.QPointF(center_hx, grip_y2))
        painter.drawLine(QtCore.QPointF(center_hx - 3, grip_y1), QtCore.QPointF(center_hx - 3, grip_y2))
        painter.drawLine(QtCore.QPointF(center_hx + 3, grip_y1), QtCore.QPointF(center_hx + 3, grip_y2))

        # 4. RETAIN THE EXACT SAME TEXT LOGIC
        if self.label:
            if getattr(self, "inside_text", False):
                self._draw_text(painter, box_rect)
            else:
                painter.setPen(self.get_text_color())
                font = painter.font()
                font.setPointSize(int(getattr(self, "font_point_size", 10)))
                font.setBold(bool(getattr(self, "font_bold", False)))
                font.setItalic(bool(getattr(self, "font_italic", False)))
                painter.setFont(font)
                
                align_h = getattr(self, "text_align_h", "center")
                align_v = getattr(self, "text_align_v", "center")
                margin = 8
                
                text_rect = QtCore.QRectF()
                flags = QtCore.Qt.TextDontClip
                
                if align_v == "up":
                    text_rect = QtCore.QRectF(box_rect.left(), box_rect.top() - 50 - margin, box_rect.width(), 50)
                    flags |= QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom
                elif align_v == "down":
                    text_rect = QtCore.QRectF(box_rect.left(), box_rect.bottom() + margin, box_rect.width(), 50)
                    flags |= QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop
                elif align_h == "left":
                    text_rect = QtCore.QRectF(box_rect.left() - 200 - margin, box_rect.top(), 200, box_rect.height())
                    flags |= QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                else: 
                    text_rect = QtCore.QRectF(box_rect.right() + margin, box_rect.top(), 200, box_rect.height())
                    flags |= QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
                    
                painter.drawText(text_rect, flags, self.label)
        
        self._draw_edit_selection(painter)
        self._draw_lock_tag(painter, box_rect)

    def update_from_drag(self, scene_pos):
        local_pos = self.mapFromScene(scene_pos)
        box_rect = self.box_rect()
        x = local_pos.x() - box_rect.left()
        
        w = box_rect.width()
        pct = max(0.0, min(1.0, x / w)) if w != 0 else 0.0
        
        self.value = self.min_value + (self.max_value - self.min_value) * pct
        self.update()

class PickerRoundRectangleItem(PickerRectangleItem):
    shape_name = "Round Rectangle"
    
    def __init__(self, label="Ctrl", controls=None, parent=None):
        PickerRectangleItem.__init__(self, label, controls, parent)
        self.rad_tl = 4.0
        self.rad_tr = 4.0
        self.rad_bl = 4.0
        self.rad_br = 4.0

    def shape(self):
        path = QtGui.QPainterPath()
        r = self.box_rect()
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        
        rtl = max(0.0, min(self.rad_tl, w / 2.0, h / 2.0))
        rtr = max(0.0, min(self.rad_tr, w / 2.0, h / 2.0))
        rbr = max(0.0, min(self.rad_br, w / 2.0, h / 2.0))
        rbl = max(0.0, min(self.rad_bl, w / 2.0, h / 2.0))
        
        path.moveTo(x + rtl, y)
        path.lineTo(x + w - rtr, y)
        if rtr > 0: path.arcTo(x + w - 2*rtr, y, 2*rtr, 2*rtr, 90, -90)
        
        path.lineTo(x + w, y + h - rbr)
        if rbr > 0: path.arcTo(x + w - 2*rbr, y + h - 2*rbr, 2*rbr, 2*rbr, 0, -90)
        
        path.lineTo(x + rbl, y + h)
        if rbl > 0: path.arcTo(x, y + h - 2*rbl, 2*rbl, 2*rbl, 270, -90)
        
        path.lineTo(x, y + rtl)
        if rtl > 0: path.arcTo(x, y, 2*rtl, 2*rtl, 180, -90)
        
        path.closeSubpath()
        return path
        
    def paint(self, painter, option, widget):
        box_rect = self.box_rect()
        painter.setBrush(self.get_bg_color())
        
        if getattr(self, "edge_visible", True):
            painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else: 
            painter.setPen(QtCore.Qt.NoPen)
            
        painter.drawPath(self.shape())
        
        self._draw_text(painter, box_rect)
        self._draw_edit_selection(painter) 
        self._draw_lock_tag(painter, box_rect)

class PickerCircleItem(PickerRectangleItem):
    shape_name = "Circle"
    def __init__(self, label="Ctrl", controls=None, parent=None):
        PickerRectangleItem.__init__(self, label, controls, parent)
    
    def shape(self):
        path = QtGui.QPainterPath()
        path.addEllipse(self.box_rect())
        return path
        
    def paint(self, painter, option, widget):
        box_rect = self.box_rect()
        painter.setBrush(self.get_bg_color())
        
        if getattr(self, "edge_visible", True):
            painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else: 
            painter.setPen(QtCore.Qt.NoPen)
            
        painter.drawEllipse(box_rect)
        self._draw_text(painter, box_rect)
        self._draw_edit_selection(painter)

        self._draw_lock_tag(painter, box_rect)

class PickerPolygonItem(PickerBaseShape):
    shape_name = "Polygon"
    def __init__(self, label="Ctrl", controls=None, points=None, parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
        self.setAcceptHoverEvents(True)
        self.is_editing_points = False
        self.active_handle = None
        self.hovered_handle = None
        self.selected_points = set()
        
        self._cached_path = None
        self._cached_rect = None
        
        self.path_points = [
            {"p": QtCore.QPointF(-30, -15), "in": QtCore.QPointF(0,0), "out": QtCore.QPointF(0,0), "s": False},
            {"p": QtCore.QPointF(30, -15), "in": QtCore.QPointF(0,0), "out": QtCore.QPointF(0,0), "s": False},
            {"p": QtCore.QPointF(30, 15), "in": QtCore.QPointF(0,0), "out": QtCore.QPointF(0,0), "s": False},
            {"p": QtCore.QPointF(-30, 15), "in": QtCore.QPointF(0,0), "out": QtCore.QPointF(0,0), "s": False}
        ]
        self._calculate_rect()

    def _get_handle_size(self):
        try:
            from .preferences import PrefManager
            base_size = float(PrefManager().get("poly_handle_size") or 8.0)
            scene = self.scene()
            if scene and scene.views():
                zoom = scene.views()[0].transform().m11()
                if zoom > 0: return base_size / zoom
        except: pass
        return 8.0
    
    def setRect(self, x, y, w, h):
        current_rect = self._get_drawn_path().boundingRect()
        old_w = current_rect.width()
        old_h = current_rect.height()
        
        if old_w <= 0.001 or old_h <= 0.001: return
        
        scale_x = w / old_w
        scale_y = h / old_h
        
        if abs(scale_x - 1.0) < 0.0001 and abs(scale_y - 1.0) < 0.0001:
            return
            
        for pt in self.path_points:
            pt["p"].setX(pt["p"].x() * scale_x); pt["p"].setY(pt["p"].y() * scale_y)
            pt["in"].setX(pt["in"].x() * scale_x); pt["in"].setY(pt["in"].y() * scale_y)
            pt["out"].setX(pt["out"].x() * scale_x); pt["out"].setY(pt["out"].y() * scale_y)
            
        self._calculate_rect()

    def _get_drawn_path(self):
        if getattr(self, "_cached_path", None) is None:
            path = QtGui.QPainterPath()
            if self.path_points:
                path.moveTo(self.path_points[0]["p"])
                for i in range(1, len(self.path_points) + 1):
                    prev = self.path_points[i-1]
                    curr = self.path_points[i % len(self.path_points)]
                    if prev["out"].isNull() and curr["in"].isNull(): path.lineTo(curr["p"])
                    else: path.cubicTo(prev["p"] + prev["out"], curr["p"] + curr["in"], curr["p"])
            self._cached_path = path
        return self._cached_path

    def _calculate_rect(self):
        self.prepareGeometryChange()
        self._cached_path = None; self._cached_rect = None
        rect = self._get_drawn_path().boundingRect()
        self.width = max(rect.width(), 10.0); self.height = max(rect.height(), 10.0)

    def box_rect(self): 
        if getattr(self, "_cached_rect", None) is None: self._cached_rect = self._get_drawn_path().boundingRect()
        return self._cached_rect

    def boundingRect(self):
        br = self.box_rect()
        if self.is_editing_points:
            # FIX: Dynamically pad the bounding box so handles are NEVER clipped!
            extra = max(20.0, self._get_handle_size() * 3.5)
            for pt in self.path_points:
                br = br.united(QtCore.QRectF(pt["p"].x() - extra, pt["p"].y() - extra, extra*2, extra*2))
                if not pt["in"].isNull():
                    hp = pt["p"] + pt["in"]
                    br = br.united(QtCore.QRectF(hp.x() - extra, hp.y() - extra, extra*2, extra*2))
                if not pt["out"].isNull():
                    hp = pt["p"] + pt["out"]
                    br = br.united(QtCore.QRectF(hp.x() - extra, hp.y() - extra, extra*2, extra*2))
                    
        pen_width = self.get_edge_thickness() if getattr(self, "edge_visible", True) else 0
        return br.adjusted(-pen_width, -pen_width, pen_width, pen_width)

    def shape(self):
        hit_path = QtGui.QPainterPath()
        hit_path.setFillRule(QtCore.Qt.WindingFill)
        
        # 1. The visible shape (so clicking the inside fill still works)
        base_path = self._get_drawn_path()
        hit_path.addPath(base_path)
        
        # 2. Add a precise, tight border exactly matching the line thickness
        thickness = self.get_edge_thickness() if getattr(self, "edge_visible", True) else 4.0
        stroker = QtGui.QPainterPathStroker()
        stroker.setWidth(max(thickness, 4.0))
        hit_path.addPath(stroker.createStroke(base_path))

        # 3. Only add tight, perfectly sized hit-boxes for the points (No more 40px bloat!)
        if self.is_editing_points:
            sz = self._get_handle_size()
            hit_size = sz * 2.5 
            h = hit_size / 2.0
            
            for pt in self.path_points:
                hit_path.addRect(QtCore.QRectF(pt["p"].x() - h, pt["p"].y() - h, hit_size, hit_size))
                if not pt["in"].isNull():
                    hp = pt["p"] + pt["in"]
                    hit_path.addRect(QtCore.QRectF(hp.x() - h, hp.y() - h, hit_size, hit_size))
                if not pt["out"].isNull():
                    hp = pt["p"] + pt["out"]
                    hit_path.addRect(QtCore.QRectF(hp.x() - h, hp.y() - h, hit_size, hit_size))
                    
        return hit_path

    def paint(self, painter, option, widget):
        painter.setBrush(self.get_bg_color())
        if getattr(self, "edge_visible", True): painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else: painter.setPen(QtCore.Qt.NoPen)
            
        painter.drawPath(self._get_drawn_path())
        box_rect = self.box_rect()
        
        self._draw_text(painter, box_rect)
            
        self._draw_edit_selection(painter)
        self._draw_lock_tag(painter, box_rect)
        if self.is_editing_points: self._draw_handles(painter)

    def _draw_edit_selection(self, painter):
        """Override specifically for Polygons to ensure accurate non-distorted outlines."""
        
        # 1: Hide the dashed outline while actively editing points! ---
        if self.is_editing_points:
            return
            
        scene = self.scene()
        is_edit = getattr(scene.views()[0], "is_edit_mode", False) if scene and scene.views() else False
        if self.isSelected() and is_edit:
            painter.save()
            
            # 2: Draw the line exactly on the edge to avoid math distortion! ---
            # By making the line slightly thicker (2.5), it acts as a perfect non-distorting highlight
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 220), 2.5, QtCore.Qt.DashLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            painter.setBrush(QtCore.Qt.NoBrush)
            
            # Draw the EXACT contour of the polygon without any scaling
            painter.drawPath(self._get_drawn_path())
            painter.restore()

    def _draw_handles(self, painter):
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        sz = self._get_handle_size()
        rad = sz / 2.0
        
        zoom = self.scene().views()[0].transform().m11() if self.scene() and self.scene().views() else 1.0
        line_w = max(1.5 / zoom, 0.1)
        
        for i, pt in enumerate(self.path_points):
            if not pt["in"].isNull() or not pt["out"].isNull() or pt["s"]:
                painter.setPen(QtGui.QPen(QtGui.QColor(200, 200, 200), line_w, QtCore.Qt.DashLine))
                if not pt["in"].isNull(): painter.drawLine(pt["p"], pt["p"] + pt["in"])
                if not pt["out"].isNull(): painter.drawLine(pt["p"], pt["p"] + pt["out"])
                
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(0, 150, 255))
            if not pt["in"].isNull(): painter.drawEllipse(pt["p"] + pt["in"], rad, rad)
            if not pt["out"].isNull(): painter.drawEllipse(pt["p"] + pt["out"], rad, rad)

            if getattr(self, "selected_points", None) and i in self.selected_points:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), line_w * 2))
                painter.setBrush(QtGui.QColor(200, 50, 255))
            else:
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), line_w))
                if self.hovered_handle == (i, 'p'): painter.setBrush(QtGui.QColor(255, 200, 0))
                else: painter.setBrush(QtGui.QColor(0, 255, 0) if pt["s"] else QtGui.QColor(255, 0, 0))
            
            painter.drawRect(QtCore.QRectF(pt["p"].x() - rad, pt["p"].y() - rad, sz, sz))

    def _get_handle_at(self, pos):
        sz = self._get_handle_size()
        hit = sz * 2.5
        h = hit / 2.0
        
        for i in reversed(range(len(self.path_points))):
            pt = self.path_points[i]
            if not pt["in"].isNull() and QtCore.QRectF(pt["p"].x() + pt["in"].x() - h, pt["p"].y() + pt["in"].y() - h, hit, hit).contains(pos): return (i, 'in')
            if not pt["out"].isNull() and QtCore.QRectF(pt["p"].x() + pt["out"].x() - h, pt["p"].y() + pt["out"].y() - h, hit, hit).contains(pos): return (i, 'out')
        for i in reversed(range(len(self.path_points))):
            pt = self.path_points[i]
            if QtCore.QRectF(pt["p"].x() - h, pt["p"].y() - h, hit, hit).contains(pos): return (i, 'p')
        return None

    def _get_closest_segment(self, local_pos):
        min_dist = float('inf'); best_idx = 0
        for i in range(len(self.path_points)):
            p1 = self.path_points[i]["p"]; p2 = self.path_points[(i + 1) % len(self.path_points)]["p"]
            l2 = (p1.x() - p2.x())**2 + (p1.y() - p2.y())**2
            if l2 == 0: dist = (local_pos.x() - p1.x())**2 + (local_pos.y() - p1.y())**2
            else:
                t = max(0.0, min(1.0, ((local_pos.x() - p1.x()) * (p2.x() - p1.x()) + (local_pos.y() - p1.y()) * (p2.y() - p1.y())) / l2))
                dist = (local_pos.x() - (p1.x() + t * (p2.x() - p1.x())))**2 + (local_pos.y() - (p1.y() + t * (p2.y() - p1.y())))**2
            if dist < min_dist: min_dist = dist; best_idx = i
        return best_idx

    def _get_closest_point(self, local_pos):
        min_dist = float('inf'); best_idx = None
        for i, pt in enumerate(self.path_points):
            dist = (local_pos.x() - pt["p"].x())**2 + (local_pos.y() - pt["p"].y())**2
            if dist < min_dist: min_dist = dist; best_idx = i
        return best_idx

    def toggle_edit_mode(self):
        self.prepareGeometryChange()
        self.is_editing_points = not self.is_editing_points
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, not self.is_editing_points)
        
        scene = self.scene()
        if scene and scene.views():
            view = scene.views()[0]
            if self.is_editing_points:
                view._exclusive_poly = self
                self.setSelected(True)
            else:
                if getattr(view, "_exclusive_poly", None) == self:
                    view._exclusive_poly = None
                    
        self._calculate_rect()
        self.update()
        
    def context_add_point(self, scene_pos):
        idx = self._get_closest_segment(self.mapFromScene(scene_pos))
        if idx is not None:
            self.path_points.insert(idx + 1, {"p": self.mapFromScene(scene_pos), "in": QtCore.QPointF(0,0), "out": QtCore.QPointF(0,0), "s": False})
            self._calculate_rect(); self.update()
            scene = self.scene()
            if scene and scene.views() and hasattr(scene.views()[0].window(), "menu_action_requested"):
                scene.views()[0].window().menu_action_requested.emit("push_undo")

    def context_remove_point(self, scene_pos):
        if len(self.path_points) <= 3: return
        idx = self._get_closest_point(self.mapFromScene(scene_pos))
        if idx is not None:
            self.path_points.pop(idx)
            self._calculate_rect(); self.update()
            scene = self.scene()
            if scene and scene.views() and hasattr(scene.views()[0].window(), "menu_action_requested"):
                scene.views()[0].window().menu_action_requested.emit("push_undo")

    def context_toggle_smooth(self, scene_pos):
        idx = self._get_closest_point(self.mapFromScene(scene_pos))
        if idx is not None:
            pt = self.path_points[idx]
            pt["s"] = not pt["s"]
            if pt["s"]:
                import math
                n = len(self.path_points)
                p_prev = self.path_points[(idx - 1) % n]["p"]
                p_curr = pt["p"]
                p_next = self.path_points[(idx + 1) % n]["p"]
                
                dx = p_next.x() - p_prev.x()
                dy = p_next.y() - p_prev.y()
                
                dist = math.hypot(dx, dy)
                if dist > 0: dx /= dist; dy /= dist
                else: dx, dy = 1.0, 0.0
                
                dist_prev = math.hypot(p_curr.x() - p_prev.x(), p_curr.y() - p_prev.y())
                dist_next = math.hypot(p_next.x() - p_curr.x(), p_next.y() - p_curr.y())
                
                len_in = dist_prev * 0.25
                len_out = dist_next * 0.25
                
                pt["in"] = QtCore.QPointF(-dx * len_in, -dy * len_in)
                pt["out"] = QtCore.QPointF(dx * len_out, dy * len_out)
            else:
                pt["in"] = QtCore.QPointF(0, 0)
                pt["out"] = QtCore.QPointF(0, 0)
                
            self._calculate_rect(); self.update()
            scene = self.scene()
            if scene and scene.views() and hasattr(scene.views()[0].window(), "menu_action_requested"):
                scene.views()[0].window().menu_action_requested.emit("push_undo")

    def align_selected_points(self, alignment):
        if not getattr(self, "selected_points", None) or len(self.selected_points) < 2: return
        pts = [self.path_points[i]["p"] for i in self.selected_points]
        
        if alignment == "left": val = min(p.x() for p in pts)
        elif alignment == "right": val = max(p.x() for p in pts)
        elif alignment == "top": val = min(p.y() for p in pts)
        elif alignment == "bottom": val = max(p.y() for p in pts)
        elif alignment == "center_x": val = sum(p.x() for p in pts) / len(pts)
        elif alignment == "center_y": val = sum(p.y() for p in pts) / len(pts)
        
        for i in self.selected_points:
            if alignment in ["left", "right", "center_x"]: self.path_points[i]["p"].setX(val)
            else: self.path_points[i]["p"].setY(val)
            
        self._calculate_rect()
        self.update()

class PickerTextItem(PickerRectangleItem):
    shape_name = "Text"
    def __init__(self, label="Ctrl", controls=None, parent=None):
        PickerRectangleItem.__init__(self, label, controls, parent)
        self.text_orientation = "Horizontal"
        self.text_v_gap = 0.0
    
    def paint(self, painter, option, widget):
        original_label = getattr(self, "label", "")
        is_vertical = getattr(self, "text_orientation", "Horizontal") == "Vertical"
        
        if not is_vertical or not original_label:
            self._draw_text(painter, self.box_rect())
        else:
            # --- CUSTOM VERTICAL ENGINE ---
            painter.save()
            rect = self.box_rect()
            
            font = painter.font()
            font.setPointSize(int(getattr(self, "font_point_size", 10)))
            font.setBold(bool(getattr(self, "font_bold", False)))
            font.setItalic(bool(getattr(self, "font_italic", False)))
            painter.setFont(font)
            painter.setPen(self.get_text_color())
            
            v_gap = getattr(self, "text_v_gap", 0.0)
            fm = QtGui.QFontMetricsF(font)
            
            # The exact height of the letter, plus user's custom gap
            char_h = fm.height()
            step = char_h + v_gap
            
            chars = list(original_label)
            total_height = (char_h * len(chars)) + (v_gap * (len(chars) - 1))
            
            align_h = getattr(self, "text_align_h", "center")
            align_v = getattr(self, "text_align_v", "center")
            
            if align_v == "up": start_y = rect.top()
            elif align_v == "down": start_y = rect.bottom() - total_height
            else: start_y = rect.center().y() - (total_height / 2.0)
            
            qt_align = QtCore.Qt.TextDontClip | QtCore.Qt.AlignTop
            if align_h == "left": qt_align |= QtCore.Qt.AlignLeft
            elif align_h == "right": qt_align |= QtCore.Qt.AlignRight
            else: qt_align |= QtCore.Qt.AlignHCenter
            
            for i, char in enumerate(chars):
                char_rect = QtCore.QRectF(rect.left(), start_y + (i * step), rect.width(), char_h)
                painter.drawText(char_rect, qt_align, char)
                
            painter.restore()
            
        self._draw_edit_selection(painter)
        self._draw_lock_tag(painter, self.box_rect())

class PickerPoseItem(PickerBaseShape):
    shape_name = "Pose"
    def __init__(self, label="Pose", controls=None, pose_data=None, parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
        self.pose_data = pose_data or {}
        
        self.image_path = ""
        self.inside_text = False
        self.pose_shape = "Rectangle"
        self.pose_scale_mode = "Fit"
        self.pose_padding = 0.0
        self.pose_roundness = 8.0
        
        self._drag_pct = None

    def shape(self):
        path = QtGui.QPainterPath()
        br = self.box_rect()
        if self.pose_shape == "Circle": path.addEllipse(br)
        elif self.pose_shape == "Round Rectangle": 
            r = getattr(self, "pose_roundness", 8.0)
            path.addRoundedRect(br, r, r)
        else: path.addRect(br)
        return path

    def paint(self, painter, option, widget):
        box_rect = self.box_rect()
        painter.setBrush(self.get_bg_color())
        
        if getattr(self, "edge_visible", True): painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else: painter.setPen(QtCore.Qt.NoPen)
        
        clip_path = self.shape()
        painter.drawPath(clip_path)
        
        img_path = getattr(self, "image_path", "")
        if img_path:
            import os
            if not os.path.isabs(img_path):
                base = getattr(self.scene().views()[0].window(), "image_base_dir", "")
                img_path = os.path.join(base, img_path)
                
            if not hasattr(self, "_cached_pixmap") or getattr(self, "_last_image_path", "") != img_path:
                self._cached_pixmap = QtGui.QPixmap(img_path) if os.path.exists(img_path) else None
                self._last_image_path = img_path
                
            pixmap = self._cached_pixmap
            if pixmap and not pixmap.isNull():
                painter.save()
                painter.setClipPath(clip_path)
                
                pad = self.pose_padding
                img_rect = box_rect.adjusted(pad, pad, -pad, -pad)
                
                if self.pose_scale_mode == "Stretch":
                    painter.drawPixmap(img_rect.toRect(), pixmap)
                else:
                    aspect_ratio = QtCore.Qt.KeepAspectRatio if self.pose_scale_mode == "Fit" else QtCore.Qt.KeepAspectRatioByExpanding
                    scaled_pix = pixmap.scaled(img_rect.size().toSize(), aspect_ratio, QtCore.Qt.SmoothTransformation)
                    px = img_rect.center().x() - scaled_pix.width()/2.0
                    py = img_rect.center().y() - scaled_pix.height()/2.0
                    painter.drawPixmap(QtCore.QPointF(px, py), scaled_pix)
                painter.restore()

        if getattr(self, "_drag_pct", None) is not None:
            pct = max(0.0, min(1.0, self._drag_pct))
            painter.save()
            painter.setClipPath(clip_path)
            
            painter.setBrush(QtGui.QColor(0, 0, 0, 120))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(box_rect)
            
            curtain_width = box_rect.width() * pct
            curtain_rect = QtCore.QRectF(box_rect.left(), box_rect.top(), curtain_width, box_rect.height())
            painter.setBrush(QtGui.QColor(100, 200, 100, 140))
            painter.drawRect(curtain_rect)
            
            painter.setPen(QtGui.QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(int(getattr(self, "font_point_size", 10)) + 6)
            font.setBold(True)
            painter.setFont(font)
            pct_label = f"{int(pct * 100)}%"
            fm = QtGui.QFontMetricsF(font)
            tight = fm.tightBoundingRect(pct_label)
            error = (fm.ascent() - fm.descent()) / 2.0 + tight.y() + tight.height() / 2.0
            pct_rect = box_rect.adjusted(0, -error, 0, -error)
            painter.drawText(pct_rect, QtCore.Qt.AlignCenter, pct_label)
            painter.restore()

        if self.label:
            if getattr(self, "inside_text", False):
                self._draw_text(painter, box_rect)
            else:
                painter.setPen(self.get_text_color())
                font = painter.font()
                font.setPointSize(int(getattr(self, "font_point_size", 10)))
                font.setBold(bool(getattr(self, "font_bold", False)))
                font.setItalic(bool(getattr(self, "font_italic", False)))
                painter.setFont(font)
                
                align_h = getattr(self, "text_align_h", "center")
                align_v = getattr(self, "text_align_v", "center")
                margin = 8
                
                text_rect = QtCore.QRectF()
                flags = QtCore.Qt.TextDontClip
                
                if align_v == "up":
                    text_rect = QtCore.QRectF(box_rect.left(), box_rect.top() - 50 - margin, box_rect.width(), 50)
                    flags |= QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom
                elif align_v == "down":
                    text_rect = QtCore.QRectF(box_rect.left(), box_rect.bottom() + margin, box_rect.width(), 50)
                    flags |= QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop
                elif align_h == "left":
                    text_rect = QtCore.QRectF(box_rect.left() - 200 - margin, box_rect.top(), 200, box_rect.height())
                    flags |= QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                else: 
                    text_rect = QtCore.QRectF(box_rect.right() + margin, box_rect.top(), 200, box_rect.height())
                    flags |= QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
                    
                painter.drawText(text_rect, flags, self.label)
            
        self._draw_edit_selection(painter)
        self._draw_lock_tag(painter, box_rect)

    def update_from_drag(self, scene_pos):
        local_pos = self.mapFromScene(scene_pos)
        box_rect = self.box_rect()
        
        start_x = getattr(self, "_drag_start_x", box_rect.left())
        delta_x = local_pos.x() - start_x
        
        drag_range = max(box_rect.width(), 10.0) 
        
        pct = max(0.0, min(1.0, delta_x / drag_range))
        self._drag_pct = pct
        self.update()
        return pct

class PickerCheckboxItem(PickerBaseShape):
    shape_name = "Checkbox"
    def __init__(self, label="Toggle", controls=None, parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
        self.is_checked = False
        self.show_mark = True
        self.mark_color = QtGui.QColor("#ffffff")
        
        self.cb_shape = "Rectangle"
        self.cb_roundness = 8.0
        self.inside_text = False
        
        self.text_inside = False
        self.cb_data = {
            "ON": {"attributes": {}, "shapes": [], "text": "ON", "color": "#4d8c90", "command": "", "cmd_type": "python"},
            "OFF": {"attributes": {}, "shapes": [], "text": "OFF", "color": "#3c6e71", "command": "", "cmd_type": "python"}
        }

    def get_bg_color(self):
        state_key = "ON" if getattr(self, "is_checked", False) else "OFF"
        base_color = self.cb_data.get(state_key, {}).get("color", "")
        if self._visual_state == "hover": return QtGui.QColor(self.bg.get("hover", "#4d8c90"))
        elif self._visual_state == "press": return QtGui.QColor(self.bg.get("press", "#2a4d4f"))
        if base_color: return QtGui.QColor(base_color)
        return QtGui.QColor(self.bg.get("normal", "#3c6e71"))

    def shape(self):
        path = QtGui.QPainterPath()
        br = self.box_rect()
        if getattr(self, "cb_shape", "Rectangle") == "Circle": path.addEllipse(br)
        elif getattr(self, "cb_shape", "Rectangle") == "Round Rectangle": 
            r = getattr(self, "cb_roundness", 8.0)
            path.addRoundedRect(br, r, r)
        else: path.addRect(br)
        return path

    def paint(self, painter, option, widget):
        box_rect = self.box_rect()
        painter.setBrush(self.get_bg_color())
        
        if getattr(self, "edge_visible", True): painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else: painter.setPen(QtCore.Qt.NoPen)
        
        painter.drawPath(self.shape())
        
        if self.is_checked and getattr(self, "show_mark", True):
            mc = getattr(self, "mark_color", QtGui.QColor("#ffffff"))
            if isinstance(mc, str): mc = QtGui.QColor(mc)
            elif not isinstance(mc, QtGui.QColor): mc = QtGui.QColor(255, 255, 255, 200)
            
            painter.setPen(QtGui.QPen(mc, max(2.0, self.height * 0.1), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            p1 = QtCore.QPointF(box_rect.left() + self.width * 0.25, box_rect.top() + self.height * 0.5)
            p2 = QtCore.QPointF(box_rect.left() + self.width * 0.45, box_rect.top() + self.height * 0.75)
            p3 = QtCore.QPointF(box_rect.left() + self.width * 0.8, box_rect.top() + self.height * 0.25)
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)

        state_key = "ON" if self.is_checked else "OFF"
        display_label = self.cb_data.get(state_key, {}).get("text", self.label)
        
        if display_label:
            if getattr(self, "inside_text", False):
                original_label = getattr(self, "label", "")
                self.label = display_label
                self._draw_text(painter, box_rect)
                self.label = original_label
            else:
                painter.setPen(self.get_text_color())
                font = painter.font()
                font.setPointSize(int(getattr(self, "font_point_size", 10)))
                font.setBold(bool(getattr(self, "font_bold", False)))
                font.setItalic(bool(getattr(self, "font_italic", False)))
                painter.setFont(font)
                
                align_h = getattr(self, "text_align_h", "right")
                if align_h == "center": align_h = "right"
                align_v = getattr(self, "text_align_v", "center")
                margin = 8
                
                text_rect = QtCore.QRectF()
                flags = QtCore.Qt.TextDontClip
                
                if align_v == "up":
                    text_rect = QtCore.QRectF(box_rect.left(), box_rect.top() - 50 - margin, box_rect.width(), 50)
                    flags |= QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom
                elif align_v == "down":
                    text_rect = QtCore.QRectF(box_rect.left(), box_rect.bottom() + margin, box_rect.width(), 50)
                    flags |= QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop
                elif align_h == "left":
                    text_rect = QtCore.QRectF(box_rect.left() - 200 - margin, box_rect.top(), 200, box_rect.height())
                    flags |= QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                else: 
                    text_rect = QtCore.QRectF(box_rect.right() + margin, box_rect.top(), 200, box_rect.height())
                    flags |= QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
                    
                painter.drawText(text_rect, flags, display_label)
            
        self._draw_edit_selection(painter)
        self._draw_lock_tag(painter, box_rect)

class PickerDropdownItem(PickerBaseShape):
    shape_name = "Dropdown"
    def __init__(self, label="Menu", controls=None, parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
        self.attribute = ""
        self.current_text = "None"
        
        self.dd_shape = "Round Rectangle"
        self.dd_roundness = 6.0
        self.inside_text = True
        
        # --- Independent Dynamic Text Variables ---
        self.dyn_text_color = "#ffffff"
        self.dyn_font_size = 11.0
        self.dyn_font_bold = True
        self.dyn_font_italic = False
        self.dyn_align_h = "Center"
    
    def shape(self):
        path = QtGui.QPainterPath()
        br = self.box_rect()
        if getattr(self, "dd_shape", "Rectangle") == "Circle": 
            path.addEllipse(br)
        elif getattr(self, "dd_shape", "Rectangle") == "Round Rectangle": 
            r = getattr(self, "dd_roundness", 6.0)
            path.addRoundedRect(br, r, r)
        else: 
            path.addRect(br)
        return path

    def paint(self, painter, option, widget):
        box_rect = self.box_rect()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        
        # 1. Background
        painter.setBrush(self.get_bg_color())
        if getattr(self, "edge_visible", True): 
            painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else: 
            painter.setPen(QtCore.Qt.NoPen)
        
        painter.drawPath(self.shape())
        
        # 2. The Dropdown Indicator Arrow (▼)
        arrow_size = min(box_rect.height() * 0.15, 6.0)
        arrow_x = box_rect.right() - (arrow_size * 2.5)
        arrow_y = box_rect.center().y()
        
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(self.get_text_color())
        
        poly = QtGui.QPolygonF()
        poly.append(QtCore.QPointF(arrow_x - arrow_size, arrow_y - (arrow_size * 0.6)))
        poly.append(QtCore.QPointF(arrow_x + arrow_size, arrow_y - (arrow_size * 0.6)))
        poly.append(QtCore.QPointF(arrow_x, arrow_y + (arrow_size * 0.8)))
        painter.drawPolygon(poly)
        
        # 3. ULTIMATE SPLIT-TEXT RENDERING ENGINE
        static_label = getattr(self, "label", "").strip()
        dynamic_val = getattr(self, "current_text", "").strip()
        
        if getattr(self, "inside_text", True):
            # --- MODE A: COMBINED INSIDE (e.g., "Costume: Armor") ---
            display_str = static_label
            if dynamic_val and dynamic_val != "None":
                display_str = f"{static_label}: {dynamic_val}" if static_label else dynamic_val
            elif not static_label:
                display_str = dynamic_val or "Dropdown"

            original_label = getattr(self, "label", "")
            self.label = display_str
            self._draw_text(painter, box_rect)
            self.label = original_label

        else:
            # --- MODE B: SPLIT (Label OUTSIDE, Dynamic Enum INSIDE) ---
            
            # A. Compulsory Inside Text (The live Maya Costume/Enum)
            inside_str = dynamic_val if (dynamic_val and dynamic_val != "None") else "None"
            
            painter.setPen(QtGui.QColor(getattr(self, "dyn_text_color", "#ffffff")))
            dyn_font = painter.font()
            dyn_font.setPointSize(int(getattr(self, "dyn_font_size", 11)))
            dyn_font.setBold(bool(getattr(self, "dyn_font_bold", True)))
            dyn_font.setItalic(bool(getattr(self, "dyn_font_italic", False)))
            painter.setFont(dyn_font)
            
            align = getattr(self, "dyn_align_h", "Center").lower()
            flags = QtCore.Qt.TextDontClip | QtCore.Qt.AlignVCenter
            if align == "left": flags |= QtCore.Qt.AlignLeft
            elif align == "right": flags |= QtCore.Qt.AlignRight
            else: flags |= QtCore.Qt.AlignHCenter
            
            # Safe Rect: Adds padding so text never overlaps the ▼ arrow!
            arrow_w = arrow_size * 3.0
            safe_rect = QtCore.QRectF(box_rect.left() + 8, box_rect.top(), box_rect.width() - arrow_w - 8, box_rect.height())
            painter.drawText(safe_rect, flags, inside_str)
            
            # B. Manually Added Text (The floating outside title)
            if static_label:
                painter.setPen(self.get_text_color())
                font = painter.font()
                font.setPointSize(int(getattr(self, "font_point_size", 10)))
                font.setBold(bool(getattr(self, "font_bold", False)))
                font.setItalic(bool(getattr(self, "font_italic", False)))
                painter.setFont(font)
                
                align_h = getattr(self, "text_align_h", "center")
                align_v = getattr(self, "text_align_v", "center")
                margin = 8
                
                text_rect = QtCore.QRectF()
                flags = QtCore.Qt.TextDontClip
                
                if align_v == "up":
                    text_rect = QtCore.QRectF(box_rect.left(), box_rect.top() - 50 - margin, box_rect.width(), 50)
                    flags |= QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom
                elif align_v == "down":
                    text_rect = QtCore.QRectF(box_rect.left(), box_rect.bottom() + margin, box_rect.width(), 50)
                    flags |= QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop
                elif align_h == "left":
                    text_rect = QtCore.QRectF(box_rect.left() - 200 - margin, box_rect.top(), 200, box_rect.height())
                    flags |= QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                else: 
                    text_rect = QtCore.QRectF(box_rect.right() + margin, box_rect.top(), 200, box_rect.height())
                    flags |= QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
                    
                painter.drawText(text_rect, flags, static_label)
            
        self._draw_edit_selection(painter)
        self._draw_lock_tag(painter, box_rect)

class PickerImageItem(PickerBaseShape):
    def __init__(self, label="", controls=None, image_path="", parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
        self.shape_name = "Image"
        self.image_path = image_path
        
        self.image_opacity = 1.0
        self.image_scale_mode = "Fit"
        self.image_padding = 0.0
        self.image_alignment = "Center"
        self.image_mask_shape = "Rectangle"
        self.image_roundness = 8.0
        
        self._cached_pixmap = None
        self._last_image_path = ""

    def set_image(self, path):
        self.image_path = path
        self.update()

    def paint(self, painter, option, widget=None):
        if hasattr(self, "box_rect"): rect = self.box_rect()
        else: rect = QtCore.QRectF(-self.width/2.0, -self.height/2.0, self.width, self.height)
        
        # 1. Establish the Mask Clipping Path
        mask_shape = getattr(self, "image_mask_shape", "Rectangle")
        path = QtGui.QPainterPath()
        if mask_shape == "Circle":
            path.addEllipse(rect)
        elif mask_shape == "Round Rectangle":
            rad = getattr(self, "image_roundness", 8.0)
            path.addRoundedRect(rect, rad, rad)
        else:
            path.addRect(rect)
            
        # 2. Draw Background & Border Defaults
        bg_dict = getattr(self, "bg", {})
        bg_hex = bg_dict.get(self._visual_state, bg_dict.get("normal", "#3c6e71"))
        bg_color = QtGui.QColor(bg_hex)
        if bg_color.alpha() > 0: painter.setBrush(QtGui.QBrush(bg_color))
        else: painter.setBrush(QtCore.Qt.NoBrush)
            
        edge_dict = getattr(self, "edge_color", {})
        edge_hex = edge_dict.get(self._visual_state, edge_dict.get("normal", "#111111"))
        
        eth_dict = getattr(self, "edge_thickness", {})
        if isinstance(eth_dict, dict):
            thickness = eth_dict.get(self._visual_state, eth_dict.get("normal", 1.5))
        else: thickness = eth_dict
            
        if getattr(self, "edge_visible", True): painter.setPen(QtGui.QPen(QtGui.QColor(edge_hex), thickness, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        else: painter.setPen(QtCore.Qt.NoPen)
            
        painter.drawPath(path)
        
        # 3. Draw Image (With Mask Clip, Padding & Alignment)
        img_path = getattr(self, "image_path", "")
        if img_path:
            import os
            if not os.path.isabs(img_path) and self.scene() and self.scene().views():
                base = getattr(self.scene().views()[0].window(), "image_base_dir", "")
                img_path = os.path.join(base, img_path)
                
            if not hasattr(self, "_cached_pixmap") or getattr(self, "_last_image_path", "") != img_path:
                self._cached_pixmap = QtGui.QPixmap(img_path) if os.path.exists(img_path) else None
                self._last_image_path = img_path
            
            pixmap = getattr(self, "_cached_pixmap", None)
            if pixmap and not pixmap.isNull():
                painter.save()
                
                # The ONLY clip we use is the Shape Mask (Rectangle/Round/Circle)
                # This ensures the image safely touches the edge but never bleeds out!
                painter.setClipPath(path) 
                
                painter.setOpacity(getattr(self, "image_opacity", 1.0))
                
                pad = getattr(self, "image_padding", 0.0)
                pad_rect = rect.adjusted(pad, pad, -pad, -pad)
                
                if pad_rect.width() > 0 and pad_rect.height() > 0:
                    scale_mode = getattr(self, "image_scale_mode", "Fit")
                    align = getattr(self, "image_alignment", "Center")
                    
                    img_w, img_h = pixmap.width(), pixmap.height()
                    if img_w > 0 and img_h > 0:
                        aspect = img_w / float(img_h)
                        
                        # 1. Calculate SIZE based on the Padded Inner Box
                        pad_aspect = pad_rect.width() / float(pad_rect.height())
                        
                        if scale_mode == "Stretch":
                            tw, th = pad_rect.width(), pad_rect.height()
                        elif scale_mode == "Fit":
                            if aspect > pad_aspect:
                                tw = pad_rect.width()
                                th = tw / aspect
                            else:
                                th = pad_rect.height()
                                tw = th * aspect
                        elif scale_mode == "Fill":
                            if aspect > pad_aspect:
                                th = pad_rect.height()
                                tw = th * aspect
                            else:
                                tw = pad_rect.width()
                                th = tw / aspect

                        # 2. Calculate POSITION (Alignment) based on the Main Outer Box
                        if align in ["Top Left", "Left", "Bottom Left"]: 
                            tx = rect.left()
                        elif align in ["Top Right", "Right", "Bottom Right"]: 
                            tx = rect.right() - tw
                        else: # Center X
                            tx = rect.center().x() - (tw / 2.0)
                            
                        if align in ["Top Left", "Top", "Top Right"]: 
                            ty = rect.top()
                        elif align in ["Bottom Left", "Bottom", "Bottom Right"]: 
                            ty = rect.bottom() - th
                        else: # Center Y
                            ty = rect.center().y() - (th / 2.0)
                            
                        target_rect = QtCore.QRectF(tx, ty, tw, th)
                        painter.drawPixmap(target_rect, pixmap, QtCore.QRectF(pixmap.rect()))
                        
                painter.restore()
        
        # 4. Draw Default Text Safely (No Base Calls Required)
        label = getattr(self, "label", "")
        if label:
            font = QtGui.QFont()
            font.setPointSize(getattr(self, "font_point_size", 10))
            font.setBold(getattr(self, "font_bold", False))
            font.setItalic(getattr(self, "font_italic", False))
            painter.setFont(font)
            
            tc_dict = getattr(self, "text_color", {})
            tc_hex = tc_dict.get(self._visual_state, tc_dict.get("normal", "#ffffff"))
            painter.setPen(QtGui.QPen(QtGui.QColor(tc_hex)))
            
            align_h = getattr(self, "text_align_h", "center")
            align_v = getattr(self, "text_align_v", "center")
            
            qt_align = 0
            if align_h == "left": qt_align |= QtCore.Qt.AlignLeft
            elif align_h == "right": qt_align |= QtCore.Qt.AlignRight
            else: qt_align |= QtCore.Qt.AlignHCenter
            
            if align_v == "up": qt_align |= QtCore.Qt.AlignTop
            elif align_v == "down": qt_align |= QtCore.Qt.AlignBottom
            else: qt_align |= QtCore.Qt.AlignVCenter
            
            painter.drawText(rect, qt_align, label)

        if self.isSelected():
            if hasattr(self, "_draw_selection_highlight"):
                self._draw_selection_highlight(painter, rect)
            else:
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 255, 0), 2.0, QtCore.Qt.DashLine))
                painter.drawPath(path)

class PickerLineItem(PickerBaseShape):
    shape_name = "Line"
    def __init__(self, label="", controls=None, parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
        self.line_style = "Solid"  # Solid, Dots, Dashes, Smooth, Zigzag
        self.line_orient = "Horizontal"  # Horizontal, Vertical, Diagonal 1, Diagonal 2
        self.line_start_cap = "None"  # None, Arrow, Bar, Point
        self.line_end_cap = "None"
        self.line_cap_scale = 1.0
        self.line_wave_count = 5

    def paint(self, painter, option, widget):
        rect = self.box_rect()
        import math
        
        thickness = self.get_edge_thickness()
        color = self.get_edge_color() if getattr(self, "edge_visible", True) else QtCore.Qt.transparent
        
        if self.line_style == "Dots": pen_style = QtCore.Qt.DotLine
        elif self.line_style == "Dashes": pen_style = QtCore.Qt.DashLine
        else: pen_style = QtCore.Qt.SolidLine
        
        pen = QtGui.QPen(color, thickness, pen_style, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        
        # 1. Determine Mathematical Anchors
        if self.line_orient == "Horizontal":
            p1, p2 = QtCore.QPointF(rect.left(), rect.center().y()), QtCore.QPointF(rect.right(), rect.center().y())
        elif self.line_orient == "Vertical":
            p1, p2 = QtCore.QPointF(rect.center().x(), rect.top()), QtCore.QPointF(rect.center().x(), rect.bottom())
        elif self.line_orient == "Diagonal 1":
            p1, p2 = QtCore.QPointF(rect.left(), rect.top()), QtCore.QPointF(rect.right(), rect.bottom())
        else:
            p1, p2 = QtCore.QPointF(rect.left(), rect.bottom()), QtCore.QPointF(rect.right(), rect.top())

        dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
        length = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)
        
        # 2. Draw Line Body (Solid / Wave Engine)
        if getattr(self, "edge_visible", True) and length > 0.001:
            if self.line_style in ["Smooth", "Zigzag"]:
                waves = max(1, int(getattr(self, "line_wave_count", 5)))
                path = QtGui.QPainterPath()
                path.moveTo(p1)
                
                # Orthogonal Vector
                nx, ny = -math.sin(angle), math.cos(angle)
                amp = rect.height() / 2.0 if self.line_orient in ["Horizontal", "Diagonal 1", "Diagonal 2"] else rect.width() / 2.0
                
                for w in range(waves):
                    wp1 = QtCore.QPointF(p1.x() + dx*(w/float(waves)), p1.y() + dy*(w/float(waves)))
                    wp2 = QtCore.QPointF(p1.x() + dx*((w+1)/float(waves)), p1.y() + dy*((w+1)/float(waves)))
                    
                    perp_dir = 1 if w % 2 == 0 else -1
                    
                    if self.line_style == "Zigzag":
                        mid = QtCore.QPointF((wp1.x()+wp2.x())*0.5, (wp1.y()+wp2.y())*0.5)
                        peak = QtCore.QPointF(mid.x() + nx*amp*perp_dir, mid.y() + ny*amp*perp_dir)
                        path.lineTo(peak)
                        path.lineTo(wp2)
                    else:
                        # Buttery Smooth Sine Wave via Cubic Bezier Math
                        q1 = QtCore.QPointF(wp1.x() + (wp2.x()-wp1.x())*0.25, wp1.y() + (wp2.y()-wp1.y())*0.25)
                        q2 = QtCore.QPointF(wp1.x() + (wp2.x()-wp1.x())*0.75, wp1.y() + (wp2.y()-wp1.y())*0.75)
                        cp1 = QtCore.QPointF(q1.x() + nx*amp*perp_dir, q1.y() + ny*amp*perp_dir)
                        cp2 = QtCore.QPointF(q2.x() + nx*amp*perp_dir, q2.y() + ny*amp*perp_dir)
                        path.cubicTo(cp1, cp2, wp2)
                painter.drawPath(path)
            else:
                painter.drawLine(p1, p2)
            
            # 3. Draw End Caps (Automatically Rotates to match angle)
            def draw_cap(pt, is_start):
                cap_type = self.line_start_cap if is_start else self.line_end_cap
                if cap_type == "None": return
                
                cap_dir = angle + math.pi if is_start else angle
                c_scale = getattr(self, "line_cap_scale", 1.0)
                size = max(6.0, thickness * 3.5) * c_scale
                
                # Offset the translation point forward to completely clear the line's RoundCap projection
                if cap_type == "Arrow":
                    projection_offset = thickness * 1.2
                    shift_x = math.cos(cap_dir) * projection_offset
                    shift_y = math.sin(cap_dir) * projection_offset
                    pt = pt + QtCore.QPointF(shift_x, shift_y)
                
                painter.save()
                painter.translate(pt)
                painter.rotate(math.degrees(cap_dir))
                
                painter.setBrush(QtGui.QBrush(color))
                if cap_type == "Arrow":
                    painter.setPen(QtCore.Qt.NoPen)
                    poly = QtGui.QPolygonF([QtCore.QPointF(0, 0), QtCore.QPointF(-size, -size*0.6), QtCore.QPointF(-size, size*0.6)])
                    painter.drawPolygon(poly)
                elif cap_type == "Point":
                    painter.setPen(QtCore.Qt.NoPen)
                    # Centered on exactly (0,0) to prevent vertical rotation offsets
                    painter.drawEllipse(QtCore.QPointF(0, 0), size * 0.5, size * 0.5)
                elif cap_type == "Bar":
                    painter.setPen(QtGui.QPen(color, thickness, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
                    painter.drawLine(QtCore.QPointF(0, -size), QtCore.QPointF(0, size))
                painter.restore()

            draw_cap(p1, True)
            draw_cap(p2, False)

        self._draw_text(painter, rect)
        self._draw_edit_selection(painter)
        self._draw_lock_tag(painter, rect)

class PickerHierarchyLayer(QtWidgets.QGraphicsItem):
    is_hierarchy_layer = True 
    
    def __init__(self, parent=None):
        QtWidgets.QGraphicsItem.__init__(self, parent)
        self.setZValue(-500) 
        self.setAcceptedMouseButtons(QtCore.Qt.NoButton) 
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QtWidgets.QGraphicsItem.ItemHasNoContents, False)
        
    def boundingRect(self):
        return QtCore.QRectF(-32000, -32000, 64000, 64000)
    
    def shape(self):
        return QtGui.QPainterPath()
    
    def paint(self, painter, option, widget):
        scene = self.scene()
        if not scene or not scene.views(): return
        
        win = scene.views()[0].window()
        if win and hasattr(win, "btn_hier") and win.btn_hier.isChecked():
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            pen = QtGui.QPen(QtGui.QColor(100, 255, 100, 150), 2, QtCore.Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(QtGui.QColor(100, 255, 100, 150))
            
            all_shapes = {itm.item_id: itm for itm in scene.items() if hasattr(itm, "item_id")}
            import math
            
            for itm in scene.items():
                if hasattr(itm, "child_links") and itm.child_links and itm.isVisible():
                    p1 = itm.sceneBoundingRect().center()
                    for cid in itm.child_links:
                        child = all_shapes.get(cid)
                        if child and child.isVisible():
                            p2 = child.sceneBoundingRect().center()
                            painter.drawLine(p1, p2)
                            
                            angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
                            arrow_size = 10
                            mid_pt = QtCore.QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
                            
                            p_a = QtCore.QPointF(mid_pt.x() - arrow_size * math.cos(angle - math.pi / 6),
                                                 mid_pt.y() - arrow_size * math.sin(angle - math.pi / 6))
                            p_b = QtCore.QPointF(mid_pt.x() - arrow_size * math.cos(angle + math.pi / 6),
                                                 mid_pt.y() - arrow_size * math.sin(angle + math.pi / 6))
                            
                            poly = QtGui.QPolygonF([mid_pt, p_a, p_b])
                            painter.drawPolygon(poly)
            painter.restore()