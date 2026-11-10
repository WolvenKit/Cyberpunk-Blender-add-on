from .mat_common import new_labeled_node

ABSENT_COLOR_FALLBACK = (1.0, 1.0, 1.0, 1.0)


class EmissiveSlotsMixin:
    def apply_structure_values(self, Data, Mat, slots):
        data = Data if isinstance(Data, dict) else {}
        self._write_values(Mat, data, slots)

    def _slot(self, slot, node, socket=None):
        self.structure_slots[slot] = (node.name, socket)

    def _value(self, nodes, slot, location):
        node = new_labeled_node(nodes, "ShaderNodeValue", slot, location)
        self._slot(slot, node)
        return node.outputs["Value"]
