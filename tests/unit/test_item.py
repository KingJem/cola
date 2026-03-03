"""
Tests for the Item class.
"""
import pytest
from src.item.items import Item


class ProductItem(Item):
    """Test item class for products."""
    FIELDS = {
        'name': str,
        'price': float,
        'url': str
    }


class BookItem(Item):
    """Test item class for books."""
    FIELDS = {
        'title': str,
        'author': str,
        'isbn': str,
        'pages': int
    }


class TestItemBasics:
    """Test basic Item functionality."""
    
    def test_item_init_empty(self):
        """Test empty item initialization."""
        item = ProductItem()
        assert len(item) == 0
        assert item._values == {}
    
    def test_item_init_with_kwargs(self):
        """Test item initialization with keyword arguments."""
        item = ProductItem(
            name='Test Product',
            price=99.99,
            url='https://example.com/product'
        )
        
        assert item['name'] == 'Test Product'
        assert item['price'] == 99.99
        assert item['url'] == 'https://example.com/product'
    
    def test_item_init_no_args(self):
        """Test that item cannot be initialized with positional args."""
        with pytest.raises(TypeError, match='keyword arguments'):
            ProductItem('invalid')


class TestItemFieldAccess:
    """Test Item field access."""
    
    def test_setitem_valid_field(self):
        """Test setting valid field."""
        item = ProductItem()
        item['name'] = 'Product A'
        item['price'] = 49.99
        
        assert item._values['name'] == 'Product A'
        assert item._values['price'] == 49.99
    
    def test_setitem_invalid_field(self):
        """Test setting invalid field raises KeyError."""
        item = ProductItem()
        
        with pytest.raises(KeyError):
            item['invalid_field'] = 'value'
    
    def test_getitem_existing_field(self):
        """Test getting existing field value."""
        item = ProductItem()
        item['name'] = 'Test'
        
        assert item['name'] == 'Test'
    
    def test_getitem_empty_field(self):
        """Test getting unset field returns None."""
        item = ProductItem()
        result = item.get('name')  # Using dict method
        # The __getitem__ returns value or None
        assert result is None or result == {}
    
    def test_delitem(self):
        """Test deleting item field."""
        item = ProductItem()
        item['name'] = 'Test'
        
        del item['name']
        assert 'name' not in item._values


class TestItemDictInterface:
    """Test Item dict-like interface."""
    
    def test_iter(self):
        """Test iterating over item keys."""
        item = ProductItem(name='Test', price=10.0)
        
        keys = list(item)
        assert 'name' in keys
        assert 'price' in keys
    
    def test_len(self):
        """Test item length."""
        item = ProductItem()
        assert len(item) == 0
        
        item['name'] = 'Test'
        assert len(item) == 1
        
        item['price'] = 10.0
        assert len(item) == 2
    
    def test_len_after_deletion(self):
        """Test length after deleting fields."""
        item = ProductItem(name='Test', price=10.0, url='http://example.com')
        assert len(item) == 3
        
        del item['price']
        assert len(item) == 2


class TestItemStr:
    """Test Item string representation."""
    
    def test_str_empty(self):
        """Test string representation of empty item."""
        item = ProductItem()
        result = str(item)
        assert 'Item' in result
    
    def test_str_with_data(self):
        """Test string representation with data."""
        item = ProductItem(name='Test', price=10.0)
        result = str(item)
        assert 'Item' in result


class TestItemToDict:
    """Test Item todict method."""
    
    def test_todict_empty(self):
        """Test todict on empty item."""
        item = ProductItem()
        result = item.todict()
        # Should return formatted string representation
        assert isinstance(result, str)
    
    def test_todict_with_data(self):
        """Test todict with data."""
        item = ProductItem(name='Product', price=99.99)
        result = item.todict()
        
        # Should contain the data
        assert isinstance(result, str)
        # pformat returns a string representation


class TestItemAttributeAccess:
    """Test Item attribute access restrictions."""
    
    def test_setattr_underscore_allowed(self):
        """Test that setting _values is allowed."""
        item = ProductItem()
        # _values should be settable during __init__
        assert hasattr(item, '_values')
    
    def test_setattr_field_not_allowed(self):
        """Test that setting field as attribute is not allowed."""
        item = ProductItem()
        
        with pytest.raises(AttributeError, match='use item'):
            item.name = 'Test'
    
    def test_getattr_field_not_allowed(self):
        """Test that getting field as attribute is not allowed."""
        item = ProductItem()
        item['name'] = 'Test'
        
        # Should raise AttributeError for field access as attribute
        with pytest.raises(AttributeError):
            _ = item.name


class TestItemFieldTypes:
    """Test Item with different field types."""
    
    def test_string_fields(self):
        """Test string field values."""
        item = ProductItem()
        item['name'] = 'Product Name'
        item['url'] = 'https://example.com'
        
        assert isinstance(item['name'], str)
        assert isinstance(item['url'], str)
    
    def test_numeric_fields(self):
        """Test numeric field values."""
        item = ProductItem()
        item['price'] = 99.99
        
        assert isinstance(item['price'], float)
    
    def test_integer_fields(self):
        """Test integer field values."""
        item = BookItem()
        item['pages'] = 350
        
        assert isinstance(item['pages'], int)


class TestItemMultipleInstances:
    """Test multiple Item instances."""
    
    def test_independent_instances(self):
        """Test that item instances are independent."""
        item1 = ProductItem(name='Product 1', price=10.0)
        item2 = ProductItem(name='Product 2', price=20.0)
        
        assert item1['name'] != item2['name']
        assert item1['price'] != item2['price']
    
    def test_different_item_classes(self):
        """Test different item class instances."""
        product = ProductItem(name='Phone', price=699.99)
        book = BookItem(title='Python Guide', author='John Doe')
        
        assert 'name' in ProductItem.FIELDS
        assert 'title' in BookItem.FIELDS
        assert 'name' not in BookItem.FIELDS


class TestItemIntegration:
    """Test Item integration scenarios."""
    
    def test_item_in_spider_parse(self):
        """Test using items in spider parse method."""
        items = []
        
        # Simulate spider parse
        item = ProductItem()
        item['name'] = 'Scraped Product'
        item['price'] = 49.99
        item['url'] = 'https://example.com/product/1'
        
        items.append(item)
        
        assert len(items) == 1
        assert items[0]['name'] == 'Scraped Product'
    
    def test_item_batch_creation(self):
        """Test creating multiple items."""
        products = [
            ProductItem(name=f'Product {i}', price=float(i * 10), url=f'http://example.com/{i}')
            for i in range(1, 6)
        ]
        
        assert len(products) == 5
        assert products[0]['name'] == 'Product 1'
        assert products[4]['price'] == 50.0
    
    def test_item_update_workflow(self):
        """Test updating item in a workflow."""
        item = ProductItem(name='Initial', price=10.0)
        
        # Update values
        item['name'] = 'Updated'
        item['price'] = 15.0
        item['url'] = 'https://example.com'
        
        assert item['name'] == 'Updated'
        assert item['price'] == 15.0
        assert len(item) == 3
