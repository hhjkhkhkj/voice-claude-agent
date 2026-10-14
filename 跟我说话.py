# -*- coding: utf-8 -*-
"""跟我说话：语音循环——你说话，Claude 干活，念给你听。

    🎤 听 → 📝 识别 → ⚡ 应声（立刻）→ 🧠 Claude 干活（慢）→ 🔊 念结果

【为什么中间要插一个「应声」】
    这是李博杰书里 6.3.5 那节的核心（印刷页 170）。
    Claude 带工具干活要 10 秒到几分钟；人对着话筒的忍受上限大概 2-3 秒。
    中间没有声音，你会以为它死了。
    所以先说一句「好，我看看」维持话头，把等待变得可以忍受。
    书里点名警告过反面做法：快慢两个模型各自回答，会给出自相矛盾的答案。
    所以这里的应声**不回答任何问题**，只是一句填充词。

【应声为什么是预生成的】
    第一版是现场调 flash 生成 + 云端合成，实测要 2.5 秒才出声——比不说话好不了多少。
    现在改成开机时把几句话预先合成成 wav 存进 应声库/，轮到谁就直接播，**延迟只剩播放本身**。
    书里 6.3.6 讲的也是这个思路：停顿、填充词本身就是"人在思考"的信号。

跑法：
    py 跟我说话.py                  用默认设置
    py 跟我说话.py --不说应声        关掉应声（对比一下就知道它值不值）
    py 跟我说话.py --设备号 3        指定麦克风（先用 录音转文字.py --设备 看编号）

退出：说「退出」「再见」「不聊了」，或者按 Ctrl+C
"""

import os
import random
import sys
import time

# ★ 坑（2026-10-05 踩过）：Windows 控制台默认 GBK，脚本里 print 的 emoji
#   （🎤🧠🔊）会直接 UnicodeEncodeError 崩掉，而且崩得没头没尾。
#   用 cmd 开独立窗口跑时必踩，PowerShell 里有时侥幸不炸。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_本目录 = os.path.dirname(os.path.abspath(__file__))
_项目根 = os.path.dirname(_本目录)
for _路径 in (_本目录, _项目根):
    if _路径 not in sys.path:
        sys.path.insert(0, _路径)

import 录音转文字
import 文字转语音
import claude大脑
from config import API_KEY      # 保留：想换回现场生成应声时要用

# —————— 参数 ——————
录音设备 = None          # None = 系统默认
输出设备 = None          # None = 系统默认
要说应声 = True
朗读上限 = 320           # 超过这个字数就不再念，剩下的打在屏幕上
退出词 = {"退出", "再见", "拜拜", "不聊了", "结束", "关机"}

解析 = sys.argv[1:]
for 位置, 参 in enumerate(解析):
    if 参 == "--不说应声":
        要说应声 = False
    elif 参 == "--设备号" and 位置 + 1 < len(解析):
        录音设备 = int(解析[位置 + 1])
    elif 参 == "--输出设备" and 位置 + 1 < len(解析):
        输出设备 = int(解析[位置 + 1])
    elif 参 == "--朗读上限" and 位置 + 1 < len(解析):
        朗读上限 = int(解析[位置 + 1])


# —————— 应声库（预先合成，播的时候零等待）——————
应声备选 = [
    "嗯，我看看",
    "好，我去查",
    "稍等啊",
    "行，马上",
    "收到",
    "好嘞，等一下",
    "嗯——",
]
应声目录 = os.path.join(_本目录, "应声库")


def 准备应声库():
    """把应声句子合成成 wav 存起来。已经有的不重做。"""
    os.makedirs(应声目录, exist_ok=True)
    缺的 = [句 for 句 in 应声备选
            if not os.path.exists(os.path.join(应声目录, 句 + ".wav"))]
    if not 缺的:
        return
    print(f"   首次运行，预先生成 {len(缺的)} 句应声（只做这一次，下次直接播）……")
    for 句 in 缺的:
        文字转语音.转语音(句, os.path.join(应声目录, 句 + ".wav"))


def 说应声():
    """立刻播一句预先合成好的应声。零延迟。"""
    句 = random.choice(应声备选)
    路径 = os.path.join(应声目录, 句 + ".wav")
    if not os.path.exists(路径):
        路径 = os.path.join(应声目录, 应声备选[0] + ".wav")
    文字转语音.播放(路径, 输出设备)
    return 句


def 说一句(文字, 文件名):
    """合成 + 播放，一步到位（用于开场、收工这些临时的话）。"""
    路径 = os.path.join(_本目录, 文件名)
    文字转语音.转语音(文字, 路径)
    文字转语音.播放(路径, 输出设备)


# —————— 把给机器看的字，改成给人听的话 ——————
def 说话化(文本):
    """把 markdown 洗掉。

    Claude 把回复打成 markdown 是给屏幕看的：**加粗**、`代码`、### 标题、
    ```代码块```。直接送给 TTS，它会把这些符号一个字一个字念出来，
    听起来像在念乱码。这里先洗一遍。
    """
    行 = []
    在代码块 = False
    for 原行 in 文本.splitlines():
        行干净 = 原行.rstrip()
        if 行干净.strip().startswith("```"):
            在代码块 = not 在代码块
            continue
        if 在代码块:
            continue
        if not 行干净.strip():
            行.append("")
            continue
        行干净 = 行干净.lstrip("#>").lstrip()
        if 行干净.startswith(("- ", "* ", "+ ")):
            行干净 = 行干净[2:]
        for 符号 in ("**", "__", "`", "*"):
            行干净 = 行干净.replace(符号, "")
        行.append(行干净)

    结果 = "\n".join(行)
    while "\n\n\n" in 结果:
        结果 = 结果.replace("\n\n\n", "\n\n")
    return 结果.strip()


def 截断(文本, 上限):
    """太长的别念完——念的人在电话那头会走神。"""
    if len(文本) <= 上限:
        return 文本, False
    切 = 文本[:上限]
    for 标点 in ("。", "！", "？", "\n", "，"):
        位置 = 切.rfind(标点)
        if 位置 > 上限 * 0.6:
            切 = 切[: 位置 + 1]
            break
    return 切, True


# —————— 主循环 ——————
def 主循环():
    print("=" * 56)
    print("🎙  跟我说话 —— 语音版 Claude Code")
    print("=" * 56)
    print(f"  claude.exe ： {claude大脑.CLAUDE}")
    print(f"  可用的工具 ： {claude大脑.允许工具}")
    print(f"  干活目录   ： {claude大脑.默认工作目录}")
    print(f"  应声       ： {'开' if 要说应声 else '关'}")
    print()
    print("  准备应声库……")
    准备应声库()
    print()
    print("  说「退出」或按 Ctrl+C 结束。")
    print()

    说一句("我在，你说吧。", "_开场.wav")
    print()

    第几轮 = 0
    while True:
        第几轮 += 1
        print(f"———— 第 {第几轮} 轮 ————")
        总起始 = time.time()

        # ① 听
        try:
            路径 = 录音转文字.录音到说完(
                最长=25,
                说完静音=1.3,
                设备=录音设备,
                准备=0 if 第几轮 > 1 else 3,
            )
        except KeyboardInterrupt:
            print("\n👋 收工。")
            break
        听完 = time.time()

        # ② 识别
        问题 = 录音转文字.转文字(路径).strip()
        识别完 = time.time()
        print("👤 你说：", 问题)
        if not 问题:
            print("   （没听清，再来一次）")
            print()
            continue

        if any(词 in 问题 for 词 in 退出词) and len(问题) <= 8:
            说一句("好，收工。", "_收工.wav")
            break

        # ③ 应声（零延迟，先把话头接住）
        if 要说应声:
            句 = 说应声()
            print(f"⚡ 应声：{句}")
        应声完 = time.time()

        # ④ Claude 干活（慢思考）
        print("🧠 Claude 干活中……")
        try:
            答案, 耗时 = claude大脑.干活(问题)
        except Exception as 错:
            答案, 耗时 = f"出错了：{错}", 0.0
        干完 = time.time()
        print(f"🤖 Claude（{耗时:.1f}s）：")
        print(答案)
        print()

        # ⑤ 念结果
        要念, 被截断 = 截断(说话化(答案), 朗读上限)
        if 要念:
            说一句(要念, "_回答.wav")
        if 被截断:
            print("   （太长，剩下的打在屏幕上了，自己看）")
            说一句("太长了，剩下的我打在屏幕上了。", "_太长.wav")

        print(f"   ⏱ 听 {听完-总起始:.1f}s ｜ 识别 {识别完-听完:.1f}s ｜ "
              f"应声 {应声完-识别完:.1f}s ｜ 干活 {干完-应声完:.1f}s ｜ "
              f"念完共 {time.time()-总起始:.1f}s")
        print()

    print("=" * 56)
    print("拜拜")
    print("=" * 56)


if __name__ == "__main__":
    try:
        主循环()
    except KeyboardInterrupt:
        print("\n👋 收工。")
