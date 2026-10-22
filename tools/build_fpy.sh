#!/bin/bash
# Build a working CPython launcher (fpy) against the Python 3.14 runtime that
# ships inside the locally installed Fusion 360 bundle.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
FUSION="$HOME/Library/Application Support/Autodesk/webdeploy/production"
BUNDLE="$(ls -d "$FUSION"/*/'Autodesk Fusion.app' 2>/dev/null | head -1)"
FW="$BUNDLE/Contents/Frameworks/Python.framework/Versions/3.14"

echo "Fusion bundle: $BUNDLE"
echo "Python  fw   : $FW"

# Pick the newest usable macOS SDK. Some SDKs ship .tbd stubs whose
# architecture lists the linker cannot parse (e.g. "arm64e.x1-macos"), so we
# probe them and fall back to the first one that links a trivial program.
pick_sdk() {
    local sdkroot
    for sdkroot in /Library/Developer/CommandLineTools/SDKs/MacOSX*.sdk \
                    /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX*.sdk; do
        [ -d "$sdkroot" ] || continue
        printf 'int main(void){return 0;}\n' > "$HERE/.sdkprobe.c"
        if clang -isysroot "$sdkroot" "$HERE/.sdkprobe.c" -o "$HERE/.sdkprobe" 2>/dev/null; then
            rm -f "$HERE/.sdkprobe.c" "$HERE/.sdkprobe"
            echo "$sdkroot"
            return 0
        fi
        rm -f "$HERE/.sdkprobe.c" "$HERE/.sdkprobe"
    done
    return 1
}

SDK="$(pick_sdk)" || { echo "no usable macOS SDK found" >&2; exit 1; }
echo "SDK         : $SDK"

clang -isysroot "$SDK" -o "$HERE/fpy" "$HERE/fpy.c" \
    -I"$FW/include/python3.14" \
    -L"$FW/lib" -lpython3.14 \
    -Wl,-rpath,"$FW/lib" \
    -Wl,-rpath,"$BUNDLE/Contents/Libraries" \
    -Wl,-rpath,"$BUNDLE/Contents/Frameworks"

echo "Built $HERE/fpy"
"$HERE/fpy" -c "import sys; print('fpy works, python', sys.version.split()[0])"
