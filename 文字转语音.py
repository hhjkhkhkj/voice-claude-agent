# -*- coding: utf-8 -*-
"""文字 → 语音 → 播出来

用硅基流动的 CosyVoice2。和识别用的是同一个密钥，不用再注册。

跑法：
    py 文字转语音.py                     说一句默认的话
    py 文字转语音.py 你好，我是你的客服     说你指定的
"""

import os
import sys

_项目根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _项目根 not in sys.path:
    sys.path.insert(0, _项目根)

import requests
import sounddevice as sd
import soundfile as sf

from config import 硅基密钥

接口 = "https://api.siliconflow.cn/v1/audio/speech"
模型 = "FunAudioLLM/CosyVoice2-0.5B"
音色 = "FunAudioLLM/CosyVoice2-0.5B:alex"     # 预设音色，不行再换（见下面注释）

本目录 = os.path.dirname(os.path.abspath(__file__))
默认输出 = os.path.join(本目录, "回复.wav")


def 合成(文字):
    """文字 → 音频**字节**（wav）。

    不写文件——后端拿到字节直接 base64 传给浏览器。
    注意：这个接口返回的是**音频二进制**，不是 JSON，
    所以用 响应.content（字节），不能用 响应.json()。
    """
    响应 = requests.post(
        接口,
        headers={"Authorization": "Bearer " + 硅基密钥},
        json={
            "model": 模型,
            "input": 文字,
            "voice": 音色,
            "response_format": "wav",
            "sample_rate": 32000,
        },
        timeout=60,
    )

    if 响应.status_code != 200:
        # 出错时把服务端说的话原样带出去，好知道是哪不对（比如音色名不对）
        raise RuntimeError(f"合成失败 {响应.status_code}：{响应.text[:400]}")

    return 响应.content


def 转语音(文字, 输出路径=None):
    """文字 → 音频文件，返回文件路径。命令行用。"""
    输出路径 = 输出路径 or 默认输出
    print("🔊 合成语音中……")

    数据 = 合成(文字)

    with open(输出路径, "wb") as 文件:
        文件.write(数据)

    print(f"   生成了 {len(数据)/1024:.1f} KB → {输出路径}")
    return 输出路径


def 播放(路径, 设备=None):
    """放出来。

    用 sounddevice 而不是 winsound —— 因为 sounddevice 能**指定输出设备**；
    winsound 只能听系统默认设置，默认选错它就放给空气听，而且不报错。
    """
    数据, 采样率 = sf.read(路径, dtype="float32")
    用哪个 = 设备 if 设备 is not None else sd.default.device[1]
    try:
        名字 = sd.query_devices(用哪个)["name"]
    except Exception:
        名字 = "?"
    print(f"▶️  播放中……（输出设备 {用哪个}：{名字}）")
    sd.play(数据, 采样率, device=设备)
    sd.wait()               # 等播完
    print("   播完了")


if __name__ == "__main__":
    参数表 = list(sys.argv[1:])

    # --输出设备 N 指定从哪个设备放（不带就用系统的默认）
    输出设备 = None
    if "--输出设备" in 参数表:
        位置 = 参数表.index("--输出设备")
        if 位置 + 1 < len(参数表):
            输出设备 = int(参数表[位置 + 1])
        参数表 = 参数表[:位置] + 参数表[位置 + 2:]

    文字 = " ".join(a for a in 参数表 if not a.startswith("--"))
    if not 文字:
        文字 = "你好，我是智能客服，请问有什么可以帮您？"

    print("要说的是：", 文字)
    print()
    路径 = 转语音(文字)
    播放(路径, 输出设备)
