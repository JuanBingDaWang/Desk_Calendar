from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDateTimeEdit,
    QTextEdit, QPushButton, QCheckBox, QComboBox, QSpinBox, QMessageBox,
    QDateEdit
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
        self.setFixedSize(420, 600)
        
        self.start_dt_final = None
        self.end_dt_final = None
        
        self._init_ui(event, default_start_dt)

    def _init_ui(self, event: Optional[Event], default_start_dt: Optional[QDateTime]) -> None:
        layout = QVBoxLayout()
        self._original_finished_state = event.finished if event else False
        self.int_validator = QIntValidator(0, 99, self)

        # --- 标题 ---
        layout.addWidget(QLabel("标题"))
        self.title_edit = QLineEdit()
        layout.addWidget(self.title_edit)

        # --- 开始时间 ---
        layout.addWidget(QLabel("开始时间"))
        start_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_hour = QLineEdit()
        self.start_hour.setPlaceholderText("时"); self.start_hour.setFixedWidth(40); self.start_hour.setValidator(self.int_validator)
        self.start_hour.editingFinished.connect(lambda: self._fmt_pad(self.start_hour))
        self.start_minute = QLineEdit()
        self.start_minute.setPlaceholderText("分"); self.start_minute.setFixedWidth(40); self.start_minute.setValidator(self.int_validator)
        self.start_minute.editingFinished.connect(lambda: self._fmt_pad(self.start_minute))
        start_layout.addWidget(self.start_date, 1); start_layout.addStretch()
        start_layout.addWidget(self.start_hour); start_layout.addWidget(QLabel(":")); start_layout.addWidget(self.start_minute)
        layout.addLayout(start_layout)

        # --- 结束时间 ---
        layout.addWidget(QLabel("结束时间"))
        end_layout = QHBoxLayout()
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_hour = QLineEdit()
        self.end_hour.setPlaceholderText("时"); self.end_hour.setFixedWidth(40); self.end_hour.setValidator(self.int_validator)
        self.end_hour.editingFinished.connect(lambda: self._fmt_pad(self.end_hour))
        self.end_minute = QLineEdit()
        self.end_minute.setPlaceholderText("分"); self.end_minute.setFixedWidth(40); self.end_minute.setValidator(self.int_validator)
        self.end_minute.editingFinished.connect(lambda: self._fmt_pad(self.end_minute))
        end_layout.addWidget(self.end_date, 1); end_layout.addStretch()
        end_layout.addWidget(self.end_hour); end_layout.addWidget(QLabel(":")); end_layout.addWidget(self.end_minute)
        layout.addLayout(end_layout)

        # --- 优先级/重复 ---
        pr_row = QHBoxLayout()
        pr_row.addWidget(QLabel("优先级")); self.priority = QComboBox(); self.priority.addItems(["低", "中", "高"]); pr_row.addWidget(self.priority)
        pr_row.addWidget(QLabel("重复")); self.repeat_rule = QComboBox(); self.repeat_rule.addItems(["无", "每日", "每周", "每月", "每年"]); pr_row.addWidget(self.repeat_rule)
        layout.addLayout(pr_row)

        # --- 提醒 ---
        layout.addWidget(QLabel("提醒"))
        self.reminder_enabled = QCheckBox("启用提醒"); self.reminder_enabled.setChecked(False); layout.addWidget(self.reminder_enabled)
        rem_row1 = QHBoxLayout()
        self.rem_type = QComboBox(); self.rem_type.addItems(["advance", "absolute"])
        rem_row1.addWidget(QLabel("方式")); rem_row1.addWidget(self.rem_type)
        self.advance_value = QSpinBox(); self.advance_value.setRange(1, 10000); self.advance_value.setValue(30)
        self.advance_unit = QComboBox(); self.advance_unit.addItems(["minutes", "hours", "days"])
        rem_row1.addWidget(QLabel("提前")); rem_row1.addWidget(self.advance_value); rem_row1.addWidget(self.advance_unit)
        layout.addLayout(rem_row1)
        rem_row2 = QHBoxLayout()
        rem_row2.addWidget(QLabel("绝对时间")); self.absolute_time = QDateTimeEdit(); self.absolute_time.setCalendarPopup(True)
        rem_row2.addWidget(self.absolute_time); layout.addLayout(rem_row2)

        # --- 备注/按钮 ---
        layout.addWidget(QLabel("备注")); self.desc = QTextEdit(); self.desc.setFixedHeight(100); layout.addWidget(self.desc)
        btn_row = QHBoxLayout()
        self.btn_ok = QPushButton("保存"); self.btn_cancel = QPushButton("取消")
        self.btn_ok.clicked.connect(self._validate_and_accept); self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_ok); btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)
        self.setLayout(layout)

        # --- 初始化 ---
        now = QDateTime.currentDateTime()
        start_dt = default_start_dt if default_start_dt else now
        self._set_ui_dt(self.start_date, self.start_hour, self.start_minute, start_dt)
        self._set_ui_dt(self.end_date, self.end_hour, self.end_minute, start_dt.addSecs(3600))
        self.absolute_time.setDateTime(start_dt.addSecs(-1800))

        if event:
            self._fill(event)

        self._sync_reminder_controls()
        self.rem_type.currentIndexChanged.connect(self._sync_reminder_controls)
        self.reminder_enabled.stateChanged.connect(self._sync_reminder_controls)

    def _fmt_pad(self, line_edit: QLineEdit) -> None:
        txt = line_edit.text().strip()
        if txt.isdigit() and len(txt) == 1: line_edit.setText("0" + txt)

    def _set_ui_dt(self, d_edit: QDateEdit, h_edit: QLineEdit, m_edit: QLineEdit, dt: QDateTime) -> None:
        d_edit.setDate(dt.date())
        h_edit.setText(f"{dt.time().hour():02d}")
        m_edit.setText(f"{dt.time().minute():02d}")

    def _parse_ui_dt(self, d_edit: QDateEdit, h_edit: QLineEdit, m_edit: QLineEdit, name: str) -> Tuple[Optional[QDateTime], str]:
        h_str = h_edit.text().strip(); m_str = m_edit.text().strip()
        if not h_str or not m_str: return None, f"“{name}”的时间不能为空"
        if not (h_str.isdigit() and m_str.isdigit()): return None, f"“{name}”的时间必须是整数"
        h = int(h_str); m = int(m_str)
        if not (0 <= h <= 23) or not (0 <= m <= 59): return None, f"“{name}”的时间超出范围"
        return QDateTime(d_edit.date(), QTime(h, m)), ""

    def _sync_reminder_controls(self) -> None:
        enabled = self.reminder_enabled.isChecked()
        is_abs = self.rem_type.currentText() == "absolute"
        self.advance_value.setEnabled(enabled and not is_abs)
        self.advance_unit.setEnabled(enabled and not is_abs)
        self.absolute_time.setEnabled(enabled and is_abs)

    def _fill(self, e: Event) -> None:
        self.title_edit.setText(e.title)
        self.priority.setCurrentText(e.priority)
        self.repeat_rule.setCurrentText(e.repeat_rule)
        self.desc.setPlainText(e.description)

        self._set_ui_dt(self.start_date, self.start_hour, self.start_minute, QDateTime(e.start_time))
        # Handle case where end_time might be None (though DataManager ensures defaults)
        et = e.end_time if e.end_time else e.start_time
        self._set_ui_dt(self.end_date, self.end_hour, self.end_minute, QDateTime(et))

        self.reminder_enabled.setChecked(e.reminder_enabled)
        self.rem_type.setCurrentText(e.reminder_type)
        self.advance_value.setValue(e.advance_value)
        self.advance_unit.setCurrentText(e.advance_unit)
        
        if e.absolute_time:
            self.absolute_time.setDateTime(QDateTime(e.absolute_time))

    def _validate_and_accept(self) -> None:
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
                "type": self.rem_type.currentText(),
                "advance_value": int(self.advance_value.value()),
                "advance_unit": self.advance_unit.currentText(),
                "absolute_time": self.absolute_time.dateTime().toString("yyyy-MM-ddTHH:mm")
                if self.rem_type.currentText() == "absolute" else None,
            },
            "finished": self._original_finished_state,
            "description": self.desc.toPlainText().strip(),
        }