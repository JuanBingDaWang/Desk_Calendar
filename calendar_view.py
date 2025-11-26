from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QEvent, QSize
from PyQt5.QtGui import QFont
from datetime import date, timedelta
from typing import Dict, List
from data_manager import Event

class CalendarView(QWidget):
    """仅负责渲染与交互；参数由外部设置（周数/格子尺寸/行列间距）"""

    configChanged = pyqtSignal()
    dateSelected = pyqtSignal(QDate)
    createEventForDate = pyqtSignal(QDate)
    eventActivated = pyqtSignal(Event) # 传递对象
    eventDeleteRequested = pyqtSignal(int)
    periodChanged = pyqtSignal()
    eventFinishStatusChanged = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.weeks_to_show = 4
        self.cell_width = 140
        self.cell_height = 110
        self.row_gap = 6
        self.col_gap = 6
        self.font_size = 12 
        self.anchor_monday = CalendarView._monday_of(date.today())
        self._init_ui()

    @staticmethod
    def _monday_of(d: date) -> date:
        return d - timedelta(days=(d.weekday() % 7))

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout()
        self.grid = QGridLayout()
        self.grid.setVerticalSpacing(self.row_gap)
        self.grid.setHorizontalSpacing(self.col_gap)
        self._rebuild_grid()
        grid_w = QWidget()
        grid_w.setLayout(self.grid)
        main_layout.addWidget(grid_w)
        self.setLayout(main_layout)

    def apply_settings(self, s: Dict) -> None:
        self.font_size = int(s.get("font_size", self.font_size))
        self.weeks_to_show = int(s.get("weeks", self.weeks_to_show))
        self.cell_width = int(s.get("cell_width", self.cell_width))
        self.cell_height = int(s.get("cell_height", self.cell_height))
        self.row_gap = int(s.get("row_gap", self.row_gap))
        self.col_gap = int(s.get("col_gap", self.col_gap))
        
        self.grid.setVerticalSpacing(self.row_gap)
        self.grid.setHorizontalSpacing(self.col_gap)
        self._rebuild_grid()
        self.configChanged.emit()
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        num_columns = 7
        num_gaps = num_columns - 1 
        content_width = (num_columns * self.cell_width) + (num_gaps * self.col_gap)
        base_hint = super().sizeHint()
        return QSize(content_width, base_hint.height())
        
    def _clear_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _rebuild_grid(self) -> None:
        self._clear_grid()
        base_style = f"font-size: {self.font_size}pt;"
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        for col, dayname in enumerate(weekdays):
            lab = QLabel(dayname)
            lab.setStyleSheet(base_style)
            lab.setAlignment(Qt.AlignCenter)
            lab.setFixedSize(self.cell_width, 28)
            self.grid.addWidget(lab, 0, col)

        total_days = self.weeks_to_show * 7
        for i in range(total_days):
            row = i // 7 + 1
            col = i % 7
            from datetime import timedelta as _td
            d = self.anchor_monday + _td(days=i)
            self._add_day_cell(row, col, d, base_style)

    def _add_day_cell(self, row: int, col: int, d: date, style_sheet: str) -> None:
        cell = QWidget()
        cell.setProperty("calendarCell", True) 
        v = QVBoxLayout(cell)
        v.setContentsMargins(4, 4, 4, 4)

        head = QLabel(d.strftime("%Y-%m-%d"))
        head.setStyleSheet(style_sheet) 
        head.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        head.setFixedHeight(20)
        head.setProperty("isHeader", True)
        
        if d == date.today():
            head.setStyleSheet(style_sheet + """
                background-color: #D3D3D3; 
                border-radius: 4px;
                padding-left: 3px;
                color: #000000;
            """)

        v.addWidget(head) 

        lst = QListWidget()
        lst.setStyleSheet(f"""
            QListWidget {{ 
                {style_sheet} 
                background-color: transparent; 
                border: none; 
            }}
        """)
        
        lst.setProperty("dateStr", d.strftime("%Y-%m-%d"))
        lst.setFixedSize(self.cell_width, self.cell_height - 24)
        lst.itemDoubleClicked.connect(self._on_item_double_clicked)
        lst.setContextMenuPolicy(Qt.CustomContextMenu)
        lst.customContextMenuRequested.connect(lambda p, list_widget=lst: self._on_context_menu(list_widget, p))
        lst.viewport().installEventFilter(self)
        v.addWidget(lst)

        def on_select():
            self.dateSelected.emit(QDate(d.year, d.month, d.day))
        head.mousePressEvent = lambda e: on_select()

        self.grid.addWidget(cell, row, col)

    def _clear_selections(self, exclude: QListWidget = None) -> None:
        for i in range(self.grid.count()):
            item = self.grid.itemAt(i)
            if not item: continue
            w = item.widget()
            if w:
                lsts = w.findChildren(QListWidget)
                if lsts:
                    lst = lsts[0]
                    if lst != exclude:
                        lst.clearSelection()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                parent = obj.parent()
                if isinstance(parent, QListWidget):
                    item = parent.itemAt(event.pos())
                    if item:
                        self._clear_selections(exclude=parent)
                    else:
                        self._clear_selections(exclude=None)
                        parent.clearSelection()

        if event.type() == QEvent.MouseButtonDblClick:
            parent = obj.parent()
            if isinstance(parent, QListWidget):
                if not parent.itemAt(event.pos()):
                    d = parent.property("dateStr")
                    qd = QDate.fromString(d, "yyyy-MM-dd")
                    self.createEventForDate.emit(qd)
                    return True 

        return super().eventFilter(obj, event)

    def render_events(self, events_by_date: Dict[str, List[Event]]) -> None:
        """接收 Event 对象列表进行渲染"""
        for i in range(self.grid.count()):
            w = self.grid.itemAt(i).widget()
            if not w: continue
            lsts = w.findChildren(QListWidget)
            if not lsts: continue
            lst = lsts[0]
            lst.clear()

            d = lst.property("dateStr")
            events = events_by_date.get(d, [])
            
            for e in events:
                prefix = ""
                if e.repeat_rule != "无":
                    prefix = "↻ " 
                
                time_str = e.start_time.strftime("%H:%M")
                item = QListWidgetItem(f"{prefix}{e.title}  {time_str}")
                item.setData(Qt.UserRole, e) # 存储 Event 对象

                if e.finished:
                    # 显式构造字体以避免丢失 size
                    f = QFont()
                    f.setPointSize(self.font_size)
                    f.setStrikeOut(True)
                    item.setFont(f)
                    item.setForeground(Qt.gray)
                    
                lst.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        e = item.data(Qt.UserRole)
        if e:
            self.eventActivated.emit(e)

    def _on_context_menu(self, list_widget: QListWidget, pos) -> None:
        item = list_widget.itemAt(pos)
        if not item:
            return
        
        e: Event = item.data(Qt.UserRole)
        finish_text = "标记为未完成" if e.finished else "标记为已完成"

        from PyQt5.QtWidgets import QMenu, QMessageBox
        menu = QMenu(self)
        act_finish = menu.addAction(finish_text)
        menu.addSeparator()
        act_edit = menu.addAction("编辑")
        act_del = menu.addAction("删除")
        
        act = menu.exec_(list_widget.mapToGlobal(pos))
        
        if act == act_edit:
            self.eventActivated.emit(e)
        elif act == act_del:
            if QMessageBox.question(self, "确认", "确定删除该日程吗？") == QMessageBox.Yes:
                self.eventDeleteRequested.emit(e.id)
        elif act == act_finish:
            self.eventFinishStatusChanged.emit(e.id, not e.finished)
                
    def get_span(self) -> tuple:
        start_date = self.anchor_monday
        end_date = start_date + timedelta(days=(self.weeks_to_show * 7) - 1)
        return start_date, end_date
        
    def jump_weeks(self, n: int) -> None:
        days = n * 7
        self.anchor_monday += timedelta(days=days)
        self._rebuild_grid()
        self.periodChanged.emit()