from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDateTimeEdit,
    QTextEdit, QPushButton, QCheckBox, QComboBox, QSpinBox, QMessageBox,
    QDateEdit, QGroupBox, QFormLayout, QWidget
)
from PyQt5.QtCore import Qt, QDateTime, QDate, QTime
from PyQt5.QtGui import QIntValidator
from typing import Optional, Dict, Tuple
from data_manager import Event

class EventDialog(QDialog):
    # 修改：event_data 接收 Event 对象，而不是 Dict
    def __init__(self, parent=None, event: Optional[Event] = None, default_start_dt: Optional[QDateTime] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("新建/编辑日程")
        self.setFixedSize(450, 650)
        
        # 读取主程序配置的背景色和字体色（如果可用）
        bg_color = "#f0f0f0" # 默认背景
        font_color = "#000000" # 默认字体
        
        if parent and hasattr(parent, 'dm'):
            s = parent.dm.get_settings()
            bg_color = s.get("bg_color", "#f0f0f0")
            font_color = s.get("font_color", "#000000")
            
        bg_rgba = self._hex_to_rgba(bg_color, 100) # 强制 100% 不透明
        
        # 动态设置字体颜色和背景色
        # 新增：针对输入框 (QLineEdit, QComboBox, etc.) 也应用背景色和字体色
        self.setStyleSheet(f"""
            QDialog {{ color: {font_color}; background-color: {bg_rgba}; }}
            QGroupBox {{ font-weight: bold; border: 1px solid gray; border-radius: 5px; margin-top: 10px; padding-top: 15px; background-color: transparent; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; color: {font_color}; }}
            QLabel, QCheckBox {{ color: {font_color}; background-color: transparent; }}
            
            /* 输入控件统一风格 */
            QLineEdit, QTextEdit, QSpinBox, QComboBox, QDateEdit, QDateTimeEdit {{
                background-color: {bg_rgba};
                color: {font_color};
                border: 1px solid #a0a0a0;
                border-radius: 3px;
                padding: 2px;
                selection-background-color: darkgray;
            }}
            /* 下拉列表的 ItemView 背景 */
            QComboBox QAbstractItemView {{
                background-color: {bg_rgba};
                color: {font_color};
                selection-background-color: darkgray;
            }}
        """)
        
        self.start_dt_final = None
        self.end_dt_final = None
        
        self._init_ui(event, default_start_dt)

    def _hex_to_rgba(self, hex_code: str, alpha_percent: int) -> str:
        hex_code = hex_code.lstrip('#')
        if len(hex_code) == 6:
            r = int(hex_code[0:2], 16)
            g = int(hex_code[2:4], 16)
            b = int(hex_code[4:6], 16)
            a = int(alpha_percent * 255 / 100)
            return f"rgba({r}, {g}, {b}, {a})"
        return hex_code

    def _init_ui(self, event: Optional[Event], default_start_dt: Optional[QDateTime]) -> None:
        layout = QVBoxLayout(self)
        self._original_finished_state = event.finished if event else False
        self.int_validator = QIntValidator(0, 99, self)

        # === 1. 基本信息 ===
        grp_basic = QGroupBox("基本信息")
        lay_basic = QFormLayout(grp_basic)
        
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("请输入日程标题...")
        lay_basic.addRow("标题:", self.title_edit)

        h_opts = QHBoxLayout()
        self.priority = QComboBox()
        self.priority.addItems(["高", "中", "低"])
        self.repeat_rule = QComboBox()
        self.repeat_rule.addItems(["无", "每日", "每周", "每月", "每年"])
        h_opts.addWidget(QLabel("优先级:"))
        h_opts.addWidget(self.priority)
        h_opts.addSpacing(15)
        h_opts.addWidget(QLabel("重复:"))
        h_opts.addWidget(self.repeat_rule)
        lay_basic.addRow(h_opts)
        
        layout.addWidget(grp_basic)

        # === 2. 时间设置 ===
        grp_time = QGroupBox("时间设置")
        lay_time = QFormLayout(grp_time)

        # 辅助函数：创建时间选择行
        def make_time_row(label_text):
            date_ed = QDateEdit()
            date_ed.setCalendarPopup(True)
            date_ed.setDisplayFormat("yyyy-MM-dd")
            hour_sp = QSpinBox(); hour_sp.setRange(0, 23)
            min_sp = QSpinBox(); min_sp.setRange(0, 59)
            row = QHBoxLayout()
            row.addWidget(date_ed)
            row.addSpacing(5)
            row.addWidget(hour_sp); row.addWidget(QLabel("时"))
            row.addWidget(min_sp); row.addWidget(QLabel("分"))
            return date_ed, hour_sp, min_sp, row

        self.start_date, self.start_hour, self.start_minute, row_start = make_time_row("开始时间")
        lay_time.addRow("开始时间:", row_start)

        self.end_date, self.end_hour, self.end_minute, row_end = make_time_row("结束时间")
        lay_time.addRow("结束时间:", row_end)
        
        layout.addWidget(grp_time)

        # === 3. 提醒设置 ===
        grp_rem = QGroupBox("提醒设置")
        lay_rem = QVBoxLayout(grp_rem)
        
        self.reminder_grp = QCheckBox("启用提醒")
        self.reminder_grp.stateChanged.connect(self._toggle_reminder_ui)
        lay_rem.addWidget(self.reminder_grp)
        
        self.rem_ui_widget = QWidget()
        rem_inner = QVBoxLayout(self.rem_ui_widget)
        rem_inner.setContentsMargins(0, 5, 0, 0)
        
        # 提醒类型
        r_type = QHBoxLayout()
        r_type.addWidget(QLabel("类型:"))
        self.rem_type = QComboBox()
        self.rem_type.addItem("提前提醒 (如: 提前10分钟)", "advance")
        self.rem_type.addItem("绝对时间 (如: 2023-01-01 10:00)", "absolute")
        self.rem_type.currentIndexChanged.connect(self._toggle_rem_type_ui)
        r_type.addWidget(self.rem_type, 1)
        rem_inner.addLayout(r_type)
        
        # 提前量UI
        self.adv_widget = QWidget()
        adv_lay = QHBoxLayout(self.adv_widget)
        adv_lay.setContentsMargins(0, 0, 0, 0)
        self.advance_value = QSpinBox(); self.advance_value.setRange(1, 9999)
        self.advance_unit = QComboBox()
        self.advance_unit.addItems(["minutes", "hours", "days"])
        adv_lay.addWidget(QLabel("提前:"))
        adv_lay.addWidget(self.advance_value)
        adv_lay.addWidget(self.advance_unit, 1)
        rem_inner.addWidget(self.adv_widget)
        
        # 绝对时间UI
        self.abs_widget = QWidget()
        abs_lay = QHBoxLayout(self.abs_widget)
        abs_lay.setContentsMargins(0, 0, 0, 0)
        self.abs_dt_edit = QDateTimeEdit()
        self.abs_dt_edit.setCalendarPopup(True)
        abs_lay.addWidget(QLabel("时间点:"))
        abs_lay.addWidget(self.abs_dt_edit, 1)
        rem_inner.addWidget(self.abs_widget)
        
        lay_rem.addWidget(self.rem_ui_widget)
        layout.addWidget(grp_rem)

        # === 4. 描述/备注 ===
        layout.addWidget(QLabel("<b>描述/备注:</b>"))
        self.desc_edit = QTextEdit()
        layout.addWidget(self.desc_edit)

        # --- 底部按钮 ---
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_save = QPushButton("保存")
        btn_cancel.clicked.connect(self.reject)
        btn_save.clicked.connect(self._on_save)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        # --- 填充数据 ---
        self._fill_data(event, default_start_dt)

    def _toggle_reminder_ui(self):
        enabled = self.reminder_grp.isChecked()
        self.rem_ui_widget.setVisible(enabled)

    def _toggle_rem_type_ui(self):
        t = self.rem_type.currentData()
        self.adv_widget.setVisible(t == "advance")
        self.abs_widget.setVisible(t == "absolute")

    def _fill_data(self, event: Optional[Event], default_start_dt: Optional[QDateTime]):
        if event:
            self.title_edit.setText(event.title)
            self.desc_edit.setPlainText(event.description)
            self.priority.setCurrentText(event.priority)
            self.repeat_rule.setCurrentText(event.repeat_rule)
            
            s = event.start_time
            e = event.end_time
            self.start_date.setDate(s.date())
            self.start_hour.setValue(s.hour)
            self.start_minute.setValue(s.minute)
            self.end_date.setDate(e.date())
            self.end_hour.setValue(e.hour)
            self.end_minute.setValue(e.minute)
            
            # Reminder
            self.reminder_grp.setChecked(event.reminder_enabled)
            # 使用 findData 查找存储的 key ("advance" 或 "absolute")
            idx = self.rem_type.findData(event.reminder_type)
            if idx >= 0: self.rem_type.setCurrentIndex(idx)
            
            self.advance_value.setValue(event.advance_value)
            self.advance_unit.setCurrentText(event.advance_unit)
            if event.absolute_time:
                self.abs_dt_edit.setDateTime(event.absolute_time)
            else:
                self.abs_dt_edit.setDateTime(QDateTime.currentDateTime())

        else:
            # New event
            self.priority.setCurrentText("中")
            self.repeat_rule.setCurrentText("无")
            if default_start_dt:
                base = default_start_dt
            else:
                # Round to nearest hour
                now = QDateTime.currentDateTime()
                base = now.addSecs(3600 - (now.time().minute() * 60 + now.time().second()))
            
            self.start_date.setDate(base.date())
            self.start_hour.setValue(base.time().hour())
            self.start_minute.setValue(base.time().minute())
            
            end = base.addSecs(3600)
            self.end_date.setDate(end.date())
            self.end_hour.setValue(end.time().hour())
            self.end_minute.setValue(end.time().minute())
            
            self.abs_dt_edit.setDateTime(base)
            self.reminder_grp.setChecked(False)

        self._toggle_reminder_ui()
        self._toggle_rem_type_ui()

    def _parse_ui_dt(self, d_widget, h_widget, m_widget, label) -> Tuple[QDateTime, str]:
        date_val = d_widget.date()
        h = h_widget.value()
        m = m_widget.value()
        return QDateTime(date_val, QTime(h, m)), ""

    def _on_save(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "输入错误", "标题不能为空！")
            return
            
        start_dt, err1 = self._parse_ui_dt(self.start_date, self.start_hour, self.start_minute, "开始时间")
        if err1: QMessageBox.warning(self, "时间格式错误", err1); return

        end_dt, err2 = self._parse_ui_dt(self.end_date, self.end_hour, self.end_minute, "结束时间")
        if err2: QMessageBox.warning(self, "时间格式错误", err2); return

        if end_dt < start_dt:
            QMessageBox.warning(self, "时间逻辑错误", "结束时间不能早于开始时间！"); return
        
        self.start_dt_final = start_dt
        self.end_dt_final = end_dt
        self.accept()
    
    def get_event_payload(self) -> Dict:
        return {
            "title": self.title_edit.text().strip(),
            "start_time": self.start_dt_final.toString("yyyy-MM-ddTHH:mm"),
            "end_time": self.end_dt_final.toString("yyyy-MM-ddTHH:mm"),
            "priority": self.priority.currentText(),
            "repeat_rule": self.repeat_rule.currentText(),
            "reminder": {
                "enabled": self.reminder_enabled.isChecked(),
                # BUG修复：使用 currentData() 保存 "advance"/"absolute" 而不是中文显示文本
                "type": self.rem_type.currentData(),
                "advance_value": int(self.advance_value.value()),
                "advance_unit": self.advance_unit.currentText(),
                "absolute_time": self.abs_dt_edit.dateTime().toString("yyyy-MM-ddTHH:mm")
            },
            "description": self.desc_edit.toPlainText(),
            "finished": self._original_finished_state
        }

    @property
    def reminder_enabled(self):
        return self.reminder_grp