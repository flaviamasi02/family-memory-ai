import json
from pathlib import Path

from core.category_suggestion_service import (
    CategorySuggestionConfig,
    CategorySuggestionService,
)
from core.category_registry import CategoryRegistry
from core.user_metadata_service import UserMetadataService
from types import SimpleNamespace
from vision.semantic_similarity_service import (
    SemanticSimilarityResult,
    canonical_photo_key,
)


class FakeClassifier:
    def classify(self, path, metadata=None, allow_visual_analysis=False):
        name = Path(path).name.lower()
        cat = (
            "screenshot"
            if "screenshot" in name
            else "family_photo" if name.startswith("img_") else "unknown"
        )
        return SimpleNamespace(
            media_category=cat,
            classification_confidence=0.9 if cat != "unknown" else 0.3,
        )


from vision.embedding_provider import (
    EmbeddingRecord,
    EmbeddingStore,
    ModelMetadata,
    now_iso,
    source_identity,
)

META = ModelMetadata("fake", "fake-v1", "test", "test", "local", "0", "0", "0", 3)


def photo(
    path: Path,
    category="unknown",
    *,
    user=False,
    confirmed=False,
    accepted=False,
    deterministic=False,
):
    if not path.exists():
        path.write_bytes(path.name.encode())
    p = SimpleNamespace(
        path=path,
        filename=path.name,
        file_size=path.stat().st_size,
        user_decision="pending",
        classification_reason="",
        sync_intelligence_from_metadata=lambda: None,
        sync_visual_features_from_metadata=lambda: None,
    )
    p.media_category = p.effective_media_category = p.automatic_media_category = (
        category
    )
    p.user_corrected_media_category = category if user else ""
    p.metadata = {
        "media_category": category,
        "effective_media_category": category,
        "automatic_media_category": category,
        "user_corrected_media_category": category if user else "",
    }
    if confirmed:
        p.metadata["category_confirmation_state"] = "confirmed"
    if accepted:
        p.metadata["category_suggestion_state"] = "accepted"
    if deterministic:
        p.metadata["deterministic_category_trusted"] = True
    return p


def put(store, p, vec, meta=META):
    key, mt, sz, fp = source_identity(p.path)
    store.put(
        EmbeddingRecord(
            key,
            fp,
            mt,
            sz,
            meta.provider_id,
            meta.checkpoint_id,
            meta.revision,
            meta.embedding_dimension,
            vec,
            now_iso(),
        )
    )


def service(tmp_path, store):
    registry = CategoryRegistry(storage_root=tmp_path / "cats")
    return CategorySuggestionService(
        embedding_store=store,
        category_registry=registry,
        media_classifier=FakeClassifier(),
        config=CategorySuggestionConfig(
            minimum_similarity=0.70, minimum_support_count=2
        ),
    )


def test_clear_single_category_support_produces_suggestion_and_excludes_source(
    tmp_path,
):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    a = photo(tmp_path / "a.jpg", "family_photo", user=True)
    b = photo(tmp_path / "b.jpg", "family_photo", confirmed=True)
    put(store, src, [1, 0, 0])
    put(store, a, [0.98, 0.02, 0])
    put(store, b, [0.95, 0.05, 0])
    result = service(tmp_path, store).suggest(src, [src, a, b], META)
    assert result.status == "suggested"
    assert result.suggested_category_id == "family_photo"
    assert result.evidence_counts["family_photo"] == 2
    assert src.path.resolve().as_posix() not in [
        e.photo_key for e in result.supporting_photos
    ]
    assert 0 <= result.confidence <= 1
    assert result.reasons == sorted(result.reasons, key=result.reasons.index)


def test_insufficient_no_embedding_stale_and_incompatible_model(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    assert service(tmp_path, store).suggest(src, [src], META).status == "no_embedding"
    put(store, src, [1, 0, 0])
    src.path.write_bytes(b"changed")
    assert service(tmp_path, store).suggest(src, [src], META).status == "no_embedding"
    other = ModelMetadata("fake", "fake-v1", "other", "test", "local", "0", "0", "0", 3)
    assert service(tmp_path, store).suggest(src, [src], other).status == "no_embedding"


def test_only_untrusted_labels_and_non_content_categories_excluded(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    machine = photo(tmp_path / "m.jpg", "family_photo")
    screenshot = photo(tmp_path / "s.jpg", "screenshot", user=True)
    put(store, src, [1, 0, 0])
    put(store, machine, [0.99, 0, 0])
    put(store, screenshot, [0.98, 0, 0])
    result = service(tmp_path, store).suggest(src, [src, machine, screenshot], META)
    assert result.status == "insufficient_evidence"


def test_unrelated_manual_confirmation_outside_semantic_matches_is_not_evidence(
    tmp_path,
):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "source.jpg")
    unknown_match = photo(tmp_path / "nearest_unknown.jpg")
    unrelated = photo(tmp_path / "unrelated.jpg", "family_photo", user=True)
    put(store, src, [1, 0, 0])

    class UnknownOnlySimilarity:
        def most_similar(self, *_args, **_kwargs):
            return [
                SemanticSimilarityResult(
                    canonical_photo_key(unknown_match), 0.99, META.model_key
                )
            ]

    svc = CategorySuggestionService(
        embedding_store=store,
        similarity_service=UnknownOnlySimilarity(),
        category_registry=CategoryRegistry(storage_root=tmp_path / "cats"),
        media_classifier=FakeClassifier(),
    )

    result = svc.suggest(src, [src, unknown_match, unrelated], META)

    assert result.status == "insufficient_evidence"
    assert result.evidence_counts == {}
    assert result.supporting_photos == []


def test_conflicting_category_evidence_and_tie(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    fam1 = photo(tmp_path / "f1.jpg", "family_photo", user=True)
    fam2 = photo(tmp_path / "f2.jpg", "family_photo", user=True)
    per1 = photo(tmp_path / "p1.jpg", "personal_photo", user=True)
    per2 = photo(tmp_path / "p2.jpg", "personal_photo", user=True)
    for p, v in [
        (src, [1, 0, 0]),
        (fam1, [0.99, 0, 0]),
        (fam2, [0.98, 0, 0]),
        (per1, [0.99, 0, 0]),
        (per2, [0.98, 0, 0]),
    ]:
        put(store, p, v)
    assert (
        service(tmp_path, store)
        .suggest(src, [src, fam1, fam2, per1, per2], META)
        .status
        == "conflicting_evidence"
    )


def test_deterministic_agreement_increases_and_disagreement_reduces_confidence(
    tmp_path,
):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "IMG_1234.jpg", "unknown")
    a = photo(tmp_path / "a.jpg", "family_photo", user=True)
    b = photo(tmp_path / "b.jpg", "family_photo", user=True)
    put(store, src, [1, 0, 0])
    put(store, a, [0.99, 0, 0])
    put(store, b, [0.98, 0, 0])
    svc = service(tmp_path, store)
    agree = svc.suggest(src, [src, a, b], META).confidence
    src.filename = "screenshot_2020.jpg"
    src.path = tmp_path / "screenshot_2020.jpg"
    src.path.write_bytes(b"src")
    put(store, src, [1, 0, 0])
    svc.invalidate_cache()
    disagree = svc.suggest(src, [src, a, b], META).confidence
    assert agree > disagree


def test_no_embedding_recomputation_or_category_modification_and_rejection(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    a = photo(tmp_path / "a.jpg", "family_photo", user=True)
    b = photo(tmp_path / "b.jpg", "family_photo", user=True)
    put(store, src, [1, 0, 0])
    put(store, a, [0.99, 0, 0])
    put(store, b, [0.98, 0, 0])
    before = src.effective_media_category
    svc = service(tmp_path, store)
    result = svc.suggest(src, [src, a, b], META)
    assert src.effective_media_category == before
    assert store.count() == 3
    svc.record_rejection(result)
    assert src.effective_media_category == before
    assert svc.feedback_events[-1]["action"] == "rejected"


def test_memory_review_ui_entry_point_is_existing_panel_not_new_tab():
    ui = Path("src/ui/album_review_page.py").read_text()
    main = Path("src/ui/main_window.py").read_text()
    assert "AI Suggestion" in ui
    assert "Apply suggestion" in ui
    assert "Reject / Not useful" in ui
    assert 'QGroupBox("Current Status")' in ui
    assert 'QLabel("Category")' in ui
    assert "status_layout.addWidget(self.media_category_value)" in ui
    assert "preview_status_layout.addWidget(self.preview_section, 3)" in ui
    assert 'QLabel("Source")' in ui
    assert "Accepted AI suggestion" in ui
    assert 'QGroupBox("Classification Summary")' in ui
    assert 'QGroupBox("Technical details")' in ui
    assert "Initial technical reason:" not in ui
    assert "_apply_category_to_rows" in ui and "result.suggested_category_id" in ui
    assert ui.count("addTab") == 0
    assert main.count("Memory Review") >= 1


def test_stale_async_result_guard_and_cache_reuse_are_present():
    ui = Path("src/ui/album_review_page.py").read_text()
    svc = Path("src/core/category_suggestion_service.py").read_text()
    assert "request_id != self._suggestion_request_id" in ui
    assert "self._details_key != self._row_key(row)" in ui
    assert "cached = self._cache.get(cache_key)" in svc
    assert "cached.evidence_signature == signature_key" in svc
    assert "invalidate_cache" in ui


def test_rejection_persists_and_suppresses_unchanged_suggestion(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    a = photo(tmp_path / "a.jpg", "family_photo", user=True)
    b = photo(tmp_path / "b.jpg", "family_photo", user=True)
    put(store, src, [1, 0, 0])
    put(store, a, [0.99, 0, 0])
    put(store, b, [0.98, 0, 0])
    svc = service(tmp_path, store)
    result = svc.suggest(src, [src, a, b], META)
    before = src.effective_media_category
    event = svc.record_rejection(
        result, source="user", photo=src, chooser_identity="profile:user"
    )
    assert src.effective_media_category == before
    assert event["action"] == "rejected"
    assert event["chooser_identity"] == "profile:user"
    assert UserMetadataService().sidecar_path_for(src.path).exists()

    reloaded = photo(tmp_path / "src.jpg")
    UserMetadataService().apply_for_photo(reloaded)
    assert reloaded.effective_media_category == before
    assert reloaded.metadata["category_suggestion_feedback"][-1]["action"] == "rejected"
    suppressed = service(tmp_path, store).suggest(reloaded, [reloaded, a, b], META)
    assert suppressed.status == "insufficient_evidence"
    assert "previously marked not useful" in suppressed.reasons[0]


def test_rejected_suggestion_can_resurface_after_evidence_changes(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    a = photo(tmp_path / "a.jpg", "family_photo", user=True)
    b = photo(tmp_path / "b.jpg", "family_photo", user=True)
    put(store, src, [1, 0, 0])
    put(store, a, [0.99, 0, 0])
    put(store, b, [0.98, 0, 0])
    svc = service(tmp_path, store)
    result = svc.suggest(src, [src, a, b], META)
    svc.record_rejection(result, photo=src)
    assert svc.suggest(src, [src, a, b], META).status == "insufficient_evidence"

    c = photo(tmp_path / "c.jpg", "family_photo", user=True)
    put(store, c, [0.97, 0, 0])
    changed = service(tmp_path, store).suggest(src, [src, a, b, c], META)
    assert changed.status == "suggested"


def test_apply_suggestion_source_uses_existing_category_workflow_and_clears_panel():
    ui = Path("src/ui/album_review_page.py").read_text()
    apply_block = ui[
        ui.index("def _apply_current_suggestion") : ui.index(
            "def _reject_current_suggestion"
        )
    ]
    assert "self._apply_category_to_rows" in apply_block
    assert 'source="ai_suggestion_accepted"' in apply_block
    assert "user_corrected_media_category" not in apply_block
    assert "record_category_correction" not in apply_block
    assert "Suggestion applied through the category correction workflow." in apply_block
    assert "self._suggestion_request_id += 1" in apply_block
    assert "if not applied:" in apply_block
    assert "No acceptance was recorded" in apply_block


def test_acceptance_metadata_round_trips_and_suppresses_the_applied_suggestion(
    tmp_path,
):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg", "family_photo", user=True)
    src.user_decision = "keep"
    src.metadata.update(
        {
            "user_decision": "keep",
            "category_confirmation_state": "manual_confirmed",
            "category_confirmation_source": "ai_suggestion_accepted",
            "category_confirmation_category": "family_photo",
            "category_confirmation_at": "2026-07-25T12:00:00+00:00",
            "category_suggestion_state": "accepted",
            "category_suggestion_model_key": META.model_key,
            "category_suggestion_applied_category": "family_photo",
            "category_suggestion_accepted_at": "2026-07-25T12:00:00+00:00",
            "category_suggestion_support_count": 2,
            "category_suggestion_confidence": 0.85,
        }
    )
    a = photo(tmp_path / "a.jpg", "family_photo", user=True)
    b = photo(tmp_path / "b.jpg", "family_photo", user=True)
    for item, vector in ((src, [1, 0, 0]), (a, [0.99, 0, 0]), (b, [0.98, 0, 0])):
        put(store, item, vector)

    UserMetadataService().save_photo_metadata(src)
    reloaded = photo(tmp_path / "src.jpg")
    UserMetadataService().apply_for_photo(reloaded)

    assert reloaded.user_corrected_media_category == "family_photo"
    assert reloaded.effective_media_category == "family_photo"
    assert reloaded.media_category == "family_photo"
    assert reloaded.user_decision == "keep"
    assert reloaded.metadata["category_confirmation_at"]
    assert reloaded.metadata["category_suggestion_state"] == "accepted"
    assert reloaded.metadata["category_suggestion_applied_category"] == "family_photo"
    assert reloaded.metadata["category_suggestion_support_count"] == 2
    result = service(tmp_path, store).suggest(reloaded, [reloaded, a, b], META)
    assert result.status == "already_accepted"
    assert result.suggested_category_id == "family_photo"
    assert result.suggested_category_name == "Family Photo"
    assert result.evidence_counts["family_photo"] == 2
    assert "already been applied" in result.reasons[0]


def test_category_apply_persists_once_before_learning_and_returns_success():
    ui = Path("src/ui/album_review_page.py").read_text()
    apply_block = ui[
        ui.index("def _apply_category_to_rows") : ui.index(
            "def _refresh_after_category_change"
        )
    ]
    assert "acceptance_metadata: Optional[dict] = None" in apply_block
    assert "if not self._save_photo_user_metadata(photo):" in apply_block
    assert apply_block.index("if not self._save_photo_user_metadata(photo):") < apply_block.index(
        "record_category_correction"
    )
    assert "return False" in apply_block
    assert "return True" in apply_block


def test_reject_path_persists_feedback_and_blocks_stale_result_restore():
    ui = Path("src/ui/album_review_page.py").read_text()
    reject_block = ui[
        ui.index("def _reject_current_suggestion") : ui.index(
            "def _sync_selectors_to_row"
        )
    ]
    assert "record_rejection" in reject_block
    assert "photo=row.breakdown.photo" in reject_block
    assert "Suggestion marked not useful. Category was not changed." in reject_block
    assert "self._suggestion_request_id += 1" in reject_block
    assert "_apply_category_to_rows" not in reject_block


def test_embedding_completion_refresh_contract_is_wired_to_memory_review():
    import inspect
    from ui.main_window import MainWindow

    assert "self._on_embedding_index_updated(result)" in inspect.getsource(
        MainWindow._on_embedding_complete
    )
    review_page = SimpleNamespace(refresh_count=0)
    review_page.on_embedding_index_updated = lambda: setattr(
        review_page, "refresh_count", review_page.refresh_count + 1
    )
    window = MainWindow.__new__(MainWindow)
    window.review_page = review_page

    window._on_embedding_index_updated(object())

    assert review_page.refresh_count == 1


def test_no_embedding_results_are_not_cached_so_later_indexing_can_be_observed(
    tmp_path,
):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    a = photo(tmp_path / "a.jpg", "family_photo", user=True)
    b = photo(tmp_path / "b.jpg", "family_photo", user=True)
    put(store, a, [0.99, 0, 0])
    put(store, b, [0.98, 0, 0])
    svc = service(tmp_path, store)
    assert svc.suggest(src, [src, a, b], META).status == "no_embedding"
    put(store, src, [1, 0, 0])
    after_indexing = svc.suggest(src, [src, a, b], META)
    assert after_indexing.status == "suggested"
    assert after_indexing.suggested_category_id == "family_photo"


def test_embedding_index_refresh_does_not_assume_review_page_exists():
    from ui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window._on_embedding_index_updated(object())


def test_single_strong_manual_category_evidence_can_suggest_for_similar_photo(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    confirmed = photo(tmp_path / "confirmed.jpg", "family_photo", user=True)
    put(store, src, [1, 0, 0])
    put(store, confirmed, [0.99, 0, 0])

    result = service(tmp_path, store).suggest(src, [src, confirmed], META)

    assert result.status == "suggested"
    assert result.suggested_category_id == "family_photo"
    assert result.evidence_counts["family_photo"] == 1


def test_manual_category_apply_records_confirmed_evidence_and_decision():
    ui = Path("src/ui/album_review_page.py").read_text()
    apply_block = ui[
        ui.index("def _apply_category_to_rows") : ui.index(
            "def _refresh_after_category_change"
        )
    ]
    assert 'metadata["category_confirmation_state"] = "manual_confirmed"' in apply_block
    assert 'metadata["category_confirmation_source"] = source' in apply_block
    assert 'metadata["category_confirmation_category"] = category' in apply_block
    assert "row.user_decision = UserDecision.Keep.value" in apply_block
    assert "record_decision_change" in apply_block
    assert "record_category_correction" in apply_block


def test_category_confirmation_fields_persist_in_sidecar(tmp_path):
    p = photo(tmp_path / "confirmed.jpg", "family_photo", user=True)
    p.user_decision = "keep"
    p.metadata["user_decision"] = "keep"
    p.metadata["category_confirmation_state"] = "manual_confirmed"
    p.metadata["category_confirmation_source"] = "user"
    p.metadata["category_confirmation_category"] = "family_photo"

    UserMetadataService().save_photo_metadata(p)
    reloaded = photo(tmp_path / "confirmed.jpg")
    UserMetadataService().apply_for_photo(reloaded)

    assert reloaded.user_decision == "keep"
    assert reloaded.metadata["category_confirmation_state"] == "manual_confirmed"
    assert reloaded.metadata["category_confirmation_source"] == "user"
    assert reloaded.metadata["category_confirmation_category"] == "family_photo"
    assert reloaded.user_corrected_media_category == "family_photo"


def test_legacy_family_photo_candidate_sidecar_loads_as_canonical_family_photo(
    tmp_path,
):
    original = photo(tmp_path / "legacy.jpg", "family_photo_candidate", user=True)
    original.user_decision = "keep"
    original.metadata.update(
        {
            "category_confirmation_state": "manual_confirmed",
            "category_confirmation_category": "family_photo_candidate",
            "category_suggestion_state": "accepted",
            "category_suggestion_applied_category": "family_photo_candidate",
        }
    )
    metadata_service = UserMetadataService()
    sidecar = metadata_service.save_photo_metadata(original)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    for key in (
        "user_corrected_media_category",
        "effective_media_category",
        "category_confirmation_category",
        "category_suggestion_applied_category",
    ):
        payload[key] = "family_photo_candidate"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    reloaded = photo(tmp_path / "legacy.jpg")
    metadata_service.apply_for_photo(reloaded)

    assert reloaded.user_corrected_media_category == "family_photo"
    assert reloaded.effective_media_category == "family_photo"
    assert reloaded.media_category == "family_photo"
    assert reloaded.metadata["category_confirmation_category"] == "family_photo"
    assert reloaded.metadata["category_suggestion_applied_category"] == "family_photo"


def test_three_manual_family_photo_labels_with_display_names_feed_suggestion(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    confirmed = [
        photo(tmp_path / f"confirmed_{index}.jpg", "Family Photo", user=True)
        for index in range(3)
    ]
    put(store, src, [1, 0, 0])
    for index, item in enumerate(confirmed):
        put(store, item, [0.99 - index * 0.01, 0.01, 0])

    result = service(tmp_path, store).suggest(src, [src, *confirmed], META)

    assert result.status == "suggested"
    assert result.suggested_category_id == "family_photo"
    assert result.evidence_counts["family_photo"] >= 2
    assert 0.0 <= result.confidence <= 1.0
    assert any(
        "previously confirmed as Family Photo" in reason for reason in result.reasons
    )


def test_three_manual_confirmed_strong_matches_override_inconclusive_rules(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "source.jpg")
    confirmed = [
        photo(tmp_path / f"manual_{index}.jpg", "family_photo", confirmed=True)
        for index in range(3)
    ]
    put(store, src, [1, 0, 0])
    for index, item in enumerate(confirmed):
        put(store, item, [0.99 - 0.01 * index, 0.01, 0])

    result = service(tmp_path, store).suggest(src, [src, *confirmed], META)

    assert result.status == "suggested"
    assert result.suggested_category_id == "family_photo"
    assert result.evidence_counts["family_photo"] == 3
    assert all(
        item.trust_level == "manual_confirmed" for item in result.supporting_photos
    )
    assert "inconclusive" in result.reasons[-1].lower()


def test_three_manual_matches_just_above_similarity_threshold_suggest_advisory_only(
    tmp_path,
):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "source.jpg")
    confirmed = [
        photo(tmp_path / f"threshold_{index}.jpg", "family_photo", confirmed=True)
        for index in range(3)
    ]
    put(store, src, [1, 0, 0])
    put(store, confirmed[0], [0.73, 0.683447, 0])
    put(store, confirmed[1], [0.72, 0.693974, 0])
    put(store, confirmed[2], [0.71, 0.704202, 0])

    result = service(tmp_path, store).suggest(src, [src, *confirmed], META)

    assert result.status == "suggested"
    assert result.suggested_category_id == "family_photo"
    assert result.evidence_counts["family_photo"] == 3
    assert src.effective_media_category == "unknown"
    assert src.user_corrected_media_category == ""


def test_two_weak_manual_matches_remain_insufficient(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "source.jpg")
    weak = [
        photo(tmp_path / f"weak_{index}.jpg", "family_photo", confirmed=True)
        for index in range(2)
    ]
    put(store, src, [1, 0, 0])
    put(store, weak[0], [0.74, 0.672606, 0])
    put(store, weak[1], [0.73, 0.683447, 0])

    result = service(tmp_path, store).suggest(src, [src, *weak], META)

    assert result.status == "insufficient_evidence"
    assert result.evidence_counts["family_photo"] == 2
    assert "not visually similar enough" in result.reasons[0]


def test_cached_insufficient_result_is_replaced_after_immediate_manual_updates(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "20210117_155357.jpg")
    evidence = [
        photo(tmp_path / name)
        for name in (
            "20210117_155350.jpg",
            "20210117_155352.jpg",
            "20210117_155354.jpg",
        )
    ]
    put(store, src, [1, 0, 0])
    for index, item in enumerate(evidence):
        put(store, item, [0.995 - index * 0.005, 0.01, 0])
    svc = service(tmp_path, store)

    before = svc.suggest(src, [src, *evidence], META)
    assert before.status == "insufficient_evidence"
    signature_before = svc._evidence_signature([src, *evidence])
    assert before.evidence_signature == signature_before

    for index, item in enumerate(evidence):
        category = "Family Photo" if index == 0 else "family_photo"
        item.user_corrected_media_category = category
        item.effective_media_category = category
        item.media_category = category
        item.user_decision = "keep"
        item.metadata.update(
            {
                "user_corrected_media_category": category,
                "effective_media_category": category,
                "media_category": category,
                "category_confirmation_state": "manual_confirmed",
                "category_confirmation_source": "user",
                "category_confirmation_category": "family_photo",
                "user_decision": "keep",
            }
        )
    signature_after = svc._evidence_signature([src, *evidence])
    assert signature_after != signature_before

    after = svc.suggest(src, [src, *evidence], META)

    assert after.status == "suggested"
    assert after.suggested_category_id == "family_photo"
    assert after.evidence_signature == signature_after
    assert after.evidence_counts["family_photo"] == 3
    assert {item.photo_key for item in after.supporting_photos} == {
        str(item.path.resolve()) for item in evidence
    }
    assert all(
        item.trust_level in {"manual_confirmed", "user_correction"}
        for item in after.supporting_photos
    )


def test_windows_path_case_and_separator_differences_resolve_trusted_match(tmp_path):
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "source.jpg")
    put(store, src, [1, 0, 0])
    candidate = photo(tmp_path / "placeholder.jpg", "family_photo", user=True)
    candidate.path = Path("c:/photos/confirmed.jpg")

    class WindowsSimilarity:
        def most_similar(self, *_args, **_kwargs):
            return [
                SemanticSimilarityResult(
                    r"C:\PHOTOS\CONFIRMED.JPG", 0.98, META.model_key
                )
            ]

    svc = CategorySuggestionService(
        embedding_store=store,
        similarity_service=WindowsSimilarity(),
        category_registry=CategoryRegistry(storage_root=tmp_path / "cats"),
        media_classifier=FakeClassifier(),
        config=CategorySuggestionConfig(minimum_support_count=1),
    )

    result = svc.suggest(src, [src, candidate], META)

    assert result.status == "suggested"
    assert result.suggested_category_id == "family_photo"
    assert canonical_photo_key(r"C:\PHOTOS\CONFIRMED.JPG") == canonical_photo_key(
        "c:/photos/confirmed.jpg"
    )


def test_debug_diagnostics_report_match_resolution_and_trust(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAMILY_MEMORY_DEBUG_SUGGESTIONS", "1")
    store = EmbeddingStore(tmp_path / "e.sqlite3")
    src = photo(tmp_path / "src.jpg")
    confirmed = photo(tmp_path / "confirmed.jpg", "family_photo", user=True)
    put(store, src, [1, 0, 0])
    put(store, confirmed, [0.99, 0, 0])

    service(tmp_path, store).suggest(src, [src, confirmed], META)

    diagnostic = capsys.readouterr().err
    assert "[CategorySuggestionMatch]" in diagnostic
    assert "filename=confirmed.jpg" in diagnostic
    assert "similarity=" in diagnostic
    assert "resolved=True" in diagnostic
    assert "raw_category='family_photo'" in diagnostic
    assert "normalized_category='family_photo'" in diagnostic
    assert "trust=user_correction" in diagnostic
    assert "accepted=True" in diagnostic


def test_album_review_category_apply_normalizes_display_label_before_persisting():
    ui = Path("src/ui/album_review_page.py").read_text()
    assert "def _normalize_category_id" in ui
    assert "category = self._normalize_category_id(" in ui
    apply_block = ui[
        ui.index("def _apply_category_to_rows") : ui.index(
            "def _refresh_after_category_change"
        )
    ]
    assert "category = self._normalize_category_id(category)" in apply_block
