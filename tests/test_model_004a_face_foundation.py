import json
from pathlib import Path

import pytest

from faces.models import BoundingBox, Face, FaceCluster, FaceEmbedding, FaceLandmark, Person
from faces.persistence import SQLiteFaceRepository
from faces.repositories import ClusterRepository, FaceEmbeddingRepository, FaceRepository, PersonRepository
from faces.services import (
    FaceClusteringService,
    FaceDetectionProvider,
    FaceEmbeddingProvider,
    NoOpFaceClusteringService,
    NoOpFaceDetectionProvider,
    PersonManagementService,
    RepositoryPersonManagementService,
    UnavailableFaceEmbeddingProvider,
)


def make_repository(tmp_path: Path) -> SQLiteFaceRepository:
    return SQLiteFaceRepository(tmp_path / "faces.sqlite3")


def make_face(image_id: str = "image-1", fingerprint: str = "fingerprint-1") -> Face:
    return Face(
        image_id=image_id,
        source_fingerprint=fingerprint,
        bounding_box=BoundingBox(10, 20, 100, 120),
        detection_confidence=0.91,
        detector_key="future-detector|v1",
        landmarks=(FaceLandmark("left_eye", 35, 50, 0.8),),
        quality_metrics={"sharpness": 0.75, "pose": 0.6},
    )


def test_domain_ids_are_stable_and_distinct():
    first = make_face()
    second = make_face()
    person = Person(name="Ada")
    cluster = FaceCluster(label="Group 1")

    assert first.id != second.id
    assert len({first.id, person.id, cluster.id}) == 3
    assert Face.from_dict(first.to_dict()).id == first.id
    assert Person.from_dict(person.to_dict()).id == person.id
    assert FaceCluster.from_dict(cluster.to_dict()).id == cluster.id


def test_face_json_serialization_preserves_extensible_detection_data():
    face = make_face()
    restored = Face.from_dict(json.loads(json.dumps(face.to_dict())))

    assert restored.bounding_box == BoundingBox(10, 20, 100, 120)
    assert restored.landmarks[0].kind == "left_eye"
    assert restored.quality_metrics == {"sharpness": 0.75, "pose": 0.6}
    assert restored.detection_confidence == 0.91


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_domain_rejects_invalid_confidence(value):
    with pytest.raises(ValueError):
        Face(image_id="image", bounding_box=BoundingBox(0, 0, 1, 1), detection_confidence=value)


def test_embedding_is_versioned_and_validates_dimension():
    embedding = FaceEmbedding("face", "provider", "model", "r1", 3, (0.1, 0.2, 0.3))
    assert embedding.model_key == "provider|model|r1|dim=3"
    assert FaceEmbedding.from_dict(embedding.to_dict()).vector == embedding.vector
    with pytest.raises(ValueError):
        FaceEmbedding("face", "provider", "model", "r1", 2, (0.1,))


def test_repository_contracts_are_runtime_compatible(tmp_path):
    repository = make_repository(tmp_path)
    assert isinstance(repository, FaceRepository)
    assert isinstance(repository, PersonRepository)
    assert isinstance(repository, ClusterRepository)
    assert isinstance(repository, FaceEmbeddingRepository)


def test_multiple_faces_per_image_and_queries(tmp_path):
    repository = make_repository(tmp_path)
    person = repository.save_person(Person(name="Ada"))
    cluster = repository.save_cluster(FaceCluster(label="Candidate"))
    first = make_face()
    second = make_face()
    first.person_id = person.id
    first.cluster_id = cluster.id
    repository.save_face(first)
    repository.save_face(second)

    assert [item.id for item in repository.faces_for_image("image-1")] == [first.id, second.id]
    assert repository.faces_for_person(person.id)[0].id == first.id
    assert repository.faces_for_cluster(cluster.id)[0].id == first.id
    assert repository.unassigned_faces()[0].id == second.id


def test_repository_upserts_records_without_changing_ids(tmp_path):
    repository = make_repository(tmp_path)
    face = repository.save_face(make_face())
    face.quality_metrics["sharpness"] = 0.95
    face.revision += 1
    repository.save_face(face)

    stored = repository.get_face(face.id)
    assert stored is not None
    assert stored.id == face.id
    assert stored.revision == 2
    assert stored.quality_metrics["sharpness"] == 0.95


def test_person_and_cluster_delete_clear_assignments(tmp_path):
    repository = make_repository(tmp_path)
    person = repository.save_person(Person(name="Ada"))
    cluster = repository.save_cluster(FaceCluster(label="Candidate", person_id=person.id))
    face = make_face()
    face.person_id, face.cluster_id = person.id, cluster.id
    repository.save_face(face)

    assert repository.delete_person(person.id)
    assert repository.get_face(face.id).person_id is None
    assert repository.get_cluster(cluster.id).person_id is None
    assert repository.delete_cluster(cluster.id)
    assert repository.get_face(face.id).cluster_id is None


def test_embedding_cache_supports_models_staleness_and_retraining(tmp_path):
    repository = make_repository(tmp_path)
    face = repository.save_face(make_face())
    old = FaceEmbedding(face.id, "provider", "model", "r1", 2, (0.1, 0.2), face.source_fingerprint)
    new = FaceEmbedding(face.id, "provider", "model", "r2", 2, (0.3, 0.4), face.source_fingerprint)
    repository.save_embedding(old)
    repository.save_embedding(new)

    assert repository.get_embedding(face.id, old.model_key).vector == pytest.approx(old.vector)
    assert len(repository.embeddings_for_model(old.model_key)) == 1
    face.source_fingerprint = "changed-source"
    repository.save_face(face)
    assert repository.embeddings_for_model(old.model_key) == []
    assert len(repository.embeddings_for_model(old.model_key, only_current=False)) == 1
    assert repository.invalidate_model_embeddings(old.model_key) == 1
    assert repository.get_embedding(face.id, old.model_key).status == "stale"


def test_deleting_image_faces_cascades_embedding_cache(tmp_path):
    repository = make_repository(tmp_path)
    face = repository.save_face(make_face())
    embedding = repository.save_embedding(FaceEmbedding(face.id, "p", "m", "1", 1, (0.2,), face.source_fingerprint))

    assert repository.delete_faces_for_image(face.image_id) == 1
    assert repository.get_face(face.id) is None
    assert repository.get_embedding(face.id, embedding.model_key) is None


def test_person_management_supports_manual_naming_and_assignments(tmp_path):
    repository = make_repository(tmp_path)
    face = repository.save_face(make_face())
    service = RepositoryPersonManagementService(repository, repository)
    person = service.create_person(" Ada ")

    assert person.name == "Ada"
    assert service.rename_person(person.id, "Ada Lovelace").name == "Ada Lovelace"
    assert service.assign_face(face.id, person.id).person_id == person.id
    assert service.assign_face(face.id, None).person_id is None


def test_service_interfaces_and_placeholders_do_no_ai_work():
    detector = NoOpFaceDetectionProvider()
    embedder = UnavailableFaceEmbeddingProvider()
    clusterer = NoOpFaceClusteringService()

    assert isinstance(detector, FaceDetectionProvider)
    assert isinstance(embedder, FaceEmbeddingProvider)
    assert isinstance(clusterer, FaceClusteringService)
    assert detector.detect(Path("not-read.jpg")) == ()
    assert embedder.embed(Path("not-read.jpg"), ()) == ()
    with pytest.raises(RuntimeError, match="MODEL-004A"):
        embedder.embed(Path("not-read.jpg"), (make_face(),))
    existing = (FaceCluster(label="Existing"),)
    assert clusterer.cluster((), existing) == existing


def test_person_service_satisfies_contract(tmp_path):
    repository = make_repository(tmp_path)
    assert isinstance(RepositoryPersonManagementService(repository, repository), PersonManagementService)
