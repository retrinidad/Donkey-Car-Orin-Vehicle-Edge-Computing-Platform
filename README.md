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

# CHI@Edge for Edge Computing

## What is it?

Chi@Edge is an edge computing platform and testbed provided by Argonne National Lab, which is run by the University of Chicago. It provide edge devices of various types such as  Raspberry Pi's, Jetson Nano's and Jetson Xavier's for rent to use as computational power (you can also put your own devices up for rent). For more detailed about the types devices they have for lease, check out the [Chi@Edge Resource Page](https://chameleoncloud.org/experiment/chiedge/hardware-info/). However, due to the fact that its edge devices are far away and are communicated with through the internet, it acts more like an cloud computing service as opposed to the local edge computing setup we have with the AGX Orin. The intent of testing out autonomous driving with models hosted on these edge devices elsewhere in the nation is to test the performance of a cloud-like computing solution, to collect more data and to hopefully lend more credence to advantages of local edge computing solutions such as the one we have set up. 

## Get started with Chi@Edge

Listed under this section are some resources to give a brief overview of what Chi@Edge does and get some hands on practice with it. 

First, you must be added to a Chi@Edge project in order to access their services. If you're interested in picking up tasks for the Chi@Edge work we do here, communicate with Dr. Wang about getting added to a Chi@Edge project. 

Intro video to Chi@Edge: [Link](https://youtu.be/b0Sy6YCBX_8?si=M6hB9iu2pQIdScwO)

Documentation: [Link](https://chameleoncloud.gitbook.io/chi-edge)

Starting with either is fine, as they both cover simliar steps but I recommend starting with the video as its a more broad overview of what Chi@Edge does and holds your hand through the basic set up process. Simliar steps to for setting up a webserver on a Chi@Edge device can also be found under the "Getting Started" tab but I would say its harder to understand and follow along with. 

Follow along with the video, understand what you can from the whole video but you will only need the information up to about to 17:40 for the purposes of our donkey car-chi@edge device setup. 

Like the video mentioned, the Chi@Edge portal is great hub to access everything Chi@Edge related and Trovi is an archive of tutorials to aid in your Chi@Edge objectives and resolve any issues you may encounter. 

Chi@Edge Portal: [Link](https://chameleoncloud.org/experiment/chiedge/)

Trovi: [Link](https://chameleoncloud.org/experiment/share/)

## Get up to speed with the current setup we have
The current setup we have follows the following archieture: 

**Components**:

**Edge Device** - Devices leased from Chi@Edge. Could be raspberry, Jetson Nano, etc. Number of devices leased is usually 1 or 2.

**Container** - Launched on the edge devices to create an light-weight OS on which to run programs, upload files, serves files over HTTP, etc. 

**Self Driving Model** - Titled "OFFICIAL_DEMO_MODEL.tfile." Is the self driving model that will be deployed on the Chi@Edge devices. 

**edge_script** - the script that communicates with donkey_script to send control signals (throttle and steering values) to the donkey car

**donkey_script** - the script that communicates with edge_script to send videos frames to the edge device to process and send control signals back. 

**System Architecture**

1 or 2 Edge Devices are leased from Chi@Edge. On those  edge devices, we create a single container. On this container, we upload the official self driving model and the edge_script. We also a assign a public IP address through which the container can be accessed over the public internet. On the donkey car, we house the donkey_script. When both scripts are run at same time, they should communicate with each other with the donkey car sending video frames to the edge device and the edge device sending control signals back.

**Getting Up to Speed with our current setup**

After following to tutorial up to about 17:40, you should have a general idea of how to lease a Chi@Edge device, launch a container, assign it public IP, and upload files to it. This is exactly what we'll be doing to set up the edge side of our setup, with the only exception being we uplaod the model and edge script to the webserver instead. In fact, the Jupyter Notebook file we'll be using is exactly the same as the one in the video, with mofidicatoins only for our specific use case. 

Find the chi_edge directory inside this repo, and upload it to the Chameleon Jupyter workspace (the one we used for the intro to Chi@Edge tutorial).

Create a copy of the the CHI@Edge.ipynb file and follow the steps outlined to lease edge device(s), launch a container, assign a public IP, and upload the model and edge script. Run each cell, modifying cells as needed for your specific context. The original CHI@Edge.ipynb file contains the outputs of running each cell which can serve as a reference for what your output should look like. 

Note: Use your project ID (if different from the one already in the notebook)

Note: sometimes you may not be able to lease 2 devices, in that case only lease 1. If you are unable to lease even 1 device, try to see if there an error causing that issue or if you're positive that there no such error, all edge device may just be booked at that time. Try again at another time.

Note: After leasing your device, you will probably want to extend your lease, because once it ends, you will lose your container and all the set up you've done up to this point. You can do that in the Chi@Edge GUI under the reservation -> leases tab. Currently you can only extend it by 7 days because of the limited amount of device and bacause other researchers have to use it also. After that time, you will have to go through these steps to setup everything up again. 

Then, open a console within the container as detailed in the video, and install these packages using the following commands:

```
apt-get update
apt-get install -y ffmpeg
pip install 'numpy<2.0.0' psutil opencv-python-headless donkeycar tflite-runtime

```

These packages are required for the edge_script to run. 

On the donkey car, cd into the directory that house the donkey script, and run the following command to start the donkey script:

```python donkey_script.py```

After that, run the following command to start the edge script on the edge device:

```python edge_script.py```

After all of this, the scripts should communicate with each other, with the donkey script logging the steering and throttle values it is receiving, and the edge script logging the video frames it is receving. The donkey car may even show a video stream of the videos frames its sending to the edge device. The donkey car will also be driving. 

## Currents tasks to do

Currently, even though we have communciation with an Chi@Edge device set up, it is still far from perfect. As of current, the throtle value is hardcoded to a fix value as the donkey car would be driving extremely fast with the throttle values it receives from the edge device. Further, the donkey car does not steer correctly on the track. Your task is to debug and fix thses issue such that its throttle no longer relies on a hardcoded value and it is able to dynamically follow the track we have for self driving. Once fixed, run experiments and collect performance and latency data to be include in our research. 

## More to come
- Communication Latency Measurement script 