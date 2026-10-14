# -*- coding: utf-8 -*-
r"""语音客服 · 网页后端

    浏览器录音  →  这里识别、思考、合成  →  返回文字 + 音频

跑法：
    py C:\Users\娅土豆\python-study\voice_agent\网页\后端.py
然后浏览器打开 http://127.0.0.1:8020

【为什么必须有后端，不让网页直接调硅基流动】
    密钥放前端就暴露了——任何人在浏览器按 F12 都能看到。
    所以密钥必须留在后端，浏览器只跟后端说话。
"""

import base64
import os
import subprocess
import sys
import tempfile

_本目录 = os.path.dirname(os.path.abspath(__file__))
_voice根 = os.path.dirname(_本目录)
_项目根 = os.path.dirname(_voice根)
for _路径 in (_voice根, _项目根):
    if _路径 not in sys.path:
        sys.path.insert(0, _路径)

import uvicorn
from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import HTMLResponse

import 客服大脑
import 文字转语音
import 录音转文字

页面路径 = os.path.join(_本目录, "页面.html")


# —————— ffmpeg ——————
# 浏览器录出来的是 webm/opus，识别接口要 wav，中间得转一道。
def _找ffmpeg():
    from shutil import which

    找到了 = which("ffmpeg")
    if 找到了:
        return 找到了
    备选 = r"D:\Download\ffmpeg\bin\ffmpeg.exe"
    if os.path.exists(备选):
        return 备选
    return None


FFMPEG = _找ffmpeg()

app = FastAPI()


@app.get("/")
def 首页():
    with open(页面路径, encoding="utf-8") as 文件:
        return HTMLResponse(文件.read())


@app.get("/租户列表")
def 租户列表():
    return {"租户": 客服大脑.有哪些租户()}


def 转成wav(原始):
    """把浏览器录的 webm/opus 转成 16k 单声道 wav。识别接口认这个。"""
    if 原始[:4] == b"RIFF":          # 已经是 wav，不用转
        return 原始
    if not FFMPEG:
        raise RuntimeError("没找到 ffmpeg，转不了音频格式")
    with tempfile.TemporaryDirectory() as 临时:
        进的 = os.path.join(临时, "in.webm")
        出的 = os.path.join(临时, "out.wav")
        with open(进的, "wb") as 文件:
            文件.write(原始)
        结果 = subprocess.run(
            [FFMPEG, "-y", "-i", 进的, "-ar", "16000", "-ac", "1", 出的],
            capture_output=True,
        )
        if 结果.returncode != 0:
            尾巴 = 结果.stderr.decode("utf-8", "ignore")[-400:]
            raise RuntimeError("音频转换失败：" + 尾巴)
        with open(出的, "rb") as 文件:
            return 文件.read()


@app.post("/对话")
async def 对话(音频: UploadFile = File(...), 租户: str = Query("诊所")):
    """收一段录音，回一句话（文字 + 音频）。"""
    try:
        原始 = await 音频.read()
        if not 原始:
            return {"错误": "没收到音频"}

        要识别的 = 转成wav(原始)

        问题 = 录音转文字.识别字节(要识别的, "声音.wav")
        if not 问题.strip():
            return {"错误": "没听清，再说一次吧"}

        回复 = 客服大脑.想(问题, 租户)

        音频数据 = 文字转语音.合成(回复)

        return {
            "问题": 问题,
            "回复": 回复,
            "音频": base64.b64encode(音频数据).decode(),
        }
    except Exception as e:
        print("对话出错：", repr(e))
        return {"错误": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    print("=" * 56)
    print("语音客服 · 网页版")
    print("=" * 56)
    print("租户　：", "、".join(客服大脑.有哪些租户()))
    print("ffmpeg：", FFMPEG or "⚠️ 没找到（浏览器录的音频转不了）")
    print()
    print("浏览器打开 →  http://127.0.0.1:8020")
    print("（想用手机开，就把 127.0.0.1 换成这台电脑的局域网 IP）")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8020)
