from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QSlider, QPushButton,
    QColorDialog, QCheckBox, QStyleOptionSpinBox, QMessageBox, QComboBox, 
    QFileDialog, QGroupBox, QFormLayout
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
        self.setFixedSize(450, 750) 
        
        self.s = dict(settings)
        self.main_window = parent 
        if "font_color" not in self.s:
            self.s["font_color"] = "#000000"
            
        self._init_ui()
        # 初始化完成后立即应用一次样式
        self._update_dialog_style()

    def _hex_to_rgba(self, hex_code: str, alpha_percent: int) -> str:
        """将 hex 颜色和 0-100 的透明度转换为 rgba 字符串"""
        hex_code = hex_code.lstrip('#')
        if len(hex_code) == 6:
            r = int(hex_code[0:2], 16)
            g = int(hex_code[2:4], 16)
            b = int(hex_code[4:6], 16)
            a = int(alpha_percent * 255 / 100)
            return f"rgba({r}, {g}, {b}, {a})"
        return hex_code

    def _update_dialog_style(self):
        """根据当前控件的值动态更新自身样式"""
        # 获取当前界面上的值（实现实时预览自身）
        vals = self.values()
        bg_hex = vals.get("bg_color", "#ffffff")
        font_hex = vals.get("font_color", "#000000")
        
        # 强制使用 100% 不透明，防止背景变黑
        bg_rgba = self._hex_to_rgba(bg_hex, 100)
        
        # 动态应用背景色和字体色，同时设置输入框样式
        self.setStyleSheet(f"""
            QDialog {{ 
                color: {font_hex}; 
                background-color: {bg_rgba}; 
            }}
            QGroupBox {{ 
                font-weight: bold; 
                margin-top: 10px; 
                border: 1px solid gray; 
                border-radius: 5px; 
                padding-top: 15px; 
                background-color: transparent; 
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                subcontrol-position: top left; 
                padding: 0 5px; 
                color: {font_hex};
            }}
            QLabel, QCheckBox {{ color: {font_hex}; background-color: transparent; }}
            
            /* 输入控件统一风格 */
            QComboBox, QSpinBox {{
                background-color: {bg_rgba};
                color: {font_hex};
                border: 1px solid #a0a0a0;
                border-radius: 3px;
                padding: 2px;
                selection-background-color: darkgray;
            }}
            /* 列表下拉框 */
            QComboBox QAbstractItemView {{
                background-color: {bg_rgba};
                color: {font_hex};
                selection-background-color: darkgray;
            }}
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # === 分组1：数据与存储 ===
        grp_data = QGroupBox("数据与存储")
        lay_data = QVBoxLayout(grp_data)
        
        h_store = QHBoxLayout()
        h_store.addWidget(QLabel("存储模式:"))
        self.storage_mode = QComboBox()
        self.storage_mode.addItem("ICS文件 (通用)", "ics")
        self.storage_mode.addItem("SQLite数据库 (高性能)", "sqlite")
        current_mode = self.s.get("storage_mode", "ics")
        idx = self.storage_mode.findData(current_mode)
        if idx >= 0: self.storage_mode.setCurrentIndex(idx)
        h_store.addWidget(self.storage_mode, 1)
        lay_data.addLayout(h_store)

        h_io = QHBoxLayout()
        self.btn_import = QPushButton("导入 ICS")
        self.btn_import.clicked.connect(self._import_data)
        self.btn_export = QPushButton("导出 ICS")
        self.btn_export.clicked.connect(self._export_data)
        h_io.addWidget(self.btn_import)
        h_io.addWidget(self.btn_export)
        lay_data.addLayout(h_io)
        
        main_layout.addWidget(grp_data)

        # === 分组2：外观与显示 ===
        grp_view = QGroupBox("外观与显示")
        lay_view = QVBoxLayout(grp_view)
        
        # 显隐设置
        h_chk = QHBoxLayout()
        self.chk_calendar_time = QCheckBox("日历显示时间")
        self.chk_list_time = QCheckBox("列表显示时间")
        self.chk_calendar_time.setChecked(bool(self.s.get("show_time_in_calendar", True)))
        self.chk_list_time.setChecked(bool(self.s.get("show_time_in_list", True)))
        self.chk_calendar_time.stateChanged.connect(self._on_setting_changed)
        self.chk_list_time.stateChanged.connect(self._on_setting_changed)
        h_chk.addWidget(self.chk_calendar_time)
        h_chk.addWidget(self.chk_list_time)
        lay_view.addLayout(h_chk)
        
        # 颜色设置
        grid_col = QFormLayout()
        
        # 颜色按钮辅助函数
        def make_color_btn(key):
            btn = QPushButton()
            btn.setFixedSize(60, 24)
            self._update_color_btn(btn, key)
            btn.clicked.connect(lambda: self._choose_color(key, btn))
            return btn
        
        self.color_btn = make_color_btn("bg_color")
        self.font_color_btn = make_color_btn("font_color")
        grid_col.addRow("全局背景:", self.color_btn)
        grid_col.addRow("默认字体:", self.font_color_btn)
        
        h_prio = QHBoxLayout()
        self.btn_p_high = make_color_btn("font_color_high")
        self.btn_p_med = make_color_btn("font_color_medium")
        self.btn_p_low = make_color_btn("font_color_low")
        h_prio.addWidget(QLabel("高:"))
        h_prio.addWidget(self.btn_p_high)
        h_prio.addWidget(QLabel("中:"))
        h_prio.addWidget(self.btn_p_med)
        h_prio.addWidget(QLabel("低:"))
        h_prio.addWidget(self.btn_p_low)
        grid_col.addRow("优先级颜色:", h_prio)
        
        lay_view.addLayout(grid_col)

        # 透明度
        grid_op = QFormLayout()
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(20, 100)
        self.opacity.setValue(int(float(self.s.get("opacity", 0.95)) * 100))
        self.opacity.valueChanged.connect(self._on_setting_changed)
        self.opacity_value = QLabel(f"{self.opacity.value()}%")
        self.opacity.valueChanged.connect(lambda v: self.opacity_value.setText(f"{v}%"))
        
        row_op = QHBoxLayout()
        row_op.addWidget(self.opacity)
        row_op.addWidget(self.opacity_value)
        grid_op.addRow("全局不透明度:", row_op)

        self.bg_opacity = QSlider(Qt.Horizontal)
        self.bg_opacity.setRange(0, 100)
        self.bg_opacity.setValue(int(self.s.get("bg_opacity", 100)))
        self.bg_opacity.valueChanged.connect(self._on_setting_changed)
        self.bg_opacity_value = QLabel(f"{self.bg_opacity.value()}%")
        self.bg_opacity.valueChanged.connect(lambda v: self.bg_opacity_value.setText(f"{v}%"))
        
        row_bg_op = QHBoxLayout()
        row_bg_op.addWidget(self.bg_opacity)
        row_bg_op.addWidget(self.bg_opacity_value)
        grid_op.addRow("背景不透明度:", row_bg_op)
        
        lay_view.addLayout(grid_op)
        main_layout.addWidget(grp_view)

        # === 分组3：布局与尺寸 ===
        grp_layout = QGroupBox("布局与尺寸")
        lay_lo = QFormLayout(grp_layout)
        
        # 周数
        self.weeks = QSpinBox()
        self.weeks.setRange(1, 52) 
        self.weeks.setValue(int(self.s.get("weeks", 4)))
        self.weeks.valueChanged.connect(self._on_setting_changed)
        lay_lo.addRow("显示周数:", self.weeks)

        # 字号
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 36)
        self.font_size.setValue(int(self.s.get("font_size", 12))) 
        self.font_size.valueChanged.connect(self._on_setting_changed)
        lay_lo.addRow("字体大小:", self.font_size)
        
        # 尺寸滑块
        def make_slider_row(key, min_v, max_v, scale=1):
            sl = QSlider(Qt.Horizontal)
            sl.setRange(min_v, max_v)
            val = int(self.s.get(key, min_v))
            sl.setValue(val)
            sl.valueChanged.connect(self._on_setting_changed)
            lbl = QLabel(str(val))
            sl.valueChanged.connect(lambda v: lbl.setText(str(v)))
            r = QHBoxLayout()
            r.addWidget(sl)
            r.addWidget(lbl)
            return sl, lbl, r

        self.cell_w, self.cell_w_value, row_cw = make_slider_row("cell_width", 90, 360)
        lay_lo.addRow("格子宽度:", row_cw)
        
        self.cell_h, self.cell_h_value, row_ch = make_slider_row("cell_height", 90, 360)
        lay_lo.addRow("格子高度:", row_ch)
        
        self.row_gap, self.row_gap_value, row_rg = make_slider_row("row_gap", 0, 60)
        lay_lo.addRow("行间距:", row_rg)
        
        self.col_gap, self.col_gap_value, row_cg = make_slider_row("col_gap", 0, 60)
        lay_lo.addRow("列间距:", row_cg)
        
        main_layout.addWidget(grp_layout)

        # --- 底部按钮 ---
        main_layout.addStretch(1)
        
        # 复位
        h_reset = QHBoxLayout()
        h_reset.addStretch(1)
        self.reset_btn = QPushButton("复位默认设置")
        self.reset_btn.clicked.connect(self._reset_settings)
        h_reset.addWidget(self.reset_btn)
        main_layout.addLayout(h_reset)
        
        # 功能按钮
        h_btns = QHBoxLayout()
        self.btn_exit = QPushButton("退出应用")
        self.btn_info = QPushButton("开发信息")
        self.btn_cancel = QPushButton("取消")
        self.btn_ok = QPushButton("保存")
        
        self.btn_exit.clicked.connect(self._exit_app)
        self.btn_info.clicked.connect(self._show_info_dialog)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._on_accept)

        h_btns.addWidget(self.btn_exit) 
        h_btns.addWidget(self.btn_info) 
        h_btns.addStretch(1)
        h_btns.addWidget(self.btn_cancel)
        h_btns.addWidget(self.btn_ok)
        main_layout.addLayout(h_btns)

    def _export_data(self):
        if not self.main_window: return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出数据", "ExportedEvents.ics", "iCalendar Files (*.ics)")
        if file_path:
            if self.main_window.dm.export_data_to_ics(file_path):
                QMessageBox.information(self, "成功", f"数据已导出到：\n{file_path}")
                folder = os.path.dirname(file_path)
                try:
                    os.startfile(folder)
                except:
                    pass
            else:
                QMessageBox.critical(self, "错误", "导出失败，请检查日志。")

    def _on_accept(self):
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
                    self.s["storage_mode"] = new_mode 
            else:
                idx = self.storage_mode.findData(old_mode)
                self.storage_mode.setCurrentIndex(idx)
                return
        self.accept()

    def _update_color_btn(self, btn: QPushButton, key: str):
        color = self.s.get(key, "#000000") 
        btn.setStyleSheet(f"background-color: {color}; border: 1px solid gray;")

    def _choose_color(self, key: str, btn: QPushButton):
        curr = self.s.get(key, "#000000")
        c = QColorDialog.getColor(QColor(curr), self, "选择颜色")
        if c.isValid():
            self.s[key] = c.name()
            self._update_color_btn(btn, key)
            self._on_setting_changed()

    def _on_setting_changed(self):
        # 实时更新自己的样式
        self._update_dialog_style()
        self.settingsChanged.emit(self.values())

    def _reset_settings(self):
        default_settings = {
            "weeks": 4,
            "cell_width": 140,
            "cell_height": 110,
            "row_gap": 6,
            "col_gap": 6,
            "opacity": 0.95,
            "bg_opacity": 100,
            "bg_color": "#ffffff",
            "font_color": "#000000",
            "font_size": 12,
            "locked": False,
            "storage_mode": "ics",
            "show_time_in_calendar": True,
            "show_time_in_list": True,
            "font_color_high": "#FF4500",
            "font_color_medium": "#000000",
            "font_color_low": "#696969"
        }
        self.s.update(default_settings)
        
        self.weeks.setValue(self.s["weeks"])
        self.cell_w.setValue(self.s["cell_width"])
        self.cell_h.setValue(self.s["cell_height"])
        self.row_gap.setValue(self.s["row_gap"])
        self.col_gap.setValue(self.s["col_gap"])
        self.opacity.setValue(int(self.s["opacity"] * 100))
        self.bg_opacity.setValue(int(self.s["bg_opacity"]))
        self.chk_calendar_time.setChecked(True)
        self.chk_list_time.setChecked(True)
        
        idx = self.storage_mode.findData("ics")
        self.storage_mode.setCurrentIndex(idx)
        
        self._update_color_btn(self.color_btn, "bg_color")
        self._update_color_btn(self.font_color_btn, "font_color")
        self._update_color_btn(self.btn_p_high, "font_color_high")
        self._update_color_btn(self.btn_p_med, "font_color_medium")
        self._update_color_btn(self.btn_p_low, "font_color_low")
        
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
            "bg_opacity": int(self.bg_opacity.value()),
            "bg_color": self.s.get("bg_color", "#ffffff"),
            "font_color": self.s.get("font_color", "#000000"),
            "show_time_in_calendar": self.chk_calendar_time.isChecked(),
            "show_time_in_list": self.chk_list_time.isChecked(),
            "font_color_high": self.s.get("font_color_high", "#FF4500"),
            "font_color_medium": self.s.get("font_color_medium", "#000000"),
            "font_color_low": self.s.get("font_color_low", "#696969"),
        }

    def _exit_app(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().quit()

    def _show_info_dialog(self):
        msg = QMessageBox()
        msg.setWindowTitle("开发信息")
        msg.setText("开发者：卷饼大王（yp.work@foxmail.com）\n"\
            "版本：1.3.0\n"\
            "日期：2025-12-20\n"\
            "说明：\n"\
            "1. 支持背景颜色透明度调节（实现完全透明背景）。\n"\
            "2. 新增不同优先级事项的字体颜色设置。\n"\
            "3. 日历视图格子边框颜色跟随字体颜色。\n"\
            "4. 界面细节优化（Tab页签和设置页文字固定黑色）。\n"\
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
                if self.main_window:
                    self.main_window._refresh_views()
            else:
                QMessageBox.warning(self, "导入结果", "未导入任何数据。\n可能是文件格式错误或文件为空。")