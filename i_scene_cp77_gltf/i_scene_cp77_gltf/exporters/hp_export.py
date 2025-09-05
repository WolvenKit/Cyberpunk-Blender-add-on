import bpy
import os
import json

def cp77_hp_export(filepath):

    script_directory = os.path.dirname(os.path.abspath(__file__))
    template_relative_path = os.path.join('..', 'resources', 'hair_profile_template.hp.json')

    # Get the absolute path to the template file
    template_hp_file = os.path.normpath(os.path.join(script_directory, template_relative_path))

    obj = bpy.context.selected_objects[0]

    # Detect the active material slot
    active_slot = obj.active_material_index

    if active_slot is None:
        print("No active material")
        
    else:
        mat = obj.active_material
        ProjPath=mat.get('ProjPath')
        hair=[]
        if mat.get('MaterialTemplate') =="base\materials\hair.mt":
            hair=mat.get('MaterialTemplate')
        if not hair:
            print("Active Material is not a Hair Profile")
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Active Material is not a Hair Profile")
            return {'CANCELLED'}
        else:
            # Load the template hair profile JSON
            with open(template_hp_file, 'r') as template_f:
                j = json.load(template_f)

            crs = ['Color Ramp', 'Color Ramp.001']

            nodes = mat.node_tree.nodes
            print(' ')
            print('Gradient Stops for', mat.name)

            for crname in crs:
                cr = nodes.get(crname)
                if cr:
                    print(' ')
                    print('Stop info for', cr.label)
                    grad = ''
                    if cr.label == 'GradientEntriesRootToTip':
                        grad = 'gradientEntriesRootToTip'
                    elif cr.label == 'GradientEntriesID':
                        grad = 'gradientEntriesID'

                    j_data = j['Data']['RootChunk'][grad]
                    elements = list(cr.color_ramp.elements)
                    elements.reverse()

                    for i, stop in enumerate(elements):
                        print('Stop #', i)
                        print('Position -', stop.position)
                        print('Color -', int(stop.color[0] * 255), int(stop.color[1] * 255), int(stop.color[2] * 255))
                        print(' ')

                        # Create a new entry for each stop
                        new_entry = {
                            "$type": "rendGradientEntry",
                            "color": {
                                "$type": "Color",
                                "Alpha": int(stop.color[3] * 255),
                                "Blue": int(stop.color[2] * 255),
                                "Green": int(stop.color[1] * 255),
                                "Red": int(stop.color[0] * 255),
                            },
                            "value": stop.position,
                        }

                        j_data.append(new_entry)

            mat_name = mat.name.replace("_cards", "")

            # Construct the output path
            outpath = os.path.join(ProjPath,'base\\characters\\common\\hair\\textures\\hair_profiles\\' f'mod_{mat_name}.hp.json')

            if not os.path.exists(os.path.dirname(outpath)):
                os.makedirs(os.path.dirname(outpath))

            # Save the updated JSON to the specified output path
            with open(outpath, 'w') as outfile:
                json.dump(j, outfile, indent=2)
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="mod_" + (mat_name) + ".hp Exported Succesfully")