import bpy
import re
import os
yamlavail=False
try:
    import yaml
    yamlavail=True
except:
    import json

wolvenkit_project = "archivexlupdate"
mod_directory = "D:\\GOGLibrary\\Cyberpunk 2077\\archive\\pc\\mod"
project_directory = "D:\\cpmod"

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
    if 'pillow' in collection.name:
        print(collection.name)
    # check if we want to keep this collection
#    for keep_check in compiled_partials:
 #       if all(p.search(collection.name) for p in keep_check):
  #          return empty_collections

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

def to_archive_xl(filename):
    xlfile={}
    xlfile['streaming']={'sectors':[]}
    sectors=xlfile['streaming']['sectors']
    for sectorPath in deletions:
        new_sector={}
        new_sector['path']=sectorPath
        new_sector['expectedNodes']=expectedNodes[sectorPath]
        new_sector['nodeDeletions']=[]
        sectorData = deletions[sectorPath]
        currentNodeIndex = -1
        currentNodeComment = ''
        currentNodeType = ''
        for empty_collection in sectorData:                           
            currentNodeIndex = empty_collection['nodeDataIndex']
            currentNodeComment = empty_collection.name
            currentNodeType = empty_collection['nodeType']    
            if currentNodeIndex>-1:         
                new_sector['nodeDeletions'].append({'index':currentNodeIndex,'type':currentNodeType,'debugName':currentNodeComment})
            # set instance variables
            
        sectors.append(new_sector)   
    with open(filename, "w") as file:
        if yamlavail:
            yaml.dump(xlfile, file, indent=4, sort_keys=False)
        else:
            json.dumps(xlfile, file, indent=4)

# Iterate over matching collections and find empty ones
for sectorCollection in [c for c in bpy.data.collections if c.name.endswith("streamingsector")]:    
    sectorName=os.path.basename(sectorCollection["filepath"])[:-5]
    expectedNodes[sectorName] = countChildNodes(sectorCollection)
    collections = find_empty_collections(sectorCollection)
    if len(collections) > 0:
        deletions[sectorName] = collections

to_archive_xl(output_filename)
