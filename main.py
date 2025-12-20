import os
import sys
import ctypes
from typing import Dict, List
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QAction,
    QHBoxLayout, QVBoxLayout, QWidget, QPushButton, QLabel, QStyle,
    QDialog, QDateTimeEdit, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt, QPoint, QDateTime, QTime
from PyQt5.QtGui import QIcon

from data_manager import DataManager, Event
from calendar_view import CalendarView
from event_dialog import EventDialog
from detail_panel import DetailPanel
from reminder_manager import ReminderManager
from settings_dialog import SettingsDialog

class CornerGrip(QWidget):
    """自定义的角落调整手柄"""
    def __init__(self, parent, corner):
        super().__init__(parent)
        self.corner = corner 
        if corner in ('tl', 'br'):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.SizeBDiagCursor)
        self.setFixedSize(20, 20)
        self.setStyleSheet("background-color: transparent;") 
        self.start_pos = None
        self.start_geo = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.globalPos()
            self.start_geo = self.parent().geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            curr_pos = event.globalPos()
            diff = curr_pos - self.start_pos
            geo = self.start_geo
            new_x, new_y = geo.x(), geo.y()
            new_w, new_h = geo.width(), geo.height()
            if self.corner == 'tl':
                new_x += diff.x(); new_y += diff.y(); new_w -= diff.x(); new_h -= diff.y()
            elif self.corner == 'tr':
                new_y += diff.y(); new_w += diff.x(); new_h -= diff.y()
            elif self.corner == 'bl':
                new_x += diff.x(); new_w -= diff.x(); new_h += diff.y()
            elif self.corner == 'br':
                new_w += diff.x(); new_h += diff.y()
            if new_w > 100 and new_h > 100:
                self.parent().setGeometry(new_x, new_y, new_w, new_h)
            event.accept()

class MainWindow(QMainWindow):
    def __init__(self, dm: DataManager):
        super().__init__()
        self.dm = dm
        self.drag_pos = QPoint()
        self.tray_icon = None
        self._locked = bool(self.dm.get_settings().get("locked", False))
        
        # 开启背景透明支持
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.reminder = ReminderManager(self.dm)
        # 连接信号，现在接收的是 Event 对象
        self.reminder.reminderTriggered.connect(self._on_reminder)
        self.reminder.dateChanged.connect(self._on_date_changed)
        self._snoozed_event_ids = set()

        self._init_ui()
        self._init_tray()
        self._restore_window_state()
        
        self.lock_checkbox.setChecked(self._locked)
        self.lock_checkbox.stateChanged.connect(self._handle_lock_state_change) 
        self._apply_settings_to_widgets()
        self._refresh_views()

    def _refresh_views(self) -> None:
        """刷新所有视图（性能优化版）"""
        self.detail.refresh_today() 

        # 优化：一次性获取日期范围内的数据
        start_date, end_date = self.calendar.get_span() 
        events_by_date = self.dm.get_events_between_dates(start_date, end_date)
        self.calendar.render_events(events_by_date)

    def _on_calendar_finish_toggled(self, event_id: int, is_finished: bool) -> None:
        if self._locked: return
        if self.dm.mark_event_as_finished(event_id, is_finished):
            self._refresh_views()
            
    def _handle_lock_state_change(self, state: int) -> None:
        is_locked = (state == Qt.Checked)
        s = self.dm.get_settings()
        s["locked"] = is_locked
        self.dm.save_settings(**s) 
        self.set_locked(is_locked)

    def _init_ui(self) -> None:
        self.setWindowFlag(Qt.FramelessWindowHint)
        central = QWidget()
        central.setObjectName("centralWidget") # 设置 ObjectName 方便 QSS 定位
        root = QVBoxLayout(central)
        root.setContentsMargins(5, 5, 5, 5) 
        root.setSpacing(0)

        self.calendar = CalendarView()
        root.addWidget(self.calendar)

        self.detail = DetailPanel(
            self.dm,
            on_edit=self._edit_event,
            on_delete=self._delete_event,
        )
        self.detail.eventStatusChanged.connect(self._refresh_views)
        self.detail.setup_nav_buttons(
            on_prev=lambda: self.calendar.jump_weeks(-self.calendar.weeks_to_show),
            on_next=lambda: self.calendar.jump_weeks(self.calendar.weeks_to_show)
        )
        root.addWidget(self.detail)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(10, 0, 10, 5) 
        
        self.lock_checkbox = QCheckBox("锁定")
        self.lock_checkbox.setFixedSize(60, 24)
        self.lock_checkbox.setToolTip("固定在桌面，禁止编辑/移动/缩放")
        bottom.addWidget(self.lock_checkbox)
        
        bottom.addStretch(1)
        bottom.addSpacing(20)
        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(self._open_settings)
        bottom.addWidget(self.btn_settings)
        root.addLayout(bottom)

        self.setCentralWidget(central)
        
        self.grip_tl = CornerGrip(self, 'tl')
        self.grip_tr = CornerGrip(self, 'tr')
        self.grip_bl = CornerGrip(self, 'bl')
        self.grip_br = CornerGrip(self, 'br')

        self.calendar.dateSelected.connect(self._on_date_selected)
        self.calendar.createEventForDate.connect(self._create_for_date)
        self.calendar.eventActivated.connect(self._edit_event)
        self.calendar.eventDeleteRequested.connect(self._delete_event)
        self.calendar.periodChanged.connect(self._refresh_views)
        self.calendar.eventFinishStatusChanged.connect(self._on_calendar_finish_toggled)

    def _init_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon_or.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        menu = QMenu()
        act_toggle = QAction("显示/隐藏主窗口", self)
        act_new = QAction("新建日程", self)
        act_exit = QAction("退出", self)
        act_toggle.triggered.connect(self._toggle_window)
        act_new.triggered.connect(self._create_from_tray)
        act_exit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_toggle)
        menu.addAction(act_new)
        menu.addAction(act_exit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _apply_settings_preview(self, s: dict, resize_window: bool = True) -> None:
        self.calendar.apply_settings(s)
        self.detail.apply_settings(s) 
        
        # 1. 应用全局透明度 (Window Opacity)
        self._set_opacity(float(s.get("opacity", 0.95))) 
        
        # 2. 应用样式（包括背景颜色+背景透明度）
        self._update_style(
            s.get("bg_color", "#ffffff"),
            s.get("bg_opacity", 100), # 获取背景不透明度
            s.get("font_color", "#000000"),
            s.get("font_size", 12)
        )
        self.set_locked(bool(s.get("locked", False)))
        if resize_window:
            self.adjustSize()
        self._place_grips()
        self._refresh_views()

    def _apply_settings_to_widgets(self) -> None:
        s = self.dm.get_settings()
        self._apply_settings_preview(s, resize_window=False)

    def _restore_window_state(self) -> None:
        s = self.dm.get_settings()
        w = s.get("window", {"x": 100, "y": 100, "w": 900, "h": 680})
        self.setGeometry(w["x"], w["y"], w["w"], w["h"])
        self._place_grips()

    def _save_window_state(self) -> None:
        g = self.geometry()
        s = self.dm.get_settings()
        s["window"] = {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}
        self.dm.save_settings(**s)

    def _place_grips(self) -> None:
        w, h = self.width(), self.height()
        s = 20
        self.grip_tl.setGeometry(0, 0, s, s)
        self.grip_tr.setGeometry(w - s, 0, s, s)
        self.grip_bl.setGeometry(0, h - s, s, s)
        self.grip_br.setGeometry(w - s, h - s, s, s)
        self.grip_tl.raise_()
        self.grip_tr.raise_()
        self.grip_bl.raise_()
        self.grip_br.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_grips()
        if not self._locked:
            self._save_window_state()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if not self._locked:
            self._save_window_state()

    def _set_opacity(self, v: float) -> None:
        self.setWindowOpacity(v)

    def _hex_to_rgba(self, hex_code: str, alpha_percent: int) -> str:
        """将 hex 颜色和 0-100 的透明度转换为 rgba 字符串"""
        hex_code = hex_code.lstrip('#')
        if len(hex_code) == 6:
            r = int(hex_code[0:2], 16)
            g = int(hex_code[2:4], 16)
            b = int(hex_code[4:6], 16)
            # Alpha: 0-255
            a = int(alpha_percent * 255 / 100)
            return f"rgba({r}, {g}, {b}, {a})"
        return hex_code

    def _update_style(self, bg_hex: str, bg_opacity: int, fg: str, font_size: int) -> None:
        # 计算 RGBA 背景色
        bg_rgba = self._hex_to_rgba(bg_hex, bg_opacity)

        style = f"""
        /* 针对中心部件设置背景色，支持透明 */
        #centralWidget {{ 
            background-color: {bg_rgba}; 
            color: {fg}; 
            font-size: {font_size}pt; 
        }}
        
        /* 通配符：所有子控件继承字体颜色和大小 */
        * {{ color: {fg}; font-size: {font_size}pt; }}
        
        QToolTip {{ 
            color: black; 
            background-color: #F0F0F0; 
            border: 1px solid #767676; 
        }}
        
        /* Tab 样式：文字固定为黑色 */
        QTabBar::tab {{ color: #000000; }}
        
        QLabel {{ border: none; background-color: transparent; }} /* 标签背景透明 */
        
        /* ================= 修改点 2：日历格子 ================= */
        /* 边框颜色跟随文字颜色 ({fg})，背景透明 */
        QWidget[calendarCell="true"] {{ border: 1px solid {fg}; background-color: transparent; }}
        
        QListWidget {{ background-color: transparent; border: none; }}
        QListWidget::item {{ background-color: transparent; }}
        QListWidget::item:selected {{ background-color: {bg_hex}; color: {fg}; border: 1px solid {fg}; }}
        
        /* ================= 修改点 1：Detail Panel ================= */
        /* TabPane 和 TextEdit 背景设置为 transparent，以透出主窗口的背景 */
        /* 同时边框也跟随文字颜色，保持风格一致 */
        QTabWidget::pane {{ border: 1px solid {fg}; background-color: transparent; }}
        QTextEdit {{ background-color: transparent; border: 1px solid {fg}; padding: 5px; color: {fg}; }}
        
        /* 按钮保持一定可见性，但文字颜色适配 */
        QPushButton {{ background-color: #e0e0e0; border: 1px solid #c0c0c0; padding: 5px 10px; border-radius: 4px; color: black; }}
        QPushButton:hover {{ background-color: #d0d0d0; }}
        QPushButton:pressed {{ background-color: #c0c0c0; }}
        #snoozeButton {{ color: white; background-color: #0078d7; }}
        #snoozeButton:hover {{ background-color: #0063bf; }}
        """
        self.setStyleSheet(style)
        self._place_grips()

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self.detail.set_locked(locked)
        for grip in [self.grip_tl, self.grip_tr, self.grip_bl, self.grip_br]:
            grip.setVisible(not locked)
        
        was_visible = self.isVisible()
        current_flags = self.windowFlags()
        current_flags &= ~Qt.WindowType_Mask
        if locked:
            new_flags = current_flags | Qt.Tool 
        else:
            new_flags = current_flags | Qt.Window
        
        self.setWindowFlags(new_flags)
        if was_visible:
            self.show()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.dm.get_settings(), self)
        dlg.settingsChanged.connect(self._apply_settings_preview)
        if dlg.exec_() == SettingsDialog.Accepted:
            vals = dlg.values()
            s = self.dm.get_settings()
            s.update(vals)
            self.dm.save_settings(**s)
            self._apply_settings_to_widgets()
            self._refresh_views()
        else:
            self._apply_settings_to_widgets()

    def _on_date_selected(self, qdate) -> None:
        pass

    def _create_for_date(self, qdate) -> None:
        if self._locked: return
        start_qdt = QDateTime(qdate, QTime(0, 0))
        dlg = EventDialog(self, default_start_dt=start_qdt)
        if dlg.exec_() == EventDialog.Accepted:
            self._save_dialog_event(dlg.get_event_payload())

    def _create_from_tray(self) -> None:
        if self._locked: return
        dlg = EventDialog(self)
        if dlg.exec_() == EventDialog.Accepted:
            self._save_dialog_event(dlg.get_event_payload())

    def _edit_event(self, e: Event) -> None:
        if self._locked: return
        # 直接传递 Event 对象
        dlg = EventDialog(self, event=e)
        if dlg.exec_() == EventDialog.Accepted:
            payload = dlg.get_event_payload()
            # 查找最新对象（虽然 e 是引用，但最好通过 ID 确认存在）
            target = self.dm.get_event(e.id)
            if not target: return
            
            target.update_from_payload(payload)
            self.dm.update_event(target)
            self._refresh_views()

    def _delete_event(self, event_id: int) -> None:
        if self._locked: return
        self.dm.delete_event(event_id)
        self._refresh_views()

    def _save_dialog_event(self, payload: Dict) -> None:
        e = Event(
            id_=0, # Will be set by dm
            title=payload["title"],
            start_time=Event.dt_from_iso(payload["start_time"]),
            end_time=Event.dt_from_iso(payload["end_time"]),
            description=payload["description"],
            priority=payload["priority"],
            repeat_rule=payload["repeat_rule"],
            reminder_enabled=payload["reminder"]["enabled"],
            reminder_type=payload["reminder"]["type"],
            advance_value=payload["reminder"]["advance_value"],
            advance_unit=payload["reminder"]["advance_unit"],
            absolute_time=Event.dt_from_iso(payload["reminder"]["absolute_time"]),
        )
        self.dm.add_event(e)
        self._refresh_views()

    def _toggle_window(self) -> None:
        if self.isVisible(): self.hide()
        else: self.show(); self.activateWindow()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    def mousePressEvent(self, event) -> None:
        if self._locked: return
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._locked: return
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()

    def _on_reminder(self, e: Event) -> None:
        # e 现在是一个 Event 对象
        reminder_window = ReminderManager.show_notification(self.tray_icon, e)
        snooze_btn = reminder_window.findChild(QPushButton, "snoozeButton")
        if snooze_btn:
            snooze_btn.clicked.connect(lambda: self._show_snooze_dialog(reminder_window.event_data))
        reminder_window.exec_()
        
        if e.id not in self._snoozed_event_ids:
            self._mark_event_as_reminded(e.id)
        else:
            self._snoozed_event_ids.discard(e.id)

    def _mark_event_as_reminded(self, event_id: int) -> None:
        try:
            event = self.dm.get_event(event_id)
            if event:
                # 更新 last_reminded_time 为当前时间
                event.last_reminded_time = datetime.now()
                self.dm.update_event(event)
        except Exception:
            pass

    def _show_snooze_dialog(self, event: Event) -> None:
        event_title = event.title or "未知事项"
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        dialog.setWindowTitle(f"设置提醒时间 - {event_title}")
        dialog.setFixedSize(400, 200)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"为事项 '{event_title}' 设置提醒时间:"))
        
        dt_lay = QHBoxLayout()
        datetime_edit = QDateTimeEdit()
        datetime_edit.setCalendarPopup(True)
        datetime_edit.setDateTime(QDateTime.currentDateTime().addSecs(60))
        dt_lay.addWidget(QLabel("选择时间:")); dt_lay.addWidget(datetime_edit)
        layout.addLayout(dt_lay)
        
        btn_lay = QHBoxLayout()
        ok_btn = QPushButton("确定"); cancel_btn = QPushButton("取消")
        btn_lay.addWidget(ok_btn); btn_lay.addWidget(cancel_btn)
        layout.addLayout(btn_lay)
        
        dialog.setLayout(layout)
        ok_btn.clicked.connect(dialog.accept); cancel_btn.clicked.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            selected_time = datetime_edit.dateTime()
            if selected_time <= QDateTime.currentDateTime():
                QMessageBox.warning(dialog, "时间无效", "请选择未来的时间")
                return
            minutes_diff = QDateTime.currentDateTime().secsTo(selected_time) // 60
            self.reminder.snooze(event.id, minutes_diff)
            self._snoozed_event_ids.add(event.id)
            QMessageBox.information(dialog, "设置成功", f"已设置在{minutes_diff}分钟后提醒")

    def _on_date_changed(self) -> None:
        """跨天时自动刷新视图"""
        # 1. 刷新日历网格布局（更新灰色高亮背景）
        # 确保你在 calendar_view.py 里加了 refresh_layout 方法（见下方）
        self.calendar.refresh_layout()
        
        # 2. 刷新数据（更新“今日聚焦”列表）
        self._refresh_views()
        
def _ensure_data_path() -> str:
    import os
    import json
    from data_manager import DataManager

    default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DataManager.SETTINGS_FILE)
    
    data_dir = os.path.dirname(default_path)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)
    
    if not os.path.exists(default_path):
        initial_json_content = {
            "version":"1.1",
            "settings":{},
            "global_memo":"",
            "events": [] 
        }
        with open(default_path, "w", encoding="utf-8") as f:
            json.dump(initial_json_content, f, indent=4, ensure_ascii=False)
        
    return default_path

if __name__ == "__main__":
    try:
        myappid = 'mycompany.calendar.app.v1.1' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon_or.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    data_file = _ensure_data_path()
    dm = DataManager(data_file)
    win = MainWindow(dm)
    win.show()
    sys.exit(app.exec_())