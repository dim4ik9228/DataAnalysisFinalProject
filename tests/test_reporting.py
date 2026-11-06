"""Check that descriptive figures preserve aggregate values and undefined groups."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PathCollection
from matplotlib.colors import to_rgba

from parentedu.reporting import ORANGE, _distribution_figure, _grade_figure


def test_grade_distribution_maps_unsorted_counts_to_actual_grade_including_zero():
    records = []
    for subject, observed in (("mat", {0: 1, 7: 2}), ("por", {0: 2, 20: 1})):
        records.extend(
            {"subject": subject, "grade": grade, "count": observed.get(grade, 0)}
            for grade in range(21)
        )
    frame = pd.DataFrame(records).sample(frac=1, random_state=7)
    fig = _distribution_figure(frame, {"mat": 3, "por": 3})
    try:
        first, second = fig.axes
        assert [bar.get_height() for bar in first.patches] == [1] + [0] * 6 + [2] + [0] * 13
        assert second.patches[0].get_height() == 2
        assert second.patches[20].get_height() == 1
        assert first.patches[0].get_facecolor() == to_rgba(ORANGE)
        assert first.get_ylim() == second.get_ylim()
        assert any("G3=0: 1" == text.get_text() for text in first.texts)
    finally:
        plt.close(fig)


def test_empty_education_group_has_no_zero_grade_marker_and_iqr_is_not_ci():
    records = []
    for subject in ("mat", "por"):
        for parent in ("Medu", "Fedu"):
            for level in range(1, 5):
                empty = subject == "mat" and level == 1
                records.append(
                    {
                        "subject": subject,
                        "parent": parent,
                        "education_level": level,
                        "n": 0 if empty else 2,
                        "q1": np.nan if empty else 3,
                        "median": np.nan if empty else 4,
                        "q3": np.nan if empty else 5,
                    }
                )
    frame = pd.DataFrame(records).sample(frac=1, random_state=9)
    fig = _grade_figure(frame, {"mat": 6, "por": 8})
    try:
        axis = fig.axes[0]
        points = [
            tuple(point)
            for collection in axis.collections
            if isinstance(collection, PathCollection)
            for point in collection.get_offsets()
        ]
        assert points == [(2.0, 4.0), (3.0, 4.0), (4.0, 4.0)]
        assert any(text.get_text() == "n=0" for text in axis.texts)
        assert any("немає" in text.get_text() for text in axis.texts)
        assert any("не довірчий інтервал" in text.get_text() for text in fig.texts)
        assert axis.get_ylim() == (0, 20)
    finally:
        plt.close(fig)
