# -*- coding: utf-8 -*-
"""前台：一句话进来，它决定「自己答」还是「交给后面的 Claude」。

【为什么要有这个东西】
    实测：claude.exe 起一个进程最简也要 5.7 秒，带工具 10 秒起。
    你问"今天几号""你叫什么"，为这一句话等 10 秒，整条链路就没法用了。

    但大部分话根本不用查文件、不用跑命令——常识就够了。
    所以让快模型（deepseek-flash，1 秒内）先接：
      · 能答的，它直接答完 —— 你 1 秒多就听到回复
      · 要动手的，它只回一句应声 —— 然后交给 Claude，同时你耳边不空

【这是书上哪一条】
    李博杰《深入理解 AI Agent》6.2.6（印刷页 160）：
    「硬编码的规则有其局限性，事件的语义决定了处理方式……
      **建议使用轻量级的分类 LLM 作为事件路由器**，
      在事件到达时快速判断应该采用哪种策略。」
    以及 6.3.5（印刷页 170）方案二「快思考交互，慢思考提醒」。

【一个请求同时干两件事】
    不用先问"要不要动手"再问"那你答什么"——那是两次调用，翻倍延迟。
    让 flash 一次输出：第一行给结论（答，还是只应声），后面才是内容。
"""

import re
import time
from datetime import datetime

import requests

import sys
import os

_项目根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _项目根 not in sys.path:
    sys.path.insert(0, _项目根)

from config import API_KEY

接口 = "https://api.deepseek.com/chat/completions"
模型 = "deepseek-flash"

_星期 = "一二三四五六日"[datetime.now().weekday()]
_现在 = datetime.now().strftime("%Y年%m月%d日 %H:%M")

人设 = (
    "你是一个语音助手的前台接线员。用户的这句话刚从语音识别出来，可能有错别字。\n"
    f"【当前时间】{_现在}，星期{_星期}。用户问时间/日期/星期，直接用这个答，别说你不知道。\n"
    "你要先判断：这句话**需不需要去查这个人的电脑**才能回答。\n"
    "\n"
    "【判断标准】\n"
    "· 闲聊、打招呼、问时间、问常识、问你自己、算数、翻译、解释概念 —— "
    "**不需要查他的电脑**，你自己答。\n"
    "· 问他电脑上的文件、代码、数据、目录、项目、日志，或者要他电脑上执行操作 —— "
    "**需要动手**，你只回一句应声，让后台去办。\n"
    "\n"
    "【输出格式，严格遵守，第一行必须是下面两种之一】\n"
    "\n"
    "第一行：直接答：\n"
    "后面接你的回答。口语，两三句，100 字内，不要 markdown、列表、代码块。\n"
    "\n"
    "或者\n"
    "\n"
    "第一行：要动手：\n"
    "后面接一句 2-8 字的应声（像「好，我去查」「稍等啊」「嗯，我看看」），"
    "**不要回答问题本身**。\n"
)


def 分流(问题, 超时=20):
    """返回 (类型, 话, 耗时)。

    类型是 "直接答" 或 "要动手"。
    出错时当 "要动手" 处理——宁可慢一点，也别让前台瞎编。
    """
    起始 = time.time()
    try:
        响应 = requests.post(
            接口,
            headers={
                "Authorization": "Bearer " + API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "model": 模型,
                "messages": [
                    {"role": "system", "content": 人设},
                    {"role": "user", "content": 问题},
                ],
                "max_tokens": 300,
            },
            timeout=超时,
        )
        响应.raise_for_status()
        原文 = 响应.json()["choices"][0]["message"]["content"].strip()
    except Exception as 错:
        return "要动手", "嗯，我看看", time.time() - 起始

    耗时 = time.time() - 起始

    # 解析第一行的标记
    第一行, _, 其余 = 原文.partition("\n")
    第一行 = 第一行.strip().lstrip("【").rstrip("】")

    if 第一行.startswith("直接答"):
        正文 = 其余.strip() or 第一行.replace("直接答：", "").replace("直接答:", "").strip()
        if not 正文:
            # 它把答案挤在第一行了
            m = re.sub(r"^【?直接答[：:】]*\s*", "", 第一行)
            正文 = m.strip()
        return "直接答", 正文, 耗时

    if 第一行.startswith("要动手"):
        应声 = 其余.strip().splitlines()[0].strip() if 其余.strip() else "嗯，我看看"
        应声 = re.sub(r"^【?要动手[：:】]*\s*", "", 应声).strip()
        应声 = 应声.strip("「」\"'")[:12] or "嗯，我看看"
        return "要动手", 应声, 耗时

    # 没按格式来 —— 当成"它其实答了"
    正文 = re.sub(r"^【?(直接答|要动手)[：:】]*\s*", "", 原文).strip()
    if 正文:
        return "直接答", 正文, 耗时
    return "要动手", "嗯，我看看", 耗时


if __name__ == "__main__":
    import sys

    问题 = " ".join(sys.argv[1:]) or "今天星期几"
    print("问：", 问题)
    类型, 话, 耗时 = 分流(问题)
    print(f"类型：{类型}　（{耗时:.1f}s）")
    print("话　：", 话)
