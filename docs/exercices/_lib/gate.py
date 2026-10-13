#!/usr/bin/env python3
"""Fail-closed gate: exact five Ready nodes and >= 4 GiB host MemAvailable."""
import json
import sys

EXPECTED = {'lab-s1', 'lab-s2', 'lab-s3', 'lab-a1', 'lab-a2'}

def check(nodes, available_kib):
    items = nodes.get('items', [])
    found = {n.get('metadata', {}).get('name') for n in items}
    if found != EXPECTED:
        raise ValueError(f'Node inventory mismatch: expected={sorted(EXPECTED)} found={sorted(str(n) for n in found)}')
    for node in items:
        conditions = node.get('status', {}).get('conditions', [])
        ready = [c.get('status') for c in conditions if c.get('type') == 'Ready']
        if ready != ['True']:
            raise ValueError(f"Node {node['metadata']['name']} NotReady/UNKNOWN: {ready}")
    if available_kib < 4 * 1024 * 1024:
        raise ValueError(f'Host RAM available={available_kib} KiB < 4 GiB')

if __name__ == '__main__':
    try:
        with open('/proc/meminfo', encoding='ascii') as stream:
            available = next(int(line.split()[1]) for line in stream if line.startswith('MemAvailable:'))
        check(json.load(sys.stdin), available)
        print(f'PASS safety gate: 5 Ready nodes; host MemAvailable={available} KiB')
    except (ValueError, KeyError, TypeError, StopIteration, OSError) as error:
        print(f'FAIL/BLOCKED safety gate: {error}', file=sys.stderr)
        sys.exit(2)
