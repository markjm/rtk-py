#!/usr/bin/env python3
"""Custom build commands that download the rtk binary at install time."""

from __future__ import annotations

import hashlib
import http
import io
import os.path
import platform
import stat
import sys
import tarfile
import urllib.request
import zipfile

from setuptools import Command, setup
from setuptools.command.build import build as orig_build
from setuptools.command.install import install as orig_install
from setuptools.command.bdist_wheel import bdist_wheel as orig_bdist_wheel


RTK_VERSION = '0.48.0'
PY_VERSION = '1'

ARCHIVE_HASHES = {
    "x86_64-unknown-linux-musl": "e4e650fa1677c0de2f6839a6040d7b17f312d32f163c402b75af70e9e5af1a91",
    "aarch64-unknown-linux-gnu": "5ed65486a96077bd6bba7c87fdc9d0e4a1918d19619be3c87380888389a30c7c",
    "x86_64-apple-darwin": "a95f2c23e08572dcc84ddff5fbe432e41e7f94369622eb086cca49ae0b6f61e8",
    "aarch64-apple-darwin": "4fa025cc93a744b6963f4e53a008e5ba3f74b6a38061f4a47c639e1c3023e0db",
    "x86_64-pc-windows-msvc": "8c9ae56bacde865112777a9fe9791b449186d8b2a081c32c0772ef773f284f93",
}

PLATFORM_TARGETS = {
    ("linux", "x86_64"): "x86_64-unknown-linux-musl",
    ("linux", "aarch64"): "aarch64-unknown-linux-gnu",
    ("darwin", "x86_64"): "x86_64-apple-darwin",
    ("darwin", "arm64"): "aarch64-apple-darwin",
    ("win32", "AMD64"): "x86_64-pc-windows-msvc",
    ("cygwin", "x86_64"): "x86_64-pc-windows-msvc",
}


def _get_platform_key() -> tuple[str, str]:
    system = sys.platform
    machine = platform.machine()
    if system == "linux":
        if machine in ("x86_64", "amd64"):
            machine = "x86_64"
        elif machine in ("aarch64", "arm64"):
            machine = "aarch64"
    elif system == "darwin":
        if machine in ("x86_64", "amd64"):
            machine = "x86_64"
        elif machine in ("aarch64", "arm64"):
            machine = "arm64"
    return system, machine


def get_download_url() -> tuple[str, str]:
    key = _get_platform_key()
    if key not in PLATFORM_TARGETS:
        raise ValueError(
            f"Unsupported platform: {key}. Supported: {sorted(PLATFORM_TARGETS.keys())}"
        )
    target = PLATFORM_TARGETS[key]
    sha256 = ARCHIVE_HASHES[target]
    is_windows = key[0] in ("win32", "cygwin")
    ext = "zip" if is_windows else "tar.gz"
    url = (
        f"https://github.com/rtk-ai/rtk/releases/download/"
        f"v{RTK_VERSION}/rtk-{target}.{ext}"
    )
    return url, sha256


def download(url: str, sha256: str) -> bytes:
    with urllib.request.urlopen(url) as resp:
        code = resp.getcode()
        if code != http.HTTPStatus.OK:
            raise ValueError(f"HTTP failure. Code: {code}")
        data = resp.read()

    checksum = hashlib.sha256(data).hexdigest()
    if checksum != sha256:
        raise ValueError(f"sha256 mismatch, expected {sha256}, got {checksum}")

    return data


def extract_binary(data: bytes, base_dir: str) -> None:
    """Extract the rtk binary from the downloaded archive."""
    is_windows = sys.platform in ("win32", "cygwin")
    exe = "rtk.exe" if is_windows else "rtk"
    os.makedirs(base_dir, exist_ok=True)
    output_path = os.path.join(base_dir, exe)

    if is_windows:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            binary_name = next(
                (n for n in names if n.endswith("rtk.exe") or n == "rtk.exe"),
                names[0],
            )
            with zf.open(binary_name) as src, open(output_path, "wb") as dst:
                dst.write(src.read())
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = tf.getnames()
            binary_name = next(
                (m for m in members if m == "rtk" or m.endswith("/rtk")),
                members[0],
            )
            member = tf.getmember(binary_name)
            extracted = tf.extractfile(member)
            if extracted is None:
                raise ValueError(f"Could not extract {binary_name} from archive")
            with open(output_path, "wb") as dst:
                dst.write(extracted.read())

    st = os.stat(output_path)
    os.chmod(output_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class build(orig_build):
    sub_commands = orig_build.sub_commands + [("fetch_binaries", None)]


class install(orig_install):
    sub_commands = orig_install.sub_commands + [("install_rtk", None)]


class fetch_binaries(Command):
    build_temp = None
    description = "download the rtk binary for the current platform"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.set_undefined_options("build", ("build_temp", "build_temp"))

    def run(self):
        url, sha256 = get_download_url()
        data = download(url, sha256)
        extract_binary(data, self.build_temp)


class install_rtk(Command):
    description = "install the rtk executable"
    outfiles = ()
    build_dir = install_dir = None
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.set_undefined_options("build", ("build_temp", "build_dir"))
        self.set_undefined_options(
            "install",
            ("install_scripts", "install_dir"),
        )

    def run(self):
        self.outfiles = self.copy_tree(self.build_dir, self.install_dir)

    def get_outputs(self):
        return self.outfiles


command_overrides = {
    "install": install,
    "install_rtk": install_rtk,
    "build": build,
    "fetch_binaries": fetch_binaries,
}


class bdist_wheel(orig_bdist_wheel):
    def finalize_options(self):
        orig_bdist_wheel.finalize_options(self)
        self.root_is_pure = False

    def get_tag(self):
        _, _, plat = orig_bdist_wheel.get_tag(self)
        if plat.startswith('linux_'):
            arch = plat.split('_', 1)[1]
            plat = f'manylinux_2_17_{arch}'
        return 'py2.py3', 'none', plat


command_overrides["bdist_wheel"] = bdist_wheel

setup(version=f'{RTK_VERSION}.{PY_VERSION}', cmdclass=command_overrides)
