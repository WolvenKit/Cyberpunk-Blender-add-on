import bpy


class CP77_UL_cloth_colliders(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if not item:
            return
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        icon_name = 'SPHERE' if item.collider_type == 'SPHERE' else 'MESH_CAPSULE'
        row.label(text=f"{item.name} [{item.region}]", icon=icon_name)


class CP77_UL_avatar_anchors(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item:
            layout.label(text=f"{item.name} [{item.anchor_type}]", icon='EMPTY_ARROWS')


class CP77_UL_garment_seam_pairs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if not item:
            return
        target = item.target_object.name if item.target_object else "same mesh"
        layout.label(
            text=f"{item.name}: {item.source_count} ↔ {item.target_count} [{target}]", icon='MOD_VERTEX_WEIGHT'
            )

CLOTH_UI_CLASSES = (
    CP77_UL_cloth_colliders,
    CP77_UL_avatar_anchors,
    CP77_UL_garment_seam_pairs,
)
