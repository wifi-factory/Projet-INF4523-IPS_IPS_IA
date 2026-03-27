from __future__ import annotations

from typing import Iterable, Mapping


def normalize_probability_map(
    probabilities: Iterable[float],
    class_labels: Iterable[str],
) -> dict[str, float]:
    return {
        str(label): float(probability)
        for label, probability in zip(class_labels, probabilities, strict=True)
    }


def pick_confidence(
    probability_map: Mapping[str, float] | None,
    predicted_label: str,
) -> float | None:
    if probability_map is None:
        return None
    probability = probability_map.get(predicted_label)
    return float(probability) if probability is not None else None
