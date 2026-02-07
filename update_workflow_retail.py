#!/usr/bin/env python3
"""
Update n8n Apollo workflow FLOW 7 to use correct camelCase field names
for Retail Marketing Directors search
"""

import sqlite3
import json
import sys
from datetime import datetime

DB_PATH = "/root/.n8n/database.sqlite"
WORKFLOW_ID = "C2kIA0mMISzcKnjC"

# New Apollo search configuration with correct field names
NEW_SEARCH_CONFIG = {
    "per_page": 25,
    "personTitles": [
        "Marketing Director",
        "Head of Marketing",
        "VP Marketing",
        "CMO"
    ],
    "personLocations": [
        "United States",
        "United Kingdom",
        "Germany",
        "France",
        "Canada"
    ],
    "organizationIndustryTagIds": ["retail"],
    "contactEmailStatusV2": ["verified"],
    "organizationNumEmployeesRanges": [
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
    """Update Apollo search node with camelCase field names"""

    print("🔧 Updating Apollo workflow with camelCase field names...")

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
            try:
                old_body = json.loads(node['parameters']['jsonBody'])
                print(f"\n📋 OLD CONFIG:")
                print(f"   Field names: {list(old_body.keys())}")
                if 'organization_industry_tag_ids' in old_body:
                    print(f"   Industry (old): {old_body.get('organization_industry_tag_ids')}")
                if 'contact_email_status' in old_body:
                    print(f"   Email status (old): {old_body.get('contact_email_status')}")
            except:
                print(f"\n📋 OLD CONFIG: (could not parse)")

            # Update jsonBody with camelCase fields
            node['parameters']['jsonBody'] = json.dumps(NEW_SEARCH_CONFIG)

            print(f"\n✨ NEW CONFIG:")
            print(f"   organizationIndustryTagIds: {NEW_SEARCH_CONFIG['organizationIndustryTagIds']}")
            print(f"   contactEmailStatusV2: {NEW_SEARCH_CONFIG['contactEmailStatusV2']}")
            print(f"   personTitles: {NEW_SEARCH_CONFIG['personTitles']}")
            print(f"   personLocations: {NEW_SEARCH_CONFIG['personLocations']}")

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
    print(f"🔄 Restart n8n: docker restart n8n")

    return True

def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Apollo Workflow Update - Retail (camelCase fields)  ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()

    # Check if running as root (needed for /root/.n8n access)
    import os
    if os.geteuid() != 0:
        print("❌ This script must be run as root (sudo)")
        print("   Run: sudo python3 update_workflow_retail.py")
        sys.exit(1)

    # Create backup
    backup_path = backup_database()

    # Update workflow
    success = update_workflow()

    if success:
        print("\n" + "="*60)
        print("🎉 SUCCESS! Workflow updated with:")
        print("   ✅ organizationIndustryTagIds: retail")
        print("   ✅ contactEmailStatusV2: verified")
        print("   ✅ personTitles: 4 retail marketing titles")
        print()
        print("📋 Next steps:")
        print("   1. docker restart n8n")
        print("   2. Wait for next scheduled run (23:00 UTC)")
        print("   3. OR trigger manually from n8n UI")
        print("   4. Monitor: ./check_apollo_simple.sh")
        print()
        print(f"💾 Backup: {backup_path}")
        print("="*60)
    else:
        print("\n❌ Update failed! Database unchanged.")
        print(f"💾 Backup available: {backup_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()
