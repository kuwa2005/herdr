#!/usr/bin/env python3
"""Update distribution/latest.json for kuwa2005/herdr fork releases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PLATFORM_FILES = {
    "linux-x86_64": "herdr-linux-x86_64",
    "linux-aarch64": "herdr-linux-aarch64",
    "macos-x86_64": "herdr-macos-x86_64",
    "macos-aarch64": "herdr-macos-aarch64",
    "windows-x86_64": "herdr-windows-x86_64.zip",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_sha256_sidecar(dist_dir: Path, filename: str) -> str | None:
    sidecar = dist_dir / f"{filename}.sha256"
    if not sidecar.is_file():
        return None
    text = sidecar.read_text(encoding="utf-8").strip().split()
    if not text:
        return None
    return text[0].lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--repo", default="kuwa2005/herdr")
    parser.add_argument("--manifest", type=Path, default=Path("distribution/latest.json"))
    parser.add_argument(
        "--notes-prefix",
        default=None,
        help="Optional markdown notes prepended for this version",
    )
    args = parser.parse_args()

    version = args.version.lstrip("v")
    tag = f"v{version}"
    base = f"https://github.com/{args.repo}/releases/download/{tag}"

    assets: dict[str, str] = {}
    sha256: dict[str, str] = {}
    for platform, filename in PLATFORM_FILES.items():
        path = args.dist_dir / filename
        if not path.is_file():
            raise SystemExit(f"missing release asset: {path}")
        digest = read_sha256_sidecar(args.dist_dir, filename) or sha256_file(path)
        assets[platform] = f"{base}/{filename}"
        sha256[platform] = digest

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    previous_version = manifest.get("version")

    # Preserve the previous top-level release under releases[<old>] when bumping.
    releases = dict(manifest.get("releases") or {})
    if previous_version and previous_version != version and previous_version not in releases:
        releases[previous_version] = {
            "notes": manifest.get("notes", ""),
            "protocol": manifest.get("protocol"),
            "endpoint_generation": manifest.get("endpoint_generation"),
            "assets": manifest.get("assets", {}),
            "sha256": manifest.get("sha256", {}),
        }

    if args.notes_prefix:
        notes = args.notes_prefix.rstrip() + "\n\n" + (manifest.get("notes") or "")
    else:
        fork_header = (
            f"### kuwa2005/herdr fork ({version})\n"
            f"- Multi-platform binaries from this repository's GitHub Releases.\n"
            f"- Japanese UI/CLI via `[ui].language = \"ja\"` (and `en` / `zh-cn`).\n\n"
        )
        existing = manifest.get("notes") or ""
        if existing.startswith(f"### kuwa2005/herdr fork ({version})"):
            notes = existing
        else:
            notes = fork_header + existing

    manifest["version"] = version
    manifest["notes"] = notes
    manifest["assets"] = assets
    manifest["sha256"] = sha256
    manifest["releases"] = releases

    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"updated {args.manifest} -> {version}")
    for platform, url in assets.items():
        print(f"  {platform}: {url}")
        print(f"    sha256={sha256[platform]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
