import cv2
import socket
import numpy as np
import donkeycar as dk
import tflite_runtime.interpreter as tflite
import psutil
import time
import threading
import queue
import struct
from collections import deque
from statistics import mean

class MetricsTracker:
    def __init__(self, window_size=1800):
        self.cpu_usage = deque(maxlen=window_size)
        self.memory_usage = deque(maxlen=window_size)
        self.inference_times = deque(maxlen=window_size)
        self.last_print_time = time.time()
        self.process = psutil.Process()
        self.metrics_lock = threading.Lock()
    
    def update_system_metrics(self):
        cpu_percent_per_core = psutil.cpu_percent(interval=None, percpu=True)
        with self.metrics_lock:
            self.cpu_usage.append(sum(cpu_percent_per_core) / len(cpu_percent_per_core))
            self.memory_usage.append(self.process.memory_percent())

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

            print(f"\nAverages over last {inf_count} frames:")
            print(f"CPU Usage: {avg_cpu:.1f}%")
            print(f"Memory Usage: {avg_mem:.1f}%")
            print(f"Inference Time: {avg_inf:.1f}ms\n")
            print("-" * 50)

            self.last_print_time = current_time

class PiConnectionServer:
    """Reversed architecture: Edge device acts as server, Pi connects to it"""
    def __init__(self, pi_id, control_port, video_port, frame_queue, model_queue):
        self.pi_id = pi_id
        self.control_port = control_port
        self.video_port = video_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', control_port))
        self.server_socket.listen(5)
        self.frame_queue = frame_queue
        self.model_queue = model_queue
        self.running = True
        self.client_socket = None
        self.frames_received = 0
        self.controls_sent = 0
        self.last_frame_time = 0
        self.last_control_time = 0
        
    def start(self):
        print(f"Starting server for {self.pi_id} on port {self.control_port}")
        # Start control server thread
        self.control_thread = threading.Thread(target=self._control_server_loop)
        self.control_thread.daemon = True
        self.control_thread.start()
        
        # Start video receiver thread - now we'll use OpenCV to capture from TCP
        self.video_thread = threading.Thread(target=self._video_loop)
        self.video_thread.daemon = True
        self.video_thread.start()
        
    def _control_server_loop(self):
        """Thread that accepts connections and sends control values back to the Pi"""
        print(f"Waiting for connection from {self.pi_id} on port {self.control_port}...")
        while self.running:
            try:
                self.server_socket.settimeout(1.0)  # Check for shutdown every second
                client_socket, addr = self.server_socket.accept()
                print(f"Connection from {addr} established for {self.pi_id}")
                self.client_socket = client_socket
                
                # Start sending controls
                while self.running and self.client_socket:
                    try:
                        steering, throttle = self.model_queue.get(timeout=1.0)
                        message = f"{steering},{throttle}\n"
                        self.client_socket.sendall(message.encode())
                        self.controls_sent += 1
                        self.last_control_time = time.time()
                        self.model_queue.task_done()
                        print(f"[ControlLoop] Sending control to {self.pi_id}: Steering={steering:.4f}, Throttle={throttle:.4f}")
                    except queue.Empty:
                        # If no control values and we haven't received frames, send zeros
                        if time.time() - self.last_frame_time > 5.0:
                            try:
                                message = "0.0,0.0\n"  # Default to stopped if no frames
                                self.client_socket.sendall(message.encode())
                                print(f"[ControlLoop] No frames received. Sending stop command to {self.pi_id}")
                            except:
                                pass
                    except BrokenPipeError:
                        print(f"Client {self.pi_id} disconnected")
                        self.client_socket = None
                        break
                    except Exception as e:
                        print(f"Error sending controls to {self.pi_id}: {e}")
                        import traceback; traceback.print_exc()
                        self.client_socket = None
                        break
            except socket.timeout:
                continue  # Loop to check if we should still be running
            except Exception as e:
                print(f"Error in control server for {self.pi_id}: {e}")
                import traceback; traceback.print_exc()
                time.sleep(1)  # Prevent tight loop on error
        
    def _video_loop(self):
        """TCP-based video reception"""
        print(f"[Video] Listening for TCP connection on port {self.video_port}")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.video_port))
        server_socket.listen(1)

        while self.running:
            try:
                client_socket, addr = server_socket.accept()
                print(f"[Video] Connection from {addr}")
                data_buffer = b''

                while self.running:
                    # Read length of JPEG frame
                    while len(data_buffer) < 4:
                        data_buffer += client_socket.recv(4096)
                    frame_len = struct.unpack('>L', data_buffer[:4])[0]
                    data_buffer = data_buffer[4:]

                    # Read the full JPEG frame
                    while len(data_buffer) < frame_len:
                        data_buffer += client_socket.recv(4096)
                    frame_data = data_buffer[:frame_len]
                    data_buffer = data_buffer[frame_len:]

                    # Decode frame
                    frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        self.frames_received += 1
                        self.last_frame_time = time.time()
                        self.frame_queue.put((self.pi_id, frame))
                        print(f"[VideoLoop] Frame received. Total: {self.frames_received}")
            except Exception as e:
                print(f"[Video] Error: {e}")
                time.sleep(1)

    def get_status(self):
        """Return connection status information"""
        now = time.time()
        frame_age = now - self.last_frame_time if self.last_frame_time > 0 else float('inf')
        control_age = now - self.last_control_time if self.last_control_time > 0 else float('inf')
        
        return {
            'pi_id': self.pi_id,
            'frames_received': self.frames_received,
            'controls_sent': self.controls_sent,
            'frame_age': frame_age,
            'control_age': control_age,
            'healthy': frame_age < 3.0 and control_age < 3.0,  # More tolerant threshold
            'connected': self.client_socket is not None
        }

    def cleanup(self):
        """Clean up all resources"""
        self.running = False
        time.sleep(0.5)  # Allow threads to exit gracefully
        
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
            except:
                pass  # Socket might already be closed
        
        try:
            self.server_socket.close()
        except:
            pass  # Server socket might already be closed

def inference_worker(frame_queues, model_queues, interpreter, input_details, output_details, metrics):
    """Worker thread that performs model inference on frames"""
    while True:
        try:
            # Get frame from queue
            pi_id, frame = frame_queues.get(timeout=0.1)
            print(f"[InferenceWorker] Received frame from {pi_id}.")
            
            # Process frame
            try:
                processed_frame = cv2.resize(frame, (IMAGE_W, IMAGE_H))
                processed_frame = np.expand_dims(processed_frame, axis=0)
                processed_frame = processed_frame.astype(np.float32) / 255.0

                print(f"[InferenceWorker] Starting inference for {pi_id}...")

                # Model inference
                inference_start = time.time()
                interpreter.set_tensor(input_details[0]['index'], processed_frame)
                interpreter.invoke()
                
                # Get control values
                steering = float(interpreter.get_tensor(output_details[0]['index'])[0][0].copy())
                throttle = float(interpreter.get_tensor(output_details[1]['index'])[0][0].copy())

                # Limit throttle to safe values for testing
                # throttle = max(min(throttle, 0.5), -0.1)  # Limit to 0.5 forward, -0.1 reverse

                print(f"[InferenceWorker] Inference done. Steering: {steering:.4f}, Throttle: {throttle:.4f}")
                
                # Add to Pi's model queue
                model_queues[pi_id].put((steering, throttle))
                
                # Update metrics
                metrics.add_inference_time(inference_start)
            except Exception as e:
                print(f"Error processing frame: {e}")
                # Send stop command in case of processing error
                model_queues[pi_id].put((0.0, 0.0))
            
            metrics.update_system_metrics()
            metrics.print_metrics()
            
            # Mark task as done
            frame_queues.task_done()
            
        except queue.Empty:
            pass  # No frames to process
        except Exception as e:
            print(f"Error in inference worker: {e}")
            import traceback; traceback.print_exc()
            time.sleep(0.1)  # Prevent tight loop on error

def status_reporter(pi_connections, stop_event):
    """Thread that reports status of all connections"""
    while not stop_event.is_set():
        try:
            time.sleep(10)  # Report every 10 seconds
            print("\n--- Connection Status Report ---")
            
            all_healthy = True
            for conn in pi_connections.values():
                status = conn.get_status()
                health = "✓" if status['healthy'] else "✗"
                conn_status = "Connected" if status['connected'] else "Disconnected"
                print(f"{status['pi_id']}: {health} | {conn_status} | Frames: {status['frames_received']} | Controls: {status['controls_sent']}")
                all_healthy = all_healthy and status['healthy']
                
            print(f"Overall system health: {'Good' if all_healthy else 'Issues Detected'}")
            print("--------------------------------\n")
        except Exception as e:
            print(f"Error in status reporter: {e}")

# Configuration
IMAGE_H = 120
IMAGE_W = 160
IMAGE_DEPTH = 3

# Control port for Pi to connect to (TCP)
CONTROL_PORT = 6000
# Video streaming port (TCP)
VIDEO_PORT = 5000

# Model path
model_path = '/var/www/html/OFFICIAL_DEMO_MODEL.tflite'
input_shape = (IMAGE_H, IMAGE_W, IMAGE_DEPTH)

# Initialize metrics and model
metrics = MetricsTracker()

# Make sure we can load the model
try:
    print(f"Loading TFLite model from {model_path}...")
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print(f"[ModelLoad] Model loaded from {model_path} with input shape: {input_details[0]['shape']}")
except Exception as e:
    print(f"Error loading model: {e}")
    import traceback; traceback.print_exc()
    print("Using dummy model for testing...")
    # Create a dummy model that returns zeros
    interpreter = None
    exit(1)  # Exit if model can't be loaded

# Create shared queues
frame_queue = queue.Queue(maxsize=50)  # Limit queue size to prevent memory issues
model_queues = {'pi1': queue.Queue()}

# Initialize connection server
pi_connections = {}
try:
    connection = PiConnectionServer(
        pi_id='pi1',
        control_port=CONTROL_PORT,
        video_port=VIDEO_PORT,
        frame_queue=frame_queue,
        model_queue=model_queues['pi1']
    )
    connection.start()
    pi_connections['pi1'] = connection
except Exception as e:
    print(f"Failed to start connection server: {e}")
    import traceback; traceback.print_exc()

# Start inference workers - multiple if needed
num_inference_workers = 2  # Reduce for lower CPU usage
inference_threads = []
for _ in range(num_inference_workers):
    thread = threading.Thread(
        target=inference_worker, 
        args=(frame_queue, model_queues, interpreter, input_details, output_details, metrics)
    )
    thread.daemon = True
    thread.start()
    inference_threads.append(thread)

# Start status reporter
stop_event = threading.Event()
status_thread = threading.Thread(target=status_reporter, args=(pi_connections, stop_event))
status_thread.daemon = True
status_thread.start()

# Main thread just monitors for keyboard interrupt
try:
    print("System running. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutdown requested...")
finally:
    # Signal threads to stop
    stop_event.set()
    
    # Cleanup connections
    for connection in pi_connections.values():
        connection.cleanup()
    
    print("Shutdown complete.")