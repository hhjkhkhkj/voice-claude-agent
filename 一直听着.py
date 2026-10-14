# -*- coding: utf-8 -*-
"""一直听着：常驻监听的语音版 Claude Code。

和 跟我说话.py 的区别：
    跟我说话.py  —— 一轮一轮来。它想事情的时候是**聋的**，你只能等。
    一直听着.py  —— 麦克风**一直在听**。你在它想事情的时候继续说话，
                    它会存起来，等这条答完接着处理。

    ┌─ 后台线程：一直读麦克风 → 判断你有没有在说话 → 切出一句 → 塞进队列
    └─ 主线程：  从队列取一句 → 识别 → 应声 → Claude 干活 → 念出来

【必须解决的一个物理问题：回授】
    你的喇叭和麦克风在同一个房间。我一出声，麦克风就会把我的话录进去，
    转成文字，再当成"你说的话"回一遍 —— 无限套娃。
    所以这里的规矩是：**播放的时候，麦克风那边一律作废**（见「正在播放」那个开关）。
    代价是：我在说话时你插话，会丢。想插话就等我停。

【阈值怎么定的】
    开机先安静 3 秒，量这段时间的噪音峰值，判定线 = 噪音峰值 × 倍数。
    噪声忽高忽低的房间（你这间），取峰值比取平均值稳。
    ★ 屏幕上会一直显示实时音量和判定线，能一眼看出是不是判定线定高了。

跑法：
    py 一直听着.py
    py 一直听着.py --设备号 1 --倍数 2.0
    py 一直听着.py --安静             不说话，只看音量条（调试用）

退出：按 Ctrl+C。这个形态没有"说退出"——因为它一直在听，容易误触。
"""

import os
import queue
import sys
import threading
import time

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

import numpy as np
import soundfile as sf

import 录音转文字
import 文字转语音
import claude大脑
import 前台

# —————— 参数 ——————
采样率 = 16000
块长 = 0.1
块采样 = int(采样率 * 块长)
最长句 = 30.0          # 一句话最长录这么久，超了强制切
静音结尾 = 1.2         # 说完之后安静这么久，就认为这句完了
起说连续 = 3           # 连续 3 块（0.3 秒）超线才算"真的开始说"——杂音扛不了这么久
校准秒数 = 3
倍数 = 1.8
录音设备 = None
输出设备 = None
只看不动 = False
手动判定线 = None       # 传了就直接用这个
自动量噪 = False        # 默认关：判定线固定 0.001，不自己判别

解析 = sys.argv[1:]
for 位置, 参 in enumerate(解析):
    if 参 == "--安静":
        只看不动 = True
    elif 参 == "--自动":
        自动量噪 = True
    elif 参 == "--设备号" and 位置 + 1 < len(解析):
        录音设备 = int(解析[位置 + 1])
    elif 参 == "--输出设备" and 位置 + 1 < len(解析):
        输出设备 = int(解析[位置 + 1])
    elif 参 == "--倍数" and 位置 + 1 < len(解析):
        倍数 = float(解析[位置 + 1])
    elif 参 == "--判定线" and 位置 + 1 < len(解析):
        手动判定线 = float(解析[位置 + 1])

波形文件 = os.path.join(_本目录, "一直听着_这段.wav")

# —————— 全局状态 ——————
正在播放 = threading.Event()     # 播放时置位，麦克风那边作废
队列 = queue.Queue()
还在跑 = threading.Event()
还在跑.set()

判定线 = [0.02]                  # 用列表包一层，好让线程里改得到
实时音量 = [0.0]
峰值一秒 = [0.0]                 # 这一秒里到过的最高音量，写进日志用
校准完成 = threading.Event()
主线程忙 = threading.Event()      # 主循环在干活时不刷音量条，免得两边打印打架


# —————— 后台线程：一直听 ——————
def 听():
    """一直读麦克风，切出一句完整的话就塞进队列。"""
    import sounddevice as sd

    # ① 开麦克风
    if 自动量噪:
        print(f"⏳ 先安静 {校准秒数} 秒，我在量这屋的底噪……")
    try:
        流 = sd.InputStream(samplerate=采样率, channels=1, dtype="int16", device=录音设备)
        流.start()
    except Exception as 错:
        print(f"❌ 打不开麦克风：{错}")
        还在跑.clear()
        return

    底噪样本 = []
    for _ in range((校准秒数 if 自动量噪 else 0) * 10):
        数据, _ = 流.read(块采样)
        底噪样本.append(float(np.abs(数据).mean()) / 32768.0)
    底噪峰 = max(底噪样本) if 底噪样本 else 0.0
    # ★ 默认**写死 0.001**，不自己判别——自动量噪每次结果都不一样，
    #   底噪一抖判定线就跟着涨，反而把说话声挡在外面。
    #   想让它自己量就加 --自动。
    if 手动判定线 is not None:
        判定线[0] = 手动判定线
        print(f"   判定线 {判定线[0]:.4f}（你指定的）")
    elif 自动量噪:
        判定线[0] = max(底噪峰 * 倍数, 0.001)
        print(f"   判定线 {判定线[0]:.4f}（自动：底噪 {底噪峰:.4f} × {倍数}）")
    else:
        判定线[0] = 0.0003
        print(f"   判定线 {判定线[0]:.4f}（固定值，不自动判别）")
    print(f"   底噪峰值 {底噪峰:.4f} —— 只是量给你看看，不影响判定")

    校准完成.set()
    print()
    print("🎤 在听着了。你直接说话，说完停一下。")
    print("   （屏幕上会实时显示音量，看得出判定线合不合适）")
    print()

    # ② 一直听
    缓冲 = []
    开始说了 = False
    连续 = 0
    静音块 = 0
    静音上限 = int(静音结尾 / 块长)
    最长块 = int(最长句 / 块长)

    while 还在跑.is_set():
        try:
            数据, _ = 流.read(块采样)
        except Exception:
            time.sleep(0.05)
            continue

        # 我在说话 —— 这一块直接作废，防止把我的声音当成你说的
        if 正在播放.is_set():
            缓冲 = []
            开始说了 = False
            连续 = 0
            静音块 = 0
            实时音量[0] = 0.0
            continue

        音量 = float(np.abs(数据).mean()) / 32768.0
        实时音量[0] = 音量
        峰值一秒[0] = max(峰值一秒[0], 音量)

        if 音量 > 判定线[0]:
            连续 += 1
            if not 开始说了 and 连续 >= 起说连续:
                开始说了 = True
                缓冲 = []
            if 开始说了:
                缓冲.append(数据.copy())
                静音块 = 0
        else:
            连续 = 0
            if 开始说了:
                缓冲.append(数据.copy())
                静音块 += 1
                # 说完了
                if 静音块 >= 静音上限:
                    切句(缓冲, 静音块)

                    # 重置
                    缓冲 = []
                    开始说了 = False
                    静音块 = 0
                    continue
            # 没说就不停地丢，别让缓冲涨到天上去

        # 说太久也强制切
        if 开始说了 and len(缓冲) >= 最长块:
            print("   ⚠️ 说得太长了，强制切一句")
            切句(缓冲, 0)
            缓冲 = []
            开始说了 = False
            静音块 = 0

    流.stop()
    流.close()


def 切句(缓冲块, 尾巴静音块):
    """把这一段音频存下来，塞进队列。"""
    if len(缓冲块) - 尾巴静音块 < 5:      # 不足 0.5 秒，多半是杂音
        return
    有效 = 缓冲块[: len(缓冲块) - 尾巴静音块] if 尾巴静音块 else 缓冲块
    音频 = np.concatenate(有效)
    时长 = len(音频) / 采样率
    if 时长 < 0.4:
        return
    sf.write(波形文件, 音频, 采样率)
    print(f"   🔴 收到一句（{时长:.1f} 秒），进队列")
    队列.put(波形文件)


# —————— 音量条 ——————
def 音量条线程():
    while 还在跑.is_set():
        if 主线程忙.is_set():
            time.sleep(0.2)
            continue
        音量 = 实时音量[0]
        有线 = 判定线[0]
        宽 = 40
        条 = "#" * min(int(音量 * 200), 宽)
        过线 = "过线" if 音量 > 有线 else "    "
        状态 = "正在播放(收音作废)" if 正在播放.is_set() else "听着"
        print(f"   [{状态}] {音量:.4f} {过线} 判定线{有线:.4f} |{条:<{宽}}|",
              end="\r", flush=True)
        time.sleep(0.12)


# —————— 应声（预生成，零延迟）——————
import random

应声备选 = ["嗯，我看看", "好，我去查", "稍等啊", "行，马上", "收到", "好嘞，等一下"]
应声目录 = os.path.join(_本目录, "应声库")


def 准备应声库():
    os.makedirs(应声目录, exist_ok=True)
    缺的 = [句 for 句 in 应声备选
            if not os.path.exists(os.path.join(应声目录, 句 + ".wav"))]
    for 句 in 缺的:
        文字转语音.转语音(句, os.path.join(应声目录, 句 + ".wav"))


def 说文字(文字, 文件名, 用应声库=False):
    """合成 + 播放。播放期间把麦克风那边屏蔽掉。"""
    if 用应声库:
        路径 = os.path.join(应声目录, 文字 + ".wav")
    else:
        路径 = os.path.join(_本目录, 文件名)
        文字转语音.转语音(文字, 路径)
    正在播放.set()
    try:
        文字转语音.播放(路径, 输出设备)
    finally:
        正在播放.clear()


def 说话化(文本):
    行 = []
    在代码块 = False
    for 原行 in 文本.splitlines():
        行干净 = 原行.rstrip()
        if 行干净.strip().startswith("```"):
            在代码块 = not 在代码块
            continue
        if 在代码块:
            continue                      # 代码内容不念
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


def 截断(文本, 上限=320):
    if len(文本) <= 上限:
        return 文本, False
    切 = 文本[:上限]
    for 标点 in ("。", "！", "？", "\n", "，"):
        位置 = 切.rfind(标点)
        if 位置 > 上限 * 0.6:
            切 = 切[: 位置 + 1]
            break
    return 切, True


# —————— 日志：每秒把麦克风电平落盘，不用看窗口也能诊断 ——————
日志文件 = os.path.join(_本目录, "_一直听着.log")
电平日志 = os.path.join(_本目录, "_麦电平.log")


def 电平日志线程():
    """每秒写一行：这句话的时间、音量、判定线、有没有过线。"""
    while 还在跑.is_set():
        time.sleep(1.0)
        本秒 = 峰值一秒[0]
        峰值一秒[0] = 0.0
        try:
            with open(电平日志, "a", encoding="utf-8") as 文件:
                过 = "★过线" if 本秒 > 判定线[0] else "     "
                文件.write(f"{time.strftime('%H:%M:%S')} 秒内最高 {本秒:.4f} "
                           f"判定线 {判定线[0]:.4f} {过}\n")
        except Exception:
            pass


def 记日志(最多, 问题, 类型, 识别, 分流, 应声, 干活):
    try:
        with open(日志文件, "a", encoding="utf-8") as 文件:
            文件.write(
                f"{time.strftime('%H:%M:%S')} 第{最多}轮 [{类型}] "
                f"识别{识别:.1f} 前台{分流:.1f} 应声{应声:.1f} 干活{干活:.1f} "
                f"| {问题[:40]}\n"
            )
    except Exception:
        pass


# —————— 主线程 ——————
def 主循环():
    print("=" * 56)
    print("🎙  一直听着 —— 语音版 Claude Code（常驻监听）")
    print("=" * 56)
    print(f"  麦克风     ： {录音设备 if 录音设备 is not None else '系统默认'}")
    print(f"  干活目录   ： {claude大脑.默认工作目录}")
    print(f"  可用工具   ： {claude大脑.允许工具}")
    print("  按 Ctrl+C 结束。")
    print()

    准备应声库()

    线程 = threading.Thread(target=听, daemon=True)
    线程.start()
    # 等校准完（最多等 20 秒，麦克风打不开就别干等）
    校准完成.wait(timeout=20)
    if not 校准完成.is_set():
        print("❌ 麦克风没能打开，看看设备号对不对（py 录音转文字.py --设备）")
        return

    if 只看不动:
        print("（--安静 模式：只听不答，Ctrl+C 退出）")
        while True:
            time.sleep(1)
        return

    # ★ 踩过的坑：这里原来写的是 音量条线程()——函数调用，不是线程。
    #   那一行永远不返回，主线程就卡在音量条里，队列里的句子一句也轮不到。
    #   现象：屏幕上音量条一直刷，但永远不说"第 1 轮"，像卡死。
    threading.Thread(target=音量条线程, daemon=True).start()
    threading.Thread(target=电平日志线程, daemon=True).start()

    第几轮 = 0
    while True:
        路径 = 队列.get()
        主线程忙.set()
        第几轮 += 1
        print()
        print(f"———— 第 {第几轮} 轮 ————" + " " * 40)
        总起始 = time.time()

        问题 = 录音转文字.转文字(路径).strip()
        识别完 = time.time()
        print("👤 你说：", 问题)
        if not 问题:
            print("   （没听清，跳过）")
            主线程忙.clear()
            continue

        if 问题 in ("退出", "再见", "拜拜"):
            说文字("好，收工。", "_收工.wav")
            break

        # 前台分流：闲聊/常识/时间，它自己答（约 1 秒）；要动手才惊动 Claude
        类型, 前台话, 分流耗时 = 前台.分流(问题)
        分完 = time.time()
        print(f"🧭 前台判定：{类型}（{分流耗时:.1f}s）")

        if 类型 == "直接答":
            print(f"⚡ 快答：{前台话}")
            说文字(前台话, "_快答.wav")
            答完 = time.time()
            print(f"   ⏱ 识别 {识别完-总起始:.1f}s ｜ 前台 {分完-识别完:.1f}s ｜ "
                  f"快答 {答完-分完:.1f}s ｜ 共 {答完-总起始:.1f}s")
            记日志(第几轮, 问题, "直接答", 识别完-总起始, 分完-识别完, 答完-分完, 0)
            主线程忙.clear()
            continue

        # 要动手：先用**预生成**的应声接住话头（零延迟），再交给 Claude
        句 = random.choice(应声备选)
        print(f"⚡ 应声：{句}　（后台 Claude 开始干活）")
        说文字(句, None, 用应声库=True)
        应声完 = time.time()

        print("🧠 Claude 干活中……（这段时间你继续说话，我会存着）")
        try:
            答案, 耗时 = claude大脑.干活(问题)
        except Exception as 错:
            答案, 耗时 = f"出错了：{错}", 0.0
        干完 = time.time()
        print(f"🤖 Claude（{耗时:.1f}s）：")
        print(答案)
        print()

        要念, 被截断 = 截断(说话化(答案))
        if 要念:
            说文字(要念, "_回答.wav")
        if 被截断:
            print("   （太长，剩下的在屏幕上）")
            说文字("太长了，剩下的我打在屏幕上了。", "_太长.wav")

        print(f"   ⏱ 识别 {识别完-总起始:.1f}s ｜ 前台 {分完-识别完:.1f}s ｜ "
              f"应声 {应声完-分完:.1f}s ｜ 干活 {干完-应声完:.1f}s ｜ "
              f"念完共 {time.time()-总起始:.1f}s")
        记日志(第几轮, 问题, "要动手", 识别完-总起始, 分完-识别完,
               应声完-分完, 干完-应声完)
        if not 队列.empty():
            print(f"   （队列里还存着 {队列.qsize()} 句，马上接着来）")
        主线程忙.clear()


if __name__ == "__main__":
    起始 = time.time()
    print()
    try:
        主循环()
    except KeyboardInterrupt:
        pass
    还在跑.clear()
    print()
    print("👋 收工。")
