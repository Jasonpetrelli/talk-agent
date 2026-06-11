"""初始化数据库并写入示例数据"""
import sqlite3

DB_PATH = "data.db"

def init():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # 供应商
    cur.execute("""CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # 商品
    cur.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT NOT NULL UNIQUE,
        product_name TEXT NOT NULL,
        category TEXT,
        weight_kg REAL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # 供应商报价
    cur.execute("""CREATE TABLE IF NOT EXISTS supplier_quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        product_code TEXT NOT NULL,
        base_price REAL NOT NULL,
        suggested_price REAL,
        is_preferred INTEGER DEFAULT 0,
        effective_date DATE NOT NULL,
        expire_date DATE,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
    )""")

    # 客户
    cur.execute("""CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_user_id TEXT UNIQUE,
        company_name TEXT,
        contact_name TEXT,
        phone TEXT,
        customer_level TEXT DEFAULT 'bronze',
        price_factor REAL DEFAULT 1.3,
        total_gmv REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # 运费规则
    cur.execute("""CREATE TABLE IF NOT EXISTS shipping_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        region_value TEXT NOT NULL,
        first_weight_kg REAL DEFAULT 1.0,
        first_price REAL NOT NULL,
        additional_weight_kg REAL DEFAULT 1.0,
        additional_price REAL,
        priority INTEGER DEFAULT 0
    )""")

    # 订单
    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        product_code TEXT,
        quantity INTEGER,
        total_gmv REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )""")

    # 对话记录
    cur.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id TEXT,
        raw_message TEXT,
        parsed_intent TEXT,
        extracted_params TEXT,
        final_reply TEXT,
        quote_generated REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # 人工介入
    cur.execute("""CREATE TABLE IF NOT EXISTS human_intervention (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        trigger_reason TEXT,
        customer_message TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )""")

    # ===== 示例数据 =====

    suppliers = [
        (1, "永康厨具", "13800001001"),
        (2, "美的电器", "13800001002"),
    ]
    cur.executemany("INSERT OR REPLACE INTO suppliers (id, name, contact_phone) VALUES (?, ?, ?)", suppliers)

    products = [
        ("ABC-100", "保温杯500ml", "日用", 0.3),
        ("DEF-200", "电热水壶1.5L", "家电", 1.2),
        ("GHI-300", "不锈钢炒锅32cm", "厨具", 2.5),
    ]
    cur.executemany("INSERT OR REPLACE INTO products (product_code, product_name, category, weight_kg, is_active) VALUES (?, ?, ?, ?, 1)", products)

    quotes = [
        (1, "ABC-100", 12.5, 19.9, 1, "2026-06-01", None),
        (2, "ABC-100", 13.0, 20.5, 0, "2026-06-01", None),
        (1, "DEF-200", 45.0, 79.0, 0, "2026-06-01", None),
        (2, "DEF-200", 43.0, 75.0, 1, "2026-06-01", None),
        (1, "GHI-300", 58.0, 99.0, 1, "2026-06-01", None),
    ]
    cur.executemany("INSERT OR REPLACE INTO supplier_quotes (supplier_id, product_code, base_price, suggested_price, is_preferred, effective_date, expire_date) VALUES (?, ?, ?, ?, ?, ?, ?)", quotes)

    customers = [
        (1, "wx_linchen", "凌晨公司", "张经理", "13900001111", "gold", 1.15, 125000),
        (2, "wx_chuangcheng", "创成商贸", "李总", "13900002222", "silver", 1.25, 68000),
        (3, "wx_trial", "试用客户", "小王", "13900003333", "trial", 1.30, 0),
    ]
    cur.executemany("INSERT OR REPLACE INTO customers (id, external_user_id, company_name, contact_name, phone, customer_level, price_factor, total_gmv) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", customers)

    shipping = [
        ("江浙沪", 1.0, 5.0, 1.0, 2.0, 1),
        ("非江浙沪", 1.0, 10.0, 1.0, 3.0, 2),
        ("全国", 1.0, 8.0, 1.0, 2.5, 3),
    ]
    cur.executemany("INSERT OR REPLACE INTO shipping_rules (region_value, first_weight_kg, first_price, additional_weight_kg, additional_price, priority) VALUES (?, ?, ?, ?, ?, ?)", shipping)

    orders = [
        (1, 1, "ABC-100", 200, 3980, "2026-06-10 09:30:00"),
        (2, 2, "DEF-200", 50, 3750, "2026-06-10 10:15:00"),
        (3, 1, "GHI-300", 30, 2970, "2026-06-09 14:00:00"),
    ]
    cur.executemany("INSERT OR REPLACE INTO orders (id, customer_id, product_code, quantity, total_gmv, created_at) VALUES (?, ?, ?, ?, ?, ?)", orders)

    conn.commit()
    conn.close()
    print("数据库初始化完成 → data.db")

if __name__ == "__main__":
    init()