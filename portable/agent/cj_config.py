import json
import os
import sys

APP_NAME = "claw-jump"

if sys.platform == "win32":
    _config_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
elif sys.platform == "darwin":
    _config_dir = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
else:
    _config_dir = os.path.expanduser(f"~/.config/{APP_NAME}")

CONFIG_FILE = os.path.join(_config_dir, "config.json")

DEFAULTS = {
    "overlay_offset_x": 0,
    "overlay_offset_y": 0,
    "has_persisted_offset": False,
    "port": 47653,
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            merged = dict(DEFAULTS)
            merged.update(cfg)
            return merged
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULTS)


def save_config(config):
    os.makedirs(_config_dir, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
