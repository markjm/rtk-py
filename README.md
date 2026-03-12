# rtk-py

Python wrapper around [rtk](https://github.com/rtk-ai/rtk) — a CLI proxy that reduces LLM token consumption by 60-90% on common dev commands.

This package downloads and installs the pre-built `rtk` binary for your platform, making it available via `pip install`.

## Installation

```bash
pip install rtk-py
```

## Usage

After installation, `rtk` is available on your `PATH`:

```bash
rtk --version
rtk init --global
rtk gain
```

See the [rtk documentation](https://github.com/rtk-ai/rtk#readme) for full usage details.

## Supported Platforms

| Platform         | Architecture |
|------------------|-------------|
| Linux            | x86_64      |
| Linux            | aarch64     |
| macOS            | x86_64      |
| macOS            | arm64       |
| Windows          | x86_64      |

## How It Works

This package follows the same pattern as [shfmt-py](https://github.com/MaxWinterstein/shfmt-py) and [shellcheck-py](https://github.com/shellcheck-py/shellcheck-py). During `pip install`, it downloads the appropriate pre-built binary from the [rtk GitHub releases](https://github.com/rtk-ai/rtk/releases) and installs it into your Python environment's `bin/` (or `Scripts/`) directory.

## Version

The Python package version tracks the upstream rtk version with an additional Python release suffix: `{rtk_version}.{py_release}` (e.g., `0.28.2.1`).

## License

For the code in this repository — see [LICENSE](LICENSE) for details.

The `rtk` binary is distributed under [MIT](https://github.com/rtk-ai/rtk/blob/master/Cargo.toml).
