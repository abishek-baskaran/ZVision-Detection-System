#!/usr/bin/env python3
# Resource Provider - Manages configuration and logging

import os
import yaml
import logging
from logging.handlers import RotatingFileHandler
import copy
from datetime import datetime

class ResourceProvider:
    """
    Provides centralized access to configuration and logging resources
    """
    
    def __init__(self, config_path='config.yaml'):
        """
        Initialize the resource provider
        
        Args:
            config_path: Path to the configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Configure logging
        self.logger = self._configure_logging()
        
        self.logger.info("ResourceProvider initialized")
    
    def _load_config(self, config_path):
        """
        Load configuration from YAML file
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            dict: Configuration dictionary
        """
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                return config or {}
            else:
                print(f"Warning: Config file not found at {config_path}, using defaults")
                return {}
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def _configure_logging(self):
        """
        Configure logging based on configuration
        
        Returns:
            logging.Logger: Configured logger
        """
        log_config = self.config.get('logging', {})
        log_level_str = log_config.get('level', 'INFO')
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        
        # Create logger
        logger = logging.getLogger('zvision')
        logger.setLevel(log_level)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler
        log_file = log_config.get('file', 'logs/zvision.log')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Rotating file handler
        max_size_mb = log_config.get('max_size_mb', 10)
        backup_count = log_config.get('backup_count', 5)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def get_config(self):
        """
        Get the configuration dictionary
        
        Returns:
            dict: Configuration dictionary
        """
        return self.config
    
    def get_logger(self):
        """
        Get the logger
        
        Returns:
            logging.Logger: Logger
        """
        return self.logger
    
    def clone_with_custom_config(self, custom_config_updates):
        """
        Create a new ResourceProvider with a custom configuration
        
        Args:
            custom_config_updates: Dictionary of configuration updates to apply
            
        Returns:
            ResourceProvider: New resource provider with updated configuration
        """
        # Create a new instance
        new_provider = ResourceProvider.__new__(ResourceProvider)
        
        # Deep copy the config
        new_provider.config = copy.deepcopy(self.config)
        
        # Apply the custom updates by recursive update
        self._recursive_update(new_provider.config, custom_config_updates)
        
        # Share the same logger
        new_provider.logger = self.logger
        
        return new_provider
    
    def _recursive_update(self, base_dict, update_dict):
        """
        Recursively update a dictionary with another
        
        Args:
            base_dict: Base dictionary to update
            update_dict: Dictionary of updates to apply
        """
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._recursive_update(base_dict[key], value)
            else:
                base_dict[key] = value 