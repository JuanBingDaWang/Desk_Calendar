import json
import os
import uuid
from datetime import datetime, timedelta, date, timezone
from typing import Any, Dict, List, Optional, Union
from icalendar import Calendar, Event as ICalEvent, vDatetime, vText

DEFAULT_VERSION = "1.1"
PRIORITY_MAP = {"高": 0, "中": 1, "低": 2}

def _default_settings() -> Dict[str, Any]:
    return {
        "window": {"x": 100, "y": 100, "w": 900, "h": 680},
        "opacity": 0.95,
        "bg_color": "#ffffff",
        "font_color": "#000000",
        "weeks": 4,
        "cell_width": 140,
        "cell_height": 110,
        "row_gap": 6,
        "col_gap": 6,
        "locked": False,
        "font_size": 12,
    }

class Event:
    """领域模型；数据层专用。统一使用对象传递，不再混用字典。"""

    def __init__(
        self,
        id_: int,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        priority: str = "中",
        repeat_rule: str = "无",
        reminder_enabled: bool = False,
        reminder_type: str = "advance",
        advance_value: int = 30,
        advance_unit: str = "minutes",
        absolute_time: Optional[datetime] = None,
        finished: bool = False,
        # 新增：记录最后一次提醒的具体时间，用于解决重复日程提醒失效问题
        last_reminded_time: Optional[datetime] = None,
        uid: Optional[str] = None
    ):
        self.id = id_
        # 用于 ICS 同步的唯一标识符，与内部 ID 分离
        self.uid = uid if uid else str(uuid.uuid4())
        self.title = title
        self.start_time = start_time
        self.end_time = end_time
        self.description = description
        self.priority = priority
        self.repeat_rule = repeat_rule
        self.reminder_enabled = reminder_enabled
        self.reminder_type = reminder_type
        self.advance_value = advance_value
        self.advance_unit = advance_unit
        self.absolute_time = absolute_time
        self.finished = finished
        self.last_reminded_time = last_reminded_time

    @staticmethod
    def _parse_dt(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str: return None
        try: return datetime.fromisoformat(dt_str)
        except ValueError: return None

    @staticmethod
    def _format_dt(dt: Optional[datetime]) -> str:
        if not dt: return ""
        return dt.isoformat(sep='T', timespec='minutes')

    @staticmethod
    def dt_from_iso(dt_str: Optional[str]) -> Optional[datetime]:
        return Event._parse_dt(dt_str)

    def update_from_payload(self, payload: Dict[str, Any]):
        """从 UI 表单数据更新对象状态"""
        new_start_time = self.dt_from_iso(payload.get("start_time"))
        
        # 如果开始时间改变，重置提醒状态
        if new_start_time and new_start_time != self.start_time:
            self.last_reminded_time = None

        self.title = payload.get("title", self.title)
        self.start_time = new_start_time or self.start_time
        self.end_time = self.dt_from_iso(payload.get("end_time")) or self.end_time
        self.description = payload.get("description", self.description)
        self.priority = payload.get("priority", self.priority)
        self.repeat_rule = payload.get("repeat_rule", self.repeat_rule)
        self.finished = payload.get("finished", self.finished)
        
        rem = payload.get("reminder", {})
        new_enabled = rem.get("enabled", self.reminder_enabled)
        
        # 如果从关闭变为开启，重置提醒
        if new_enabled and not self.reminder_enabled:
            self.last_reminded_time = None
            
        self.reminder_enabled = new_enabled
        self.reminder_type = rem.get("type", self.reminder_type)
        self.advance_value = rem.get("advance_value", self.advance_value)
        self.advance_unit = rem.get("advance_unit", self.advance_unit)
        self.absolute_time = self.dt_from_iso(rem.get("absolute_time"))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        # 兼容旧版本数据：如果没有 last_reminded_time，尝试读取 reminded bool
        lrt = cls._parse_dt(data.get("last_reminded_time"))
        if not lrt and data.get("reminded") is True:
             # 旧数据迁移：如果是已提醒，暂时设为很久以前，避免重复弹
             lrt = datetime.min 

        return cls(
            id_=int(data.get("id", 0)), 
            uid=data.get("uid"),
            title=data.get("title", ""),
            start_time=cls._parse_dt(data.get("start_time")),
            end_time=cls._parse_dt(data.get("end_time")),
            description=data.get("description", ""),
            priority=data.get("priority", "中"),
            repeat_rule=data.get("repeat_rule", "无"),
            reminder_enabled=data.get("reminder", {}).get("enabled", False),
            reminder_type=data.get("reminder", {}).get("type", "advance"),
            advance_value=data.get("reminder", {}).get("advance_value", 30),
            advance_unit=data.get("reminder", {}).get("advance_unit", "minutes"),
            absolute_time=cls._parse_dt(data.get("reminder", {}).get("absolute_time")),
            finished=data.get("finished", False),
            last_reminded_time=lrt
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "uid": self.uid,
            "title": self.title,
            "start_time": self._format_dt(self.start_time),
            "end_time": self._format_dt(self.end_time),
            "description": self.description,
            "priority": self.priority,
            "repeat_rule": self.repeat_rule,
            "finished": self.finished,
            "last_reminded_time": self._format_dt(self.last_reminded_time),
            "reminder": {
                "enabled": self.reminder_enabled,
                "type": self.reminder_type,
                "advance_value": self.advance_value,
                "advance_unit": self.advance_unit,
                "absolute_time": self._format_dt(self.absolute_time),
            },
        }

    @classmethod
    def from_ical_component(cls, comp: ICalEvent, internal_id: int) -> Optional['Event']:
        try:
            uid = str(comp.get('uid', ''))
            dtstart_ical = comp.get('dtstart').dt
            dtend_ical = comp.get('dtend').dt
            
            # 时区处理
            start_time = dtstart_ical.astimezone(timezone.utc).replace(tzinfo=None) if hasattr(dtstart_ical, 'tzinfo') and dtstart_ical.tzinfo else dtstart_ical
            end_time = dtend_ical.astimezone(timezone.utc).replace(tzinfo=None) if hasattr(dtend_ical, 'tzinfo') and dtend_ical.tzinfo else dtend_ical
            
            # 如果是 date 类型（全天事件），转为 datetime
            if type(start_time) is date:
                start_time = datetime(start_time.year, start_time.month, start_time.day)
            if type(end_time) is date:
                end_time = datetime(end_time.year, end_time.month, end_time.day)

            title = str(comp.get('summary', ''))
            description = str(comp.get('description', ''))
            
            repeat_rule = "无"
            rrule_comp = comp.get('rrule')
            if rrule_comp:
                rrule_dict = dict(rrule_comp)
                freq = rrule_dict.get('freq', [None])[0]
                if freq == 'DAILY': repeat_rule = "每日"
                elif freq == 'WEEKLY': repeat_rule = "每周"
                elif freq == 'MONTHLY': repeat_rule = "每月"
                elif freq == 'YEARLY': repeat_rule = "每年"
            
            finished = True if str(comp.get('X-FINISHED')) == 'TRUE' else False
            
            # 提醒扩展属性解析
            reminder_enabled = True if str(comp.get('X-REMINDER-ENABLED')) == 'TRUE' else False
            reminder_type = str(comp.get('X-REMINDER-TYPE', 'advance'))
            advance_value = int(str(comp.get('X-REMINDER-ADV-VAL', 30)))
            advance_unit = str(comp.get('X-REMINDER-ADV-UNIT', 'minutes'))
            abs_str = str(comp.get('X-REMINDER-ABS-TIME', ''))
            absolute_time = cls._parse_dt(abs_str) if abs_str else None
            last_rem_str = str(comp.get('X-LAST-REMINDED', ''))
            last_reminded_time = cls._parse_dt(last_rem_str) if last_rem_str else None

            return cls(
                id_=internal_id, # 使用传入的内部 ID
                uid=uid,
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                priority="中",
                repeat_rule=repeat_rule,
                reminder_enabled=reminder_enabled,
                reminder_type=reminder_type,
                advance_value=advance_value,
                advance_unit=advance_unit,
                absolute_time=absolute_time,
                finished=finished,
                last_reminded_time=last_reminded_time
            )
        except Exception as e:
            print(f"Error converting iCal component: {e}")
            return None

    def to_ical_component(self) -> ICalEvent:
        ical_event = ICalEvent()
        ical_event.add('uid', self.uid)
        ical_event.add('summary', self.title)
        ical_event.add('description', self.description)
        
        ical_event.add('dtstart', vDatetime(self.start_time))
        ical_event.add('dtend', vDatetime(self.end_time))

        freq_map = {'每日': 'DAILY', '每周': 'WEEKLY', '每月': 'MONTHLY', '每年': 'YEARLY'}
        freq = freq_map.get(self.repeat_rule)
        if freq:
            rrule_str = f"FREQ={freq}"
            if freq == 'WEEKLY':
                day_map = {0:'MO', 1:'TU', 2:'WE', 3:'TH', 4:'FR', 5:'SA', 6:'SU'}
                rrule_str += f";BYDAY={day_map[self.start_time.weekday()]}"
            ical_event.add('rrule', rrule_str)
        
        ical_event.add('X-FINISHED', 'TRUE' if self.finished else 'FALSE')
        ical_event.add('X-REMINDER-ENABLED', 'TRUE' if self.reminder_enabled else 'FALSE')
        ical_event.add('X-REMINDER-TYPE', self.reminder_type)
        ical_event.add('X-REMINDER-ADV-VAL', str(self.advance_value))
        ical_event.add('X-REMINDER-ADV-UNIT', self.advance_unit)
        if self.absolute_time:
            ical_event.add('X-REMINDER-ABS-TIME', self._format_dt(self.absolute_time))
        if self.last_reminded_time:
            ical_event.add('X-LAST-REMINDED', self._format_dt(self.last_reminded_time))

        return ical_event


class DataManager:
    SETTINGS_FILE = "CalendarData.json"
    EVENTS_FILE = "Events.ics"

    def __init__(self, data_path: str):
        self._data_dir = os.path.dirname(data_path)
        self._settings_path = data_path
        self._events_path = os.path.join(self._data_dir, self.EVENTS_FILE)

        self.data: Dict[str, Any] = self.load_data()
        self._recalculate_next_id()
    
    def _recalculate_next_id(self):
        max_id = 0
        for e in self.get_all_events():
             if e.id > max_id:
                max_id = e.id
        self._next_event_id = max_id + 1

    def load_data(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "version": DEFAULT_VERSION,
            "settings": _default_settings(),
            "global_memo": "",
            "events": []
        }
        
        # 1. Load JSON (Settings)
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    data["version"] = raw_data.get("version", DEFAULT_VERSION)
                    for k, v in raw_data.get("settings", {}).items():
                        if k in data["settings"]:
                            data["settings"][k] = v
                    data["global_memo"] = raw_data.get("global_memo", "")
            except json.JSONDecodeError:
                print(f"Warning: {self._settings_path} is corrupted. Using default settings.")
        
        # 2. Load ICS (Events)
        events: List[Event] = self._load_events_from_ics()
        data["events"] = events 
        return data

    def save_data(self, save_settings_only: bool = False) -> bool:
        settings_data = {
            "version": DEFAULT_VERSION,
            "settings": self.data["settings"],
            "global_memo": self.data["global_memo"],
            "events": [] # Events stored in ICS
        }
        try:
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings to JSON: {e}")
            return False

        if not save_settings_only:
            return self._save_events_to_ics(self.data["events"])
        return True

    def _load_events_from_ics(self) -> List[Event]:
        if not os.path.exists(self._events_path):
            return []
        events: List[Event] = []
        try:
            with open(self._events_path, "r", encoding="utf-8") as f:
                cal = Calendar.from_ical(f.read())
            
            # 临时 ID 计数器，用于加载时给每个事件分配唯一的内部 INT ID
            # 实际应用中可以维护一个 UID->INT 映射表，这里简化处理
            temp_id = 1 
            for component in cal.walk('vevent'):
                e = Event.from_ical_component(component, temp_id)
                if e:
                    events.append(e)
                    temp_id += 1
            return events
        except Exception as e:
            print(f"Error loading events from ICS: {e}")
            return []

    def _save_events_to_ics(self, events: List[Event]) -> bool:
        try:
            cal = Calendar()
            cal.add('prodid', '-//My Calendar App//NONSGML v1.1//EN')
            cal.add('version', '2.0')
            for e in events:
                ical_event = e.to_ical_component()
                cal.add_component(ical_event)
            with open(self._events_path, "wb") as f: 
                f.write(cal.to_ical())
            return True
        except Exception as e:
            print(f"Error saving events to ICS: {e}")
            return False

    def add_event(self, e: Event) -> int:
        e.id = self._next_event_id
        self._next_event_id += 1
        self.data["events"].append(e)
        self._save_events_to_ics(self.data["events"])
        return e.id

    def update_event(self, e: Event) -> bool:
        for i, existing_event in enumerate(self.data["events"]):
            if existing_event.id == e.id:
                self.data["events"][i] = e
                self._save_events_to_ics(self.data["events"])
                return True
        return False
    
    def mark_event_as_finished(self, event_id: int, is_finished: bool) -> bool:
        e = self.get_event(event_id)
        if e:
            e.finished = is_finished
            return self.update_event(e)
        return False

    def delete_event(self, event_id: int) -> bool:
        original_count = len(self.data["events"])
        self.data["events"] = [e for e in self.data["events"] if e.id != event_id]
        if len(self.data["events"]) < original_count:
            self._save_events_to_ics(self.data["events"])
            return True
        return False
        
    def save_global_memo(self, memo: str) -> bool:
        self.data["global_memo"] = memo
        return self.save_data(save_settings_only=True)
    
    def get_all_events(self) -> List[Event]:
        return self.data["events"]

    def get_event(self, event_id: int) -> Optional[Event]:
        for e in self.data["events"]:
            if e.id == event_id:
                return e
        return None

    def _is_occurring_on(self, event: Event, target: date, start: date) -> bool:
        if target < start:
            return False
        rule = event.repeat_rule
        if rule == "无":
            return target == start
        elif rule == "每日":
            return True
        elif rule == "每周":
            return target.weekday() == start.weekday()
        elif rule == "每月":
            return target.day == start.day
        elif rule == "每年":
            return target.month == start.month and target.day == start.day
        return False

    def list_events_by_date(self, date_str: str) -> List[Event]:
        """保留以兼容旧代码，但建议使用批量获取"""
        try:
            target_date = datetime.fromisoformat(f"{date_str}T00:00:00").date()
        except ValueError:
            return []
        
        # 简单封装批量查询
        return self.get_events_between_dates(target_date, target_date).get(date_str, [])

    def get_events_between_dates(self, start_date: date, end_date: date) -> Dict[str, List[Event]]:
        """
        高性能批量查询：一次性计算日期范围内所有事件的分布。
        返回字典: { 'yyyy-mm-dd': [Event, Event...], ... }
        """
        result: Dict[str, List[Event]] = {}
        
        # 初始化字典的所有 Key，确保没有事件的那天也是空列表
        curr = start_date
        while curr <= end_date:
            result[curr.strftime("%Y-%m-%d")] = []
            curr += timedelta(days=1)

        for e in self.data["events"]:
            e_start_date = e.start_time.date()
            
            # 如果事件开始时间晚于查询结束时间，直接跳过
            if e_start_date > end_date:
                continue

            # 处理不重复事件
            if e.repeat_rule == "无":
                date_key = e_start_date.strftime("%Y-%m-%d")
                if date_key in result:
                    result[date_key].append(e)
                continue

            # 处理重复事件
            # 优化：只遍历查询范围内的时间
            # 计算首次可能发生的时间点，避免从 e.start_time 开始无效遍历
            check_date = start_date if start_date > e_start_date else e_start_date
            
            while check_date <= end_date:
                if self._is_occurring_on(e, check_date, e_start_date):
                    date_key = check_date.strftime("%Y-%m-%d")
                    
                    # 创建虚拟事件对象，调整时间
                    if check_date != e_start_date:
                        virtual_e = Event.from_dict(e.to_dict())
                        # 重新赋予内部 ID，保证 UI 操作（如完成）能找到原件
                        # 注意：如果要在视图里修改重复事项的某一天，需要更复杂的逻辑，目前仅支持修改源头
                        virtual_e.id = e.id 
                        
                        days_diff = (check_date - e_start_date).days
                        time_delta = timedelta(days=days_diff)
                        virtual_e.start_time += time_delta
                        virtual_e.end_time += time_delta
                        result[date_key].append(virtual_e)
                    else:
                        result[date_key].append(e)
                
                check_date += timedelta(days=1)

        # 排序
        for date_key in result:
            result[date_key].sort(key=lambda x: (PRIORITY_MAP.get(x.priority, 1), x.start_time))
            
        return result

    def get_settings(self) -> Dict[str, Any]:
        return self.data["settings"]

    def save_settings(self, **kwargs) -> bool:
        self.data["settings"].update(kwargs)
        return self.save_data(save_settings_only=True)

    def update_settings(self, new_settings: Dict[str, Any]) -> bool:
        self.data["settings"].update(new_settings)
        return self.save_data(save_settings_only=True)
        
    def get_global_memo(self) -> str:
        return self.data.get("global_memo", "")