"""Check packaged Android resources and official wrapper integrity without an SDK.

This is source/package validation, NOT a substitute for compiling or device tests.
Run: python android/verify_source.py from the repository root.
"""
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


def main():
    root = Path(__file__).resolve().parent
    resources = root / "app/src/main/res"
    xml_paths = list(resources.rglob("*.xml")) + [root / "app/src/main/AndroidManifest.xml"]
    parsed = {path: ElementTree.parse(path).getroot() for path in xml_paths}
    available = set()
    for path, tree in parsed.items():
        if path.parent.name.startswith("values"):
            available.update(f"{node.tag}/{node.attrib['name']}" for node in tree if "name" in node.attrib)
        elif path.is_relative_to(resources):
            available.add(f"{path.parent.name.split('-')[0]}/{path.stem}")
    for path, tree in parsed.items():
        for node in tree.iter():
            for value in [*node.attrib.values(), node.text or ""]:
                value = value.strip()
                if value.startswith("@") and not value.startswith("@android:"):
                    assert value[1:] in available, f"Missing resource {value} in {path}"
    android = "{http://schemas.android.com/apk/res/android}"
    manifest = parsed[root / "app/src/main/AndroidManifest.xml"]
    permissions = {node.attrib[android + "name"] for node in manifest.findall("uses-permission")}
    assert permissions == {"android.permission.INTERNET"}, permissions
    application = manifest.find("application")
    assert application is not None
    assert application.attrib[android + "usesCleartextTraffic"] == "false"
    assert application.attrib[android + "allowBackup"] == "false"
    network = parsed[resources / "xml/network_security_config.xml"]
    assert network.find("base-config").attrib["cleartextTrafficPermitted"] == "false"
    wrapper = root / "gradle/wrapper/gradle-wrapper.jar"
    expected = "81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f"
    assert sha256(wrapper.read_bytes()).hexdigest() == expected, "Official wrapper checksum mismatch"
    with ZipFile(wrapper) as archive:
        assert "org/gradle/wrapper/GradleWrapperMain.class" in archive.namelist()
        assert archive.testzip() is None
    properties = (root / "gradle/wrapper/gradle-wrapper.properties").read_text(encoding="utf-8")
    assert "distributionSha256Sum=20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78" in properties
    assert "gradle-8.13-bin.zip" in properties
    print(f"PASS: {len(xml_paths)} XML files; resource references; INTERNET-only manifest; HTTPS and backup policy; official Gradle wrapper JAR and distribution checksum.")
    print("NOT RUN: Android compilation, lint, JVM tests, emulator or device tests. These require JDK 17 and Android SDK.")


if __name__ == "__main__":
    main()
