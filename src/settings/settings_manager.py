import importlib
from collections.abc import MutableMapping
from copy import deepcopy

from src.settings import default

# 配置优先级:高优先级一旦写入,低优先级不能再覆盖同名键。
# 运行时/CLI 下发的配置必须压过爬虫 custom_settings(平台管控的前提)。
PRIORITY_DEFAULT = 0    # settings/default.py 框架默认
PRIORITY_PROJECT = 10   # 项目级配置文件(预留)
PRIORITY_SPIDER = 20    # Spider.custom_settings
PRIORITY_RUNTIME = 30   # 运行时传入 / CLI / 热配置


class SettingsManager(MutableMapping):

    def __init__(self, custom_settings: dict = None):
        self.attributes = dict()
        self._priorities = dict()
        self.set_setting(default, priority=PRIORITY_DEFAULT)
        # 构造传入的即"本次运行"的配置,优先级最高
        self.update_values(custom_settings, priority=PRIORITY_RUNTIME)

    def __getitem__(self, item):
        if item in self.attributes:
            return self.attributes[item]
        else:
            return None

    def __contains__(self, item):
        return item in self.attributes

    def __setitem__(self, key, value):
        self.set(key, value)

    def __delitem__(self, key):
        del self.attributes[key]
        self._priorities.pop(key, None)

    def set(self, key, value, priority=PRIORITY_RUNTIME):
        if priority < self._priorities.get(key, PRIORITY_DEFAULT):
            return  # 已有更高优先级的值,忽略本次写入
        self.attributes[key] = value
        self._priorities[key] = priority

    def get(self, key, default=None):
        return self.attributes.get(key, default)

    def getint(self, key, default=0):
        return int(self.get(key, default))

    def getfloat(self, key, default=0.0):
        return float(self.get(key, default))

    def getboolean(self, key, default=False):
        # 注意:不能用 or 串联,否则显式的 False 会穿透到默认值
        got = self.get(key, None)
        if got is None:
            got = self.get(key.lower(), None)
        if got is None:
            got = default
        if isinstance(got, str):
            if got.lower() == "true":
                return True
            if got.lower() == "false":
                return False
        try:
            return bool(int(got))
        except (ValueError, TypeError):
            raise ValueError(f"无法解析布尔配置 {key}={got!r}")

    def getbool(self, key, default=False):
        return self.getboolean(key, default)

    def getlist(self, key, default=None):
        value = self.get(key, default or [])
        if isinstance(value, str):
            return value.split(',')
        return list(value)

    def set_setting(self, module, priority=PRIORITY_PROJECT):
        if isinstance(module, str):
            module = importlib.import_module(module)

        for key in dir(module):
            if key.isupper():
                self.set(key, getattr(module, key), priority=priority)

    def update_values(self, custom_settings, priority=PRIORITY_RUNTIME):
        if custom_settings:
            for key, value in custom_settings.items():
                self.set(key, value, priority=priority)

    def __iter__(self):
        return iter(self.attributes)

    def __len__(self):
        return len(self.attributes)

    def __str__(self):
        return f"Settings manager"

    def copy(self):
        return deepcopy(self)
