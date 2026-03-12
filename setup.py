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


RTK_VERSION = '0.28.2'
PY_VERSION = '1'

ARCHIVE_SHA256 = {
    ("linux", "x86_64"): (
        "x86_64-unknown-linux-musl",
        "c7b61e87b8430e42b04ab84fbe1b3b41b563454b0181247fd04844b8e9194371",
    ),
    ("linux", "aarch64"): (
        "aarch64-unknown-linux-gnu",
        "9dbf6dd22cfdf8b85b916505a5e96e1721d7af4cbe2f3dc90b87c9d677d01636",
    ),
    ("darwin", "x86_64"): (
        "x86_64-apple-darwin",
        "5ce5dab3b744a6ecce7ff9deea9fd4606f72c6490c9ee447d74883d9393dcbc7",
    ),
    ("darwin", "arm64"): (
        "aarch64-apple-darwin",
        "5dede8ac36648960a3ad52611856b9047a7817b755750d2bdbda8d4e9931db4d",
    ),
    ("win32", "AMD64"): (
        "x86_64-pc-windows-msvc",
        "8bd4ae58b8657f9afd82c76f28e06232b0e8f994e949176206425dcc6005936a",
    ),
}
ARCHIVE_SHA256[("cygwin", "x86_64")] = ARCHIVE_SHA256[("win32", "AMD64")]


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
    if key not in ARCHIVE_SHA256:
        raise ValueError(
            f"Unsupported platform: {key}. Supported: {sorted(ARCHIVE_SHA256.keys())}"
        )
    target, sha256 = ARCHIVE_SHA256[key]
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
