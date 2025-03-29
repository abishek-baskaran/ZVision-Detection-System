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
        self.is_video_file = False
        
        if isinstance(self.device_id, str):
            if (self.device_id.startswith('rtsp://') or 
                self.device_id.startswith('http://') or 
                self.device_id.startswith('https://')):
                self.is_ip_camera = True
                self.logger.info(f"IP camera detected with URL: {self.device_id}")
            elif (self.device_id.endswith('.mp4') or 
                  self.device_id.endswith('.avi') or 
                  self.device_id.endswith('.mov') or 
                  self.device_id.endswith('.mkv')):
                self.is_video_file = True
                self.logger.info(f"Video file detected: {self.device_id}")
        
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
        
        # Set max wait time to 2 seconds total (try 4 times with 0.5s)
        max_attempts = 4
        for attempt in range(max_attempts):
            if self.thread and self.thread.is_alive():
                try:
                    self.thread.join(timeout=0.5)
                    if not self.thread.is_alive():
                        break
                except Exception as e:
                    self.logger.error(f"Error joining camera thread: {e}")
            else:
                break
        
        # If thread is still alive after timeout, log a warning
        if self.thread and self.thread.is_alive():
            self.logger.warning("Camera thread did not terminate properly. This could lead to resource leaks.")
        else:
            self.logger.info("Camera capture thread stopped")
        
        # Reset thread reference to avoid join attempts on non-existent thread
        self.thread = None
    
    def _capture_loop(self):
        """
        Main loop for capturing frames from the camera
        """
        # Initialize camera
        cap = None
        retry_count = 0
        video_finished = False
        
        # Variables for video file FPS control
        video_fps = self.fps  # Default to config FPS
        frame_delay = 1.0 / video_fps  # Time between frames
        last_frame_time = time.time()
        
        try:
            while self.is_running and retry_count < self.max_retries and not video_finished:
                try:
                    # Check if running again before opening camera
                    if not self.is_running:
                        break
                        
                    # Open camera
                    if cap is None:
                        self.logger.info(f"Opening camera source: {self.device_id}")
                        cap = cv2.VideoCapture(self.device_id)
                        
                        # Set properties for non-IP cameras and non-video files
                        if not self.is_ip_camera and not self.is_video_file:
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                            cap.set(cv2.CAP_PROP_FPS, self.fps)
                        
                        # For video files, get the actual FPS from the file
                        if self.is_video_file:
                            video_fps = cap.get(cv2.CAP_PROP_FPS)
                            if video_fps <= 0:  # Invalid FPS
                                video_fps = self.fps  # Fall back to config
                            frame_delay = 1.0 / video_fps
                            self.logger.info(f"Video file FPS: {video_fps}, frame delay: {frame_delay:.4f}s")
                    
                    # Check camera opened successfully
                    if not cap.isOpened():
                        self.logger.error(f"Failed to open camera {self.device_id}")
                        retry_count += 1
                        if retry_count < self.max_retries and self.is_running:
                            self.logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {retry_count}/{self.max_retries})")
                            
                            # Break retry delay into small chunks to check is_running
                            for _ in range(int(self.retry_delay * 10)):
                                if not self.is_running:
                                    break
                                time.sleep(0.1)
                                
                        if cap is not None:
                            cap.release()
                            cap = None
                        continue
                    
                    # Reset retry count on successful connection
                    retry_count = 0
                    self.logger.info(f"Camera opened successfully")
                    
                    # For video files, special handling for looping or ending
                    if self.is_video_file:
                        # Get video file details
                        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        self.logger.info(f"Video file has {frame_count} frames, playing at {video_fps} FPS")
                    
                    # Current FPS tracking
                    frame_count = 0
                    fps_start_time = time.time()
                    self.current_fps = 0
                    
                    # Start capturing frames
                    consecutive_failures = 0
                    while self.is_running:
                        # Check if we should exit
                        if not self.is_running:
                            break
                        
                        # For video files, control playback speed to match video FPS
                        if self.is_video_file:
                            current_time = time.time()
                            elapsed = current_time - last_frame_time
                            
                            # If it's not time for the next frame yet, wait
                            if elapsed < frame_delay:
                                sleep_time = min(frame_delay - elapsed, 0.01)  # Max 10ms sleep for responsiveness
                                time.sleep(sleep_time)
                                continue
                            
                        try:
                            # Read frame from camera
                            ret, frame = cap.read()
                            
                            if not ret:
                                self.logger.warning("Failed to read frame from camera")
                                consecutive_failures += 1
                                
                                # For video files, it's normal to reach the end
                                if self.is_video_file:
                                    self.logger.info("End of video file reached, restarting from beginning")
                                    # Reopen video
                                    if cap is not None:
                                        cap.release()
                                    cap = cv2.VideoCapture(self.device_id)
                                    if not cap.isOpened():
                                        self.logger.error(f"Failed to reopen video file {self.device_id}")
                                        video_finished = True
                                        break
                                    consecutive_failures = 0
                                # For IP cameras, try to reconnect
                                elif self.is_ip_camera or consecutive_failures > 10:
                                    self.logger.info("Too many consecutive failures, reconnecting...")
                                    
                                    # Clean release of camera
                                    if cap is not None:
                                        cap.release()
                                        cap = None
                                    break
                                
                                # Check if running before sleep
                                if not self.is_running:
                                    break
                                time.sleep(0.1)
                                continue
                            
                            # Reset consecutive failures when we get a good frame
                            consecutive_failures = 0
                            
                            # Update last frame time for video FPS control
                            if self.is_video_file:
                                last_frame_time = time.time()
                            
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
                            
                            # Check if running before sleep
                            if not self.is_running:
                                break
                            time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.error(f"Camera connection error: {e}")
                    retry_count += 1
                    
                    if retry_count < self.max_retries and self.is_running:
                        self.logger.info(f"Retrying in {self.retry_delay} seconds... (Attempt {retry_count}/{self.max_retries})")
                        
                        # Break retry delay into small chunks to check is_running
                        for _ in range(int(self.retry_delay * 10)):
                            if not self.is_running:
                                break
                            time.sleep(0.1)
                    
                    # Clean up camera resources
                    if cap is not None:
                        cap.release()
                        cap = None
            
        finally:
            # Final cleanup - ensure camera is released
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