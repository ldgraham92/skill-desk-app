"""Verify the entire glib backport and the resolved Linux dependency graph."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT/'src-tauri/vendor/glib-0.18.5'
SHA256 = '233daaf6e83ae6a12a52055f568f9d7cf4671dabb78ff9560ab6da230ce00ee5'
ORIGINAL = b'''            let p: *mut libc::c_char = std::ptr::null_mut();
            let s = b"&s\\0";
            ffi::g_variant_get_child(
                self.variant.to_glib_none().0,
                i,
                s as *const u8 as *const _,
                &p,'''
PATCHED = ORIGINAL.replace(b'let p:', b'let mut p:').replace(b'                &p,', b'                &mut p,')


def main():
    with urllib.request.urlopen('https://static.crates.io/crates/glib/glib-0.18.5.crate', timeout=60) as response:
        archive = response.read(2_000_001)
    assert hashlib.sha256(archive).hexdigest() == SHA256, 'Original crate checksum differs'
    expected = set()
    with tarfile.open(fileobj=io.BytesIO(archive)) as package:
        for member in package.getmembers():
            if member.isdir():
                continue
            assert member.isfile(), 'Unexpected archive entry'
            relative = Path(member.name).relative_to('glib-0.18.5')
            assert '..' not in relative.parts
            expected.add(relative.as_posix())
            content = package.extractfile(member).read()
            if relative.as_posix() == 'src/variant_iter.rs':
                assert content.count(ORIGINAL) == 1, 'Upstream patch context differs'
                content = content.replace(ORIGINAL, PATCHED)
            local = VENDOR/relative
            assert not local.is_symlink() and local.read_bytes() == content, f'Vendor mismatch: {relative}'
    actual = {p.relative_to(VENDOR).as_posix() for p in VENDOR.rglob('*') if p.is_file() or p.is_symlink()}
    assert actual == expected, 'Vendored file inventory differs'
    metadata = json.loads(subprocess.check_output([
        'cargo', 'metadata', '--locked', '--format-version', '1', '--filter-platform', 'x86_64-unknown-linux-gnu',
        '--manifest-path', str(ROOT/'src-tauri/Cargo.toml')], text=True, encoding='utf-8'))
    resolved = {node['id'] for node in metadata['resolve']['nodes']}
    glib = [p for p in metadata['packages'] if p['id'] in resolved and p['name'] == 'glib']
    assert len(glib) == 1 and glib[0]['source'] is None, 'Unpatched or duplicate glib in Linux graph'
    assert Path(glib[0]['manifest_path']).resolve() == (VENDOR/'Cargo.toml').resolve()
    print(json.dumps(dict(verifiedFiles=len(expected), upstreamPatchOnly=True, linuxGlibCopies=1,
                         version=glib[0]['version'], source='vendored security backport')))


if __name__ == '__main__':
    main()
