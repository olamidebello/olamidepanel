"""Repair the global hostname hash and remove only byte-identical enabled aliases."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

TOKEN = re.compile(r'''\#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[{};]|[^\s{};#]+''')


def tune(text):
    tokens = [m for m in TOKEN.finditer(text) if not m.group().startswith('#')]
    stack, directive, removals, insertion = [], [], [], None
    for token in tokens:
        value = token.group()
        if value == '{':
            name = directive[0].group() if directive else ''
            stack.append(name)
            if stack == ['http']:
                if insertion is not None:
                    raise ValueError('Multiple http contexts require manual review')
                insertion = token.end()
            directive = []
        elif value == '}':
            if stack:
                stack.pop()
            directive = []
        elif value == ';':
            if stack == ['http'] and directive and directive[0].group() in ('server_names_hash_bucket_size', 'server_names_hash_max_size'):
                removals.append((directive[0].start(), token.end()))
            directive = []
        else:
            directive.append(token)
    if insertion is None:
        raise ValueError('No http context found')
    sizes = {'server_names_hash_bucket_size': 256, 'server_names_hash_max_size': 8192}
    for a,b in removals:
        parts = text[a:b].rstrip(';').split()
        if len(parts) != 2 or not parts[1].isdigit():
            raise ValueError('Unexpected hash directive; manual review required')
        sizes[parts[0]] = max(sizes[parts[0]], int(parts[1]))
    desired = [f'{key} {value};' for key,value in sizes.items()]
    changes = [(a,b,'') for a,b in removals]
    changes.append((insertion,insertion,'\n    ' + '\n    '.join(desired)))
    # Preserve an already suitable setting exactly for idempotency.
    active = [text[a:b] for a,b in removals]
    if sorted(re.sub(r'\s+', ' ', s).strip() for s in active) == sorted(desired):
        return text
    for start,end,replacement in sorted(changes, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def repair(config, enabled, backup_root, nginx):
    old = config.read_text()
    new = tune(old)
    duplicates, seen = [], {}
    for path in sorted(enabled.iterdir()):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            duplicates.append(path)
        else:
            seen[digest] = path
    changed = new != old or bool(duplicates)
    backup = backup_root / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    moved = []
    if changed:
        backup.mkdir(parents=True, mode=0o700)
        shutil.copy2(config, backup / 'nginx.conf')
    try:
        if new != old:
            temporary = config.with_name('nginx.conf.weather-tmp')
            shutil.copy2(config, temporary)
            temporary.write_text(new)
            os.replace(temporary, config)
        for path in duplicates:
            target = backup / path.name
            shutil.move(str(path), str(target))
            moved.append((path,target))
        check = subprocess.run([nginx, '-t'], capture_output=True, text=True)
        if check.returncode:
            raise RuntimeError(check.stderr)
    except Exception:
        if changed:
            shutil.copy2(backup / 'nginx.conf', config)
        for original,saved in reversed(moved):
            shutil.move(str(saved), str(original))
        raise
    return {'changed': changed, 'backup': str(backup) if changed else '',
            'disabled_identical_aliases': [str(p) for p in duplicates],
            'warnings': check.stderr}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--nginx', default='/usr/sbin/nginx')
    args = parser.parse_args()
    try:
        print(json.dumps(repair(Path('/etc/nginx/nginx.conf'), Path('/etc/nginx/sites-enabled'), Path('/var/backups/olamide-weather/nginx'), args.nginx)))
    except Exception as error:
        raise SystemExit(str(error))
