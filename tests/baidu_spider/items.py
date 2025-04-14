from src.items import Field
from src import Item


class BaiduItem(Item):

    url = Field()
    title = Field()

class LayItem(Item):

    title = Field()
    answers = Field()
    detail_link = Field()
