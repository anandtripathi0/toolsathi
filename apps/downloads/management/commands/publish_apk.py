import hashlib
import json
import shutil
import subprocess
import re
import os
import zipfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Verify a release-signed APK using Android apksigner, then publish it for download.'
    def add_arguments(self, parser):
        parser.add_argument('apk')
        parser.add_argument('--version', required=True)
        parser.add_argument('--apksigner', required=True, help='Absolute path to SDK apksigner or apksigner.bat')
        parser.add_argument('--aapt', help='Absolute path to SDK aapt; defaults to the apksigner directory')

    def handle(self, **options):
        source = Path(options['apk']).resolve()
        signer = Path(options['apksigner']).resolve()
        aapt = Path(options['aapt']).resolve() if options.get('aapt') else signer.parent / ('aapt.exe' if os.name == 'nt' else 'aapt')
        if not source.is_file() or not signer.is_file() or not aapt.is_file():
            raise CommandError('APK, apksigner, and aapt must be existing files.')
        try:
            with zipfile.ZipFile(source) as apk:
                if not {'AndroidManifest.xml', 'classes.dex'}.issubset(apk.namelist()) or apk.testzip():
                    raise CommandError('Invalid APK archive.')
            result = subprocess.run([str(signer), 'verify', '--verbose', '--print-certs', str(source)], capture_output=True, text=True, timeout=60)
            inspection = subprocess.run([str(aapt), 'dump', 'badging', str(source)], capture_output=True, text=True, timeout=60)
        except (OSError, zipfile.BadZipFile, subprocess.TimeoutExpired) as error:
            raise CommandError('APK verification failed.') from error
        if result.returncode != 0 or 'Android Debug' in result.stdout:
            raise CommandError('A verified release-signed APK is required; debug APKs are not published.')
        package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", inspection.stdout, re.MULTILINE)
        if inspection.returncode or not package or package[1] != 'com.toolsathi.app' or 'application-debuggable' in inspection.stdout:
            raise CommandError('The APK must be the non-debuggable com.toolsathi.app release application.')
        if options['version'] != package[3]:
            raise CommandError(f'The requested version differs from actual APK version {package[3]}.')
        settings.APK_DIR.mkdir(parents=True, exist_ok=True)
        target = settings.APK_DIR / 'toolsathi-latest.apk'
        temp = settings.APK_DIR / 'toolsathi-upload.apk'
        shutil.copyfile(source, temp)
        digest = hashlib.sha256(temp.read_bytes()).hexdigest()
        temp.replace(target)
        metadata = {'version': package[3], 'version_code': package[2], 'package': package[1], 'sha256': digest, 'verified': True}
        (settings.APK_DIR / 'release.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Published ToolSathi {options["version"]}; SHA-256 {digest}'))
