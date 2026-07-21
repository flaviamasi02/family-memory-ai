from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vision.batch_embedding_service import BatchEmbeddingService
from vision.embedding_provider import FakeEmbeddingProvider
from vision.evaluation_sources import folder_image_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate persistent MobileCLIP embeddings for a small diagnostic image folder.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--provider", choices=("mobileclip", "fake"), default="mobileclip", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    paths = folder_image_paths(args.folder, max(1, min(300, args.limit)))
    service = BatchEmbeddingService(provider=FakeEmbeddingProvider() if args.provider == "fake" else None)
    result = service.embed_images(paths)
    print(f"total_discovered={len(paths)}")
    print(f"processed={result.processed_successfully}")
    print(f"cached={result.skipped_cached}")
    print(f"failed={result.failed}")
    print(f"cancelled={result.cancelled}")
    print(f"elapsed_seconds={result.elapsed_seconds:.3f}")
    print(f"embedding_dimension={service.provider.metadata.embedding_dimension}")
    for outcome in result.outcomes:
        if outcome.status == "failed":
            print(f"failed_image={outcome.image}: {outcome.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
