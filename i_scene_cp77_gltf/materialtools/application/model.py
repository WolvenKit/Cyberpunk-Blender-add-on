from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MaterialToolState:
    context: object = None
    scene: object = None
    props: object = None
    obj: object = None
    material: object = None
    node_tree: object = None
    root_node: object = None
    layer_index: int = 1
    layer_socket: object = None
    layer_node: object = None
    mask_node: object = None
    template_path: str = ""
    palette: object = None
    errors: tuple = ()

    @property
    def valid_material(self):
        if self.obj is None or getattr(self.obj, "type", None) != "MESH":
            return False
        if self.material is None or self.node_tree is None or self.root_node is None:
            return False
        try:
            return (
                bool(getattr(self.material, "use_nodes", False))
                and self.material.get("MLSetup") is not None
            )
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("MaterialToolState.valid_material", type(error).__name__),
                "valid material: fell back after %s",
                error,
                exc_info=True,
            )
            return False

    @property
    def valid_layer(self):
        return (
            self.valid_material
            and self.layer_socket is not None
            and self.layer_node is not None
        )

    @property
    def error_message(self):
        return "; ".join(self.errors)


@dataclass(frozen=True, slots=True)
class TemplateState:
    layer_node: object = None
    layer_tree: object = None
    base_node: object = None
    template_tree: object = None
    group_input: object = None
    microblend_node: object = None
    template_path: str = ""
    errors: tuple = ()

    @property
    def valid(self):
        return (
            not self.errors
            and self.base_node is not None
            and self.template_tree is not None
        )

    @property
    def error_message(self):
        return "; ".join(self.errors)


@dataclass(frozen=True, slots=True)
class MaterialTemplateBuildResult:
    material: Any
    assigned_count: int
    template_path: str
    depot_root: str


@dataclass(frozen=True, slots=True)
class MultilayerTemplateLoadResult:
    palette: Any
    template_path: str


@dataclass(frozen=True, slots=True)
class MaterialDepotScanResult:
    loaded_count: int
    setup_count: int
    failures: tuple[str, ...]
    collision_count: int
    first_palette: Any = None

    @property
    def succeeded(self) -> bool:
        return bool(self.loaded_count or self.setup_count)


@dataclass(frozen=True, slots=True)
class MicroblendLoadResult:
    loaded_count: int
    existing_count: int
    failures: tuple[str, ...]
    collision_count: int

    @property
    def succeeded(self) -> bool:
        return bool(self.loaded_count or self.existing_count)
