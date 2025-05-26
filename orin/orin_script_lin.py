import cv2
import socket
import numpy as np
import tensorflow as tf
import donkeycar as dk
import tflite_runtime.interpreter as tflite
import psutil
import time
import threading
import queue
from collections import deque
from statistics import mean
from typing import Dict, Tuple, List

#rolling window of roughly 60 seconds of history captured
class MetricsTracker:
    def __init__(self, window_size=1800):
        self.cpu_usage = deque(maxlen=window_size)
        self.memory_usage = deque(maxlen=window_size)
        self.inference_times = deque(maxlen=window_size)
        self.last_print_time = time.time()
        self.process = psutil.Process()
        self.metrics_lock = threading.Lock()
        self.queue_sizes = deque(maxlen=window_size)  # Track frame queue size
        self.fps = deque(maxlen=window_size)  # Track frames processed per second. fps = frames processed per second, not typical video frame rate meaning
        self.last_frame_count = 0
        self.last_fps_time = time.time()
    
    def update_system_metrics(self):
        cpu_percent_per_core = psutil.cpu_percent(interval=None, percpu=True)
        with self.metrics_lock:
            self.cpu_usage.append(sum(cpu_percent_per_core) / len(cpu_percent_per_core))
            self.memory_usage.append(self.process.memory_percent())

            # Add queue size tracking
            self.queue_sizes.append(frame_queue.qsize())

            #Calculate FPS (frames processed per second)
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                current_frame_count = sum(conn.frames_received for conn in pi_connections.values())
                frames_since_last = current_frame_count - self.last_frame_count
                fps = frames_since_last / (current_time - self.last_fps_time)
                self.fps.append(fps)
                self.last_frame_count = current_frame_count
                self.last_fps_time = current_time

    def add_inference_time(self, start_time):
        with self.metrics_lock:
            self.inference_times.append((time.time() - start_time) * 1000)

    def print_metrics(self):
        current_time = time.time()
        if current_time - self.last_print_time >= 5:
            with self.metrics_lock:
                avg_cpu = mean(self.cpu_usage) if self.cpu_usage else 0
                avg_mem = mean(self.memory_usage) if self.memory_usage else 0
                avg_inf = mean(self.inference_times) if self.inference_times else 0
                inf_count = len(self.inference_times)
                avg_fps = mean(self.fps) if self.fps else 0
                avg_queue = mean(self.queue_sizes) if self.queue_sizes else 0

            print(f"\nSystem Performance (last {inf_count} frames):")
            print(f"CPU: {avg_cpu:.1f}% | Memory: {avg_mem:.1f}% | Inference: {avg_inf:.1f}ms")
            print(f"FPS: {avg_fps:.1f} | Queue Size: {avg_queue:.1f} frames")
            print("-" * 50)

            self.last_print_time = current_time

class PiConnection:
    def __init__(self, pi_id: str, ip: str, UDP_PORT: int, TCP_PORT: int, 
                 frame_queue: queue.Queue, model_queue: queue.Queue):
        self.pi_id = pi_id
        self.ip = ip
        self.UDP_PORT = UDP_PORT
        self.TCP_PORT = TCP_PORT
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.frame_queue = frame_queue
        self.model_queue = model_queue
        self.running = True
        self.frames_received = 0
        self.controls_sent = 0
        self.last_frame_time = 0
        self.last_control_time = 0
        self.latest_frame = None
        self.latest_steering = 0
        self.latest_throttle = 0

    def start(self):
        # Connect control socket
        self.control_socket.connect((self.ip, self.TCP_PORT))
        
        # Start video capture
        self.cap = cv2.VideoCapture(f"udp://{self.ip}:{self.UDP_PORT}", cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video stream from {self.ip}")
        
        # Start video receiver thread
        self.video_thread = threading.Thread(target=self._video_loop)
        self.video_thread.daemon = True
        self.video_thread.start()
        
        # Start control sender thread
        self.control_thread = threading.Thread(target=self._control_loop)
        self.control_thread.daemon = True
        self.control_thread.start()
        
        print(f"Started connection to {self.pi_id} at {self.ip}")

   #Thread that receives frames from its assigned pi and puts them in processing queue
    def _video_loop(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
                if ret:
                    self.frames_received += 1
                    self.last_frame_time = time.time()
                    self.latest_frame = frame.copy() # Store a copy of the latest frame for display
                    self.frame_queue.put((self.pi_id, frame))
                else:
                    time.sleep(0.01)  # Short sleep if no frame
            except Exception as e:
                print(f"Error in video loop for {self.pi_id}: {e}")
                time.sleep(0.1)  # Prevent tight loop on error

    #Thread that sends control values back to its assigned Pi
    def _control_loop(self):
        while self.running:
            try:
                steering, throttle = self.model_queue.get(timeout=1.0)

                # Store latest values for display
                self.latest_steering = steering
                self.latest_throttle = throttle

                message = f"{steering},{throttle}\n"
                self.control_socket.sendall(message.encode())
                self.controls_sent += 1
                self.last_control_time = time.time()
                self.model_queue.task_done()
            except queue.Empty:
                pass  # No control values to send
            except Exception as e:
                print(f"Error sending controls to {self.pi_id}: {e}")
                time.sleep(0.1)  # Prevent tight loop on error
    

#Return connection status info
    def get_status(self):
        now = time.time()
        frame_age = now - self.last_frame_time if self.last_frame_time > 0 else float('inf')
        control_age = now - self.last_control_time if self.last_control_time > 0 else float('inf')
        
        return {
            'pi_id': self.pi_id,
            'frames_received': self.frames_received,
            'controls_sent': self.controls_sent,
            'frame_age': frame_age,
            'control_age': control_age,
            'healthy': frame_age < 1.0 and control_age < 1.0
        }
#Clean up resources
    def cleanup(self):
        self.running = False
        time.sleep(0.5)  # Allow threads to exit gracefully
        
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            
        try:
            self.control_socket.shutdown(socket.SHUT_RDWR)
            self.control_socket.close()
        except:
            pass

#Worker threads that perform model inference on frames
def inference_worker(frame_queues, model_queues, interpreter, input_details, output_details, metrics):
    while True:
        try:
            # Fetch frame from queue
            pi_id, frame = frame_queues.get(timeout=0.1)
            
            # Process frame
            processed_frame = cv2.resize(frame, (IMAGE_W, IMAGE_H))
            processed_frame = np.expand_dims(processed_frame, axis=0)
            processed_frame = processed_frame.astype(np.float32) / 255.0

            # Model inference
            inference_start = time.time()
            interpreter.set_tensor(input_details[0]['index'], processed_frame)
            interpreter.invoke()
            
            # Obtain control values
            steering = float(interpreter.get_tensor(output_details[0]['index'])[0][0])
            throttle = float(interpreter.get_tensor(output_details[1]['index'])[0][0])
            
            # Add to Pi's model queue
            model_queues[pi_id].put((steering, throttle))
            
            # Update metrics
            metrics.add_inference_time(inference_start)
            
            # Mark task as done
            frame_queues.task_done()
            
        except queue.Empty:
            pass  # No frames to process
        except Exception as e:
            print(f"Error in inference worker: {e}")
            time.sleep(0.1)  # Prevent tight loop on error
            
#Thread that reports connection status
def status_reporter(pi_connections, stop_event):
    while not stop_event.is_set():
        try:
            time.sleep(10)  # Report connection status every 10 seconds
            print("\n--- Connection Status Report ---")
            
            all_healthy = True
            for conn in pi_connections.values():
                status = conn.get_status()
                health = "✓" if status['healthy'] else "✗"
                print(f"{status['pi_id']}: {health} | Frames: {status['frames_received']} | Controls: {status['controls_sent']}")
                all_healthy = all_healthy and status['healthy']
                
            print(f"Overall system health: {'Good' if all_healthy else 'Issues Detected'}")
            print("--------------------------------\n")
        except Exception as e:
            print(f"Error in status reporter: {e}")

def metrics_monitor(metrics, stop_event):
    while not stop_event.is_set():
        metrics.update_system_metrics()
        metrics.print_metrics()
        time.sleep(1)

#Starts thread displaying frames from all pi connections 
def display_frames(pi_connections, stop_event):    
    # Create windows for each Pi
    for pi_id in pi_connections:
        cv2.namedWindow(f"Camera Feed - {pi_id}", cv2.WINDOW_NORMAL)
        cv2.resizeWindow(f"Camera Feed - {pi_id}", 640, 480)
    
    # Create shared dictionary to store latest frames
    latest_frames = {}
    
    while not stop_event.is_set():
        for pi_id, connection in pi_connections.items():
            # Update frames if connection has a latest_frame
            if hasattr(connection, 'latest_frame') and connection.latest_frame is not None:
                latest_frames[pi_id] = connection.latest_frame
            
            # Display the latest frame
            if pi_id in latest_frames:
                # Text overlay displaying steering/throttle values
                frame = latest_frames[pi_id].copy()
                if hasattr(connection, 'latest_steering') and hasattr(connection, 'latest_throttle'):
                    cv2.putText(frame, f"Steering: {connection.latest_steering:.2f}", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(frame, f"Throttle: {connection.latest_throttle:.2f}", 
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.imshow(f"Camera Feed - {pi_id}", frame)
        
        # press 'q' to quit
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            stop_event.set()
            break
            
        time.sleep(0.03)  # Sleep to control frame rate
    
    # Clean up
    for pi_id in pi_connections:
        cv2.destroyWindow(f"Camera Feed - {pi_id}")

IMAGE_H = 120
IMAGE_W = 160
IMAGE_DEPTH = 3

PI_CONFIGS = {
    'pi1': {'ip': '192.168.1.65', 'UDP_PORT': 5000, 'TCP_PORT': 6000},
    'pi3':{'ip':'192.168.1.219','UDP_PORT': 2000, 'TCP_PORT': 4000}
    # Add Pis here, include ip address and the UDP_PORT + TCP_PORT each pi will be occupying
}

#model path goes here
model_path = '/home/rafael/Downloads/donkey-car-main/models/OFFICIAL_DEMO_MODEL.tflite'
input_shape = (IMAGE_H, IMAGE_W, IMAGE_DEPTH)

# Initialize metrics and model
metrics = MetricsTracker()

# Create shared queues
frame_queue = queue.Queue(maxsize=50)  # Limit queue size to prevent memory issues
model_queues = {pi_id: queue.Queue() for pi_id in PI_CONFIGS.keys()}

# Initialize connections for all Pis
pi_connections: Dict[str, PiConnection] = {}
for pi_id, config in PI_CONFIGS.items():
    try:
        connection = PiConnection(
            pi_id=pi_id,
            ip=config['ip'], 
            UDP_PORT=config['UDP_PORT'], 
            TCP_PORT=config['TCP_PORT'],
            frame_queue=frame_queue,
            model_queue=model_queues[pi_id]
        )
        connection.start()
        pi_connections[pi_id] = connection
    except Exception as e:
        print(f"Failed to connect to {pi_id}: {e}")

# Start inference worker threads
num_inference_workers = 8  # Increase this on more powerful systems
inference_threads = []
for _ in range(num_inference_workers):
    worker_interpreter = tflite.Interpreter(model_path=model_path)
    worker_interpreter.allocate_tensors()
    worker_input_details = worker_interpreter.get_input_details()
    worker_output_details = worker_interpreter.get_output_details()

    thread = threading.Thread(
        target=inference_worker, 
        args=(frame_queue, model_queues, worker_interpreter, 
              worker_input_details, worker_output_details, metrics)
    )
    thread.daemon = True
    thread.start()
    inference_threads.append(thread)

# Start status reporter thread
stop_event = threading.Event()
status_thread = threading.Thread(target=status_reporter, args=(pi_connections, stop_event))
status_thread.daemon = True
status_thread.start()

# Start metrics monitoring thread
metrics_thread = threading.Thread(target=metrics_monitor, args=(metrics, stop_event))
metrics_thread.daemon = True
metrics_thread.start()

# Add after starting the other threads:
display_thread = threading.Thread(target=display_frames, args=(pi_connections, stop_event))
display_thread.daemon = True
display_thread.start()

# Main thread monitors for keyboard interrupt
try:
    print("System running. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutdown requested...")
finally:
    # Signal threads to stop
    stop_event.set()
    
    # Wait for display to close
    time.sleep(0.5)
    
    # Cleanup connections
    for connection in pi_connections.values():
        connection.cleanup()
    
    # Make sure OpenCV windows are closed
    cv2.destroyAllWindows()
    
    print("Shutdown complete.")
