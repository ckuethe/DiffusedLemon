import json
import os
from typing import Dict, Any


class Config:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.config_path = config_path
        self._config = {}
        self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                self._config = json.load(f)
        self._apply_env_vars()

    def _apply_env_vars(self):
        env_mapping = {
            "LM_SERVER_URI": "server_uri",
            "LM_STORAGE_DIR": "storage_dir",
            "LM_LOG_FILE": "log_file",
            "LM_AUTH_TOKEN": "auth_token",
            "LM_DEFAULT_MODEL": "default_model",
            "LM_DEFAULT_SIZE": "default_size",
            "LM_PROMPT_ASSIST_MODEL": "prompt_assist_model",
            "LM_PROMPT_ASSIST_SYSTEM_PROMPT": "prompt_assist_system_prompt",
        }
        for env_var, config_key in env_mapping.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                if config_key == "auth_token" and value == "":
                    value = None
                self._config[config_key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def __getattr__(self, name: str) -> Any:
        if name in self._config:
            return self._config[name]
        raise AttributeError(f"'Config' object has no attribute '{name}'")

    def to_dict(self) -> Dict[str, Any]:
        return self._config.copy()


config = Config()
