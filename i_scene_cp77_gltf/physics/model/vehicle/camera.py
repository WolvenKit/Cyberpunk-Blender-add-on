from __future__ import annotations

TPP_CAMERA_HEIGHTS = ("High", "Low")
TPP_CAMERA_DISTANCES = ("Close", "Medium", "Far")
DEFAULT_TPP_CAMERA_PARAMS_RECORD = "Camera.VehicleTPP_DefaultParams"

TPP_CAMERA_PRESET_DEFAULTS = {
    "lookAtOffset": (0.0, 0.0, 0.3),
    "defaultRotationPitch": 10.0,
    "baseBoomLength": 7.0,
    "boomLengthOffset": 0.0,
}

# Used by the game when a vehicle lists no usable preset.
TPP_CAMERA_FALLBACK_PRESET = {
    "height": "Low",
    "distance": "Close",
    "lookAtOffset": (0.0, 0.0, 3.0),
    "defaultRotationPitch": 5.0,
    "boomLength": 4.0,
}

TPP_CAMERA_PARAM_DEFAULTS = {
    "fov": 69.0,
    "autoCenterMaxSpeedThreshold": 20.0,
    "autoCenterSpeed": 5.0,
    "cameraBoomExtensionSpeed": 3.0,
    "drivingDirectionCompensationSpeedMin": 4.0,
    "drivingDirectionCompensationSpeedMax": 120.0,
    "drivingDirectionCompensationSpeedCoef": 1.0,
    "drivingDirectionCompensationAngle": 100.0,
    "drivingDirectionCompensationAngleSmooth": 70.0,
    "drivingDirectionCompensationAngularVelocityMin": 150.0,
    "elasticBoomForwardAccelerationCoef": 10.0,
    "elasticBoomAccelerationExpansionLength": 0.5,
    "elasticBoomSpeedExpansionSpeedMin": 10.0,
    "elasticBoomSpeedExpansionSpeedMax": 20.0,
    "elasticBoomSpeedExpansionLength": 0.5,
    "elasticBoomVelocity": True,
    "elasticBoomAcceleration": True,
    "drivingDirectionCompensation": True,
}

# Smoothing time, in seconds, of the camera's speed and velocity dampers.
TPP_CAMERA_SMOOTH_TIME = 0.1
