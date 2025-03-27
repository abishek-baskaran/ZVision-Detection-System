#!/usr/bin/env python3
# Resource Provider - Manages configuration and logging

import os
import yaml
import logging
from logging.handlers import RotatingFileHandler

class ResourceProvider:
    """
    Provides centralized access to configuration and logging resources
    """
    
    def __init__(self, config_path):
        """
        Initialize the resource provider
        
        Args:
            config_path (str): Path to the configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self._setup_logging()
        self.logger = self.get_logger("ResourceProvider")
        
    def _load_config(self):
        """
        Load configuration from YAML file
        
        Returns:
            dict: Configuration dictionary
        """
        try:
            with open(self.config_path, 'r') as config_file:
                config = yaml.safe_load(config_file)
                return config
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Return a default configuration if the file cannot be loaded
            return {
                "camera": {"device_id": 0, "width": 640, "height": 480, "fps": 30},
                "detection": {"confidence_threshold": 0.5, "idle_fps": 1, "active_fps": 5},
                "api": {"host": "0.0.0.0", "port": 5000, "debug": False},
                "database": {"path": "database/zvision.db"},
                "logging": {"level": "INFO", "file": "logs/app.log", "max_size_mb": 10, "backup_count": 3}
            }
    
    def _setup_logging(self):
        """
        Set up the logging system for the application
        """
        # Get logging level from config
        log_level_str = self.config.get('logging', {}).get('level', 'INFO')
        log_level = getattr(logging, log_level_str)
        
        # Set up root logger
        root_logger = logging.getLogger()
        
        # Clear existing handlers on root logger
        if root_logger.handlers:
            root_logger.handlers.clear()
        
        # Set level on root logger
        root_logger.setLevel(log_level)
        
        # Create formatters
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Create file handler if a log file is specified
        log_file = self.config.get('logging', {}).get('file')
        if log_file:
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            # Get max size and backup count
            max_size_mb = self.config.get('logging', {}).get('max_size_mb', 10)
            backup_count = self.config.get('logging', {}).get('backup_count', 3)
            
            # Create rotating file handler
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
    
    def get_config(self):
        """
        Get the configuration dictionary
        
        Returns:
            dict: Configuration dictionary
        """
        return self.config
    
    def get_logger(self, name="zvision"):
        """
        Get a logger for a given module name
        
        Args:
            name (str): The name of the module for which to get a logger
            
        Returns:
            Logger: Configured logger instance with the given name
        """
        return logging.getLogger(name) 