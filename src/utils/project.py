from src.settings.settings_manager import SettingsManager


def get_settings():
    settings = SettingsManager({"1": 2})
    settings.set_setting(settings)
    return settings


def load_class(obj):
    if  isinstance(obj, str):
        module_name, class_name = obj.rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)

    if callable(obj):
        return obj


