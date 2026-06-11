"""
运营 Agent 业务逻辑 - LLM 意图识别 + 调用后端 API
"""
import requests
from intent_extractor import extract_intent

BACKEND_URL = "http://localhost:8000"

# 商品名称 -> 型号映射（可从数据库动态加载）
PRODUCT_NAME_MAP = {
    "保温杯": "ABC-100",
    "电热水壶": "DEF-200",
    "电热水壶1.5L": "DEF-200",
    "电热水壶2L": "DSH-100",
    "炒锅": "GHI-300",
}


def resolve_product_code(code_or_name: str) -> str:
    """将商品名称转为型号"""
    if code_or_name.upper() in ["ABC-100", "DEF-200", "GHI-300"]:
        return code_or_name.upper()
    return PRODUCT_NAME_MAP.get(code_or_name, code_or_name)


def ops_agent(user_msg: str) -> str:
    """运营 Agent 主入口：LLM 识别意图，执行操作，返回回复"""
    intent_data = extract_intent(user_msg)
    intent = intent_data.get("intent", "unknown")
    params = intent_data.get("params", {})

    handlers = {
        "query_price": lambda: handle_query_price(params.get("product_code", "")),
        "update_price": lambda: handle_update_price(params),
        "query_customer": lambda: handle_query_customer(params.get("company_name", "")),
        "update_factor": lambda: handle_update_factor(params),
        "query_shipping": lambda: handle_query_shipping(params.get("region", "江浙沪")),
        "update_shipping": lambda: handle_update_shipping(params),
        "query_gmv": lambda: handle_query_gmv(params.get("range", "today")),
        "get_pending": lambda: handle_get_pending(),
        "help": lambda: show_help(),
    }

    if intent in handlers:
        try:
            return handlers[intent]()
        except Exception as e:
            return f"操作失败：{e}"

    return f"没理解您的意思，换个说法试试？\n\n{show_help()}"


# ========== 各功能处理函数 ==========


def handle_query_price(product_code: str) -> str:
    product_code = resolve_product_code(product_code)
    if not product_code:
        return "请告诉我商品型号，例如：查 ABC-100 的价格"
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/price", params={"product_code": product_code}, timeout=5)
        if resp.status_code == 200:
            d = resp.json()
            return f"商品 {product_code}（主推：{d['supplier_name']}）\n底价：{d['base_price']} 元\n建议售价：{d['suggested_price']} 元"
        return f"没找到型号 {product_code}，换个型号试试？"
    except Exception as e:
        return f"查询失败：{e}"


def handle_update_price(params: dict) -> str:
    product_code = resolve_product_code(params.get("product_code", ""))
    new_price = params.get("new_price")
    if not product_code:
        return "请告诉我要改哪个型号，例如：把 ABC-100 底价改成 13.5 元"
    if not new_price:
        return "请告诉我新价格，例如：改成 13.5 元"
    try:
        resp = requests.put(f"{BACKEND_URL}/api/admin/price",
                            json={"product_code": product_code, "supplier_id": 1, "new_price": float(new_price)}, timeout=5)
        if resp.status_code == 200:
            return f"已将 {product_code} 底价改为 {new_price} 元"
        return f"修改失败：{resp.json().get('detail', '未知错误')}"
    except Exception as e:
        return f"操作失败：{e}"


def handle_query_customer(company_name: str) -> str:
    if not company_name:
        return "请告诉我要查的客户名，例如：查客户 凌晨公司"
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/customers", params={"name": company_name}, timeout=5)
        if resp.status_code == 200:
            c = resp.json()
            return (f"客户「{c['company_name']}」\n"
                    f"等级：{c['customer_level']}\n"
                    f"定价系数：{c['price_factor']}\n"
                    f"累计 GMV：{c['total_gmv']} 元")
        return f"没找到客户「{company_name}」"
    except Exception as e:
        return f"查询失败：{e}"


def handle_update_factor(params: dict) -> str:
    company_name = params.get("company_name", "")
    factor = params.get("factor")
    if not company_name:
        return "请告诉我完整的公司名，例如：凌晨公司"
    if not factor:
        return "请告诉我要改的系数，例如：系数 1.2"
    try:
        resp = requests.put(f"{BACKEND_URL}/api/admin/customers/update-factor",
                            json={"company_name": company_name, "price_factor": float(factor)}, timeout=5)
        if resp.status_code == 200:
            return f"已更新 {company_name} 定价系数 → {factor}"
        return f"更新失败：{resp.json().get('detail', '未知错误')}"
    except Exception as e:
        return f"操作失败：{e}"


def handle_query_shipping(region: str) -> str:
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/shipping", params={"region": region}, timeout=5)
        if resp.status_code == 200:
            s = resp.json()
            return f"{s['region_value']} 运费：首重 {s['first_weight_kg']}kg 内 {s['first_price']} 元，续重 {s['additional_price']} 元/kg"
        return f"没找到 {region} 的运费规则"
    except Exception as e:
        return f"查询失败：{e}"


def handle_update_shipping(params: dict) -> str:
    region = params.get("region", "")
    price = params.get("price")
    if not region:
        return "请告诉我要改哪个地区，例如：江浙沪首重改成 8 元"
    if not price:
        return "请告诉我新价格，例如：首重改成 6 元"
    try:
        resp = requests.put(f"{BACKEND_URL}/api/admin/shipping",
                            params={"region": region, "first_price": float(price)}, timeout=5)
        if resp.status_code == 200:
            return f"已更新 {region} 首重 → {price} 元"
        return "更新失败"
    except Exception as e:
        return f"操作失败：{e}"


def handle_query_gmv(range: str) -> str:
    labels = {"today": "今日", "yesterday": "昨日", "week": "本周"}
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/stats/gmv", params={"range": range}, timeout=5)
        if resp.status_code == 200:
            d = resp.json()
            return f"{labels.get(range, '今日')} GMV：{d['total_gmv']} 元，订单数：{d['total_orders']}"
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
        "- 查价格：说商品型号，如 ABC-100 多少钱\n"
        "- 改价格：如 把 ABC-100 底价改成 13.5 元\n"
        "- 查客户：如 查下凌晨公司\n"
        "- 改系数：如 凌晨公司系数改成 1.2\n"
        "- 查运费：如 江浙沪运费多少\n"
        "- 改运费：如 江浙沪首重改成 6 元\n"
        "- 查销售额：如 今天卖了多少钱\n"
        "- 待处理：如 有没有要处理的订单\n"
    )
