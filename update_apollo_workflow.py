#!/usr/bin/env python3
"""
Update n8n Apollo workflow to search for Retail Marketing Directors
instead of Hedge Fund Portfolio Managers
"""

import sqlite3
import json
import sys
from datetime import datetime

DB_PATH = "/root/.n8n/database.sqlite"
WORKFLOW_ID = "C2kIA0mMISzcKnjC"

# New Apollo search configuration
NEW_SEARCH_CONFIG = {
    "per_page": 25,
    "person_titles": [
        "Marketing Director",
        "Director of Marketing",
        "Head of Marketing",
        "VP Marketing",
        "Vice President of Marketing",
        "Chief Marketing Officer",
        "CMO"
    ],
    "person_locations": [
        "United States",
        "United Kingdom",
        "Germany",
        "France",
        "Canada",
        "Italy",
        "Spain"
    ],
    "organization_industry_tag_ids": ["retail"],
    "contact_email_status": ["verified"],
    "organization_num_employees_ranges": [
        "51,200",
        "201,500",
        "501,1000",
        "1001,5000",
        "5001,10000"
    ]
}

def backup_database():
    """Create backup before making changes"""
    import shutil
    backup_path = f"{DB_PATH}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def update_workflow():
    """Update Apollo search node in workflow"""

    print("🔧 Updating Apollo workflow configuration...")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get current workflow
    cursor.execute("SELECT nodes FROM workflow_entity WHERE id = ?", (WORKFLOW_ID,))
    result = cursor.fetchone()

    if not result:
        print(f"❌ Workflow {WORKFLOW_ID} not found!")
        return False

    # Parse nodes JSON
    nodes = json.loads(result[0])
    print(f"📊 Found {len(nodes)} nodes in workflow")

    # Find and update Apollo Search node
    updated = False
    for node in nodes:
        if node.get('name') == 'Apollo Search':
            print(f"🎯 Found Apollo Search node: {node['id']}")

            # Show old config
            old_body = json.loads(node['parameters']['jsonBody'])
            print(f"\n📋 OLD CONFIG:")
            print(f"   Titles: {old_body.get('person_titles', [])}")
            print(f"   Locations: {old_body.get('person_locations', [])}")

            # Update jsonBody
            node['parameters']['jsonBody'] = json.dumps(NEW_SEARCH_CONFIG)

            print(f"\n✨ NEW CONFIG:")
            print(f"   Titles: {NEW_SEARCH_CONFIG['person_titles']}")
            print(f"   Locations: {NEW_SEARCH_CONFIG['person_locations']}")
            print(f"   Industry: {NEW_SEARCH_CONFIG['organization_industry_tag_ids']}")
            print(f"   Email Status: {NEW_SEARCH_CONFIG['contact_email_status']}")

            updated = True
            break

    if not updated:
        print("❌ Apollo Search node not found in workflow!")
        return False

    # Save updated workflow
    updated_nodes_json = json.dumps(nodes)
    cursor.execute(
        "UPDATE workflow_entity SET nodes = ?, updatedAt = CURRENT_TIMESTAMP WHERE id = ?",
        (updated_nodes_json, WORKFLOW_ID)
    )
    conn.commit()
    conn.close()

    print("\n✅ Workflow updated successfully!")
    print(f"🔄 Restart n8n to apply changes: docker restart n8n")

    return True

def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Apollo Workflow Update - Retail Marketing Directors ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()

    # Check if running as root (needed for /root/.n8n access)
    import os
    if os.geteuid() != 0:
        print("❌ This script must be run as root (sudo)")
        print("   Run: sudo python3 update_apollo_workflow.py")
        sys.exit(1)

    # Create backup
    backup_path = backup_database()

    # Update workflow
    success = update_workflow()

    if success:
        print("\n" + "="*60)
        print("🎉 SUCCESS! Workflow updated to target:")
        print("   - Retail Marketing Directors")
        print("   - 7,800 potential leads in Apollo")
        print("   - Verified emails only")
        print()
        print("📋 Next steps:")
        print("   1. Restart n8n: docker restart n8n")
        print("   2. Wait 30 seconds")
        print("   3. Check executions: workflow will run at next schedule")
        print("   4. Monitor: ./check_apollo_simple.sh")
        print()
        print(f"💾 Backup saved: {backup_path}")
        print("="*60)
    else:
        print("\n❌ Update failed! Database unchanged.")
        print(f"💾 Backup available: {backup_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()
