import bpy 
import os
from .common import get_script_dir

script_dir = get_script_dir()

def newScript(self,context):
    base_name = "new_script"
    script_name = base_name + ".py"

    # Check if a script with the default name already exists
    i = 1
    while os.path.exists(os.path.join(script_dir, script_name)):
        script_name = f"{base_name}_{i}.py"
        i += 1

    script_path = os.path.join(script_dir, script_name)

    with open(script_path, 'w') as f:
        f.write("# New Script")

    return {'FINISHED'}
        

def loadScript(self,context):
    if self.new_name:
    # Rename the script
        name = (self.new_name + ".py")
        script_path = os.path.join(script_dir, self.script_file)
        new_script_path = os.path.join(script_dir, name)

        if os.path.exists(script_path):
            if not os.path.exists(new_script_path):
                os.rename(script_path, new_script_path)
                self.report({'INFO'}, f"Renamed '{script_name}' to '{name}'")
            else:
                self.report({'ERROR'}, f"A script with the name '{name}' already exists.")
    else:
        # Check if the script is already loaded
        script_text = bpy.data.texts.get(script_name)
        # Switch to the loaded script if present
        if script_text is not None:
            context.space_data.text = script_text  
        else:
            # If the script is not loaded, load it
            script_path = os.path.join(script_dir, script_name)

            if os.path.exists(script_path):
                with open(script_path, 'r') as f:
                    text_data = bpy.data.texts.new(name=script_name)
                    text_data.from_string(f.read())
                    # Set the loaded script as active
                    context.space_data.text = text_data  


def saveScript(self, context):
    script_text = context.space_data.text
    if script_text:
        script_path = os.path.join(script_dir, self.script_file)
        with open(script_path, 'w') as f:
            f.write(script_text.as_string())
