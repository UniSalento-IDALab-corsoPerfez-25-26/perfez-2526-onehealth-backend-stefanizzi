#!/usr/bin/env python3
"""OneHealthAI: conservatively archive unreferenced root compatibility wrappers.

Run from the project root: python scripts/maintenance/cleanup_root_wrappers.py --apply
Rollback: python scripts/maintenance/cleanup_root_wrappers.py --rollback
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = Path.cwd().resolve()
JOURNAL = ROOT / 'onehealth_migration_journal.json'
ARCHIVE = ROOT / '.onehealth_compat_archive'
MANIFEST = ARCHIVE / 'manifest.json'
SKIP_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'data', 'reports',
             '.onehealth_wrapper_backup', '.onehealth_compat_archive', '.pytest_cache',
             '.mypy_cache', '.ruff_cache', 'dist', 'build'}
CODE_EXTENSIONS = {'.py', '.sh', '.bash', '.zsh', '.toml', '.yml', '.yaml',
                   '.ini', '.cfg', '.service', '.ipynb'}
DOC_EXTENSIONS = {'.md', '.txt'}
MAX_TEXT_BYTES = 1_000_000


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def path_from_record(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def records() -> list[tuple[Path, Path]]:
    if not JOURNAL.is_file():
        raise RuntimeError(f'Registro non trovato: {JOURNAL}')
    data = json.loads(JOURNAL.read_text(encoding='utf-8'))
    copies = data.get('copies', [])
    if not isinstance(copies, list) or len(copies) != 32:
        raise RuntimeError(f'Attese 32 copie nel registro; trovate {len(copies) if isinstance(copies,list) else "formato invalido"}.')
    out = []
    for entry in copies:
        if not isinstance(entry, dict):
            raise RuntimeError('Voce registro non valida')
        src = entry.get('source') or entry.get('src')
        dst = entry.get('destination') or entry.get('dst') or entry.get('target')
        if not src or not dst:
            raise RuntimeError(f'Voce registro incompleta: {entry}')
        src, dst = path_from_record(src), path_from_record(dst)
        if src.parent != ROOT or dst == src or ROOT not in dst.parents:
            raise RuntimeError(f'Percorso imprevisto: {src} -> {dst}')
        out.append((src, dst))
    if len({src.name for src, _ in out}) != len(out):
        raise RuntimeError('File radice duplicati nel registro')
    return out


def find_backup(src: Path, dst: Path) -> Path | None:
    backup_root = ROOT / '.onehealth_wrapper_backup'
    if not backup_root.is_dir():
        return None
    candidates = [p for p in backup_root.rglob(src.name) if p.is_file()]
    valid = [p for p in candidates if digest(p) == digest(dst)]
    return valid[0] if len(valid) == 1 else None


def references(sources: list[Path]) -> tuple[dict[str,list[str]],dict[str,list[str]],list[str]]:
    names = {s.name: s.stem for s in sources}
    code = {n: [] for n in names}
    docs = {n: [] for n in names}
    scan_errors = []
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.is_symlink() or path.resolve() == SCRIPT:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts[:-1]):
            continue
        if path in sources or path.name in {'onehealth_migration_journal.json', '.onehealth_wrapper_migration.json'}:
            continue
        ext = path.suffix.lower()
        if ext not in CODE_EXTENSIONS | DOC_EXTENSIONS and path.name not in {'Dockerfile', 'Makefile'}:
            continue
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                scan_errors.append(f'Troppo grande da esaminare: {path.relative_to(ROOT)}')
                continue
            contents = path.read_text(encoding='utf-8')
        except (UnicodeError, OSError) as e:
            scan_errors.append(f'Impossibile leggere {path.relative_to(ROOT)}: {e}')
            continue
        for name, stem in names.items():
            # References to the filename, and Python imports of the bare stem.
            found = bool(re.search(r'(?<![\w.])' + re.escape(name) + r'(?![\w])', contents))
            if ext == '.py' and not found:
                found = bool(re.search(r'\b(?:from|import)\s+' + re.escape(stem) + r'\b', contents))
            if found:
                bucket = docs if ext in DOC_EXTENSIONS else code
                bucket[name].append(str(path.relative_to(ROOT)))
    return code, docs, scan_errors


def rollback() -> None:
    if not MANIFEST.is_file():
        raise RuntimeError('Nessun manifesto di archiviazione presente.')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    archived = manifest['archived']
    errors = []
    for name, sha in archived.items():
        src = ARCHIVE / 'wrappers' / name
        dst = ROOT / name
        if not src.is_file() or digest(src) != sha or dst.exists():
            errors.append(name)
    if errors:
        raise RuntimeError('Rollback bloccato; file assenti, alterati o già presenti: ' + ', '.join(errors))
    for name in archived:
        (ARCHIVE / 'wrappers' / name).rename(ROOT / name)
    MANIFEST.rename(ARCHIVE / 'manifest_rolled_back.json')
    print(f'RIPRISTINO COMPLETATO: {len(archived)} wrapper riportati nella radice.')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    action = ap.add_mutually_exclusive_group()
    action.add_argument('--apply', action='store_true', help='Archivia i wrapper verificati e non referenziati')
    action.add_argument('--rollback', action='store_true', help='Ripristina i wrapper archiviati')
    args = ap.parse_args()
    if args.rollback:
        rollback()
        return
    if MANIFEST.exists():
        raise RuntimeError('Esiste già una migrazione attiva. Non ripeterla; usare --rollback se necessario.')
    pairs = records()
    code_refs, doc_refs, scan_errors = references([s for s, _ in pairs])
    safe = []
    retained = []
    for src, dst in pairs:
        reasons = []
        if not src.is_file() or not dst.is_file():
            reasons.append('wrapper o destinazione mancante')
        else:
            backup = find_backup(src, dst)
            if backup is None:
                reasons.append('backup originale non verificato')
            if src.stat().st_size > 4000 or digest(src) == digest(dst):
                reasons.append('wrapper non riconosciuto')
            try:
                wrapper = src.read_text(encoding='utf-8')
                # Marker must mention destination script filename or path.
                if dst.name not in wrapper and str(dst.relative_to(ROOT)) not in wrapper:
                    reasons.append('destinazione non identificabile nel wrapper')
            except (OSError, UnicodeError):
                reasons.append('wrapper non leggibile')
        if code_refs[src.name]:
            reasons.append('riferimenti nel codice: ' + ', '.join(code_refs[src.name][:6]))
        if scan_errors:
            reasons.append('scansione incompleta')
        if reasons:
            retained.append((src.name, reasons))
        else:
            safe.append(src)
    print('=== ONEHEALTHAI — PULIZIA CARTELLA PRINCIPALE ===')
    print(f'Wrapper analizzati: {len(pairs)}')
    print(f'Archiviabili in sicurezza: {len(safe)}')
    print(f'Da conservare per ora: {len(retained)}')
    if scan_errors:
        print('\nAVVERTENZE SCANSIONE:')
        for x in scan_errors[:10]: print(' -', x)
    for name, reasons in retained:
        print(f'CONSERVATO {name}: ' + '; '.join(reasons))
    if any(doc_refs.values()):
        print('\nRiferimenti solo documentali (non bloccano):')
        for name, refs in doc_refs.items():
            if refs: print(f' {name}: {", ".join(refs[:3])}')
    if not args.apply:
        print('\nSIMULAZIONE: nessun file modificato. Per applicare: --apply')
        return
    ARCHIVE.mkdir(exist_ok=True)
    dest = ARCHIVE / 'wrappers'
    dest.mkdir(exist_ok=True)
    if any((dest / p.name).exists() for p in safe):
        raise RuntimeError('Archivio contiene già un wrapper: nessuno spostamento effettuato.')
    archived = {}
    try:
        for p in safe:
            archived[p.name] = digest(p)
            p.rename(dest / p.name)
        manifest = {
            'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'archived': archived,
            'retained': {name: reasons for name, reasons in retained},
            'note': 'Spostamenti reversibili; nessun dataset o microservizio modificato'
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception:
        for name in archived:
            if (dest / name).exists() and not (ROOT / name).exists():
                (dest / name).rename(ROOT / name)
        raise
    print(f'\nCOMPLETATO: {len(archived)} wrapper spostati in {dest.relative_to(ROOT)}')
    print(f'Wrapper rimasti in radice: {len(retained)}')
    print('Rollback: python scripts/maintenance/cleanup_root_wrappers.py --rollback')
    print('Nessun dataset, pipeline o servizio modificato.')


if __name__ == '__main__':
    main()
