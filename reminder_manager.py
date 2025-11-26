from PyQt5.QtCore import QObject, QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import QSystemTrayIcon, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
from datetime import datetime, timedelta
from typing import Optional
from data_manager import DataManager, Event

class ReminderManager(QObject):
    # 传递 Event 对象而不是字典，保持类型安全
    reminderTriggered = pyqtSignal(Event)

    def __init__(self, dm: DataManager, interval_ms: int = 30000):
        super().__init__()
        self.dm = dm
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_reminders)
        self.timer.start(interval_ms)

    def _calc_trigger_dt(self, e: Event, current_time: datetime) -> Optional[datetime]:
        """计算给定时间附近的触发时间点"""
        if not e.reminder_enabled:
            return None
            
        # 1. 确定基准开始时间
        # 如果是重复事项，我们需要计算【今天】（或最近一次）发生的时间
        # 简单起见，我们假设 current_time 对应的那次发生
        # 这里的简化逻辑：只检查今天发生的事件
        # 更严谨的逻辑应该结合 DataManager._is_occurring_on
        
        target_start = e.start_time
        
        # 处理重复日程的基准时间偏移
        if e.repeat_rule != "无":
            # 将基准日期移动到今天，保持时间（时分秒）不变
            # 只有当今天确实发生了这件事才算
            # 这里依赖 DataManager 的逻辑，但在 Manager 内部遍历时比较难
            # 简化策略：check_reminders 里已经遍历了今天的事件，
            # 传进来的 e 如果是重复事件，它应该是被 DataManager 处理过的 Virtual Event（时间已修正）
            # 或者我们需要在这里动态计算。
            # 鉴于 DataManager.get_events_between_dates 返回的是虚拟对象，时间已准。
            pass

        if e.reminder_type == "absolute":
            # 绝对时间提醒只针对非重复，或者重复事件的特定设置（暂不支持重复事件每期不同的绝对提醒）
            return e.absolute_time
            
        val = int(e.advance_value or 30)
        unit = (e.advance_unit or "minutes").lower()
        delta = timedelta(minutes=val)
        if unit == "hours":
            delta = timedelta(hours=val)
        elif unit == "days":
            delta = timedelta(days=val)
            
        return target_start - delta

    def check_reminders(self) -> None:
        """定时检查"""
        now = datetime.now().replace(second=0, microsecond=0)
        today_date = now.date()
        
        # 使用高效接口获取今天的事件（包含重复事件的虚拟对象，时间已修正为今天）
        todays_events_dict = self.dm.get_events_between_dates(today_date, today_date)
        events_list = todays_events_dict.get(today_date.strftime("%Y-%m-%d"), [])
        
        for e in events_list:
            if e.finished: 
                continue

            # 计算触发时间
            trig_dt = self._calc_trigger_dt(e, now)
            if not trig_dt:
                continue
            
            trig_dt = trig_dt.replace(second=0, microsecond=0)

            # 判断逻辑：
            # 1. 当前时间 >= 触发时间
            # 2. 从未提醒过 OR 上次提醒时间早于本次触发时间 (针对重复事件)
            should_remind = False
            
            if now >= trig_dt:
                if e.last_reminded_time is None:
                    should_remind = True
                elif e.last_reminded_time < trig_dt:
                    should_remind = True
            
            if should_remind:
                # 找到原始对象进行更新（因为 e 可能是虚拟对象）
                origin_event = self.dm.get_event(e.id)
                if origin_event:
                    # 发出信号
                    self.reminderTriggered.emit(origin_event)

    @staticmethod
    def show_notification(tray_icon: QSystemTrayIcon, e: Event) -> QDialog:
        reminder_window = QDialog()
        reminder_window.setWindowTitle(f"日程提醒：{e.title}")
        reminder_window.setFixedSize(400, 200)
        reminder_window.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)

        main_layout = QVBoxLayout()
        title_label = QLabel(f"<h3>{e.title or '未命名事项'}</h3>")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 格式化时间
        t_str = e.start_time.strftime("%Y-%m-%d %H:%M")
        if e.end_time:
             t_str += f" - {e.end_time.strftime('%H:%M')}"
             
        time_label = QLabel(f"时间：{t_str}")
        time_label.setWordWrap(True)
        main_layout.addWidget(time_label)

        desc_label = QLabel(f"备注：{e.description or '无备注'}")
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)

        button_layout = QHBoxLayout()
        snooze_btn = QPushButton("稍后提醒")
        snooze_btn.setObjectName("snoozeButton")
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(reminder_window.accept)
        button_layout.addWidget(snooze_btn)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

        reminder_window.setLayout(main_layout)
        reminder_window.event_data = e # 保存对象引用

        screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        window_geo = reminder_window.frameGeometry()
        x = screen_geo.right() - window_geo.width()
        y = screen_geo.bottom() - window_geo.height()
        reminder_window.move(x, y)
        
        # 播放系统提示音（可选）
        QApplication.beep()
        
        return reminder_window

    def snooze(self, event_id: int, minutes: int) -> None:
        e = self.dm.get_event(int(event_id))
        if not e:
            return
        # 贪睡逻辑：修改为绝对时间提醒，设置为当前+N分钟
        e.reminder_enabled = True
        e.reminder_type = "absolute"
        e.absolute_time = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=int(minutes))
        # 重置 last_reminded_time 以便下次再次触发
        e.last_reminded_time = None 
        self.dm.update_event(e)