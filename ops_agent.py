"""
运营 Agent 业务逻辑 - 意图识别 + 调用后端 API
这是项目的智能核心，所有自然语言理解、决策都在这里
"""

import re
import requests

BACKEND_URL = "http://localhost:8000"


def ops_agent(user_msg: str) -> str:
    """运营 Agent 主入口：解析意图，执行操作，返回回复"""
    msg = user_msg.strip()

    has_model = bool(re.search(r"[A-Za-z0-9]{3,}-[A-Za-z0-9]+", msg.upper()))

    # ----- 改价格（先于查价格，避免"改成"被"查价"捕获）-----
    if re.search(r"改价|修改价格|底价[改调变]|底价改成", msg):
        return handle_update_price(msg)

    # ----- 改运费 -----
    if re.search(r"改运费|运费改成", msg):
        return handle_update_shipping(msg)

    # ----- 改客户系数 -----
    if re.search(r"改系数|定价系数|系数改成", msg):
        return handle_update_customer_factor(msg)

    # ----- 查客户 -----
    if re.search(r"查客户|客户信息|客户配置", msg):
        return handle_query_customer(msg)

    # ----- 查价格（需要型号 + 价格/报价关键词，且不是"改"操作）-----
    if has_model and re.search(r"查|价|报价|多少钱|底价|要.*个|买|订购", msg):
        return handle_query_price(msg)

    # ----- GMV 统计 -----
    if not has_model and re.search(r"gmv|成交|卖了|销售额|业绩", msg.lower()):
        return handle_query_gmv(msg)

    # ----- 查运费 -----
    if re.search(r"运费|配送费|快递费", msg):
        return handle_query_shipping(msg)

    # ----- 待处理 -----
    if re.search(r"待处理|人工介入|投诉|转人工", msg):
        return handle_get_pending(msg)

    # ----- 帮助 -----
    if re.search(r"帮助|help|功能|能做什么|可用指令", msg.lower()):
        return show_help()

    return f"我没理解您的意思。试试这些指令：\n\n{show_help()}"


# ========== 各功能处理函数 ==========


def handle_query_price(msg: str) -> str:
    m = re.search(r"([A-Za-z0-9]{3,}-?[A-Za-z0-9]+)", msg.upper())
    if not m:
        return "请告诉我商品型号，例如：查 ABC-100 的价格"
    code = m.group(1)
    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/price", params={"product_code": code}, timeout=5)
        if resp.status_code == 200:
            d = resp.json()
            return f"商品 {code}（主推：{d['supplier_name']}）\n底价：{d['base_price']} 元\n建议售价：{d['suggested_price']} 元"
        return f"没找到型号 {code}，换个型号试试？"
    except Exception as e:
        return f"查询失败：{e}"


def handle_update_price(msg: str) -> str:
    """提取型号+新价格，二次确认格式"""
    pm = re.search(r"([A-Za-z0-9]{3,}-?[A-Za-z0-9]+)", msg.upper())
    vm = re.search(r"(?:改成|改为|改成?)\s*(\d+(?:\.\d+)?)\s*元?", msg)
    sm = re.search(r"供应商[IDid号]*\s*(\d+)", msg)
    if not pm:
        return "请告诉我要改哪个型号，例如：把 ABC-100 底价改成 13.5 元"
    if not vm:
        return "请告诉我新价格，例如：改成 13.5 元"
    code = pm.group(1)
    price = float(vm.group(1))
    sid = int(sm.group(1)) if sm else 1
    return f"确认：将 {code} 底价改为 {price} 元（供应商 ID={sid}）？\n回复「确认」执行，回复其他取消。"


def handle_query_customer(msg: str) -> str:
    m = re.search(r"查客户[：:]*\s*(\S+)", msg)
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


def handle_update_customer_factor(msg: str) -> str:
    nm = re.search(r"把\s*(\S+公司)", msg) or re.search(r"(\S+公司)", msg)
    fm = re.search(r"系数[：:]*\s*(?:改成?)?\s*(\d+(?:\.\d+)?)", msg)
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


def handle_query_shipping(msg: str) -> str:
    regions = ["非江浙沪", "江浙沪", "浙江", "江苏", "上海", "北京", "广东", "全国"]
    region = "江浙沪"
    for r in regions:
        if r in msg:
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


def handle_update_shipping(msg: str) -> str:
    regions = ["非江浙沪", "江浙沪", "浙江", "江苏", "上海", "北京", "广东", "全国"]
    region = None
    for r in regions:
        if r in msg:
            region = r
            break
    if not region:
        return "请告诉我要改哪个地区，例如：江浙沪首重改成 8 元"
    pm = re.search(r"(\d+(?:\.\d+)?)\s*元?", msg)
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


def handle_query_gmv(msg: str) -> str:
    if "昨天" in msg:
        rng = "yesterday"
    elif "本周" in msg or "这周" in msg:
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


def handle_get_pending(msg: str) -> str:
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
        "查价格 ABC-100\n"
        "把 ABC-100 底价改成 13.5 元\n"
        "查客户 凌晨公司\n"
        "把 凌晨公司 定价系数改成 1.2\n"
        "江浙沪的运费\n"
        "江浙沪首重改成 6 元\n"
        "今天卖了多少钱\n"
        "有没有待处理的人工介入\n"
        "帮助 — 查看所有指令"
    )