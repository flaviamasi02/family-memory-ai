from pathlib import Path

from core.category_suggestion_service import (
    CategorySuggestionConfig,
    CategorySuggestionService,
)
from core.category_registry import CategoryRegistry
from core.user_metadata_service import UserMetadataService
from types import SimpleNamespace


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
    deterministic=False
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
    assert "_apply_category_to_rows" in ui and "result.suggested_category_id" in ui
    assert ui.count("addTab") == 0
    assert main.count("Memory Review") >= 1


def test_stale_async_result_guard_and_cache_reuse_are_present():
    ui = Path("src/ui/album_review_page.py").read_text()
    svc = Path("src/core/category_suggestion_service.py").read_text()
    assert "request_id != self._suggestion_request_id" in ui
    assert "self._details_key != self._row_key(row)" in ui
    assert "if cache_key in self._cache" in svc
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
    main = Path("src/ui/main_window.py").read_text()
    ui = Path("src/ui/album_review_page.py").read_text()
    complete_block = main[
        main.index("def _on_embedding_complete") : main.index("def _on_embedding_error")
    ]
    assert "self.status_label.setText" in complete_block
    assert "Semantic embeddings indexed" in complete_block
    assert "Indexing semantic embeddings" not in complete_block
    assert "self._on_embedding_index_updated(result)" in complete_block
    assert "def _on_embedding_index_updated" in main
    assert "review_page.on_embedding_index_updated()" in main
    assert "def on_embedding_index_updated" in ui
    assert "self._category_suggestion_service.invalidate_cache()" in ui
    assert "self._request_category_suggestion(row)" in ui


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
    main = Path("src/ui/main_window.py").read_text()
    refresh_block = main[
        main.index("def _on_embedding_index_updated") : main.index(
            "def _on_embedding_error"
        )
    ]
    assert 'getattr(self, "review_page", None)' in refresh_block
    assert "self.review_page.on_embedding_index_updated()" not in refresh_block
    assert "review_page.on_embedding_index_updated()" in refresh_block


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
