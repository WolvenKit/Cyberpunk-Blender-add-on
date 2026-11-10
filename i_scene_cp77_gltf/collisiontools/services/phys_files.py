from ...assetio.documents import DocumentSession
from ...blender.physics.resources import import_phys_resource_to_actor
from ...core.log import get_logger
from ...physics.services.repository import PhysicsRepository

_LOG = get_logger(__name__)


def load_phys(filepath):
    with DocumentSession() as documents:
        return PhysicsRepository(documents).load(filepath, required=True)


def import_phys_to_actor(filepath, target_obj, context):
    try:
        resource = load_phys(filepath)
    except Exception as error:
        _LOG.error("Unable to read physics resource: %s", error, exc_info=True)
        return False
    return import_phys_resource_to_actor(resource, target_obj, context)
