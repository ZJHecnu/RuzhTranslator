#!/usr/bin/env python3
"""Build script for Ruzh Translator DMG.

Usage:
    source .venv/bin/activate
    python build_dmg.py            # Full build: PyInstaller → DMG
    python build_dmg.py --skip-pyinstaller  # DMG only (if .app already built)

Requirements:
    pip install PySide6 pyinstaller
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
APP_NAME = "Ruzh Translator"
APP_BUNDLE = DIST / "RuzhTranslator.app"
DMG_NAME = f"RuzhTranslator-0.1.0.dmg"
STAGING = DIST / "dmg_staging"

# ── Step 1: PyInstaller build ────────────────────────────────────


def run_pyinstaller():
    """Build the .app bundle with PyInstaller."""
    print("=" * 60)
    print("Step 1: Building .app with PyInstaller")
    print("=" * 60)

    spec_path = ROOT / "ruzh_translator.spec"
    if not spec_path.exists():
        print(f"✗ Spec file not found: {spec_path}")
        sys.exit(1)

    # Clean previous build
    for d in ["build", "dist"]:
        path = ROOT / d
        if path.exists():
            print(f"  Cleaning {d}/...")
            shutil.rmtree(path)

    # Run PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec_path),
        "--clean",
        "--noconfirm",
        "--log-level", "INFO",
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("✗ PyInstaller build failed")
        sys.exit(1)

    if not APP_BUNDLE.exists():
        print(f"✗ .app bundle not found at {APP_BUNDLE}")
        sys.exit(1)

    print(f"  ✓ .app built: {APP_BUNDLE}")
    _print_size(APP_BUNDLE)


# ── Step 2: Create DMG ───────────────────────────────────────────


def create_dmg():
    """Create a DMG installer from the .app bundle."""
    print()
    print("=" * 60)
    print("Step 2: Creating DMG installer")
    print("=" * 60)

    if not APP_BUNDLE.exists():
        print(f"✗ .app not found at {APP_BUNDLE}")
        print("  Run without --skip-pyinstaller first")
        sys.exit(1)

    # Clean
    for path in [STAGING, DIST / DMG_NAME, DIST / "RuzhTranslator-tmp.dmg"]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    # Create staging
    STAGING.mkdir(parents=True, exist_ok=True)

    # Copy app
    print(f"  Copying {APP_BUNDLE.name} → staging...")
    shutil.copytree(APP_BUNDLE, STAGING / APP_BUNDLE.name, symlinks=True)

    # Create Applications symlink
    apps_link = STAGING / "Applications"
    if not apps_link.exists():
        apps_link.symlink_to("/Applications")
        print("  Created /Applications shortcut")

    # Build DMG (simple version without AppleScript layout)
    tmp_dmg = DIST / "RuzhTranslator-tmp.dmg"
    final_dmg = DIST / DMG_NAME

    print(f"  Creating DMG...")
    subprocess.run(
        [
            "hdiutil", "create",
            "-volname", APP_NAME,
            "-srcfolder", str(STAGING),
            "-ov",
            "-format", "UDZO",
            "-imagekey", "zlib-level=9",
            str(final_dmg),
        ],
        check=True,
    )

    # Verify
    size = final_dmg.stat().st_size
    print(f"  ✓ DMG created: {final_dmg}")
    print(f"    Size: {_fmt_size(size)}")

    # Clean staging
    shutil.rmtree(STAGING, ignore_errors=True)

    return final_dmg


# ── Helpers ───────────────────────────────────────────────────────


def _print_size(path: Path):
    """Print the total size of a directory."""
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    print(f"    Size: {_fmt_size(total)}")


def _fmt_size(size: int) -> str:
    """Format file size in human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ── Main ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Build Ruzh Translator DMG")
    parser.add_argument(
        "--skip-pyinstaller",
        action="store_true",
        help="Skip PyInstaller build, only create DMG from existing .app",
    )
    args = parser.parse_args()

    print(f"Ruzh Translator DMG Builder")
    print(f"Root: {ROOT}")
    print()

    if not args.skip_pyinstaller:
        run_pyinstaller()
    else:
        print("Skipping PyInstaller build (--skip-pyinstaller)")

    final_dmg = create_dmg()

    print()
    print("=" * 60)
    print(f"✓ BUILD COMPLETE")
    print(f"  {final_dmg}")
    print("=" * 60)
    print()
    print("To install:")
    print("  1. Double-click the DMG file")
    print("  2. Drag Ruzh Translator.app to Applications")
    print("  3. On first launch, right-click → Open (Gatekeeper bypass)")
    print()


if __name__ == "__main__":
    main()
