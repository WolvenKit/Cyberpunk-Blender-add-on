from ..registration import RegistrationLedger
from .dangles import register as register_dangles
from .dangles import unregister as unregister_dangles
from .pxbridge import register as register_pxbridge
from .pxbridge import unregister as unregister_pxbridge
from .ui import CP77_PT_PhysicsTools


classes = (CP77_PT_PhysicsTools,)

_LEDGER = RegistrationLedger("collisiontools")


def register_collisiontools():
    if _LEDGER.active:
        return
    try:
        register_pxbridge()
        _LEDGER.add_cleanup("PxBridge", unregister_pxbridge)
        register_dangles()
        _LEDGER.add_cleanup("Dangles", unregister_dangles)
        _LEDGER.register_classes(classes)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_collisiontools():
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(
            f"{label}: {error}" for label, error in failures
        ))
