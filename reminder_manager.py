from PyQt5.QtCore import QObject, QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import QSystemTrayIcon, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
from datetime import datetime, timedelta
from typing import Optional
from copy import deepcopy
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
            
        target_start = e.start_time
        
        # 处理重复日程的基准时间偏移
        if e.repeat_rule != "无":
            # 简化逻辑：仅考虑当天发生的重复事件
            # 实际逻辑应调用 DataManager._is_occurring_on 并构造当天的 datetime
            today = current_time.date()
            if self.dm._is_occurring_on(e, today, e.start_time.date()):
                # 将时间替换为今天
                target_start = datetime.combine(today, e.start_time.time())
            else:
                return None
        
        if e.reminder_type == 'absolute':
            return e.absolute_time
        else:
            # advance
            delta = timedelta(minutes=0)
            if e.advance_unit == 'minutes': delta = timedelta(minutes=e.advance_value)
            elif e.advance_unit == 'hours': delta = timedelta(hours=e.advance_value)
            elif e.advance_unit == 'days': delta = timedelta(days=e.advance_value)
            return target_start - delta

    def check_reminders(self):
        now = datetime.now()
        
        # 1. 检查日期变更（用于刷新 CalendarView 的“今天”高亮等）
        if now.date() != self._current_date:
            self._current_date = now.date()
            self.dateChanged.emit()
            
        # 2. 扫描事件
        # 为了性能，可以只扫描“今天”和“明天”的事件，或者 SQLite 优化查询
        # 这里简单遍历所有事件（缓存），对于大数据量需优化
        for e in self.dm.get_all_events():
            if e.finished: continue
            if not e.reminder_enabled: continue
            
            trigger_dt = self._calc_trigger_dt(e, now)
            if not trigger_dt: continue
            
            # 判断是否触发：时间到了，且上次没提醒过（或上次提醒是很久以前）
            # 容差：过去 1 分钟内
            diff = (now - trigger_dt).total_seconds()
            if 0 <= diff < 65:
                # 检查 last_reminded_time
                # 如果是重复事件，last_reminded_time 应该是“针对本次的提醒时间”
                # 这里简单判定：如果 last_reminded_time 离现在很近，说明刚提醒过
                if e.last_reminded_time:
                    seconds_since_last = (now - e.last_reminded_time).total_seconds()
                    if seconds_since_last < 120: # 2分钟内不重复提醒
                        continue
                
                # 触发
                self.reminderTriggered.emit(e)

    def snooze(self, event_id: int, minutes: int) -> None:
        e = self.dm.get_event(int(event_id))
        if not e:
            return
            
        # 如果是重复事件，不要修改母体。
        # 策略：创建一个临时的、一次性的“影子”事件专门用于提醒
        # 或者如果是普通事件，直接修改 absolute_time？
        # 为了代码简单，我们采用“修改原事件的提醒设置”策略，但如果是重复事件，这会有副作用。
        # 最稳妥的方式：新建一个临时事件。
        
        if e.repeat_rule != "无":
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
            
            self.dm.add_event(snooze_event)
            
            # 更新原事件的 last_reminded_time 防止再次触发（针对本次）
            e.last_reminded_time = datetime.now()
            self.dm.update_event(e)
            
        else:
            # 非重复事件，直接修改为绝对提醒
            e.reminder_type = "absolute"
            e.absolute_time = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=int(minutes))
            # 重置 last_reminded_time 以便 check_reminders 再次捕获
            e.last_reminded_time = None 
            self.dm.update_event(e)

    @staticmethod
    def show_notification(tray_icon: QSystemTrayIcon, event: Event) -> QDialog:
        # 播放声音或气泡（可选）
        if tray_icon:
            tray_icon.showMessage(
                "日程提醒", 
                f"{event.title} 即将开始", 
                QSystemTrayIcon.Information, 
                3000
            )
        
        QApplication.beep() # 播放系统提示音
        
        # 创建弹窗
        dialog = QDialog()
        dialog.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        dialog.setWindowTitle("日程提醒")
        dialog.setFixedSize(350, 200)
        
        # --- 修改：强制黑色文字，避免受主程序样式影响 ---
        dialog.setStyleSheet("color: #000000; background-color: #ffffff;")

        layout = QVBoxLayout(dialog)
        
        title_label = QLabel(f"<h3>{event.title}</h3>")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        time_str = event.start_time.strftime("%Y-%m-%d %H:%M")
        time_label = QLabel(f"开始时间: {time_str}")
        time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(time_label)
        
        if event.description:
            desc_label = QLabel(f"备注: {event.description}")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
            
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        snooze_btn = QPushButton("稍后提醒")
        snooze_btn.setObjectName("snoozeButton") # 用于 main.py 绑定事件
        
        ok_btn = QPushButton("知道了")
        ok_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(snooze_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        # 绑定数据供 main.py 使用
        dialog.event_data = event
        
        return dialog