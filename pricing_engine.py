"""报价计算引擎 - 根据规则计算含运费报价"""
import sqlite3
from typing import Optional

DB_PATH = "data.db"

# 区域系数
REGION_ZONES = {
    "一区": 0.8,  # 江浙沪皖等近程省份
    "二区": 1.4,  # 其他远程省份
}

# 重货关键词
HEAVY_KEYWORDS = [
    "档案盒", "纸杯", "文件筐", "文件座", "文件柜", "书立", "白板",
    "本子", "笔记本", "记事本", "活页本", "活页芯", "活页替芯",
    "奖状", "证书", "贴纸", "不干胶", "信封", "档案袋",
    "海报", "相纸", "相片纸", "卡纸", "皮纹纸", "铜版纸"
]

# 重货排除词
HEAVY_EXCLUDE = [
    "装订机", "收纳盒", "装订盒", "碎纸机", "打孔机", "过塑机",
    "塑封机", "切纸机", "裁纸机", "白板笔", "白板擦", "白板架",
    "白板磁粒", "白板磁钉"
]

# 复印纸关键词
COPY_PAPER_KEYWORDS = ["复印纸", "A4纸", "打印纸"]

# 省份到区域映射
PROVINCE_TO_ZONE = {
    # 一区（江浙沪皖等）
    "浙江": "一区", "江苏": "一区", "上海": "一区", "安徽": "一区",
    "杭州": "一区", "宁波": "一区", "温州": "一区", "嘉兴": "一区",
    "湖州": "一区", "绍兴": "一区", "金华": "一区", "衢州": "一区",
    "舟山": "一区", "台州": "一区", "丽水": "一区",
    "南京": "一区", "苏州": "一区", "无锡": "一区", "常州": "一区",
    "徐州": "一区", "南通": "一区", "连云港": "一区", "淮安": "一区",
    "盐城": "一区", "扬州": "一区", "镇江": "一区", "泰州": "一区",
    "宿迁": "一区",
    "合肥": "一区", "芜湖": "一区", "蚌埠": "一区", "淮南": "一区",
    "马鞍山": "一区", "淮北": "一区", "铜陵": "一区", "安庆": "一区",
    "黄山": "一区", "滁州": "一区", "阜阳": "一区", "宿州": "一区",
    "六安": "一区", "亳州": "一区", "池州": "一区", "宣城": "一区",
    "江浙沪": "一区", "江浙沪皖": "一区",
    # 二区（其他）
    "北京": "二区", "天津": "二区", "河北": "二区", "山西": "二区",
    "辽宁": "二区", "吉林": "二区", "黑龙江": "二区",
    "福建": "二区", "江西": "二区", "山东": "二区", "河南": "二区",
    "湖北": "二区", "湖南": "二区", "广东": "二区", "广西": "二区",
    "海南": "二区", "重庆": "二区", "四川": "二区", "贵州": "二区",
    "云南": "二区", "西藏": "二区", "陕西": "二区", "甘肃": "二区",
    "青海": "二区", "宁夏": "二区", "新疆": "二区", "内蒙古": "二区",
    "全国": "二区", "非江浙沪": "二区",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def classify_product(product_name: str) -> str:
    """判断商品分类：normal/heavy/copy_paper"""
    name = product_name

    # 复印纸判定（优先）
    for kw in COPY_PAPER_KEYWORDS:
        if kw in name:
            return "copy_paper"

    # 重货判定（需排除词）
    for kw in HEAVY_KEYWORDS:
        if kw in name:
            # 检查排除词
            excluded = False
            for ex in HEAVY_EXCLUDE:
                if ex in name:
                    excluded = True
                    break
            if not excluded:
                return "heavy"

    return "normal"


def get_zone(region: str) -> str:
    """将地区转为区域"""
    for key, zone in PROVINCE_TO_ZONE.items():
        if key in region:
            return zone
    return "二区"  # 默认二区


def calculate_shipping(weight_kg: float, zone: str) -> float:
    """计算运费"""
    coefficient = REGION_ZONES.get(zone, 1.4)
    return weight_kg * coefficient + 4.5


def query_product(product_code: str) -> Optional[dict]:
    """查询商品信息"""
    conn = get_db()
    try:
        # 先精确匹配 products 表
        row = conn.execute(
            "SELECT * FROM products WHERE product_code = ?",
            (product_code.upper(),)
        ).fetchone()

        if not row:
            # 模糊匹配 products 表
            row = conn.execute(
                "SELECT * FROM products WHERE product_name LIKE ?",
                (f"%{product_code}%",)
            ).fetchone()

        if not row:
            # 精确匹配得力商品（物料编码、货号、描述）
            clean = product_code.replace("DL-", "").replace("得力", "").replace("deli", "").strip()
            if clean:
                row = conn.execute("""
                    SELECT dp.material_code, dp.material_desc, dp.category,
                           dp.weight_grams, dp.base_price, 'DL-' || dp.material_code as product_code
                    FROM deli_products dp
                    WHERE dp.material_code = ? OR dp.huohao = ? OR dp.material_desc = ?
                """, (clean, clean, product_code)).fetchone()

        if not row and clean:
            # 模糊匹配得力商品
            row = conn.execute("""
                SELECT dp.material_code, dp.material_desc, dp.category,
                       dp.weight_grams, dp.base_price, 'DL-' || dp.material_code as product_code
                FROM deli_products dp
                WHERE dp.material_desc LIKE ?
                LIMIT 1
            """, (f"%{clean}%",)).fetchone()

            # 多关键词匹配
            if not row:
                import re as _re
                parts = _re.split(r'[（(、/\s]+', clean)
                new_parts = []
                for p in parts:
                    new_parts.extend(_re.split(r'(?<=[a-zA-Z0-9])(?=[一-鿿])|(?<=[一-鿿])(?=[a-zA-Z0-9])', p))
                parts = [p for p in new_parts if len(p) >= 2]
                if parts:
                    where = " AND ".join(["dp.material_desc LIKE ?"] * len(parts))
                    params = [f"%{p}%" for p in parts]
                    row = conn.execute(f"""
                        SELECT dp.material_code, dp.material_desc, dp.category,
                               dp.weight_grams, dp.base_price, 'DL-' || dp.material_code as product_code
                        FROM deli_products dp
                        WHERE {where}
                        LIMIT 1
                    """, params).fetchone()

        if row:
            if "weight_grams" in row.keys():
                return {
                    "product_code": row["product_code"],
                    "product_name": row["material_desc"],
                    "category": row["category"],
                    "weight_kg": (row["weight_grams"] or 0) / 1000,
                    "base_price": row["base_price"]
                }
            return {
                "product_code": row["product_code"],
                "product_name": row["product_name"],
                "category": row["category"],
                "weight_kg": row["weight_kg"] or 0,
                "base_price": None
            }
        return None
    finally:
        conn.close()


def search_products(keyword: str) -> list:
    """搜索商品，返回匹配列表"""
    conn = get_db()
    try:
        results = []

        # 先精确匹配 products 表
        rows = conn.execute(
            "SELECT product_code, product_name, category FROM products WHERE product_code = ? OR product_name = ?",
            (keyword.upper(), keyword)
        ).fetchall()
        for r in rows:
            results.append({"code": r["product_code"], "name": r["product_name"], "category": r["category"]})

        # 精确匹配得力商品（物料编码、货号、描述）
        if not results:
            clean = keyword.replace("DL-", "").replace("得力", "").replace("deli", "").strip()
            if clean:
                rows = conn.execute("""
                    SELECT 'DL-' || dp.material_code as code, dp.material_desc as name, dp.category
                    FROM deli_products dp
                    WHERE dp.material_code = ? OR dp.huohao = ? OR dp.material_desc = ?
                """, (clean, clean, keyword)).fetchall()
                for r in rows:
                    results.append({"code": r["code"], "name": r["name"], "category": r["category"]})

        # 模糊匹配 products 表
        if not results:
            rows = conn.execute(
                "SELECT product_code, product_name, category FROM products WHERE product_name LIKE ? OR product_code LIKE ? LIMIT 10",
                (f"%{keyword}%", f"%{keyword}%")
            ).fetchall()
            for r in rows:
                results.append({"code": r["product_code"], "name": r["product_name"], "category": r["category"]})

        # 模糊匹配得力商品（多关键词）
        if not results:
            clean = keyword.replace("得力", "").replace("deli", "").strip()
            if clean:
                # 尝试整体模糊
                rows = conn.execute("""
                    SELECT 'DL-' || dp.material_code as code, dp.material_desc as name, dp.category
                    FROM deli_products dp
                    WHERE dp.material_desc LIKE ?
                    LIMIT 10
                """, (f"%{clean}%",)).fetchall()
                for r in rows:
                    results.append({"code": r["code"], "name": r["name"], "category": r["category"]})

                # 如果没匹配到，按中英文边界拆分后 AND 搜索
                if not results:
                    import re as _re
                    # 先按常见分隔符拆
                    parts = _re.split(r'[（(、/\s]+', clean)
                    # 再按中英文边界拆
                    new_parts = []
                    for p in parts:
                        new_parts.extend(_re.split(r'(?<=[a-zA-Z0-9])(?=[一-鿿])|(?<=[一-鿿])(?=[a-zA-Z0-9])', p))
                    parts = [p for p in new_parts if len(p) >= 2]
                    if parts:
                        where = " AND ".join(["dp.material_desc LIKE ?"] * len(parts))
                        params = [f"%{p}%" for p in parts]
                        rows = conn.execute(f"""
                            SELECT 'DL-' || dp.material_code as code, dp.material_desc as name, dp.category
                            FROM deli_products dp
                            WHERE {where}
                            LIMIT 10
                        """, params).fetchall()
                        for r in rows:
                            results.append({"code": r["code"], "name": r["name"], "category": r["category"]})

        return results
    finally:
        conn.close()


def query_best_price(product_code: str) -> Optional[dict]:
    """查询最优报价"""
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT sq.base_price, s.name AS supplier_name, sq.suggested_price
            FROM supplier_quotes sq
            JOIN suppliers s ON sq.supplier_id = s.id
            WHERE sq.product_code = ? AND sq.is_preferred = 1
              AND (sq.expire_date IS NULL OR sq.expire_date > date())
            ORDER BY sq.base_price ASC LIMIT 1
        """, (product_code.upper(),)).fetchone()

        if not row:
            # 查任意报价
            row = conn.execute("""
                SELECT sq.base_price, s.name AS supplier_name, sq.suggested_price
                FROM supplier_quotes sq
                JOIN suppliers s ON sq.supplier_id = s.id
                WHERE sq.product_code = ?
                ORDER BY sq.base_price ASC LIMIT 1
            """, (product_code.upper(),)).fetchone()

        if row:
            return {
                "base_price": row["base_price"],
                "supplier_name": row["supplier_name"],
                "suggested_price": row["suggested_price"]
            }
        return None
    finally:
        conn.close()


def calculate_quote(product_code: str, quantity: int, region: str) -> dict:
    """
    计算最终报价
    返回: {success, message, details}
    """
    # 1. 查询商品信息
    product = query_product(product_code)
    if not product:
        return {"success": False, "message": f"未找到商品 {product_code}"}

    product_name = product["product_name"]
    weight_kg = product["weight_kg"]

    # 2. 判断商品分类
    category = classify_product(product_name)

    # 复印纸直接返回
    if category == "copy_paper":
        return {
            "success": True,
            "message": "复印纸请直接向供应商询价",
            "details": {"category": "copy_paper"}
        }

    # 3. 查询底价
    price_info = query_best_price(product["product_code"])
    if not price_info:
        return {"success": False, "message": f"未找到 {product_name} 的报价"}

    base_price = price_info["base_price"]
    supplier = price_info["supplier_name"]

    # 4. 计算单价
    if category == "heavy":
        # 重货：出厂价(86.5)包邮，单价 = base_price * 86.5
        unit_price = base_price * 0.865
        shipping = 0
        shipping_rule = "包邮（重货）"
    else:
        # 普通商品：比价取最低，需要计算运费
        # 这里简化处理，使用 base_price * 0.85 * 0.95（最低价列）
        unit_price = base_price * 0.85 * 0.95

        if not region:
            # 没有地区，先不算运费，提示需要地区
            shipping = None
            shipping_rule = "需要收货地区才能计算运费"
        else:
            zone = get_zone(region)
            total_weight = weight_kg * quantity
            shipping = calculate_shipping(total_weight, zone)
            shipping_rule = f"{zone}：{weight_kg}kg/件 × {quantity}件 × {REGION_ZONES[zone]}元/kg + 4.5元基础费"

    # 5. 计算总价
    goods_total = unit_price * quantity
    if shipping is not None:
        final_total = goods_total + shipping
        # 低金额规则：总价<50元加5元
        low_amount_fee = 0
        if final_total < 50:
            low_amount_fee = 5
            final_total += 5
    else:
        final_total = None
        low_amount_fee = 0

    # 6. 构建回复
    lines = [
        f"【{product_name}】",
        f"供应商：{supplier}",
        f"单价：{unit_price:.2f} 元/件",
        f"数量：{quantity} 件",
        f"商品小计：{goods_total:.2f} 元",
    ]

    if shipping is not None:
        lines.extend([
            f"运费：{shipping:.2f} 元（{shipping_rule}）",
        ])
        if low_amount_fee > 0:
            lines.append(f"低金额附加费：{low_amount_fee} 元（订单总价<50元）")
        lines.append(f"─────────────")
        lines.append(f"合计：{final_total:.2f} 元")
    else:
        lines.append(f"─────────────")
        lines.append(f"商品总价：{goods_total:.2f} 元")
        lines.append(f"（还需提供收货地区才能计算运费）")

    return {
        "success": True,
        "message": "\n".join(lines),
        "details": {
            "product_code": product["product_code"],
            "product_name": product_name,
            "category": category,
            "supplier": supplier,
            "unit_price": unit_price,
            "quantity": quantity,
            "goods_total": goods_total,
            "shipping": shipping,
            "shipping_rule": shipping_rule,
            "region": region,
            "final_total": final_total,
            "weight_kg": weight_kg
        }
    }
