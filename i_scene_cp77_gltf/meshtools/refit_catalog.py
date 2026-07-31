from dataclasses import dataclass
import os

from ..paths import get_refit_dir


@dataclass(frozen=True, slots=True)
class RefitterOption:
    name: str
    filename: str | None

    def resolve_path(self):
        if self.filename is None:
            return None
        return os.path.join(get_refit_dir(), self.filename)


_BASE_REFITTERS = (
    RefitterOption("None", None),
    RefitterOption("Gymfiend", "gymfiend_autofitter.npz"),
    RefitterOption("Fryja", "fryja _autofitter.npz"),
    RefitterOption("Solo_Ultimate", "soloultimate_autofitter.npz"),
    RefitterOption("Adonis", "adonis_autofitter.npz"),
    RefitterOption("Flat_Chest", "na_flatchest_autofitter.npz"),
    RefitterOption("Hyst_EBB_RB", "hyst_ebb_rb_autofitter.npz"),
    RefitterOption("Hyst_EBB", "hyst_ebb_autofitter.npz"),
    RefitterOption("Hyst_RB", "hyst_rb_autofitter.npz"),
    RefitterOption("Lush", "lush_autofitter.npz"),
    RefitterOption("VanillaFemToMasc", "vanilla_femtomasc_autofitter.npz"),
    RefitterOption("VanillaMascToFem", "vanilla_masctofem_autofitter.npz"),
    RefitterOption("VanillaFem_BigBoobs", "f_normal_to_big_boobs_autofitter.npz"),
    RefitterOption("VanillaFem_SmallBoobs", "f_normal_to_small_boobs_autofitter.npz"),
    RefitterOption("Elegy", "elegy_autofitter.npz"),
)

_ADDON_REFITTERS = (
    RefitterOption("SoloArmsAddon", "addon_solo_arms.npz"),
    RefitterOption("Hyst_EBBP_Addon", "addon_hyst_ebbp.npz"),
    RefitterOption("Hyst_EBBN_Addon", "addon_hyst_ebbn.npz"),
)


def base_refitter_options():
    return _BASE_REFITTERS


def addon_refitter_options():
    return _ADDON_REFITTERS


def resolve_refitter(name, *, addon=False):
    options = _ADDON_REFITTERS if addon else _BASE_REFITTERS
    for option in options:
        if option.name == name:
            return option.resolve_path()
    raise KeyError(name)


def refitter_enum_items(*, addon=False):
    options = _ADDON_REFITTERS if addon else _BASE_REFITTERS
    return tuple((option.name, option.name, "") for option in options)
