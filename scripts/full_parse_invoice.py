#!/usr/bin/env python3
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

async def full_parse():
    config = Config()
    config.prompt_header_path = Path("/app/prompts/header_v9.txt")

    print(f"Using model: {config.gemini_model}")
    print(f"Header prompt: {config.prompt_header_path}\n")

    orchestrator = Orchestrator(config)

    file_path = Path(config.invoices_dir) / "invoice.jpg"

    print(f"Processing: {file_path}")
    print("="*80)

    result = await orchestrator.process_document(file_path)

    if result.get("success"):
        print("\n✅ Parsing successful!")
        print(f"Document ID: {result.get('document_id')}")
        print(f"Output file: {result.get('output_file')}")
        print(f"Elapsed time: {result.get('elapsed_time', 0):.2f}s")

        # Show header structure
        data = result.get("data", {})
        header = {
            "document_info": data.get("document_info", {}),
            "parties": data.get("parties", {}),
            "references": data.get("references", {})
        }

        print("\n" + "="*80)
        print("HEADER DATA:")
        print("="*80)
        print(json.dumps(header, ensure_ascii=False, indent=2))
    else:
        print(f"\n❌ Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(full_parse())








