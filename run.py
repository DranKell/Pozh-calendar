# -*- coding: utf-8 -*-
import json
from pathlib import Path

import uvicorn

cfg = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
srv_cfg = cfg.get("server", {})
host = str(srv_cfg.get("host", "0.0.0.0"))
port = int(srv_cfg.get("port", 9000))

if __name__ == "__main__":
    title_text = f"Календарь ТО · http://localhost:{port}"
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(f"{title_text} (Сервер работает)")
    except Exception:
        pass
    import sys
    sys.stdout.write(f"\x1b]2;{title_text} (Сервер работает)\x07")
    sys.stdout.flush()

    print()
    print("  КАЛЕНДАРЬ ТО · умный календарь ТО")
    print("  ->  Локально: http://localhost:%d" % port)
    if host == "0.0.0.0":
        print("  ->  По сети:  http://<IP_СЕРВЕРА>:%d" % port)
    print()
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
