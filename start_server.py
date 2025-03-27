#!/usr/bin/env python3
# Start Server Script for ZVision Detection System

import os
import sys
import logging
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('zvision')

# Log startup
logger.info("Starting ZVision detection system...")

try:
    # Import the main application module
    logger.info("Importing main module...")
    from main import ZVision
    
    # Create and start the detection system
    logger.info("Initializing ZVision detection system...")
    app = ZVision()
    app.start()
    
except Exception as e:
    logger.error(f"Error starting ZVision detection system: {e}")
    logger.error(traceback.format_exc())
    sys.exit(1) 