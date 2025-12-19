#!/usr/bin/env python3
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

async def parse_invoice():
    config = Config()
    config.prompt_header_path = Path("/app/prompts/header_v9.txt")

    orchestrator = Orchestrator(config)

    file_path = Path(config.invoices_dir) / "invoice.jpg"
    result = await orchestrator.process_document(file_path)

    if result.get("success"):
        data = result.get("data", {})
        header = {
            "document_info": data.get("document_info", {}),
            "parties": data.get("parties", {}),
            "references": data.get("references", {}),
            "signatures": data.get("signatures", []),
            "totals": data.get("totals", {}),
            "amounts_in_words": data.get("amounts_in_words", {}),
            "other_fields": data.get("other_fields", [])
        }
        print(json.dumps(header, ensure_ascii=False, indent=2))
    else:
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(parse_invoice())








