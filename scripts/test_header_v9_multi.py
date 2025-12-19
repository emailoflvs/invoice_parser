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
logger = logging.getLogger("test_v9_multi")

async def test_document(orchestrator, file_path, test_name):
    """Test a single document and return header data"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing: {test_name} ({file_path.name})")
    logger.info(f"{'='*80}")

    try:
        result = await orchestrator.process_document(file_path)

        if not result.get("success"):
            logger.error(f"❌ Failed: {result.get('error')}")
            return None

        # Data is directly in result["data"], not in result["data"]["header"]
        data = result.get("data", {})
        # Extract only header-related fields
        header_data = {
            "document_info": data.get("document_info", {}),
            "parties": data.get("parties", {}),
            "references": data.get("references", {}),
            "signatures": data.get("signatures", []),
            "totals": data.get("totals", {}),
            "amounts_in_words": data.get("amounts_in_words", {}),
            "other_fields": data.get("other_fields", [])
        }

        # Save individual result
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"header_v9_{file_path.stem}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(header_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Saved to: {output_file}")

        return {
            "file": file_path.name,
            "header": header_data,
            "success": True
        }

    except Exception as e:
        logger.error(f"❌ Error processing {file_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "file": file_path.name,
            "error": str(e),
            "success": False
        }

async def run_tests():
    try:
        config = Config()
        config.prompt_header_path = Path("/app/prompts/header_v9.txt")

        logger.info(f"Model: {config.gemini_model}")
        logger.info(f"Header Prompt: {config.prompt_header_path}")

        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Config error: {e}")
        sys.exit(1)

    # Test files
    test_files = [
        ("invoice.jpg", "Ukrainian Invoice"),
        ("french_invoice.jpg", "French Invoice"),
        ("karinka.jpg", "Karinka Invoice")
    ]

    invoices_dir = Path(config.invoices_dir)
    results = []

    for filename, test_name in test_files:
        file_path = invoices_dir / filename

        if not file_path.exists():
            logger.warning(f"⚠️  File not found: {file_path}, skipping...")
            continue

        result = await test_document(orchestrator, file_path, test_name)
        if result:
            results.append(result)

    # Print summary
    logger.info(f"\n{'='*80}")
    logger.info("SUMMARY")
    logger.info(f"{'='*80}")

    for result in results:
        if result.get("success"):
            header = result.get("header", {})
            logger.info(f"\n✅ {result['file']}:")
            logger.info(f"   - document_info keys: {list(header.get('document_info', {}).keys())}")
            logger.info(f"   - parties keys: {list(header.get('parties', {}).keys())}")

            # Show sample structure
            doc_info = header.get("document_info", {})
            if doc_info:
                doc_type = doc_info.get("document_type", {})
                if isinstance(doc_type, dict):
                    logger.info(f"   - document_type structure: {type(doc_type).__name__}")
                    logger.info(f"   - document_type has _label: {'_label' in doc_type}")
                    logger.info(f"   - document_type value: {doc_type.get('value', 'N/A')[:50]}")
        else:
            logger.error(f"❌ {result['file']}: {result.get('error', 'Unknown error')}")

    # Save combined results
    output_dir = Path("output")
    summary_file = output_dir / "header_v9_test_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_results": results,
            "total_tested": len(results),
            "successful": len([r for r in results if r.get("success")]),
            "failed": len([r for r in results if not r.get("success")])
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"\n📄 Full summary saved to: {summary_file}")

if __name__ == "__main__":
    asyncio.run(run_tests())

