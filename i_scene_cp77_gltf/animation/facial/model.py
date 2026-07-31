from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrackSegments:
    num_tracks: int
    envelope_start: int
    envelope_end: int
    main_start: int
    main_end: int
    lipsync_ovr_start: int
    lipsync_ovr_end: int
    lipsync_out_start: int
    lipsync_out_end: int
    wrinkle_start: int
    wrinkle_end: int

    @classmethod
    def from_setup(cls, setup, num_tracks: int) -> "TrackSegments":
        envelope_end = int(setup.num_envelope_tracks)
        main_start = envelope_end
        main_end = main_start + int(setup.num_main_poses)
        lipsync_ovr_start = main_end
        lipsync_ovr_end = lipsync_ovr_start + int(setup.num_lipsync_overrides)
        lipsync_out_start = lipsync_ovr_end
        lipsync_out_end = lipsync_out_start + int(setup.num_main_poses)
        wrinkle_start = lipsync_out_end
        wrinkle_end = wrinkle_start + int(setup.num_wrinkle_tracks)
        if wrinkle_end > num_tracks:
            raise ValueError(
                f"Facial setup requires {wrinkle_end} tracks, but the rig provides {num_tracks}"
            )
        return cls(
            num_tracks=num_tracks,
            envelope_start=0,
            envelope_end=envelope_end,
            main_start=main_start,
            main_end=main_end,
            lipsync_ovr_start=lipsync_ovr_start,
            lipsync_ovr_end=lipsync_ovr_end,
            lipsync_out_start=lipsync_out_start,
            lipsync_out_end=lipsync_out_end,
            wrinkle_start=wrinkle_start,
            wrinkle_end=wrinkle_end,
        )

    def is_input(self, track_index: int) -> bool:
        return (
            self.envelope_start <= track_index < self.envelope_end
            or self.main_start <= track_index < self.main_end
            or self.lipsync_ovr_start <= track_index < self.lipsync_ovr_end
        )

    def is_output(self, track_index: int) -> bool:
        return (
            self.lipsync_out_start <= track_index < self.lipsync_out_end
            or self.wrinkle_start <= track_index < self.wrinkle_end
        )
