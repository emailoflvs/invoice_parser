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
logger = logging.getLogger("test_invoice_v9")

async def test_invoice():
    try:
        config = Config()
        config.prompt_header_path = Path("/app/prompts/header_v9.txt")
        
        logger.info(f"Model: {config.gemini_model}")
        logger.info(f"Header Prompt: {config.prompt_header_path}")
        
        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Config error: {e}")
        sys.exit(1)
    
    # Test file
    test_file = "invoice.jpg"
    file_path = Path(config.invoices_dir) / test_file
    
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing: {test_file}")
    logger.info(f"{'='*80}\n")
    
    try:
        result = await orchestrator.process_document(file_path)
        
        if not result.get("success"):
            logger.error(f"❌ Failed: {result.get('error')}")
            return
        
        # Extract header data
        data = result.get("data", {})
        header_data = {
            "document_info": data.get("document_info", {}),
            "parties": data.get("parties", {}),
            "references": data.get("references", {}),
            "signatures": data.get("signatures", []),
            "totals": data.get("totals", {}),
            "amounts_in_words": data.get("amounts_in_words", {}),
            "other_fields": data.get("other_fields", [])
        }
        
        # Print header data
        print("\n" + "="*80)
        print("HEADER DATA (JSON):")
        print("="*80)
        print(json.dumps(header_data, ensure_ascii=False, indent=2))
        
        # Print summary
        print("\n" + "="*80)
        print("SUMMARY:")
        print("="*80)
        
        doc_info = header_data.get("document_info", {})
        if doc_info:
            print("\n📄 Document Info:")
            for key, value in doc_info.items():
                if isinstance(value, dict):
                    label = value.get("_label", "N/A")
                    val = value.get("value", "N/A")
                    print(f"  - {key}:")
                    print(f"    _label: {label}")
                    print(f"    value: {val}")
        
        parties = header_data.get("parties", {})
        if parties:
            print(f"\n👥 Parties ({len(parties)}):")
            for role, party_data in parties.items():
                party_label = party_data.get("_label", "N/A")
                print(f"  - {role}:")
                print(f"    _label: {party_label}")
                fields = {k: v for k, v in party_data.items() if k != "_label"}
                print(f"    Fields: {list(fields.keys())}")
                for field_name, field_value in fields.items():
                    if isinstance(field_value, dict):
                        label = field_value.get("_label", "N/A")
                        val = field_value.get("value", "N/A")
                        if val and val != "N/A":
                            print(f"      {field_name}:")
                            print(f"        _label: {label}")
                            print(f"        value: {val[:80]}{'...' if len(str(val)) > 80 else ''}")
        
        references = header_data.get("references", {})
        if references:
            print(f"\n📋 References ({len(references)}):")
            for key, value in references.items():
                if isinstance(value, dict):
                    label = value.get("_label", "N/A")
                    val = value.get("value", "N/A")
                    print(f"  - {key}: {label} -> {val}")
        
        signatures = header_data.get("signatures", [])
        if signatures:
            print(f"\n✍️  Signatures ({len(signatures)}):")
            for sig in signatures:
                print(f"  - Signed: {sig.get('is_signed', False)}, Stamped: {sig.get('is_stamped', False)}")
        
        # Save to file
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "header_v9_invoice_full.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(header_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n✅ Full result saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_invoice())








