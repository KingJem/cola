from abc import ABCMeta


class Field(dict):
    pass


class ItemMeta(ABCMeta):
    def __new__(cls, name, bases, attrs):
        # 保存类中已定义的FIELDS（如果有）
        existing_fields = attrs.get('FIELDS', None)
        
        # 从Field类定义中提取字段
        fields = {}
        for key, value in list(attrs.items()):
            if isinstance(value, Field):
                fields[key] = value

        cls_instance = super(ItemMeta, cls).__new__(cls, name, bases, attrs)
        
        # 如果有Field定义的字段，使用它们；否则使用existing_fields（如果存在）；默认为空dict
        if fields:
            cls_instance.FIELDS = fields
        elif existing_fields is not None:
            cls_instance.FIELDS = existing_fields
        else:
            cls_instance.FIELDS = {}
            
        return cls_instance
