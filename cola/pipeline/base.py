"""Pipeline 基类与 DropItem 异常"""


class DropItem(Exception):
    """
    在 Pipeline 中抛出此异常以丢弃当前 Item。
    被丢弃的 Item 不会传递给后续 Pipeline。

    用法：
        async def process_item(self, item, spider):
            if not item.get('name'):
                raise DropItem(f"Missing name in item: {item}")
            return item
    """
    pass


class BasePipeline:
    """
    所有 Pipeline 的基类。

    子类应实现 process_item()，可选实现 open_spider() 和 close_spider()。
    """

    @classmethod
    def create_instance(cls, crawler):
        return cls()

    async def open_spider(self, spider):
        """Spider 开始爬取时调用。可用于建立数据库连接、打开文件等。"""
        pass

    async def close_spider(self, spider):
        """Spider 结束爬取时调用。可用于关闭连接、刷新文件等。"""
        pass

    async def process_item(self, item, spider):
        """
        处理每个 Item。必须返回 item 或抛出 DropItem。

        Args:
            item: Spider 爬取到的数据（dict 或 Item 实例）
            spider: 当前 Spider 实例

        Returns:
            处理后的 item（可被修改）

        Raises:
            DropItem: 丢弃此 item
        """
        raise NotImplementedError(f"{type(self).__name__} must implement process_item()")
