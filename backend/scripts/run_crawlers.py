"""
Script to run all crawlers and collect financial knowledge data.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from crawlers.eastmoney_crawler import EastMoneyCrawler


async def save_results(results: List[Dict[str, Any]], output_dir: Path, source_name: str):
    """Save crawled results to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{source_name}_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"OK: Saved {len(results)} entries to {output_file}")
    return output_file


async def run_eastmoney_crawler(output_dir: Path):
    """Run EastMoney crawler."""
    print("\n[EastMoney Crawler]")
    print("Starting crawler...")

    crawler = EastMoneyCrawler(rate_limit=2.0)  # 2 seconds between requests

    try:
        results = await crawler.crawl()
        print(f"Crawled {len(results)} articles")

        if results:
            await save_results(results, output_dir, "eastmoney")
            return len(results)
        else:
            print("WARNING: No results collected")
            return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 0
    finally:
        # Close session if exists
        if crawler.session:
            await crawler.session.close()


async def main():
    """Main execution function."""
    print("=" * 60)
    print("Financial Knowledge Crawler")
    print("=" * 60)

    # Setup output directory
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "data" / "knowledge_base" / "raw"

    print(f"\nOutput directory: {output_dir}")

    # Run crawlers
    total_entries = 0

    # EastMoney
    count = await run_eastmoney_crawler(output_dir)
    total_entries += count

    # Summary
    print("\n" + "=" * 60)
    print(f"Total entries collected: {total_entries}")
    print("=" * 60)

    if total_entries > 0:
        print("\nOK: Crawling completed successfully")
        print(f"\nNext steps:")
        print(f"1. Review collected data in: {output_dir}")
        print(f"2. Run vectorization script to index the data")
    else:
        print("\nWARNING: No data collected. Check crawler configuration and network connection.")


if __name__ == "__main__":
    asyncio.run(main())
