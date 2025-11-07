"""Configuration management."""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Try config/config.json first, then fallback to config.json in root
            config_path = 'config/config.json'
            if not Path(config_path).exists():
                config_path = 'config.json'
        self.config_path = Path(config_path)
        self.default_config = {
            'watch_duration': '30',
            'max_actions_per_account': 3,
            'human_behavior': True,
            'enable_likes': True,
            'enable_subscriptions': False,
            'enable_referral': True,
            'urls_strategy': 'random',
            'create_channel': False,
            'enable_title_search': False,
            'filter_strategy': 'none'
        }
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with defaults
                    merged_config = {**self.default_config, **config}
                    return merged_config
            except Exception as e:
                print(f"Error loading config: {e}")
                return self.default_config.copy()
        return self.default_config.copy()
    
    def save(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file."""
        try:
            # Ensure config directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Merge with defaults to ensure all keys exist
            merged_config = {**self.default_config, **config}
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(merged_config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        config = self.load()
        return config.get(key, default)
    
    def update(self, updates: Dict[str, Any]) -> bool:
        """Update configuration with new values."""
        config = self.load()
        config.update(updates)
        return self.save(config)

