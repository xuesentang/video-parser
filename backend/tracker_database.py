"""博主追踪系统 - 数据库层
新增3张表：creators(博主)、subscriptions(用户订阅)、reports(报告)
复用现有 database.py 的 get_db() 连接管理
"""

from datetime import datetime, timezone
from database import get_db


# ============================================================
# 建表
# ============================================================

def init_tracker_tables():
    """初始化追踪系统相关表（幂等，重复调用不会报错）"""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS creators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                avatar_url TEXT DEFAULT '',
                description TEXT DEFAULT '',
                home_url TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                last_checked_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(platform, platform_id)
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                creator_id INTEGER NOT NULL,
                alias TEXT DEFAULT '',
                group_tag TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, creator_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (creator_id) REFERENCES creators(id)
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                report_date TEXT NOT NULL,
                time_range_hours INTEGER DEFAULT 24,
                content_markdown TEXT DEFAULT '',
                status TEXT DEFAULT 'generating',
                video_count INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                progress_current INTEGER DEFAULT 0,
                progress_total INTEGER DEFAULT 0,
                current_creator TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_creators_platform
                ON creators(platform, platform_id);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_user
                ON subscriptions(user_id);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_user_creator
                ON subscriptions(user_id, creator_id);
            CREATE INDEX IF NOT EXISTS idx_reports_user
                ON reports(user_id, report_date);
        """)

        try:
            conn.execute("ALTER TABLE reports ADD COLUMN progress_current INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE reports ADD COLUMN progress_total INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE reports ADD COLUMN current_creator TEXT DEFAULT ''")
        except Exception:
            pass


# ============================================================
# creators CRUD
# ============================================================

def get_or_create_creator(platform: str, platform_id: str, name: str = "",
                           avatar_url: str = "", description: str = "",
                           home_url: str = "") -> dict:
    """获取或创建博主，返回博主记录字典"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM creators WHERE platform = ? AND platform_id = ?",
            (platform, platform_id),
        ).fetchone()

        if row:
            # 更新博主信息（名称/头像/简介可能变化）
            conn.execute(
                """UPDATE creators
                   SET name = ?, avatar_url = ?, description = ?, home_url = ?,
                       status = 'active', updated_at = datetime('now')
                   WHERE id = ?""",
                (name, avatar_url, description, home_url, row["id"]),
            )
            return dict(row) | {"name": name, "avatar_url": avatar_url,
                                "description": description, "home_url": home_url}

        cursor = conn.execute(
            """INSERT INTO creators (platform, platform_id, name, avatar_url, description, home_url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (platform, platform_id, name, avatar_url, description, home_url),
        )
        return {
            "id": cursor.lastrowid, "platform": platform,
            "platform_id": platform_id, "name": name,
            "avatar_url": avatar_url, "description": description,
            "home_url": home_url, "status": "active",
        }


def get_creator_by_id(creator_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM creators WHERE id = ?", (creator_id,)).fetchone()
        return dict(row) if row else None


def update_creator_status(creator_id: int, status: str):
    """更新博主状态（active/invalid）"""
    with get_db() as conn:
        conn.execute(
            "UPDATE creators SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, creator_id),
        )


def update_creator_checked(creator_id: int):
    """更新博主最后检测时间"""
    with get_db() as conn:
        conn.execute(
            "UPDATE creators SET last_checked_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (creator_id,),
        )


# ============================================================
# subscriptions CRUD
# ============================================================

def add_subscription(user_id: int, creator_id: int, alias: str = "",
                     group_tag: str = "") -> dict:
    """添加订阅，返回订阅记录。如已存在则抛出 ValueError"""
    with get_db() as conn:
        # 检查是否已订阅
        existing = conn.execute(
            "SELECT id FROM subscriptions WHERE user_id = ? AND creator_id = ?",
            (user_id, creator_id),
        ).fetchone()
        if existing:
            raise ValueError("已订阅该博主")

        cursor = conn.execute(
            """INSERT INTO subscriptions (user_id, creator_id, alias, group_tag)
               VALUES (?, ?, ?, ?)""",
            (user_id, creator_id, alias, group_tag),
        )
        return {"id": cursor.lastrowid, "user_id": user_id,
                "creator_id": creator_id, "alias": alias, "group_tag": group_tag}


def get_user_subscriptions(user_id: int) -> list[dict]:
    """获取用户全部订阅，附带博主信息"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT s.id as sub_id, s.alias, s.group_tag, s.created_at as sub_created_at,
                      c.id as creator_id, c.platform, c.platform_id,
                      c.name, c.avatar_url, c.description, c.home_url,
                      c.status, c.last_checked_at
               FROM subscriptions s
               JOIN creators c ON s.creator_id = c.id
               WHERE s.user_id = ?
               ORDER BY c.platform, c.name""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_subscription_by_id(sub_id: int, user_id: int) -> dict | None:
    """获取指定订阅（带博主信息），限制用户"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT s.id as sub_id, s.alias, s.group_tag, s.created_at as sub_created_at,
                      c.id as creator_id, c.platform, c.platform_id,
                      c.name, c.avatar_url, c.description, c.home_url,
                      c.status, c.last_checked_at
               FROM subscriptions s
               JOIN creators c ON s.creator_id = c.id
               WHERE s.id = ? AND s.user_id = ?""",
            (sub_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def update_subscription(sub_id: int, user_id: int, alias: str = None,
                        group_tag: str = None):
    """更新订阅的别名/分组，仅更新非 None 字段"""
    with get_db() as conn:
        sets, params = [], []
        if alias is not None:
            sets.append("alias = ?")
            params.append(alias)
        if group_tag is not None:
            sets.append("group_tag = ?")
            params.append(group_tag)
        if not sets:
            return
        params.append(sub_id)
        params.append(user_id)
        conn.execute(
            f"UPDATE subscriptions SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
            params,
        )


def delete_subscription(sub_id: int, user_id: int) -> bool:
    """删除订阅，返回是否成功"""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id = ?",
            (sub_id, user_id),
        )
        return cursor.rowcount > 0


def get_user_subscribed_creators(user_id: int) -> list[dict]:
    """获取用户订阅的全部博主（用于报告生成），仅返回 active 博主"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT DISTINCT c.*
               FROM subscriptions s
               JOIN creators c ON s.creator_id = c.id
               WHERE s.user_id = ? AND c.status = 'active'
               ORDER BY c.platform""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# reports CRUD
# ============================================================

def create_report(user_id: int, report_date: str, time_range_hours: int = 24) -> dict:
    """创建一条报告记录（状态为 generating）"""
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO reports (user_id, report_date, time_range_hours, status)
               VALUES (?, ?, ?, 'generating')""",
            (user_id, report_date, time_range_hours),
        )
        return {"id": cursor.lastrowid, "user_id": user_id,
                "report_date": report_date, "status": "generating"}


def update_report_content(report_id: int, content_markdown: str,
                          video_count: int, status: str = "completed",
                          error_message: str = ""):
    """更新报告内容"""
    with get_db() as conn:
        conn.execute(
            """UPDATE reports
               SET content_markdown = ?, video_count = ?, status = ?, error_message = ?,
                   created_at = datetime('now')
               WHERE id = ?""",
            (content_markdown, video_count, status, error_message, report_id),
        )


def update_report_progress(report_id: int, current: int, total: int, current_creator: str = ""):
    """更新报告生成进度（供前端轮询）"""
    with get_db() as conn:
        conn.execute(
            """UPDATE reports
               SET progress_current = ?, progress_total = ?, current_creator = ?
               WHERE id = ?""",
            (current, total, current_creator, report_id),
        )


def fail_report(report_id: int, error_message: str):
    """标记报告生成失败"""
    with get_db() as conn:
        conn.execute(
            "UPDATE reports SET status = 'failed', error_message = ? WHERE id = ?",
            (error_message, report_id),
        )


def get_user_reports(user_id: int, limit: int = 20, offset: int = 0) -> list[dict]:
    """获取用户报告列表（按日期倒序，不含 content_markdown 大字段）"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, user_id, report_date, time_range_hours,
                      status, video_count, error_message,
                      progress_current, progress_total, current_creator,
                      created_at
               FROM reports
               WHERE user_id = ?
               ORDER BY report_date DESC, id DESC
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_report(report_id: int, user_id: int) -> bool:
    """删除报告，返回是否成功"""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM reports WHERE id = ? AND user_id = ?",
            (report_id, user_id),
        )
        return cursor.rowcount > 0


def get_report_by_id(report_id: int, user_id: int) -> dict | None:
    """获取报告详情（含 content_markdown）"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE id = ? AND user_id = ?",
            (report_id, user_id),
        ).fetchone()
        return dict(row) if row else None


# ============================================================
# settings（用简单 KV 表存储用户定时配置）
# ============================================================

def init_tracker_settings_table():
    """创建 tracker_settings KV 表"""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracker_settings (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)


def get_tracker_setting(user_id: int, key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM tracker_settings WHERE user_id = ? AND key = ?",
            (user_id, key),
        ).fetchone()
        return row["value"] if row else default


def set_tracker_setting(user_id: int, key: str, value: str):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO tracker_settings (user_id, key, value)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value""",
            (user_id, key, value),
        )


def get_user_tracker_settings(user_id: int) -> dict:
    """获取用户全部追踪设置"""
    defaults = {
        "schedule_time": "12:00",
        "time_range_hours": "24",
        "enabled": "true",
    }
    with get_db() as conn:
        rows = conn.execute(
            "SELECT key, value FROM tracker_settings WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        result = dict(defaults)
        for r in rows:
            result[r["key"]] = r["value"]
    return result
