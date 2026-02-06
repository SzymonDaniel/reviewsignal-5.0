#!/usr/bin/env python3
"""
Export Email Sequences to Instantly.ai Format
==============================================
Converts our JSON sequences to Instantly-compatible format for import.

Usage:
    python export_to_instantly.py --sequence portfolio_manager
    python export_to_instantly.py --all --output instantly_export/

Author: ReviewSignal.ai
"""

import json
import os
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


SEQUENCES_DIR = Path(__file__).parent.parent / "email_templates" / "sequences"
OUTPUT_DIR = Path(__file__).parent.parent / "exports" / "instantly"


def load_sequence(name: str) -> Dict:
    """Load a sequence JSON file"""
    filepath = SEQUENCES_DIR / f"{name}_sequence.json"
    if not filepath.exists():
        raise FileNotFoundError(f"Sequence not found: {filepath}")

    with open(filepath) as f:
        return json.load(f)


def convert_to_instantly_format(sequence: Dict) -> Dict:
    """
    Convert our sequence format to Instantly.ai campaign format.

    Instantly expects:
    - campaign_name
    - email_list
    - sequences (array of email steps)
    """
    instantly_sequence = {
        "campaign_name": f"ReviewSignal - {sequence['sequence_name']}",
        "segment": sequence.get("segment", "general"),
        "target_titles": sequence.get("target_titles", []),
        "settings": {
            "send_as_reply": True,
            "track_opens": True,
            "track_clicks": True,
            "stop_on_reply": True,
            "stop_on_auto_reply": False,
            "daily_limit": 50,
            "sending_window": {
                "start_hour": 9,
                "end_hour": 17,
                "timezone": "America/New_York",
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
            }
        },
        "steps": []
    }

    for i, email in enumerate(sequence["emails"]):
        step = {
            "step_number": email["step"],
            "delay_days": sequence["delay_days"][i] if i < len(sequence["delay_days"]) else 3,
            "subject": email["subject"],
            "body": email["body_text"],
            "body_html": email.get("body_html", ""),
            "variants": []  # For A/B testing later
        }
        instantly_sequence["steps"].append(step)

    return instantly_sequence


def generate_csv_for_instantly(sequence: Dict) -> str:
    """
    Generate CSV format that can be pasted into Instantly sequence builder.

    Format:
    Step | Delay | Subject | Body
    """
    lines = ["Step,Delay (days),Subject,Body"]

    for i, email in enumerate(sequence["emails"]):
        delay = sequence["delay_days"][i] if i < len(sequence["delay_days"]) else 3
        subject = email["subject"].replace('"', '""')
        body = email["body_text"].replace('"', '""').replace('\n', '\\n')

        lines.append(f'{email["step"]},{delay},"{subject}","{body}"')

    return "\n".join(lines)


def generate_instantly_import_json(sequences: List[Dict]) -> str:
    """Generate JSON that can be imported to Instantly via API"""
    return json.dumps({
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "source": "ReviewSignal Email Template System",
        "campaigns": [convert_to_instantly_format(seq) for seq in sequences]
    }, indent=2)


def list_available_sequences() -> List[str]:
    """List all available sequences"""
    sequences = []
    for f in SEQUENCES_DIR.glob("*_sequence.json"):
        name = f.stem.replace("_sequence", "")
        sequences.append(name)
    return sorted(sequences)


def main():
    parser = argparse.ArgumentParser(description='Export sequences to Instantly format')
    parser.add_argument('--sequence', type=str, help='Specific sequence to export')
    parser.add_argument('--all', action='store_true', help='Export all sequences')
    parser.add_argument('--list', action='store_true', help='List available sequences')
    parser.add_argument('--output', type=str, default=None, help='Output directory')
    parser.add_argument('--format', type=str, choices=['json', 'csv', 'both'], default='both')

    args = parser.parse_args()

    if args.list:
        print("\n📧 Available Email Sequences:")
        print("=" * 50)
        for seq in list_available_sequences():
            print(f"  • {seq}")
        print()
        return

    # Determine output directory
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load sequences
    sequences = []
    if args.all:
        for name in list_available_sequences():
            try:
                sequences.append(load_sequence(name))
                print(f"✅ Loaded: {name}")
            except Exception as e:
                print(f"❌ Failed to load {name}: {e}")
    elif args.sequence:
        sequences.append(load_sequence(args.sequence))
        print(f"✅ Loaded: {args.sequence}")
    else:
        print("Please specify --sequence NAME or --all")
        print("Use --list to see available sequences")
        return

    # Export
    print(f"\n📤 Exporting to {output_dir}...")

    if args.format in ['json', 'both']:
        # Export combined JSON
        json_path = output_dir / "instantly_campaigns.json"
        with open(json_path, 'w') as f:
            f.write(generate_instantly_import_json(sequences))
        print(f"  ✅ JSON: {json_path}")

        # Export individual JSON files
        for seq in sequences:
            name = seq.get('segment', 'unknown')
            individual_path = output_dir / f"{name}_campaign.json"
            with open(individual_path, 'w') as f:
                json.dump(convert_to_instantly_format(seq), f, indent=2)
            print(f"  ✅ JSON: {individual_path}")

    if args.format in ['csv', 'both']:
        # Export CSV files
        for seq in sequences:
            name = seq.get('segment', 'unknown')
            csv_path = output_dir / f"{name}_sequence.csv"
            with open(csv_path, 'w') as f:
                f.write(generate_csv_for_instantly(seq))
            print(f"  ✅ CSV: {csv_path}")

    print(f"\n✅ Export complete! Files in: {output_dir}")

    # Print summary
    print("\n📊 Summary:")
    print("=" * 50)
    for seq in sequences:
        print(f"  {seq['sequence_name']}")
        print(f"    Segment: {seq.get('segment', 'N/A')}")
        print(f"    Emails: {len(seq['emails'])}")
        print(f"    Targets: {', '.join(seq.get('target_titles', [])[:3])}")
        print()


if __name__ == "__main__":
    main()
