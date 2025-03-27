#!/usr/bin/env python3
# Camera Manager - Handles video capture

import cv2
import time
import threading
import queue
import re

class CameraManager:
    """
    Manages camera capture in a separate thread
    """
    
    def __init__(self, resource_provider):
        """
        Initialize the camera manager
        
        Args:
            resource_provider: The resource provider for config and logging
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        
        # Extract camera settings from config
        camera_config = self.config.get('camera', {})
        self.device_id = camera_config.get('device_id', 0)
        self.width = camera_config.get('width', 640)
        self.height = camera_config.get('height', 480)
        self.fps = camera_config.get('fps', 30)
        
        # Check if device_id is an RTSP URL
        self.is_ip_camera = False
        if isinstance(self.device_id, str) and (
            self.device_id.startswith('rtsp://') or 
            self.device_id.startswith('http://') or 
            self.device_id.startswith('https://')
        ):
            self.is_ip_camera = True
            self.logger.info(f"IP camera detected with URL: {self.device_id}")
        
        # Frame queue with maximum size of 1 to always have the latest frame
        self.frame_queue = queue.Queue(maxsize=1)
        
        # Thread control
        self.is_running = False
        self.thread = None
        
        # Latest frame for direct access
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        # Connection retry settings for IP cameras
        self.max_retries = 5
        self.retry_delay = 3
        
        self.logger.info(f"CameraManager initialized with {'IP camera' if self.is_ip_camera else 'device ' + str(self.device_id)}, "
                        f"resolution {self.width}x{self.height}, FPS {self.fps}")
    
    def start(self):
        """
        Start the camera capture thread
        """
        if self.is_running:
            self.logger.warning("Camera capture thread already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info("Camera capture thread started")
    
    def stop(self):
        """
        Stop the camera capture thread
        """
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.logger.info("Camera capture thread stopped")
    
    def _capture_loop(self):
        """
        Main loop for capturing frames from the camera
        """
        # Initialize camera
        cap = None
        retry_count = 0
        
        while self.is_running and retry_count < self.max_retries:
            try:
                # Open camera
                if cap is None:
                    self.logger.info(f"Opening camera source: {self.device_id}")
                    cap = cv2.VideoCapture(self.device_id)
                    
                    # Set properties for non-IP cameras
                    if not self.is_ip_camera:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                        cap.set(cv2.CAP_PROP_FPS, self.fps)
                
                if not cap.isOpened():
                    self.logger.error(f"Failed to open camera {self.device_id}")
                    retry_count += 1
                    if retry_count < self.max_retries:
                        self.logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {retry_count}/{self.max_retries})")
                        time.sleep(self.retry_delay)
                    continue
                
                # Reset retry count on successful connection
                retry_count = 0
                self.logger.info(f"Camera opened successfully")
                
                # Start capturing frames
                while self.is_running:
                    try:
                        # Read frame from camera
                        ret, frame = cap.read()
                        
                        if not ret:
                            self.logger.warning("Failed to read frame from camera")
                            
                            # For IP cameras, try to reconnect
                            if self.is_ip_camera:
                                self.logger.info("Attempting to reconnect to IP camera...")
                                cap.release()
                                cap = None
                                break
                            
                            time.sleep(0.1)
                            continue
                        
                        # Resize frame if dimensions don't match expected size
                        if self.is_ip_camera and (frame.shape[1] != self.width or frame.shape[0] != self.height):
                            frame = cv2.resize(frame, (self.width, self.height))
                        
                        # Update latest frame with thread safety
                        with self.frame_lock:
                            self.latest_frame = frame.copy()
                        
                        # Put frame in queue, replacing any existing frame
                        try:
                            # Put without blocking, drop oldest frame if queue is full
                            self.frame_queue.put(frame, block=False)
                        except queue.Full:
                            # If queue is full, get the old frame to make space
                            _ = self.frame_queue.get()
                            # Then put the new frame
                            self.frame_queue.put(frame)
                            
                    except Exception as e:
                        self.logger.error(f"Error in camera capture loop: {e}")
                        time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Camera connection error: {e}")
                retry_count += 1
                if retry_count < self.max_retries:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {retry_count}/{self.max_retries})")
                    time.sleep(self.retry_delay)
                if cap is not None:
                    cap.release()
                    cap = None
        
        # Release camera resources
        if cap is not None:
            cap.release()
            
        self.logger.info("Camera resources released")
    
    def get_frame(self, block=False, timeout=None):
        """
        Get the latest frame from the queue
        
        Args:
            block (bool): Whether to block until a frame is available
            timeout (float): Timeout for blocking (None means no timeout)
            
        Returns:
            numpy.ndarray: The latest frame, or None if no frame is available
        """
        try:
            return self.frame_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def get_latest_frame(self):
        """
        Get the latest frame directly (thread-safe)
        
        Returns:
            numpy.ndarray: Copy of the latest frame, or None if no frame is available
        """
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None 