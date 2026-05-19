from __future__ import annotations

import csv
import json
import re
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except ImportError:  # Pillow is optional at runtime, but recommended for clean logo resizing.
    Image = None
    ImageTk = None

try:
    import mysql.connector as mysql_connector
    from mysql.connector import Error as MySQLError
except ImportError:  # The GUI can still open and show setup guidance.
    mysql_connector = None
    MySQLError = Exception

try:
    import pymysql
except ImportError:
    pymysql = None

from housing_workflows import (
    approve_application_with_assignment,
    get_housing_integrity_snapshot,
    list_application_queue,
    list_assignable_rooms,
    list_available_beds,
    list_room_transfer_queue,
    reconcile_housing_data,
)
from system_workflows import (
    complete_room_transfer,
    get_system_integrity_snapshot,
    reconcile_operational_data,
)


APP_TITLE = "Galala Dorms Administration"
CONFIG_PATH = Path(__file__).with_name("db_config.json")
ASSET_DIR = Path(__file__).with_name("assets")
LOGO_PATH = ASSET_DIR / "galala_university_logo.png"
ROW_LIMIT = 300
FK_LIMIT = 800

DEFAULT_CONFIG = {
    "host": "localhost",
    "port": "3306",
    "user": "root",
    "password": "",
    "database": "GUDorms",
}

COLORS = {
    "bg": "#eef7f1",
    "panel": "#ffffff",
    "panel_soft": "#f7fbf8",
    "nav": "#0ca747",
    "nav_soft": "#0ca747",
    "nav_selected": "#21a363",
    "text": "#163226",
    "muted": "#64766c",
    "line": "#d5e6dc",
    "accent": "#1f9d5b",
    "accent_dark": "#12733f",
    "success": "#178a51",
    "warning": "#b66a00",
    "danger": "#bf3a30",
    "blue": "#173a8a",
    "logo_green": "#9acc68",
    "chip": "#e2f5e9",
}

FONTS = {
    "brand": ("Segoe UI", 18, "bold"),
    "h1": ("Segoe UI", 22, "bold"),
    "h2": ("Segoe UI", 14, "bold"),
    "body": ("Segoe UI", 10),
    "small": ("Segoe UI", 8),
    "metric": ("Segoe UI", 24, "bold"),
}

TABLE_GROUPS: list[tuple[str, list[str]]] = [
    (
        "Admin",
        [
            "Faculty",
            "AcademicProgram",
            "AcademicSemester",
            "Role",
            "SystemUser",
            "Announcement",
            "Notification",
            "StudentAnnouncement",
        ],
    ),
    (
        "People & Staff",
        [
            "Student",
            "EmergencyContact",
            "Staff",
            "StaffBuilding",
        ],
    ),
    (
        "Buildings & Rooms",
        [
            "Building",
            "RoomType",
            "Room",
            "BedSlot",
        ],
    ),
    (
        "Housing",
        [
            "Registration",
            "RoomAssignment",
            "OccupancyLog",
            "RoomTransfer",
            "LeavePermission",
        ],
    ),
    (
        "Maintenance & Assets",
        [
            "MaintenanceRequest",
            "MaintenanceLog",
            "RoomInspection",
            "Asset",
        ],
    ),
    (
        "Finance",
        [
            "Invoice",
            "PaymentTransaction",
            "Penalty",
            "Blacklist",
        ],
    ),
    (
        "Services",
        [
            "MealSubscription",
            "MealAttendance",
            "DormService",
            "Laundry",
            "LaundryUsage",
            "LostAndFoundItem",
        ],
    ),
    (
        "Security & Visitors",
        [
            "AccessLog",
            "Visitor",
            "VisitorPermission",
            "Complaint",
            "IncidentReport",
        ],
    ),
]

TABLE_LOOKUP = {
    table.casefold(): (group_name, table)
    for group_name, tables in TABLE_GROUPS
    for table in tables
}

DEPARTMENT_SHORTCUTS: list[tuple[str, str, str]] = [
    ("Housing", "Assignments, registrations, transfers, leave permissions", "RoomAssignment"),
    ("Finance", "Invoices, payments, penalties, blacklist records", "Invoice"),
    ("People & Staff", "Students, emergency contacts, staff, building assignments", "Student"),
    ("Maintenance & Assets", "Maintenance requests, inspections, logs, assets", "MaintenanceRequest"),
    ("Security & Visitors", "Access logs, visitors, complaints, incidents", "AccessLog"),
    ("Services", "Meals, laundry, dorm services, lost and found", "MealSubscription"),
    ("Buildings & Rooms", "Buildings, rooms, bed slots, room types", "Building"),
    ("Admin", "Faculties, semesters, users, announcements, notifications", "Faculty"),
]

TEXT_TYPES = {
    "char",
    "varchar",
    "tinytext",
    "text",
    "mediumtext",
    "longtext",
    "enum",
    "set",
    "date",
    "datetime",
    "timestamp",
    "time",
    "year",
}

DISPLAY_CANDIDATES = [
    "Name",
    "Title",
    "Subject",
    "BuildingName",
    "BuildingCode",
    "RoomNumber",
    "Code",
    "FirstName",
    "LastName",
    "Email",
    "RoleName",
    "ItemName",
    "SerialNumber",
    "Type",
    "Status",
]

REPORTING_VIEW_DESCRIPTIONS = {
    "vw_studentdirectory": "Student names with faculty and program context.",
    "vw_roomoccupancy": "Room capacity, occupancy, and available beds.",
    "vw_activemaintenancerequests": "Maintenance work still needing attention.",
    "vw_studentfinancials": "Student-level billing, paid amounts, and balances.",
    "vw_buildingcapacityoverview": "Building-wide configured capacity snapshot.",
    "vw_availablebeds": "Immediately assignable free bed slots.",
    "vw_actionableinspections": "Failed inspections or inspections needing follow-up.",
    "vw_assetinventory": "Active asset inventory across rooms and buildings.",
    "vw_expiringcontracts": "Active room assignments ending soon.",
    "vw_activeblacklist": "Currently active blacklist records.",
    "vw_dailymealsummary": "Meal attendance totals for today.",
    "vw_activeleavepermissions": "Currently active approved leave permissions.",
    "vw_monthlyrevenue": "Monthly completed-payment revenue summary.",
    "vw_maintenancekpis": "Maintenance request throughput and resolution time.",
    "vw_overdueinvoicesalert": "Invoices already past due and needing follow-up.",
}

REPORTING_VIEW_LABELS = {
    "vw_studentdirectory": "Student Directory",
    "vw_roomoccupancy": "Room Occupancy",
    "vw_activemaintenancerequests": "Active Maintenance Requests",
    "vw_studentfinancials": "Student Financials",
    "vw_buildingcapacityoverview": "Building Capacity Overview",
    "vw_availablebeds": "Available Beds",
    "vw_actionableinspections": "Actionable Inspections",
    "vw_assetinventory": "Asset Inventory",
    "vw_expiringcontracts": "Expiring Contracts",
    "vw_activeblacklist": "Active Blacklist",
    "vw_dailymealsummary": "Daily Meal Summary",
    "vw_activeleavepermissions": "Active Leave Permissions",
    "vw_monthlyrevenue": "Monthly Revenue",
    "vw_maintenancekpis": "Maintenance KPIs",
    "vw_overdueinvoicesalert": "Overdue Invoices Alert",
}

SYSTEM_TIME_COLUMNS = {
    "CreatedAt",
    "UpdatedAt",
    "SubmittedAt",
    "ReportedAt",
    "LoggedAt",
    "ResolvedAt",
    "ClosedAt",
    "ReadAt",
}
SYSTEM_TIME_COLUMN_KEYS = {name.casefold() for name in SYSTEM_TIME_COLUMNS}


def quote_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"Unsafe SQL identifier: {name}")
    return f"`{name}`"


def parse_enum_values(column_type: str) -> list[str]:
    if not column_type.lower().startswith("enum("):
        return []
    inner = column_type[5:-1]
    try:
        return next(csv.reader([inner], quotechar="'", escapechar="\\"))
    except csv.Error:
        return []


def display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    return str(value)


def humanize_name(name: str) -> str:
    canonical = TABLE_LOOKUP.get(name.casefold(), ("", name))[1]
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", canonical.replace("_", " "))
    if spaced == canonical and canonical.islower():
        spaced = canonical.replace("_", " ").title()
    spaced = spaced.replace(" I D", " ID").replace(" Z I P", " ZIP")
    return re.sub(r"\s+", " ", spaced).strip()


def module_for_table(table_name: str) -> str:
    return TABLE_LOOKUP.get(table_name.casefold(), ("Other", table_name))[0]


def reporting_view_label(view_name: str) -> str:
    return REPORTING_VIEW_LABELS.get(view_name.casefold(), humanize_name(view_name.removeprefix("vw_")))


def is_auto_increment(column: dict[str, Any]) -> bool:
    return "auto_increment" in (column.get("extra") or "").lower()


def is_tinyint_bool(column: dict[str, Any]) -> bool:
    return column.get("data_type") == "tinyint" and column.get("column_type") in {
        "tinyint(1)",
        "tinyint(1) unsigned",
    }


def default_text(column: dict[str, Any]) -> str:
    return display_value(column.get("default")).lower()


def is_system_managed(column: dict[str, Any]) -> bool:
    extra = (column.get("extra") or "").lower()
    default = default_text(column)
    name = column.get("name", "")
    return (
        "on update" in extra
        or "current_timestamp" in default
        or "curdate" in default
        or name.casefold() in SYSTEM_TIME_COLUMN_KEYS
    )


def is_required_for_insert(column: dict[str, Any]) -> bool:
    return (
        not column["nullable"]
        and column["default"] is None
        and not is_auto_increment(column)
        and not is_system_managed(column)
    )


def summarize_exception(exc: Exception) -> str:
    text = str(exc).strip()
    return text if text else exc.__class__.__name__


class DatabaseClient:
    def __init__(self) -> None:
        self.connection = None
        self.database_name = ""
        self.driver = ""

    @property
    def connected(self) -> bool:
        if not self.connection:
            return False
        if self.driver == "mysql-connector":
            return bool(self.connection.is_connected())
        if self.driver == "pymysql":
            return bool(self.connection.open)
        return False

    def connect(self, config: dict[str, str]) -> None:
        try:
            port = int(config["port"])
        except ValueError as exc:
            raise ValueError("Port must be a number, for example 3306.") from exc

        if self.connected:
            self.connection.close()

        if mysql_connector is not None:
            self.connection = mysql_connector.connect(
                host=config["host"],
                port=port,
                user=config["user"],
                password=config["password"],
                database=config["database"],
                autocommit=False,
            )
            self.driver = "mysql-connector"
        elif pymysql is not None:
            self.connection = pymysql.connect(
                host=config["host"],
                port=port,
                user=config["user"],
                password=config["password"],
                database=config["database"],
                autocommit=False,
                cursorclass=pymysql.cursors.DictCursor,
            )
            self.driver = "pymysql"
        else:
            raise RuntimeError(
                "No MySQL driver is installed. Run: pip install -r requirements.txt"
            )
        self.database_name = config["database"]

    def close(self) -> None:
        if self.connected:
            self.connection.close()

    def query(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        if not self.connected:
            raise RuntimeError("Not connected to MySQL.")
        cursor = self.connection.cursor(dictionary=True) if self.driver == "mysql-connector" else self.connection.cursor()
        try:
            if params:
                cursor.execute(sql, tuple(params))
            else:
                cursor.execute(sql)
            return list(cursor.fetchall())
        finally:
            cursor.close()

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> int:
        if not self.connected:
            raise RuntimeError("Not connected to MySQL.")
        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(sql, tuple(params))
            else:
                cursor.execute(sql)
            affected = cursor.rowcount
            self.connection.commit()
            return affected
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    @contextmanager
    def transaction(self):
        if not self.connected:
            raise RuntimeError("Not connected to MySQL.")
        cursor = self.connection.cursor(dictionary=True) if self.driver == "mysql-connector" else self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def table_names(self) -> list[str]:
        rows = self.query(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
            """
        )
        return [row["TABLE_NAME"] for row in rows]

    def view_names(self) -> list[str]:
        rows = self.query(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA = DATABASE()
            ORDER BY TABLE_NAME
            """
        )
        return [row["TABLE_NAME"] for row in rows]

    def table_columns(self, table_name: str) -> list[dict[str, Any]]:
        rows = self.query(
            """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                COLUMN_TYPE,
                IS_NULLABLE,
                COLUMN_KEY,
                COLUMN_DEFAULT,
                EXTRA,
                COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        )
        return [
            {
                "name": row["COLUMN_NAME"],
                "data_type": row["DATA_TYPE"],
                "column_type": row["COLUMN_TYPE"],
                "nullable": row["IS_NULLABLE"] == "YES",
                "key": row["COLUMN_KEY"] or "",
                "default": row["COLUMN_DEFAULT"],
                "extra": row["EXTRA"] or "",
                "comment": row["COLUMN_COMMENT"] or "",
                "enum_values": parse_enum_values(row["COLUMN_TYPE"] or ""),
            }
            for row in rows
        ]

    def foreign_keys(self, table_name: str) -> dict[str, tuple[str, str]]:
        rows = self.query(
            """
            SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        )
        return {
            row["COLUMN_NAME"]: (row["REFERENCED_TABLE_NAME"], row["REFERENCED_COLUMN_NAME"])
            for row in rows
        }

    def row_count(self, table_name: str, where_sql: str = "", params: tuple[Any, ...] = ()) -> int:
        sql = f"SELECT COUNT(*) AS total FROM {quote_identifier(table_name)}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        rows = self.query(sql, params)
        return int(rows[0]["total"])

    def table_row_counts(self, table_names: list[str]) -> dict[str, int]:
        if not table_names:
            return {}

        query_parts = []
        params: list[Any] = []
        for table_name in table_names:
            query_parts.append(
                f"SELECT %s AS TableName, COUNT(*) AS total FROM {quote_identifier(table_name)}"
            )
            params.append(table_name)

        rows = self.query(" UNION ALL ".join(query_parts), params)
        return {
            row["TableName"]: int(row["total"])
            for row in rows
        }

    def scalar(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> Any:
        rows = self.query(sql, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))


class ScrollableFrame(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        *,
        frame_style: str = "Panel.TFrame",
        background: str = COLORS["panel"],
        show_scrollbar: bool = True,
    ) -> None:
        super().__init__(parent, style=frame_style)
        self.show_scrollbar = show_scrollbar
        self.scrollbar_visible = False
        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            borderwidth=0,
            background=background,
        )
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style=frame_style)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)
        self._update_scrollbar_visibility()

    def _update_scrollbar_visibility(self) -> None:
        if not self.show_scrollbar:
            return
        bbox = self.canvas.bbox("all")
        content_height = (bbox[3] - bbox[1]) if bbox else 0
        needs_scrollbar = content_height > self.canvas.winfo_height()
        if needs_scrollbar and not self.scrollbar_visible:
            self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.scrollbar_visible = True
        elif not needs_scrollbar and self.scrollbar_visible:
            self.scrollbar.pack_forget()
            self.scrollbar_visible = False

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class LogoManager:
    def __init__(self, root: tk.Misc, logo_path: Path) -> None:
        self.root = root
        self.logo_path = logo_path
        self._cache: dict[tuple[int, int], tk.PhotoImage] = {}

    def get(self, max_width: int, max_height: int) -> tk.PhotoImage | None:
        key = (max_width, max_height)
        if key in self._cache:
            return self._cache[key]
        if not self.logo_path.exists():
            return None

        try:
            if Image is not None and ImageTk is not None:
                image = Image.open(self.logo_path).convert("RGBA")
                resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
                image.thumbnail((max_width, max_height), resampling)
                photo = ImageTk.PhotoImage(image)
            else:
                photo = tk.PhotoImage(file=str(self.logo_path))
                scale = max(
                    1,
                    int(photo.width() / max_width) + (1 if photo.width() % max_width else 0),
                    int(photo.height() / max_height) + (1 if photo.height() % max_height else 0),
                )
                if scale > 1:
                    photo = photo.subsample(scale, scale)
            self._cache[key] = photo
            return photo
        except (OSError, tk.TclError):
            return None


class SettingsDialog(tk.Toplevel):
    def __init__(self, app: "GUDormsAdminApp") -> None:
        super().__init__(app)
        self.app = app
        self.title("Database Settings")
        self.configure(background=COLORS["bg"])
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        self.vars = {
            key: tk.StringVar(value=app.config_values.get(key, DEFAULT_CONFIG[key]))
            for key in DEFAULT_CONFIG
        }
        self.save_password_var = tk.BooleanVar(value=bool(app.config_values.get("password")))

        self.build()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(20, self.center)

    def build(self) -> None:
        container = tk.Frame(
            self,
            background=COLORS["panel"],
            padx=20,
            pady=18,
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        container.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        tk.Label(
            container,
            text="Database Settings",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=FONTS["h2"],
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        tk.Label(
            container,
            text="These settings are hidden from the main dashboard.",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=FONTS["body"],
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 14))

        fields = [
            ("host", "Host", False),
            ("port", "Port", False),
            ("user", "User", False),
            ("password", "Password", True),
            ("database", "Database", False),
        ]
        for index, (key, label, secret) in enumerate(fields, start=2):
            tk.Label(
                container,
                text=label,
                background=COLORS["panel"],
                foreground=COLORS["text"],
                font=("Segoe UI", 9, "bold"),
            ).grid(row=index, column=0, sticky=tk.W, padx=(0, 12), pady=6)
            entry = ttk.Entry(
                container,
                textvariable=self.vars[key],
                width=34,
                show="*" if secret else "",
            )
            entry.grid(row=index, column=1, sticky=tk.EW, pady=6)

        ttk.Checkbutton(
            container,
            text="save password in db_config.json",
            variable=self.save_password_var,
        ).grid(row=7, column=1, sticky=tk.W, pady=(4, 12))

        actions = ttk.Frame(container, style="Panel.TFrame")
        actions.grid(row=8, column=0, columnspan=2, sticky=tk.E, pady=(4, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(actions, text="Save", command=self.save_only).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            actions,
            text="Test / Reconnect",
            style="Primary.TButton",
            command=self.save_and_reconnect,
        ).pack(side=tk.RIGHT)

        container.columnconfigure(1, weight=1)

    def collect(self) -> dict[str, str]:
        config = {
            key: var.get().strip() if key != "password" else var.get()
            for key, var in self.vars.items()
        }
        for key, default in DEFAULT_CONFIG.items():
            if key != "password" and not config[key]:
                config[key] = default
        return config

    def save_only(self) -> None:
        self.app.save_config_values(self.collect(), self.save_password_var.get())
        self.destroy()

    def save_and_reconnect(self) -> None:
        config = self.collect()
        self.app.save_config_values(config, self.save_password_var.get())
        if self.app.connect_to_database(config, show_errors=True):
            self.destroy()

    def center(self) -> None:
        self.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() - self.winfo_width()) // 2
        y = self.app.winfo_rooty() + (self.app.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")


class ApplicationAssignmentDialog(tk.Toplevel):
    def __init__(self, app: "GUDormsAdminApp", application: dict[str, Any]) -> None:
        super().__init__(app)
        self.app = app
        self.application = application
        self.rooms = list_assignable_rooms(app.db, application["StudentID"])
        self.room_display_to_id: dict[str, int] = {}
        self.bed_display_to_id: dict[str, int] = {}
        self.title("Approve application and assign room")
        self.configure(background=COLORS["bg"])
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        self.room_var = tk.StringVar()
        self.bed_var = tk.StringVar()
        self.check_in_var = tk.StringVar(
            value=display_value(application.get("StartDate") or date.today())
        )
        self.contract_var = tk.StringVar()

        self.build()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(20, self.center)

    def build(self) -> None:
        container = tk.Frame(
            self,
            background=COLORS["panel"],
            padx=20,
            pady=18,
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        container.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        tk.Label(
            container,
            text="Approve + assign room",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=FONTS["h2"],
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        tk.Label(
            container,
            text=f"{self.application['StudentName']} · {self.application['StudentID']}",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=FONTS["body"],
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 14))

        room_values = []
        for room in self.rooms:
            label = (
                f"{room['BuildingName']} ({room['BuildingCode']}) · "
                f"{room['RoomNumber']} · "
                f"{room['CurrentOccupancy']}/{room['Capacity']} occupied"
            )
            if room.get("RoomTypeName"):
                label += f" · {room['RoomTypeName']}"
            room_values.append(label)
            self.room_display_to_id[label] = room["RoomID"]

        self.make_label(container, "Room").grid(row=2, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        room_combo = ttk.Combobox(
            container,
            textvariable=self.room_var,
            values=room_values,
            state="readonly",
            width=52,
        )
        room_combo.grid(row=2, column=1, sticky=tk.EW, pady=6)
        room_combo.bind("<<ComboboxSelected>>", self.refresh_beds)
        if room_values:
            self.room_var.set(room_values[0])

        self.make_label(container, "Bed slot").grid(row=3, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        self.bed_combo = ttk.Combobox(
            container,
            textvariable=self.bed_var,
            values=[],
            state="readonly",
            width=52,
        )
        self.bed_combo.grid(row=3, column=1, sticky=tk.EW, pady=6)

        self.make_label(container, "Check-in date").grid(row=4, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        ttk.Entry(container, textvariable=self.check_in_var).grid(row=4, column=1, sticky=tk.EW, pady=6)

        self.make_label(container, "Contract duration").grid(row=5, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        ttk.Entry(container, textvariable=self.contract_var).grid(row=5, column=1, sticky=tk.EW, pady=6)

        self.make_label(container, "Notes").grid(row=6, column=0, sticky=tk.NW, padx=(0, 12), pady=6)
        self.notes_text = tk.Text(
            container,
            height=4,
            wrap=tk.WORD,
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            font=("Segoe UI", 10),
        )
        self.notes_text.grid(row=6, column=1, sticky=tk.EW, pady=6)

        tk.Label(
            container,
            text=(
                "If a room has bed slots and no bed is chosen, the system automatically "
                "uses the first free bed."
            ),
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=FONTS["small"],
        ).grid(row=7, column=1, sticky=tk.W, pady=(0, 12))

        actions = ttk.Frame(container, style="Panel.TFrame")
        actions.grid(row=8, column=0, columnspan=2, sticky=tk.E, pady=(4, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            actions,
            text="Approve + Assign",
            style="Primary.TButton",
            command=self.submit,
        ).pack(side=tk.RIGHT)

        container.columnconfigure(1, weight=1)
        self.refresh_beds()

    def make_label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=("Segoe UI", 9, "bold"),
        )

    def refresh_beds(self, _event: tk.Event | None = None) -> None:
        self.bed_display_to_id = {}
        room_id = self.room_display_to_id.get(self.room_var.get())
        if room_id is None:
            self.bed_combo.configure(values=[""])
            self.bed_var.set("")
            return
        beds = list_available_beds(self.app.db, room_id)
        values = [""]
        for bed in beds:
            label = bed["BedNumber"]
            if bed.get("BedPosition"):
                label += f" · {bed['BedPosition']}"
            values.append(label)
            self.bed_display_to_id[label] = bed["BedSlotID"]
        self.bed_combo.configure(values=values)
        self.bed_var.set("")

    def submit(self) -> None:
        room_id = self.room_display_to_id.get(self.room_var.get())
        if room_id is None:
            messagebox.showwarning("Choose a room", "Select an available room first.")
            return
        try:
            check_in_date = date.fromisoformat(self.check_in_var.get().strip())
        except ValueError:
            messagebox.showwarning("Check the date", "Check-in date must use YYYY-MM-DD.")
            return
        bed_slot_id = self.bed_display_to_id.get(self.bed_var.get())
        try:
            assignment_id = approve_application_with_assignment(
                self.app.db,
                self.application["ApplicationID"],
                room_id,
                bed_slot_id=bed_slot_id,
                check_in_date=check_in_date,
                contract_duration=self.contract_var.get().strip() or None,
                notes=self.notes_text.get("1.0", tk.END).strip() or None,
            )
        except Exception as exc:
            messagebox.showerror("Assignment failed", summarize_exception(exc))
            return
        self.app.set_status(
            f"Approved application {self.application['ApplicationID']} and created assignment {assignment_id}."
        )
        self.destroy()
        self.app.show_housing_operations()

    def center(self) -> None:
        self.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() - self.winfo_width()) // 2
        y = self.app.winfo_rooty() + (self.app.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")


class GUDormsAdminApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1400x860")
        self.minsize(1120, 720)
        self.configure(background=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.db = DatabaseClient()
        self.config_values = self.load_config()
        self.logo_manager = LogoManager(self, LOGO_PATH)
        self.available_tables: list[str] = []
        self.table_name_lookup: dict[str, str] = {}
        self.available_views: list[str] = []
        self.view_name_lookup: dict[str, str] = {}
        self.table_count_cache: dict[str, int | str] = {}
        self.current_table = ""
        self.current_columns: list[dict[str, Any]] = []
        self.current_foreign_keys: dict[str, tuple[str, str]] = {}
        self.current_relation_kind = "table"
        self.fk_options: dict[str, dict[str, str]] = {}
        self.fk_display_to_value: dict[str, dict[str, str]] = {}
        self.form_fields: dict[str, dict[str, Any]] = {}
        self.rows_by_item: dict[str, dict[str, Any]] = {}
        self.selected_row: dict[str, Any] | None = None
        self.current_view = "dashboard"

        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Starting dashboard...")
        self.connection_state_var = tk.StringVar(value="Database offline")
        self.form_mode_var = tk.StringVar(value="New record")
        self.connection_hint_var = tk.StringVar(value="Open Settings to configure MySQL")

        self.configure_styles()
        self.build_shell()
        self.populate_navigation()
        self.nav_tree.selection_set("dashboard")
        self.connect_to_database(self.config_values, show_errors=False)
        self.show_dashboard()

    def configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=("Segoe UI", 10))
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Soft.TFrame", background=COLORS["panel_soft"])
        style.configure("Header.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=FONTS["h1"])
        style.configure("Subheader.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
        style.configure("Section.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=FONTS["h2"])
        style.configure("Field.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 9, "bold"))
        style.configure("Hint.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 8))
        style.configure("Status.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])

        style.configure("Primary.TButton", background=COLORS["accent"], foreground="#ffffff", padding=(12, 7))
        style.map("Primary.TButton", background=[("active", COLORS["accent_dark"]), ("disabled", "#a9d7bd")])
        style.configure("Danger.TButton", background="#fff1ef", foreground=COLORS["danger"], padding=(12, 7))
        style.configure("Ghost.TButton", background=COLORS["panel"], foreground=COLORS["accent_dark"], padding=(10, 6))
        style.configure("TButton", padding=(10, 6))

        style.configure(
            "Treeview",
            rowheight=28,
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#e7f2ea",
            foreground=COLORS["text"],
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
        )
        style.map("Treeview", background=[("selected", "#d8f0df")], foreground=[("selected", COLORS["text"])])

        style.configure(
            "Nav.Treeview",
            rowheight=30,
            background=COLORS["nav"],
            fieldbackground=COLORS["nav"],
            foreground="#dff3e6",
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.map(
            "Nav.Treeview",
            background=[("selected", COLORS["nav_selected"])],
            foreground=[("selected", "#ffffff")],
        )

        style.configure("TEntry", padding=(4, 4))
        style.configure("TCombobox", padding=(4, 4))

    def load_config(self) -> dict[str, str]:
        if not CONFIG_PATH.exists():
            return DEFAULT_CONFIG.copy()
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config = DEFAULT_CONFIG.copy()
            config.update({key: str(value) for key, value in saved.items()})
            return config
        except (OSError, json.JSONDecodeError):
            return DEFAULT_CONFIG.copy()

    def save_config_values(self, config: dict[str, str], save_password: bool) -> None:
        to_save = config.copy()
        if not save_password:
            to_save["password"] = ""
        CONFIG_PATH.write_text(json.dumps(to_save, indent=2), encoding="utf-8")
        self.config_values = config.copy()
        self.set_status(f"Database settings saved to {CONFIG_PATH.name}.")

    def build_shell(self) -> None:
        shell = tk.Frame(self, background=COLORS["bg"])
        shell.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(shell, background=COLORS["nav"], width=300)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, background=COLORS["nav"], padx=18, pady=18)
        brand.pack(fill=tk.X)
        logo = self.logo_manager.get(236, 78)
        if logo:
            tk.Label(brand, image=logo, background=COLORS["nav"]).pack(anchor=tk.W, pady=(0, 10))
        else:
            tk.Label(
                brand,
                text="GU",
                background=COLORS["logo_green"],
                foreground=COLORS["blue"],
                font=("Segoe UI", 28, "bold"),
                padx=14,
                pady=8,
            ).pack(anchor=tk.W, pady=(0, 10))
        tk.Label(
            brand,
            text="Dorms Administration",
            background=COLORS["nav"],
            foreground="#ffffff",
            font=FONTS["brand"],
        ).pack(anchor=tk.W)
        tk.Label(
            brand,
            text="Galala University operations",
            background=COLORS["nav"],
            foreground="#b6d8c3",
            font=("Segoe UI", 10),
        ).pack(anchor=tk.W, pady=(2, 0))

        status_chip = tk.Frame(brand, background=COLORS["nav_soft"], padx=10, pady=8)
        status_chip.pack(fill=tk.X, pady=(16, 0))
        tk.Label(
            status_chip,
            textvariable=self.connection_state_var,
            background=COLORS["nav_soft"],
            foreground="#ecfff2",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            status_chip,
            textvariable=self.connection_hint_var,
            background=COLORS["nav_soft"],
            foreground="#b6d8c3",
            font=("Segoe UI", 8),
        ).pack(anchor=tk.W)

        nav_wrap = tk.Frame(sidebar, background=COLORS["nav"], padx=12, pady=8)
        nav_wrap.pack(fill=tk.BOTH, expand=True)
        self.nav_tree = ttk.Treeview(nav_wrap, show="tree", selectmode="browse", style="Nav.Treeview")
        self.nav_tree.pack(fill=tk.BOTH, expand=True)
        self.nav_tree.bind("<<TreeviewSelect>>", self.on_navigation_select)

        sidebar_footer = tk.Frame(sidebar, background=COLORS["nav"], padx=12, pady=14)
        sidebar_footer.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(
            sidebar_footer,
            text="Database Settings",
            command=self.open_settings,
            background=COLORS["accent"],
            foreground="#ffffff",
            activebackground=COLORS["accent_dark"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(fill=tk.X)

        main = ttk.Frame(shell, style="App.TFrame", padding=(18, 14, 18, 12))
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content = ttk.Frame(main, style="App.TFrame")
        self.content.pack(fill=tk.BOTH, expand=True)

        status = tk.Frame(main, background=COLORS["panel"], padx=12, pady=8)
        status.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)
        ttk.Button(status, text="Settings", command=self.open_settings).pack(side=tk.RIGHT)
        ttk.Button(status, text="Refresh Current View", command=self.refresh_current_view).pack(
            side=tk.RIGHT,
            padx=(0, 8),
        )

    def populate_navigation(self) -> None:
        for item in self.nav_tree.get_children():
            self.nav_tree.delete(item)

        self.nav_tree.insert("", tk.END, iid="dashboard", text="Dashboard", open=True)
        self.nav_tree.insert("", tk.END, iid="housing_ops", text="Housing Operations", open=True)
        self.nav_tree.insert("", tk.END, iid="system_integrity", text="System Integrity", open=True)
        self.nav_tree.insert("", tk.END, iid="reporting_views", text="Reporting Views", open=True)
        for view_name in self.ordered_available_views():
            self.nav_tree.insert(
                "reporting_views",
                tk.END,
                iid=f"view:{view_name}",
                text=reporting_view_label(view_name),
            )
        workflows_id = "workflows"
        self.nav_tree.insert("", tk.END, iid=workflows_id, text="Departments", open=True)
        for group_name, _description, _table in DEPARTMENT_SHORTCUTS:
            self.nav_tree.insert(workflows_id, tk.END, iid=f"workflow:{group_name}", text=group_name)

        advanced_id = "advanced"
        self.nav_tree.insert("", tk.END, iid=advanced_id, text="Advanced Data Manager", open=False)
        assigned: set[str] = set()

        for group_name, tables in TABLE_GROUPS:
            group_id = f"advanced_group:{group_name}"
            self.nav_tree.insert(advanced_id, tk.END, iid=group_id, text=group_name, open=False)
            for table in tables:
                actual_table = self.resolve_table_name(table)
                if not self.available_tables or actual_table:
                    table_id = actual_table or table
                    self.nav_tree.insert(
                        group_id,
                        tk.END,
                        iid=f"table:{table_id}",
                        text=humanize_name(table),
                    )
                    assigned.add(table_id.casefold())

        extras = [table for table in self.available_tables if table.casefold() not in assigned]
        if extras:
            group_id = "advanced_group:Other"
            self.nav_tree.insert(advanced_id, tk.END, iid=group_id, text="Other", open=False)
            for table in extras:
                self.nav_tree.insert(group_id, tk.END, iid=f"table:{table}", text=humanize_name(table))

    def rebuild_table_lookup(self) -> None:
        self.table_name_lookup = {
            table.casefold(): table
            for table in self.available_tables
        }
        self.view_name_lookup = {
            view.casefold(): view
            for view in self.available_views
        }

    def resolve_table_name(self, table_name: str) -> str:
        if not self.available_tables:
            return table_name
        return self.table_name_lookup.get(table_name.casefold(), "")

    def resolve_view_name(self, view_name: str) -> str:
        if not self.available_views:
            return view_name
        return self.view_name_lookup.get(view_name.casefold(), "")

    def ordered_available_tables(self) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        for _group_name, tables in TABLE_GROUPS:
            for table in tables:
                actual_table = self.resolve_table_name(table)
                if actual_table and actual_table.casefold() not in seen:
                    ordered.append(actual_table)
                    seen.add(actual_table.casefold())

        for table in sorted(self.available_tables, key=lambda value: humanize_name(value).casefold()):
            if table.casefold() not in seen:
                ordered.append(table)
                seen.add(table.casefold())

        return ordered

    def ordered_available_views(self) -> list[str]:
        return sorted(self.available_views, key=lambda value: reporting_view_label(value).casefold())

    def clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def make_scrollable_page(self) -> ttk.Frame:
        page = ScrollableFrame(
            self.content,
            frame_style="App.TFrame",
            background=COLORS["bg"],
        )
        page.pack(fill=tk.BOTH, expand=True)
        return page.inner

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def connect_to_database(self, config: dict[str, str] | None = None, show_errors: bool = True) -> bool:
        config = config or self.config_values
        try:
            self.db.connect(config)
            self.available_tables = self.db.table_names()
            self.available_views = self.db.view_names()
            self.rebuild_table_lookup()
            self.populate_navigation()
            self.config_values = config.copy()
            self.connection_state_var.set(f"Online: {config['database']}")
            self.connection_hint_var.set(f"{config['user']}@{config['host']}:{config['port']}")
            self.set_status(f"Connected to {config['database']} as {config['user']}.")
            return True
        except (RuntimeError, MySQLError, ValueError) as exc:
            self.available_tables = []
            self.available_views = []
            self.rebuild_table_lookup()
            self.populate_navigation()
            self.connection_state_var.set("Database offline")
            self.connection_hint_var.set("Open Settings to reconnect")
            self.set_status(f"Database offline: {summarize_exception(exc)}")
            if show_errors:
                messagebox.showerror("Connection failed", summarize_exception(exc))
            return False

    def open_settings(self) -> None:
        SettingsDialog(self)

    def refresh_dashboard(self) -> None:
        if self.db.connected:
            self.available_tables = self.db.table_names()
            self.available_views = self.db.view_names()
            self.rebuild_table_lookup()
            self.populate_navigation()
            self.table_count_cache.clear()
        self.show_dashboard()
        self.set_status(f"Dashboard refreshed at {datetime.now():%H:%M:%S}.")

    def refresh_current_view(self) -> None:
        if self.current_view == "dashboard":
            self.refresh_dashboard()
        elif self.current_view == "housing_ops":
            self.show_housing_operations()
            self.set_status(f"Housing operations refreshed at {datetime.now():%H:%M:%S}.")
        elif self.current_view == "system_integrity":
            self.show_system_integrity()
            self.set_status(f"System integrity refreshed at {datetime.now():%H:%M:%S}.")
        elif self.current_view == "reporting_views":
            self.show_reporting_views()
            self.set_status(f"Reporting views refreshed at {datetime.now():%H:%M:%S}.")
        elif self.current_view.startswith("department:"):
            self.show_department(self.current_view.split(":", 1)[1])
            self.set_status(f"Department view refreshed at {datetime.now():%H:%M:%S}.")
        elif self.current_view == "advanced":
            self.show_advanced_manager()
            self.set_status(f"Advanced manager refreshed at {datetime.now():%H:%M:%S}.")
        elif self.current_view.startswith("table:"):
            self.refresh_rows(clear_form=False)
            self.set_status(f"{humanize_name(self.current_table)} refreshed at {datetime.now():%H:%M:%S}.")
        elif self.current_view.startswith("view:"):
            self.refresh_rows(clear_form=False)
            self.set_status(f"{humanize_name(self.current_table)} refreshed at {datetime.now():%H:%M:%S}.")

    def on_navigation_select(self, _event: tk.Event) -> None:
        selected = self.nav_tree.selection()
        if not selected:
            return
        item_id = selected[0]
        if item_id == "dashboard":
            self.show_dashboard()
        elif item_id == "housing_ops":
            self.show_housing_operations()
        elif item_id == "system_integrity":
            self.show_system_integrity()
        elif item_id == "reporting_views":
            self.show_reporting_views()
        elif item_id == "advanced":
            self.show_advanced_manager()
        elif item_id.startswith("workflow:"):
            self.show_department(item_id.split(":", 1)[1])
        elif item_id.startswith("table:"):
            self.load_table(item_id.split(":", 1)[1])
        elif item_id.startswith("view:"):
            self.load_view(item_id.split(":", 1)[1])

    def show_dashboard(self) -> None:
        self.current_view = "dashboard"
        self.clear_content()
        wrapper = self.make_scrollable_page()

        header = self.make_panel(wrapper, padx=20, pady=18)
        header.pack(fill=tk.X)
        top = ttk.Frame(header, style="Panel.TFrame")
        top.pack(fill=tk.X)
        ttk.Label(top, text="Dorms Management Dashboard", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(top, text="Refresh", style="Primary.TButton", command=self.refresh_dashboard).pack(side=tk.RIGHT)
        ttk.Label(
            header,
            text="Operational overview for residence, room allocation, finance, maintenance, services, and security teams.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(3, 0))

        if not self.db.connected:
            self.render_offline_notice(wrapper)
            return

        dashboard = self.load_dashboard_data()
        metrics_frame = tk.Frame(wrapper, background=COLORS["bg"])
        metrics_frame.pack(fill=tk.X, pady=(14, 12))
        for index, (label, value, color, caption) in enumerate(dashboard["kpis"]):
            card = self.make_metric_card(metrics_frame, label, value, color, caption)
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 10), pady=(0, 10))
        for column in range(4):
            metrics_frame.columnconfigure(column, weight=1)

        sections = ttk.Frame(wrapper, style="App.TFrame")
        sections.pack(fill=tk.BOTH, expand=True)

        priority_panel = self.make_panel(sections, padx=16, pady=14)
        priority_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        ttk.Label(priority_panel, text="Priority Queues", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(
            priority_panel,
            text="Work that needs dorm staff attention first.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(2, 12))
        self.render_priority_queue(priority_panel, dashboard["queues"])

        right = ttk.Frame(sections, style="App.TFrame")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        activity_panel = self.make_panel(right, padx=16, pady=14)
        activity_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        ttk.Label(activity_panel, text="Dorm Activity", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(
            activity_panel,
            text="Useful snapshots across services, access, and student support.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(2, 12))
        self.render_activity_snapshot(activity_panel, dashboard["activity"])

        tools_panel = self.make_panel(right, padx=16, pady=14)
        tools_panel.pack(fill=tk.X)
        ttk.Label(tools_panel, text="Management Tools", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(
            tools_panel,
            text="Open department workflows or use direct table access for administrative corrections.",
            style="Subheader.TLabel",
            wraplength=520,
        ).pack(anchor=tk.W, pady=(2, 12))
        self.render_management_tools(tools_panel)

    def render_offline_notice(self, parent: ttk.Frame) -> None:
        notice = tk.Frame(
            parent,
            background="#fff8e8",
            highlightbackground="#efd39a",
            highlightthickness=1,
            padx=18,
            pady=16,
        )
        notice.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            notice,
            text="Database is offline",
            background="#fff8e8",
            foreground=COLORS["warning"],
            font=FONTS["h2"],
        ).pack(anchor=tk.W)
        tk.Label(
            notice,
            text="The dashboard shell is ready. Open Settings to update MySQL credentials and reconnect.",
            background="#fff8e8",
            foreground=COLORS["muted"],
            font=FONTS["body"],
        ).pack(anchor=tk.W, pady=(4, 10))
        ttk.Button(notice, text="Open Settings", style="Primary.TButton", command=self.open_settings).pack(anchor=tk.W)

    def dashboard_count(
        self,
        table: str,
        where_sql: str = "",
        params: tuple[Any, ...] = (),
    ) -> int | None:
        actual_table = self.resolve_table_name(table)
        if not actual_table:
            return 0
        try:
            return self.db.row_count(actual_table, where_sql, params)
        except Exception:
            return None

    def dashboard_scalar(
        self,
        table: str,
        expression: str,
        where_sql: str = "",
        params: tuple[Any, ...] = (),
    ) -> Any:
        actual_table = self.resolve_table_name(table)
        if not actual_table:
            return 0
        try:
            sql = f"SELECT {expression} AS value FROM {quote_identifier(actual_table)}"
            if where_sql:
                sql += f" WHERE {where_sql}"
            return self.db.scalar(sql, params)
        except Exception:
            return None

    def dashboard_custom_scalar(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> Any:
        try:
            return self.db.scalar(sql, params)
        except Exception:
            return None

    def dashboard_prefer_scalar(self, primary_sql: str, fallback_sql: str) -> Any:
        value = self.dashboard_custom_scalar(primary_sql)
        return self.dashboard_custom_scalar(fallback_sql) if value is None else value

    def count_text(self, value: int | None) -> str:
        if value is None:
            return "0"
        return str(int(value))

    def dashboard_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def load_dashboard_data(self) -> dict[str, Any]:
        active_students = self.dashboard_count("Student", "Status = %s", ("Active",))
        active_assignments = self.dashboard_count("RoomAssignment", "Status = %s", ("Active",))
        physical_bed_slots = self.dashboard_scalar("BedSlot", "COUNT(*)")
        available_physical_bed_slots = self.dashboard_scalar(
            "BedSlot",
            "COUNT(*)",
            "IsOccupied = 0 AND IsReserved = 0",
        )
        configured_room_capacity = self.dashboard_scalar("Room", "COALESCE(SUM(Capacity), 0)")
        configured_available_capacity = self.dashboard_custom_scalar(
            """
            SELECT COALESCE(
                SUM(GREATEST(room.Capacity - COALESCE(room.CurrentOccupancy, 0), 0)),
                0
            )
            FROM Room room
            JOIN Building building ON building.BuildingID = room.BuildingID
            WHERE building.Status = 'Active'
              AND room.Status IN ('Available', 'Occupied')
            """
        )

        physical_bed_slots_num = self.dashboard_int(physical_bed_slots)
        uses_physical_bed_slots = physical_bed_slots_num > 0
        total_capacity_num = (
            physical_bed_slots_num
            if uses_physical_bed_slots
            else self.dashboard_int(configured_room_capacity)
        )
        available_beds = (
            self.dashboard_int(available_physical_bed_slots)
            if uses_physical_bed_slots
            else self.dashboard_int(configured_available_capacity)
        )
        capacity_caption = (
            "physical bed slots"
            if uses_physical_bed_slots
            else "configured room capacity"
        )
        available_beds_caption = (
            "free physical bed slots"
            if uses_physical_bed_slots
            else "available room capacity"
        )

        available_rooms = self.dashboard_custom_scalar(
            """
            SELECT COUNT(*)
            FROM Room room
            JOIN Building building ON building.BuildingID = room.BuildingID
            WHERE building.Status = 'Active'
              AND room.Status IN ('Available', 'Occupied')
              AND COALESCE(room.CurrentOccupancy, 0) < room.Capacity
              AND (
                    NOT EXISTS (
                        SELECT 1
                        FROM BedSlot bed
                        WHERE bed.RoomID = room.RoomID
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM BedSlot bed
                        WHERE bed.RoomID = room.RoomID
                          AND bed.IsOccupied = 0
                          AND bed.IsReserved = 0
                    )
              )
            """
        )
        open_maintenance = self.dashboard_prefer_scalar(
            "SELECT COUNT(*) FROM vw_ActiveMaintenanceRequests",
            """
            SELECT COUNT(*)
            FROM MaintenanceRequest
            WHERE Status IN ('Open', 'In Progress')
            """,
        )

        active_assignments_num = active_assignments or 0
        occupancy_value = "0%"
        if total_capacity_num:
            occupancy_value = f"{round((active_assignments_num / total_capacity_num) * 100)}%"

        queues = [
            (
                "Pending housing applications",
                self.dashboard_count("Registration", "Status IN ('Pending', 'Waitlisted')"),
                "Registration",
                "Review applications and waitlist decisions.",
                COLORS["accent_dark"],
            ),
            (
                "Approved applications awaiting assignment",
                self.dashboard_custom_scalar(
                    """
                    SELECT COUNT(*)
                    FROM Registration reg
                    LEFT JOIN RoomAssignment ra ON ra.ApplicationID = reg.ApplicationID
                    WHERE reg.Status = 'Approved'
                      AND ra.AssignmentID IS NULL
                    """
                ),
                "Registration",
                "Approved students who still need a room assignment.",
                COLORS["warning"],
            ),
            (
                "Overdue invoices",
                self.dashboard_prefer_scalar(
                    "SELECT COUNT(*) FROM vw_OverdueInvoicesAlert",
                    "SELECT COUNT(*) FROM Invoice WHERE PaymentStatus = 'Overdue'",
                ),
                "Invoice",
                "Finance follow-up already past due.",
                COLORS["danger"],
            ),
            (
                "Critical maintenance",
                self.dashboard_count(
                    "MaintenanceRequest",
                    "Priority = 'Critical' AND Status NOT IN ('Closed', 'Cancelled')",
                ),
                "MaintenanceRequest",
                "Urgent facilities issues to dispatch.",
                COLORS["danger"],
            ),
            (
                "Open complaints",
                self.dashboard_count("Complaint", "Status IN ('Open', 'In Progress')"),
                "Complaint",
                "Student support items still unresolved.",
                COLORS["warning"],
            ),
            (
                "Pending leave permissions",
                self.dashboard_count("LeavePermission", "Status = %s", ("Pending",)),
                "LeavePermission",
                "Overnight or leave approvals awaiting staff.",
                COLORS["accent_dark"],
            ),
            (
                "Pending visitor approvals",
                self.dashboard_count("VisitorPermission", "Status = %s", ("Pending",)),
                "VisitorPermission",
                "Visitor access requests awaiting approval.",
                COLORS["warning"],
            ),
            (
                "Active students without portal account",
                self.dashboard_custom_scalar(
                    """
                    SELECT COUNT(*)
                    FROM Student student
                    LEFT JOIN SystemUser user_account
                      ON user_account.StudentID = student.StudentID
                     AND user_account.Status = 'Active'
                    LEFT JOIN Role role
                      ON role.RoleID = user_account.RoleID
                     AND LOWER(role.RoleName) LIKE '%student%'
                    WHERE student.Status = 'Active'
                      AND role.RoleID IS NULL
                    """
                ),
                "Student",
                "These records exist, but cannot sign in to the website yet.",
                COLORS["warning"],
            ),
        ]

        activity = [
            (
                "Available bed slots",
                available_beds,
                available_beds_caption,
            ),
            (
                "Actionable inspections",
                self.dashboard_prefer_scalar(
                    "SELECT COUNT(*) FROM vw_ActionableInspections",
                    """
                    SELECT COUNT(*)
                    FROM RoomInspection
                    WHERE Status = 'Failed' OR FollowUpRequired = 1
                    """,
                ),
                "needs follow-up",
            ),
            (
                "Expiring contracts",
                self.dashboard_prefer_scalar(
                    "SELECT COUNT(*) FROM vw_ExpiringContracts",
                    """
                    SELECT COUNT(*)
                    FROM RoomAssignment
                    WHERE Status = 'Active'
                      AND CheckOutDate BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                    """,
                ),
                "next 30 days",
            ),
            (
                "Active blacklist",
                self.dashboard_prefer_scalar(
                    "SELECT COUNT(*) FROM vw_ActiveBlacklist",
                    """
                    SELECT COUNT(*)
                    FROM Blacklist
                    WHERE Status = 'Active'
                      AND (EndDate IS NULL OR EndDate >= CURDATE())
                    """,
                ),
                "current records",
            ),
            ("Recent payments", self.dashboard_count("PaymentTransaction", "PaymentDate >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"), "last 30 days"),
            ("Meal check-ins", self.dashboard_count("MealAttendance", "MealDate = CURDATE()"), "today"),
        ]

        return {
            "kpis": [
                (
                    "Active Students",
                    self.count_text(active_students),
                    COLORS["accent"],
                    "Students currently marked active",
                ),
                (
                    "Occupancy",
                    occupancy_value,
                    COLORS["accent_dark"],
                    f"{active_assignments_num} active assignments / {total_capacity_num} {capacity_caption}",
                ),
                (
                    "Available Rooms",
                    self.count_text(available_rooms),
                    COLORS["success"],
                    "Rooms ready for assignment",
                ),
                (
                    "Open Maintenance",
                    self.count_text(open_maintenance),
                    COLORS["warning"],
                    "Open or in-progress requests",
                ),
            ],
            "queues": queues,
            "activity": activity,
        }

    def render_priority_queue(self, parent: ttk.Frame, queues: list[tuple[str, int | None, str, str, str]]) -> None:
        for title, count, table_name, description, color in queues:
            row = tk.Frame(
                parent,
                background=COLORS["panel_soft"],
                highlightbackground=COLORS["line"],
                highlightthickness=1,
                padx=12,
                pady=10,
            )
            row.pack(fill=tk.X, pady=(0, 8))
            badge_color = COLORS["success"] if count == 0 else color
            tk.Label(
                row,
                text=self.count_text(count),
                width=4,
                background=badge_color,
                foreground="#ffffff",
                font=("Segoe UI", 13, "bold"),
                padx=6,
                pady=5,
            ).pack(side=tk.LEFT, padx=(0, 12))
            text_block = tk.Frame(row, background=COLORS["panel_soft"])
            text_block.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(
                text_block,
                text=title,
                background=COLORS["panel_soft"],
                foreground=COLORS["text"],
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor=tk.W)
            tk.Label(
                text_block,
                text=description,
                background=COLORS["panel_soft"],
                foreground=COLORS["muted"],
                font=("Segoe UI", 8),
                wraplength=360,
                justify=tk.LEFT,
            ).pack(anchor=tk.W)
            ttk.Button(row, text="Open", command=lambda table=table_name: self.load_table(table)).pack(side=tk.RIGHT)

    def render_activity_snapshot(self, parent: ttk.Frame, activity: list[tuple[str, int | None, str]]) -> None:
        grid = tk.Frame(parent, background=COLORS["panel"])
        grid.pack(fill=tk.BOTH, expand=True)
        for index, (label, count, caption) in enumerate(activity):
            tile = tk.Frame(
                grid,
                background=COLORS["panel_soft"],
                highlightbackground=COLORS["line"],
                highlightthickness=1,
                padx=12,
                pady=10,
            )
            tile.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0, 10), pady=(0, 10))
            tk.Label(
                tile,
                text=label,
                background=COLORS["panel_soft"],
                foreground=COLORS["muted"],
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor=tk.W)
            tk.Label(
                tile,
                text=self.count_text(count),
                background=COLORS["panel_soft"],
                foreground=COLORS["accent_dark"],
                font=("Segoe UI", 18, "bold"),
            ).pack(anchor=tk.W)
            tk.Label(
                tile,
                text=caption,
                background=COLORS["panel_soft"],
                foreground=COLORS["muted"],
                font=("Segoe UI", 8),
            ).pack(anchor=tk.W)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    def render_management_tools(self, parent: ttk.Frame) -> None:
        tools = [
            ("Housing Operations", self.show_housing_operations),
            ("System Integrity", self.show_system_integrity),
            ("Reporting Views", self.show_reporting_views),
            ("Housing", lambda: self.show_department("Housing")),
            ("Finance", lambda: self.show_department("Finance")),
            ("Staff & Students", lambda: self.show_department("People & Staff")),
            ("Maintenance", lambda: self.show_department("Maintenance & Assets")),
            ("Security", lambda: self.show_department("Security & Visitors")),
            ("Advanced Data Manager", self.show_advanced_manager),
        ]
        grid = tk.Frame(parent, background=COLORS["panel"])
        grid.pack(fill=tk.X)
        for index, (label, command) in enumerate(tools):
            button = ttk.Button(grid, text=label, command=command)
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 10), pady=(0, 8))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    def show_system_integrity(self) -> None:
        self.current_view = "system_integrity"
        self.clear_content()
        wrapper = self.make_scrollable_page()

        header = self.make_panel(wrapper, padx=20, pady=18)
        header.pack(fill=tk.X)
        top = ttk.Frame(header, style="Panel.TFrame")
        top.pack(fill=tk.X)
        ttk.Label(top, text="System Integrity", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(
            top,
            text="Refresh",
            style="Primary.TButton",
            command=self.show_system_integrity,
        ).pack(side=tk.RIGHT)
        ttk.Label(
            header,
            text="Cross-module consistency checks for the records shared by the admin GUI and student website.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(3, 0))

        if not self.db.connected:
            self.render_offline_notice(wrapper)
            return

        snapshot = get_system_integrity_snapshot(self.db)
        cards = [
            ("Resolved maintenance missing time", snapshot["resolved_maintenance_missing_timestamp"], COLORS["warning"]),
            ("Closed complaints missing time", snapshot["closed_complaints_missing_timestamp"], COLORS["warning"]),
            ("Resolved incidents missing time", snapshot["resolved_incidents_missing_timestamp"], COLORS["warning"]),
            ("Decision dates missing", snapshot["decisions_missing_dates"], COLORS["warning"]),
            ("Invoice status drift", snapshot["invoice_status_mismatch"], COLORS["danger"]),
            ("Broken completed transfers", snapshot["completed_transfers_without_new_assignment"], COLORS["danger"]),
            ("Approved transfers waiting move", snapshot["approved_transfers_due_without_move"], COLORS["danger"]),
            ("Payment / invoice student mismatch", snapshot["payment_student_mismatch"], COLORS["danger"]),
            ("Portal account profile drift", snapshot["student_account_profile_mismatch"], COLORS["warning"]),
            ("Students without portal account", snapshot["active_students_without_portal_account"], COLORS["warning"]),
            ("Expired visitor passes still active", snapshot["stale_visitor_permissions"], COLORS["warning"]),
            ("Expired meal plans still active", snapshot["stale_meal_subscriptions"], COLORS["warning"]),
            ("Past-due penalties still pending", snapshot["pending_penalties_past_due"], COLORS["warning"]),
            ("Room inspection rollup drift", snapshot["room_inspection_rollup_mismatch"], COLORS["warning"]),
            ("Building maintenance rollup drift", snapshot["building_maintenance_rollup_mismatch"], COLORS["warning"]),
            ("Checkout before check-in", snapshot["assignment_checkout_before_checkin"], COLORS["danger"]),
            ("Transfer before source check-in", snapshot["transfer_move_before_source_checkin"], COLORS["danger"]),
        ]
        health = ttk.Frame(wrapper, style="App.TFrame")
        health.pack(fill=tk.X, pady=(14, 12))
        for index, (label, value, color) in enumerate(cards):
            card = self.make_metric_card(health, label, str(value), color)
            card.grid(row=index // 4, column=index % 4, sticky="nsew", padx=(0, 10), pady=(0, 10))
        for column in range(4):
            health.columnconfigure(column, weight=1)

        action_panel = self.make_panel(wrapper, padx=16, pady=14)
        action_panel.pack(fill=tk.X)
        ttk.Label(action_panel, text="Safe operational repair", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(
            action_panel,
            text=(
                "Fills missing resolution / decision timestamps, recalculates invoice payment status "
                "from completed transactions, completes due approved room transfers, expires stale student-facing "
                "records, updates room/building rollups, and re-syncs linked student login emails and names from Student."
            ),
            style="Subheader.TLabel",
            wraplength=980,
        ).pack(anchor=tk.W, pady=(2, 10))
        ttk.Button(
            action_panel,
            text="Reconcile safe operational data",
            style="Primary.TButton",
            command=self.reconcile_operational_from_ui,
        ).pack(anchor=tk.W)

    def reconcile_operational_from_ui(self) -> None:
        try:
            result = reconcile_operational_data(self.db)
        except Exception as exc:
            messagebox.showerror("Reconcile failed", summarize_exception(exc))
            return
        self.set_status(
            "Operational data reconciled: "
            f"{result.get('maintenance_timestamps', 0)} maintenance timestamp(s), "
            f"{result.get('complaint_timestamps', 0)} complaint timestamp(s), "
            f"{result.get('incident_timestamps', 0)} incident timestamp(s), "
            f"{result.get('registration_decisions', 0)} registration decision(s), "
            f"{result.get('transfer_decisions', 0)} transfer decision(s), "
            f"{result.get('leave_decisions', 0)} leave decision(s), "
            f"{result.get('visitor_decisions', 0)} visitor decision(s), "
            f"{result.get('expired_visitor_permissions', 0)} expired visitor permission(s), "
            f"{result.get('expired_meal_subscriptions', 0)} expired meal subscription(s), "
            f"{result.get('overdue_penalties', 0)} overdue penalty status update(s), "
            f"{result.get('repaired_assignment_dates', 0)} assignment date repair(s), "
            f"{result.get('repaired_transfer_dates', 0)} transfer date repair(s), "
            f"{result.get('completed_due_transfers', 0)} due transfer completion(s), "
            f"{result.get('invoice_statuses', 0)} invoice status update(s), "
            f"{result.get('synced_student_accounts', 0)} portal account sync(s), "
            f"{result.get('room_inspection_rollups', 0)} room inspection rollup(s), "
            f"{result.get('building_maintenance_rollups', 0)} building maintenance rollup(s)."
        )
        self.show_system_integrity()

    def show_housing_operations(self) -> None:
        self.current_view = "housing_ops"
        self.clear_content()
        wrapper = self.make_scrollable_page()

        header = self.make_panel(wrapper, padx=20, pady=18)
        header.pack(fill=tk.X)
        top = ttk.Frame(header, style="Panel.TFrame")
        top.pack(fill=tk.X)
        ttk.Label(top, text="Housing Operations", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(
            top,
            text="Refresh",
            style="Primary.TButton",
            command=self.show_housing_operations,
        ).pack(side=tk.RIGHT)
        ttk.Label(
            header,
            text="Application approval, room assignment, and housing-data consistency in one workflow.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(3, 0))

        if not self.db.connected:
            self.render_offline_notice(wrapper)
            return

        snapshot = get_housing_integrity_snapshot(self.db)
        health = ttk.Frame(wrapper, style="App.TFrame")
        health.pack(fill=tk.X, pady=(14, 12))
        cards = [
            ("Approved / unassigned", snapshot["approved_without_assignment"], COLORS["warning"]),
            ("Missing occupancy logs", snapshot["missing_occupancy_logs"], COLORS["warning"]),
            ("Room occupancy drift", snapshot["occupancy_mismatch"], COLORS["danger"]),
            ("Active assignments missing beds", snapshot["active_assignments_missing_bed_slots"], COLORS["warning"]),
            ("Orphan bed slots", snapshot["orphan_bed_slots"], COLORS["danger"]),
            ("Bed / room mismatch", snapshot["assignment_bed_room_mismatch"], COLORS["danger"]),
            ("Application / student mismatch", snapshot["assignment_application_student_mismatch"], COLORS["danger"]),
            ("Unavailable-room assignments", snapshot["active_assignment_in_unavailable_room"], COLORS["danger"]),
            ("Rooms over capacity", snapshot["active_room_over_capacity"], COLORS["danger"]),
        ]
        for index, (label, value, color) in enumerate(cards):
            card = self.make_metric_card(health, label, str(value), color)
            card.grid(row=index // 5, column=index % 5, sticky="nsew", padx=(0, 10), pady=(0, 10))
        for column in range(5):
            health.columnconfigure(column, weight=1)

        action_panel = self.make_panel(wrapper, padx=16, pady=14)
        action_panel.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(action_panel, text="Safe auto-record repair", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(
            action_panel,
            text=(
                "Rebuilds room occupancy, room availability/occupied status, bed occupancy, "
                "fills missing active bed assignments when a free bed exists, and restores missing occupancy-log rows "
                "from active assignments. Orphan bed slots are flagged "
                "for manual correction because their parent room no longer exists."
            ),
            style="Subheader.TLabel",
            wraplength=980,
        ).pack(anchor=tk.W, pady=(2, 10))
        ttk.Button(
            action_panel,
            text="Reconcile safe housing data",
            style="Primary.TButton",
            command=self.reconcile_housing_from_ui,
        ).pack(anchor=tk.W)

        queue_panel = self.make_panel(wrapper, padx=16, pady=14)
        queue_panel.pack(fill=tk.BOTH, expand=True)
        header_row = ttk.Frame(queue_panel, style="Panel.TFrame")
        header_row.pack(fill=tk.X)
        ttk.Label(header_row, text="Applications awaiting assignment", style="Section.TLabel").pack(side=tk.LEFT)
        queue_actions = ttk.Frame(header_row, style="Panel.TFrame")
        queue_actions.pack(side=tk.RIGHT)
        ttk.Button(
            queue_actions,
            text="Open Registration Table",
            command=lambda: self.load_table("Registration"),
        ).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            queue_actions,
            text="Approve + Assign",
            style="Primary.TButton",
            command=self.open_selected_application_assignment,
        ).pack(side=tk.RIGHT)
        ttk.Label(
            queue_panel,
            text="Approval alone is not enough; each accepted student needs a linked room assignment.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(2, 10))

        columns = ("application", "student", "status", "priority", "gpa", "semester", "requested", "contact")
        application_table_wrap = ttk.Frame(queue_panel, style="Panel.TFrame")
        application_table_wrap.pack(fill=tk.BOTH, expand=True)
        self.application_queue_tree = ttk.Treeview(
            application_table_wrap,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        application_scroll = ttk.Scrollbar(
            application_table_wrap,
            orient=tk.VERTICAL,
            command=self.application_queue_tree.yview,
        )
        self.application_queue_tree.configure(yscrollcommand=application_scroll.set)
        headings = {
            "application": "Application",
            "student": "Student",
            "status": "Status",
            "priority": "Priority",
            "gpa": "GPA",
            "semester": "Semester",
            "requested": "Requested dates",
            "contact": "Contact",
        }
        widths = {
            "application": 95,
            "student": 210,
            "status": 100,
            "priority": 80,
            "gpa": 70,
            "semester": 180,
            "requested": 190,
            "contact": 240,
        }
        for column in columns:
            self.application_queue_tree.heading(column, text=headings[column])
            self.application_queue_tree.column(column, width=widths[column], anchor=tk.W)
        self.application_queue_tree.grid(row=0, column=0, sticky="nsew")
        application_scroll.grid(row=0, column=1, sticky="ns")
        application_table_wrap.rowconfigure(0, weight=1)
        application_table_wrap.columnconfigure(0, weight=1)
        self.application_queue_rows = {}
        for index, row in enumerate(list_application_queue(self.db)):
            semester = " / ".join(
                value for value in [row.get("SemesterName"), row.get("AcademicYear")] if value
            ) or "—"
            requested_dates = " → ".join(
                display_value(value) for value in [row.get("StartDate"), row.get("EndDate")] if value
            ) or "—"
            contact = ", ".join(
                value for value in [row.get("PhoneNumber"), row.get("City"), row.get("Country")] if value
            ) or row.get("Email") or "—"
            item_id = f"application:{row['ApplicationID']}"
            self.application_queue_rows[item_id] = row
            self.application_queue_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    row["ApplicationID"],
                    f"{row['StudentName']} ({row['StudentID']})",
                    row["Status"],
                    row.get("Priority", "—"),
                    display_value(row.get("GPA")) or "—",
                    semester,
                    requested_dates,
                    contact,
                ),
                tags=("odd",) if index % 2 else (),
            )
        self.application_queue_tree.tag_configure("odd", background="#f6f9fc")
        self.application_queue_tree.bind(
            "<Double-1>",
            lambda _event: self.open_selected_application_assignment(),
        )

        transfer_panel = self.make_panel(wrapper, padx=16, pady=14)
        transfer_panel.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        transfer_header = ttk.Frame(transfer_panel, style="Panel.TFrame")
        transfer_header.pack(fill=tk.X)
        ttk.Label(transfer_header, text="Transfer requests awaiting move", style="Section.TLabel").pack(side=tk.LEFT)
        transfer_actions = ttk.Frame(transfer_header, style="Panel.TFrame")
        transfer_actions.pack(side=tk.RIGHT)
        ttk.Button(
            transfer_actions,
            text="Open RoomTransfer Table",
            command=lambda: self.load_table("RoomTransfer"),
        ).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            transfer_actions,
            text="Approve + Move",
            style="Primary.TButton",
            command=self.move_selected_transfer,
        ).pack(side=tk.RIGHT)
        ttk.Label(
            transfer_panel,
            text="Approving a due transfer now performs the move, closes the old assignment, and opens the new one.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(2, 10))

        transfer_columns = ("transfer", "student", "from_room", "to_room", "status", "requested", "priority")
        transfer_table_wrap = ttk.Frame(transfer_panel, style="Panel.TFrame")
        transfer_table_wrap.pack(fill=tk.BOTH, expand=True)
        self.transfer_queue_tree = ttk.Treeview(
            transfer_table_wrap,
            columns=transfer_columns,
            show="headings",
            selectmode="browse",
        )
        transfer_scroll = ttk.Scrollbar(
            transfer_table_wrap,
            orient=tk.VERTICAL,
            command=self.transfer_queue_tree.yview,
        )
        self.transfer_queue_tree.configure(yscrollcommand=transfer_scroll.set)
        transfer_headings = {
            "transfer": "Transfer",
            "student": "Student",
            "from_room": "From",
            "to_room": "To",
            "status": "Status",
            "requested": "Requested / move date",
            "priority": "Priority",
        }
        transfer_widths = {
            "transfer": 80,
            "student": 210,
            "from_room": 180,
            "to_room": 180,
            "status": 95,
            "requested": 180,
            "priority": 90,
        }
        for column in transfer_columns:
            self.transfer_queue_tree.heading(column, text=transfer_headings[column])
            self.transfer_queue_tree.column(column, width=transfer_widths[column], anchor=tk.W)
        self.transfer_queue_tree.grid(row=0, column=0, sticky="nsew")
        transfer_scroll.grid(row=0, column=1, sticky="ns")
        transfer_table_wrap.rowconfigure(0, weight=1)
        transfer_table_wrap.columnconfigure(0, weight=1)
        self.transfer_queue_rows = {}
        for index, row in enumerate(list_room_transfer_queue(self.db)):
            item_id = f"transfer:{row['TransferID']}"
            self.transfer_queue_rows[item_id] = row
            move_display = " / ".join(
                value
                for value in [
                    display_value(row.get("RequestDate")),
                    display_value(row.get("EffectiveMoveDate")) if row.get("EffectiveMoveDate") else "",
                ]
                if value
            )
            self.transfer_queue_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    row["TransferID"],
                    f"{row['StudentName']} ({row['StudentID']})",
                    f"{row['FromBuildingName']} {row['FromRoomNumber']}",
                    f"{row['ToBuildingName']} {row['ToRoomNumber']}",
                    row["Status"],
                    move_display or "—",
                    row["PriorityLevel"],
                ),
                tags=("odd",) if index % 2 else (),
            )
        self.transfer_queue_tree.tag_configure("odd", background="#f6f9fc")
        self.transfer_queue_tree.bind("<Double-1>", lambda _event: self.move_selected_transfer())

    def reconcile_housing_from_ui(self) -> None:
        try:
            result = reconcile_housing_data(self.db)
        except Exception as exc:
            messagebox.showerror("Reconcile failed", summarize_exception(exc))
            return
        self.set_status(
            "Housing data reconciled: "
            f"{result.get('inserted_logs', 0)} log(s), "
            f"{result.get('closed_logs', 0)} closed log(s), "
            f"{result.get('updated_room_occupancy', 0)} room occupancy value(s), "
            f"{result.get('updated_room_status', 0)} room status value(s), "
            f"{result.get('updated_beds', 0)} bed status value(s), "
            f"{result.get('assigned_missing_beds', 0)} missing bed(s) assigned."
        )
        self.show_housing_operations()

    def selected_application_row(self) -> dict[str, Any] | None:
        tree = getattr(self, "application_queue_tree", None)
        if tree is None:
            return None
        selected = tree.selection()
        if not selected:
            return None
        return self.application_queue_rows.get(selected[0])

    def open_selected_application_assignment(self) -> None:
        row = self.selected_application_row()
        if row is None:
            messagebox.showinfo("Select an application", "Choose an application before assigning a room.")
            return
        ApplicationAssignmentDialog(self, row)

    def selected_transfer_row(self) -> dict[str, Any] | None:
        tree = getattr(self, "transfer_queue_tree", None)
        if tree is None:
            return None
        selected = tree.selection()
        if not selected:
            return None
        return self.transfer_queue_rows.get(selected[0])

    def move_selected_transfer(self) -> None:
        row = self.selected_transfer_row()
        if row is None:
            messagebox.showinfo("Select a transfer", "Choose a transfer request before moving the student.")
            return
        try:
            new_assignment_id = complete_room_transfer(
                self.db,
                int(row["TransferID"]),
                effective_move_date=row.get("EffectiveMoveDate"),
            )
        except Exception as exc:
            messagebox.showerror("Transfer failed", summarize_exception(exc))
            return
        self.set_status(f"Completed transfer {row['TransferID']} and created assignment {new_assignment_id}.")
        self.show_housing_operations()

    def show_department(self, group_name: str) -> None:
        self.current_view = f"department:{group_name}"
        self.clear_content()
        wrapper = self.make_scrollable_page()

        header = self.make_panel(wrapper, padx=20, pady=18)
        header.pack(fill=tk.X)
        title_row = ttk.Frame(header, style="Panel.TFrame")
        title_row.pack(fill=tk.X)
        ttk.Label(title_row, text=group_name, style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(
            title_row,
            text="Refresh",
            style="Primary.TButton",
            command=lambda name=group_name: self.show_department(name),
        ).pack(side=tk.RIGHT)
        description = next(
            (item[1] for item in DEPARTMENT_SHORTCUTS if item[0] == group_name),
            "Department workspace",
        )
        ttk.Label(header, text=description, style="Subheader.TLabel").pack(anchor=tk.W, pady=(3, 0))

        if not self.db.connected:
            self.render_offline_notice(wrapper)
            return

        self.refresh_table_count_cache()
        body = self.make_panel(wrapper, padx=16, pady=14)
        body.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        ttk.Label(body, text="Department Tables", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(
            body,
            text="Choose a table to manage records for this department.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(2, 12))

        grid = tk.Frame(body, background=COLORS["panel"])
        grid.pack(fill=tk.BOTH, expand=True)
        tables = next((tables for name, tables in TABLE_GROUPS if name == group_name), [])
        for index, table_name in enumerate(tables):
            actual_table = self.resolve_table_name(table_name)
            if not actual_table:
                continue
            card = self.make_table_card(grid, actual_table)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=(0, 10), pady=(0, 10))
        for column in range(3):
            grid.columnconfigure(column, weight=1)

    def make_table_card(self, parent: tk.Widget, table_name: str) -> tk.Frame:
        card = tk.Frame(
            parent,
            background=COLORS["panel_soft"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=14,
            pady=12,
            cursor="hand2",
        )
        tk.Label(
            card,
            text=humanize_name(table_name),
            background=COLORS["panel_soft"],
            foreground=COLORS["text"],
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)
        rows = self.table_count_cache.get(table_name, "?")
        tk.Label(
            card,
            text=f"{rows} row(s)",
            background=COLORS["panel_soft"],
            foreground=COLORS["accent_dark"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(4, 8))
        ttk.Button(card, text="Manage Records", command=lambda: self.load_table(table_name)).pack(anchor=tk.W)
        card.bind("<Double-1>", lambda _event: self.load_table(table_name))
        return card

    def show_advanced_manager(self) -> None:
        self.current_view = "advanced"
        self.clear_content()
        wrapper = self.make_scrollable_page()

        header = self.make_panel(wrapper, padx=20, pady=18)
        header.pack(fill=tk.X)
        title_row = ttk.Frame(header, style="Panel.TFrame")
        title_row.pack(fill=tk.X)
        ttk.Label(title_row, text="Advanced Data Manager", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(
            title_row,
            text="Refresh",
            style="Primary.TButton",
            command=self.show_advanced_manager,
        ).pack(side=tk.RIGHT)
        ttk.Label(
            header,
            text="Direct schema-aware table access for administrators.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(3, 0))

        if not self.db.connected:
            self.render_offline_notice(wrapper)
            return

        self.refresh_table_count_cache()
        table_panel = self.make_panel(wrapper, padx=16, pady=14)
        table_panel.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        self.render_table_inventory(table_panel)

    def show_reporting_views(self) -> None:
        self.current_view = "reporting_views"
        self.clear_content()
        wrapper = self.make_scrollable_page()

        header = self.make_panel(wrapper, padx=20, pady=18)
        header.pack(fill=tk.X)
        title_row = ttk.Frame(header, style="Panel.TFrame")
        title_row.pack(fill=tk.X)
        ttk.Label(title_row, text="Reporting Views", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(
            title_row,
            text="Refresh",
            style="Primary.TButton",
            command=self.show_reporting_views,
        ).pack(side=tk.RIGHT)
        ttk.Label(
            header,
            text="Read-only analytical snapshots built from the database views in your final schema.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(3, 0))

        if not self.db.connected:
            self.render_offline_notice(wrapper)
            return

        body = self.make_panel(wrapper, padx=16, pady=14)
        body.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        ttk.Label(body, text="Available views", style="Section.TLabel").pack(anchor=tk.W)
        ttk.Label(
            body,
            text="Open a view to inspect the exact dashboard/report rows without editing source data.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(2, 12))

        grid = tk.Frame(body, background=COLORS["panel"])
        grid.pack(fill=tk.BOTH, expand=True)
        for index, view_name in enumerate(self.ordered_available_views()):
            card = self.make_view_card(grid, view_name)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=(0, 10), pady=(0, 10))
        for column in range(3):
            grid.columnconfigure(column, weight=1)

    def make_view_card(self, parent: tk.Widget, view_name: str) -> tk.Frame:
        card = tk.Frame(
            parent,
            background=COLORS["panel_soft"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=14,
            pady=12,
            cursor="hand2",
        )
        key = view_name.casefold()
        count = self.dashboard_custom_scalar(f"SELECT COUNT(*) FROM {quote_identifier(view_name)}")
        tk.Label(
            card,
            text=reporting_view_label(view_name),
            background=COLORS["panel_soft"],
            foreground=COLORS["text"],
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            card,
            text=f"{self.count_text(count)} row(s)",
            background=COLORS["panel_soft"],
            foreground=COLORS["accent_dark"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(4, 4))
        tk.Label(
            card,
            text=REPORTING_VIEW_DESCRIPTIONS.get(key, "Read-only reporting view."),
            background=COLORS["panel_soft"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 8),
            wraplength=260,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 8))
        ttk.Button(card, text="Open View", command=lambda: self.load_view(view_name)).pack(anchor=tk.W)
        card.bind("<Double-1>", lambda _event: self.load_view(view_name))
        return card

    def make_panel(self, parent: tk.Widget, padx: int = 0, pady: int = 0) -> ttk.Frame:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=(padx, pady))
        return panel

    def make_metric_card(
        self,
        parent: tk.Widget,
        label: str,
        value: str,
        color: str,
        caption: str = "",
    ) -> tk.Frame:
        card = tk.Frame(
            parent,
            background=COLORS["panel"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=14,
            pady=14,
        )
        tk.Label(
            card,
            text=label,
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            card,
            text=value,
            background=COLORS["panel"],
            foreground=color,
            font=FONTS["metric"],
        ).pack(anchor=tk.W, pady=(2, 0))
        if caption:
            tk.Label(
                card,
                text=caption,
                background=COLORS["panel"],
                foreground=COLORS["muted"],
                font=("Segoe UI", 8),
            ).pack(anchor=tk.W)
        return card

    def refresh_table_count_cache(self) -> None:
        self.table_count_cache = {}
        table_names = self.ordered_available_tables()
        try:
            self.table_count_cache = self.db.table_row_counts(table_names)
            missing_tables = [
                table_name
                for table_name in table_names
                if table_name not in self.table_count_cache
            ]
        except Exception:
            missing_tables = table_names

        for table_name in missing_tables:
            try:
                self.table_count_cache[table_name] = self.db.row_count(table_name)
            except Exception:
                self.table_count_cache[table_name] = "?"

    def render_table_inventory(self, parent: ttk.Frame, limit: int | None = None) -> None:
        table_wrap = ttk.Frame(parent, style="Panel.TFrame")
        table_wrap.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        table = ttk.Treeview(table_wrap, columns=("module", "table", "rows"), show="headings")
        table.heading("module", text="Module")
        table.heading("table", text="Table")
        table.heading("rows", text="Rows")
        table.column("module", width=170, anchor=tk.W)
        table.column("table", width=240, anchor=tk.W)
        table.column("rows", width=90, anchor=tk.E)
        y_scroll = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=table.yview)
        table.configure(yscrollcommand=y_scroll.set)
        table.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)
        table.tag_configure("odd", background="#f6f9fc")

        table_names = self.ordered_available_tables()
        if limit is not None:
            table_names = table_names[:limit]
        for index, table_name in enumerate(table_names):
            rows = self.table_count_cache.get(table_name, "?")
            table.insert(
                "",
                tk.END,
                iid=f"inventory:{table_name}",
                values=(module_for_table(table_name), humanize_name(table_name), rows),
                tags=("odd",) if index % 2 else (),
            )

        table.bind("<Double-1>", lambda _event: self.open_inventory_selection(table))

    def open_inventory_selection(self, table_widget: ttk.Treeview) -> None:
        selected = table_widget.selection()
        if not selected:
            return
        item_id = selected[0]
        if item_id.startswith("inventory:"):
            table_name = item_id.split(":", 1)[1]
            self.load_table(table_name)
            self.nav_tree.selection_set(f"table:{table_name}")

    def load_table(self, table_name: str) -> None:
        if not self.db.connected:
            self.show_dashboard()
            self.open_settings()
            return
        actual_table = self.resolve_table_name(table_name)
        if not actual_table:
            messagebox.showwarning("Table missing", f"{table_name} is not in this database.")
            return

        try:
            self.current_table = actual_table
            self.current_view = f"table:{actual_table}"
            self.current_relation_kind = "table"
            self.current_columns = self.db.table_columns(actual_table)
            self.current_foreign_keys = self.db.foreign_keys(actual_table)
            self.fk_options, self.fk_display_to_value = self.load_fk_options()
            self.render_table_editor()
            self.refresh_rows(clear_form=True)
        except Exception as exc:
            messagebox.showerror("Could not load table", summarize_exception(exc))

    def load_view(self, view_name: str) -> None:
        if not self.db.connected:
            self.show_reporting_views()
            self.open_settings()
            return
        actual_view = self.resolve_view_name(view_name)
        if not actual_view:
            messagebox.showwarning("View missing", f"{view_name} is not in this database.")
            return

        try:
            self.current_table = actual_view
            self.current_view = f"view:{actual_view}"
            self.current_relation_kind = "view"
            self.current_columns = self.db.table_columns(actual_view)
            self.current_foreign_keys = {}
            self.fk_options = {}
            self.fk_display_to_value = {}
            self.render_view_browser()
            self.refresh_rows(clear_form=False)
        except Exception as exc:
            messagebox.showerror("Could not load view", summarize_exception(exc))

    def load_fk_options(self) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
        value_to_display: dict[str, dict[str, str]] = {}
        display_to_value: dict[str, dict[str, str]] = {}

        for column_name, (ref_table, ref_column) in self.current_foreign_keys.items():
            try:
                rows = self.db.query(
                    f"SELECT * FROM {quote_identifier(ref_table)} "
                    f"ORDER BY {quote_identifier(ref_column)} LIMIT {FK_LIMIT}"
                )
            except Exception:
                continue

            value_map: dict[str, str] = {}
            display_map: dict[str, str] = {}
            for row in rows:
                raw_id = display_value(row.get(ref_column))
                label = self.build_row_label(row, ref_column)
                display = f"{raw_id} - {label}" if label and label != raw_id else raw_id
                value_map[raw_id] = display
                display_map[display] = raw_id
            value_to_display[column_name] = value_map
            display_to_value[column_name] = display_map

        return value_to_display, display_to_value

    def build_row_label(self, row: dict[str, Any], key_column: str) -> str:
        if "FirstName" in row and "LastName" in row:
            full_name = " ".join(
                part
                for part in [display_value(row["FirstName"]), display_value(row["LastName"])]
                if part
            )
            if full_name:
                return full_name

        bits = []
        for column in DISPLAY_CANDIDATES:
            if column == key_column:
                continue
            value = display_value(row.get(column))
            if value:
                bits.append(value)
            if len(bits) == 2:
                break
        return " / ".join(bits) if bits else display_value(row.get(key_column))

    def render_table_editor(self) -> None:
        self.clear_content()
        self.form_fields = {}
        self.rows_by_item = {}
        self.selected_row = None
        self.search_var.set("")
        self.form_mode_var.set("New record")

        wrapper = ttk.Frame(self.content, style="App.TFrame")
        wrapper.pack(fill=tk.BOTH, expand=True)

        header = self.make_panel(wrapper, padx=16, pady=14)
        header.pack(fill=tk.X)
        title_row = ttk.Frame(header, style="Panel.TFrame")
        title_row.pack(fill=tk.X)
        ttk.Label(title_row, text=humanize_name(self.current_table), style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            title_row,
            text=f"{module_for_table(self.current_table)} module",
            style="Subheader.TLabel",
        ).pack(side=tk.LEFT, padx=(14, 0), pady=(7, 0))

        metadata = self.table_metadata_text()
        ttk.Label(header, text=metadata, style="Subheader.TLabel").pack(anchor=tk.W, pady=(4, 0))

        toolbar = ttk.Frame(wrapper, style="App.TFrame")
        toolbar.pack(fill=tk.X, pady=(12, 10))

        search_box = tk.Frame(toolbar, background=COLORS["panel"], padx=10, pady=8)
        search_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            search_box,
            text="Search",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 8))
        search = ttk.Entry(search_box, textvariable=self.search_var)
        search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search.bind("<Return>", lambda _event: self.refresh_rows(clear_form=True))
        ttk.Button(search_box, text="Go", command=lambda: self.refresh_rows(clear_form=True)).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(toolbar, text="Refresh", command=lambda: self.refresh_rows(clear_form=True)).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(toolbar, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=(8, 0))

        pane = ttk.PanedWindow(wrapper, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        grid_panel = self.make_panel(pane, padx=10, pady=10)
        form_panel = self.make_panel(pane, padx=12, pady=12)
        pane.add(grid_panel, weight=3)
        pane.add(form_panel, weight=2)

        self.build_record_grid(grid_panel)
        self.build_record_form(form_panel)

    def render_view_browser(self) -> None:
        self.clear_content()
        self.form_fields = {}
        self.rows_by_item = {}
        self.selected_row = None
        self.search_var.set("")

        wrapper = ttk.Frame(self.content, style="App.TFrame")
        wrapper.pack(fill=tk.BOTH, expand=True)

        header = self.make_panel(wrapper, padx=16, pady=14)
        header.pack(fill=tk.X)
        title_row = ttk.Frame(header, style="Panel.TFrame")
        title_row.pack(fill=tk.X)
        ttk.Label(
            title_row,
            text=reporting_view_label(self.current_table),
            style="Header.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Label(
            title_row,
            text="read-only view",
            style="Subheader.TLabel",
        ).pack(side=tk.LEFT, padx=(14, 0), pady=(7, 0))
        ttk.Button(
            title_row,
            text="Back to Reporting Views",
            command=self.show_reporting_views,
        ).pack(side=tk.RIGHT)

        ttk.Label(
            header,
            text=REPORTING_VIEW_DESCRIPTIONS.get(
                self.current_table.casefold(),
                "Read-only reporting view from the database schema.",
            ),
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))

        toolbar = ttk.Frame(wrapper, style="App.TFrame")
        toolbar.pack(fill=tk.X, pady=(12, 10))

        search_box = tk.Frame(toolbar, background=COLORS["panel"], padx=10, pady=8)
        search_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            search_box,
            text="Search",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 8))
        search = ttk.Entry(search_box, textvariable=self.search_var)
        search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search.bind("<Return>", lambda _event: self.refresh_rows(clear_form=False))
        ttk.Button(search_box, text="Go", command=lambda: self.refresh_rows(clear_form=False)).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(toolbar, text="Refresh", command=lambda: self.refresh_rows(clear_form=False)).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(toolbar, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=(8, 0))

        grid_panel = self.make_panel(wrapper, padx=10, pady=10)
        grid_panel.pack(fill=tk.BOTH, expand=True)
        self.build_record_grid(grid_panel, bind_selection=False)

    def table_metadata_text(self) -> str:
        pk_columns = self.primary_key_columns()
        fk_count = len(self.current_foreign_keys)
        pk_text = ", ".join(pk_columns) if pk_columns else "none"
        return (
            f"{len(self.current_columns)} columns | primary key: {pk_text} | "
            f"{fk_count} relationship{'s' if fk_count != 1 else ''} | showing up to {ROW_LIMIT} rows"
        )

    def build_record_grid(self, parent: ttk.Frame, *, bind_selection: bool = True) -> None:
        top = ttk.Frame(parent, style="Panel.TFrame")
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(top, text="Records", style="Section.TLabel").pack(side=tk.LEFT)
        self.row_count_label = ttk.Label(top, text="", style="Subheader.TLabel")
        self.row_count_label.pack(side=tk.RIGHT)

        table_wrap = ttk.Frame(parent, style="Panel.TFrame")
        table_wrap.pack(fill=tk.BOTH, expand=True)
        self.record_tree = ttk.Treeview(
            table_wrap,
            columns=[column["name"] for column in self.current_columns],
            show="headings",
            selectmode="browse",
        )
        y_scroll = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=self.record_tree.yview)
        x_scroll = ttk.Scrollbar(table_wrap, orient=tk.HORIZONTAL, command=self.record_tree.xview)
        self.record_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.record_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)
        if bind_selection:
            self.record_tree.bind("<<TreeviewSelect>>", self.on_record_select)
        self.record_tree.tag_configure("odd", background="#f6f9fc")

        for column in self.current_columns:
            name = column["name"]
            self.record_tree.heading(name, text=humanize_name(name))
            self.record_tree.column(name, width=self.column_width(column), minwidth=80, stretch=False)

    def build_record_form(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Panel.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text="Record editor", style="Section.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self.form_mode_var, style="Subheader.TLabel").pack(side=tk.RIGHT)

        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.pack(fill=tk.X, pady=(10, 10))
        self.new_button = ttk.Button(actions, text="New", command=self.clear_form)
        self.add_button = ttk.Button(actions, text="Create", style="Primary.TButton", command=self.insert_record)
        self.update_button = ttk.Button(actions, text="Save Changes", command=self.update_record)
        self.delete_button = ttk.Button(actions, text="Delete", style="Danger.TButton", command=self.delete_record)
        self.new_button.pack(side=tk.LEFT, padx=(0, 7))
        self.add_button.pack(side=tk.LEFT, padx=(0, 7))
        self.update_button.pack(side=tk.LEFT, padx=(0, 7))
        self.delete_button.pack(side=tk.LEFT)

        ttk.Label(
            parent,
            text="Required fields use *. System-managed fields are locked.",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        scrollable = ScrollableFrame(parent)
        scrollable.pack(fill=tk.BOTH, expand=True)
        self.build_form_fields(scrollable.inner)
        self.update_field_states()
        self.update_action_states()

    def column_width(self, column: dict[str, Any]) -> int:
        name = column["name"]
        data_type = column["data_type"]
        if data_type in {"text", "mediumtext", "longtext"}:
            return 260
        if data_type in {"decimal", "int", "tinyint", "smallint"}:
            return max(95, len(name) * 8)
        if data_type in {"date", "datetime", "timestamp"}:
            return 150
        return min(230, max(120, len(name) * 9))

    def build_form_fields(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        for index, column in enumerate(self.current_columns):
            field = ttk.Frame(parent, style="Panel.TFrame")
            field.grid(row=index, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
            field.columnconfigure(0, weight=1)

            required = is_required_for_insert(column)
            label_text = f"{humanize_name(column['name'])}{' *' if required else ''}"
            if column["key"] == "PRI":
                label_text += "  [key]"
            elif column["name"] in self.current_foreign_keys:
                label_text += "  [link]"
            ttk.Label(field, text=label_text, style="Field.TLabel").grid(row=0, column=0, sticky=tk.W)

            widget_info = self.create_form_widget(field, column)
            widget = widget_info["widget"]
            widget.grid(row=1, column=0, sticky="ew", pady=(3, 0))
            self.form_fields[column["name"]] = widget_info

            hint = self.field_hint(column)
            if hint:
                ttk.Label(field, text=hint, style="Hint.TLabel", wraplength=430).grid(row=2, column=0, sticky=tk.W, pady=(2, 0))

    def field_hint(self, column: dict[str, Any]) -> str:
        pieces: list[str] = []
        if column["name"] in self.current_foreign_keys:
            ref_table, ref_column = self.current_foreign_keys[column["name"]]
            pieces.append(f"References {humanize_name(ref_table)}.{humanize_name(ref_column)}")
        elif column["enum_values"]:
            pieces.append("Choose one of the allowed values")
        elif is_tinyint_bool(column):
            pieces.append("0 = No, 1 = Yes")
        elif column["data_type"] in {"date", "datetime", "timestamp", "time"}:
            pieces.append(self.date_hint(column["data_type"]))
        if is_system_managed(column):
            pieces.append("managed by MySQL")
        if column.get("comment"):
            pieces.append(column["comment"])
        return " | ".join(pieces)

    def date_hint(self, data_type: str) -> str:
        if data_type == "date":
            return "Format: YYYY-MM-DD"
        if data_type == "time":
            return "Format: HH:MM:SS"
        return "Format: YYYY-MM-DD HH:MM:SS"

    def create_form_widget(self, parent: ttk.Frame, column: dict[str, Any]) -> dict[str, Any]:
        name = column["name"]
        var = tk.StringVar()
        kind = "entry"
        values: list[str] = []
        display_to_value: dict[str, str] = {}

        if column["enum_values"]:
            kind = "enum"
            values = [""] + column["enum_values"]
            widget: tk.Widget = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
        elif name in self.fk_options and self.fk_options[name]:
            kind = "fk"
            values = [""] + list(self.fk_options[name].values())
            display_to_value = self.fk_display_to_value.get(name, {})
            widget = ttk.Combobox(parent, textvariable=var, values=values, state="normal")
        elif is_tinyint_bool(column):
            kind = "bool"
            values = ["", "0 - No", "1 - Yes"]
            display_to_value = {"0 - No": "0", "1 - Yes": "1"}
            widget = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
        elif column["data_type"] in {"text", "mediumtext", "longtext"}:
            kind = "text"
            widget = tk.Text(
                parent,
                height=4,
                wrap=tk.WORD,
                relief=tk.SOLID,
                borderwidth=1,
                highlightthickness=1,
                highlightbackground=COLORS["line"],
                font=("Segoe UI", 10),
            )
        else:
            show = "*" if name.lower() in {"password", "passwordhash"} else ""
            widget = ttk.Entry(parent, textvariable=var, show=show)

        return {
            "column": column,
            "kind": kind,
            "widget": widget,
            "var": var,
            "values": values,
            "display_to_value": display_to_value,
        }

    def refresh_rows(self, clear_form: bool = False) -> None:
        if not self.current_table:
            return

        columns = [column["name"] for column in self.current_columns]
        select_cols = ", ".join(quote_identifier(column) for column in columns)
        sql = f"SELECT {select_cols} FROM {quote_identifier(self.current_table)}"
        params: list[Any] = []

        term = self.search_var.get().strip()
        if term:
            searchable = [
                column["name"]
                for column in self.current_columns
                if column["data_type"] in TEXT_TYPES or column["key"] == "PRI"
            ]
            if searchable:
                sql += " WHERE " + " OR ".join(
                    f"CAST({quote_identifier(column)} AS CHAR) LIKE %s"
                    for column in searchable
                )
                params.extend([f"%{term}%"] * len(searchable))

        pk_columns = self.primary_key_columns()
        if pk_columns:
            order_parts = ", ".join(f"{quote_identifier(column)} DESC" for column in pk_columns)
            sql += f" ORDER BY {order_parts}"
        sql += f" LIMIT {ROW_LIMIT}"

        try:
            selected_pk = self.selected_primary_key()
            rows = self.db.query(sql, params)
            self.render_rows(rows, selected_pk=selected_pk)
            if clear_form:
                self.clear_form(silent=True)
            self.row_count_label.configure(text=f"{len(rows)} row(s)")
            self.set_status(f"{self.current_table}: showing {len(rows)} row(s).")
        except Exception as exc:
            messagebox.showerror("Query failed", summarize_exception(exc))

    def selected_primary_key(self) -> tuple[Any, ...] | None:
        pk_columns = self.primary_key_columns()
        if self.selected_row is None or not pk_columns:
            return None
        return tuple(self.selected_row.get(column) for column in pk_columns)

    def render_rows(
        self,
        rows: list[dict[str, Any]],
        selected_pk: tuple[Any, ...] | None = None,
    ) -> None:
        for item in self.record_tree.get_children():
            self.record_tree.delete(item)
        self.rows_by_item = {}
        columns = [column["name"] for column in self.current_columns]
        pk_columns = self.primary_key_columns()
        item_to_reselect = None
        for index, row in enumerate(rows):
            item_id = f"row:{index}"
            self.rows_by_item[item_id] = row
            self.record_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=[display_value(row.get(column)) for column in columns],
                tags=("odd",) if index % 2 else (),
            )
            if selected_pk is not None and pk_columns:
                row_pk = tuple(row.get(column) for column in pk_columns)
                if row_pk == selected_pk:
                    item_to_reselect = item_id
        if item_to_reselect is not None:
            self.record_tree.selection_set(item_to_reselect)
            self.record_tree.focus(item_to_reselect)

    def on_record_select(self, _event: tk.Event) -> None:
        selected = self.record_tree.selection()
        if not selected:
            return
        self.selected_row = self.rows_by_item.get(selected[0])
        if self.selected_row is None:
            return
        self.populate_form(self.selected_row)
        self.form_mode_var.set("Editing selected record")
        self.update_field_states()
        self.update_action_states()

    def populate_form(self, row: dict[str, Any]) -> None:
        for name in self.form_fields:
            value = display_value(row.get(name))
            self.set_field_value(name, value)

    def set_field_value(self, name: str, value: str) -> None:
        info = self.form_fields[name]
        widget = info["widget"]
        column = info["column"]

        if info["kind"] == "text":
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            widget.insert("1.0", value)
            return

        if info["kind"] == "fk":
            value = self.fk_options.get(name, {}).get(value, value)
        elif info["kind"] == "bool":
            value = {"0": "0 - No", "1": "1 - Yes"}.get(value, value)

        self.set_widget_state(info, "normal")
        info["var"].set(value)
        self.apply_widget_state(info, self.is_field_readonly(column))

    def get_field_value(self, name: str) -> Any:
        info = self.form_fields[name]
        if info["kind"] == "text":
            raw = info["widget"].get("1.0", tk.END).strip()
        else:
            raw = info["var"].get().strip()

        if raw == "":
            return None
        if raw in info["display_to_value"]:
            return info["display_to_value"][raw]
        return raw

    def clear_form(self, silent: bool = False) -> None:
        self.selected_row = None
        self.form_mode_var.set("New record")
        if hasattr(self, "record_tree"):
            self.record_tree.selection_remove(self.record_tree.selection())
        for name, info in self.form_fields.items():
            self.set_widget_state(info, "normal")
            if info["kind"] == "text":
                info["widget"].delete("1.0", tk.END)
            else:
                info["var"].set("")
            self.apply_widget_state(info, self.is_field_readonly(info["column"]))
        self.update_action_states()
        if not silent:
            self.set_status(f"{self.current_table}: ready for a new record.")

    def set_widget_state(self, info: dict[str, Any], state: str) -> None:
        widget = info["widget"]
        if info["kind"] == "text":
            widget.configure(state="normal" if state != "disabled" else "disabled")
        elif isinstance(widget, ttk.Combobox):
            if state == "disabled":
                widget.configure(state="disabled")
            elif info["kind"] in {"enum", "bool"}:
                widget.configure(state="readonly")
            else:
                widget.configure(state="normal")
        else:
            widget.configure(state="readonly" if state == "readonly" else state)

    def apply_widget_state(self, info: dict[str, Any], readonly: bool) -> None:
        if readonly:
            self.set_widget_state(info, "disabled" if info["kind"] in {"enum", "bool", "fk"} else "readonly")
        else:
            self.set_widget_state(info, "normal")

    def update_field_states(self) -> None:
        for info in self.form_fields.values():
            self.apply_widget_state(info, self.is_field_readonly(info["column"]))

    def update_action_states(self) -> None:
        has_selection = self.selected_row is not None
        if hasattr(self, "update_button"):
            self.update_button.state(["!disabled"] if has_selection else ["disabled"])
            self.delete_button.state(["!disabled"] if has_selection else ["disabled"])

    def is_field_readonly(self, column: dict[str, Any]) -> bool:
        if is_auto_increment(column) or is_system_managed(column):
            return True
        return self.selected_row is not None and column["key"] == "PRI"

    def collect_form_data(self, for_insert: bool) -> dict[str, Any]:
        data: dict[str, Any] = {}
        errors: list[str] = []

        for column in self.current_columns:
            name = column["name"]
            if is_auto_increment(column) or is_system_managed(column):
                continue
            if not for_insert and column["key"] == "PRI":
                continue

            value = self.get_field_value(name)
            if for_insert and value is None and self.can_omit_empty_insert_value(column):
                continue

            if value is None and (for_insert or not column["nullable"]) and is_required_for_insert(column):
                errors.append(f"{humanize_name(name)} is required.")
                continue

            try:
                data[name] = self.coerce_value(column, value)
            except ValueError as exc:
                errors.append(str(exc))

        if errors:
            raise ValueError("\n".join(errors))
        return data

    def normalize_domain_data(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = data.copy()
        table = self.current_table.casefold()
        if (
            table == "registration"
            and normalized.get("Status") in {"Approved", "Rejected", "Cancelled"}
            and not normalized.get("ApprovalDate")
        ):
            normalized["ApprovalDate"] = date.today()
        if (
            table == "roomtransfer"
            and normalized.get("Status") in {"Approved", "Rejected", "Completed", "Cancelled"}
            and not normalized.get("ApprovalDate")
        ):
            normalized["ApprovalDate"] = date.today()
        if (
            table == "leavepermission"
            and normalized.get("Status") in {"Approved", "Rejected", "Cancelled"}
            and not normalized.get("ApprovalDate")
        ):
            normalized["ApprovalDate"] = date.today()
        if (
            table == "visitorpermission"
            and normalized.get("Status") in {"Approved", "Rejected", "Expired"}
            and not normalized.get("ApprovalDate")
        ):
            normalized["ApprovalDate"] = date.today()
        if (
            table == "maintenancerequest"
            and normalized.get("Status") in {"Resolved", "Closed"}
            and not normalized.get("ResolvedAt")
        ):
            normalized["ResolvedAt"] = datetime.now()
        if (
            table == "complaint"
            and normalized.get("Status") in {"Resolved", "Closed"}
            and not normalized.get("ClosedAt")
        ):
            normalized["ClosedAt"] = datetime.now()
        if (
            table == "incidentreport"
            and normalized.get("Status") in {"Resolved", "Closed"}
            and not normalized.get("ResolvedAt")
        ):
            normalized["ResolvedAt"] = datetime.now()
        if (
            table == "roomassignment"
            and normalized.get("Status") in {"Completed", "Cancelled"}
            and not normalized.get("ActualCheckOutDate")
        ):
            normalized["ActualCheckOutDate"] = date.today()
        return normalized

    def run_post_mutation_hooks(self, table_name: str) -> None:
        table = table_name.casefold()
        if table in {"roomassignment", "occupancylog", "room", "bedslot"}:
            try:
                reconcile_housing_data(self.db)
            except Exception as exc:
                self.set_status(
                    f"{table_name} changed, but housing reconciliation needs attention: {summarize_exception(exc)}"
                )
        if table in {
            "maintenancerequest",
            "complaint",
            "incidentreport",
            "registration",
            "roomtransfer",
            "roominspection",
            "leavepermission",
            "visitorpermission",
            "invoice",
            "paymenttransaction",
            "penalty",
            "mealsubscription",
            "student",
            "systemuser",
        }:
            try:
                reconcile_operational_data(self.db)
            except Exception as exc:
                self.set_status(
                    f"{table_name} changed, but operational reconciliation needs attention: {summarize_exception(exc)}"
                )

    def validate_domain_consistency(
        self,
        table_name: str,
        data: dict[str, Any],
        old_row: dict[str, Any] | None = None,
    ) -> None:
        table = table_name.casefold()

        def current(field_name: str, default: Any = None) -> Any:
            if field_name in data:
                return data[field_name]
            if old_row is not None:
                return old_row.get(field_name)
            return default

        if table == "paymenttransaction":
            invoice_id = current("InvoiceID")
            student_id = current("StudentID")
            if invoice_id and student_id:
                invoice_student_id = self.db.scalar(
                    "SELECT StudentID FROM Invoice WHERE InvoiceID = %s",
                    (invoice_id,),
                )
                if invoice_student_id and invoice_student_id != student_id:
                    raise ValueError("Payment student must match the selected invoice student.")

        elif table == "invoice":
            assignment_id = current("AssignmentID")
            student_id = current("StudentID")
            if assignment_id and student_id:
                assignment_student_id = self.db.scalar(
                    "SELECT StudentID FROM RoomAssignment WHERE AssignmentID = %s",
                    (assignment_id,),
                )
                if assignment_student_id and assignment_student_id != student_id:
                    raise ValueError("Invoice student must match the selected room assignment student.")

        elif table == "roomtransfer":
            student_id = current("StudentID")
            from_room_id = current("FromRoomID")
            to_room_id = current("ToRoomID")
            if from_room_id and to_room_id and from_room_id == to_room_id:
                raise ValueError("Transfer source room and destination room must be different.")
            if student_id and from_room_id:
                active_source_assignment = self.db.scalar(
                    """
                    SELECT COUNT(*)
                    FROM RoomAssignment
                    WHERE StudentID = %s
                      AND RoomID = %s
                      AND Status = 'Active'
                    """,
                    (student_id, from_room_id),
                )
                target_status = current("Status", "Pending")
                requires_active_source = target_status in {"Pending", "Approved"} or (
                    target_status == "Completed"
                    and (old_row is None or old_row.get("Status") != "Completed")
                )
                if not active_source_assignment and requires_active_source:
                    raise ValueError("The student must have an active assignment in the transfer source room.")
            if to_room_id and current("Status", "Pending") in {"Pending", "Approved"}:
                destination = self.db.query(
                    """
                    SELECT
                        room.Status AS RoomStatus,
                        room.Capacity,
                        COALESCE(room.CurrentOccupancy, 0) AS CurrentOccupancy,
                        building.Status AS BuildingStatus
                    FROM Room room
                    JOIN Building building ON building.BuildingID = room.BuildingID
                    WHERE room.RoomID = %s
                    """,
                    (to_room_id,),
                )
                if destination:
                    destination_row = destination[0]
                    if destination_row["BuildingStatus"] != "Active":
                        raise ValueError("Transfer destination building must be active.")
                    if destination_row["RoomStatus"] not in {"Available", "Occupied"}:
                        raise ValueError("Transfer destination room is not assignable.")
                    if destination_row["CurrentOccupancy"] >= destination_row["Capacity"]:
                        raise ValueError("Transfer destination room is already full.")
                    total_beds = self.db.scalar(
                        "SELECT COUNT(*) FROM BedSlot WHERE RoomID = %s",
                        (to_room_id,),
                    )
                    free_beds = self.db.scalar(
                        """
                        SELECT COUNT(*)
                        FROM BedSlot
                        WHERE RoomID = %s
                          AND IsOccupied = 0
                          AND IsReserved = 0
                        """,
                        (to_room_id,),
                    )
                    if total_beds and not free_beds:
                        raise ValueError("Transfer destination room has no free bed slot.")

        elif table == "roomassignment" and current("Status") == "Active":
            student_id = current("StudentID")
            assignment_id = current("AssignmentID")
            room_id = current("RoomID")
            bed_slot_id = current("BedSlotID")
            application_id = current("ApplicationID")
            if student_id:
                active_assignments = self.db.scalar(
                    """
                    SELECT COUNT(*)
                    FROM RoomAssignment
                    WHERE StudentID = %s
                      AND Status = 'Active'
                      AND (%s IS NULL OR AssignmentID <> %s)
                    """,
                    (student_id, assignment_id, assignment_id),
                )
                if active_assignments:
                    raise ValueError("This student already has another active room assignment.")
            if room_id:
                room = self.db.query(
                    """
                    SELECT
                        room.Status AS RoomStatus,
                        room.Capacity,
                        COALESCE(room.CurrentOccupancy, 0) AS CurrentOccupancy,
                        building.Status AS BuildingStatus
                    FROM Room room
                    JOIN Building building ON building.BuildingID = room.BuildingID
                    WHERE room.RoomID = %s
                    """,
                    (room_id,),
                )
                if room:
                    room_row = room[0]
                    occupied_without_current = int(room_row["CurrentOccupancy"] or 0)
                    if old_row is not None and old_row.get("Status") == "Active" and old_row.get("RoomID") == room_id:
                        occupied_without_current = max(occupied_without_current - 1, 0)
                    if room_row["BuildingStatus"] != "Active":
                        raise ValueError("Active assignments must be in an active building.")
                    if room_row["RoomStatus"] not in {"Available", "Occupied"}:
                        raise ValueError("Active assignments must use an assignable room.")
                    if occupied_without_current >= room_row["Capacity"]:
                        raise ValueError("This room is already full.")
            if application_id and student_id:
                application_student_id = self.db.scalar(
                    "SELECT StudentID FROM Registration WHERE ApplicationID = %s",
                    (application_id,),
                )
                if application_student_id and application_student_id != student_id:
                    raise ValueError("Assignment student must match the linked application student.")
            if bed_slot_id and room_id:
                bed = self.db.query(
                    """
                    SELECT RoomID, IsOccupied, IsReserved
                    FROM BedSlot
                    WHERE BedSlotID = %s
                    """,
                    (bed_slot_id,),
                )
                if not bed:
                    raise ValueError("Selected bed slot does not exist.")
                bed_row = bed[0]
                if bed_row["RoomID"] != room_id:
                    raise ValueError("Selected bed slot must belong to the selected room.")
                bed_already_used_by_other = bool(bed_row["IsOccupied"])
                if old_row is not None and old_row.get("BedSlotID") == bed_slot_id:
                    bed_already_used_by_other = False
                if bed_already_used_by_other or bed_row["IsReserved"]:
                    raise ValueError("Selected bed slot is not available.")
            elif room_id:
                total_beds = self.db.scalar(
                    "SELECT COUNT(*) FROM BedSlot WHERE RoomID = %s",
                    (room_id,),
                )
                free_beds = self.db.scalar(
                    """
                    SELECT COUNT(*)
                    FROM BedSlot
                    WHERE RoomID = %s
                      AND IsOccupied = 0
                      AND IsReserved = 0
                    """,
                    (room_id,),
                )
                if total_beds and not free_beds:
                    raise ValueError("This room has bed slots, but none are free.")

        date_ranges = {
            "registration": ("StartDate", "EndDate", "Application end date must be on or after its start date."),
            "leavepermission": ("StartDate", "EndDate", "Leave end date must be on or after its start date."),
            "visitorpermission": ("StartDate", "EndDate", "Visitor-permission end date must be on or after its start date."),
            "mealsubscription": ("StartDate", "EndDate", "Meal-subscription end date must be on or after its start date."),
        }
        if table in date_ranges:
            start_field, end_field, error_message = date_ranges[table]
            start_date = current(start_field)
            end_date = current(end_field)
            if start_date and end_date and end_date < start_date:
                raise ValueError(error_message)

        if table == "roomassignment":
            check_in_date = current("CheckInDate")
            check_out_date = current("CheckOutDate")
            actual_check_out_date = current("ActualCheckOutDate")
            if check_in_date and check_out_date and check_out_date <= check_in_date:
                raise ValueError("Scheduled checkout date must be after check-in date.")
            if check_in_date and actual_check_out_date and actual_check_out_date < check_in_date:
                raise ValueError("Actual checkout date cannot be before check-in date.")

        if table == "roomtransfer":
            request_date = current("RequestDate")
            effective_move_date = current("EffectiveMoveDate")
            if request_date and effective_move_date and effective_move_date < request_date:
                raise ValueError("Effective move date cannot be before the transfer request date.")

    def field_changed(
        self,
        old_row: dict[str, Any] | None,
        new_data: dict[str, Any],
        field_name: str,
    ) -> bool:
        return bool(old_row is not None and field_name in new_data and old_row.get(field_name) != new_data.get(field_name))

    def create_student_notification(
        self,
        student_id: str | None,
        title: str,
        message: str,
        priority: str = "Normal",
        type_name: str = "Admin Update",
    ) -> None:
        if not student_id:
            return
        self.db.execute(
            """
            INSERT INTO Notification (
                StudentID,
                Title,
                Message,
                Channel,
                Type,
                IsRead,
                PriorityLevel,
                Status
            )
            VALUES (%s, %s, %s, 'In-App', %s, 0, %s, 'Sent')
            """,
            (student_id, title, message, type_name, priority),
        )

    def emit_student_notification_for_mutation(
        self,
        table_name: str,
        operation: str,
        old_row: dict[str, Any] | None,
        new_data: dict[str, Any],
    ) -> None:
        table = table_name.casefold()

        def current(field_name: str, default: Any = None) -> Any:
            if field_name in new_data:
                return new_data.get(field_name)
            if old_row is not None:
                return old_row.get(field_name)
            return default

        title = ""
        message = ""
        priority = "Normal"
        type_name = "Admin Update"
        student_id = current("StudentID")

        if table == "penalty":
            if operation == "insert":
                title = "Penalty added"
                message = (
                    f"A {current('Type', 'penalty')} record of EGP {display_value(current('Amount', '0'))} "
                    "was added to your student record."
                )
                priority = "High"
                type_name = "Penalty"
            elif self.field_changed(old_row, new_data, "Status") or self.field_changed(old_row, new_data, "Amount"):
                title = "Penalty updated"
                message = (
                    f"Your {current('Type', 'penalty')} record is now {current('Status', 'updated')} "
                    f"with amount EGP {display_value(current('Amount', '0'))}."
                )
                priority = "High"
                type_name = "Penalty"

        elif table == "blacklist":
            if operation == "insert":
                title = "Blacklist record added"
                message = f"A blacklist record was added to your profile with status {current('Status', 'Active')}."
                priority = "Urgent"
                type_name = "Conduct"
            elif self.field_changed(old_row, new_data, "Status") or self.field_changed(old_row, new_data, "AppealStatus"):
                title = "Blacklist record updated"
                message = (
                    f"Your blacklist status is {current('Status', 'updated')}; "
                    f"appeal status: {current('AppealStatus', 'None')}."
                )
                priority = "High"
                type_name = "Conduct"

        elif table == "incidentreport":
            student_id = current("StudentID")
            if student_id and operation == "insert":
                title = "Incident report linked"
                message = f"An incident report was linked to your student record: {current('Title', 'Incident report')}."
                priority = current("SeverityLevel", "Normal")
                type_name = "Incident"
            elif student_id and self.field_changed(old_row, new_data, "Status"):
                title = "Incident report updated"
                message = f"Incident report '{current('Title', 'Incident report')}' is now {current('Status', 'updated')}."
                priority = current("SeverityLevel", "Normal")
                type_name = "Incident"

        elif table == "registration" and self.field_changed(old_row, new_data, "Status"):
            title = "Application status updated"
            message = f"Your dorm application is now {current('Status', 'updated')}."
            if current("Status") == "Approved":
                assigned = self.db.scalar(
                    """
                    SELECT COUNT(*)
                    FROM RoomAssignment
                    WHERE ApplicationID = %s
                    """,
                    (current("ApplicationID"),),
                )
                if not assigned:
                    message += " Room assignment is still pending."
            priority = "High" if current("Status") == "Approved" else "Normal"
            type_name = "Housing"

        elif table == "roomassignment" and operation == "insert":
            title = "Room assignment created"
            message = "A room assignment was added to your student record."
            priority = "High"
            type_name = "Housing"
        elif table == "roomassignment" and self.field_changed(old_row, new_data, "Status"):
            title = "Room assignment updated"
            message = f"Your room assignment is now {current('Status', 'updated')}."
            priority = "High"
            type_name = "Housing"

        elif table == "roomtransfer" and self.field_changed(old_row, new_data, "Status"):
            title = "Room transfer updated"
            message = f"Your room transfer request is now {current('Status', 'updated')}."
            priority = "High" if current("Status") in {"Approved", "Completed"} else "Normal"
            type_name = "Housing"

        elif table == "leavepermission" and self.field_changed(old_row, new_data, "Status"):
            title = "Leave request updated"
            message = f"Your leave request is now {current('Status', 'updated')}."
            type_name = "Permission"

        elif table == "visitorpermission" and self.field_changed(old_row, new_data, "Status"):
            title = "Visitor request updated"
            message = f"Your visitor request is now {current('Status', 'updated')}."
            type_name = "Permission"

        elif table == "maintenancerequest":
            student_id = current("ReportedByStudentID")
            if student_id and self.field_changed(old_row, new_data, "Status"):
                title = "Maintenance request updated"
                message = f"Maintenance request '{current('Title', 'Request')}' is now {current('Status', 'updated')}."
                type_name = "Maintenance"

        elif table == "maintenancelog" and operation == "insert":
            request_id = current("RequestID")
            if request_id:
                student_id = self.db.scalar(
                    """
                    SELECT ReportedByStudentID
                    FROM MaintenanceRequest
                    WHERE RequestID = %s
                    """,
                    (request_id,),
                )
                if student_id:
                    title = "Maintenance progress added"
                    message = "A new maintenance work-log update was added to your request."
                    type_name = "Maintenance"

        elif table == "complaint" and self.field_changed(old_row, new_data, "Status"):
            # Resolved/closed complaint notifications are already emitted by the database trigger.
            # Keep GUI notifications for intermediate status changes only to avoid duplicate student messages.
            if current("Status") not in {"Resolved", "Closed"}:
                title = "Complaint updated"
                message = f"Complaint '{current('Subject', 'Complaint')}' is now {current('Status', 'updated')}."
                type_name = "Complaint"

        elif table == "roominspection" and operation == "insert":
            room_id = current("RoomID")
            if room_id:
                student_ids = self.db.query(
                    """
                    SELECT StudentID
                    FROM RoomAssignment
                    WHERE RoomID = %s
                      AND Status = 'Active'
                    """,
                    (room_id,),
                )
                for row in student_ids:
                    try:
                        self.create_student_notification(
                            row.get("StudentID"),
                            "Room inspection recorded",
                            "A room inspection record was added for your current room.",
                            "Normal",
                            "Housing",
                        )
                    except Exception as exc:
                        self.set_status(
                            f"{table_name} saved, but a room-inspection notification could not be created: "
                            f"{summarize_exception(exc)}"
                        )
                return

        elif table == "invoice":
            if operation == "insert":
                title = "Invoice added"
                message = (
                    f"A new {current('InvoiceType', 'invoice')} invoice for "
                    f"EGP {display_value(current('TotalAmount', '0'))} was added."
                )
                type_name = "Finance"
            elif self.field_changed(old_row, new_data, "PaymentStatus"):
                title = "Invoice status updated"
                message = f"Your invoice is now {current('PaymentStatus', 'updated')}."
                type_name = "Finance"

        elif table == "paymenttransaction" and operation == "insert":
            title = "Payment recorded"
            message = (
                f"A payment of EGP {display_value(current('PaymentAmount', '0'))} "
                f"was recorded with status {current('PaymentStatus', 'Completed')}."
            )
            type_name = "Finance"

        elif table == "student" and (
            self.field_changed(old_row, new_data, "Status")
            or self.field_changed(old_row, new_data, "DisciplinaryStatus")
        ):
            student_id = current("StudentID")
            title = "Student record updated"
            message = (
                f"Student status: {current('Status', 'updated')}; "
                f"disciplinary status: {current('DisciplinaryStatus', 'updated')}."
            )
            priority = "High" if current("DisciplinaryStatus") not in {None, "Clear"} else "Normal"
            type_name = "Student Record"

        if title and student_id:
            try:
                self.create_student_notification(student_id, title, message, priority, type_name)
            except Exception as exc:
                self.set_status(
                    f"{table_name} saved, but the student notification could not be created: {summarize_exception(exc)}"
                )

    def can_omit_empty_insert_value(self, column: dict[str, Any]) -> bool:
        return column["default"] is not None or column["nullable"]

    def coerce_value(self, column: dict[str, Any], value: Any) -> Any:
        if value is None:
            return None

        data_type = column["data_type"]
        name = humanize_name(column["name"])
        text = str(value).strip()

        try:
            if data_type in {"int", "tinyint", "smallint", "mediumint", "bigint"}:
                return int(text)
            if data_type in {"decimal", "numeric", "float", "double"}:
                return Decimal(text)
            if data_type == "date":
                return date.fromisoformat(text)
            if data_type in {"datetime", "timestamp"}:
                normalized = text.replace("T", " ")
                return datetime.fromisoformat(normalized)
            if data_type == "time":
                return time.fromisoformat(text)
            if data_type == "year":
                year = int(text)
                if year < 1901 or year > 2155:
                    raise ValueError
                return year
        except (ValueError, InvalidOperation) as exc:
            expected = column["column_type"]
            raise ValueError(f"{name} must match {expected}.") from exc

        return text

    def insert_record(self) -> None:
        try:
            data = self.normalize_domain_data(self.collect_form_data(for_insert=True))
            self.validate_domain_consistency(self.current_table, data)
        except ValueError as exc:
            messagebox.showwarning("Check the form", str(exc))
            return

        if not data:
            messagebox.showinfo("Nothing to add", "Fill in at least one editable field first.")
            return

        columns = list(data.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        column_sql = ", ".join(quote_identifier(column) for column in columns)
        sql = (
            f"INSERT INTO {quote_identifier(self.current_table)} "
            f"({column_sql}) VALUES ({placeholders})"
        )
        try:
            self.db.execute(sql, [data[column] for column in columns])
            self.emit_student_notification_for_mutation(
                self.current_table,
                "insert",
                None,
                data,
            )
            self.run_post_mutation_hooks(self.current_table)
            self.refresh_rows(clear_form=True)
            self.set_status(f"Added record to {self.current_table}.")
        except Exception as exc:
            messagebox.showerror("Insert failed", summarize_exception(exc))

    def update_record(self) -> None:
        if self.selected_row is None:
            messagebox.showinfo("Select a record", "Select an existing row before updating.")
            return

        pk_columns = self.primary_key_columns()
        if not pk_columns:
            messagebox.showwarning(
                "No primary key",
                f"{self.current_table} has no primary key, so this app cannot update it safely.",
            )
            return

        try:
            data = self.normalize_domain_data(self.collect_form_data(for_insert=False))
            self.validate_domain_consistency(self.current_table, data, self.selected_row)
        except ValueError as exc:
            messagebox.showwarning("Check the form", str(exc))
            return

        update_columns = list(data.keys())
        if not update_columns:
            messagebox.showinfo("Nothing to update", "There are no editable fields to update.")
            return

        if (
            self.current_table.casefold() == "registration"
            and self.field_changed(self.selected_row, data, "Status")
            and data.get("Status") == "Approved"
        ):
            assigned_count = self.db.scalar(
                """
                SELECT COUNT(*)
                FROM RoomAssignment
                WHERE ApplicationID = %s
                """,
                (self.selected_row.get("ApplicationID"),),
            )
            if not assigned_count:
                messagebox.showwarning(
                    "Use Housing Operations",
                    "Approve this application with a room assignment from Housing Operations > Approve + Assign "
                    "so the student record, occupancy, and website stay consistent.",
                )
                return

        if (
            self.current_table.casefold() == "roomtransfer"
            and self.field_changed(self.selected_row, data, "Status")
            and data.get("Status") in {"Approved", "Completed"}
            and (
                data.get("Status") == "Completed"
                or data.get("EffectiveMoveDate") is None
                or (
                    isinstance(data.get("EffectiveMoveDate"), date)
                    and data.get("EffectiveMoveDate") <= date.today()
                )
            )
        ):
            try:
                new_assignment_id = complete_room_transfer(
                    self.db,
                    int(self.selected_row["TransferID"]),
                    effective_move_date=data.get("EffectiveMoveDate"),
                    notes=data.get("Notes"),
                )
                extra_transfer_fields = {
                    field_name: data[field_name]
                    for field_name in ("ApprovedBy", "ApprovalDate", "Reason", "PriorityLevel")
                    if field_name in data
                }
                if extra_transfer_fields:
                    set_sql = ", ".join(
                        f"{quote_identifier(field_name)} = %s"
                        for field_name in extra_transfer_fields
                    )
                    params = list(extra_transfer_fields.values()) + [self.selected_row["TransferID"]]
                    self.db.execute(
                        f"UPDATE RoomTransfer SET {set_sql} WHERE TransferID = %s",
                        params,
                    )
                self.run_post_mutation_hooks(self.current_table)
                self.refresh_rows(clear_form=True)
                self.set_status(
                    f"Completed room transfer and created assignment {new_assignment_id}."
                )
            except Exception as exc:
                messagebox.showerror("Transfer completion failed", summarize_exception(exc))
            return

        set_sql = ", ".join(f"{quote_identifier(column)} = %s" for column in update_columns)
        where_sql = " AND ".join(f"{quote_identifier(column)} = %s" for column in pk_columns)
        params = [data[column] for column in update_columns]
        params.extend(self.selected_row[column] for column in pk_columns)
        sql = (
            f"UPDATE {quote_identifier(self.current_table)} "
            f"SET {set_sql} WHERE {where_sql}"
        )

        try:
            old_row = self.selected_row.copy()
            affected = self.db.execute(sql, params)
            self.emit_student_notification_for_mutation(
                self.current_table,
                "update",
                old_row,
                data,
            )
            self.run_post_mutation_hooks(self.current_table)
            self.refresh_rows(clear_form=True)
            self.set_status(f"Updated {affected} row(s) in {self.current_table}.")
        except Exception as exc:
            messagebox.showerror("Update failed", summarize_exception(exc))

    def _get_child_tables(self, table_name: str) -> list[tuple[str, str, str]]:
        """Return list of (child_table, child_column, parent_column) referencing this table."""
        try:
            rows = self.db.query(
                """
                SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND REFERENCED_TABLE_NAME = %s
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """,
                (table_name,),
            )
            return [(r["TABLE_NAME"], r["COLUMN_NAME"], r["REFERENCED_COLUMN_NAME"]) for r in rows]
        except Exception:
            return []

    def _cascade_delete(self, table_name: str, pk_columns: list[str], row: dict[str, Any]) -> int:
        """Delete a record and all child records that reference it."""
        pk_values = [row[column] for column in pk_columns]
        where_sql = " AND ".join(f"{quote_identifier(column)} = %s" for column in pk_columns)
        delete_sql = f"DELETE FROM {quote_identifier(table_name)} WHERE {where_sql}"

        # Special pre-handling for RoomAssignment
        if table_name.casefold() == "roomassignment":
            assignment_id = row.get("AssignmentID")
            if assignment_id is not None:
                self.db.execute(
                    """
                    UPDATE OccupancyLog
                    SET EndDate = COALESCE(EndDate, CURDATE())
                    WHERE AssignmentID = %s
                      AND EndDate IS NULL
                    """,
                    (assignment_id,),
                )

        # Try direct delete first
        try:
            return self.db.execute(delete_sql, pk_values)
        except Exception as exc:
            error_text = str(exc).lower()
            if "foreign key" not in error_text and "constraint" not in error_text:
                raise

        # Cascade: find and delete child records first
        children = self._get_child_tables(table_name)
        if not children:
            raise

        deleted_children = 0
        for child_table, child_column, parent_column in children:
            if child_table.casefold() == table_name.casefold():
                continue
            try:
                child_rows = self.db.query(
                    f"SELECT * FROM {quote_identifier(child_table)} WHERE {quote_identifier(child_column)} = %s",
                    (row.get(parent_column),),
                )
                for child_row in child_rows:
                    child_pk = self.db.query(
                        """
                        SELECT COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s
                          AND CONSTRAINT_NAME = 'PRIMARY'
                        ORDER BY ORDINAL_POSITION
                        """,
                        (child_table,),
                    )
                    child_pk_columns = [r["COLUMN_NAME"] for r in child_pk]
                    if child_pk_columns:
                        deleted_children += self._cascade_delete(child_table, child_pk_columns, child_row)
            except Exception:
                continue

        # Retry parent delete after children are gone
        return self.db.execute(delete_sql, pk_values)

    def delete_record(self) -> None:
        if self.selected_row is None:
            messagebox.showinfo("Select a record", "Select an existing row before deleting.")
            return

        pk_columns = self.primary_key_columns()
        if not pk_columns:
            messagebox.showwarning(
                "No primary key",
                f"{self.current_table} has no primary key, so this app cannot delete it safely.",
            )
            return

        label = ", ".join(
            f"{humanize_name(column)}={display_value(self.selected_row[column])}"
            for column in pk_columns
        )
        if not messagebox.askyesno("Delete record", f"Delete this {humanize_name(self.current_table)} record and all linked child records?\n\n{label}"):
            return

        try:
            affected = self._cascade_delete(self.current_table, pk_columns, self.selected_row)
            self.run_post_mutation_hooks(self.current_table)
            self.refresh_rows(clear_form=True)
            self.set_status(f"Deleted {affected} row(s) from {self.current_table}.")
        except Exception as exc:
            messagebox.showerror("Delete failed", summarize_exception(exc))

    def export_csv(self) -> None:
        if not self.rows_by_item:
            messagebox.showinfo("Nothing to export", "Refresh or search for rows first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export visible rows",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{self.current_table}.csv",
        )
        if not path:
            return

        columns = [column["name"] for column in self.current_columns]
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                for row in self.rows_by_item.values():
                    writer.writerow({column: display_value(row.get(column)) for column in columns})
            self.set_status(f"Exported visible rows to {path}")
        except OSError as exc:
            messagebox.showerror("Export failed", summarize_exception(exc))

    def primary_key_columns(self) -> list[str]:
        return [column["name"] for column in self.current_columns if column["key"] == "PRI"]

    def on_close(self) -> None:
        self.db.close()
        self.destroy()


def main() -> None:
    app = GUDormsAdminApp()
    app.mainloop()


if __name__ == "__main__":
    main()
