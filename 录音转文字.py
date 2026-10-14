# -*- coding: utf-8 -*-
"""第一步：麦克风 → 文字

最笨的版本：按固定秒数录一段 → 存成 wav → 发给硅基流动转文字 → 打印。

先跑通这一段，后面才接得上"文字 → AI → 文字 → 语音 → 播放"。

跑法：
    py 录音转文字.py            录 5 秒
    py 录音转文字.py 8          录 8 秒
    py 录音转文字.py --设备     先看电脑上有没有麦克风
"""

import os
import sys
import time

_项目根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _项目根 not in sys.path:
    sys.path.insert(0, _项目根)

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf

from config import 硅基密钥

# —————— 参数 ——————
采样率 = 16000          # 语音识别够用了，文件也小
默认秒数 = 5
接口 = "https://api.siliconflow.cn/v1/audio/transcriptions"
识别模型 = "FunAudioLLM/SenseVoiceSmall"
录音文件 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "录音.wav")


def 看设备():
    """列出电脑上的音频设备。没有麦克风的话，这里一眼就能看出来。"""
    print("电脑上的音频设备：")
    print(sd.query_devices())
    try:
        默认输入 = sd.query_devices(kind="input")
        print("\n默认输入设备：", 默认输入["name"])
    except Exception as e:
        print("\n⚠️ 找不到可用的输入设备（麦克风）：", repr(e))


def 录音到说完(最长=15, 说完静音=1.5, 设备=None, 准备=2, 倍数=1.8, 音量阈值=None):
    """录到用户说完为止（靠音量自动判断），最长不超过「最长」秒。

    ★ 人主动开口的形状：你什么时候想说就说，说完停一下它自己停。

    【两个踩过的坑，都在这里修了】

    坑一：判定阈值写死成 0.012。
        结果这屋底噪一直高于它，程序从第一秒就以为"你在说话"，30 秒不停。
        → 现在先花 1 秒量环境噪音，判定线 = 噪音 × 倍数。

    坑二：短促杂音会被当成"开始说话"。
        椅子响一下、碰一下键盘，音量冲过判定线 → 以为你说完了 → 停了。
        而真正的说话在它停之后才发生，整段白录。
        → 现在要求**连续 3 块（0.3 秒）**都超线，才算真的在说话。
           杂音都是一下子的事，扛不住连续 0.3 秒。
    """
    块长 = 0.1                       # 每 0.1 秒看一次音量
    块采样 = int(采样率 * 块长)
    最长块数 = int(最长 / 块长)
    静音块上限 = int(说完静音 / 块长)
    连续块要求 = 3                   # 要连续 3 块超线才算"真的开始说了"

    if 准备:
        print(f"⏳ {准备} 秒后开始，之后你随时开口都行")
        for 剩 in range(准备, 0, -1):
            print(f"   {剩}", end="\r", flush=True)
            time.sleep(1)

    print("🎤 在听……你直接说话，说完停一下")

    录音块 = []
    开始说了 = False
    静音块 = 0
    连续块 = 0
    基线 = 0.0
    阈值 = 音量阈值 or 0.02

    with sd.InputStream(samplerate=采样率, channels=1, dtype="int16", device=设备) as 流:
        # —————— 先量 1 秒环境噪音（这一秒不算进录音）——————
        样本 = []
        for _ in range(20):            # 量 2 秒
            数据, _ = 流.read(块采样)
            样本.append(float(np.abs(数据).mean()) / 32768.0)
        # ★ 用**峰值**，不用中位数。
        #   这屋的噪音忽高忽低：中位数可能只有 0.008，但尖峰经常冲到 0.04。
        #   拿中位数定线 → 尖峰一直超线 → "安静 1.8 秒"永远等不到 → 录满 15 秒。
        #   所以基线取这 2 秒里的最高值，把噪音的天花板量出来。
        基线 = float(np.max(样本))
        if 音量阈值 is None:
            阈值 = max(基线 * 倍数, 0.01)
        print(f"   （噪音峰值 {基线:.4f}　判定线 {阈值:.4f}）")

        # —————— 正式听 ——————
        最高 = 0.0
        for _ in range(最长块数):
            数据, _ = 流.read(块采样)
            录音块.append(数据.copy())
            音量 = float(np.abs(数据).mean()) / 32768.0     # 换算成 0~1
            最高 = max(最高, 音量)

            if 音量 > 阈值:
                连续块 += 1
                if not 开始说了 and 连续块 >= 连续块要求:
                    开始说了 = True
                    print("   🔴 听到你说话了……", flush=True)
                if 开始说了:
                    静音块 = 0
            else:
                连续块 = 0                # 断了就归零，杂音扛不过这关
                if 开始说了:
                    静音块 += 1
                    if 静音块 >= 静音块上限:
                        break

    print(f"   （这段最高音量 {最高:.4f}　判定线 {阈值:.4f}）")
    if 开始说了:
        print("   ✅ 你说完了")
        # 尾巴那一段静音别送去识别，白占长度
        if 0 < 静音块 < len(录音块):
            有效 = 录音块[: len(录音块) - 静音块]
        else:
            有效 = 录音块
    else:
        print("   ⚠️ 一直没等到你说话（是不是 F4 亮着？或者声音太小）")
        有效 = 录音块

    音频 = np.concatenate(有效) if len(有效) else np.zeros((0, 1), dtype="int16")
    sf.write(录音文件, 音频, 采样率)
    print(f"   存到：{录音文件}（{len(音频)/采样率:.1f} 秒）")
    return 录音文件


def 录音(秒数, 设备=None, 准备=3):
    """从麦克风录一段，存成 wav，返回文件路径。

    设备=None 就用系统默认的；传数字就指定用第几号设备（见 --设备 列表）。

    【为什么要"准备"那 3 秒】
        agent 发完消息、到脚本真正开录，中间只隔一秒。
        用户还没读完消息，录音已经开始、结束——前三次全白录，就是这个原因。
        所以先倒 3 秒给他反应时间。
    """
    if 准备:
        print(f"⏳ {准备} 秒后开始录，准备一下……")
        for 剩 in range(准备, 0, -1):
            print(f"   {剩}", end="\r", flush=True)
            time.sleep(1)

    print(f"🎤 开始录音，{秒数} 秒——现在就说" + (f"（设备 {设备}）" if 设备 is not None else ""))
    # 先开录，再倒数。
    # （倒数是给说话的人看的，不能倒完才开录——那样第一句话就白说了。）
    音频 = sd.rec(
        int(秒数 * 采样率),
        samplerate=采样率,
        channels=1,
        dtype="int16",
        device=设备,
    )
    for 剩 in range(秒数, 0, -1):
        print(f"   还剩 {剩} 秒", end="\r", flush=True)
        time.sleep(1)
    sd.wait()               # 等真的录完
    print("   ✅ 录完了" + " " * 20)

    sf.write(录音文件, 音频, 采样率)
    print(f"   存到：{录音文件}")
    return 录音文件


def 识别字节(音频数据, 文件名="audio.wav"):
    """把音频**字节**发给硅基流动，拿回文字。

    不碰文件系统——后端收到浏览器传上来的音频，直接丢进来就行。
    """
    表单 = {
        "file": (文件名, 音频数据),
        "model": (None, 识别模型),
    }
    响应 = requests.post(
        接口,
        headers={"Authorization": "Bearer " + 硅基密钥},
        files=表单,
        timeout=60,
    )
    响应.raise_for_status()
    return 响应.json()["text"]


def 转文字(路径):
    """从文件读音频 → 识别。命令行用。"""
    print("📝 转文字中……")
    with open(路径, "rb") as 音频:
        return 识别字节(音频.read(), os.path.basename(路径))


if __name__ == "__main__":
    if "--设备" in sys.argv:
        看设备()
        sys.exit(0)

    设备 = None
    固定秒数 = None
    阈值 = None

    参数表 = sys.argv[1:]
    for 位置, 参数 in enumerate(参数表):
        if 位置 + 1 >= len(参数表):
            continue
        if 参数 == "--设备号":
            设备 = int(参数表[位置 + 1])
        elif 参数 == "--固定":
            固定秒数 = int(参数表[位置 + 1])
        elif 参数 == "--音量":
            阈值 = float(参数表[位置 + 1])

    # 光写个数字（老用法）= 固定秒数
    for 参数 in 参数表:
        if 参数.isdigit() and 固定秒数 is None:
            固定秒数 = int(参数)

    if 固定秒数 is not None:
        # 老模式：固定录 N 秒
        路径 = 录音(固定秒数, 设备)
    else:
        # 默认模式：你说完它自己停 —— 人主动开口，不用掐点
        额外 = {}
        if 阈值 is not None:
            额外["音量阈值"] = 阈值
        路径 = 录音到说完(设备=设备, **额外)

    文字 = 转文字(路径)
    print()
    print("=" * 50)
    print("你说的是：", 文字)
    print("=" * 50)
