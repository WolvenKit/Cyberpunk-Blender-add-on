
import bpy

from ...blender.animgraph.layout import layout_node_tree


class ParserLayoutMixin:
    def _layout_all(self) -> None:
        """Lay out all imported node trees with conservative spacing"""
        edges_by_tree: dict[
            int, set[tuple[bpy.types.Node, bpy.types.Node]]
        ] = {}

        def add(
            src: bpy.types.Node | None, dst: bpy.types.Node | None
        ) -> None:
            if (
                src is None
                or dst is None
                or src is dst
                or src.id_data is not dst.id_data
            ):
                return
            edges_by_tree.setdefault(id(src.id_data), set()).add((src, dst))

        for hid, entries in self.node_links.items():
            dst = self.bl_nodes.get(hid)
            for _key, _caption, wrapper in entries:
                source_hid = self._link_target_handle(wrapper)
                add(
                    self.bl_nodes.get(source_hid) if source_hid is not None else None,
                    dst,
                )

        for src, dst in self.transition_layout_edges:
            add(src, dst)
        for src, _out_name, dst, _in_name in self.boundary_links:
            add(src, dst)
        if self.root_output_node is not None and self.root_output_link is not None:
            source_hid = self._link_target_handle(self.root_output_link)
            add(
                self.bl_nodes.get(source_hid) if source_hid is not None else None,
                self.root_output_node,
            )
        for src, group_out in self.group_wires:
            add(src, group_out)

        trees = {id(self.root_tree): self.root_tree}
        for tree in self.tree_of_container.values():
            trees[id(tree)] = tree

        self.layout_overlap_count = 0
        self.layout_trees_checked = 0
        self.curve_widgets_initialized = 0
        self.curve_widgets_failed = 0
        self.source_alignment_report = {}
        for tree_id, tree in trees.items():
            # Sorted for a deterministic edge order; the set only removes duplicates.
            edges = sorted(
                edges_by_tree.get(tree_id, ()),
                key=lambda pair: (pair[0].name, pair[1].name),
            )
            self.layout_overlap_count += layout_node_tree(tree, edges)
            self.layout_trees_checked += 1
        if self.layout_overlap_count:
            self.problems.append(
                f"estimated layout still has {self.layout_overlap_count} overlapping node pair(s)"
            )
