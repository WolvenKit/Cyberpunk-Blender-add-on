import bpy

deletions = {}
expectedNodes = {}

indent="  "

# function to recursively count nested collections
def countChildNodes(collection):
    numChildNodes = len(coll.children_recursive)
    return numChildNodes

# Function to recursively find collections without children (these contain deletions)
def find_empty_collections(collection):
    coll = collection
    empty_collections =[col for col in coll.children_recursive if len(col.children) == 0 and len(col.objects) == 0 and 'nodeIndex' in col and 'nodeType' in col]
    return empty_collections

# Function to serialize to text file (OK, to console for now...)
def to_archive_xl():
    print("\n streaming:")
    print(f"{indent}sectors:")
    for sectorName in deletions:
        print(f"{indent}{indent}- path: base\worlds\\03_night_city\_compiled\default\{sectorName}")
        print(f"{indent}{indent}{indent}expectedNodes: {expectedNodes[sectorName]}")
        print(f"{indent}{indent}{indent}nodeDeletions:")
        sectorData = deletions[sectorName]

        for empty_collection in sectorData:
            print(f"{indent}{indent}{indent}{indent}# {empty_collection.name}")
            print(f"{indent}{indent}{indent}{indent}- index: {empty_collection['nodeIndex']}")
            print(f"{indent}{indent}{indent}{indent}{indent}type:  {empty_collection['nodeType']}")

# Iterate over matching collections and find empty ones
for sectorCollection in [c for c in bpy.data.collections if c.name.endswith("streamingsector")]:
    expectedNodes[sectorCollection.name] = countChildNodes(sectorCollection)
    if expectedNodes[sectorCollection.name] > 0:
        deletions[sectorCollection.name] = find_empty_collections(sectorCollection)

to_archive_xl()