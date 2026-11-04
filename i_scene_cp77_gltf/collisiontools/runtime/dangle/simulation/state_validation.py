from __future__ import annotations


def missing_dangle_bindings(state, node_index, resolve_bone):
    """Return bindings that make one Dangle constraint a no-op"""
    nodes = tuple(getattr(state, "dangle_nodes", ()) or ())
    if not 0 <= int(node_index) < len(nodes):
        return ("<invalid dangle node>",)
    dnode = nodes[int(node_index)]
    missing = []
    seen = set()

    def require(name):
        value = str(name or "")
        resolved = resolve_bone(value) if value else None
        if value and resolved is None and value not in seen:
            seen.add(value)
            missing.append(value)
        return resolved

    particles = [
        particle
        for chain in getattr(dnode, "chains", ()) or ()
        for particle in getattr(chain, "particles", ()) or ()
    ]
    for particle in particles:
        name = str(getattr(particle, "bone_name", "") or "")
        pose_bone = require(name)
        if pose_bone is not None and getattr(pose_bone, "parent", None) is None:
            marker = f"{name}::<parent>"
            if marker not in seen:
                seen.add(marker)
                missing.append(marker)
        for constraint in getattr(particle, "link_constraints", ()) or ():
            require(getattr(constraint, "target_bone", ""))
        for constraint in getattr(particle, "ellipsoid_constraints", ()) or ():
            require(getattr(constraint, "target_bone", ""))
        for constraint in getattr(particle, "pendulum_constraints", ()) or ():
            require(getattr(constraint, "target_bone", ""))

    has_local_shapes = any(
        len(getattr(node, "collision_shapes", ()) or ()) > 0 for node in nodes
    )
    shapes = (
        getattr(dnode, "collision_shapes", ())
        if has_local_shapes
        else getattr(state, "collision_shapes", ())
    )
    for shape in shapes or ():
        require(getattr(shape, "bone_name", ""))
    return tuple(missing)


def require_local_particle_index(
    particle_node_indices,
    owner_index: int,
    target_index: int,
    bone_name: str,
) -> int:
    """Enforce node-local Dyng particle-container lookup"""
    owner_index = int(owner_index)
    target_index = int(target_index)
    target_node = (
        int(particle_node_indices[target_index])
        if 0 <= target_index < len(particle_node_indices)
        else -1
    )
    if target_node != int(particle_node_indices[owner_index]):
        raise ValueError(
            f"ellipsoid bone '{bone_name}' is outside its Dyng particle container"
        )
    return target_index


def state_configuration_errors(state, *, active_dangles=None):
    """Return editor states that cannot represent the simulation"""
    active = (
        set(range(len(getattr(state, "dangle_nodes", ()))))
        if active_dangles is None
        else set(active_dangles)
    )
    errors = []
    for node_index, dnode in enumerate(getattr(state, "dangle_nodes", ())):
        if node_index not in active:
            continue
        chains = tuple(getattr(dnode, "chains", ()) or ())
        if not chains:
            continue
        solvers = {str(getattr(chain, "solver", "DYNG") or "DYNG") for chain in chains}
        if len(solvers) != 1:
            errors.append(
                f"Dangle node {node_index + 1} mixes solver types: "
                + ", ".join(sorted(solvers))
            )
            continue
        solver = next(iter(solvers))
        particles = [
            particle for chain in chains for particle in getattr(chain, "particles", ())
        ]
        if solver in {"PBD", "SPRING", "PENDULUM"} and (
            len(chains) != 1 or len(particles) != 1
        ):
            errors.append(
                f"Dangle node {node_index + 1} uses {solver}, which requires "
                "exactly one chain with one particle"
            )
        names = [
            str(getattr(particle, "bone_name", "") or "") for particle in particles
        ]
        if any(not name for name in names):
            errors.append(f"Dangle node {node_index + 1} has an unnamed particle")
        seen = set()
        duplicates = []
        for name in names:
            if name and name in seen and name not in duplicates:
                duplicates.append(name)
            seen.add(name)
        if duplicates:
            errors.append(
                f"Dangle node {node_index + 1} assigns multiple particles to: "
                + ", ".join(duplicates)
            )
        if solver == "DYNG":
            particle_names = set(names)
            for particle in particles:
                owner = str(getattr(particle, "bone_name", "") or "")
                references = []
                references.extend(
                    ("link target", str(getattr(item, "target_bone", "") or ""))
                    for item in getattr(particle, "link_constraints", ())
                )
                references.extend(
                    ("ellipsoid bone", str(getattr(item, "target_bone", "") or ""))
                    for item in getattr(particle, "ellipsoid_constraints", ())
                )
                references.extend(
                    ("cone attachment", str(getattr(item, "target_bone", "") or ""))
                    for item in getattr(particle, "pendulum_constraints", ())
                )
                for role, target in references:
                    if target not in particle_names:
                        errors.append(
                            f"Dangle node {node_index + 1} particle {owner or '<unnamed>'} "
                            f"has {role} {target or '<empty>'} outside its Dyng particle container"
                        )
    return errors
