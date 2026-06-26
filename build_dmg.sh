#!/bin/bash
# Build Ruzh Translator DMG installer
#
# Prerequisites:
#   1. PyInstaller built: .venv/bin/pyinstaller ruzh_translator.spec
#   2. dist/RuzhTranslator.app exists
#
# Usage: bash build_dmg.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Ruzh Translator"
APP_BUNDLE="dist/RuzhTranslator.app"
DMG_NAME="RuzhTranslator-0.1.0.dmg"
DMG_TEMP="dist/RuzhTranslator-tmp.dmg"
STAGING="dist/dmg_staging"

echo "=== Building Ruzh Translator DMG ==="

# Step 0: Build the .app with PyInstaller if not already done
if [ ! -d "$APP_BUNDLE" ]; then
    echo "→ Building .app bundle with PyInstaller..."
    source .venv/bin/activate
    pyinstaller ruzh_translator.spec --clean --noconfirm
    echo "✓ .app bundle built"
else
    echo "✓ .app bundle found, skipping PyInstaller"
fi

# Step 1: Clean previous build artifacts
echo "→ Cleaning previous DMG artifacts..."
rm -rf "$DMG_TEMP" "$STAGING" "dist/$DMG_NAME"

# Step 2: Create staging directory
echo "→ Creating DMG staging directory..."
mkdir -p "$STAGING"

# Step 3: Copy .app bundle
echo "→ Copying application bundle..."
cp -R "$APP_BUNDLE" "$STAGING/"

# Step 4: Create Applications symlink (for drag-to-install)
echo "→ Creating Applications shortcut..."
ln -s /Applications "$STAGING/Applications"

# Step 5: Create DMG
echo "→ Creating DMG file..."
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDRW \
    "$DMG_TEMP"

# Step 6: Mount the DMG to customize layout
echo "→ Mounting DMG for layout customization..."
DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "$DMG_TEMP" | grep Apple_HFS | awk '{print $1}')
echo "   Mounted at device: $DEVICE"

# Give Finder time to recognize the volume
sleep 2

# Use AppleScript to arrange icons
echo "→ Arranging DMG window layout..."
osascript <<EOF
tell application "Finder"
    tell disk "$APP_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {400, 100, 900, 480}
        set theViewOptions to the icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 80
        set background picture of theViewOptions to file ".background:background.png"
        set position of item "$APP_NAME.app" of container window to {140, 160}
        set position of item "Applications" of container window to {360, 160}
        close
        open
        update without registering applications
        delay 1
    end tell
end tell
EOF

# Step 7: Convert to compressed read-only DMG
echo "→ Converting to final compressed DMG..."
hdiutil detach "$DEVICE" -quiet
sleep 1
hdiutil convert "$DMG_TEMP" -format UDZO -imagekey zlib-level=9 -o "dist/$DMG_NAME"

# Step 8: Cleanup
echo "→ Cleaning up..."
rm -f "$DMG_TEMP"
rm -rf "$STAGING"

echo ""
echo "========================================="
echo " ✓ DMG created: dist/$DMG_NAME"
echo "========================================="
echo ""
echo "To install:"
echo "  1. Double-click $DMG_NAME"
echo "  2. Drag Ruzh Translator.app to Applications"
echo "  3. Launch from Applications or Spotlight"
echo ""
ls -lh "dist/$DMG_NAME"
