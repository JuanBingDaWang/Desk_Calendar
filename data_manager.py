import json
import os
import uuid
import sqlite3
import shutil
from datetime import datetime, timedelta, date, timezone
from typing import Any, Dict, List, Optional, Union
from icalendar import Calendar, Event as ICalEvent, vDatetime, vText

DEFAULT_VERSION = "1.2" # 版本号升级
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
        "storage_mode": "ics" # 新增：ics 或 sqlite
    }

class Event:
    """领域模型；数据层专用。"""

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
        last_reminded_time: Optional[datetime] = None,
        uid: Optional[str] = None
    ):
        self.id = id_
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
    def _format_dt(dt: Optional[datetime]) -> Optional[str]:
        if not dt: return None # SQLite 存 NULL 比较好
        return dt.isoformat(sep='T', timespec='minutes')

    @staticmethod
    def dt_from_iso(dt_str: Optional[str]) -> Optional[datetime]:
        return Event._parse_dt(dt_str)

    def update_from_payload(self, payload: Dict[str, Any]):
        new_start_time = self.dt_from_iso(payload.get("start_time"))
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
        
        if new_enabled and not self.reminder_enabled:
            self.last_reminded_time = None
            
        self.reminder_enabled = new_enabled
        self.reminder_type = rem.get("type", self.reminder_type)
        self.advance_value = rem.get("advance_value", self.advance_value)
        self.advance_unit = rem.get("advance_unit", self.advance_unit)
        self.absolute_time = self.dt_from_iso(rem.get("absolute_time"))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        lrt = cls._parse_dt(data.get("last_reminded_time"))
        if not lrt and data.get("reminded") is True:
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
            
            start_time = dtstart_ical.astimezone(timezone.utc).replace(tzinfo=None) if hasattr(dtstart_ical, 'tzinfo') and dtstart_ical.tzinfo else dtstart_ical
            end_time = dtend_ical.astimezone(timezone.utc).replace(tzinfo=None) if hasattr(dtend_ical, 'tzinfo') and dtend_ical.tzinfo else dtend_ical
            
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
            
            reminder_enabled = True if str(comp.get('X-REMINDER-ENABLED')) == 'TRUE' else False
            reminder_type = str(comp.get('X-REMINDER-TYPE', 'advance'))
            advance_value = int(str(comp.get('X-REMINDER-ADV-VAL', 30)))
            advance_unit = str(comp.get('X-REMINDER-ADV-UNIT', 'minutes'))
            abs_str = str(comp.get('X-REMINDER-ABS-TIME', ''))
            absolute_time = cls._parse_dt(abs_str) if abs_str else None
            last_rem_str = str(comp.get('X-LAST-REMINDED', ''))
            last_reminded_time = cls._parse_dt(last_rem_str) if last_rem_str else None

            return cls(
                id_=internal_id, 
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
    EVENTS_FILE_ICS = "Events.ics"
    EVENTS_FILE_DB = "Events.db"

    def __init__(self, data_path: str):
        self._data_dir = os.path.dirname(data_path)
        self._settings_path = data_path
        self._ics_path = os.path.join(self._data_dir, self.EVENTS_FILE_ICS)
        self._db_path = os.path.join(self._data_dir, self.EVENTS_FILE_DB)

        # 1. 先加载配置
        self.data: Dict[str, Any] = self._load_settings_only()
        
        # 2. 检查存储模式
        self.storage_mode = self.data["settings"].get("storage_mode", "ics")
        
        # 3. 初始化 DB（如果需要）
        self._init_db_schema()

        # 4. 加载事件数据
        self.events_cache: List[Event] = [] # 内存缓存，如果是 SQLite 模式，用于部分逻辑
        self.reload_events()
        self._recalculate_next_id()
    
    def _init_db_schema(self):
        """初始化 SQLite 表结构"""
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            title TEXT,
            start_time TEXT,
            end_time TEXT,
            description TEXT,
            priority TEXT,
            repeat_rule TEXT,
            reminder_enabled INTEGER,
            reminder_type TEXT,
            advance_value INTEGER,
            advance_unit TEXT,
            absolute_time TEXT,
            finished INTEGER,
            last_reminded_time TEXT
        )''')
        conn.commit()
        conn.close()

    def _load_settings_only(self) -> Dict[str, Any]:
        data = {
            "version": DEFAULT_VERSION,
            "settings": _default_settings(),
            "global_memo": "",
            "events": [] # 占位
        }
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    data["version"] = raw_data.get("version", DEFAULT_VERSION)
                    for k, v in raw_data.get("settings", {}).items():
                        data["settings"][k] = v
                    data["global_memo"] = raw_data.get("global_memo", "")
            except Exception:
                pass
        return data

    def reload_events(self):
        """根据当前模式加载数据"""
        if self.storage_mode == "sqlite":
            self.events_cache = self._load_events_from_db()
        else:
            self.events_cache = self._load_events_from_ics()
        # 确保 self.data['events'] 指向缓存，虽然主要操作已不再依赖它，但为了兼容旧引用
        self.data["events"] = self.events_cache

    def _recalculate_next_id(self):
        if self.storage_mode == "sqlite":
            # SQLite 自增ID，不需要手动计算，但为了兼容，取最大值
             conn = sqlite3.connect(self._db_path)
             c = conn.cursor()
             c.execute("SELECT MAX(id) FROM events")
             val = c.fetchone()[0]
             conn.close()
             self._next_event_id = (val or 0) + 1
        else:
            max_id = 0
            for e in self.events_cache:
                if e.id > max_id:
                    max_id = e.id
            self._next_event_id = max_id + 1

    def save_data(self, save_settings_only: bool = False) -> bool:
        """保存设置，如果是 ICS 模式也保存事件"""
        settings_data = {
            "version": DEFAULT_VERSION,
            "settings": self.data["settings"],
            "global_memo": self.data["global_memo"],
            "events": [] 
        }
        try:
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

        if not save_settings_only:
            if self.storage_mode == "ics":
                return self._save_events_to_ics(self.events_cache)
            # SQLite 在修改时即时保存，不需要整体 save
        return True

    # --- ICS Operations ---
    def _load_events_from_ics(self) -> List[Event]:
        if not os.path.exists(self._ics_path):
            return []
        events: List[Event] = []
        try:
            with open(self._ics_path, "r", encoding="utf-8") as f:
                cal = Calendar.from_ical(f.read())
            temp_id = 1 
            for component in cal.walk('vevent'):
                e = Event.from_ical_component(component, temp_id)
                if e:
                    events.append(e)
                    temp_id += 1
            return events
        except Exception as e:
            print(f"Error loading ICS: {e}")
            return []

    def _save_events_to_ics(self, events: List[Event], path: str = None) -> bool:
        target_path = path if path else self._ics_path
        try:
            cal = Calendar()
            cal.add('prodid', '-//My Calendar App//NONSGML v1.2//EN')
            cal.add('version', '2.0')
            for e in events:
                ical_event = e.to_ical_component()
                cal.add_component(ical_event)
            with open(target_path, "wb") as f: 
                f.write(cal.to_ical())
            return True
        except Exception as e:
            print(f"Error saving ICS: {e}")
            return False

    # --- SQLite Operations ---
    def _event_to_tuple(self, e: Event) -> tuple:
        return (
            e.uid, e.title, 
            Event._format_dt(e.start_time), Event._format_dt(e.end_time),
            e.description, e.priority, e.repeat_rule,
            1 if e.reminder_enabled else 0, e.reminder_type,
            e.advance_value, e.advance_unit,
            Event._format_dt(e.absolute_time),
            1 if e.finished else 0,
            Event._format_dt(e.last_reminded_time)
        )
    
    def _row_to_event(self, row) -> Event:
        # row: (id, uid, title, start, end, desc, pri, rule, rem_en, rem_type, val, unit, abs, fin, last_rem)
        return Event(
            id_=row[0],
            uid=row[1],
            title=row[2],
            start_time=Event._parse_dt(row[3]),
            end_time=Event._parse_dt(row[4]),
            description=row[5],
            priority=row[6],
            repeat_rule=row[7],
            reminder_enabled=bool(row[8]),
            reminder_type=row[9],
            advance_value=row[10],
            advance_unit=row[11],
            absolute_time=Event._parse_dt(row[12]),
            finished=bool(row[13]),
            last_reminded_time=Event._parse_dt(row[14])
        )

    def _load_events_from_db(self) -> List[Event]:
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM events")
        rows = c.fetchall()
        events = [self._row_to_event(r) for r in rows]
        conn.close()
        return events

    def _insert_event_db(self, e: Event) -> int:
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        params = self._event_to_tuple(e)
        c.execute('''INSERT INTO events (
            uid, title, start_time, end_time, description, priority, repeat_rule,
            reminder_enabled, reminder_type, advance_value, advance_unit, absolute_time,
            finished, last_reminded_time
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', params)
        new_id = c.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def _update_event_db(self, e: Event) -> bool:
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        params = self._event_to_tuple(e) + (e.id,)
        c.execute('''UPDATE events SET
            uid=?, title=?, start_time=?, end_time=?, description=?, priority=?, repeat_rule=?,
            reminder_enabled=?, reminder_type=?, advance_value=?, advance_unit=?, absolute_time=?,
            finished=?, last_reminded_time=?
            WHERE id=?''', params)
        conn.commit()
        conn.close()
        return True

    def _delete_event_db(self, event_id: int) -> bool:
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()
        conn.close()
        return True

    # --- Mode Switching & Export ---
    def switch_storage_mode(self, new_mode: str) -> bool:
        if new_mode == self.storage_mode:
            return True
        
        # 1. 迁移数据
        events_to_migrate = self.get_all_events() # 当前内存中的数据
        
        if new_mode == "sqlite":
            # ICS -> SQLite
            # 清空旧表(可选)或合并。这里选择清空重建以保证完全一致
            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            c.execute("DELETE FROM events") 
            conn.commit()
            conn.close()
            for e in events_to_migrate:
                self._insert_event_db(e)
                
        elif new_mode == "ics":
            # SQLite -> ICS
            self._save_events_to_ics(events_to_migrate)

        # 2. 更新设置
        self.storage_mode = new_mode
        self.data["settings"]["storage_mode"] = new_mode
        self.save_settings()
        
        # 3. 重新加载
        self.reload_events()
        return True

    def export_data_to_ics(self, target_path: str) -> bool:
        """导出当前数据到指定 ICS 文件"""
        events = self.get_all_events()
        return self._save_events_to_ics(events, target_path)

    def add_event(self, e: Event, auto_save: bool = True) -> int:
        if self.storage_mode == "sqlite":
            new_id = self._insert_event_db(e)
            e.id = new_id
            self.events_cache.append(e)
            return new_id
        else:
            e.id = self._next_event_id
            self._next_event_id += 1
            self.events_cache.append(e)
            # 只有当 auto_save 为 True 时才写入文件
            if auto_save:
                self._save_events_to_ics(self.events_cache) 
            return e.id

    def update_event(self, e: Event) -> bool:
        # 更新缓存中的对象
        found = False
        for i, existing in enumerate(self.events_cache):
            if existing.id == e.id:
                self.events_cache[i] = e
                found = True
                break
        
        if self.storage_mode == "sqlite":
            return self._update_event_db(e)
        else:
            if found:
                self._save_events_to_ics(self.events_cache)
                return True
        return False

    def mark_event_as_finished(self, event_id: int, is_finished: bool) -> bool:
        e = self.get_event(event_id)
        if e:
            e.finished = is_finished
            return self.update_event(e)
        return False

    def delete_event(self, event_id: int) -> bool:
        self.events_cache = [e for e in self.events_cache if e.id != event_id]
        self.data["events"] = self.events_cache # Update reference
        
        if self.storage_mode == "sqlite":
            return self._delete_event_db(event_id)
        else:
            return self._save_events_to_ics(self.events_cache)

    def get_all_events(self) -> List[Event]:
        # 直接返回缓存即可，因为缓存始终保持同步
        return self.events_cache

    def get_event(self, event_id: int) -> Optional[Event]:
        for e in self.events_cache:
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
        try:
            target_date = datetime.fromisoformat(f"{date_str}T00:00:00").date()
        except ValueError:
            return []
        return self.get_events_between_dates(target_date, target_date).get(date_str, [])

    def get_events_between_dates(self, start_date: date, end_date: date) -> Dict[str, List[Event]]:
        """
        获取日期范围内的事件。
        SQLite 优化策略：
        1. 查出所有重复规则 != '无' 的事件 (确保久远的重复事件能被计算到)
        2. 查出 start_time 在查询范围内的单次事件 (正常日程)
        3. 查出 absolute_time 在查询范围内的事件 (确保跨天/跨年的绝对提醒能触发)
        """
        result: Dict[str, List[Event]] = {}
        curr = start_date
        while curr <= end_date:
            result[curr.strftime("%Y-%m-%d")] = []
            curr += timedelta(days=1)

        source_events = []
        if self.storage_mode == "sqlite":
            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            
            # 构造查询时间范围字符串 (ISO格式)
            s_str = f"{start_date.isoformat()}T00:00"
            e_str = f"{end_date.isoformat()}T23:59"
            
            # SQL 逻辑：
            # 1. 只要是重复事件，必须取出计算 (repeat_rule != '无')
            # 2. 或者：开始时间在查询范围内
            # 3. 或者：设置了绝对提醒，且绝对提醒的时间在查询范围内 (关键优化！)
            c.execute("""
                SELECT * FROM events 
                WHERE repeat_rule != '无' 
                OR (start_time >= ? AND start_time <= ?)
                OR (reminder_type = 'absolute' AND absolute_time >= ? AND absolute_time <= ?)
            """, (s_str, e_str, s_str, e_str))
            
            rows = c.fetchall()
            source_events = [self._row_to_event(r) for r in rows]
            conn.close()
        else:
            source_events = self.events_cache

        # --- 以下逻辑保持不变 ---
        for e in source_events:
            e_start_date = e.start_time.date()
            
            # 处理不重复事件
            if e.repeat_rule == "无":
                # 判定1：日程本身在范围内
                is_in_range = start_date <= e_start_date <= end_date
                
                # 判定2：绝对提醒在范围内（即使用户只在提醒那天打开软件，没看日程那天，也能加载出来）
                is_rem_in_range = False
                if e.reminder_type == 'absolute' and e.absolute_time:
                    rem_date = e.absolute_time.date()
                    if start_date <= rem_date <= end_date:
                        is_rem_in_range = True
                
                # 只有当 日程在范围内 或 提醒在范围内 时才放入结果
                # 注意：result 的 key 是日期，我们通常把事件挂载在它发生的日期
                # 如果是纯粹为了提醒被加载进来（本身不在今天），它需要被挂载在“今天”这个 key 下吗？
                # ReminderManager 遍历的是 list_events_by_date(today)。
                # 所以，如果今天是提醒日但不是日程日，我们需要把它算作“今天的数据”以便 ReminderManager 扫描到。
                
                if is_in_range:
                    date_key = e_start_date.strftime("%Y-%m-%d")
                    if date_key in result:
                        result[date_key].append(e)
                
                if is_rem_in_range and not is_in_range:
                    # 特殊情况：日程不在今天，但提醒在今天。
                    # 为了让 check_reminders 能扫描到它，我们将它临时放入提醒日的列表中
                    rem_date_key = e.absolute_time.date().strftime("%Y-%m-%d")
                    if rem_date_key in result:
                        # 避免重复添加（如果提醒日 == 日程日，上面已经加过了）
                        # 只有当它们不同天时才执行
                        if e not in result[rem_date_key]:
                            result[rem_date_key].append(e)
                continue

            # 重复事件处理 (保持原样)
            if e_start_date > end_date: continue
            
            check_date = start_date if start_date > e_start_date else e_start_date
            while check_date <= end_date:
                if self._is_occurring_on(e, check_date, e_start_date):
                    date_key = check_date.strftime("%Y-%m-%d")
                    if check_date != e_start_date:
                        virtual_e = Event.from_dict(e.to_dict())
                        virtual_e.id = e.id 
                        days_diff = (check_date - e_start_date).days
                        time_delta = timedelta(days=days_diff)
                        virtual_e.start_time += time_delta
                        virtual_e.end_time += time_delta
                        result[date_key].append(virtual_e)
                    else:
                        result[date_key].append(e)
                check_date += timedelta(days=1)

        for date_key in result:
            result[date_key].sort(key=lambda x: (PRIORITY_MAP.get(x.priority, 1), x.start_time))
            
        return result

    def get_settings(self) -> Dict[str, Any]:
        return self.data["settings"]

    def save_settings(self, **kwargs) -> bool:
        self.data["settings"].update(kwargs)
        return self.save_data(save_settings_only=True)
        
    def get_global_memo(self) -> str:
        return self.data.get("global_memo", "")

    def save_global_memo(self, memo: str) -> bool:
        self.data["global_memo"] = memo
        return self.save_data(save_settings_only=True)

    def import_from_ics(self, file_path: str) -> int:
        if not os.path.exists(file_path):
            return 0
        
        count = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                if not file_content.strip():
                    return 0
                cal = Calendar.from_ical(file_content)
            
            existing_uids = {evt.uid for evt in self.events_cache}
            for component in cal.walk('vevent'):
                e = Event.from_ical_component(component, internal_id=0)
                if e:
                    if e.uid in existing_uids:
                        continue # 跳过已存在的事件
                    self.add_event(e, auto_save=False)
                    count += 1
                    existing_uids.add(e.uid)
            
            # 循环结束后，统一保存一次
            if self.storage_mode == "ics":
                self._save_events_to_ics(self.events_cache)
            
            # 注意：SQLite 模式目前是逐条插入，虽然有一点慢但比 ICS 重写文件快得多，
            # 如果想极致优化 SQLite 导入，可以后续重构，但目前这样对于几千条数据是可以接受的。
            
            return count
        except Exception as e:
            print(f"Import error: {e}")
            return 0