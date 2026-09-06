#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_demo_gif.py — 用 mock-api 的真实响应生成 README 演示 GIF

数据全部实时调用运行中的 mock-api（http://localhost:8018），仅渲染层为绘制帧。
用法：
  1. 先起服务: docker compose up -d
  2. 生成:     python scripts/make_demo_gif.py
  3. 停服务:   docker compose down
依赖: pillow, httpx（pip install pillow httpx）
"""
import json
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

BASE = "http://localhost:8018"
OUT = Path(__file__).resolve().parent.parent / "docs" / "img" / "demo.gif"
W, H = 1120, 630
BG = (13, 17, 23)          # GitHub dark
BAR = (22, 27, 34)
FG = (201, 209, 217)
DIM = (110, 118, 129)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
CYAN = (88, 166, 255)
YELLOW = (210, 153, 34)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]

MONO = "C:/Windows/Fonts/consola.ttf"
CJK = "C:/Windows/Fonts/msyh.ttc"


def font(size, cjk=False):
    return ImageFont.truetype(CJK if cjk else MONO, size)


def fetch(client, path):
    # 注意: Docker Desktop 端口转发下, keep-alive 连接的第二个请求会被错误路由成
    # 404 (实测复现)。因此每个请求都走独立连接 (Connection: close 语义)。
    r = httpx.get(BASE + path, timeout=10)
    return r.json(), r.elapsed.total_seconds() * 1000


def new_frame(title):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 终端标题栏
    d.rectangle([0, 0, W, 44], fill=BAR)
    for i, c in enumerate(DOTS):
        d.ellipse([20 + i * 28, 15, 36 + i * 28, 31], fill=c)
    d.text((W // 2, 22), title, anchor="mm", fill=DIM, font=font(18))
    return img, d


def put(d, lines, y=70):
    """lines: [(text, color, size, cjk, bold)]"""
    for text, color, size, cjk, bold in lines:
        f = font(size, cjk)
        if bold:  # 简易加粗: 双写偏移
            d.text((40, y), text, fill=color, font=f)
            d.text((41, y), text, fill=color, font=f)
        d.text((40, y), text, fill=color, font=f)
        y += int(size * 1.45)
    return y


def jlines(obj, indent=0, max_lines=None, key_color=CYAN, val_color=FG):
    """把 obj 转成 [(text,color,...)] 的简易 JSON 风格行。"""
    out = []
    pad = " " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                out.append((f'{pad}"{k}":', key_color, 20, False, False))
                out.extend(jlines(v, indent + 4))
            else:
                s = json.dumps(v, ensure_ascii=False)
                out.append((f'{pad}"{k}": {s}', val_color, 20, False, False))
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:max_lines or len(obj)]):
            s = json.dumps(item, ensure_ascii=False)
            out.append((f"{pad}{s}", val_color, 20, False, False))
        if max_lines and len(obj) > max_lines:
            out.append((f"{pad}... ({len(obj)} items)", DIM, 18, False, False))
    return out


def frame_health(client):
    data, _ = fetch(client, "/health")
    img, d = new_frame("terminal — engineering-delivery-playbook")
    lines = [
        ("$ curl http://localhost:8018/health", GREEN, 22, False, False),
        ("", FG, 12, False, False),
        (json.dumps(data, ensure_ascii=False), FG, 22, False, False),
        ("", FG, 14, False, False),
        ("# 60 个模拟测点 · 30 天时序数据 · 3 类 REST 接口", DIM, 20, True, False),
        ("# FastAPI + Docker, 一键启动", DIM, 20, True, False),
    ]
    put(d, lines)
    return img


def frame_points(client):
    data, _ = fetch(client, "/points?page=1&size=4")
    img, d = new_frame("terminal — GET /points")
    lines = [
        ("$ curl \"http://localhost:8018/points?page=1&size=4\"", GREEN, 22, False, False),
        ("", FG, 10, False, False),
    ]
    lines += jlines(data)[:14]
    put(d, lines)
    return img


def frame_report(client, mode):
    url = ("/reports/monthly?points=point_001,point_002,point_003,point_004,"
           "point_005,point_006,point_007,point_008,point_009,point_010"
           "&start=2026-07-01&end=2026-07-07&mode=" + mode)
    data, elapsed = fetch(client, url)
    img, d = new_frame(f"terminal — GET /reports/monthly (mode={mode})")
    n = data["query_count"]
    qc_color = GREEN if mode == "batch" else RED
    lines = [
        ("$ curl \".../reports/monthly?10 points x 7 days&mode=" + mode + "\"", GREEN, 20, False, False),
        ("", FG, 8, False, False),
        (f"mode        = {data['mode']}", FG, 24, False, False),
        ("rows        = %d  (10 points x 7 daily cols)" % len(data["rows"]), FG, 24, False, False),
        ("elapsed_ms  = %.1f" % data["elapsed_ms"], CYAN, 24, False, False),
        ("", FG, 8, False, False),
        ("query_count = %d" % n, qc_color, 40, False, True),
        ("", FG, 6, False, False),
        ("# 10 测点 × 7 天报表的数据库查询次数", DIM, 19, True, False),
    ]
    if mode == "batch":
        lines.append(("# 批量 IN 查询 + 内存 Map 索引: 恒为 1 次", DIM, 19, True, False))
    else:
        lines.append(("# 逐测点逐天循环查询 (N+1 反面教材)", DIM, 19, True, False))
    put(d, lines)
    return img


def frame_end():
    img, d = new_frame("terminal — try it yourself")
    lines = [
        ("$ git clone https://github.com/yang-shenxu/engineering-delivery-playbook", GREEN, 19, False, False),
        ("$ cd engineering-delivery-playbook", GREEN, 19, False, False),
        ("$ docker compose up -d && ./demo.sh", GREEN, 19, False, False),
        ("", FG, 12, False, False),
        ("60 测点 · 3 类 REST 接口 · batch vs n1 性能对比 · 18 条自检用例", FG, 22, True, False),
        ("", FG, 10, False, False),
        ("性能优化 / 防幻觉提示词 / AI 协作治理 / 配置驱动报表工具", CYAN, 22, True, False),
        ("github.com/yang-shenxu/engineering-delivery-playbook", DIM, 19, False, False),
    ]
    put(d, lines)
    return img


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    with httpx.Client(timeout=10) as client:
        h = fetch(client, "/health")[0]
        if h.get("status") != "ok":
            raise SystemExit("mock-api 未就绪，先 docker compose up -d")
        frames.append(frame_health(client))
        frames.append(frame_points(client))
        frames.append(frame_report(client, "batch"))
        frames.append(frame_report(client, "n1"))
        frames.append(frame_end())
    dwell = [2200, 2600, 3000, 3000, 2600]
    frames[0].save(
        OUT, save_all=True, append_images=frames[1:], loop=0,
        duration=dwell, optimize=True,
    )
    print(f"saved: {OUT}  ({OUT.stat().st_size/1024:.0f} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
