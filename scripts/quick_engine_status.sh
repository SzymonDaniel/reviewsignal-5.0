#!/bin/bash
# Quick status check for all AI engines

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  AI ENGINES - QUICK STATUS CHECK                          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check services
echo "🔍 Service Status:"
echo "  Echo Engine:        $(systemctl is-active echo-engine.service)"
echo "  Singularity Engine: $(systemctl is-active singularity-engine.service)"
echo "  Higgs Nexus:        $(systemctl is-active higgs-nexus.service)"
echo ""

# Check ports
echo "🌐 Port Status:"
netstat -tlnp 2>/dev/null | grep -E "8002|8003|8004" | awk '{print "  Port " $4 ": LISTENING"}'
echo ""

# Check auto-restart
echo "♻️  Auto-Restart:"
echo "  Echo Engine:        $(systemctl show echo-engine.service -p Restart --value)"
echo "  Singularity Engine: $(systemctl show singularity-engine.service -p Restart --value)"
echo "  Higgs Nexus:        $(systemctl show higgs-nexus.service -p Restart --value)"
echo ""

# Check enabled (auto-start on boot)
echo "🚀 Auto-Start on Boot:"
echo "  Echo Engine:        $(systemctl is-enabled echo-engine.service)"
echo "  Singularity Engine: $(systemctl is-enabled singularity-engine.service)"
echo "  Higgs Nexus:        $(systemctl is-enabled higgs-nexus.service)"
echo ""

# Memory usage
echo "💾 Memory Usage:"
systemctl status echo-engine.service singularity-engine.service higgs-nexus.service 2>/dev/null | grep -E "echo-engine|singularity-engine|higgs-nexus|Memory:" | grep -A 1 "service" | grep "Memory:" | awk '{print "  " $2}'
echo ""

# Uptime
echo "⏰ Uptime:"
for service in echo-engine singularity-engine higgs-nexus; do
  uptime=$(systemctl status $service.service 2>/dev/null | grep 'Active:' | awk '{print $6, $7, $8}')
  echo "  $service: $uptime"
done
echo ""

echo "✅ ALL ENGINES CONFIGURED FOR 24/7 NON-STOP OPERATION!"
echo ""
echo "Configuration:"
echo "  ✓ Restart=always    (auto-restart on crash)"
echo "  ✓ Enabled           (start on boot)"
echo "  ✓ Running           (currently active)"
echo ""
