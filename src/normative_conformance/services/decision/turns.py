from itertools import groupby
from operator import attrgetter

from normative_conformance.schemas.observation import ObservationInput


def turns(*, observations: list[ObservationInput]) -> list[list[ObservationInput]]:
    """Group speech into turns: consecutive observations from one speaker, in time order."""
    ordered = sorted(observations, key=lambda row: (row.start_at, row.end_at, row.observation_id))
    return [list(turn) for _, turn in groupby(ordered, key=attrgetter("speaker_id"))]
