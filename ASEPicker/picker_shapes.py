# ASEPicker/picker_shapes.py
try:
    from PySide2 import QtWidgets, QtGui, QtCore
except ImportError:
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
        painter.setBrush(self.get_bg_color())
        
        if getattr(self, "edge_visible", True): 
            painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
        else: 
            painter.setPen(QtCore.Qt.NoPen)
        painter.drawRect(box_rect)
        
        rng = self.max_value - self.min_value
        pct = 0.0 if rng == 0 else (self.value - self.min_value) / rng
        pct = max(0.0, min(1.0, pct))
        hw = box_rect.height() * 0.3 * self.handle_scale
        hh = box_rect.height() * 1.1 * self.handle_scale
        hx = box_rect.left() + (box_rect.width() * pct) - (hw / 2)
        hy = box_rect.center().y() - (hh / 2)
        
        hc = self.handle_color if isinstance(self.handle_color, QtGui.QColor) else QtGui.QColor(self.handle_color)
        painter.setBrush(hc)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(QtCore.QRectF(hx, hy, hw, hh), 2, 2)
        
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
            extra = 15.0
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
        if self.is_editing_points:
            hit_path = QtGui.QPainterPath()
            hit_path.setFillRule(QtCore.Qt.WindingFill)
            hit_path.addPath(self._get_drawn_path())
            extra = self._get_handle_size() * 2.0
            for pt in self.path_points:
                hit_path.addRect(QtCore.QRectF(pt["p"].x() - extra, pt["p"].y() - extra, extra*2, extra*2))
                if not pt["in"].isNull():
                    hp = pt["p"] + pt["in"]
                    hit_path.addRect(QtCore.QRectF(hp.x() - extra, hp.y() - extra, extra*2, extra*2))
                if not pt["out"].isNull():
                    hp = pt["p"] + pt["out"]
                    hit_path.addRect(QtCore.QRectF(hp.x() - extra, hp.y() - extra, extra*2, extra*2))
            return hit_path
            
        return self._get_drawn_path()

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
        """Override specifically for Polygons to scale from their true bounding box center!"""
        scene = self.scene()
        is_edit = getattr(scene.views()[0], "is_edit_mode", False) if scene and scene.views() else False
        if self.isSelected() and is_edit:
            painter.save()
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 220), 2.0, QtCore.Qt.DashLine))
            painter.setBrush(QtCore.Qt.NoBrush)
            
            # 1. Find the true center of the drawn points
            path = self.shape()
            br = path.boundingRect()
            cx, cy = br.center().x(), br.center().y()
            
            # 2. Scale exactly 6 pixels outward
            w, h = max(br.width(), 1.0), max(br.height(), 1.0)
            sx = (w + 6.0) / w
            sy = (h + 6.0) / h
            
            # 3. Translate to center, scale, and translate back
            painter.translate(cx, cy)
            painter.scale(sx, sy)
            painter.translate(-cx, -cy)
            
            painter.drawPath(path)
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

            if self.hovered_handle == (i, 'p'): painter.setBrush(QtGui.QColor(255, 200, 0))
            else: painter.setBrush(QtGui.QColor(0, 255, 0) if pt["s"] else QtGui.QColor(255, 0, 0))
            
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), line_w))
            painter.drawRect(QtCore.QRectF(pt["p"].x() - rad, pt["p"].y() - rad, sz, sz))

    def _get_handle_at(self, pos):
        sz = self._get_handle_size()
        hit = sz * 1.5
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

class PickerTextItem(PickerRectangleItem):
    shape_name = "Text"
    def __init__(self, label="Ctrl", controls=None, parent=None):
        PickerRectangleItem.__init__(self, label, controls, parent)
    
    def paint(self, painter, option, widget):
        self._draw_text(painter, self.box_rect())
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

class PickerImageItem(PickerBaseShape):
    shape_name = "Image"
    def __init__(self, label="Image", controls=None, parent=None):
        PickerBaseShape.__init__(self, label, controls, parent)
        self.image_path = ""
        self.image_opacity = 1.0
        self.image_scale_mode = "Fit"
    
    def paint(self, painter, option, widget):
        box_rect = self.box_rect()
        
        if self.isSelected() and getattr(self.scene().views()[0], "is_edit_mode", False):
            painter.setBrush(QtGui.QColor(82, 133, 166, 100))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(box_rect)
            
        image_path = getattr(self, "image_path", "")
        if image_path:
            import os
            if not os.path.isabs(image_path):
                base = getattr(self.scene().views()[0].window(), "image_base_dir", "")
                image_path = os.path.join(base, image_path)
                
            if not hasattr(self, "_cached_pixmap") or getattr(self, "_last_image_path", "") != image_path:
                self._cached_pixmap = QtGui.QPixmap(image_path) if os.path.exists(image_path) else None
                self._last_image_path = image_path
                
            pixmap = self._cached_pixmap
            if pixmap and not pixmap.isNull():
                painter.save()
                
                painter.setOpacity(getattr(self, "image_opacity", 1.0))
                
                scale_mode = getattr(self, "image_scale_mode", "Fit")
                if scale_mode == "Stretch":
                    painter.drawPixmap(box_rect.toRect(), pixmap)
                else:
                    aspect_ratio = QtCore.Qt.KeepAspectRatio if scale_mode == "Fit" else QtCore.Qt.KeepAspectRatioByExpanding
                    scaled_pix = pixmap.scaled(box_rect.size().toSize(), aspect_ratio, QtCore.Qt.SmoothTransformation)
                    
                    px = box_rect.center().x() - scaled_pix.width()/2.0
                    py = box_rect.center().y() - scaled_pix.height()/2.0
                    
                    painter.setClipRect(box_rect)
                    painter.drawPixmap(QtCore.QPointF(px, py), scaled_pix)
                    
                painter.restore()
        else:
            painter.setBrush(self.get_bg_color())
            if getattr(self, "edge_visible", True): 
                painter.setPen(QtGui.QPen(self.get_edge_color(), self.get_edge_thickness()))
            else: 
                painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(box_rect)
            self._draw_text(painter, box_rect)
            
        self._draw_edit_selection(painter)
        self._draw_lock_tag(painter, box_rect)

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