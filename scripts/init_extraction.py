#!/usr/bin/env python3
"""Initial extraction script to process the entire vault."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.config import settings
from backend.extraction.pipeline import ExtractionPipeline


def main():
    """Run initial extraction of the vault."""
    print("=" * 60)
    print("Personal Agent - Initial Vault Extraction")
    print("=" * 60)

    # Check vault exists
    vault_path = Path(settings.vault_path)
    if not vault_path.exists():
        print(f"Error: Vault not found at {vault_path}")
        return 1

    # Create pipeline
    print(f"\nVault path: {vault_path}")
    print("Initializing extraction pipeline...")

    pipeline = ExtractionPipeline(
        vault_path=vault_path,
        use_llm=True,
        use_vision=False,  # Disable vision for initial extraction (faster)
    )

    # Scan vault
    print("\nScanning vault...")
    stats = pipeline.scan_vault()

    print(f"\nVault contents:")
    print(f"  Projects (folders): {stats.get('projects', 0)}")
    print(f"  Markdown files:     {stats.get('.md', 0)}")
    print(f"  PDF files:          {stats.get('.pdf', 0)}")
    print(f"  Word documents:     {stats.get('.docx', 0)}")
    print(f"  PowerPoints:        {stats.get('.pptx', 0)}")
    print(f"  Images:             {stats.get('.png', 0) + stats.get('.jpg', 0) + stats.get('.jpeg', 0)}")
    print(f"  Total files:        {stats.get('total_files', 0)}")

    # Confirm
    print("\nThis will process all files and build the knowledge graph.")
    response = input("Continue? [y/N]: ")

    if response.lower() != 'y':
        print("Aborted.")
        return 0

    # Progress callback
    def progress(current, total, file_path):
        pct = (current / total) * 100 if total > 0 else 0
        file_name = Path(file_path).name[:40]
        print(f"\r[{pct:5.1f}%] {current}/{total} - {file_name:<40}", end="", flush=True)

    # Run extraction
    print("\nStarting extraction...")
    print("-" * 60)

    try:
        result = pipeline.process_vault(
            parallel=True,
            max_workers=4,
            progress_callback=progress,
        )

        print("\n" + "-" * 60)
        print("\nExtraction complete!")
        print(f"\nResults:")
        print(f"  Files processed: {result.get('processed', 0)}")
        print(f"  Files failed:    {result.get('failed', 0)}")
        print(f"  Projects:        {result.get('projects', 0)}")
        print(f"  Documents:       {result.get('documents', 0)}")
        print(f"  Concepts:        {result.get('concepts', 0)}")
        print(f"  People:          {result.get('people', 0)}")

        print("\nKnowledge graph is ready!")
        print("Start the API server with: uv run python -m backend.main")
        print("Then access Neo4j browser at: http://localhost:7474")

    except Exception as e:
        print(f"\n\nError during extraction: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        pipeline.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
