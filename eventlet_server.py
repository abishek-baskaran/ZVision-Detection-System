#!/usr/bin/env python3
# eventlet_server.py - Minimal Flask-SocketIO server

# Monkey patch first - before any other imports
import eventlet
eventlet.monkey_patch()
print("Eventlet monkey patching applied")

# Standard imports
import os
import time
import logging
from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('eventlet-server')

# Create Flask app and SocketIO
app = Flask(__name__, static_folder="static", static_url_path="/static")
socketio = SocketIO(app, cors_allowed_origins="*")

# Define routes
@app.route('/')
def index():
    """Serve the test page"""
    return send_from_directory('static', 'simple_test.html')

@app.route('/api/test')
def test_api():
    """Simple test endpoint"""
    return jsonify({
        "status": "ok",
        "message": "Eventlet SocketIO server is running"
    })

# Define SocketIO events
@socketio.on('connect')
def on_connect():
    logger.info("Client connected")
    socketio.emit('message', {'data': 'Connected to server'})

@socketio.on('disconnect')
def on_disconnect():
    logger.info("Client disconnected")

# Background thread for periodic events
def background_thread():
    """Send server time to client every 10 seconds"""
    count = 0
    while True:
        count += 1
        socketio.emit('server_time', {
            'time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'count': count
        })
        eventlet.sleep(10)

# Create static directory if it doesn't exist
os.makedirs('static', exist_ok=True)

if __name__ == '__main__':
    # Start background thread
    eventlet.spawn(background_thread)
    
    # Start server
    logger.info("Starting Flask-SocketIO server on port 5000")
    print("Server running at: http://localhost:5000")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        print(f"Failed to start server: {e}") 