from __future__ import annotations

from ...bartmoss.matrix import flatten_matrix

COMPONENT_SPACE_MATRIX_KEY = "cp77_component_space_matrix"
RESOURCE_SPACE_MATRIX_KEY = "cp77_resource_space_matrix"


def store_mesh_placement(obj, component_matrix, resource_matrix):
    obj[COMPONENT_SPACE_MATRIX_KEY] = flatten_matrix(component_matrix).tolist()
    obj[RESOURCE_SPACE_MATRIX_KEY] = flatten_matrix(resource_matrix).tolist()
