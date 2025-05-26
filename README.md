# Raspberry Pi Donkey Car - Orin Vehicular Edge Computing Platform

## Requirements
Hardware
- At least one Donkey Car
- An NVIDIA Jetson AGX Orin Module
- Road Track Mat

Software
- Prerequisite steps will cover most of the necessary software to install. However, on the Donkey Car you
are using please enter this command in the terminal: pip install adafruit-circuitpython-pca9685
- On the Orin module, install OpenCV, Tensorflow, and Tensorflow Lite

## Prerequisite Steps
First, obtain your Donkey Car, prebuilt or build your own. We used the Waveshare PiRacer Pro AI Kit, which
is equipped with a Raspberry Pi 4 unit and a Raspberry Pi Camera Module.

The Donkey Car documentation wiki will be a great help in getting your Donkey Car hardware and software
ready. Here is the link: https://docs.donkeycar.com/

Once you have your built Donkey Car, please follow the steps in the "Install the software" page. Once that
is complete, proceed to the "Create Donkeycar App" page and use the donkey createcar --path ~/mycar command.

These steps should be enough to get your Donkey Car driving. "Get driving" will teach you how to drive your
vehicle with a joystick controller, e.g. Xbox controller.

If you want to create your own autopilot, follow the "Create an atuopilot" page. For this project, we have
only used Deep Learning Autpilots. While you can create your own autopilot model, we will provide one for
you. You can make use of the tflite linear model OFFICIAL_DEMO_MODEL.tflite at https://github.com/SigsFig/donkey-car/tree/main/models. 
An additional tflite categorical model is provided. 

Finally, you must also install the required software on the Orin module. Software installation for all
devices usually took us 20 to 30 minutes.

## Running your vehicle locally
Navigate to your mycar directory and use the command: python manage.py drive --model ~/mycar/models/OFFICIAL_DEMO_MODEL.tflite --type tflite_linear

If using a different model, make sure that --type is followed by the appropriate model type.

Make sure to calibrate your vehicle using config.py if lane following is not accurate.

We provide our own manage.py file that records metrics of the car running locally if you would like to use 
that one, measuring CPU and memory usage and inference latency.

## Running the Donkey Car - Orin Edge Computing Platform
IMPORTANT - Make sure pins.py is installed in your mycar directory on your Raspberry Pi 4 Donkey Car.

On your Donkey Car, run the rpi4.py script from your mycar directory and place it on your track. Then, run the orin_script_lin.py script on the Orin module from the Orin's mycar directory. If running the provided categorical model, run this orin_script_cat.py instead.

Additionally, in your Donkey Car's local copy of rpi4.py, update the server_ip variable to be the actual IP
address of your Orin module. You may change the value of UDP_PORT and TCP_PORT, but these values must be 
valid. In your Orin module's local copy of orin_script_lin.py and orin_script_cat.py, in the PI_CONFIGS 
dictionary, include your Donkey Car into the collection and list your car's ip address (which is not the 
server_ip variable from rpi4.py) and UDP_PORT and TCP_PORT (the same ones from your Donkey Car's local copy 
of rpi4.py).

To obtain the ip address of your Donkey Car or Orin device, use the command hostname -I on your terminal and use the first value that appears.

## More to come
- How to connect to a device on CHI@EDGE
- Communication Latency Measurement scripts