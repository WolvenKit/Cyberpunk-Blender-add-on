from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedAppearance:
    appearances: tuple
    appearance_names: tuple
    appearances_by_name: object
    components_by_appearance_name: object
    chunks_by_appearance_name: object
    parent_transform_lookup_by_appearance_name: object
    skinning_lookup_by_appearance_name: object
    shape_lookup_by_appearance_name: object
    light_channels_by_appearance_name: object
