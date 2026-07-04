class RequestException(Exception):
    pass


class DecodeException(Exception):
    pass


class MiddlewareException(Exception):
    pass


class NotConfigured(Exception):
    """组件缺少必要配置时抛出;中间件/扩展加载器捕获后跳过该组件。"""
    pass


class ReceiverTypeError(TypeError):
    """事件订阅者必须是协程函数。"""
    pass


class ExtensionInitError(Exception):
    """扩展缺少 create_instance 方法或初始化失败。"""
    pass
