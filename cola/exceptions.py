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


class IgnoreRequest(Exception):
    """中间件抛出以丢弃当前请求(如 offsite 过滤);引擎记录后跳过。"""

    def __init__(self, msg: str = ''):
        super().__init__(msg)
        self.msg = msg


class DownloadMaxsizeExceeded(Exception):
    """响应体超过 DOWNLOAD_MAXSIZE 限制。"""
    pass
