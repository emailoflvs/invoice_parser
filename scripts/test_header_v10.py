#!/usr/bin/env python3
import sys
import json
import logging
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_v10")

async def test_document(orchestrator, file_path):
    """Test a single document and return header data"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing: {file_path.name}")
    logger.info(f"{'='*80}")

    try:
        result = await orchestrator.process_document(file_path)

        if not result.get("success"):
            logger.error(f"❌ Failed: {result.get('error')}")
            return None

        data = result.get("data", {})
        # Extract fields
        header_data = {
            "document_info": data.get("document_info", {}),
            "parties": data.get("parties", {}),
            "references": data.get("references", {}),
            "signatures": data.get("signatures", []),
            "totals": data.get("totals", {}),
            "amounts_in_words": data.get("amounts_in_words", {}),
            "other_fields": data.get("other_fields", [])
        }

        # Save result
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"header_v10_{file_path.stem}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(header_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Saved to: {output_file}")

        # Verify Totals
        totals = header_data.get("totals", {})
        logger.info("\nChecking Totals:")
        for key, value in totals.items():
            if key == "_label": continue
            if isinstance(value, dict):
                logger.info(f"  - {key}: value={value.get('value')}, _label='{value.get('_label')}'")
            else:
                logger.warning(f"  - {key}: DIRECT VALUE (expected object): {value}")

        # Verify Amounts in Words
        amounts = header_data.get("amounts_in_words", {})
        logger.info("\nChecking Amounts in Words:")
        for key, value in amounts.items():
            if key == "_label": continue
            if isinstance(value, dict):
                logger.info(f"  - {key}: value='{str(value.get('value'))[:20]}...', _label='{value.get('_label')}'")
            else:
                logger.warning(f"  - {key}: DIRECT VALUE (expected object): {value}")

        return header_data

    except Exception as e:
        logger.error(f"❌ Error processing {file_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return None

async def run_tests():
    try:
        config = Config()
        config.prompt_header_path = Path("/app/prompts/header_v10.txt")
        # Ensure model is appropriate
        config.gemini_model = "gemini-2.0-flash-exp" # Or gemini-2.0-flash-thinking-exp if needed

        logger.info(f"Model: {config.gemini_model}")
        logger.info(f"Header Prompt: {config.prompt_header_path}")

        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Config error: {e}")
        sys.exit(1)

    # Test file
    invoices_dir = Path(config.invoices_dir)
    file_path = invoices_dir / "invoice.jpg"

    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return

    await test_document(orchestrator, file_path)

if __name__ == "__main__":
    asyncio.run(run_tests())









