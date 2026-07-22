from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vision.embedding_provider import EmbeddingStore, FakeEmbeddingProvider
from vision.evaluation_sources import folder_image_paths
from vision.mobileclip_provider import MobileCLIPEmbeddingProvider
from vision.semantic_similarity_service import SemanticSimilarityService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print most similar images using already persisted MobileCLIP embeddings.")
    parser.add_argument("source", type=Path, help="Source image with an existing embedding.")
    parser.add_argument("folder", type=Path, help="Folder or indexed library path used to restrict candidate images.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of matches to print.")
    parser.add_argument("--min-similarity", type=float, default=None, help="Optional minimum cosine similarity.")
    parser.add_argument("--include-source", action="store_true", help="Include the source image if it is in the candidates.")
    parser.add_argument("--provider", choices=("mobileclip", "fake"), default="mobileclip", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    provider = FakeEmbeddingProvider() if args.provider == "fake" else MobileCLIPEmbeddingProvider()
    candidates = folder_image_paths(args.folder, 1_000_000) if args.folder.is_dir() else [args.folder]
    results = SemanticSimilarityService(EmbeddingStore()).most_similar(
        args.source,
        provider.metadata,
        candidates=candidates,
        limit=max(1, args.limit),
        exclude_source=not args.include_source,
        minimum_similarity=args.min_similarity,
    )

    print(f"source={args.source}")
    print(f"model_key={provider.metadata.model_key}")
    print(f"candidate_images={len(candidates)}")
    print(f"results={len(results)}")
    for idx, result in enumerate(results, start=1):
        print(f"{idx}\tscore={result.similarity:.6f}\timage={result.photo_key}")
    if not results:
        print("No matches found. Ensure source and candidate embeddings already exist for this exact model key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
