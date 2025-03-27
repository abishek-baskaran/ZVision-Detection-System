#!/usr/bin/env python3
# API Manager - Handles REST API endpoints

import os
import json
import cv2
import base64
import threading
import time
from datetime import datetime
import eventlet
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_cors import CORS
from flask_socketio import SocketIO

class APIManager:
    """
    Manages the REST API for the system
    """
    
    def __init__(self, resource_provider, camera_manager, detection_manager, dashboard_manager, db_manager):
        """
        Initialize the API manager
        
        Args:
            resource_provider: The resource provider for config and logging
            camera_manager: The camera manager for accessing frames
            detection_manager: The detection manager for accessing detection state
            dashboard_manager: The dashboard manager for accessing metrics
            db_manager: The database manager for accessing stored data
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        self.camera_manager = camera_manager
        self.detection_manager = detection_manager
        self.dashboard_manager = dashboard_manager
        self.db_manager = db_manager
        
        # Extract API settings from config
        api_config = self.config.get('api', {})
        self.host = api_config.get('host', '0.0.0.0')
        self.port = api_config.get('port', 5000)
        self.debug = api_config.get('debug', False)
        
        # Initialize Flask app
        self.app = Flask(__name__, static_folder="../static", static_url_path="/static")
        CORS(self.app)  # Enable Cross-Origin Resource Sharing
        
        # Initialize SocketIO - simplify configuration to avoid issues
        self.socketio = SocketIO(
            self.app, 
            cors_allowed_origins="*",
            async_mode='threading'  # Use threading mode instead of eventlet
        )
        self.logger.info(f"Using SocketIO with threading mode")
        
        # Register API routes
        self._register_routes()
        
        # Link detection manager to this API manager for socket events
        if detection_manager:
            detection_manager.api_manager = self
        
        self.logger.info(f"APIManager initialized on {self.host}:{self.port}")
        self.logger.info("Real-time WebSocket notifications enabled")
    
    def _register_routes(self):
        """
        Register API routes with Flask
        """
        # Index route - serve test page
        @self.app.route('/', methods=['GET'])
        @self.app.route('/test', methods=['GET'])
        def index():
            try:
                # Return a simple test page from static folder
                return send_from_directory('../static', 'test_page.html')
            except Exception as e:
                self.logger.error(f"Error serving test page: {e}")
                return self._generate_default_html()
        
        # MJPEG Video feed endpoint - provides continuous streaming
        @self.app.route('/video_feed')
        def video_feed():
            try:
                # Generator function to yield frames in MJPEG format
                def gen_frames():
                    while True:
                        frame = self.camera_manager.get_latest_frame()
                        if frame is None:
                            time.sleep(0.1)  # No frame available, wait a bit
                            continue
                        
                        # Encode frame as JPEG
                        success, buffer = cv2.imencode('.jpg', frame)
                        if not success:
                            continue
                            
                        # Convert to bytes and yield as an MJPEG frame
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                        
                        # Sleep to control the frame rate (20 FPS max)
                        time.sleep(0.05)
                
                # Return a streaming response with the correct MIME type
                self.logger.info("Starting MJPEG video stream")
                return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
            
            except Exception as e:
                self.logger.error(f"Error in video feed: {e}")
                return "Video feed error", 500
        
        # Status endpoint - Get current system status
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            try:
                # Collect individual parts with separate try/except blocks
                system_status = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "running"
                }
                
                # Get detection status with error handling
                try:
                    detection_status = self.detection_manager.get_detection_status()
                except Exception as e:
                    self.logger.error(f"Error getting detection status: {e}")
                    detection_status = {
                        "person_detected": False,
                        "last_detection_time": None,
                        "direction": "unknown"
                    }
                
                # Get detection active state with error handling
                try:
                    detection_active = self.detection_manager.is_running
                except Exception as e:
                    self.logger.error(f"Error getting detection active state: {e}")
                    detection_active = False
                
                # Get dashboard summary with error handling
                try:
                    dashboard_summary = self.dashboard_manager.get_summary()
                except Exception as e:
                    self.logger.error(f"Error getting dashboard summary: {e}")
                    dashboard_summary = {}
                
                # Combine all parts
                status = {
                    "system": system_status,
                    "detection": detection_status,
                    "detection_active": detection_active,
                    "dashboard": dashboard_summary
                }
                
                return jsonify(status)
            except Exception as e:
                self.logger.error(f"Critical error in status endpoint: {e}")
                # Return minimal status info
                return jsonify({
                    "system": {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "error"
                    },
                    "detection": {
                        "person_detected": False,
                        "direction": "unknown"
                    },
                    "detection_active": False,
                    "error": str(e)
                }), 500
        
        # Events endpoint - Get recent events from database
        @self.app.route('/api/events', methods=['GET'])
        def get_events():
            try:
                limit = request.args.get('limit', 50, type=int)
                events = self.db_manager.get_events(limit=limit)
                return jsonify(events)
            except Exception as e:
                self.logger.error(f"Error in events endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Detection events endpoint - Get recent detection events
        @self.app.route('/api/detections/recent', methods=['GET'])
        def get_recent_detections():
            try:
                # Get count parameter, default to 10
                count = request.args.get('count', 10, type=int)
                
                # Get recent detections from database
                recent = self.db_manager.get_recent_detection_events(limit=count)
                
                return jsonify(recent)
            except Exception as e:
                self.logger.error(f"Error in recent detections endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Metrics endpoint - Get system metrics
        @self.app.route('/api/metrics', methods=['GET'])
        def get_metrics():
            try:
                # Get metrics from dashboard manager
                total_metrics = self.dashboard_manager.get_total_metrics()
                
                # Get hourly metrics (default 24 hours)
                hours = request.args.get('hours', 24, type=int)
                hourly_metrics = self.dashboard_manager.get_hourly_metrics(hours=hours)
                
                # Get footfall count explicitly
                footfall_count = self.dashboard_manager.get_footfall_count()
                
                metrics = {
                    "total": total_metrics,
                    "hourly": hourly_metrics,
                    "footfall_count": footfall_count
                }
                
                return jsonify(metrics)
            except Exception as e:
                self.logger.error(f"Error in metrics endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Daily metrics endpoint - Get metrics aggregated by day
        @self.app.route('/api/metrics/daily', methods=['GET'])
        def get_daily_metrics():
            try:
                # Get days parameter, default to 7
                days = request.args.get('days', 7, type=int)
                
                # Get daily metrics from dashboard manager
                daily_metrics = self.dashboard_manager.get_detection_metrics_by_day(days=days)
                
                return jsonify(daily_metrics)
            except Exception as e:
                self.logger.error(f"Error in daily metrics endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Metrics summary endpoint - Get cumulative metrics over time
        @self.app.route('/api/metrics/summary', methods=['GET'])
        def get_metrics_summary():
            try:
                # Get days parameter, default to 7
                days = request.args.get('days', 7, type=int)
                
                # Get direction counts from database for long-term analytics
                direction_counts = self.db_manager.get_detection_count_by_direction(days=days)
                
                # Calculate total detections
                total_detections = sum(direction_counts.values())
                
                summary = {
                    "period_days": days,
                    "total_detections": total_detections,
                    "direction_counts": direction_counts
                }
                
                return jsonify(summary)
            except Exception as e:
                self.logger.error(f"Error in metrics summary endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Current frame endpoint (latest snapshot)
        @self.app.route('/api/frame/current', methods=['GET'])
        def get_current_frame():
            try:
                # Get latest frame
                frame = self.camera_manager.get_latest_frame()
                
                if frame is None:
                    return jsonify({"error": "No frame available"}), 404
                
                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', frame)
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                # Return as JSON with data URI
                return jsonify({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "image_data": f"data:image/jpeg;base64,{jpg_as_text}"
                })
            except Exception as e:
                self.logger.error(f"Error in current frame endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Settings endpoint - GET
        @self.app.route('/api/settings', methods=['GET'])
        def get_settings():
            try:
                # Get all settings from config (for now, in future may use DB)
                settings = self.config
                
                # Don't expose sensitive settings
                if 'api' in settings and 'debug' in settings['api']:
                    del settings['api']['debug']
                
                return jsonify(settings)
            except Exception as e:
                self.logger.error(f"Error in get settings endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Detection control endpoints
        @self.app.route('/api/detection/stop', methods=['POST'])
        def stop_detection():
            try:
                self.detection_manager.stop()
                self.logger.info("Detection stopped via API")
                return jsonify({"message": "Detection stopped", "active": False})
            except Exception as e:
                self.logger.error(f"Error stopping detection: {e}")
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/detection/start', methods=['POST'])
        def start_detection():
            try:
                self.detection_manager.start()
                self.logger.info("Detection started via API")
                return jsonify({"message": "Detection started", "active": True})
            except Exception as e:
                self.logger.error(f"Error starting detection: {e}")
                return jsonify({"error": str(e)}), 500
    
    def _generate_default_html(self):
        """
        Generate a default HTML page if test_page.html is not available
        
        Returns:
            str: Basic HTML for test page
        """
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>ZVision Detection System</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
                h1 { color: #333; }
                .container { max-width: 800px; margin: 0 auto; }
                .status { margin: 20px 0; padding: 10px; border: 1px solid #ddd; }
                #camera-feed { width: 100%; max-width: 640px; border: 1px solid #ddd; }
                button { padding: 10px; margin: 10px 0; background: #4CAF50; color: white; border: none; cursor: pointer; }
                button:hover { background: #45a049; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>ZVision Detection System</h1>
                <div class="status" id="status-container">
                    Loading status...
                </div>
                <h2>Camera Feed</h2>
                <img id="camera-feed" src="" alt="Camera feed loading...">
                <div>
                    <button id="refresh-btn">Refresh</button>
                </div>
                <script>
                    // Simple script to update status and frame
                    function updateStatus() {
                        fetch('/api/status')
                            .then(response => response.json())
                            .then(data => {
                                let statusHTML = '<h3>System Status</h3>';
                                statusHTML += `<p>Time: ${data.system.timestamp}</p>`;
                                statusHTML += `<p>System: ${data.system.status}</p>`;
                                statusHTML += '<h3>Detection Status</h3>';
                                statusHTML += `<p>Person Detected: ${data.detection.person_detected}</p>`;
                                statusHTML += `<p>Direction: ${data.detection.direction}</p>`;
                                if (data.detection.last_detection_time) {
                                    statusHTML += `<p>Last Detection: ${data.detection.last_detection_time}</p>`;
                                }
                                document.getElementById('status-container').innerHTML = statusHTML;
                            })
                            .catch(err => {
                                console.error('Error fetching status:', err);
                            });
                    }
                    
                    function updateFrame() {
                        fetch('/api/frame/current')
                            .then(response => response.json())
                            .then(data => {
                                document.getElementById('camera-feed').src = data.image_data;
                            })
                            .catch(err => {
                                console.error('Error fetching frame:', err);
                            });
                    }
                    
                    // Update on page load
                    updateStatus();
                    updateFrame();
                    
                    // Set up refresh button
                    document.getElementById('refresh-btn').addEventListener('click', function() {
                        updateStatus();
                        updateFrame();
                    });
                    
                    // Auto-refresh every 5 seconds
                    setInterval(function() {
                        updateStatus();
                        updateFrame();
                    }, 5000);
                </script>
            </div>
        </body>
        </html>
        """
    
    def emit_event(self, event_type, data=None):
        """
        Emit a socket.io event to all connected clients
        
        Args:
            event_type: Type of the event (e.g., 'detection_start', 'detection_end', 'direction')
            data: Data to send with the event
        """
        try:
            if data is None:
                data = {}
            
            # Add timestamp to all events
            if 'timestamp' not in data:
                data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            self.logger.debug(f"Emitting socket event: {event_type} with data: {data}")
            self.socketio.emit(event_type, data)
        except Exception as e:
            self.logger.error(f"Error emitting socket event: {e}")
        
    def start(self):
        """
        Start the API server
        """
        # Ensure static directory exists
        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
        os.makedirs(static_dir, exist_ok=True)
        
        # Write test page if it doesn't exist
        test_page_path = os.path.join(static_dir, 'test_page.html')
        if not os.path.exists(test_page_path):
            self.logger.info(f"Creating default test page at {test_page_path}")
            with open(test_page_path, 'w') as f:
                f.write(self._generate_default_html())
        
        # Start the Flask app with SocketIO
        self.logger.info(f"Starting API server at http://{self.host}:{self.port}")
        self.logger.info("Using threading mode for Flask-SocketIO")
        
        try:
            # Use standard SocketIO run method with threading mode
            self.socketio.run(
                self.app, 
                host=self.host, 
                port=self.port, 
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            self.logger.error(f"Error starting API server: {e}")
            raise
    
    def stop(self):
        """
        Stop the API server (not typically used with Flask's dev server)
        """
        # Flask's development server doesn't support clean shutdown
        # In production, we would use a proper WSGI server like Gunicorn
        self.logger.info("API server stop requested (but dev server doesn't support clean shutdown)")
        
        # For future implementation with a proper server
        pass 