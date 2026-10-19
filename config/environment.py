"""Load an explicitly selected private environment file without running shell code.

Files use KEY=VALUE lines, optional matching quotes, and # comments. Values are
literal: backslashes, dollar signs, and command substitutions are never expanded.
The whole file is validated before any process environment is changed.
"""
import os
import re
import stat
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_MAX_FILE_BYTES = 65536


class EnvironmentFileError(ValueError):
    """Invalid environment file; diagnostics deliberately omit its values."""


def _parse_environment(content):
    values = {}
    for number, raw_line in enumerate(content.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        error = f'Invalid private environment file at line {number}.'
        if '\x00' in line or '=' not in line:
            raise EnvironmentFileError(error)
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if not _KEY.fullmatch(key) or key in values:
            raise EnvironmentFileError(error)
        if value.startswith(('"', "'")):
            quote = value[0]
            closing = value.find(quote, 1)
            if closing < 0:
                raise EnvironmentFileError(error)
            suffix = value[closing + 1:].strip()
            if suffix and not suffix.startswith('#'):
                raise EnvironmentFileError(error)
            value = value[1:closing]
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].rstrip()
            if '"' in value or "'" in value:
                raise EnvironmentFileError(error)
        values[key] = value
    return values


def load_environment(path, override=True):
    """Validate and load a private absolute file outside the source checkout.

    On POSIX the regular file must belong to this process's user and have mode
    0600. The final path cannot be a symlink. ``override=True`` makes the
    explicitly selected file authoritative over inherited process variables.
    """
    file_path = Path(path).expanduser()
    if not file_path.is_absolute():
        raise EnvironmentFileError('Private environment file path must be absolute.')
    try:
        resolved = file_path.resolve(strict=True)
        if resolved.is_relative_to(PROJECT_ROOT):
            raise EnvironmentFileError('Private environment file must be outside the source checkout.')
        initial_stat = file_path.lstat()
        if not stat.S_ISREG(initial_stat.st_mode):
            raise EnvironmentFileError('Private environment file must be a regular file, not a symlink.')
        descriptor = os.open(file_path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'rb') as private_file:
            opened_stat = os.fstat(private_file.fileno())
            if (opened_stat.st_dev, opened_stat.st_ino) != (initial_stat.st_dev, initial_stat.st_ino):
                raise EnvironmentFileError('Private environment file changed while opening it.')
            if os.name == 'posix' and (
                opened_stat.st_uid != os.getuid() or stat.S_IMODE(opened_stat.st_mode) != 0o600
            ):
                raise EnvironmentFileError('Private environment file must be owned by this user with mode 0600.')
            raw_content = private_file.read(_MAX_FILE_BYTES + 1)
        if len(raw_content) > _MAX_FILE_BYTES:
            raise EnvironmentFileError('Private environment file exceeds the size limit.')
        content = raw_content.decode('utf-8')
    except (OSError, UnicodeError, ValueError) as error:
        if isinstance(error, EnvironmentFileError):
            raise
        raise EnvironmentFileError('Cannot read the private environment file safely.') from None
    values = _parse_environment(content)
    if override:
        os.environ.update(values)
    else:
        for key, value in values.items():
            os.environ.setdefault(key, value)
    return values


def load_configured_environment():
    """Opt in with TOOLSATHI_ENV_FILE; never discover or load .env implicitly."""
    path = os.environ.get('TOOLSATHI_ENV_FILE')
    return load_environment(path) if path else {}
