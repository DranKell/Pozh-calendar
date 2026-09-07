# -*- coding: utf-8 -*-
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
