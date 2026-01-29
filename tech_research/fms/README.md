- to install rmf-core, no need to build it

```bash
sudo apt update
sudo apt install ros-jazzy-rmf-dev
```

- to install rmf-demo, which is the best practice to solve dependency problem
since the official release of jazzy version, it should be installed with binaries
first, install gazebo

```bash
sudo apt update
sudo apt install curl lsb-release gnupg
sudo curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
sudo apt update
sudo apt install gz-harmonic
```

- then to install demo

```bash
mkdir ~/rmf_ws/src -p
cd ~/rmf_ws/src
git clone https://github.com/open-rmf/rmf_demos.git -b 2.3.0
cd ..
colcon build
```

- ros-demo should be set, additional to naive jazzy-ros env

```bash
source ./install/local_setup.bash
```
