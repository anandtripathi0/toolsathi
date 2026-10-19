"""Build and verify a release on a machine with JDK 17 and the Android SDK.

Run with --check for prerequisite checks only. This does not install an SDK,
create signing keys, publish artifacts, or substitute for device acceptance.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
SIGNING_VARIABLES = ('TOOLSATHI_KEYSTORE', 'TOOLSATHI_STORE_PASSWORD',
                     'TOOLSATHI_KEY_ALIAS', 'TOOLSATHI_KEY_PASSWORD')


def preflight():
    errors = []
    suffix = '.exe' if os.name == 'nt' else ''
    java_home = os.environ.get('JAVA_HOME')
    java = Path(java_home) / 'bin' / ('java' + suffix) if java_home else Path(shutil.which('java') or '__missing_java__')
    if not java.is_file():
        errors.append('JDK 17 is missing. Set JAVA_HOME and PATH to an installed JDK 17.')
    else:
        if not (java.parent / ('javac' + suffix)).is_file():
            errors.append('Install a complete JDK 17, including javac; a JRE alone is insufficient.')
        try:
            result = subprocess.run([str(java), '-version'], capture_output=True, text=True, timeout=20)
            version = re.search(r'version "(\d+)', result.stdout + result.stderr)
            if result.returncode or not version or version[1] != '17':
                errors.append('The selected Java runtime must be JDK 17.')
        except (OSError, subprocess.TimeoutExpired):
            errors.append('Could not execute the selected Java runtime.')

    sdk_value = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    sdk = Path(sdk_value) if sdk_value else None
    signer = aapt = None
    if sdk is None or not sdk.is_dir():
        errors.append('Android SDK is missing. Set ANDROID_HOME to its absolute directory.')
    else:
        if not (sdk / 'platforms/android-36/android.jar').is_file():
            errors.append('Install Android SDK platform 36.')
        build_tools = sdk / 'build-tools/35.0.0'
        signer = build_tools / ('apksigner.bat' if os.name == 'nt' else 'apksigner')
        aapt = build_tools / ('aapt.exe' if os.name == 'nt' else 'aapt')
        if not signer.is_file() or not aapt.is_file():
            errors.append('Install Android SDK build tools 35.0.0 (apksigner and aapt).')

    missing = [name for name in SIGNING_VARIABLES if not os.environ.get(name, '').strip()]
    if missing:
        errors.append('Set private signing environment variables: ' + ', '.join(missing) + '.')
    key_value = os.environ.get('TOOLSATHI_KEYSTORE')
    if key_value:
        key = Path(key_value)
        if not key.is_absolute() or not key.is_file():
            errors.append('TOOLSATHI_KEYSTORE must point to an existing absolute keystore path.')
        elif key.resolve().is_relative_to(ROOT.parent):
            errors.append('Keep the release keystore outside the repository.')

    for error in errors:
        print('BLOCKED: ' + error, file=sys.stderr)
    return errors, signer, aapt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check prerequisites; do not build.')
    args = parser.parse_args()
    errors, signer, aapt = preflight()
    if errors:
        return 2
    if args.check:
        print('PASS: build prerequisites present. No compilation, signing, publication or device tests run.')
        return 0

    wrapper = ROOT / ('gradlew.bat' if os.name == 'nt' else 'gradlew')
    apk = ROOT / 'app/build/outputs/apk/release/app-release.apk'
    try:
        subprocess.run([str(wrapper), '--no-daemon', '--console=plain',
                        'testDebugUnitTest', 'lintRelease', 'assembleRelease'], cwd=ROOT, check=True)
        signature = subprocess.run([str(signer), 'verify', '--verbose', '--print-certs', str(apk)],
                                   capture_output=True, text=True, timeout=60)
        if signature.returncode or re.search('Android Debug', signature.stdout + signature.stderr, re.I):
            raise ValueError('Release signature verification failed or a debug certificate was detected.')
        inspection = subprocess.run([str(aapt), 'dump', 'badging', str(apk)],
                                    capture_output=True, text=True, timeout=60)
        package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'",
                            inspection.stdout, re.MULTILINE)
        if inspection.returncode or not package or package[1] != 'com.toolsathi.app' or 'application-debuggable' in inspection.stdout:
            raise ValueError('Expected the non-debuggable com.toolsathi.app release package.')
        with apk.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        # Captured SDK output and signing environment values are never printed.
        print('FAILED: release build or verification did not complete. ' +
              (str(error) if isinstance(error, ValueError) else 'Check the installed toolchain and Gradle output.'), file=sys.stderr)
        return 1

    print(f'PASS: signed {package[1]} version {package[3]}; SHA-256 {digest}')
    print(f'APK: {apk}')
    print('NOT TESTED: install/device behavior and the live HTTPS origin. Complete docs/ANDROID.md acceptance checks before publishing.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
