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

# Import our new analytics engine
from . import analytics_engine

class APIManager:
    """
    Manages the REST API for the system
    """
    
    def __init__(self, resource_provider, camera_manager, detection_manager, dashboard_manager, db_manager, camera_registry=None):
        """
        Initialize the API manager
        
        Args:
            resource_provider: The resource provider for config and logging
            camera_manager: The camera manager for accessing frames
            detection_manager: The detection manager for accessing detection state
            dashboard_manager: The dashboard manager for accessing metrics
            db_manager: The database manager for accessing stored data
            camera_registry: The camera registry for managing multiple cameras
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        self.camera_manager = camera_manager
        self.detection_manager = detection_manager
        self.dashboard_manager = dashboard_manager
        self.db_manager = db_manager
        self.camera_registry = camera_registry
        
        # Extract API settings from config
        api_config = self.config.get('api', {})
        self.host = api_config.get('host', '0.0.0.0')
        self.port = api_config.get('port', 5000)
        self.debug = api_config.get('debug', False)
        
        # Configure Flask logging to use standard output
        import logging
        logging.getLogger('werkzeug').setLevel(logging.INFO)
        
        # Initialize Flask app
        self.app = Flask(__name__, static_folder="../static", static_url_path="/static")
        CORS(self.app)  # Enable Cross-Origin Resource Sharing
        
        # Initialize SocketIO with minimal configuration to ensure proper behavior
        self.socketio = SocketIO(
            self.app, 
            cors_allowed_origins="*",
            async_mode='threading',  # Use threading mode instead of eventlet
            logger=True,             # Enable SocketIO's logger
            engineio_logger=True     # Enable Engine.IO's logger
        )
        self.logger.info(f"Using SocketIO with threading mode")
        
        # Initialize analytics engine
        analytics_engine.init(self.config)
        
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

        # Camera-specific video feed endpoint
        @self.app.route('/video_feed/<camera_id>')
        def camera_video_feed(camera_id):
            if not self.camera_registry:
                self.logger.error("Camera registry not available")
                return "Camera registry not available", 500
                
            try:
                cam = self.camera_registry.get_camera(camera_id)
                if cam is None:
                    self.logger.error(f"Camera not found: {camera_id}")
                    return "Camera not found", 404
                
                # Generator function to yield frames from the specific camera
                def gen_frames():
                    while True:
                        frame = cam.get_latest_frame()
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
                
                self.logger.info(f"Starting MJPEG video stream for camera {camera_id}")
                return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
            
            except Exception as e:
                self.logger.error(f"Error in video feed for camera {camera_id}: {e}")
                return f"Video feed error: {str(e)}", 500
        
        # Camera Management Endpoints
        
        # List all cameras
        @self.app.route('/api/cameras', methods=['GET'])
        def list_cameras():
            if not self.camera_registry:
                self.logger.error("Camera registry not available")
                return jsonify({"error": "Camera registry not available"}), 500
            
            try:
                all_cameras = self.camera_registry.get_all_cameras()
                camera_list = []
                
                for camera_id, camera in all_cameras.items():
                    # Check if person is detected on this camera
                    person_detected = False
                    if self.detection_manager and camera_id in self.detection_manager.states:
                        person_detected = self.detection_manager.states[camera_id].get("person_detected", False)
                    
                    camera_info = {
                        "id": camera_id,
                        "name": getattr(camera, "name", f"Camera {camera_id}"),
                        "source": getattr(camera, "device_id", None),
                        "status": "active" if camera.is_running else "inactive",
                        "person_detected": person_detected
                    }
                    camera_list.append(camera_info)
                
                return jsonify(camera_list)
            
            except Exception as e:
                self.logger.error(f"Error listing cameras: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Add a new camera
        @self.app.route('/api/cameras', methods=['POST'])
        def add_camera():
            if not self.camera_registry:
                self.logger.error("Camera registry not available")
                return jsonify({"error": "Camera registry not available"}), 500
            
            try:
                data = request.get_json()
                
                # Validate required fields
                if not data or 'id' not in data or 'source' not in data:
                    return jsonify({"error": "Missing required fields: id and source"}), 400
                
                # Extract parameters
                cam_id = data["id"]
                source = data["source"]
                name = data.get("name", f"Camera {cam_id}")
                width = data.get("width")
                height = data.get("height")
                fps = data.get("fps")
                
                # Add camera to registry
                success = self.camera_registry.add_camera(cam_id, source, name=name, enabled=True)
                
                if not success:
                    return jsonify({"error": "Failed to add camera"}), 500
                
                # Store camera configuration in database if a method exists
                if hasattr(self.db_manager, 'add_camera'):
                    self.db_manager.add_camera(cam_id, source, name, width, height, fps)
                
                return jsonify({"status": "Camera added", "id": cam_id}), 201
            
            except Exception as e:
                self.logger.error(f"Error adding camera: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Get camera details
        @self.app.route('/api/cameras/<camera_id>', methods=['GET'])
        def get_camera_details(camera_id):
            if not self.camera_registry:
                self.logger.error("Camera registry not available")
                return jsonify({"error": "Camera registry not available"}), 500
            
            try:
                camera = self.camera_registry.get_camera(camera_id)
                if camera is None:
                    return jsonify({"error": f"Camera {camera_id} not found"}), 404
                
                # Get ROI settings if available
                roi_settings = None
                entry_direction = None
                if self.detection_manager and camera_id in self.detection_manager.roi_settings:
                    roi = self.detection_manager.roi_settings[camera_id]
                    if "coords" in roi:
                        roi_settings = {
                            "x1": roi["coords"][0],
                            "y1": roi["coords"][1],
                            "x2": roi["coords"][2],
                            "y2": roi["coords"][3]
                        }
                    if "entry_direction" in roi:
                        entry_direction = roi["entry_direction"]
                
                # Check if person is detected on this camera
                person_detected = False
                if self.detection_manager and camera_id in self.detection_manager.states:
                    person_detected = self.detection_manager.states[camera_id].get("person_detected", False)
                
                camera_info = {
                    "id": camera_id,
                    "name": getattr(camera, "name", f"Camera {camera_id}"),
                    "source": getattr(camera, "device_id", None),
                    "status": "active" if camera.is_running else "inactive",
                    "person_detected": person_detected,
                    "roi": roi_settings,
                    "entry_direction": entry_direction,
                    "resolution": {
                        "width": getattr(camera, "width", 640),
                        "height": getattr(camera, "height", 480)
                    },
                    "fps": getattr(camera, "fps", 30)
                }
                
                return jsonify(camera_info)
            
            except Exception as e:
                self.logger.error(f"Error getting camera details: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Update camera
        @self.app.route('/api/cameras/<camera_id>', methods=['PUT'])
        def update_camera(camera_id):
            if not self.camera_registry:
                self.logger.error("Camera registry not available")
                return jsonify({"error": "Camera registry not available"}), 500
            
            try:
                camera = self.camera_registry.get_camera(camera_id)
                if camera is None:
                    return jsonify({"error": f"Camera {camera_id} not found"}), 404
                
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No update data provided"}), 400
                
                # Update camera name if provided
                if 'name' in data:
                    # Currently there's no direct way to update just the name,
                    # so we need to recreate the camera with the new name
                    source = getattr(camera, "device_id", None)
                    if source is not None:
                        enabled = camera.is_running
                        # Stop the old camera first
                        if enabled:
                            camera.stop()
                        # Add with the same ID but new name
                        success = self.camera_registry.add_camera(camera_id, source, name=data['name'], enabled=enabled)
                        if not success:
                            return jsonify({"error": "Failed to update camera name"}), 500
                
                # Enable/disable detection if specified
                if 'detection_enabled' in data:
                    enabled = data['detection_enabled']
                    if not self.detection_manager:
                        return jsonify({"error": "Detection manager not available"}), 500
                    
                    if enabled:
                        self.detection_manager.start_camera(camera_id)
                    else:
                        self.detection_manager.stop_camera(camera_id)
                
                return jsonify({"status": "Camera updated", "id": camera_id})
            
            except Exception as e:
                self.logger.error(f"Error updating camera: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Remove camera
        @self.app.route('/api/cameras/<camera_id>', methods=['DELETE'])
        def remove_camera(camera_id):
            if not self.camera_registry:
                self.logger.error("Camera registry not available")
                return jsonify({"error": "Camera registry not available"}), 500
            
            try:
                # Check if camera exists
                camera = self.camera_registry.get_camera(camera_id)
                if camera is None:
                    return jsonify({"error": f"Camera {camera_id} not found"}), 404
                
                # Stop detection for this camera if it's running
                if self.detection_manager:
                    self.detection_manager.stop_camera(camera_id)
                
                # Remove camera from registry
                success = self.camera_registry.remove_camera(camera_id)
                if not success:
                    return jsonify({"error": "Failed to remove camera"}), 500
                
                # Remove camera configuration from database if method exists
                if hasattr(self.db_manager, 'remove_camera'):
                    self.db_manager.remove_camera(camera_id)
                
                # Remove ROI settings for this camera from database
                if hasattr(self.db_manager, 'clear_roi'):
                    self.db_manager.clear_roi(camera_id)
                
                return jsonify({"status": "Camera removed", "id": camera_id})
            
            except Exception as e:
                self.logger.error(f"Error removing camera: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Camera status endpoint
        @self.app.route('/api/cameras/<camera_id>/status', methods=['GET'])
        def get_camera_status(camera_id):
            if not self.camera_registry:
                self.logger.error("Camera registry not available")
                return jsonify({"error": "Camera registry not available"}), 500
            
            try:
                camera = self.camera_registry.get_camera(camera_id)
                if camera is None:
                    return jsonify({"error": f"Camera {camera_id} not found"}), 404
                
                # Get detection state for this camera
                detection_active = False
                person_detected = False
                last_detection_time = None
                direction = "unknown"
                
                if self.detection_manager:
                    # Check if detection is running for this camera
                    detection_active = camera_id in self.detection_manager.detection_threads and \
                                       self.detection_manager.detection_threads[camera_id].is_alive()
                    
                    # Get detection state if available
                    if camera_id in self.detection_manager.states:
                        state = self.detection_manager.states[camera_id]
                        person_detected = state.get("person_detected", False)
                        last_detection_time = state.get("last_detection_time")
                        
                        # Convert direction code to string
                        dir_code = state.get("current_direction", self.detection_manager.DIRECTION_UNKNOWN)
                        if dir_code == self.detection_manager.DIRECTION_LEFT_TO_RIGHT:
                            direction = "left_to_right"
                        elif dir_code == self.detection_manager.DIRECTION_RIGHT_TO_LEFT:
                            direction = "right_to_left"
                
                status = {
                    "id": camera_id,
                    "streaming": camera.is_running,
                    "detection_active": detection_active,
                    "person_detected": person_detected,
                    "last_detection_time": last_detection_time,
                    "direction": direction,
                    "frame_rate": getattr(camera, "current_fps", 0)
                }
                
                return jsonify(status)
            
            except Exception as e:
                self.logger.error(f"Error getting camera status: {e}")
                return jsonify({"error": str(e)}), 500
        
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
                
                # Get ROI configuration if available
                roi_config = {}
                try:
                    # Since get_roi and get_entry_direction now require camera_id,
                    # we'll just omit the ROI from the status endpoint
                    # Clients should use /api/cameras/{camera_id} to get ROI details for each camera
                    pass
                except Exception as e:
                    self.logger.error(f"Error getting ROI configuration: {e}")
                
                # Combine all parts
                status = {
                    "system": system_status,
                    "detection": detection_status,
                    "detection_active": detection_active,
                    "dashboard": dashboard_summary
                    # ROI config is removed from status response - use camera-specific endpoints instead
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
        
        # ROI Configuration Endpoints
        @self.app.route('/api/cameras/<camera_id>/roi', methods=['POST'])
        def set_roi(camera_id):
            try:
                data = request.get_json()
                roi = (data['x1'], data['y1'], data['x2'], data['y2'])
                entry_dir = data['entry_direction']
                
                # Set ROI in detection manager
                self.detection_manager.set_roi(str(camera_id), roi)
                self.detection_manager.set_entry_direction(str(camera_id), entry_dir)
                
                self.logger.info(f"ROI set to {roi} and entry direction to {entry_dir} for camera {camera_id} via API")
                return jsonify({"success": True, "message": "ROI configuration saved"})
            except Exception as e:
                self.logger.error(f"Failed to save ROI: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/api/cameras/<camera_id>/roi/clear', methods=['POST'])
        def clear_roi(camera_id):
            try:
                # Clear ROI in detection manager
                self.detection_manager.clear_roi(str(camera_id))
                
                self.logger.info(f"ROI configuration cleared for camera {camera_id} via API")
                return jsonify({"success": True, "message": "ROI configuration cleared"})
            except Exception as e:
                self.logger.error(f"Failed to clear ROI: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        # Analytics endpoints for multi-camera support
        
        # Compare metrics across cameras
        @self.app.route('/api/analytics/compare', methods=['GET'])
        def compare_cameras():
            if not self.dashboard_manager:
                self.logger.error("Dashboard manager not available")
                return jsonify({"error": "Dashboard manager not available"}), 500
                
            try:
                # Get time period from query params
                hours = request.args.get('hours', 24, type=int)
                days = request.args.get('days', None, type=int)
                
                # Convert days to hours if specified
                if days is not None:
                    hours = days * 24
                
                # Use the analytics engine to get entry counts
                metrics = analytics_engine.get_camera_entry_counts(
                    last_hours=hours,
                    camera_registry=self.camera_registry
                )
                
                # Calculate aggregated total
                total_count = sum(metrics.values())
                
                return jsonify({
                    "time_period": f"Last {hours} hours",
                    "camera_counts": metrics,
                    "total": total_count
                })
                
            except Exception as e:
                self.logger.error(f"Error in compare cameras endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Time series data for one or more cameras
        @self.app.route('/api/analytics/time-series', methods=['GET'])
        def time_series_analytics():
            if not self.dashboard_manager:
                self.logger.error("Dashboard manager not available")
                return jsonify({"error": "Dashboard manager not available"}), 500
                
            try:
                # Get parameters from request
                camera_id = request.args.get('camera', None)  # Optional specific camera
                hours = request.args.get('hours', 24, type=int)
                
                # Use the analytics engine to get time series data
                time_series_data = analytics_engine.get_time_series(
                    camera_id=camera_id,
                    hours=hours,
                    camera_registry=self.camera_registry
                )
                
                return jsonify({
                    "time_period": f"Last {hours} hours",
                    "data": time_series_data
                })
                
            except Exception as e:
                self.logger.error(f"Error in time series endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Heatmap data stub (not implemented yet)
        @self.app.route('/api/analytics/heatmap', methods=['GET'])
        def heatmap_analytics():
            try:
                camera_id = request.args.get('camera', 'main')
                width = request.args.get('width', 10, type=int)
                height = request.args.get('height', 10, type=int)
                
                # Get heatmap data from analytics engine
                heatmap_data = analytics_engine.get_heatmap(
                    camera_id=camera_id,
                    width=width,
                    height=height
                )
                
                return jsonify({
                    "camera_id": camera_id,
                    "width": width,
                    "height": height,
                    "heatmap": heatmap_data
                })
            except Exception as e:
                self.logger.error(f"Error in heatmap endpoint: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Get camera snapshot history
        @self.app.route('/api/snapshots/<camera_id>', methods=['GET'])
        def get_camera_snapshots(camera_id):
            try:
                limit = request.args.get('limit', default=10, type=int)
                
                # Check if camera exists
                if self.camera_registry and not self.camera_registry.get_camera(camera_id):
                    return jsonify({"error": f"Camera {camera_id} not found"}), 404
                
                # Get recent detection events with snapshots for this camera
                conn = self.db_manager._get_connection()
                cursor = conn.cursor()
                
                query = """
                    SELECT id, timestamp, event_type, direction, snapshot_path
                    FROM detection_events
                    WHERE camera_id = ? AND snapshot_path IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                
                cursor.execute(query, (camera_id, limit))
                rows = cursor.fetchall()
                conn.close()
                
                snapshots = []
                for row in rows:
                    snapshot_info = {
                        "id": row[0],
                        "timestamp": row[1],
                        "event_type": row[2],
                        "direction": row[3],
                        "snapshot_path": row[4]
                    }
                    
                    # Check if the file exists
                    if row[4] and os.path.exists(row[4]):
                        snapshot_info["exists"] = True
                    else:
                        snapshot_info["exists"] = False
                        
                    snapshots.append(snapshot_info)
                
                return jsonify({
                    "camera_id": camera_id,
                    "count": len(snapshots),
                    "snapshots": snapshots
                })
                
            except Exception as e:
                self.logger.error(f"Error retrieving snapshots for camera {camera_id}: {e}")
                return jsonify({"error": str(e)}), 500
        
        # Serve specific snapshot by path
        @self.app.route('/api/snapshot/image/<path:snapshot_path>', methods=['GET'])
        def get_snapshot_image(snapshot_path):
            try:
                # Ensure the path is within the snapshots directory for security
                snapshot_dir = os.path.abspath("snapshots")
                requested_path = os.path.abspath(os.path.join("snapshots", snapshot_path))
                
                # Check if the requested path is within the snapshots directory
                if not requested_path.startswith(snapshot_dir):
                    return jsonify({"error": "Invalid snapshot path"}), 403
                
                # Check if the file exists
                if not os.path.exists(requested_path):
                    return jsonify({"error": "Snapshot not found"}), 404
                
                # Serve the file
                return send_from_directory(os.path.dirname(requested_path), 
                                         os.path.basename(requested_path),
                                         mimetype='image/jpeg')
                
            except Exception as e:
                self.logger.error(f"Error serving snapshot {snapshot_path}: {e}")
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
            # Use Flask's native run method to ensure all development server messages are shown
            self.socketio.run(
                self.app, 
                host=self.host, 
                port=self.port, 
                debug=False,
                use_reloader=False,
                log_output=True,
                allow_unsafe_werkzeug=True  # Allow Werkzeug development server messages
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