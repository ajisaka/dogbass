from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import tempfile
import tomllib
from typing import Any, cast
import zipfile


ROOT = Path(__file__).resolve().parent
PACKAGE_DIR = ROOT / "dogbass"


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, object] | None = None,
    metadata_directory: str | None = None,
) -> str:
    del config_settings, metadata_directory

    project = _load_project_metadata()
    dist_name = _normalize_distribution_name(project["name"])
    version = project["version"]
    wheel_name = f"{dist_name}-{version}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    dist_info_dir = f"{dist_name}-{version}.dist-info"

    files: list[tuple[str, bytes]] = []
    for path in sorted(PACKAGE_DIR.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        files.append((path.relative_to(ROOT).as_posix(), path.read_bytes()))

    files.extend(
        [
            (f"{dist_info_dir}/METADATA", _metadata_contents(project).encode("utf-8")),
            (f"{dist_info_dir}/WHEEL", _wheel_contents().encode("utf-8")),
            (
                f"{dist_info_dir}/entry_points.txt",
                _entry_points_contents(project).encode("utf-8"),
            ),
        ]
    )

    record_lines: list[str] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        for relative_path, content in files:
            wheel.writestr(relative_path, content)
            record_lines.append(_record_line(relative_path, content))

        record_path = f"{dist_info_dir}/RECORD"
        record_lines.append(f"{record_path},,")
        wheel.writestr(record_path, "\n".join(record_lines).encode("utf-8"))

    return wheel_name


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, object] | None = None,
    metadata_directory: str | None = None,
) -> str:
    return build_wheel(wheel_directory, config_settings, metadata_directory)


def get_requires_for_build_wheel(
    config_settings: dict[str, object] | None = None,
) -> list[str]:
    del config_settings
    return []


def get_requires_for_build_editable(
    config_settings: dict[str, object] | None = None,
) -> list[str]:
    del config_settings
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str, config_settings: dict[str, object] | None = None
) -> str:
    del config_settings
    project = _load_project_metadata()
    dist_name = _normalize_distribution_name(project["name"])
    version = project["version"]
    dist_info_dir = Path(metadata_directory) / f"{dist_name}-{version}.dist-info"
    dist_info_dir.mkdir(parents=True, exist_ok=True)
    (dist_info_dir / "METADATA").write_text(
        _metadata_contents(project), encoding="utf-8"
    )
    (dist_info_dir / "WHEEL").write_text(_wheel_contents(), encoding="utf-8")
    (dist_info_dir / "entry_points.txt").write_text(
        _entry_points_contents(project), encoding="utf-8"
    )
    return dist_info_dir.name


def prepare_metadata_for_build_editable(
    metadata_directory: str, config_settings: dict[str, object] | None = None
) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_sdist(
    sdist_directory: str, config_settings: dict[str, object] | None = None
) -> str:
    del config_settings
    project = _load_project_metadata()
    dist_name = _normalize_distribution_name(project["name"])
    version = project["version"]
    archive_name = f"{dist_name}-{version}.tar.gz"
    archive_path = Path(sdist_directory) / archive_name

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir) / f"{dist_name}-{version}"
        temp_root.mkdir(parents=True, exist_ok=True)

        for relative_path in (
            "pyproject.toml",
            "README.md",
            "main.py",
            "build_backend.py",
        ):
            source = ROOT / relative_path
            target = temp_root / relative_path
            target.write_bytes(source.read_bytes())

        package_target = temp_root / "dogbass"
        package_target.mkdir(parents=True, exist_ok=True)
        for path in sorted(PACKAGE_DIR.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue
            target = temp_root / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())

        import tarfile

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(temp_root, arcname=temp_root.name)

    return archive_name


def _load_project_metadata() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    project = cast(dict[str, Any], data["project"])
    return {
        "name": cast(str, project["name"]),
        "version": cast(str, project["version"]),
        "description": cast(str, project.get("description", "")),
        "requires_python": cast(str, project["requires-python"]),
        "dependencies": cast(list[str], project.get("dependencies", [])),
        "scripts": cast(dict[str, str], project.get("scripts", {})),
    }


def _metadata_contents(project: dict[str, Any]) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {cast(str, project['name'])}",
        f"Version: {cast(str, project['version'])}",
    ]
    description = cast(str, project["description"])
    if description:
        lines.append(f"Summary: {description}")
    lines.append(f"Requires-Python: {cast(str, project['requires_python'])}")

    for dependency in cast(list[str], project["dependencies"]):
        lines.append(f"Requires-Dist: {dependency}")

    return "\n".join(lines) + "\n"


def _wheel_contents() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: dogbass build_backend",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def _entry_points_contents(project: dict[str, Any]) -> str:
    scripts = cast(dict[str, str], project["scripts"])
    lines = ["[console_scripts]"]
    for name, target in scripts.items():
        lines.append(f"{name} = {target}")
    lines.append("")
    return "\n".join(lines)


def _record_line(path: str, content: bytes) -> str:
    digest = hashlib.sha256(content).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{path},sha256={encoded},{len(content)}"


def _normalize_distribution_name(name: str) -> str:
    return name.replace("-", "_")
