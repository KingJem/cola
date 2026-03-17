import importlib.util
import os
from src.settings.settings_manager import SettingsManager


def get_settings(settings_module: str = 'settings') -> SettingsManager:
    """
    动态加载用户项目的 settings.py 并返回 SettingsManager。
    从当前工作目录查找 settings 模块。
    """
    from src.settings.default import get_default_settings
    manager = SettingsManager(get_default_settings())

    # 尝试加载用户 settings 模块
    cwd = os.getcwd()
    settings_path = os.path.join(cwd, f'{settings_module}.py')
    if os.path.exists(settings_path):
        spec = importlib.util.spec_from_file_location(settings_module, settings_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for key in dir(module):
            if key.isupper():
                manager[key] = getattr(module, key)

    return manager


def load_class(obj):
    if isinstance(obj, str):
        module_name, class_name = obj.rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)

    if callable(obj):
        return obj
