"""导入报价规则和得力商品数据"""
import sqlite3
from docx import Document
import openpyxl

DB_PATH = "data.db"

# ===== 导入报价规则 =====

def import_pricing_rules():
    doc = Document("/Users/jeson/Downloads/报价规则手册.docx")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 提取文本内容
    content_parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            content_parts.append(para.text.strip())

    # 提取表格内容
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            content_parts.append(" | ".join(cells))

    full_content = "\n".join(content_parts)

    # 按章节分割存储
    rules = [
        ("category", "商品分类规则", "普通商品/重货抛货/复印纸判定规则"),
        ("heavy_keywords", "重货关键词", "档案盒、纸杯、文件筐、文件座、文件柜、书立、白板、本子、笔记本、记事本、活页本等"),
        ("heavy_exclude", "重货排除词", "装订机、收纳盒、装订盒、碎纸机、打孔机、过塑机、塑封机、切纸机、裁纸机等"),
        ("copy_paper", "复印纸判定", "复印纸、A4纸、打印纸（仅限明确标注为复印纸类别的商品）"),
        ("normal_pricing", "普通商品报价", "多价格列含运费比价，取含运费总价最低值，参与比价：85*95、85、86.5、1.05、1.15"),
        ("heavy_pricing", "重货抛货报价", "固定使用出厂价(86.5)价格列，运费=0（包邮）"),
        ("copy_pricing", "复印纸报价", "无论数量多少，统一返回：复印纸请直接向供应商询价"),
        ("shipping", "运费规则", "运费 = 总重量(kg) × 区域系数 + 基础费(4.5元)，一区0.8元/kg，二区1.4元/kg"),
        ("low_amount", "低金额规则", "订单总价<50元时，额外加5元基础费用"),
        ("brand", "品牌标准化", "得力/deli/DELI/得力DELI/得力 deli → 得力"),
        ("full_content", "完整规则手册", full_content),
    ]

    cur.executemany(
        "INSERT OR REPLACE INTO pricing_rules (rule_type, rule_name, rule_content) VALUES (?, ?, ?)",
        rules
    )
    conn.commit()
    conn.close()
    print(f"✓ 导入 {len(rules)} 条报价规则")


# ===== 导入得力商品 =====

def import_deli_products():
    wb = openpyxl.load_workbook("/Users/jeson/Downloads/副本得力全品类报价表20250422_副本.xlsx", data_only=True)
    ws = wb.active

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 确保得力供应商存在
    cur.execute("INSERT OR REPLACE INTO suppliers (id, name, contact_phone) VALUES (?, ?, ?)",
                (3, "得力集团", "400-185-0555"))

    count = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        try:
            material_code = str(row[2]) if row[2] else None  # 物料编码
            huohao = str(row[3]) if row[3] else None         # 货号
            material_desc = str(row[4]) if row[4] else None  # 物料描述
            category = str(row[1]) if row[1] else None       # 物料组描述
            outer_package = str(row[5]) if row[5] else None  # 外包装
            mid_package2 = str(row[6]) if row[6] else None   # 中包装2
            mid_package1 = str(row[7]) if row[7] else None   # 中包装1
            small_package = str(row[8]) if row[8] else None  # 小包装
            min_sales_unit = str(row[9]) if row[9] else None # 最小销售单位
            price_type = str(row[10]) if row[10] else None   # 价格类型
            base_price = float(row[11]) if row[11] else 0    # 单价

            # 价格列（公式计算后的值）
            price_85_95 = float(row[12]) if row[12] else None
            price_85 = float(row[13]) if row[13] else None
            price_86_5 = float(row[14]) if row[14] else None
            price_1_05 = float(row[15]) if row[15] else None
            price_1_15 = float(row[16]) if row[16] else None

            barcode = str(row[17]) if row[17] else None      # 条形码
            external_group = str(row[18]) if row[18] else None # 外部物料组
            product_source = str(row[19]) if row[19] else None # 产品来源描述
            new_product_start = row[20] if row[20] else None   # 新品有效开始日期
            new_product_end = row[21] if row[21] else None     # 新品有效结束日期
            exclusive_type = str(row[22]) if row[22] else None # 产品专供类型

            # 重量安全转换（第23列是重量）
            weight_grams = 0
            if row[23] is not None:
                try:
                    weight_grams = float(row[23])
                except (ValueError, TypeError):
                    weight_grams = 0

            quantity = int(row[24]) if row[24] else None      # 数量
            amount = float(row[25]) if row[25] else None      # 金额
            total_weight = float(row[26]) if row[26] else None # 总重量
            price_85_95_calc = float(row[27]) if row[27] else None # 85-95

            if not material_code or not material_desc:
                continue

            # 插入 deli_products（完整字段）
            cur.execute("""
                INSERT OR REPLACE INTO deli_products
                (material_code, huohao, material_desc, category,
                 outer_package, mid_package2, mid_package1, small_package,
                 min_sales_unit, price_type, base_price,
                 price_85_95, price_85, price_86_5, price_1_05, price_1_15,
                 barcode, external_group, product_source,
                 new_product_start, new_product_end, exclusive_type,
                 weight_grams, quantity, amount, total_weight, price_85_95_calc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (material_code, huohao, material_desc, category,
                  outer_package, mid_package2, mid_package1, small_package,
                  min_sales_unit, price_type, base_price,
                  price_85_95, price_85, price_86_5, price_1_05, price_1_15,
                  barcode, external_group, product_source,
                  new_product_start, new_product_end, exclusive_type,
                  weight_grams, quantity, amount, total_weight, price_85_95_calc))

            # 同时插入 products 表（统一格式）
            product_code = f"DL-{material_code}"
            weight_kg = weight_grams / 1000 if weight_grams else 0
            cur.execute("""
                INSERT OR REPLACE INTO products
                (product_code, product_name, category, weight_kg, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (product_code, material_desc, category, weight_kg))

            # 插入供应商报价（得力供应商 ID=3）
            if base_price > 0:
                cur.execute("""
                    INSERT OR REPLACE INTO supplier_quotes
                    (supplier_id, product_code, base_price, is_preferred, effective_date)
                    VALUES (?, ?, ?, 1, date('now'))
                """, (3, product_code, base_price))

            count += 1
            if count % 1000 == 0:
                print(f"  已处理 {count} 条...")

        except Exception as e:
            continue

    conn.commit()
    conn.close()
    print(f"✓ 导入 {count} 条得力商品")


if __name__ == "__main__":
    print("开始导入数据...")
    import_pricing_rules()
    import_deli_products()
    print("导入完成！")
