## Top level Structure

| Module | Purpose |
|---|---|
| `__init__.py` | Add-on entry point and registration of every package |
| `cyber_props.py` | The CP77 Modding panel's shared properties and the Cycles and Vulkan switches |
| **animation** | Animation without Blender UI: AnimGraph model and runtime, clips, rigs, dangles, facial and JALI lip sync, mocap retargeting |
| **animtools** | rigs, poses, clips, AnimGraph editing, facial and Rigify |
| **assetio** | Asset IO, depot and project paths, document reading and writing, WolvenKit values, TweakDB, ArchiveXL and streaming documents |
| **bartmoss** | Shared math, matrices, quaternions, geometry, transforms, vehicle and camera dynamics |
| **blender** | Blender adapters: node trees, objects, armatures, poses, keyframes, transactions and previews |
| **collisiontools** | PhysX actors, the dangle physics editor, vehicle authoring and preview |
| **core** | main plumbing, add-on identity, logging, notifications, preferences and registration |
| **entity** | Entity and appearance documents, components, edits, lights and light zones |
| **enttools** | tools for editing imported entities and exporting them |
| **exporters** | Exporters for meshes, animations, rigs, AnimGraphs, materials, collisions and sectors |
| **gltf** | The GLB container and the glTF contract import and export share |
| **icons** | The add-on's UI icons |
| **importers** | Importers for meshes, entities, sectors, rigs, animations, AnimGraphs, characters, materials and collisions |
| **ink** | Ink widget libraries without Blender. layout, animation, rasterizing and write-back |
| **inktools** | widget screens in the scene and their editing handles |
| **material_types** | One shader graph builder per game material template |
| **materials** | Material resolution and building, parsing, repository, caches and images |
| **materialtools** | multilayer authoring, mask painting and material export |
| **meshes** | Mesh resource model and repository |
| **meshtools** | refit, weight transfer, shape keys, presets and base characters |
| **physics** | Physics without Blender UI: shapes, filters, vehicle game data and the PhysX bridge |
| **redSpace** | axis and space conversions between the game and Blender |
| **resources** | Bundled rigs, characters, material defaults, refitters, scripts, workspaces and NLTK data |
| **scenetools** | lights, sectors, world, sky, fog and weather previews |
| **scriptman** | Script Manager for user scripts |
| **wheels** | Bundled Python wheels for JALI lip sync |

## Component responsibilities

| Component | Responsibility | Should contain | Must not contain | Dependencies |
|---|---|---|---|---|
| **UI** | Presentation and user interaction | Panels, layouts, controls, property display, status indicators | Business logic, asset processing, calculations, simulation | Operators, properties, read-only runtime state |
| **Operators** | Entry points for user actions | `poll()`, `invoke()`, `execute()`, input validation, context management, undo integration, result reporting | Complex processing, duplicated algorithms, persistent simulation state | Services, Blender API |
| **Services** | Coordinate application workflows | Operation sequencing, preparation, resource coordination, transaction management, error handling | UI layout, duplicated domain logic, unnecessary persistent state | Handlers, runtime, domain, models, shared infrastructure |
| **Handlers** | Process specific types or events | Entity component processing, sector node dispatch, specialized event handling | Entire workflows, UI logic, unrelated processing, duplicated services | Services, domain, models, Blender adapters |
| **Runtime** | Manage active, stateful execution | Simulation sessions, animation evaluation, frame updates, state buffers, caches, lifecycle management | UI presentation, asset parsing, duplicated mathematical algorithms | Domain, models, execution backends |
| **Model** | Define structured data and contracts | Dataclasses, typed records, enums, schemas, immutable representations, structural validation | Blender object creation, workflow orchestration, simulation execution, file I/O | Standard library, neutral data types |
| **Domain** | Implement authoritative rules and algorithms | Transform mathematics, rig relationships, animation blending, geometry algorithms, physics calculations, semantic validation | UI logic, Blender context management, file dialogs, workflow coordination | Models, mathematical libraries |

## Architectural rules

| Rule | Requirement |
|---|---|
| **Single ownership** | Every algorithm, representation and operation has one authoritative implementation. |
| **Dependency direction** | Higher-level components depend on lower-level functionality. Avoid circular dependencies and reverse imports. |
| **UI separation** | UI presents functionality; it does not implement functionality. |
| **Thin operators** | Operators delegate processing to services and manage Blender-specific interaction. |
| **Service orchestration** | Services coordinate operations rather than reimplement algorithms or type-specific handlers. |
| **Handler isolation** | Handlers process one defined asset type or event. Blender event callbacks should delegate substantive work. |
| **Runtime isolation** | Runtime owns active state and repeated evaluation, not UI or asset-loading workflows. |
| **Model neutrality** | Core models remain independent of `bpy` and Blender scene state. |
| **Domain neutrality** | Domain algorithms should be reusable without Blender wherever practical. |
| **Shared infrastructure** | Use `assetio` for asset resolution, `bartmoss` for shared mathematics, `redSpace` for REDengine spatial semantics, and established Blender adapters for scene operations. |
| **Transactions** | Failed operations must restore prior state and remove partial changes. |
| **No compatibility facades** | Remove obsolete aliases, wrappers and duplicate implementations rather than maintaining competing code paths. |
| **Performance** | Avoid `bpy.ops` in hot loops, repeated parsing, linear lookups, redundant dependency-graph updates and unnecessary allocations. |
| **Logging** | Use centralized logging with appropriate levels, meaningful context and complete exception tracebacks. |
| **Production stability** | Preserve existing behaviour, asset fidelity, transforms, animation keys and data contracts unless changes are explicitly required. |

## Typical execution flow

| Order | Component | Role in execution |
|---|---|---|
| 1 | **UI** | Collects and presents user settings |
| 2 | **Operator** | Initiates the requested action |
| 3 | **Service** | Plans and coordinates the operation |
| 4 | **Handler** | Processes specialized asset types or events, when necessary |
| 5 | **Domain** | Performs authoritative calculations and applies semantic rules |
| 6 | **Model** | Represents data exchanged throughout processing |
| 7 | **Runtime** | Maintains ongoing execution when the operation requires it |
| 8 | **Service / Operator / UI** | Finalizes the operation and reports results |
