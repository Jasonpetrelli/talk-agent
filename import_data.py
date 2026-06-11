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
    wb = openpyxl.load_workbook("/Users/jeson/Downloads/副本得力全品类报价表20250422_副本.xlsx")
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
            base_price = float(row[11]) if row[11] else 0    # 单价

            # 重量可能不是数字，需要安全转换
            try:
                weight_grams = float(row[22]) if row[22] and str(row[22]).replace('.', '').isdigit() else 0
            except (ValueError, TypeError):
                weight_grams = 0

            if not material_code or not material_desc:
                continue

            # 插入 deli_products
            cur.execute("""
                INSERT OR REPLACE INTO deli_products
                (material_code, huohao, material_desc, category, weight_grams, base_price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (material_code, huohao, material_desc, category, weight_grams, base_price))

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
