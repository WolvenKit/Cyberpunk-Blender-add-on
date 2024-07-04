import bpy
from bpy.types import AddonPreferences
from bpy.props import (StringProperty, EnumProperty, BoolProperty, CollectionProperty)


class CP77IOSuitePreferences(AddonPreferences):

    bl_idname = __name__.split('.')[0]

    experimental_features: BoolProperty(
        name= "Enable Experimental Features",
        description="Experimental Features for Mod Developers, may encounter bugs",
        default=False,
    )

    # Define the depotfolder path property
    depotfolder_path: StringProperty(
        name="MaterialDepot Path",
        description="Path to the material depot folder",
        subtype='DIR_PATH',
        default="//MaterialDepot"
    )


# toggle the mod tools tab and its sub panels - default True
    show_modtools: BoolProperty(
        name= "Show Mod Tools",
        description="Show the Mod tools Tab in the 3d viewport",
        default=True,
    )

# only display the panels based on context
    context_only: BoolProperty(
        name= "Only Show Mod Tools in Context",
        description="Show the Mod tools Tab in the 3d viewport",
        default=False,
    )

    show_meshtools: BoolProperty(
        name= "Show the Mesh Tools Panel",
        description="Show the mesh tools panel",
        default=True,
    )

    show_collisiontools: BoolProperty(
        name= "Show the Collision Tools Panel",
        description="Show the Collision tools panel",
        default=True,
    )

    show_animtools: BoolProperty(
        name= "Show the Animation Tools Panel",
        description="Show the anim tools panel",
        default=True,
    )

    show_modtools: BoolProperty(
        name= "Show Mod Tools",
        description="Show the Mod tools Tab in the 3d viewport",
        default=True,
    )
    non_verbose: BoolProperty(
        name= "Turn off Verbose Logging",
        description="Turns off useful print statements to avoid clutter in the console",
        default=False,
    )

    def draw(self, context):           
        layout = self.layout
        box = layout.box()

        row = box.row()
        row.prop(self, "show_modtools",toggle=1) 
        row.prop(self, "experimental_features",toggle=1)
        row.prop(self, "non_verbose",toggle=1)
        if self.experimental_features:
            row = box.row()
            row.prop(self, "depotfolder_path")
            row = box.row()
        if self.show_modtools:
            row.alignment = 'LEFT'
            box = layout.box()
            box.label(text="Mod Tools Properties")
            split = row.split(factor=0.5,align=True)
            col = split.column(align=True)
            row.alignment = 'LEFT'
            row = box.row()
            col = row.column(align=True)
            col.prop(self, "context_only")
            col.prop(self, "show_meshtools")
            col.prop(self, "show_collisiontools")
            col.prop(self, "show_animtools")

def register_prefs():
    bpy.utils.register_class(CP77IOSuitePreferences)

def unregister_prefs():
    bpy.utils.unregister_class(CP77IOSuitePreferences)