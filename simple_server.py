#!/usr/bin/env python3
# simple_server.py - A simplified server script without SocketIO

from flask import Flask, send_from_directory, jsonify
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('simple-server')

# Create Flask app
app = Flask(__name__, static_folder="static", static_url_path="/static")

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
        "message": "Simple API server is running"
    })

# Create static directory if it doesn't exist
os.makedirs('static', exist_ok=True)

if __name__ == '__main__':
    logger.info("Starting simple Flask server on port 5000")
    print("Server running at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True) 