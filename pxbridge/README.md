TODO: a proper readme that's actually helpful

Build Instructions:
* clone the pybind11 repo into pxbridge/extern/
* clone the nvidia physx 3.4 repo, build the projects so you have your .dll and .lib files
* Update CMakeLists.txt so that the paths to blender and physx are correct
* make a folder /pxbridge/build
* open terminal in that folder
* ``` 
  cmake ..
  ```
  then:

* ```
  cd ..
  cmake --build build --config release
  ```
you should end up with pxbridge.pyd in /build/release without any compilation errors.
Physx 3.4 is old and it probably won't go as smooth as this the first time, I will(god I hope) update this to be acutally useful
Soon™