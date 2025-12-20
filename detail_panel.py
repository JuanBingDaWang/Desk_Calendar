from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem, QTextEdit, QPushButton, QHBoxLayout, QMessageBox, QCheckBox, QLabel, QApplication, QShortcut
from PyQt5.QtCore import Qt, QDate, pyqtSignal, QEvent
from PyQt5.QtGui import QKeySequence, QTextCursor
from typing import List, Dict, Callable
from collections import deque
from data_manager import Event

class DetailPanel(QWidget):
    """三页签：今日聚焦/全部待办/全局备忘录"""
    eventStatusChanged = pyqtSignal()

    # on_edit 接收 Event 对象
    def __init__(self, data_manager, on_edit: Callable[[Event], None], on_delete: Callable[[int], None]):
        super().__init__()
        self.dm = data_manager
        self.on_edit = on_edit
        self.on_delete = on_delete
        self._locked = False
        
        self._undo_stack = deque(maxlen=5)
        # 初始化设置
        self.show_time_in_list = self.dm.get_settings().get("show_time_in_list", True)
        self.p_colors = {
            "高": self.dm.get_settings().get("font_color_high", "#FF4500"),
            "中": self.dm.get_settings().get("font_color_medium", "#000000"),
            "低": self.dm.get_settings().get("font_color_low", "#696969"),
        }
        
        self._init_ui()
        self.refresh_today()

    def apply_settings(self, settings: Dict) -> None:
        """应用设置，支持预览"""
        self.show_time_in_list = bool(settings.get("show_time_in_list", True))
        self.p_colors = {
            "高": settings.get("font_color_high", "#FF4500"),
            "中": settings.get("font_color_medium", "#000000"),
            "低": settings.get("font_color_low", "#696969"),
        }
        # 刷新界面以应用变更
        self.refresh_today()

    def _create_item_widget(self, event: Event, show_date: bool = False) -> QWidget:
        widget = QWidget()
        h_layout = QHBoxLayout(widget)
        h_layout.setContentsMargins(0, 3, 0, 3) 
        h_layout.setSpacing(5) 
        
        checkbox = QCheckBox()
        checkbox.setChecked(event.finished)
        checkbox.setProperty("eventId", event.id) 
        
        if event.repeat_rule != "无":
            checkbox.setEnabled(False)
            checkbox.setToolTip("重复日程无法直接标记完成（这会影响所有日期的状态）")
        else:
            checkbox.stateChanged.connect(self._on_checkbox_state_changed)

        h_layout.addWidget(checkbox)
        
        time_str = event.start_time.strftime("%H:%M")
        
        # 根据设置构建文本
        text_parts = []
        if show_date:
            text_parts.append(f"[{event.start_time.strftime('%m-%d')}]")
        
        text_parts.append(event.title)
        
        if self.show_time_in_list:
            text_parts.append(time_str)
        
        text = "  ".join(text_parts)
            
        label = QLabel(text)
        
        # 应用颜色样式
        if event.finished:
            label.setStyleSheet("text-decoration: line-through; color: #888888;") 
        else:
            # 根据优先级设置颜色
            p_color = self.p_colors.get(event.priority, "#000000")
            label.setStyleSheet(f"color: {p_color};")

        label.setWordWrap(True)
        h_layout.addWidget(label, 1)
        widget.setLayout(h_layout)
        return widget

    def _on_checkbox_state_changed(self, state: int) -> None:
        checkbox = self.sender() 
        event_id = checkbox.property("eventId")
        is_finished = state == Qt.Checked
        
        if event_id is not None:
            if self.dm.mark_event_as_finished(event_id, is_finished):
                self.eventStatusChanged.emit()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        self.today_list = QListWidget()
        self.tabs.addTab(self.today_list, "今日聚焦")

        self.all_todos_list = QListWidget()
        self.tabs.addTab(self.all_todos_list, "全部待办")
        
        memo_page = QWidget()
        memo_layout = QVBoxLayout(memo_page)
        self.memo = QTextEdit()
        self.memo.installEventFilter(self)
        
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self.memo)
        self.save_shortcut.activated.connect(self._save_memo)
        
        btn_row = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_clear = QPushButton("清空")
        btn_save.clicked.connect(lambda: self._save_memo())
        btn_clear.clicked.connect(lambda: self._clear_memo())
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_clear)
        memo_layout.addWidget(self.memo)
        memo_layout.addLayout(btn_row)
        self.tabs.addTab(memo_page, "全局备忘录")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

        self.today_list.itemDoubleClicked.connect(self._on_double)
        self.today_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.today_list.customContextMenuRequested.connect(lambda p: self._ctx_menu(self.today_list, p))

        self.all_todos_list.itemDoubleClicked.connect(self._on_double)
        self.all_todos_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.all_todos_list.customContextMenuRequested.connect(lambda p: self._ctx_menu(self.all_todos_list, p))

        self._load_memo()

    def eventFilter(self, obj, event):
        if obj == self.memo:
            if event.type() == QEvent.FocusOut:
                if not self._locked:
                    self._save_memo()
            
            elif event.type() == QEvent.KeyPress:
                if not self._locked:
                    if event.matches(QKeySequence.Undo) or (event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier):
                        if self.memo.document().isUndoAvailable():
                            self.memo.undo()
                            return True 
                        elif self._undo_stack:
                            last_content = self._undo_stack.pop()
                            self.memo.setPlainText(last_content)
                            cursor = self.memo.textCursor()
                            cursor.movePosition(QTextCursor.End)
                            self.memo.setTextCursor(cursor)
                            self._save_memo()
                            return True
        return super().eventFilter(obj, event)
        
    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self.memo.setReadOnly(locked)

    def _ctx_menu(self, lst: QListWidget, pos) -> None:
        if self._locked:
            return
        item = lst.itemAt(pos)
        if not item:
            return
        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        act_edit = menu.addAction("编辑")
        act_del = menu.addAction("删除")
        act = menu.exec_(lst.mapToGlobal(pos))
        
        e: Event = item.data(Qt.UserRole)
        if act == act_edit:
            self.on_edit(e)
        elif act == act_del:
            if QMessageBox.question(self, "确认", "确定删除该日程吗？") == QMessageBox.Yes:
                self.on_delete(e.id)

    def _on_double(self, item: QListWidgetItem) -> None:
        if self._locked:
            return
        e: Event = item.data(Qt.UserRole)
        self.on_edit(e)

    def refresh_today(self) -> None:
        self.today_list.clear()
        d = QDate.currentDate().toString("yyyy-MM-dd")
        # 使用旧接口或新接口皆可，list_events_by_date 内部已优化
        events: List[Event] = self.dm.list_events_by_date(d)
        
        if not events:
            self.today_list.addItem("今日无日程")
        else:   
            for e in events:
                it = QListWidgetItem()
                item_widget = self._create_item_widget(e, show_date=False)
                it.setSizeHint(item_widget.sizeHint())
                it.setData(Qt.UserRole, e) 
                self.today_list.addItem(it)
                self.today_list.setItemWidget(it, item_widget)
        
        self.refresh_all_todos()

    def refresh_all_todos(self) -> None:
        self.all_todos_list.clear()
        all_events = self.dm.get_all_events()
        unfinished_events = [e for e in all_events if not e.finished]
        unfinished_events.sort(key=lambda x: x.start_time)
        
        if not unfinished_events:
            self.all_todos_list.addItem("太棒了，所有事项已完成！")
            return
            
        for e in unfinished_events:
            it = QListWidgetItem()
            item_widget = self._create_item_widget(e, show_date=True)
            it.setSizeHint(item_widget.sizeHint())
            it.setData(Qt.UserRole, e)
            self.all_todos_list.addItem(it)
            self.all_todos_list.setItemWidget(it, item_widget)

    def _load_memo(self) -> None:
        try:
            self.memo.setPlainText(self.dm.get_global_memo())
        except Exception:
            pass

    def _save_memo(self) -> None:
        if self._locked:
            return
        self.dm.save_global_memo(self.memo.toPlainText())

    def _clear_memo(self) -> None:
        if self._locked:
            return
        current_text = self.memo.toPlainText()
        if not current_text:
            return
        self._undo_stack.append(current_text)
        self.memo.clear()
        self.dm.save_global_memo("")

    def setup_nav_buttons(self, on_prev: Callable, on_next: Callable):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(5)
        
        btn_prev = QPushButton("<")
        btn_prev.setToolTip("向前翻页")
        btn_prev.setFixedSize(30, 24)
        btn_prev.clicked.connect(on_prev)
        
        btn_next = QPushButton(">")
        btn_next.setToolTip("向后翻页")
        btn_next.setFixedSize(30, 24)
        btn_next.clicked.connect(on_next)
        
        layout.addWidget(btn_prev)
        layout.addWidget(btn_next)
        
        self.tabs.setCornerWidget(container, Qt.TopRightCorner)