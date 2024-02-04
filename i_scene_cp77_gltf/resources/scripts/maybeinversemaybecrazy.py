import json
from mathutils import Matrix
import bpy

############ path to your .mesh.json here \\ not \ ##############
input = "M:\\t0_000_ma_base__full_hql.mesh.json"

############## path to the new file we're making #########
output = "M:\\outputmatrices.json"


# Load the JSON data
with open(input, "r") as json_file:
    data = json.load(json_file)

# Extract boneRigMatrices data
bone_matrices_data = data["Data"]["RootChunk"]["boneRigMatrices"]

# Initialize a list to store the results
results = []

# Process each matrix in boneRigMatrices
for index, matrix_data in enumerate(bone_matrices_data):
    input_matrix = Matrix()

    # Extract the values from the JSON data and populate the matrix
    input_matrix[0][0] = matrix_data["W"]["X"]
    input_matrix[0][1] = matrix_data["W"]["Y"]
    input_matrix[0][2] = matrix_data["W"]["Z"]
    input_matrix[0][3] = matrix_data["W"]["W"]

    input_matrix[1][0] = matrix_data["X"]["X"]
    input_matrix[1][1] = matrix_data["X"]["Y"]
    input_matrix[1][2] = matrix_data["X"]["Z"]
    input_matrix[1][3] = matrix_data["X"]["W"]

    input_matrix[2][0] = matrix_data["Y"]["X"]
    input_matrix[2][1] = matrix_data["Y"]["Y"]
    input_matrix[2][2] = matrix_data["Y"]["Z"]
    input_matrix[2][3] = matrix_data["Y"]["W"]

    input_matrix[3][0] = matrix_data["Z"]["X"]
    input_matrix[3][1] = matrix_data["Z"]["Y"]
    input_matrix[3][2] = matrix_data["Z"]["Z"]
    input_matrix[3][3] = matrix_data["Z"]["W"]

    for row_idx, row in enumerate(["W", "X", "Y", "Z"]):
        for col_idx, col in enumerate(["W", "X", "Y", "Z"]):
            input_matrix[row_idx][col_idx] = matrix_data[row][col]

    # Calculate the inverse of the matrix
    inverse_matrix = input_matrix.inverted()

    # Extract translation values from the last column of the inverse matrix
    translation = inverse_matrix.translation

    # Create a dictionary for the formatted result
    result = {
        str(index): {
            "w": [inverse_matrix[0][0], inverse_matrix[0][1], inverse_matrix[0][2], inverse_matrix[0][3]],
            "x": [inverse_matrix[1][0], inverse_matrix[1][1], inverse_matrix[1][2], inverse_matrix[1][3]],
            "y": [inverse_matrix[2][0], inverse_matrix[2][1], inverse_matrix[2][2], inverse_matrix[2][3]],
            "z": [inverse_matrix[3][0], inverse_matrix[3][1], inverse_matrix[3][2], inverse_matrix[3][3]],
        },
        "Translation Values (XYZ)": {"X": translation.x, "Y": translation.y, "Z": translation.z},
    }

    results.append(result)

# Dump the results to a new JSON file
with open(output, "w") as output_file:
    json.dump(results, output_file, indent=4)

print("Results have been stored in", output)
