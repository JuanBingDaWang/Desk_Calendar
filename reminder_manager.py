from PyQt5.QtCore import QObject, QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import QSystemTrayIcon, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
from datetime import datetime, timedelta
from typing import Optional
from data_manager import DataManager, Event

class ReminderManager(QObject):
    # 传递 Event 对象而不是字典，保持类型安全
    reminderTriggered = pyqtSignal(Event)
    dateChanged = pyqtSignal()

    def __init__(self, dm: DataManager, interval_ms: int = 30000):
        super().__init__()
        self.dm = dm
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_reminders)
        self.timer.start(interval_ms)
        self._current_date = datetime.now().date()

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

        if today_date != self._current_date:
            self._current_date = today_date
            self.dateChanged.emit() 
        
        # 【关键修改】查询范围扩大。
        # 为了支持“提前 N 天”的提醒，我们需要预读取未来 N 天的日程。
        # 即使只查未来 7 天，也能覆盖绝大多数需求。如果支持更久，可以设为 30 或 60。
        look_ahead_days = 30 
        end_query_date = today_date + timedelta(days=look_ahead_days)
        
        # 获取今天到未来 30 天的所有日程
        events_dict = self.dm.get_events_between_dates(today_date, end_query_date)
        
        # 遍历字典中所有的 key (每一天)
        for date_str, events_list in events_dict.items():
            for e in events_list:
                if e.finished: 
                    continue

                # 计算触发时间
                trig_dt = self._calc_trigger_dt(e, now)
                if not trig_dt:
                    continue
                
                trig_dt = trig_dt.replace(second=0, microsecond=0)

                # 判断逻辑... (保持不变)
                should_remind = False
                if now >= trig_dt:
                    # 增加一个保护：如果触发时间太久远（比如 2 天前就该触发了），是否还要弹窗？
                    # 你的逻辑是只要没提醒过就弹，这没问题，保证不错过。
                    if e.last_reminded_time is None:
                        should_remind = True
                    elif e.last_reminded_time < trig_dt:
                        should_remind = True
                
                if should_remind:
                    origin_event = self.dm.get_event(e.id)
                    if origin_event:
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
            
        # === 修复逻辑 ===
        if e.repeat_rule != "无":
            # 如果是重复事件，不要修改母体。
            # 策略：创建一个临时的、一次性的“影子”事件专门用于提醒
            from copy import deepcopy
            snooze_event = deepcopy(e)
            snooze_event.id = 0 # 让 DataManager 分配新 ID
            snooze_event.uid = None # 生成新 UID
            snooze_event.title = f"{e.title} (稍后提醒)"
            snooze_event.repeat_rule = "无"
            snooze_event.reminder_enabled = True
            snooze_event.reminder_type = "absolute"
            
            # 设置绝对触发时间
            trigger_time = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=int(minutes))
            snooze_event.absolute_time = trigger_time
            
            # 为了不污染日历视图，我们可以设置一个特殊标记，或者就在日历上显示也没关系
            # 这里简单处理：作为普通事件插入，但你可以给它加个特殊 tag 让它不在日历显示
            # 为简单起见，直接作为新事件插入：
            self.dm.add_event(snooze_event)
            
            # 更新原事件的 last_reminded_time 防止再次触发（针对本次）
            e.last_reminded_time = datetime.now()
            self.dm.update_event(e)
            
        else:
            # 非重复事件，保持原有逻辑
            e.reminder_enabled = True
            e.reminder_type = "absolute"
            e.absolute_time = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=int(minutes))
            e.last_reminded_time = None 
            self.dm.update_event(e)