"""Install corpus hook templates that call sow-lint (no duplicated rate tables)."""

from __future__ import annotations

import pathlib
import shutil
import importlib.resources as resources


_TEMPLATE_NAMES = (
    "pre-commit",
    "cc-session-start.sh",
    "cc-stop.sh",
    "cc-pretooluse-git.sh",
    "install.sh",
)


def _templates_dir() -> pathlib.Path:
    # Package data: zero_employee/hooks_templates/
    try:
        root = resources.files("zero_employee").joinpath("hooks_templates")
        # Traversable → Path when on disk (editable / wheel force-include)
        return pathlib.Path(str(root))
    except Exception:
        return pathlib.Path(__file__).parent / "hooks_templates"


def hooks_install(
    corpus_root: pathlib.Path | str,
    *,
    install_git_hook: bool = True,
) -> dict:
    """Write hook templates into <corpus>/tools/hooks/ and optionally .git/hooks/pre-commit.

    Returns {written: [...], git_hook: path|None, hooks_dir: path}.
    """
    corpus_root = pathlib.Path(corpus_root).resolve()
    hooks_dir = corpus_root / "tools" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    src_dir = _templates_dir()
    written = []
    for name in _TEMPLATE_NAMES:
        src = src_dir / name
        if not src.is_file():
            raise FileNotFoundError(f"missing hook template: {src}")
        dest = hooks_dir / name
        shutil.copyfile(src, dest)
        dest.chmod(dest.stat().st_mode | 0o111)
        written.append(str(dest.relative_to(corpus_root)))

    git_hook = None
    if install_git_hook:
        git_dir = corpus_root / ".git"
        if git_dir.is_dir() or git_dir.is_file():  # file = worktree gitfile
            dst = corpus_root / ".git" / "hooks" / "pre-commit"
            # When .git is a file (worktree), resolve the real git dir
            if git_dir.is_file():
                text = git_dir.read_text(encoding="utf-8", errors="replace").strip()
                if text.startswith("gitdir:"):
                    real = (corpus_root / text.split(":", 1)[1].strip()).resolve()
                    dst = real / "hooks" / "pre-commit"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(hooks_dir / "pre-commit", dst)
            dst.chmod(dst.stat().st_mode | 0o111)
            git_hook = str(dst)

    return {"written": written, "git_hook": git_hook, "hooks_dir": str(hooks_dir)}
