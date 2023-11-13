import bpy 
import os

plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
script_dir = os.path.join(plugin_dir, "scripts")

class CP77ScriptManager(bpy.types.Panel):
    bl_label = "Script Manager"
    bl_idname = "CP77_PT_ScriptManagerPanel"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "CP77 Modding"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        # Get the path to the "scripts" folder in the add-on's root directory


        # List available scripts
        script_files = [f for f in os.listdir(script_dir)]

        
        for script_file in script_files:
            row = col.row(align=True)
            #row.operator("text.run_script", text="", icon='PLAY')
            row.operator("script_manager.load_script", text=script_file).script_file = script_file
            row.operator("script_manager.delete_script", text="", icon="X").script_file = script_file

        row = box.row(align=True)
        row.operator("script_manager.create_script", text="New Script")
        row = box.row(align=True)
        row.operator("script_manager.save_script", text="Save Script").script_file = script_file


class CP77CreateScript(bpy.types.Operator):
    bl_idname = "script_manager.create_script"
    bl_label = "Create New Script"
    bl_description = "create a new script in the cp77 modding scripts directory"

    def execute(self, context):
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
        

class CP77LoadScript(bpy.types.Operator):
    bl_idname = "script_manager.load_script"
    bl_label = "Load Script"
    bl_description = "Click to load or switch to this script, ctrl+click to rename"
    
    script_file: bpy.props.StringProperty()
    new_name: bpy.props.StringProperty(name="New name", default="")

    def execute(self, context):
        script_name = self.script_file

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


class CP77SaveScript(bpy.types.Operator):
    bl_idname = "script_manager.save_script"
    bl_label = "Save Script"
    bl_description = "Press to save this script"
    
    script_file: bpy.props.StringProperty()

    def execute(self, context):
        script_text = context.space_data.text
        if script_text:
            script_path = os.path.join(script_dir, self.script_file)
            with open(script_path, 'w') as f:
                f.write(script_text.as_string())

        return {'FINISHED'}


class CP77DeleteScript(bpy.types.Operator):
    bl_idname = "script_manager.delete_script"
    bl_label = "Delete Script"
    bl_description = "Press to delete this script"
    
    script_file: bpy.props.StringProperty()

    def execute(self, context):
        script_path = os.path.join(script_dir, self.script_file)

        if os.path.exists(script_path):
            os.remove(script_path)

        return {'FINISHED'}