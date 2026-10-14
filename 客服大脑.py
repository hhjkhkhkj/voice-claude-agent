# -*- coding: utf-8 -*-
"""客服大脑：文字进，回复出。

【换壳就靠这一个文件】
    它不写死任何业务——人设、知识库、兜底话术全部从 租户配置/xxx.json 读。
    所以：
        诊所客服 = 同一套程序 + 诊所.json
        餐馆客服 = 同一套程序 + 餐馆.json
    加一个新客户 = 写一个新的 json，**代码一行不用改**。

【知识库现在是怎么用的】
    全部塞进 system prompt。因为样例里只有五六条，这样最直接。
    等某家的知识库涨到几百条，再换成向量检索（只捞最相关的几条塞进去）。
    到时候要改的只有 组装人设() 一个函数，别处不用动。

【为什么用 flash 不用 pro】
    ① 语音对**延迟**敏感——等三秒体验就崩，flash 更快
    ② 便宜三分之一（输出 ¥4/百万 vs ¥13.5/百万）
    ③ 客服的话短，用不上 pro 的推理深度
"""

import json
import os
import sys

_项目根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _项目根 not in sys.path:
    sys.path.insert(0, _项目根)

import requests

from config import API_KEY

接口 = "https://api.deepseek.com/chat/completions"
模型 = "deepseek-flash"

本目录 = os.path.dirname(os.path.abspath(__file__))
租户目录 = os.path.join(本目录, "租户配置")


def 有哪些租户():
    """列出 租户配置/ 里所有 json 的名字。"""
    if not os.path.isdir(租户目录):
        return []
    return sorted(
        os.path.splitext(名)[0]
        for 名 in os.listdir(租户目录)
        if 名.endswith(".json")
    )


def 读配置(租户名):
    """读某个租户的配置。名字写错了就报错，并列出有哪些。"""
    路径 = os.path.join(租户目录, 租户名 + ".json")
    if not os.path.exists(路径):
        raise FileNotFoundError(
            f"没有「{租户名}」这个租户。现有：" + "、".join(有哪些租户())
        )
    with open(路径, encoding="utf-8") as 文件:
        return json.load(文件)


def 组装人设(配置):
    """把 人设 + 知识库 + 兜底话术 拼成给模型的 system 消息。

    ⚠️ 以后知识库大了，要改的就是这一个函数（换成"只捞最相关的几条"）。
    """
    行 = [配置["人设"], ""]
    行.append("下面是你能回答的业务信息。**只能依据这些回答**，不在这里面的就说不知道，绝对不要编：")
    for 条 in 配置.get("知识库", []):
        行.append("· " + 条)
    if 配置.get("接不上时"):
        行.append("")
        行.append("遇到答不上来的，就用类似这样的话回复：" + 配置["接不上时"])
    行.append("")
    行.append("记住：你在打电话，不是在写文章。短句，口语，不超过三句。")
    return "\n".join(行)


def 想(问题, 租户="诊所", 历史=None):
    """问一句，回一句。

    历史格式：[{"role": "user"/"assistant", "content": "..."}, ...]
    （现在用不上，留着给"多轮对话"用。）
    """
    配置 = 读配置(租户)

    消息 = [{"role": "system", "content": 组装人设(配置)}]
    for 一轮 in (历史 or []):
        消息.append(一轮)
    消息.append({"role": "user", "content": 问题})

    响应 = requests.post(
        接口,
        headers={
            "Authorization": "Bearer " + API_KEY,
            "Content-Type": "application/json",
        },
        json={"model": 模型, "messages": 消息},
        timeout=60,
    )
    响应.raise_for_status()
    结果 = 响应.json()

    usage = 结果.get("usage", {})
    print(
        f"   [token] 输入 {usage.get('prompt_tokens')}　输出 {usage.get('completion_tokens')}"
    )
    return 结果["choices"][0]["message"]["content"]


if __name__ == "__main__":
    参数表 = list(sys.argv[1:])

    租户 = "诊所"
    if "--租户" in 参数表:
        位置 = 参数表.index("--租户")
        if 位置 + 1 < len(参数表):
            租户 = 参数表[位置 + 1]
        参数表 = 参数表[:位置] + 参数表[位置 + 2:]

    问题 = " ".join(参数表)

    if not 问题:
        print("现有租户：", "、".join(有哪些租户()) or "（无）")
        print()
        print("用法：py 客服大脑.py --租户 诊所 你们几点上班")
        sys.exit(0)

    print(f"【{租户}】问：", 问题)
    print(f"【{租户}】答：", 想(问题, 租户))
