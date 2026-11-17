import bpy


class LoadedImageIndex:
    def __init__(self, image_key):
        self._image_key = image_key
        self._names = {}
        self._count = -1

    def __len__(self):
        return len(self._names)

    @property
    def complete(self):
        return self._count >= 0

    @property
    def indexed_images(self):
        return max(0, self._count)

    def clear(self):
        self._names.clear()
        self._count = -1

    def _rebuild(self):
        self._names.clear()
        for image in tuple(bpy.data.images):
            key = self._image_key(image)
            if key:
                self._names.setdefault(key, image.name)
        self._count = len(bpy.data.images)

    def _matching(self, key):
        name = self._names.get(key)
        image = bpy.data.images.get(name) if name else None
        return image if image is not None and self._image_key(image) == key else None

    def find(self, key):
        if self._count != len(bpy.data.images):
            self._rebuild()
        image = self._matching(key)
        if image is None and key in self._names:
            self._rebuild()
            image = self._matching(key)
        return image

    def remember(self, key, image):
        self._names[key] = image.name
        self._count = len(bpy.data.images)

    def count_unindexed_image(self, count_before):
        if self._count == count_before:
            self._count = count_before + 1
