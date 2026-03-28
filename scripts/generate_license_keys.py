#!/usr/bin/env python3
"""
Generate license keys in bulk for distribution.

Usage:
    python scripts/generate_license_keys.py --plan pro --count 100 --output keys.txt
    python scripts/generate_license_keys.py --plan enterprise --count 10 --seats 50
    python scripts/generate_license_keys.py --all-plans --count 20
"""
import argparse
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_keys(plan: str, count: int, seats: int = 1) -> list:
    """Generate license keys using the LicenseKeyGenerator."""
    try:
        from src.licenses.license_keys import LicenseKeyGenerator
        gen = LicenseKeyGenerator()
        return gen.generate_batch(plan, count=count, seats=seats)
    except ImportError:
        # Fallback: generate keys without the full module
        import hashlib
        import random
        import string

        PLAN_PREFIXES = {
            "free": "FREE", "basic": "BASC", "pro": "PRO0", "enterprise": "ENTR"
        }
        prefix = PLAN_PREFIXES.get(plan.lower(), plan[:4].upper())
        keys = []
        chars = string.ascii_uppercase + string.digits

        for _ in range(count):
            seg1 = "".join(random.choices(chars, k=4))
            seg2 = "".join(random.choices(chars, k=4))
            # Checksum from first 4 chars of SHA256
            raw = f"{prefix}{seg1}{seg2}{seats}"
            checksum = hashlib.sha256(raw.encode()).hexdigest()[:4].upper()
            keys.append(f"{prefix}-{seg1}-{seg2}-{checksum}")

        return keys


def write_output(keys: list, output_path: str, plan: str, seats: int) -> None:
    """Write generated keys to file with metadata header."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# AgenteDeVoz License Keys\n")
        f.write(f"# Generated: {timestamp}\n")
        f.write(f"# Plan: {plan.upper()}\n")
        f.write(f"# Seats per key: {seats}\n")
        f.write(f"# Total keys: {len(keys)}\n")
        f.write("#" + "-" * 30 + "\n")
        for key in keys:
            f.write(f"{key}\n")
    print(f"[OK] {len(keys)} keys written to '{output_path}'")


def main():
    parser = argparse.ArgumentParser(description="Generate AgenteDeVoz license keys in bulk.")
    parser.add_argument("--plan",       default="pro",  choices=["free","basic","pro","enterprise"], help="License plan")
    parser.add_argument("--count",      type=int, default=10, help="Number of keys to generate")
    parser.add_argument("--seats",      type=int, default=1,  help="Max seats per license")
    parser.add_argument("--output",     default=None,          help="Output file path (default: stdout)")
    parser.add_argument("--all-plans",  action="store_true",   help="Generate keys for all plans")
    args = parser.parse_args()

    if args.all_plans:
        for plan in ["free", "basic", "pro", "enterprise"]:
            keys = generate_keys(plan, args.count, args.seats)
            output = args.output or f"keys_{plan}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
            output = output.replace(".txt", f"_{plan}.txt")
            write_output(keys, output, plan, args.seats)
    else:
        keys = generate_keys(args.plan, args.count, args.seats)
        if args.output:
            write_output(keys, args.output, args.plan, args.seats)
        else:
            print(f"# {args.count} {args.plan.upper()} keys (seats={args.seats})")
            for key in keys:
                print(key)


if __name__ == "__main__":
    main()
