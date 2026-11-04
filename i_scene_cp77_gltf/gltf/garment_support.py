GARMENT_SUPPORT_MORPH = "GarmentSupport"
GARMENT_CAP_ATTRIBUTE = "_GarmentSupportCap"
GARMENT_WEIGHT_ATTRIBUTE = "_GarmentSupportWeight"


def canonical_garment_attribute(name: str) -> str:
    folded = str(name).casefold()
    if folded == GARMENT_CAP_ATTRIBUTE.casefold():
        return GARMENT_CAP_ATTRIBUTE
    if folded == GARMENT_WEIGHT_ATTRIBUTE.casefold():
        return GARMENT_WEIGHT_ATTRIBUTE
    return str(name)


def is_garment_attribute(name: str) -> bool:
    canonical = canonical_garment_attribute(name)
    return canonical in {GARMENT_CAP_ATTRIBUTE, GARMENT_WEIGHT_ATTRIBUTE}
