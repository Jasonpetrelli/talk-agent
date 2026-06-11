"""
运营 Agent 业务逻辑 - 询报价 + 各类查询
"""
import requests
from intent_extractor import extract_quote_info
from pricing_engine import calculate_quote

BACKEND_URL = "http://localhost:8000"


def ops_agent(user_msg: str) -> str:
    """运营 Agent 主入口"""
    info = extract_quote_info(user_msg)
    intent = info.get("intent", "unknown")

    if intent == "quote":
        return handle_quote(info)
    elif intent == "query_price":
        return handle_query_price(info.get("product", ""))
    elif intent == "query_customer":
        return handle_query_customer(user_msg)
    elif intent == "update_price":
        return handle_update_price(info.get("product", ""), user_msg)
    elif intent == "update_factor":
        return handle_update_factor(user_msg)
    elif intent == "query_shipping":
        return handle_query_shipping(user_msg)
    elif intent == "update_shipping":
        return handle_update_shipping(user_msg)
    elif intent == "query_gmv":
        return handle_query_gmv(user_msg)
    elif intent == "get_pending":
        return handle_get_pending()
    elif intent == "help":
        return show_help()
    else:
        return f"没理解您的意思，换个说法试试？\n\n{show_help()}"


# ========== 询价处理 ==========


def handle_quote(info: dict) -> str:
    """处理询价请求"""
    product = info.get("product", "")
    quantity = info.get("quantity", 1)
    region = info.get("region", "")

    # 缺少商品信息，追问
    if not product:
        return "请告诉我您要订什么商品？\n例如：得力订书钉、保温杯、文件夹"

    # 缺少地区，追问
    if not region:
        return f"收到！{product} {quantity} 件。\n请告诉我收货地区（省份或城市），我来算含运费的报价。\n例如：杭州、上海、广东"

    # 计算报价
    result = calculate_quote(product, quantity, region)

    if result["success"]:
        return result["message"]
    else:
        return result["message"]


# ========== 其他查询 ==========


def handle_query_price(product: str) -> str:
    if not product:
        return "请告诉我商品型号，例如：查 ABC-100 的价格"
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/price", params={"product_code": product}, timeout=5)
        if resp.status_code == 200:
            d = resp.json()
            name = d.get("product_name", product)
            return f"商品 {name}\n底价：{d['base_price']} 元\n供应商：{d['supplier_name']}"
        return f"没找到型号 {product}，换个型号试试？"
    except Exception as e:
        return f"查询失败：{e}"


def handle_query_customer(user_msg: str) -> str:
    import re
    m = re.search(r"查客户[：:]*\s*(\S+)", user_msg)
    if not m:
        return "请告诉我要查的客户名，例如：查客户 凌晨公司"
    name = m.group(1)
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/customers", params={"name": name}, timeout=5)
        if resp.status_code == 200:
            c = resp.json()
            return (f"客户「{c['company_name']}」\n"
                    f"等级：{c['customer_level']}\n"
                    f"定价系数：{c['price_factor']}\n"
                    f"累计 GMV：{c['total_gmv']} 元")
        return f"没找到客户「{name}」"
    except Exception as e:
        return f"查询失败：{e}"


def handle_update_price(product: str, user_msg: str) -> str:
    import re as _re
    vm = _re.search(r"(\d+(?:\.\d+)?)\s*元?", user_msg)
    if not product:
        return "请告诉我要改哪个型号"
    if not vm:
        return "请告诉我新价格"
    new_price = float(vm.group(1))
    try:
        resp = requests.put(f"{BACKEND_URL}/api/admin/price",
                            json={"product_code": product, "supplier_id": 1, "new_price": new_price}, timeout=5)
        if resp.status_code == 200:
            return f"已将 {product} 底价改为 {new_price} 元"
        return f"修改失败：{resp.json().get('detail', '未知错误')}"
    except Exception as e:
        return f"操作失败：{e}"


def handle_update_factor(user_msg: str) -> str:
    import re
    nm = re.search(r"把\s*(\S+公司)", user_msg) or re.search(r"(\S+公司)", user_msg)
    fm = re.search(r"系数[：:]*\s*(?:改成?)?\s*(\d+(?:\.\d+)?)", user_msg)
    if not nm:
        return "请告诉我完整的公司名，例如：凌晨公司"
    if not fm:
        return "请告诉我要改的系数，例如：系数 1.2"
    name = nm.group(1)
    factor = float(fm.group(1))
    try:
        resp = requests.put(f"{BACKEND_URL}/api/admin/customers/update-factor",
                            json={"company_name": name, "price_factor": factor}, timeout=5)
        if resp.status_code == 200:
            return f"已更新 {name} 定价系数 → {factor}"
        return f"更新失败：{resp.json().get('detail', '未知错误')}"
    except Exception as e:
        return f"操作失败：{e}"


def handle_query_shipping(user_msg: str) -> str:
    import re
    regions = ["非江浙沪", "江浙沪", "浙江", "江苏", "上海", "北京", "广东", "全国"]
    region = "江浙沪"
    for r in regions:
        if r in user_msg:
            region = r
            break
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/shipping", params={"region": region}, timeout=5)
        if resp.status_code == 200:
            s = resp.json()
            return f"{s['region_value']} 运费：首重 {s['first_weight_kg']}kg 内 {s['first_price']} 元，续重 {s['additional_price']} 元/kg"
        return f"没找到 {region} 的运费规则"
    except Exception as e:
        return f"查询失败：{e}"


def handle_update_shipping(user_msg: str) -> str:
    import re
    regions = ["非江浙沪", "江浙沪", "浙江", "江苏", "上海", "北京", "广东", "全国"]
    region = None
    for r in regions:
        if r in user_msg:
            region = r
            break
    if not region:
        return "请告诉我要改哪个地区，例如：江浙沪首重改成 8 元"
    pm = re.search(r"(\d+(?:\.\d+)?)\s*元?", user_msg)
    if not pm:
        return "请告诉我新价格，例如：首重改成 6 元"
    price = float(pm.group(1))
    try:
        resp = requests.put(f"{BACKEND_URL}/api/admin/shipping",
                            params={"region": region, "first_price": price}, timeout=5)
        if resp.status_code == 200:
            return f"已更新 {region} 首重 → {price} 元"
        return "更新失败"
    except Exception as e:
        return f"操作失败：{e}"


def handle_query_gmv(user_msg: str) -> str:
    if "昨天" in user_msg:
        rng = "yesterday"
    elif "本周" in user_msg or "这周" in user_msg:
        rng = "week"
    else:
        rng = "today"
    labels = {"today": "今日", "yesterday": "昨日", "week": "本周"}
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/stats/gmv", params={"range": rng}, timeout=5)
        if resp.status_code == 200:
            d = resp.json()
            return f"{labels[rng]} GMV：{d['total_gmv']} 元，订单数：{d['total_orders']}"
        return "查询失败"
    except Exception as e:
        return f"调用失败：{e}"


def handle_get_pending() -> str:
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/interventions/pending", timeout=5)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if not items:
                return "当前没有待处理的人工介入请求。"
            lines = [f"{len(items)} 条待处理："]
            for it in items[:5]:
                lines.append(f"  - {it['company_name'] or '未知'}: {it['trigger_reason']}")
            return "\n".join(lines)
        return "查询失败"
    except Exception as e:
        return f"调用失败：{e}"


def show_help() -> str:
    return (
        "我可以帮您：\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "【询价】\n"
        "  说商品+数量+地区，如：\n"
        "  - 得力订书钉100个发杭州\n"
        "  - 保温杯50个发上海\n"
        "  - 文件夹20个广东\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "【其他功能】\n"
        "  - 查底价：说型号，如 查 DL-100000001 价格\n"
        "  - 查客户：如 查客户 凌晨公司\n"
        "  - 查销售额：如 今天卖了多少\n"
        "  - 运费查询：如 江浙沪运费\n"
        "  - 帮助：查看此提示\n"
    )
