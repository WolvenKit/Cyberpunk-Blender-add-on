Build Instructions:
* clone the pybind11 repo into pxbridge/extern/
* clone the nvidia physx 3.4 repo, build the projects so you have your .dll and .lib files
* Make sure you have Python 3.13.x installed on your system
* Update CMakeLists.txt so that the paths to physx are correct (CMake will automatically locate Python 3.13).
* make sure you have a /pxbridge/build folder
* open terminal in that folder
* ``` 
  cmake ..

* ```
  cd ..
  cmake --build build --config release
  ```
you should end up with pxbridge.pyd in /build/release without any compilation errors.
Physx 3.4 is old and it probably won't go as smooth as this the first time, I will(god I hope) update this to be actually useful Soon™