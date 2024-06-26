import bpy
import os
import sys
from ..main.common import get_script_dir
from bpy.props import StringProperty
from bpy.types import Operator
from .scriptman_funcs import *
from ..main.common import get_classes


script_dir= get_script_dir()


class CP77CreateScript(Operator):
    '''Operator to add a new blank .py file to the scripts directory'''
    bl_idname = "script_manager.create_script"
    bl_label = "Create New Script"
    bl_description = "Create a new script in the CP77 modding scripts directory"

    script_name: bpy.props.StringProperty(name="Script Name", default="new_script")

    def execute(self, context):
        base_name = self.script_name
        script_name = base_name + ".py"
        i = 1
        
        while os.path.exists(os.path.join(script_dir, script_name)):
            script_name = f"{base_name}_{i}.py"
            i += 1

        with open(os.path.join(script_dir, script_name), 'w') as f:
            f.write("# New Script")

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
        

class CP77LoadScript(Operator):
    bl_idname = "script_manager.load_script"
    bl_label = "Load Script"
    bl_description = "Click to load or switch to this script, ctrl+click to rename"
    
    script_file: StringProperty()
    new_name: StringProperty(name="New name", default=".py")

    def execute(self, context):
        script_name = self.script_file

        if self.new_name:
            # Rename the script
            script_path = os.path.join(script_dir, script_file)
            new_script_path = os.path.join(s, self.new_name)

            if os.path.exists(script_path):
                if not os.path.exists(new_script_path):
                    os.rename(script_path, new_script_path)
                    self.report({'INFO'}, f"Renamed '{script_name}' to '{self.new_name}'")
                else:
                    self.report({'ERROR'}, f"A script with the name '{self.new_name}' already exists.")
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
        
        return {'FINISHED'}

    def invoke(self, context, event):
        if event.ctrl:
            # Ctrl+Click to rename
            return context.window_manager.invoke_props_dialog(self)
        else:
            self.new_name = ""
            return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "new_name")


class CP77SaveScript(Operator):
    bl_idname = "script_manager.save_script"
    bl_label = "Save Script"
    bl_description = "Press to save this script"
    
    script_file: StringProperty()

    def execute(self, context):
        script_text = context.space_data.text
        if script_text:
            script_path = os.path.join(script_dir, self.script_file)
            with open(script_path, 'w') as f:
                f.write(script_text.as_string())

        return {'FINISHED'}


class CP77DeleteScript(Operator):
    bl_idname = "script_manager.delete_script"
    bl_label = "Delete Script"
    bl_description = "Press to delete this script"
    
    script_file: StringProperty()
    def execute(self, context):
        script_path = os.path.join(script_dir, self.script_file)

        if os.path.exists(script_path):
            os.remove(script_path)

        return {'FINISHED'}
operators, other_classes = get_classes(sys.modules[__name__])

