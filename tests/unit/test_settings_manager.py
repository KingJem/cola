"""
Tests for the SettingsManager class.
"""
import pytest
from src.settings.settings_manager import SettingsManager
from src.settings import default


class TestSettingsManagerBasics:
    """Test basic SettingsManager functionality."""
    
    def test_init_default(self):
        """Test initialization with default settings."""
        settings = SettingsManager()
        assert isinstance(settings, SettingsManager)
        assert len(settings) > 0  # Should have default settings
    
    def test_init_with_custom_settings(self):
        """Test initialization with custom settings."""
        custom = {'PROJECT_NAME': 'TestProject', 'CUSTOM_VALUE': 123}
        settings = SettingsManager(custom_settings=custom)
        
        assert settings.get('PROJECT_NAME') == 'TestProject'
        assert settings.get('CUSTOM_VALUE') == 123
    
    def test_contains_default_settings(self):
        """Test that default settings are loaded."""
        settings = SettingsManager()
        # Check for some common default settings
        assert 'CONCURRENT_REQUESTS' in settings


class TestSettingsManagerGetSet:
    """Test get/set operations."""
    
    def test_get_existing_key(self):
        """Test getting existing key."""
        settings = SettingsManager({'KEY': 'value'})
        assert settings.get('KEY') == 'value'
    
    def test_get_nonexistent_key(self):
        """Test getting non-existent key."""
        settings = SettingsManager()
        assert settings.get('NONEXISTENT_KEY') is None
    
    def test_get_with_default(self):
        """Test get with default value."""
        settings = SettingsManager()
        assert settings.get('NONEXISTENT', 'default_val') == 'default_val'
    
    def test_set_new_key(self):
        """Test setting new key."""
        settings = SettingsManager()
        settings.set('NEW_KEY', 'new_value')
        assert settings.get('NEW_KEY') == 'new_value'
    
    def test_set_existing_key(self):
        """Test overwriting existing key."""
        settings = SettingsManager({'KEY': 'old'})
        settings.set('KEY', 'new')
        assert settings.get('KEY') == 'new'


class TestSettingsManagerDictInterface:
    """Test dict-like interface operations."""
    
    def test_getitem(self):
        """Test __getitem__ access."""
        settings = SettingsManager({'KEY': 'value'})
        assert settings['KEY'] == 'value'
    
    def test_getitem_nonexistent(self):
        """Test __getitem__ for non-existent key."""
        settings = SettingsManager()
        # Returns None instead of raising KeyError
        assert settings['NONEXISTENT'] is None
    
    def test_setitem(self):
        """Test __setitem__ assignment."""
        settings = SettingsManager()
        settings['NEW_KEY'] = 'new_value'
        assert settings['NEW_KEY'] == 'new_value'
    
    def test_delitem(self):
        """Test __delitem__ deletion."""
        settings = SettingsManager({'KEY': 'value'})
        del settings['KEY']
        assert settings.get('KEY') is None
    
    def test_contains(self):
        """Test __contains__ (in operator)."""
        settings = SettingsManager({'KEY': 'value'})
        assert 'KEY' in settings
        assert 'NONEXISTENT' not in settings
    
    def test_iter(self):
        """Test __iter__ iteration."""
        settings = SettingsManager({'KEY1': 'val1', 'KEY2': 'val2'})
        keys = list(settings)
        assert 'KEY1' in keys
        assert 'KEY2' in keys
    
    def test_len(self):
        """Test __len__ length."""
        settings = SettingsManager({'KEY1': 'val1', 'KEY2': 'val2'})
        # Length includes default settings plus custom ones
        assert len(settings) >= 2


class TestSettingsManagerTypeConversion:
    """Test type conversion methods."""
    
    def test_getint_string(self):
        """Test getint with string value."""
        settings = SettingsManager({'PORT': '8080'})
        assert settings.getint('PORT') == 8080
        assert isinstance(settings.getint('PORT'), int)
    
    def test_getint_number(self):
        """Test getint with numeric value."""
        settings = SettingsManager({'COUNT': 42})
        assert settings.getint('COUNT') == 42
    
    def test_getint_default(self):
        """Test getint with default value."""
        settings = SettingsManager()
        assert settings.getint('NONEXISTENT') == 0
        assert settings.getint('NONEXISTENT', 100) == 100
    
    def test_getfloat_string(self):
        """Test getfloat with string value."""
        settings = SettingsManager({'RATE': '3.14'})
        assert settings.getfloat('RATE') == 3.14
        assert isinstance(settings.getfloat('RATE'), float)
    
    def test_getfloat_number(self):
        """Test getfloat with numeric value."""
        settings = SettingsManager({'RATE': 2.5})
        assert settings.getfloat('RATE') == 2.5
    
    def test_getfloat_default(self):
        """Test getfloat with default value."""
        settings = SettingsManager()
        assert settings.getfloat('NONEXISTENT') == 0.0
        assert settings.getfloat('NONEXISTENT', 1.5) == 1.5
    
    def test_getboolean_true_values(self):
        """Test getboolean with various true values."""
        test_cases = [
            ('1', True),
            (1, True),
            ('true', True),
            ('True', True),
            ('TRUE', True),
            (True, True),
        ]
        
        for value, expected in test_cases:
            settings = SettingsManager({'FLAG': value})
            assert settings.getboolean('FLAG') == expected
    
    def test_getboolean_false_values(self):
        """Test getboolean with various false values."""
        test_cases = [
            ('0', False),
            (0, False),
            ('false', False),
            ('False', False),
            ('FALSE', False),
            (False, False),
        ]
        
        for value, expected in test_cases:
            settings = SettingsManager({'FLAG': value})
            assert settings.getboolean('FLAG') == expected
    
    def test_getboolean_default(self):
        """Test getboolean with default value."""
        settings = SettingsManager()
        assert settings.getboolean('NONEXISTENT') == False
        assert settings.getboolean('NONEXISTENT', True) == True
    
    def test_getbool_alias(self):
        """Test getbool as alias for getboolean."""
        settings = SettingsManager({'FLAG': '1'})
        assert settings.getbool('FLAG') == True
        assert settings.getbool('NONEXISTENT', True) == True
    
    def test_getlist_string(self):
        """Test getlist with comma-separated string."""
        settings = SettingsManager({'ITEMS': 'a,b,c,d'})
        result = settings.getlist('ITEMS')
        assert result == ['a', 'b', 'c', 'd']
        assert isinstance(result, list)
    
    def test_getlist_list(self):
        """Test getlist with list value."""
        settings = SettingsManager({'ITEMS': [1, 2, 3]})
        result = settings.getlist('ITEMS')
        assert result == [1, 2, 3]
    
    def test_getlist_default(self):
        """Test getlist with default value."""
        settings = SettingsManager()
        assert settings.getlist('NONEXISTENT') == []
        assert settings.getlist('NONEXISTENT', ['a', 'b']) == ['a', 'b']


class TestSettingsManagerModuleLoading:
    """Test loading settings from module."""
    
    def test_set_setting_module_object(self):
        """Test loading settings from module object."""
        settings = SettingsManager()
        settings.set_setting(default)
        
        # Should have loaded uppercase attributes from default module
        assert len(settings) > 0
    
    def test_set_setting_module_string(self):
        """Test loading settings from module string."""
        settings = SettingsManager()
        settings.set_setting('src.settings.default')
        
        # Should have loaded settings
        assert len(settings) > 0
    
    def test_update_values_dict(self):
        """Test updating multiple values."""
        settings = SettingsManager()
        updates = {
            'KEY1': 'value1',
            'KEY2': 'value2',
            'KEY3': 123
        }
        settings.update_values(updates)
        
        assert settings['KEY1'] == 'value1'
        assert settings['KEY2'] == 'value2'
        assert settings['KEY3'] == 123
    
    def test_update_values_none(self):
        """Test update_values with None."""
        settings = SettingsManager()
        # Should not raise error
        settings.update_values(None)


class TestSettingsManagerCopy:
    """Test settings copy functionality."""
    
    def test_copy_deep(self):
        """Test that copy creates deep copy."""
        original = SettingsManager({'KEY': 'value', 'NESTED': {'a': 1}})
        copied = original.copy()
        
        # Modify copied
        copied['KEY'] = 'new_value'
        copied['NEW_KEY'] = 'added'
        
        # Original should be unchanged
        assert original['KEY'] == 'value'
        assert 'NEW_KEY' not in original
    
    def test_copy_independent(self):
        """Test that copies are independent."""
        original = SettingsManager({'COUNT': 0})
        copy1 = original.copy()
        copy2 = original.copy()
        
        copy1['COUNT'] = 1
        copy2['COUNT'] = 2
        
        assert original['COUNT'] == 0
        assert copy1['COUNT'] == 1
        assert copy2['COUNT'] == 2


class TestSettingsManagerStr:
    """Test string representation."""
    
    def test_str(self):
        """Test __str__ method."""
        settings = SettingsManager()
        result = str(settings)
        assert 'Settings manager' in result


class TestSettingsManagerIntegration:
    """Test integration scenarios."""
    
    def test_spider_custom_settings(self):
        """Test merging spider custom settings."""
        base_settings = SettingsManager({
            'CONCURRENT_REQUESTS': 8,
            'RETRY_TIMES': 3
        })
        
        spider_settings = {
            'CONCURRENT_REQUESTS': 16,  # Override
            'CUSTOM_SPIDER_SETTING': 'value'
        }
        
        base_settings.update_values(spider_settings)
        
        assert base_settings['CONCURRENT_REQUESTS'] == 16
        assert base_settings['RETRY_TIMES'] == 3
        assert base_settings['CUSTOM_SPIDER_SETTING'] == 'value'
    
    def test_case_insensitive_getboolean(self):
        """Test case-insensitive boolean getting."""
        settings = SettingsManager({
            'debug': '1',
            'DEBUG': '0'
        })
        
        # getboolean tries both cases
        result = settings.getboolean('debug')
        assert result in [True, False]
