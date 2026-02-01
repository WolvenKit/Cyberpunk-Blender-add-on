cmake_minimum_required(VERSION 3.18)
project(pxbridge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# SET PATH TO BLENDER ROOT

set(BLENDER_ROOT "C:/Program Files/Blender Foundation/Blender 5.0/5.0")
set(BL_PYTHON_DIR "${BLENDER_ROOT}/python")

if (EXISTS "${BL_PYTHON_DIR}/libs/python311.lib")
    set(MY_PY_LIB "${BL_PYTHON_DIR}/libs/python311.lib")
elseif (EXISTS "${BL_PYTHON_DIR}/libs/python3.lib")
    set(MY_PY_LIB "${BL_PYTHON_DIR}/libs/python3.lib")
else ()
    message(FATAL_ERROR "Could not find python lib in ${BL_PYTHON_DIR}/libs")
endif ()

set(MY_PY_INC "${BL_PYTHON_DIR}/include")

message(STATUS "--- MANUAL PYTHON CONFIG ---")
message(STATUS "  - Library: ${MY_PY_LIB}")
message(STATUS "  - Include: ${MY_PY_INC}")
if (MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    message(STATUS "  - Forcing MSVC Runtime Library to /MT")
endif ()


set(PYBIND11_NOPYTHON ON)

if (EXISTS "${CMAKE_CURRENT_LIST_DIR}/third_party/pybind11")
    add_subdirectory("third_party/pybind11")
elseif (EXISTS "${CMAKE_CURRENT_LIST_DIR}/extern/pybind11")
    add_subdirectory("extern/pybind11")
else ()
    message(FATAL_ERROR "pybind11 not found.")
endif ()

if (NOT PHYSX_SDK_DIR)
    set(PHYSX_SDK_DIR "C:/repos/PhysX-3.4/PhysX_3.4")
endif ()
if (NOT PHYSX_LIB_DIR)
    set(PHYSX_LIB_DIR "${PHYSX_SDK_DIR}/Lib/vc15win64")
endif ()

file(TO_CMAKE_PATH "${PHYSX_SDK_DIR}" PHYSX_SDK_DIR)
file(TO_CMAKE_PATH "${PHYSX_LIB_DIR}" PHYSX_LIB_DIR)

get_filename_component(PXSHARED_ROOT "${PHYSX_SDK_DIR}/.." ABSOLUTE)
find_path(PHYSX_INCLUDE_DIR NAMES PxPhysicsAPI.h HINTS "${PHYSX_SDK_DIR}" PATH_SUFFIXES include Include)
find_path(PXSHARED_INCLUDE_DIR NAMES foundation/Px.h HINTS "${PXSHARED_ROOT}" PATH_SUFFIXES PxShared/include)
find_path(PHYSX_VEHICLE_INCLUDE_DIR NAMES vehicle/PxVehicleSDK.h HINTS "${PHYSX_SDK_DIR}" PATH_SUFFIXES include Include)

set(PHYSX_LIBRARIES "")
set(PHYSX_SHARED_LIB_DIR "${PXSHARED_ROOT}/PxShared/lib/vc15win64")
file(TO_CMAKE_PATH "${PHYSX_SHARED_LIB_DIR}" PHYSX_SHARED_LIB_DIR)

macro(find_physx_lib ALIAS LIB_NAME SEARCH_PATH)
    find_library(LIB_PATH_${ALIAS} NAMES ${LIB_NAME} HINTS "${SEARCH_PATH}" NO_DEFAULT_PATH)
    if (NOT LIB_PATH_${ALIAS})
        message(FATAL_ERROR "Could not find '${LIB_NAME}' in ${SEARCH_PATH}")
    endif ()
    list(APPEND PHYSX_LIBRARIES "${LIB_PATH_${ALIAS}}")
endmacro()

find_physx_lib(Foundation PxFoundation_x64 "${PHYSX_SHARED_LIB_DIR}")
find_physx_lib(PvdSDK PxPvdSDK_x64 "${PHYSX_SHARED_LIB_DIR}")
find_physx_lib(Task PxTask_x64 "${PHYSX_SHARED_LIB_DIR}")
find_physx_lib(PhysX PhysX3_x64 "${PHYSX_LIB_DIR}")
find_physx_lib(Common PhysX3Common_x64 "${PHYSX_LIB_DIR}")
find_physx_lib(Cooking PhysX3Cooking_x64 "${PHYSX_LIB_DIR}")
find_physx_lib(Extensions PhysX3Extensions "${PHYSX_LIB_DIR}")
find_physx_lib(Vehicle PhysX3Vehicle "${PHYSX_LIB_DIR}")

add_library(pxbridge SHARED pxbridge.cpp)

target_compile_definitions(pxbridge PRIVATE Py_EXPORTS)

set_target_properties(pxbridge PROPERTIES
        PREFIX ""
        SUFFIX ".pyd"
)

target_link_libraries(pxbridge PRIVATE pybind11::headers)

target_include_directories(pxbridge PRIVATE "${MY_PY_INC}")
target_link_libraries(pxbridge PRIVATE "${MY_PY_LIB}")

target_include_directories(pxbridge PRIVATE
        "${PHYSX_INCLUDE_DIR}"
        "${PXSHARED_INCLUDE_DIR}"
        "${PHYSX_VEHICLE_INCLUDE_DIR}"
)

target_link_libraries(pxbridge PRIVATE ${PHYSX_LIBRARIES})

message(STATUS "Configuration Successful. Ready to build Release.")

message(STATUS "Configuration Successful. Ready to build.")