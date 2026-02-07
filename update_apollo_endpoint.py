#!/usr/bin/env python3
"""
Update Apollo workflow to use new API endpoint:
/mixed_people/search (deprecated) → /mixed_people/api_search (new)
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = "/root/.n8n/database.sqlite"
WORKFLOW_ID = "C2kIA0mMISzcKnjC"

OLD_ENDPOINT = "https://api.apollo.io/api/v1/mixed_people/search"
NEW_ENDPOINT = "https://api.apollo.io/api/v1/mixed_people/api_search"

def update_endpoint():
    """Update Apollo Search node endpoint"""

    print("🔧 Updating Apollo API endpoint...")

    # Backup
    import shutil
    backup_path = f"{DB_PATH}.backup.endpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Backup: {backup_path}")

    # Connect
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get workflow
    cursor.execute("SELECT nodes FROM workflow_entity WHERE id = ?", (WORKFLOW_ID,))
    result = cursor.fetchone()

    if not result:
        print(f"❌ Workflow not found!")
        return False

    # Parse and update
    nodes = json.loads(result[0])
    updated = False

    for node in nodes:
        if node.get('name') == 'Apollo Search':
            old_url = node['parameters']['url']
            node['parameters']['url'] = NEW_ENDPOINT

            print(f"\n📝 Apollo Search node updated:")
            print(f"   OLD: {old_url}")
            print(f"   NEW: {NEW_ENDPOINT}")
            updated = True
            break

    if not updated:
        print("❌ Apollo Search node not found!")
        return False

    # Save
    cursor.execute(
        "UPDATE workflow_entity SET nodes = ?, updatedAt = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(nodes), WORKFLOW_ID)
    )
    conn.commit()
    conn.close()

    print("✅ Endpoint updated!")
    return True

if __name__ == "__main__":
    print("╔════════════════════════════════════════╗")
    print("║  Apollo Endpoint Update - New API     ║")
    print("╚════════════════════════════════════════╝\n")

    import os
    if os.geteuid() != 0:
        print("❌ Run as root: sudo python3 update_apollo_endpoint.py")
        exit(1)

    if update_endpoint():
        print("\n" + "="*50)
        print("✅ SUCCESS! Restart n8n:")
        print("   docker restart n8n")
        print("="*50)
    else:
        print("\n❌ Update failed!")
