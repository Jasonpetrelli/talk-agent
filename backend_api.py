"""
数据层 API 服务 - 数据读写 + 数据库操作
启动: uvicorn backend_api:app --host 0.0.0.0 --port 8000 --reload
"""

import sqlite3
from datetime import date, datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="询报价数据服务")

DB_PATH = "data.db"

# ---------- 模型 ----------

class PriceUpdateRequest(BaseModel):
    product_code: str
    supplier_id: int
    new_price: float

class CustomerUpdateFactor(BaseModel):
    company_name: str
    price_factor: float

# ---------- 数据库工具 ----------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- 商品报价 ----------

@app.get("/api/admin/price")
def query_price(product_code: str):
    """查询商品推荐报价"""
    conn = get_db()
    try:
        # 先精确匹配
        cur = conn.execute("""
            SELECT sq.base_price, s.name AS supplier_name, sq.suggested_price
            FROM supplier_quotes sq
            JOIN suppliers s ON sq.supplier_id = s.id
            WHERE sq.product_code = ? AND sq.is_preferred = 1
              AND (sq.expire_date IS NULL OR sq.expire_date > date())
            ORDER BY sq.base_price ASC LIMIT 1
        """, (product_code.upper(),))
        row = cur.fetchone()

        # 如果精确匹配失败，尝试模糊搜索得力商品
        if not row:
            # 支持多关键词搜索，如"得力订书钉" -> "得力" AND "订书钉"
            keywords = [k for k in product_code.replace("得力", "").replace("deli", "").strip() if k]
            if not keywords:
                keywords = [product_code]

            where_conditions = " AND ".join(["dp.material_desc LIKE ?"] * len(keywords))
            where_params = [f"%{k}%" for k in keywords]

            cur = conn.execute(f"""
                SELECT dp.material_code, dp.material_desc, dp.base_price,
                       s.name AS supplier_name
                FROM deli_products dp
                JOIN suppliers s ON s.id = 3
                WHERE {where_conditions}
                LIMIT 1
            """, where_params)
            row = cur.fetchone()
            if row:
                return {
                    "product_code": f"DL-{row['material_code']}",
                    "product_name": row["material_desc"],
                    "base_price": row["base_price"],
                    "supplier_name": row["supplier_name"],
                    "suggested_price": None
                }

        if not row:
            raise HTTPException(404, "未找到该商品")
        return {"product_code": product_code.upper(), "base_price": row["base_price"],
                "supplier_name": row["supplier_name"], "suggested_price": row["suggested_price"]}
    finally:
        conn.close()

@app.put("/api/admin/price")
def update_price(req: PriceUpdateRequest):
    """修改商品底价"""
    conn = get_db()
    try:
        conn.execute("UPDATE supplier_quotes SET expire_date = date() WHERE product_code = ? AND supplier_id = ? AND expire_date IS NULL",
                     (req.product_code.upper(), req.supplier_id))
        conn.execute("INSERT INTO supplier_quotes (supplier_id, product_code, base_price, effective_date) VALUES (?, ?, ?, date())",
                     (req.supplier_id, req.product_code.upper(), req.new_price))
        conn.commit()
        return {"success": True, "message": f"{req.product_code.upper()} 底价→{req.new_price}元"}
    finally:
        conn.close()

# ---------- 客户管理 ----------

@app.get("/api/admin/customers")
def query_customer(name: str = None, wechat_id: str = None):
    """查询客户"""
    conn = get_db()
    try:
        if name:
            row = conn.execute("SELECT * FROM customers WHERE company_name LIKE ?", (f"%{name}%",)).fetchone()
        elif wechat_id:
            row = conn.execute("SELECT * FROM customers WHERE external_user_id = ?", (wechat_id,)).fetchone()
        else:
            raise HTTPException(400, "需要 name 或 wechat_id")
        if not row:
            raise HTTPException(404, "客户不存在")
        return dict(row)
    finally:
        conn.close()

@app.put("/api/admin/customers/update-factor")
def update_customer_factor(req: CustomerUpdateFactor):
    """修改客户定价系数"""
    conn = get_db()
    try:
        cur = conn.execute("UPDATE customers SET price_factor = ? WHERE company_name = ?",
                           (req.price_factor, req.company_name))
        if cur.rowcount == 0:
            raise HTTPException(404, "客户不存在")
        conn.commit()
        return {"success": True, "message": f"{req.company_name} 系数→{req.price_factor}"}
    finally:
        conn.close()

# ---------- 运费规则 ----------

@app.get("/api/admin/shipping")
def query_shipping(region: str = "江浙沪"):
    """查询运费"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM shipping_rules WHERE region_value = ? OR region_value = '全国' ORDER BY priority ASC LIMIT 1",
                           (region,)).fetchone()
        if not row:
            return {"region": region, "first_weight": 1.0, "first_price": 5.0, "additional_price": 2.0}
        return dict(row)
    finally:
        conn.close()

@app.put("/api/admin/shipping")
def update_shipping(region: str, first_price: float):
    """修改运费首重价格"""
    conn = get_db()
    try:
        conn.execute("UPDATE shipping_rules SET first_price = ? WHERE region_value = ?", (first_price, region))
        conn.commit()
        return {"success": True, "message": f"{region} 首重→{first_price}元"}
    finally:
        conn.close()

# ---------- GMV 统计 ----------

@app.get("/api/admin/stats/gmv")
def query_gmv(range: str = "today"):
    """GMV 统计"""
    conn = get_db()
    try:
        if range == "today":
            sql = "SELECT COALESCE(SUM(total_gmv),0), COUNT(*) FROM orders WHERE DATE(created_at)=DATE()"
        elif range == "yesterday":
            sql = "SELECT COALESCE(SUM(total_gmv),0), COUNT(*) FROM orders WHERE DATE(created_at)=DATE('now','-1 day')"
        elif range == "week":
            sql = "SELECT COALESCE(SUM(total_gmv),0), COUNT(*) FROM orders WHERE created_at >= DATE('now','-7 days')"
        else:
            sql = "SELECT COALESCE(SUM(total_gmv),0), COUNT(*) FROM orders WHERE DATE(created_at)=DATE()"
        row = conn.execute(sql).fetchone()
        return {"total_gmv": row[0] or 0, "total_orders": row[1]}
    finally:
        conn.close()

# ---------- 待处理人工介入 ----------

@app.get("/api/admin/interventions/pending")
def get_pending():
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT hi.id, c.company_name, hi.trigger_reason, hi.customer_message
            FROM human_intervention hi
            LEFT JOIN customers c ON hi.customer_id = c.id
            WHERE hi.status = 'pending' ORDER BY hi.created_at ASC LIMIT 20
        """).fetchall()
        return {"items": [dict(r) for r in rows]}
    finally:
        conn.close()

# ---------- 健康检查 ----------

@app.get("/health")
def health():
    return {"status": "ok", "service": "backend_api", "port": 8000}