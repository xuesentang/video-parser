import os
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")


def get_db_path():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


VIP_EMAIL = "18300618398@163.com"
NORMAL_USER_USAGE_LIMIT = 20


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_vip INTEGER DEFAULT 0,
                vip_expire_at TEXT,
                usage_count INTEGER DEFAULT 0,
                daily_summary_count INTEGER DEFAULT 0,
                last_summary_date TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'cny',
                status TEXT DEFAULT 'pending',
                plan_type TEXT DEFAULT 'monthly',
                stripe_session_id TEXT UNIQUE,
                stripe_payment_intent_id TEXT,
                paid_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_order_no ON orders(order_no);
            CREATE INDEX IF NOT EXISTS idx_orders_stripe_session_id ON orders(stripe_session_id);
        """)

        # 迁移：如果 usage_count 字段不存在，则添加
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "usage_count" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN usage_count INTEGER DEFAULT 0")

        # 确保 VIP 用户（指定邮箱）拥有永久 VIP 权限并设置默认密码
        from auth import hash_password
        vip_user = conn.execute("SELECT * FROM users WHERE email = ?", (VIP_EMAIL,)).fetchone()
        if not vip_user:
            # 创建 VIP 用户，密码为 985211
            conn.execute(
                "INSERT INTO users (email, password_hash, is_vip, vip_expire_at) VALUES (?, ?, ?, ?)",
                (VIP_EMAIL, hash_password("985211"), 1, "2099-12-31T23:59:59"),
            )
        else:
            # 更新现有 VIP 用户的密码和状态
            conn.execute(
                "UPDATE users SET password_hash = ?, is_vip = 1, vip_expire_at = ?, updated_at = datetime('now') WHERE email = ?",
                (hash_password("985211"), "2099-12-31T23:59:59", VIP_EMAIL),
            )


FREE_DAILY_SUMMARY_LIMIT = 3


def get_user_by_email(email: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_user(email: str, password_hash: str) -> dict:
    """创建用户，VIP邮箱自动获得永久VIP权限"""
    is_vip = 1 if email.lower() == VIP_EMAIL.lower() else 0
    vip_expire_at = "2099-12-31T23:59:59" if is_vip else None
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, is_vip, vip_expire_at) VALUES (?, ?, ?, ?)",
            (email, password_hash, is_vip, vip_expire_at),
        )
        return {"id": cursor.lastrowid, "email": email, "is_vip": is_vip, "vip_expire_at": vip_expire_at}


def check_and_increment_summary(user_id: int) -> tuple[bool, int]:
    """
    检查用户是否可以使用 AI 总结，并自增计数。
    VIP 用户无限使用，普通用户使用统一的 usage_count 额度。
    返回 (allowed, remaining_count)
    """
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return False, 0

        # VIP 用户无限使用
        if user["is_vip"] and user["vip_expire_at"]:
            expire = datetime.fromisoformat(user["vip_expire_at"])
            if expire.tzinfo is None:  # 如果没有时区信息
                expire = expire.replace(tzinfo=timezone.utc)  # 添加 UTC 时区
            if expire > datetime.now(timezone.utc):
                return True, -1  # -1 means unlimited

        # 普通用户使用统一额度
        current = user["usage_count"] or 0
        if current >= NORMAL_USER_USAGE_LIMIT:
            return False, NORMAL_USER_USAGE_LIMIT - current

        conn.execute(
            "UPDATE users SET usage_count = usage_count + 1, updated_at = datetime('now') WHERE id = ?",
            (user_id,),
        )
        return True, NORMAL_USER_USAGE_LIMIT - current - 1


def check_and_increment_usage(user_id: int) -> tuple[bool, int]:
    """
    检查用户是否可以使用视频解析/下载功能，并自增计数。
    VIP 用户无限使用，普通用户只有20次额度。
    返回 (allowed, remaining_count)
    """
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return False, 0

        # VIP 用户无限使用
        if user["is_vip"] and user["vip_expire_at"]:
            expire = datetime.fromisoformat(user["vip_expire_at"])
            if expire.tzinfo is None:  # 如果没有时区信息
                expire = expire.replace(tzinfo=timezone.utc)  # 添加 UTC 时区
            if expire > datetime.now(timezone.utc):
                return True, -1  # -1 means unlimited

        # 普通用户检查额度
        current = user["usage_count"] or 0
        if current >= NORMAL_USER_USAGE_LIMIT:
            return False, 0

        conn.execute(
            "UPDATE users SET usage_count = usage_count + 1, updated_at = datetime('now') WHERE id = ?",
            (user_id,),
        )
        return True, NORMAL_USER_USAGE_LIMIT - current - 1


def get_user_usage(user_id: int) -> int:
    """获取用户已使用次数"""
    with get_db() as conn:
        user = conn.execute("SELECT usage_count FROM users WHERE id = ?", (user_id,)).fetchone()
        return user["usage_count"] if user else 0


def create_order(user_id: int, order_no: str, amount: int, currency: str = "cny", plan_type: str = "monthly") -> dict:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO orders (order_no, user_id, amount, currency, plan_type) VALUES (?, ?, ?, ?, ?)",
            (order_no, user_id, amount, currency, plan_type),
        )
        return {"order_no": order_no, "user_id": user_id, "amount": amount}


def update_order_stripe_session(order_no: str, session_id: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE orders SET stripe_session_id = ?, updated_at = datetime('now') WHERE order_no = ?",
            (session_id, order_no),
        )


def complete_order(session_id: str, payment_intent_id: str) -> dict | None:
    """
    支付完成时更新订单状态、激活 VIP。
    使用事务保证幂等：只有 pending 状态的订单才会被更新。
    """
    with get_db() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE stripe_session_id = ? AND status = 'pending'",
            (session_id,),
        ).fetchone()

        if not order:
            return None

        now = datetime.now(timezone.utc).isoformat()

        from dateutil.relativedelta import relativedelta
        user = conn.execute("SELECT * FROM users WHERE id = ?", (order["user_id"],)).fetchone()

        current_expire = None
        if user["vip_expire_at"]:
            try:
                current_expire = datetime.fromisoformat(user["vip_expire_at"])
            except ValueError:
                pass

        base_time = datetime.now(timezone.utc)
        if current_expire and current_expire > base_time:
            base_time = current_expire

        if order["plan_type"] == "monthly":
            new_expire = base_time + relativedelta(months=1)
        elif order["plan_type"] == "yearly":
            new_expire = base_time + relativedelta(years=1)
        else:
            new_expire = base_time + relativedelta(months=1)

        conn.execute(
            "UPDATE orders SET status = 'paid', stripe_payment_intent_id = ?, paid_at = ?, updated_at = ? WHERE id = ?",
            (payment_intent_id, now, now, order["id"]),
        )

        conn.execute(
            "UPDATE users SET is_vip = 1, vip_expire_at = ?, updated_at = ? WHERE id = ?",
            (new_expire.isoformat(), now, order["user_id"]),
        )

        return dict(order)


def get_order_by_no(order_no: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()
        return dict(row) if row else None


def get_user_orders(user_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
