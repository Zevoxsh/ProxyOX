#!/bin/bash

# Quick script to check ProxyOX logs

echo "==================================="
echo "   ProxyOX Service Logs"
echo "==================================="
echo ""

# Show last 50 lines of logs
journalctl -u proxyox -n 50 --no-pager

echo ""
echo "==================================="
echo "To follow logs in real-time, run:"
echo "  sudo journalctl -u proxyox -f"
echo "==================================="
