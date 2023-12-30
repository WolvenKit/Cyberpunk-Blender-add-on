import bpy
import re

wolvenkit_project = "apartment_dogtown_cleaned_up"
mod_directory = "C:\\Games\\Cyberpunk 2077\\archive\\pc\\mod\\"
project_directory = "F:\\CyberpunkFiles\\world_editing\\"

export_to_mod_dir = True
consider_partial_deletions = True

# Specify the filename where you want to save the output. Make sure to use an existing folder!
output_filename = f"{project_directory}\\{wolvenkit_project}\\source\\resources\\{wolvenkit_project}.archive.xl"

if export_to_mod_dir:
    output_filename = f"{mod_directory}\\{wolvenkit_project}.archive.xl"

# if an item matches all strings in one of the sub-arrays, delete it
delete_partials = [
    [ "soda_can" ],
    [ "squat_clothes" ],
    [ "takeout_cup" ],
    [ "trash" ],
]

# if an item matches all strings in one of the sub-arrays, keep it. Supports regular expression.
keep_partials = [ 
    [ "^q\d\d" ],
    # ["entropy_lamp.*"]
]


# For indenting your .xl file
indent="  "

# --------------------------- DO NOT EDIT BELOW THIS LINE -------------------------------------

deletions = {}
expectedNodes = {}

# function to recursively count nested collections
def countChildNodes(collection):
    if 'expectedNodes' in collection:
        numChildNodes = collection['expectedNodes']
        return numChildNodes


# Compile regular expressions for keep_partials
compiled_partials = [[re.compile(p) for p in partials] for partials in keep_partials]

# Function to find collections without children (these contain deletions)
def find_empty_collections(collection):
    empty_collections = []
    is_deletion_candidate = 'nodeIndex' in collection and 'nodeType' in collection

    # check if we want to keep this collection
    for keep_check in compiled_partials:
        if all(p.search(collection.name) for p in keep_check):
            return empty_collections

    if len(collection.children) == 0 and is_deletion_candidate:
        if len(collection.objects) == 0:
            empty_collections.append(collection)
        if consider_partial_deletions and len(collection.children) > 0 and not collection.children[0]["Name"].startswith("submesh_00"):
            empty_collections.append(collection)
    elif is_deletion_candidate:
        for deletion_check in delete_partials:
            if all(partial in collection.name for partial in deletion_check):
                empty_collections.append(collection)
        
    for child_collection in collection.children:
        empty_collections.extend(find_empty_collections(child_collection))        

    return empty_collections


# Function to write to a text file
def to_archive_xl(filename):
    with open(filename, "w") as file:
        file.write("streaming:\n")
        file.write(f"{indent}sectors:\n")
        for sectorPath in deletions:
            deletedNodes = []
            file.write(f"{indent}{indent}- path: {sectorPath}\n")
            file.write(f"{indent}{indent}{indent}expectedNodes: {expectedNodes[sectorPath]}\n")
            file.write(f"{indent}{indent}{indent}nodeDeletions:\n")
            sectorData = deletions[sectorPath]

            currentNodeIndex = -1
            currentNodeComment = ''
            currentNodeType = ''
            for empty_collection in sectorData:
                if empty_collection['nodeIndex'] > currentNodeIndex:
                    # new node! write the old one                    
                    file.write(f"{indent}{indent}{indent}{indent}# {currentNodeComment}\n")
                    file.write(f"{indent}{indent}{indent}{indent}- index: {currentNodeIndex}\n")
                    file.write(f"{indent}{indent}{indent}{indent}{indent}type: {currentNodeType}\n")
                    
                    # set instance variables
                    currentNodeIndex = empty_collection['nodeIndex']
                    currentNodeComment = empty_collection.name
                    currentNodeType = empty_collection['nodeType']
                elif empty_collection['nodeIndex'] == currentNodeIndex:
                    currentNodeComment = f"{currentNodeComment}, {empty_collection.name}"


# Iterate over matching collections and find empty ones
for sectorCollection in [c for c in bpy.data.collections if c.name.endswith("streamingsector")]:
    prefix, file_path = sectorCollection["filepath"].split('raw\\')
    file_path = file_path.replace(".json", "")
    expectedNodes[file_path] = countChildNodes(sectorCollection)
    collections = find_empty_collections(sectorCollection)
    if len(collections) > 0:
        deletions[file_path] = collections

to_archive_xl(output_filename)
