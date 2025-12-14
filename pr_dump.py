#!/usr/bin/env python3
# save as dump_project.py

from __future__ import annotations
import argparse
import os
from pathlib import Path

# Папки, которые почти всегда не нужны в сводке
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    ".venv", "venv", "env", ".tox", "node_modules",
    "dist", "build", ".cache", ".ruff_cache"
}

# Расширения (нижний регистр) файлов, которые считаем бинарными и пропускаем
BINARY_EXTS = {
    # изображения
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp", ".ico", ".psd", ".ai",
    # видео / аудио
    ".mp4", ".mov", ".mkv", ".avi", ".wmv", ".mp3", ".wav", ".flac", ".ogg",
    # документы/офис
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # архивы
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz",
    # двоичные/исполняемые/объектные
    ".exe", ".dll", ".lib", ".so", ".dylib", ".o", ".a", ".bin",
    # базы
    ".sqlite", ".sqlite3", ".db",
    # шрифты
    ".ttf", ".otf", ".woff", ".woff2",
    # другие тяжелые артефакты
    ".ipynb_checkpoints"
}

# Файлы, которые точно не хотим включать по имени (включая скрытые служебные)
DEFAULT_EXCLUDE_FILES = {
    ".DS_Store", "Thumbs.db"
}

def should_skip_dir(dirname: str, extra_exclude_dirs: set[str]) -> bool:
    name = dirname.lower()
    return (name in extra_exclude_dirs) or name.startswith(".git")

def is_binary_path(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in BINARY_EXTS:
        return True
    # эвристика: если файла нет расширения, но он большой — вероятно бинарник
    return False

def read_text_safely(p: Path, max_bytes: int | None) -> str | None:
    try:
        if max_bytes is not None and p.stat().st_size > max_bytes:
            return None  # пропускаем слишком большие файлы
        # читаем как юникод с замещением «битых» символов
        data = p.read_bytes()
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace")
    except Exception:
        return None

def dump_project(
    root: Path,
    out_file: Path,
    exclude_dirs: set[str],
    exclude_files: set[str],
    include_binary: bool,
    max_bytes: int | None,
) -> int:
    root = root.resolve()
    out_file = out_file.resolve()

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # фильтруем каталоги «на месте» — так os.walk не будет в них заходить
        dirnames[:] = [
            d for d in dirnames
            if not should_skip_dir(d, exclude_dirs)
        ]
        # собираем файлы
        for fname in filenames:
            if fname in exclude_files:
                continue
            p = Path(dirpath, fname)
            # не включать сам файл-вывод
            try:
                if p.resolve() == out_file:
                    continue
            except Exception:
                pass

            if not include_binary and is_binary_path(p):
                continue

            files.append(p)

    # детерминированный порядок
    files.sort(key=lambda p: str(p.relative_to(root)).lower())

    # пишем
    count_written = 0
    with out_file.open("w", encoding="utf-8", newline="\n") as out:
        for i, p in enumerate(files, 1):
            rel = p.relative_to(root)
            text = read_text_safely(p, max_bytes=max_bytes)

            if text is None:
                # пропустим нечитаемые/слишком большие
                continue

            # Заголовок с путём к файлу
            out.write(f"{rel.as_posix()}\n")
            out.write(text)
            # Разделитель — пустая строка (гарантируем хотя бы один перевод строки)
            if not text.endswith("\n"):
                out.write("\n")
            out.write("\n")
            count_written += 1

    return count_written

def main():
    ap = argparse.ArgumentParser(
        description="Собрать все текстовые файлы проекта в один txt, "
                    "помечая путь к каждому в начале и разделяя файлы пустой строкой."
    )
    ap.add_argument("--root", type=Path, default=Path.cwd(),
                    help="Корень проекта (по умолчанию — текущая папка).")
    ap.add_argument("--out", type=Path, default=Path("project_dump.txt"),
                    help="Куда записать результат (по умолчанию project_dump.txt).")
    ap.add_argument("--include-binary", action="store_true",
                    help="Пытаться включать бинарные файлы (не рекомендую).")
    ap.add_argument("--no-default-excludes", action="store_true",
                    help="Не исключать стандартные папки/файлы вроде .git, .venv и т.п.")
    ap.add_argument("--max-bytes", type=int, default=2_000_000,
                    help="Макс. размер файла в байтах (по умолчанию 2 МБ). 0 — без ограничения.")

    args = ap.parse_args()

    exclude_dirs = set()
    exclude_files = set()
    if not args.no_default_excludes:
        exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
        exclude_files = set(DEFAULT_EXCLUDE_FILES)

    max_bytes = None if args.max_bytes == 0 else args.max_bytes

    count = dump_project(
        root=args.root,
        out_file=args.out,
        exclude_dirs=exclude_dirs,
        exclude_files=exclude_files,
        include_binary=args.include_binary,
        max_bytes=max_bytes,
    )
    print(f"Готово: записано файлов: {count}\nВыходной файл: {args.out.resolve()}")

if __name__ == "__main__":
    main()
