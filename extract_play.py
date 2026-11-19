#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_play.py —— 输入 AI Passport 玩法链接,自动下载合并固件并提取 app 镜像。

用法:
    python extract_play.py "<玩法链接>"
    python extract_play.py "https://ai-passport.folotoy.cn/plays/2378/?v=6123-2"

输出:
    <玩法名>-merged.bin   平台原始合并镜像(带 SHA-256 校验)
    <玩法名>-app.bin      提取出的纯 app 镜像(可直接刷入切换器槽位)

仅用 Python 标准库,无需 pip 安装任何依赖。
"""

import hashlib
import os
import re
import struct
import sys
import urllib.request
import urllib.error

API_BASE = os.environ.get("FOLOTOY_AI_PASSPORT_URL", "https://ai-passport.folotoy.cn")

PART_ENTRY = struct.Struct("<HBBII16sI")
PART_TYPE_APP = 0


def fetch_plays() -> list:
    print(f"正在读取玩法列表({API_BASE}/api/plays)…")
    with urllib.request.urlopen(API_BASE + "/api/plays", timeout=120) as resp:
        import json
        return json.load(resp).get("plays", [])


def find_play(plays: list, url: str) -> dict:
    m = re.search(r"/plays/(\d+)", url)
    if not m:
        raise SystemExit("无法从链接中识别玩法 ID(应为 /plays/<数字>/)。")
    play_id = int(m.group(1))
    for p in plays:
        if p.get("id") == play_id or p.get("projectId") == play_id:
            return p
    raise SystemExit(f"在玩法列表里没找到 ID={play_id} 的玩法。")


def download(url: str, dest: str) -> bytes:
    print(f"下载: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "extract-play/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    return data


def parse_partition_table(raw: bytes) -> list:
    """返回 [(label, kind, subtype, offset, size), ...]"""
    parts = []
    for cursor in range(0, 0xC00, PART_ENTRY.size):
        magic = int.from_bytes(raw[cursor:cursor + 2], "little")
        if magic in (0xFFFF, 0xEBEB):
            break
        if magic != 0x50AA:
            break
        _, kind, subtype, offset, size, label_raw, _ = PART_ENTRY.unpack_from(raw, cursor)
        label = label_raw.split(b"\0", 1)[0].decode("ascii", "strict")
        parts.append((label, kind, subtype, offset, size))
    return parts


def sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s\u00b7]+', "_", name).strip("_")


def process_play(url: str, log=None) -> tuple:
    """下载并提取;返回 (merged_path, app_path)。log 为进度回调。"""
    if log is None:
        log = print
    plays = fetch_plays()
    play = find_play(plays, url)
    title = play.get("title") or {}
    name = (title.get("zh") or title.get("en") or play.get("slug") or f"play-{play.get('id')}")
    fw = play.get("firmware") or {}
    if not fw.get("available") or not fw.get("url"):
        raise SystemExit("该玩法没有可下载的固件。")

    dl_url = fw["url"]
    if dl_url.startswith("/"):
        dl_url = API_BASE + dl_url
    expect_sha = fw.get("sha256")

    safe = sanitize(str(name))
    merged_path = f"{safe}-merged.bin"
    app_path = f"{safe}-app.bin"

    data = download(dl_url, merged_path)

    if expect_sha:
        actual = hashlib.sha256(data).hexdigest()
        log(f"SHA-256: {actual}")
        if actual != expect_sha:
            raise SystemExit("SHA-256 校验失败!下载的文件可能损坏,请重试。")
        log("SHA-256 校验通过。")
    else:
        log("平台未提供 SHA-256,跳过校验。")

    if len(data) < 0x9000:
        raise SystemExit("文件太小,不像合并镜像。")

    parts = parse_partition_table(data[0x8000:0x9000])
    apps = [p for p in parts if p[1] == PART_TYPE_APP]
    if not apps:
        raise SystemExit("合并镜像里没有找到 app 分区。")
    label, kind, subtype, offset, size = apps[0]
    log(f"app 分区: {label} @ 0x{offset:x}")

    app = data[offset:]
    with open(app_path, "wb") as f:
        f.write(app)
    log(f"app 镜像大小: {len(app)} 字节 ({len(app)/1024/1024:.2f} MB)")
    return os.path.abspath(merged_path), os.path.abspath(app_path)


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else input("请输入玩法链接: ").strip()
    if not url:
        raise SystemExit("没有输入链接。")
    merged, app = process_play(url)
    print(f"\n完成:")
    print(f"  合并镜像: {merged}")
    print(f"  app 镜像: {app}")
    print("\n把 *-app.bin 拖进「AI Passport 槽位刷写助手」选择固件即可刷入槽位。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        raise SystemExit(f"网络错误: {exc}")
