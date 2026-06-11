"""LLM 意图识别模块 - 提取询价信息"""
import json
import re
import anthropic

QUOTE_PROMPT = """你是一个询价助手。从用户消息中提取询价信息，返回 JSON。

用户消息：{user_msg}

需要提取：
1. product: 商品型号或名称（如 ABC-100、订书钉、文件夹）
2. quantity: 数量（数字，默认1）
3. region: 收货地区（省份或城市名）
4. intent: 意图（quote=询价, query_price=查底价, query_customer=查客户, update_price=改价格, update_factor=改系数, query_gmv=查销售额, get_pending=查待处理, help=帮助）

规则：
- "100个"、"50盒"、"200支" → 提取数字作为 quantity
- 地区从消息中提取省份/城市名，如"杭州"、"浙江"、"上海"、"江浙沪"
- 如果用户只说商品没说数量，默认 quantity=1
- 如果没说地区，region 留空字符串
- "多少钱"、"报价"、"价格"、"要"、"买"、"订"、"采购" → 意图是 quote
- 只要提到了商品+数量（哪怕没有"多少钱"），也是 quote
- "查"、"看" → 意图是 query_price
- "发XX"、"到XX"、"寄XX" → 意图是 quote（补充地区），从消息中提取地区
- 识别不出意图返回 {{"intent": "unknown"}}

示例：
用户：我要100个订书钉发到杭州
{{"intent": "quote", "product": "订书钉", "quantity": 100, "region": "杭州"}}

用户：得力文件夹多少钱
{{"intent": "quote", "product": "得力文件夹", "quantity": 1, "region": ""}}

用户：保温杯50个发上海
{{"intent": "quote", "product": "保温杯", "quantity": 50, "region": "上海"}}

用户：保温杯50个
{{"intent": "quote", "product": "保温杯", "quantity": 50, "region": ""}}

用户：发上海
{{"intent": "quote", "product": "", "quantity": 1, "region": "上海"}}

用户：查客户 凌晨公司
{{"intent": "query_customer", "product": "", "quantity": 1, "region": ""}}

只返回 JSON。"""


def extract_quote_info(user_msg: str) -> dict:
    """提取询价信息"""
    # 快速处理：纯数字或短型号，直接返回 quote 意图
    msg = user_msg.strip()
    if msg.isdigit() and len(msg) <= 6:
        return {"intent": "quote", "product": msg, "quantity": 1, "region": ""}
    if len(msg) <= 10 and any(c.isalpha() for c in msg) and not any(kw in msg for kw in ["查", "改", "帮助", "help"]):
        # 可能是型号，直接尝试
        pass

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="mimo-v2.5",
            max_tokens=1000,
            messages=[{"role": "user", "content": QUOTE_PROMPT.format(user_msg=user_msg)}]
        )

        text = ""
        for block in resp.content:
            if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                text = block.text.strip()
                break
            elif type(block).__name__ == "ThinkingBlock" and hasattr(block, "thinking"):
                thinking = block.thinking
                brace_count = 0
                end_pos = len(thinking)
                for i in range(len(thinking) - 1, -1, -1):
                    if thinking[i] == '}':
                        if brace_count == 0:
                            end_pos = i + 1
                        brace_count += 1
                    elif thinking[i] == '{':
                        brace_count -= 1
                        if brace_count == 0:
                            text = thinking[i:end_pos]
                            break

        if not text:
            return {"intent": "unknown", "product": "", "quantity": 1, "region": ""}

        data = json.loads(text)
        return {
            "intent": data.get("intent", "unknown"),
            "product": data.get("product", ""),
            "quantity": int(data.get("quantity", 1)),
            "region": data.get("region", "")
        }
    except Exception as e:
        print(f"意图识别错误: {e}")
        return {"intent": "unknown", "product": "", "quantity": 1, "region": ""}
