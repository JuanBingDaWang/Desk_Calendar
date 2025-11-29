from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QSlider, QPushButton,
    QColorDialog, QCheckBox, QStyleOptionSpinBox, QMessageBox, QComboBox, QFileDialog
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
        self.setFixedSize(420, 650) # 稍微增加高度
        self.s = dict(settings)
        # 获取 DataManager 实例引用，通常 settings 只是字典，我们需要回调或者让 parent 处理
        # 这里为了简单，我们假设 parent 是 MainWindow，有 dm 属性
        self.main_window = parent 
        if "font_color" not in self.s:
            self.s["font_color"] = "#000000"
        self._init_ui()

    def _init_ui(self):
        lay = QVBoxLayout(self)

        # --- 存储设置 (新增) ---
        store_grp = QHBoxLayout()
        store_grp.addWidget(QLabel("存储模式"))
        self.storage_mode = QComboBox()
        self.storage_mode.addItem("ICS文件 (通用)", "ics")
        self.storage_mode.addItem("SQLite数据库 (高性能)", "sqlite")
        
        current_mode = self.s.get("storage_mode", "ics")
        idx = self.storage_mode.findData(current_mode)
        if idx >= 0: self.storage_mode.setCurrentIndex(idx)
        
        # 存储模式变更由确认按钮统一处理，防止误触
        store_grp.addWidget(self.storage_mode)
        lay.addLayout(store_grp)

        # --- 数据导入导出 ---
        io_row = QHBoxLayout()
        
        self.btn_import = QPushButton("导入旧版（ICS）数据")
        self.btn_import.clicked.connect(self._import_data)
        io_row.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("导出数据为通用ICS格式")
        self.btn_export.clicked.connect(self._export_data)
        io_row.addWidget(self.btn_export)
        
        lay.addLayout(io_row)

        lay.addWidget(QLabel("<hr>")) # 分割线

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
        self.btn_ok.clicked.connect(self._on_accept) # 修改连接到新的处理函数

        row.addWidget(self.btn_exit) 
        row.addWidget(self.btn_info) 
        row.addStretch(1)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_ok)
        lay.addLayout(row)

        self.setLayout(lay)

    def _export_data(self):
        if not self.main_window: return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出数据", "ExportedEvents.ics", "iCalendar Files (*.ics)")
        if file_path:
            if self.main_window.dm.export_data_to_ics(file_path):
                QMessageBox.information(self, "成功", f"数据已导出到：\n{file_path}")
                # 打开文件夹
                folder = os.path.dirname(file_path)
                try:
                    os.startfile(folder)
                except:
                    pass
            else:
                QMessageBox.critical(self, "错误", "导出失败，请检查日志。")

    def _on_accept(self):
        # 处理存储模式切换
        new_mode = self.storage_mode.currentData()
        old_mode = self.s.get("storage_mode", "ics")
        
        if new_mode != old_mode:
            reply = QMessageBox.question(
                self, "切换存储模式", 
                f"确定要从 {old_mode} 切换到 {new_mode} 吗？\n当前数据将自动迁移。",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                if self.main_window:
                    self.main_window.dm.switch_storage_mode(new_mode)
                    self.s["storage_mode"] = new_mode # 更新本地字典以供返回
            else:
                # 恢复 UI 显示
                idx = self.storage_mode.findData(old_mode)
                self.storage_mode.setCurrentIndex(idx)
                return

        self.accept()

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
            "locked": False,
            "storage_mode": "ics"
        }
        
        self.s.update(default_settings)
        
        self.weeks.setValue(self.s["weeks"])
        self.cell_w.setValue(self.s["cell_width"])
        self.cell_h.setValue(self.s["cell_height"])
        self.row_gap.setValue(self.s["row_gap"])
        self.col_gap.setValue(self.s["col_gap"])
        self.opacity.setValue(int(self.s["opacity"] * 100))
        self.font_size.setValue(self.s["font_size"])
        
        idx = self.storage_mode.findData("ics")
        self.storage_mode.setCurrentIndex(idx)
        
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
            # storage_mode 单独处理，这里主要返回外观设置
        }

    def _exit_app(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().quit()

    def _show_info_dialog(self):
        msg = QMessageBox()
        msg.setWindowTitle("开发信息")
        msg.setText("开发者：卷饼大王（yp.work@foxmail.com）\n"\
            "版本：1.2.0\n"\
            "日期：2025-11-29\n"\
            "说明：新增 SQLite 存储支持，提升数据量大时的性能。\n"\
            "如果在使用中遇到任何bug，欢迎通过邮箱和我联系。\n"\
            "软件教程请见公众号：叶草凡的日记本。" )
        
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

    def _import_data(self):
        if not self.main_window: return
        
        # 提示用户最好先备份
        reply = QMessageBox.information(
            self, "导入数据", 
            "即将从外部 ICS 文件导入数据到当前日历。\n"
            "建议导入前先导出备份当前数据。\n\n"
            "【注意！】这仅导入日程数据，“全局备忘录”中的数据需要您手动复制到剪贴板，再粘贴进来。\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 ICS 文件", "", "iCalendar Files (*.ics);;All Files (*)"
        )
        
        if file_path:
            count = self.main_window.dm.import_from_ics(file_path)
            if count > 0:
                QMessageBox.information(self, "导入成功", f"成功导入了 {count} 条日程！\n关闭设置窗口后生效。")
                # 可以在这里触发一个信号告诉主窗口数据变了，但按照目前的架构，
                # 设置窗口关闭时通常会刷新视图，或者用户手动操作后刷新。
                # 为了即时反馈，可以手动刷新一下：
                if self.main_window:
                    self.main_window._refresh_views()
            else:
                QMessageBox.warning(self, "导入结果", "未导入任何数据。\n可能是文件格式错误或文件为空。")