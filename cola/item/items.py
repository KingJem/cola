from collections.abc import MutableMapping
from pprint import pformat

from cola.item import ItemMeta


class Item(MutableMapping, metaclass=ItemMeta):
    FIELDS: dict = dict()

    def __init__(self, *args, **kwargs):
        object.__setattr__(self, '_values', {})
        if args:
            raise TypeError("Item can only be initialized with keyword arguments")
        if kwargs:
            for key, value in kwargs.items():
                self[key] = value

    def __setitem__(self, key, value):
        # 确保FIELDS属性存在并且不是None
        try:
            fields = object.__getattribute__(self, 'FIELDS')
        except AttributeError:
            fields = None
        
        if fields is None:
            object.__setattr__(self, 'FIELDS', {})
            fields = {}
        
        # 如果FIELDS是空字典，允许动态添加字段；否则检查key是否在FIELDS中
        if not fields or key in fields:
            values = object.__getattribute__(self, '_values')
            values[key] = value
        else:
            raise KeyError(f"Field {key!r} is not defined in {self.__class__.__name__}.FIELDS")

    def __getitem__(self, key):
        return self._values.get(key, None)

    def __str__(self):
        values = object.__getattribute__(self, '_values')
        return "Item({})".format(values)

    def __delitem__(self, key):
        del self._values[key]

    def __setattr__(self, key, value):
        if key.startswith('_'):
            object.__setattr__(self, key, value)
        else:
            raise AttributeError(f" use item[{key!r}] = {value!r} to set field value")

    def __getattribute__(self, item):
        field = super().__getattribute__('FIELDS')
        if item in field:
            raise AttributeError(f" use item[{item!r}]  to get field value")
        # 关键修复：返回属性值
        return super().__getattribute__(item)

    def __getattr__(self, item):
        string = f"{self.__class__.__name__} do not support field {item!r}"
        f"Please add the `{item}` field to the {self.__class__.__name__} class and use `item[{item}]`"

        raise AttributeError(string)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def todict(self):
        return pformat(dict(self._values))
