VEHICLE_CURVE_EXTENSIONS = (
    ".curveset.json",
    ".vehcurveset.json",
    ".bikecurveset.json",
)


def vehicle_curve_loader(asset_index, documents):
    def load(reference):
        lowered = str(reference).casefold()
        if lowered.endswith(".vehcurveset"):
            extension = ".vehcurveset.json"
        elif lowered.endswith(".bikecurveset"):
            extension = ".bikecurveset.json"
        else:
            extension = ".curveset.json"
        path = asset_index.resolve_expected(reference, extension)
        return documents.payload(path) if path else None

    return load
