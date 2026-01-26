#pragma once

#include <cstdint>
#include <fstream>
#include <memory>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <unordered_map>
#include <vector>

#include "PxPhysicsAPI.h"

// Vehicle includes
#include "vehicle/PxVehicleDrive4W.h"
#include "vehicle/PxVehicleUpdate.h"
#include "vehicle/PxVehicleUtilSetup.h"

using namespace physx;
namespace py = pybind11;

class PhysXManager
{
private:
    // Core SDK
    PxFoundation* mFoundation = nullptr;
    PxPhysics* mPhysics = nullptr;
    PxCooking* mCooking = nullptr;
    PxScene* mScene = nullptr;
    PxMaterial* mMaterial = nullptr;
    PxDefaultCpuDispatcher* mDispatcher = nullptr;
    PxDefaultAllocator mAllocator;

    // Serialization
    PxSerializationRegistry* mSerializationRegistry = nullptr;
    std::vector<void*> mSerializedMemories;

    // Vehicle Placeholders
    PxVehicleDrive4W* mVehicle = nullptr;
    PxBatchQuery* mBatchQuery = nullptr;
    PxVehicleDrivableSurfaceToTireFrictionPairs* mFrictionPairs = nullptr;
    PxRaycastQueryResult* mRaycastResults = nullptr;
    PxRaycastHit* mRaycastHits = nullptr;
    PxVehicleWheelQueryResult* mVehWheelQueryResults = nullptr;
    PxWheelQueryResult* mWheelQueryResults = nullptr;

    // Handle Map
    std::unordered_map<uint64_t, PxRigidActor*> mActorMap;

    // Helpers
    PxGeometryHolder createGeometryHolder(const std::string& type,
                                          const std::string& data,
                                          const std::vector<float>& dims,
                                          std::vector<PxBase*>& outResources);

    static void setupVehicleBuffers();
    void cleanupVehicle();

public:
    PhysXManager();
    ~PhysXManager();

    bool init();
    void shutdown();
    void reset();

    bool isInitialized() const { return mPhysics != nullptr; }
    auto getActorCount() const -> size_t { return mActorMap.size(); }

    void setGravity(float x, float y, float z);

    // Cooking
    auto cookMesh(std::string type, std::vector<float> verts,
                  const std::vector<int>& indices, int vertLimit) -> py::bytes;
    static auto processHeightField(int rows, int cols,
                                   std::vector<float> heights) -> py::bytes;
    auto cookHeightFieldFromMesh(int rows, int cols,
                                 std::vector<float> startPos,
                                 std::vector<float> step,
                                 std::vector<float> meshVerts,
                                 std::vector<int> meshIndices,
                                 std::vector<float> meshTransform) -> py::bytes;
    auto getCookedGeometry(const std::string& type, std::string data) const -> py::dict;

    // I/O
    static bool saveCookedData(const std::string& path, py::bytes data);
    static py::bytes loadCookedData(const std::string& path);
    bool exportScene(const std::string& path);
    bool importScene(const std::string& path);

    // Dynamics
    auto computeMassProperties(py::list shapeList,
                               std::vector<float> densities) -> py::dict;

    // Actors
    auto createActor(std::string actorType, std::vector<float> actorPose,
                     py::list shapeList, float mass,
                     std::vector<float> massLocalPose,
                     std::vector<float> inertia) -> uint64_t;

    void removeActor(uint64_t handle);

    void applyForce(uint64_t actorHandle, std::vector<float> force, int mode,
                    bool usePos, const std::vector<float>& pos);

    void setKinematicTarget(uint64_t handle, std::vector<float> pos,
                            std::vector<float> rot);

    // Simulation
    void startStep(float dt);
    bool fetchResults(bool block);
    auto getActivePoses() -> py::dict;

    // Vehicle Stubs
    void buildVehicle(py::dict params);
    void updateInputs(float t, float b, float s, float h, float dt);
    auto getStats() -> py::dict;
};
