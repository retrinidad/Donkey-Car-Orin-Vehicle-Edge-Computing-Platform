import subprocess
import socket
import time
from adafruit_pca9685 import PCA9685
import busio
import board
import threading
import pins
import donkeycar as dk
from donkeycar.parts.actuator import PWMSteering, PWMThrottle, PulseController



server_ip = '192.168.1.231'
VIDEO_PORT = 5000
CONTROL_PORT = 6000

cfg = dk.load_config()

dt = cfg.PWM_STEERING_THROTTLE

steering_controller = PulseController(
    pwm_pin=pins.pwm_pin_by_id(dt["PWM_STEERING_PIN"]),
    pwm_scale=dt["PWM_STEERING_SCALE"],
    pwm_inverted=dt["PWM_STEERING_INVERTED"]
)

steering = PWMSteering(
    controller=steering_controller,
    left_pulse=dt["STEERING_LEFT_PWM"],
    right_pulse=dt["STEERING_RIGHT_PWM"]
)

throttle_controller = PulseController(
    pwm_pin=pins.pwm_pin_by_id(dt["PWM_THROTTLE_PIN"]),
    pwm_scale=dt["PWM_THROTTLE_SCALE"],
    pwm_inverted=dt["PWM_THROTTLE_INVERTED"]
)

throttle = PWMThrottle(
    controller = throttle_controller,
    max_pulse = dt["THROTTLE_FORWARD_PWM"],
    zero_pulse = dt["THROTTLE_STOPPED_PWM"],
    min_pulse = dt["THROTTLE_REVERSE_PWM"]
)


def start_control_client():
    """Connect to the Orin's TCP control server and receive steering/throttle commands."""
    while True:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"Connecting to control server at {server_ip}:{CONTROL_PORT}...")
            sock.connect((server_ip, CONTROL_PORT))
            print("Connected to control server.")

            buffer = ""
            while True:
                data = sock.recv(1024)
                if not data:
                    print("Control server closed connection.")
                    break

                buffer += data.decode("utf-8")

                # Process all complete newline-delimited messages
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        steering_value, throttle_value = map(float, line.split(","))
                    except ValueError:
                        print(f"Invalid data received: {line}")
                        continue

                    steering.run(steering_value)
                    throttle.run(throttle_value)

        except (ConnectionRefusedError, ConnectionResetError, OSError) as e:
            print(f"Control connection error: {e}. Retrying in 2 seconds...")

        except KeyboardInterrupt:
            print("Interrupted. Shutting down...")
            break

        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

        time.sleep(2)  # Wait before reconnection attempt

#original width 640 height 480
def start_video_stream():
    cmd = (
        f"libcamera-vid -t 0 --width 160 --height 120 --inline --hflip --vflip "
        f"--output tcp://{server_ip}:{VIDEO_PORT}"
    )
    print(f"Starting libcamera-vid TCP stream to {server_ip}:{VIDEO_PORT}...")
    subprocess.Popen(cmd, shell=True)
    print("Video stream started.")

threading.Thread(target=start_video_stream, daemon=True).start()
start_control_client()

