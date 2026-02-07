#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Autonomous Agent - Daily Health Check
# Runs system analysis, generates reports, checks for optimizations
# ═══════════════════════════════════════════════════════════════

set -e

cd /home/info_betsim/reviewsignal-5.0

# Load environment
export $(grep -v '^#' .env | xargs)

# Run agent with daily check tasks
python3 -c "
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from agent.autonomous_agent import create_agent, create_task, ActionType, TaskPriority

async def daily_check():
    agent = create_agent()

    # Schedule daily tasks
    agent.schedule_task(create_task(
        name='Daily System Health Check',
        description='Check all services, database stats, API health',
        action_type=ActionType.MONITOR,
        priority=TaskPriority.HIGH
    ))

    agent.schedule_task(create_task(
        name='Performance Analysis',
        description='Analyze metrics, find bottlenecks, suggest optimizations',
        action_type=ActionType.ANALYZE,
        priority=TaskPriority.MEDIUM
    ))

    agent.schedule_task(create_task(
        name='Daily Executive Report',
        description='Generate summary: new data, leads, system status',
        action_type=ActionType.REPORT,
        priority=TaskPriority.MEDIUM
    ))

    print('🤖 Starting Autonomous Agent - Daily Check')
    print('   Tasks scheduled: 3')
    print('')

    # Run agent for max 10 minutes (enough for 3 tasks)
    try:
        await asyncio.wait_for(agent.start(), timeout=600)
    except asyncio.TimeoutError:
        print('✅ Daily check completed (timeout reached)')
    except Exception as e:
        print(f'⚠️  Error during daily check: {e}')
        return 1

    return 0

if __name__ == '__main__':
    exit(asyncio.run(daily_check()))
"

echo "✅ Agent daily check completed at $(date)"
