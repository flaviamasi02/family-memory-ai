from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import pytest

from learning.category_learning_engine import CategoryLearningEngine
from learning.preference_learning_engine import PreferenceLearningEngine


def _photos(count: int):
    return [
        SimpleNamespace(
            path=Path(f"synthetic-{index}.jpg"), metadata={}, visual_features=None,
            automatic_media_category="unknown", effective_media_category="unknown",
            media_category="unknown", user_corrected_media_category="",
        )
        for index in range(count)
    ]


@pytest.mark.parametrize("count", [10, 100, 1000])
def test_perf_002_learning_profile_persistence_is_constant_per_bulk_action(tmp_path, count):
    category = CategoryLearningEngine(storage_root=tmp_path / "category")
    preference = PreferenceLearningEngine(storage_root=tmp_path / "preference")
    saves = {"category": 0, "preference": 0}
    category._save_profile = lambda: saves.__setitem__("category", saves["category"] + 1)
    preference._save_profile = lambda: saves.__setitem__("preference", saves["preference"] + 1)

    started = perf_counter()
    with category.bulk_update(), preference.bulk_update():
        for photo in _photos(count):
            category.record_category_correction(photo, "unknown", "meme", "user_bulk")
            preference.record_category_correction(photo, "unknown", "meme", "user_bulk")
    elapsed = perf_counter() - started

    assert saves == {"category": 1, "preference": 1}
    assert category.profile.total_events == count
    assert preference.profile.total_events == count
    # A generous guard against accidentally restoring quadratic per-event saves.
    assert elapsed < 5.0


def test_perf_002_nested_batches_commit_only_at_outer_boundary(tmp_path):
    engine = PreferenceLearningEngine(storage_root=tmp_path)
    saves = []
    engine._save_profile = lambda: saves.append(True)
    photo = _photos(1)[0]
    with engine.bulk_update():
        with engine.bulk_update():
            engine.record_category_correction(photo, "unknown", "document", "user_bulk")
        assert saves == []
    assert saves == [True]
