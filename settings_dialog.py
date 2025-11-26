from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QSlider, QPushButton,
    QColorDialog, QCheckBox, QStyleOptionSpinBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap
import os

class SettingsDialog(QDialog):
    """集中设置面板"""
    settingsChanged = pyqtSignal(dict)

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("设置")
        self.setFixedSize(420, 580)
        self.s = dict(settings)
        if "font_color" not in self.s:
            self.s["font_color"] = "#000000"
        self._init_ui()

    def _init_ui(self):
        lay = QVBoxLayout(self)

        # --- 周数 ---
        row = QHBoxLayout()
        row.addWidget(QLabel("显示周数"))
        self.weeks = QSpinBox()
        self.weeks.setRange(1, 52) 
        self.weeks.setValue(int(self.s.get("weeks", 4)))
        self.weeks.valueChanged.connect(self._on_setting_changed)
        
        row.addWidget(self.weeks)
        row.addStretch(1) 
        lay.addLayout(row)

        # --- 字号 ---
        row = QHBoxLayout()
        row.addWidget(QLabel("文字字号"))
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 36)
        self.font_size.setValue(int(self.s.get("font_size", 12))) 
        self.font_size.valueChanged.connect(self._on_setting_changed)
        
        row.addWidget(self.font_size)
        row.addStretch(1) 
        lay.addLayout(row)

        # --- 格子尺寸 ---
        row = QHBoxLayout()
        row.addWidget(QLabel("格子宽度"))
        self.cell_w = QSlider(Qt.Horizontal)
        self.cell_w.setRange(90, 360)
        self.cell_w.setValue(int(self.s.get("cell_width", 140)))
        self.cell_w.setTickInterval(10)
        self.cell_w.setTickPosition(QSlider.TicksBelow)
        self.cell_w.valueChanged.connect(self._on_setting_changed)
        
        self.cell_w_value = QLabel(str(self.cell_w.value()))
        self.cell_w.valueChanged.connect(lambda value: self.cell_w_value.setText(str(value)))
        
        row.addWidget(self.cell_w)
        row.addWidget(self.cell_w_value)
        
        row.addWidget(QLabel("格子高度"))
        self.cell_h = QSlider(Qt.Horizontal)
        self.cell_h.setRange(90, 360)
        self.cell_h.setValue(int(self.s.get("cell_height", 110)))
        self.cell_h.setTickInterval(10)
        self.cell_h.setTickPosition(QSlider.TicksBelow)
        self.cell_h.valueChanged.connect(self._on_setting_changed)
        
        self.cell_h_value = QLabel(str(self.cell_h.value()))
        self.cell_h.valueChanged.connect(lambda value: self.cell_h_value.setText(str(value)))
        
        row.addWidget(self.cell_h)
        row.addWidget(self.cell_h_value)
        lay.addLayout(row)

        # --- 间距 ---
        row = QHBoxLayout()
        row.addWidget(QLabel("行间距"))
        self.row_gap = QSlider(Qt.Horizontal)
        self.row_gap.setRange(0, 60)
        self.row_gap.setValue(int(self.s.get("row_gap", 6)))
        self.row_gap.setTickInterval(5)
        self.row_gap.setTickPosition(QSlider.TicksBelow)
        self.row_gap.valueChanged.connect(self._on_setting_changed)
        
        self.row_gap_value = QLabel(str(self.row_gap.value()))
        self.row_gap.valueChanged.connect(lambda value: self.row_gap_value.setText(str(value)))
        
        row.addWidget(self.row_gap)
        row.addWidget(self.row_gap_value)

        row.addWidget(QLabel("列间距"))
        self.col_gap = QSlider(Qt.Horizontal)
        self.col_gap.setRange(0, 60)
        self.col_gap.setValue(int(self.s.get("col_gap", 6)))
        self.col_gap.setTickInterval(5)
        self.col_gap.setTickPosition(QSlider.TicksBelow)
        self.col_gap.valueChanged.connect(self._on_setting_changed)
        
        self.col_gap_value = QLabel(str(self.col_gap.value()))
        self.col_gap.valueChanged.connect(lambda value: self.col_gap_value.setText(str(value)))
        
        row.addWidget(self.col_gap)
        row.addWidget(self.col_gap_value)
        lay.addLayout(row)

        # --- 透明度 ---
        row = QHBoxLayout()
        row.addWidget(QLabel("透明度"))
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(20, 100)
        self.opacity.setValue(int(float(self.s.get("opacity", 0.95)) * 100))
        self.opacity.setTickInterval(5)
        self.opacity.setTickPosition(QSlider.TicksBelow)
        self.opacity.valueChanged.connect(self._on_setting_changed)
        
        self.opacity_value = QLabel(f"{self.opacity.value()}%")
        self.opacity.valueChanged.connect(lambda value: self.opacity_value.setText(f"{value}%"))
        
        row.addWidget(self.opacity)
        row.addWidget(self.opacity_value)
        lay.addLayout(row)

        # --- 背景色 ---
        row = QHBoxLayout()
        row.addWidget(QLabel("背景色"))
        self.color_btn = QPushButton()
        self._update_bg_color_button()
        self.color_btn.clicked.connect(self._choose_bg_color)
        row.addWidget(self.color_btn)
        lay.addLayout(row)
        
        # --- 字体颜色 ---
        row = QHBoxLayout()
        row.addWidget(QLabel("字体颜色"))
        self.font_color_btn = QPushButton()
        self._update_font_color_button()
        self.font_color_btn.clicked.connect(self._choose_font_color)
        row.addWidget(self.font_color_btn)
        lay.addLayout(row)

        # --- 复位按钮 ---
        row = QHBoxLayout()
        row.addStretch(1)
        self.reset_btn = QPushButton("复位所有设置")
        self.reset_btn.clicked.connect(self._reset_settings)
        row.addWidget(self.reset_btn)
        lay.addLayout(row)

        # --- 底部按钮 ---
        row = QHBoxLayout()
        self.btn_exit = QPushButton("退出应用")
        self.btn_info = QPushButton("开发信息")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok = QPushButton("保存")
        
        self.btn_exit.clicked.connect(self._exit_app)
        self.btn_info.clicked.connect(self._show_info_dialog)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept)

        row.addWidget(self.btn_exit) 
        row.addWidget(self.btn_info) 
        row.addStretch(1)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_ok)
        lay.addLayout(row)

        self.setLayout(lay)

    def _update_bg_color_button(self):
        color = self.s.get("bg_color", "#ffffff")
        self.color_btn.setStyleSheet(f"background-color: {color};")

    def _update_font_color_button(self):
        color = self.s.get("font_color", "#000000")
        self.font_color_btn.setStyleSheet(f"background-color: {color};")

    def _choose_bg_color(self):
        c = QColorDialog.getColor(QColor(self.s.get("bg_color", "#ffffff")), self, "选择背景色")
        if c.isValid():
            self.s["bg_color"] = c.name()
            self._update_bg_color_button()
            self._on_setting_changed()

    def _choose_font_color(self):
        c = QColorDialog.getColor(QColor(self.s.get("font_color", "#000000")), self, "选择字体颜色")
        if c.isValid():
            self.s["font_color"] = c.name()
            self._update_font_color_button()
            self._on_setting_changed()

    def _on_setting_changed(self):
        self.settingsChanged.emit(self.values())

    def _reset_settings(self):
        default_settings = {
            "weeks": 4,
            "cell_width": 140,
            "cell_height": 110,
            "row_gap": 6,
            "col_gap": 6,
            "opacity": 0.95,
            "bg_color": "#ffffff",
            "font_color": "#000000",
            "font_size": 12,
            "locked": False
        }
        
        self.s.update(default_settings)
        
        self.weeks.setValue(self.s["weeks"])
        self.cell_w.setValue(self.s["cell_width"])
        self.cell_h.setValue(self.s["cell_height"])
        self.row_gap.setValue(self.s["row_gap"])
        self.col_gap.setValue(self.s["col_gap"])
        self.opacity.setValue(int(self.s["opacity"] * 100))
        self.font_size.setValue(self.s["font_size"])
        
        self._update_bg_color_button()
        self._update_font_color_button()
        self._on_setting_changed()

    def values(self) -> dict:
        return {
            "weeks": int(self.weeks.value()),
            "font_size": int(self.font_size.value()),
            "cell_width": int(self.cell_w.value()),
            "cell_height": int(self.cell_h.value()),
            "row_gap": int(self.row_gap.value()),
            "col_gap": int(self.col_gap.value()),
            "opacity": self.opacity.value() / 100.0,
            "bg_color": self.s.get("bg_color", "#ffffff"),
            "font_color": self.s.get("font_color", "#000000"),
        }

    def _exit_app(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().quit()

    def _show_info_dialog(self):
        msg = QMessageBox()
        msg.setWindowTitle("开发信息")
        msg.setText("开发者：卷饼大王（yp.work@foxmail.com）\n"\
            "版本：1.1.0\n"\
            "日期：2025-11-26\n"\
            "说明：修复了重复提醒Bug，优化了加载性能。\n"\
            "如果在使用中遇到任何bug，欢迎通过邮箱和我联系。\n"\
            "软件教程和源码请见公众号：叶草凡的日记本。" )
        
        file_dir = os.path.dirname(os.path.abspath(__file__))
        qrcode_path = os.path.join(file_dir, "payment_qrcode.png")
        pixmap = QPixmap(qrcode_path)
        
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            msg.setIconPixmap(scaled_pixmap)
        else:
            msg.setIcon(QMessageBox.Information)
        
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()