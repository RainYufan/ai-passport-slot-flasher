#!/usr/bin/env python3
"""入口:正常启动 GUI;带 --selftest 时做无界面自检(打包后验证 esptool 可用)。"""
import sys


def _selftest() -> int:
    from ai_passport_flasher import flash

    argv = sys.argv
    port = None
    if "--port" in argv:
        port = argv[argv.index("--port") + 1]
    ports = [p for p in flash.list_ports()]
    print("ports:", ports)
    candidates = [port] if port else [dev for dev, _ in ports if "usbmodem" in dev]
    for dev in candidates:
        try:
            layout = flash.detect_device_layout(dev)
        except Exception as exc:  # noqa: BLE001
            print(f"{dev}: ERROR {exc}")
            continue
        if layout is None:
            print(f"{dev}: 未识别为切换器")
            continue
        slots = ", ".join(f"{s.tag}@0x{s.offset:x}({s.size})" for s in layout.slots)
        print(f"{dev}: layout={layout.name_zh} slots=[{slots}]")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    from ai_passport_flasher.gui import main

    raise SystemExit(main())
