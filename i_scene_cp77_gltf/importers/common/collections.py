from __future__ import annotations


def link_collection_once(parent, child):
    if parent.children.get(child.name) is not child:
        parent.children.link(child)
