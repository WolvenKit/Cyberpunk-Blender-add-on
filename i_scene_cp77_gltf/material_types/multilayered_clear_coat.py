from .multilayer_coat import (
    apply_principled_multilayer_coat_values,
    configure_principled_multilayer_coat,
    selected_layer_indices,
)
from .multilayered import Multilayered


class MultilayeredClearCoat(Multilayered):
    def configure_multilayer_surface(self, Mat, Data, context):
        configure_principled_multilayer_coat(Data, context)

    def surface_structure(self, Data, layer_count):
        return selected_layer_indices(Data, layer_count)

    def apply_surface_values(self, Mat, Data, slots, layer_count):
        apply_principled_multilayer_coat_values(Mat, Data, slots)
