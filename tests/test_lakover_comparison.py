import sys
import os
import logging
from pathlib import Path
import json
import time
from tabulate import tabulate

# Add src to python path
sys.path.append(str(Path(__file__).parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_comparison():
    # Config
    config = Config()
    config.mode = "TEST"

    print(f"DEBUG: PARALLEL_PARSING={config.parallel_parsing}")

    # DEBUG: Check which key is being loaded
    key_prefix = config.gemini_api_key[:5] if config.gemini_api_key else "None"
    print(f"DEBUG: Loaded GEMINI_API_KEY starting with: {key_prefix}...")

    # Ensure paths are correct absolute paths
    project_root = Path(__file__).parent
    config.prompts_dir = project_root / "prompts"
    config.invoices_dir = project_root / "invoices"
    config.output_dir = project_root / "output"
    # Use a local temp dir that is definitely writable and unique to avoid permission issues with previous root runs
    import tempfile
    config.temp_dir = Path(tempfile.mkdtemp(prefix="invoice_parser_test_"))
    config.logs_dir = project_root / "logs"
    config.examples_dir = project_root / "examples"
    config.prompt_header_path = config.prompts_dir / "header_v8.txt"

    # Create directories if they don't exist
    config.temp_dir.mkdir(parents=True, exist_ok=True)
    config.logs_dir.mkdir(parents=True, exist_ok=True)

    target_file = config.invoices_dir / "lakover.jpg"
    if not target_file.exists():
        logger.error(f"Target file not found: {target_file}")
        return

    prompts_to_test = ["v13"]
    results = []

    print(f"\n{'='*60}")
    print(f"STARTING FOCUSED TEST (v13 ONLY) ON {target_file.name}")
    print(f"{'='*60}\n")

    # No wait needed if key was changed
    # print("Waiting 45s for API quota to reset...", end="", flush=True)
    # time.sleep(45)
    # print(" Done.")

    for version in prompts_to_test:
        prompt_file = config.prompts_dir / f"items_{version}.txt"
        if not prompt_file.exists():
            logger.error(f"Prompt file not found: {prompt_file}")
            continue

        print(f"Testing {version}...", end="", flush=True)

        # Set current prompt
        config.prompt_items_path = prompt_file

        # Init orchestrator with new config
        orchestrator = Orchestrator(config)

        start_time = time.time()
        try:
            # Add delay to respect quota
            if len(results) > 0:
                print(" (waiting 10s for API)...", end="", flush=True)
                time.sleep(10)

            result = orchestrator.process_document(target_file)
            duration = time.time() - start_time

            if result["success"]:
                data = result["data"]
                # Normalize data access
                if hasattr(data, "model_dump"):
                    data_dict = data.model_dump()
                else:
                    data_dict = data

                # Extract items
                items = []
                if "line_items" in data_dict: # v10, v13 style
                    items = data_dict["line_items"]
                elif "items" in data_dict: # standard style
                    items = data_dict["items"]
                elif "table_data" in data_dict and "line_items" in data_dict["table_data"]:
                    items = data_dict["table_data"]["line_items"]

                # Check for RAW column usage
                raw_usage = 0
                raw_content = []
                column_mapping = data_dict.get("column_mapping", {})

                for item in items:
                    if "raw" in item and item["raw"]:
                        raw_usage += 1
                        raw_content.append(item["raw"])

                results.append({
                    "version": version,
                    "status": "SUCCESS",
                    "items_count": len(items),
                    "columns_found": list(column_mapping.keys()),
                    "raw_items": raw_usage,
                    "duration": f"{duration:.1f}s",
                    "raw_content_sample": raw_content,
                    "items_data": items  # Store full data for display
                })
                print(f" DONE ({len(items)} items)")
            else:
                results.append({
                    "version": version,
                    "status": "FAILED",
                    "error": result.get("error"),
                    "duration": f"{duration:.1f}s"
                })
                print(" FAILED")

        except Exception as e:
            print(f" ERROR: {e}")
            results.append({
                "version": version,
                "status": "ERROR",
                "error": str(e),
                "duration": "0s"
            })

    # Print Comparison Table
    print("\n\n" + "="*80)
    print("COMPARISON RESULT")
    print("="*80)

    table_data = []
    for res in results:
        if res["status"] == "SUCCESS":
            cols = len(res["columns_found"])
            raw_info = f"{res['raw_items']} used"
            table_data.append([
                res["version"],
                res["items_count"],
                cols,
                raw_info,
                res["duration"]
            ])
        else:
            table_data.append([res["version"], "FAILED", "-", res.get("error", "")[:30]+"...", res["duration"]])

    print(tabulate(table_data, headers=["Version", "Items", "Cols", "Raw Usage", "Time"], tablefmt="grid"))

    # Detailed v13 Analysis
    for res in results:
        if res["version"] == "v13" and res["status"] == "SUCCESS":
            print(f"\n\n=== v13 DETAILED ANALYSIS ===")
            print(f"Found {len(res['items_data'])} items.")

            if res['raw_items'] > 0:
                print(f"\n[SAFETY NET TRIGGERED] 'raw' column usage detected in {res['raw_items']} rows:")
                for i, content in enumerate(res['raw_content_sample']):
                     print(f"  Row {i+1}: {content}")
            else:
                print("\n[CLEAN PARSE] 'raw' column was empty (Safety Net not needed).")

            print("\nExtracted Items Preview:")
            for i, item in enumerate(res['items_data']):
                print(f"  Row {i+1}: {item}")


if __name__ == "__main__":
    run_comparison()

