#!/usr/bin/env python3
# Minimal Socket.IO test server

import eventlet
eventlet.monkey_patch()

from flask import Flask, send_file
from flask_socketio import SocketIO
import time
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('socket-test')

# Initialize Flask and SocketIO
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Serve the test page
@app.route('/')
def index():
    return send_file('static/simple_test.html')

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    socketio.emit('message', {'data': 'Welcome to the Socket.IO test server!'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

# Background task for emitting test events
def background_emitter():
    """Emit test events every few seconds"""
    count = 0
    while True:
        count += 1
        logger.info(f"Emitting test event #{count}")
        socketio.emit('test_event', {'count': count, 'timestamp': time.time()})
        
        # Every third event, simulate a detection
        if count % 3 == 0:
            logger.info("Emitting simulated detection_start event")
            socketio.emit('detection_start', {
                'message': 'Person detected',
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Every fourth event, simulate direction
        if count % 4 == 0:
            logger.info("Emitting simulated direction event")
            socketio.emit('direction', {
                'direction': 'left_to_right',
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        eventlet.sleep(5)  # Wait 5 seconds between emissions

if __name__ == '__main__':
    # Ensure the static directory exists
    os.makedirs('static', exist_ok=True)
    
    # Start the background task
    eventlet.spawn(background_emitter)
    
    # Start the server
    logger.info("Starting Socket.IO test server on http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 