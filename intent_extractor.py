"""LLM 意图识别模块 - 把自然语言转成结构化意图"""
import json
import re
import anthropic

INTENT_PROMPT = """你是一个意图识别器。从用户消息中提取意图和参数，返回 JSON。

用户消息：{user_msg}

可选意图：
- query_price: 查价格（需要 product_code）
- update_price: 改价格（需要 product_code, new_price）
- query_customer: 查客户（需要 company_name）
- update_factor: 改系数（需要 company_name, factor）
- query_shipping: 查运费（需要 region）
- update_shipping: 改运费（需要 region, price）
- query_gmv: 查销售额（需要 range: today/yesterday/week）
- get_pending: 查待处理人工介入/投诉/转人工
- help: 帮助

规则：
1. product_code 格式是字母+数字如 ABC-100，如果用户只说商品名如"保温杯"，也提取为 product_code
2. "昨天" range=yesterday，"今天"或没提 range=today，"本周/这周" range=week
3. 地区从消息提取，默认江浙沪
4. "待处理/人工介入/投诉/转人工" 意图是 get_pending
5. 识别不出返回 {{"intent": "unknown"}}

示例：
用户：ABC-100 多少钱
{{"intent": "query_price", "params": {{"product_code": "ABC-100"}}}}

用户：保温杯价格
{{"intent": "query_price", "params": {{"product_code": "保温杯"}}}}

用户：今天卖了多少
{{"intent": "query_gmv", "params": {{"range": "today"}}}}

用户：有没有待处理的订单
{{"intent": "get_pending", "params": {{}}}}

只返回 JSON。"""


def extract_intent(user_msg: str) -> dict:
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="mimo-v2.5",
            max_tokens=1000,
            messages=[{"role": "user", "content": INTENT_PROMPT.format(user_msg=user_msg)}]
        )
        # 从响应中提取文本
        text = ""
        for block in resp.content:
            if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                text = block.text.strip()
                break
            elif type(block).__name__ == "ThinkingBlock" and hasattr(block, "thinking"):
                # 从 thinking 末尾找 JSON
                thinking = block.thinking
                # 找最后一个完整的 JSON 对象
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
            return {"intent": "unknown", "params": {}}
        print(f"LLM 返回: {text}")  # 调试
        data = json.loads(text)
        # 统一字段名
        intent = data.get("intent", "unknown")
        params = data.get("params", data.get("parameters", {}))
        # product_name -> product_code
        if "product_name" in params:
            params["product_code"] = params.pop("product_name")
        return {"intent": intent, "params": params}
    except Exception as e:
        print(f"意图识别错误: {e}")  # 调试
        return {"intent": "unknown", "params": {}}
