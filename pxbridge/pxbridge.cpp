#include "pxbridge.h"
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

using namespace pybind11::literals;

class SafeErrorCallback : public PxErrorCallback
{
public:
  auto reportError(PxErrorCode::Enum code, const char* message,
                   const char* file, int line) -> void override;
};

auto SafeErrorCallback::reportError(PxErrorCode::Enum code, const char* message,
                                    const char* file, int line) -> void
{
  if (code != PxErrorCode::eDEBUG_INFO && code != PxErrorCode::ePERF_WARNING)
  {
    printf("[PhysX %d] %s\n", code, message);
  }
}

PhysXManager::PhysXManager() = default;

PhysXManager::~PhysXManager() { shutdown(); }

// LIFECYCLE

bool PhysXManager::init()
{
  if (mPhysics)
    return true;

  static SafeErrorCallback gErrorCallback;
  static PxDefaultAllocator gAllocator;

  mFoundation =
    PxCreateFoundation(PX_FOUNDATION_VERSION, gAllocator, gErrorCallback);
  if (!mFoundation)
  {
    printf("!! PxFoundation Failed\n");
    return false;
  }

  PxTolerancesScale scale;
  scale.length = 1.0f;
  scale.speed = 9.81f;

  mPhysics = PxCreatePhysics(PX_PHYSICS_VERSION, *mFoundation, scale);
  if (!mPhysics)
  {
    printf("!! PxPhysics Failed\n");
    return false;
  }

  // 1. Initialize Extensions
  if (!PxInitExtensions(*mPhysics, nullptr))
  {
    printf("!! PxExtensions Init Failed\n");
    return false;
  }

  // 2. Create Serialization Registry
  // Passing *mPhysics automatically registers core Physics serializers
  mSerializationRegistry =
    PxSerialization::createSerializationRegistry(*mPhysics);
  if (!mSerializationRegistry)
  {
    printf("!! Serialization Registry Failed\n");
    return false;
  }
  PxCookingParams params(scale);
  params.meshPreprocessParams = PxMeshPreprocessingFlag::eWELD_VERTICES;
  params.meshWeldTolerance = 0.05f;
  mCooking = PxCreateCooking(PX_PHYSICS_VERSION, *mFoundation, params);

  PxSceneDesc sceneDesc(mPhysics->getTolerancesScale());
  sceneDesc.gravity = PxVec3(0.0f, 0.0f, -9.81f);
  mDispatcher = PxDefaultCpuDispatcherCreate(2);
  sceneDesc.cpuDispatcher = mDispatcher;
  sceneDesc.filterShader = PxDefaultSimulationFilterShader;
  sceneDesc.flags |= PxSceneFlag::eENABLE_ACTIVE_ACTORS;

  mScene = mPhysics->createScene(sceneDesc);
  if (!mScene)
  {
    printf("!! PxScene Failed\n");
    return false;
  }

  mMaterial = mPhysics->createMaterial(0.5f, 0.5f, 0.6f);

  printf("[pxbridge] Initialized.\n");
  return true;
}

void PhysXManager::shutdown()
{
  cleanupVehicle();
  mActorMap.clear();

  if (mScene)
  {
    mScene->release();
    mScene = nullptr;
  }
  if (mDispatcher)
  {
    mDispatcher->release();
    mDispatcher = nullptr;
  }
  if (mCooking)
  {
    mCooking->release();
    mCooking = nullptr;
  }

  // Free serialized memory blocks
  for (void* ptr : mSerializedMemories)
  {
    free(ptr);
  }
  mSerializedMemories.clear();

  if (mSerializationRegistry)
  {
    mSerializationRegistry->release();
    mSerializationRegistry = nullptr;
  }

  if (mMaterial)
  {
    mMaterial->release();
    mMaterial = nullptr;
  }

  PxCloseExtensions();

  if (mPhysics)
  {
    mPhysics->release();
    mPhysics = nullptr;
  }
  if (mFoundation)
  {
    mFoundation->release();
    mFoundation = nullptr;
  }
}

void PhysXManager::reset()
{
  cleanupVehicle();

  if (mScene)
  {
    mScene->release();
    mScene = nullptr;
  }
  mActorMap.clear();

  // Clear serialization memory on reset
  for (void* ptr : mSerializedMemories)
  {
    free(ptr);
  }
  mSerializedMemories.clear();

  if (mPhysics && mDispatcher)
  {
    PxSceneDesc sceneDesc(mPhysics->getTolerancesScale());
    sceneDesc.gravity = PxVec3(0.0f, 0.0f, -9.81f);
    sceneDesc.cpuDispatcher = mDispatcher;
    sceneDesc.filterShader = PxDefaultSimulationFilterShader;
    sceneDesc.flags |= PxSceneFlag::eENABLE_ACTIVE_ACTORS;
    mScene = mPhysics->createScene(sceneDesc);
  }
}

void PhysXManager::setGravity(float x, float y, float z)
{
  if (mScene)
    mScene->setGravity(PxVec3(x, y, z));
}

// BINARY SERIALIZATION (SCENE)

bool PhysXManager::exportScene(const std::string& path)
{
  if (!mScene || !mSerializationRegistry)
    return false;

  // 1. Create Collection
  PxCollection* collection = PxCreateCollection();

  // 2. Add Actors
  PxU32 nbActors = mScene->getNbActors(PxActorTypeFlag::eRIGID_DYNAMIC |
    PxActorTypeFlag::eRIGID_STATIC);
  if (nbActors > 0)
  {
    std::vector<PxActor*> actors(nbActors);
    mScene->getActors(PxActorTypeFlag::eRIGID_DYNAMIC |
                      PxActorTypeFlag::eRIGID_STATIC,
                      actors.data(), nbActors);
    for (PxActor* actor : actors)
    {
      collection->add(*actor);
    }
  }

  // 3. Complete Collection
  PxSerialization::complete(*collection, *mSerializationRegistry);

  // 4. Serialize to File
  PxDefaultFileOutputStream outStream(path.c_str());
  if (!outStream.isValid())
  {
    printf("!! Failed to open %s for writing\n", path.c_str());
    collection->release();
    return false;
  }

  bool success = PxSerialization::serializeCollectionToBinary(
    outStream, *collection, *mSerializationRegistry);

  collection->release();
  return success;
}

bool PhysXManager::importScene(const std::string& path)
{
  if (!mSerializationRegistry)
  {
    // TODO: Log Error "Serialization Registry not initialized"
    return false;
  }

  // 1. Read file
  FILE* fp = fopen(path.c_str(), "rb");
  if (!fp)
    return false;

  fseek(fp, 0, SEEK_END);
  unsigned fileSize = ftell(fp);
  fseek(fp, 0, SEEK_SET);

  // Allocate with padding for alignment
  void* rawMemory = malloc(fileSize + PX_SERIAL_FILE_ALIGN);
  if (!rawMemory)
  {
    fclose(fp);
    return false;
  }

  auto rawAddr = reinterpret_cast<size_t>(rawMemory);
  size_t alignedAddr =
    (rawAddr + PX_SERIAL_FILE_ALIGN - 1) & ~(PX_SERIAL_FILE_ALIGN - 1);
  void* alignedMemory = reinterpret_cast<void*>(alignedAddr);

  fread(alignedMemory, 1, fileSize, fp);
  fclose(fp);

  // 2. Deserialize
  // Note: Do NOT push to mSerializedMemories yet. Wait for success or it crashes.
  PxCollection* collection = PxSerialization::createCollectionFromBinary(
    alignedMemory, *mSerializationRegistry);

  if (!collection)
  {
    // deserialization failed, cleanup and return
    free(rawMemory);
    return false;
  }

  // 3. Success: Keep memory alive
  mSerializedMemories.push_back(rawMemory);

  // 4. Complete the collection (resolves references)
  PxSerialization::complete(*collection, *mSerializationRegistry);

  // 5. Add to Scene
  if (!mScene)
    reset();

  if (mScene)
  {
    mScene->addCollection(*collection);
  }
  else
  {
    collection->release();
    return false;
  }

  // 6. Re-populate Handle Map
  PxU32 nbObjects = collection->getNbObjects();
  for (PxU32 i = 0; i < nbObjects; i++)
  {
    PxBase& obj = collection->getObject(i);

    // Check for actors
    const PxType type = obj.getConcreteType();
    if (type == PxConcreteType::eRIGID_DYNAMIC ||
      type == PxConcreteType::eRIGID_STATIC)
    {
      PxRigidActor* actor;
      actor = dynamic_cast<PxRigidActor*>(&obj);

      // Map pointer to handle
      auto handle = reinterpret_cast<uint64_t>(actor);
      mActorMap[handle] = actor;
    }
  }

  // Release the collection wrapper (objects stay in the scene)
  collection->release();
  return true;
}

// I/O

auto PhysXManager::saveCookedData(const std::string& path, py::bytes data) -> bool
{
  // Convert py::bytes to string
  std::string s_data = data;

  // Open file
  std::ofstream file(path, std::ios::binary);

  // Check if open failed
  if (!file.is_open())
  {
    printf("!! Failed to open file for writing: %s\n", path.c_str());
    return false;
  }

  // Write and close
  file.write(s_data.data(), s_data.size());
  file.close();
  return true;
}

auto PhysXManager::loadCookedData(const std::string& path) -> py::bytes
{
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file.is_open())
  {
    return py::bytes("");
  }

  std::streamsize size = file.tellg();
  file.seekg(0, std::ios::beg);

  if (size <= 0)
  {
    return py::bytes("");
  }

  std::vector<char> buffer(size);
  if (file.read(buffer.data(), size))
  {
    return py::bytes(buffer.data(), size);
  }

  return py::bytes("");
}

// bool PhysXManager::get_value(std::ofstream file, bool &value1) {
//     if (file.is_open()) return false;
//     value1 = false;
//     return true;
// }

// COOKING

py::bytes PhysXManager::cookMesh(std::string type, std::vector<float> verts,
                                 const std::vector<int>& indices, int vertLimit)
{
  if (!mCooking)
    return py::bytes("");
  PxDefaultMemoryOutputStream buf;
  if (type == "CONVEX")
  {
    PxConvexMeshDesc desc;
    desc.points.count = verts.size() / 3;
    desc.points.stride = sizeof(float) * 3;
    desc.points.data = verts.data();
    desc.flags = PxConvexFlag::eCOMPUTE_CONVEX;
    desc.vertexLimit = (PxU16)vertLimit;
    if (mCooking->cookConvexMesh(desc, buf))
      return py::bytes(reinterpret_cast<char*>(buf.getData()), buf.getSize());
  }
  else if (type == "TRIANGLE")
  {
    PxTriangleMeshDesc desc;
    desc.points.count = verts.size() / 3;
    desc.points.stride = sizeof(float) * 3;
    desc.points.data = verts.data();
    desc.triangles.count = indices.size() / 3;
    desc.triangles.stride = 3 * sizeof(PxU32);
    desc.triangles.data = indices.data();
    if (mCooking->cookTriangleMesh(desc, buf))
      return py::bytes((char*)buf.getData(), buf.getSize());
  }
  return py::bytes("");
}

auto PhysXManager::processHeightField(int rows, int cols,
                                      std::vector<float> heights) -> py::bytes
{
  if (heights.size() != rows * cols)
    return py::bytes("");
  float minH = 1e9f;
  float maxH = -1e9f;
  for (float h : heights)
  {
    if (h < minH)
      minH = h;
    if (h > maxH)
      maxH = h;
  }
  float delta = maxH - minH;
  if (delta < 0.0001f)
    delta = 1.0f;
  float heightScale = delta / 32767.0f;

  size_t headerSize = 16;
  size_t dataSize = rows * cols * sizeof(PxHeightFieldSample);
  std::vector<uint8_t> buffer(headerSize + dataSize);

  memcpy(&buffer[0], &rows, 4);
  memcpy(&buffer[4], &cols, 4);
  memcpy(&buffer[8], &minH, 4);
  memcpy(&buffer[12], &heightScale, 4);

  PxHeightFieldSample* samples = (PxHeightFieldSample*)&buffer[headerSize];
  for (size_t i = 0; i < heights.size(); i++)
  {
    int16_t q = (int16_t)((heights[i] - minH) / heightScale);
    samples[i].height = q;
    samples[i].materialIndex0 = PxBitAndByte(0);
    samples[i].materialIndex1 = PxBitAndByte(0);
    samples[i].clearTessFlag();
  }
  return py::bytes((char*)buffer.data(), buffer.size());
}

// GEOMETRY FACTORY

PxGeometryHolder PhysXManager::createGeometryHolder(
  const std::string& type, const std::string& data,
  const std::vector<float>& dims, std::vector<PxBase*>& outResources)
{
  if (type == "BOX")
    return PxGeometryHolder(PxBoxGeometry(dims[0], dims[1], dims[2]));
  if (type == "SPHERE")
    return PxGeometryHolder(PxSphereGeometry(dims[0]));
  if (type == "CAPSULE")
    return PxGeometryHolder(PxCapsuleGeometry(dims[0], dims[1]));

  if (!data.empty())
  {
    if (type == "CONVEX")
    {
      PxDefaultMemoryInputData input((PxU8*)data.data(), data.size());
      PxConvexMesh* mesh = mPhysics->createConvexMesh(input);
      if (mesh)
      {
        outResources.push_back(mesh);
        return PxGeometryHolder(PxConvexMeshGeometry(mesh));
      }
    }
    else if (type == "TRIANGLE")
    {
      PxDefaultMemoryInputData input((PxU8*)data.data(), data.size());
      PxTriangleMesh* mesh = mPhysics->createTriangleMesh(input);
      if (mesh)
      {
        outResources.push_back(mesh);
        return PxGeometryHolder(PxTriangleMeshGeometry(mesh));
      }
    }
    else if (type == "HEIGHTFIELD" && data.size() >= 16)
    {
      const char* buf = data.data();
      int rows = *(int*)&buf[0];
      int cols = *(int*)&buf[4];
      float hScale = *(float*)&buf[12];
      PxHeightFieldDesc desc;
      desc.nbRows = rows;
      desc.nbColumns = cols;
      desc.samples.data = (void*)&buf[16];
      desc.samples.stride = sizeof(PxHeightFieldSample);
      PxDefaultMemoryOutputStream cookBuf;
      if (mCooking->cookHeightField(desc, cookBuf))
      {
        PxDefaultMemoryInputData cookInput(cookBuf.getData(),
                                           cookBuf.getSize());
        if (PxHeightField* hf = mPhysics->createHeightField(cookInput))
        {
          outResources.push_back(hf);
          float rScale = (dims[0] * 2.0f) / (rows - 1);
          float cScale = (dims[1] * 2.0f) / (cols - 1);
          if (rScale < 0.001f)
            rScale = 1.0f;
          if (cScale < 0.001f)
            cScale = 1.0f;
          return PxGeometryHolder(PxHeightFieldGeometry(
            hf, PxMeshGeometryFlag::eDOUBLE_SIDED, hScale, rScale, cScale));
        }
      }
    }
  }
  return PxGeometryHolder(PxBoxGeometry(0.1f, 0.1f, 0.1f));
}

// ACTOR CREATION

uint64_t PhysXManager::createActor(std::string actorType,
                                   std::vector<float> actorPose,
                                   py::list shapeList, float mass,
                                   std::vector<float> massLocalPose,
                                   std::vector<float> inertia)
{
  if (!mScene)
    return 0;
  PxTransform tr(
    PxVec3(actorPose[0], actorPose[1], actorPose[2]),
    PxQuat(actorPose[3], actorPose[4], actorPose[5], actorPose[6]));

  PxRigidActor* actor = nullptr;
  if (actorType == "DYNAMIC" || actorType == "KINEMATIC")
  {
    PxRigidDynamic* dyn = mPhysics->createRigidDynamic(tr);
    if (actorType == "KINEMATIC")
      dyn->setRigidBodyFlag(PxRigidBodyFlag::eKINEMATIC, true);
    actor = dyn;
  }
  else
  {
    actor = mPhysics->createRigidStatic(tr);
  }
  if (!actor)
    return 0;

  std::vector<PxBase*> tempResources;
  try
  {
    for (auto item : shapeList)
    {
      py::dict sDef = item.cast<py::dict>();
      std::string sType = sDef["type"].cast<std::string>();
      std::string sData = sDef["data"].cast<std::string>();
      auto sDims = sDef["dims"].cast<std::vector<float>>();
      auto sPos = sDef["pos"].cast<std::vector<float>>();
      auto sRot = sDef["rot"].cast<std::vector<float>>();
      auto sMat = sDef["mat"].cast<std::vector<float>>();

      PxMaterial* mat = mPhysics->createMaterial(sMat[0], sMat[1], sMat[2]);
      if (!mat)
        mat = mMaterial;

      PxGeometryHolder geom =
        createGeometryHolder(sType, sData, sDims, tempResources);
      PxShape* shape =
        PxRigidActorExt::createExclusiveShape(*actor, geom.any(), *mat);

      if (shape)
      {
        PxTransform localTr(PxVec3(sPos[0], sPos[1], sPos[2]),
                            PxQuat(sRot[0], sRot[1], sRot[2], sRot[3]));
        shape->setLocalPose(localTr);

        // APPLY FILTER DATA
        if (sDef.contains("filter"))
        {
          auto sFilter = sDef["filter"].cast<std::vector<int>>();
          PxFilterData fd;
          fd.word0 = sFilter[0]; // Group
          fd.word1 = sFilter[1]; // Mask
          fd.word2 = sFilter[2]; // Query Flag
          fd.word3 = sFilter[3]; // Reserved
          shape->setSimulationFilterData(fd);
          shape->setQueryFilterData(fd);
        }
      }
      if (mat != mMaterial)
        mat->release();
    }
  }
  catch (...)
  {
  }

  for (auto* res : tempResources)
    res->release();

  if (actorType == "DYNAMIC")
  {
    PxRigidDynamic* dyn;
    dyn = static_cast<PxRigidDynamic*>(actor);

    if (dyn->getNbShapes() > 0)
    {
      PxRigidBodyExt::updateMassAndInertia(*dyn, 1.0f);
      if (mass > 0.001f)
        dyn->setMass(mass);
    }
    else
    {
      dyn->setMass(mass > 0 ? mass : 1.0f);
      dyn->setMassSpaceInertiaTensor(PxVec3(1.0f, 1.0f, 1.0f));
    }

    if (massLocalPose.size() >= 3)
      dyn->setCMassLocalPose(PxTransform(
        PxVec3(massLocalPose[0], massLocalPose[1], massLocalPose[2])));
    if (inertia.size() >= 3 && inertia[0] > 0)
      dyn->setMassSpaceInertiaTensor(
        PxVec3(inertia[0], inertia[1], inertia[2]));

    if (dyn->getMass() < 0.0001f)
      dyn->setMass(1.0f);
  }

  mScene->addActor(*actor);

  uint64_t handle = reinterpret_cast<uint64_t>(actor);
  mActorMap[handle] = actor;
  return handle;
}

void PhysXManager::removeActor(uint64_t handle)
{
  auto it = mActorMap.find(handle);
  if (it != mActorMap.end())
  {
    mScene->removeActor(*it->second);
    it->second->release();
    mActorMap.erase(it);
  }
}

// DYNAMICS & RUNTIME

py::dict PhysXManager::computeMassProperties(py::list shapeList,
                                             std::vector<float> densities)
{
  if (!mPhysics)
    return py::dict();
  PxRigidDynamic* dummy = mPhysics->createRigidDynamic(PxTransform(PxIdentity));
  std::vector<PxBase*> tempResources;
  try
  {
    for (auto item : shapeList)
    {
      auto sDef = item.cast<py::dict>();
      auto sType = sDef["type"].cast<std::string>();
      auto sData = sDef["data"].cast<std::string>();
      auto sDims = sDef["dims"].cast<std::vector<float>>();
      auto sPos = sDef["pos"].cast<std::vector<float>>();
      auto sRot = sDef["rot"].cast<std::vector<float>>();
      PxGeometryHolder geom =
        createGeometryHolder(sType, sData, sDims, tempResources);
      if (PxShape* shape = PxRigidActorExt::createExclusiveShape(
        *dummy, geom.any(), *mMaterial))
      {
        PxTransform localTr(PxVec3(sPos[0], sPos[1], sPos[2]),
                            PxQuat(sRot[0], sRot[1], sRot[2], sRot[3]));
        shape->setLocalPose(localTr);
      }
    }

    if (densities.size() != dummy->getNbShapes())
      densities.resize(dummy->getNbShapes(), 1000.0f);
    PxRigidBodyExt::updateMassAndInertia(*dummy, densities.data(),
                                         densities.size());

    float mass = dummy->getMass();
    PxVec3 com = dummy->getCMassLocalPose().p;
    PxVec3 inert = dummy->getMassSpaceInertiaTensor();
    dummy->release();
    for (auto* res : tempResources)
      res->release();
    return py::dict(
      "mass"_a = mass, "com"_a = std::vector<float>{com.x, com.y, com.z},
      "inertia"_a = std::vector<float>{inert.x, inert.y, inert.z});
  }
  catch (...)
  {
    if (dummy)
      dummy->release();
    for (auto* res : tempResources)
      res->release();
    return py::dict();
  }
}

void PhysXManager::applyForce(uint64_t handle, std::vector<float> force,
                              int mode, bool usePos,
                              const std::vector<float>& pos)
{
  if (!mScene)
    return;
  auto it = mActorMap.find(handle);
  if (it == mActorMap.end())
    return;
  if (it->second->getType() == PxActorType::eRIGID_DYNAMIC)
  {
    PxRigidDynamic* dyn = static_cast<PxRigidDynamic*>(it->second);
    PxVec3 f(force[0], force[1], force[2]);
    if (usePos && pos.size() >= 3)
    {
      PxRigidBodyExt::addForceAtPos(*dyn, f, PxVec3(pos[0], pos[1], pos[2]),
                                    PxForceMode::Enum(mode), true);
    }
    else
    {
      dyn->addForce(f, static_cast<PxForceMode::Enum>(mode), true);
    }
  }
}

void PhysXManager::startStep(float dt)
{
  if (mScene)
    mScene->simulate(dt);
}

bool PhysXManager::fetchResults(bool block)
{
  if (mScene)
    return mScene->fetchResults(block);
  return false;
}

auto PhysXManager::getActivePoses() -> py::dict
{
  py::dict results;
  if (!mScene)
    return results;
  uint32_t count = 0;
  PxActor** actors = mScene->getActiveActors(count);
  for (uint32_t i = 0; i < count; i++)
  {
    if (actors[i]->getType() == PxActorType::eRIGID_DYNAMIC)
    {
      PxRigidActor* rigid = static_cast<PxRigidActor*>(actors[i]);
      PxTransform t = rigid->getGlobalPose();
      uint64_t handle = reinterpret_cast<uint64_t>(rigid);
      std::vector<float> p = {t.p.x, t.p.y, t.p.z, t.q.x, t.q.y, t.q.z, t.q.w};
      results[std::to_string(handle).c_str()] = p;
    }
  }
  return results;
}

py::dict PhysXManager::getCookedGeometry(const std::string& type,
                                         std::string data) const
{
  if (data.empty() || !mPhysics)
    return py::dict();
  PxDefaultMemoryInputData input(reinterpret_cast<PxU8*>(data.data()),
                                 data.size());
  std::vector<float> out_verts;
  std::vector<int> out_indices;
  if (type == "CONVEX")
  {
    if (PxConvexMesh* mesh = mPhysics->createConvexMesh(input))
    {
      const PxVec3* verts = mesh->getVertices();
      for (PxU32 i = 0; i < mesh->getNbVertices(); i++)
      {
        out_verts.push_back(verts[i].x);
        out_verts.push_back(verts[i].y);
        out_verts.push_back(verts[i].z);
      }
      const PxU8* idxBuffer = mesh->getIndexBuffer();
      for (PxU32 i = 0; i < mesh->getNbPolygons(); i++)
      {
        PxHullPolygon poly;
        mesh->getPolygonData(i, poly);
        for (PxU32 j = 1; j < poly.mNbVerts - 1; j++)
        {
          out_indices.push_back(idxBuffer[poly.mIndexBase]);
          out_indices.push_back(idxBuffer[poly.mIndexBase + j]);
          out_indices.push_back(idxBuffer[poly.mIndexBase + j + 1]);
        }
      }
      mesh->release();
    }
  }
  return py::dict("vertices"_a = out_verts, "indices"_a = out_indices);
}

py::bytes PhysXManager::cookHeightFieldFromMesh(
  int rows, int cols, std::vector<float> startPos, std::vector<float> step,
  std::vector<float> meshVerts, std::vector<int> meshIndices,
  std::vector<float> meshTransform)
{
  if (!mCooking || !mPhysics)
    return py::bytes("");

  // 1. Cook Temporary BVH for the source mesh
  PxTriangleMeshDesc meshDesc;
  meshDesc.points.count = meshVerts.size() / 3;
  meshDesc.points.stride = sizeof(float) * 3;
  meshDesc.points.data = meshVerts.data();
  meshDesc.triangles.count = meshIndices.size() / 3;
  meshDesc.triangles.stride = 3 * sizeof(int);
  meshDesc.triangles.data = meshIndices.data();

  PxDefaultMemoryOutputStream meshCookBuf;
  if (!mCooking->cookTriangleMesh(meshDesc, meshCookBuf))
    return py::bytes("");

  PxDefaultMemoryInputData meshInput(meshCookBuf.getData(),
                                     meshCookBuf.getSize());
  PxTriangleMesh* triMesh = mPhysics->createTriangleMesh(meshInput);
  if (!triMesh)
    return py::bytes("");

  // 2. Prepare Raycasting
  PxTriangleMeshGeometry targetGeom(triMesh);

  // Construct Transform from passed [px,py,pz, qx,qy,qz,qw]
  PxTransform targetPose(PxIdentity);
  if (meshTransform.size() >= 7)
  {
    targetPose = PxTransform(
      PxVec3(meshTransform[0], meshTransform[1], meshTransform[2]),
      PxQuat(meshTransform[3], meshTransform[4], meshTransform[5],
             meshTransform[6]));
  }

  std::vector<float> heights;
  heights.reserve(rows * cols);

  // 3. Raycast Loop
  for (int r = 0; r < rows; r++)
  {
    for (int c = 0; c < cols; c++)
    {
      float x = startPos[0] + (c * step[0]);
      float y = startPos[1] + (r * step[1]);
      // Start high up and cast down
      PxVec3 origin(x, y, startPos[2] + 1000.0f);
      PxVec3 dir(0, 0, -1);
      PxRaycastHit hit;

      bool hitRes =
        PxGeometryQuery::raycast(origin, dir, targetGeom, targetPose, 2000.0f,
                                 PxHitFlag::eDEFAULT, 1, &hit);

      if (hitRes)
      {
        heights.push_back(hit.position.z);
      }
      else
      {
        heights.push_back(startPos[2]); // Miss = Floor
      }
    }
  }

  // 4. Cleanup
  triMesh->release();

  // 5. Delegate to cooker
  return processHeightField(rows, cols, heights);
}

// Stubs
void PhysXManager::setupVehicleBuffers()
{
}

auto PhysXManager::cleanupVehicle() -> void
{
}

void PhysXManager::buildVehicle(py::dict params)
{
}

void PhysXManager::updateInputs(float t, float b, float s, float h, float dt)
{
}

py::dict PhysXManager::getStats() { return py::dict(); }

// BINDING

PhysXManager& getManager()
{
  static PhysXManager instance;
  return instance;
}

PYBIND11_MODULE(pxveh34, m)
{
  m.def("init", []() { return getManager().init(); });
  m.def("shutdown", []() { getManager().shutdown(); });
  m.def("reset", []() { getManager().reset(); });
  m.def("set_gravity",
        [](float x, float y, float z) { getManager().setGravity(x, y, z); });

  m.def("cook_mesh", [](std::string t, std::vector<float> v, std::vector<int> i,
                        int l)
  {
    return getManager().cookMesh(t, v, i, l);
  });
  m.def("process_heightfield", [](int r, int c, std::vector<float> h)
  {
    return getManager().processHeightField(r, c, h);
  });
  m.def("get_cooked_geometry", [](std::string t, std::string d)
  {
    return getManager().getCookedGeometry(t, d);
  });

  m.def("cook_hf_from_mesh", [](int r, int c, std::vector<float> start,
                                std::vector<float> step, std::vector<float> v,
                                std::vector<int> i, std::vector<float> t)
  {
    return getManager().cookHeightFieldFromMesh(r, c, start, step, v, i, t);
  });

  m.def("save_cooked_data", [](std::string p, const py::bytes& d)
  {
    return getManager().saveCookedData(p, d);
  });
  m.def("load_cooked_data",
        [](std::string p) { return getManager().loadCookedData(p); });
  m.def("export_scene",
        [](std::string p) { return getManager().exportScene(p); });
  m.def("import_scene",
        [](const std::string& p) { return getManager().importScene(p); });

  m.def("create_actor",
        [](const std::string& type, const std::vector<float>& ap,
           py::list shapes, float mass, std::vector<float> com,
           std::vector<float> inert)
        {
          return getManager().createActor(type, ap, shapes, mass, com, inert);
        });

  m.def("remove_actor",
        [](uint64_t handle) { getManager().removeActor(handle); });
  m.def("apply_force",
        [](uint64_t handle, const std::vector<float>& f, int mode, bool usePos,
           const std::vector<float>& pos)
        {
          getManager().applyForce(handle, f, mode, usePos, pos);
        });

  m.def("start_step", [](float dt) { getManager().startStep(dt); });
  m.def("fetch_results",
        [](bool block) { return getManager().fetchResults(block); });
  m.def("get_active_poses", []() { return getManager().getActivePoses(); });

  m.def("compute_mass_props",
        [](const py::list& shapes, const std::vector<float>& densities)
        {
          return getManager().computeMassProperties(shapes, densities);
        });

  m.def("is_initialized", []() { return getManager().isInitialized(); });
  m.def("get_actor_count", []() { return getManager().getActorCount(); });

  m.def("build_vehicle", [](py::dict p)
  {
  });
  m.def("update_inputs", [](float t, float b, float s, float h, float dt)
  {
  });
  m.def("get_stats", []() { return py::dict(); });
}
