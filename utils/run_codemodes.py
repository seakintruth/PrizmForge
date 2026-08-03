#!/usr/bin/env python3
""""
utils/run_codemods.py

Run a set of conservative LibCST-based codemods and a targeted edit_payload union expansion.

Usage:
  # Run all codemods (project root defaults to parent of this script's dir)
  python codemods/run_codemods.py

  # Run only selected codemods (comma-separated)
  python codemods/run_codemods.py --only fix_callable,add_typing_imports

  # Override project root
  python codemods/run_codemods.py /abs/path/to/project
"""
import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Set

try:
    import libcst as cst
    from libcst import matchers as m
except Exception as exc:
    print("Missing dependency: pip install libcst", file=sys.stderr)
    raise exc


# === Configuration ===
EXCLUDE_DIRS = {".venv", "venv", "build", "dist", ".git", ".pytest_cache", ".tox", "__pycache__", "site-packages"}
SKIP_PATTERNS = ["tests", "test_", "site-packages"]

# targeted file & replacement for the edit_payload union widening (adjust if needed)
EDIT_PAYLOAD_FILE = "file_editing/edit_payload.py"
EDIT_PAYLOAD_OLD = r"list\[ReplaceBlock\]"
EDIT_PAYLOAD_NEW = "list[ReplaceBlock | InsertAfter | DeleteLines | UpdateDocumentation | CreateFile | FindReplace | FullReplace | ApplyDiff]"


# === Helpers ===
def project_root_from_script(script_path: Path, override: Path | None) -> Path:
    if override:
        return override.resolve()
    # script is expected at repo_root/codemods/run_codemods.py
    return script_path.resolve().parent.parent


def iter_py_files(root: Path, skip_dirs: Iterable[str] = EXCLUDE_DIRS) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        if any(part in skip_dirs for part in p.parts):
            continue
        yield p


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf8")
    except Exception:
        return path.read_text()


# === Codemod 1: Replace builtin 'callable' type -> typing.Callable ===
class CallableFixer(cst.CSTTransformer):
    def __init__(self) -> None:
        self.needs_callable_import = False

    def leave_Annotation(self, original: cst.Annotation, updated: cst.Annotation) -> cst.Annotation:
        ann = updated.annotation
        if m.matches(ann, m.Name("callable")):
            self.needs_callable_import = True
            return updated.with_changes(annotation=cst.Name("Callable"))
        if m.matches(ann, m.Subscript(m.Name("callable"))):
            self.needs_callable_import = True
            new_code = ann.code.replace("callable", "Callable")
            return cst.Annotation(cst.parse_expression(new_code))
        return updated

    def leave_Param(self, original: cst.Param, updated: cst.Param) -> cst.Param:
        if updated.annotation and m.matches(updated.annotation.annotation, m.Name("callable")):
            self.needs_callable_import = True
            return updated.with_changes(annotation=cst.Annotation(cst.Name("Callable")))
        return updated


def run_fix_callable(root: Path) -> int:
    changed = 0
    for p in iter_py_files(root):
        src = read_text(p)
        try:
            mod = cst.parse_module(src)
        except Exception:
            continue
        fixer = CallableFixer()
        new_mod = mod.visit(fixer)
        code = new_mod.code
        if fixer.needs_callable_import:
            if "from typing import Callable" not in code and "import typing" not in code:
                code = "from typing import Callable\n\n" + code
        if code != src:
            p.write_text(code, encoding="utf8")
            print("fix_callable: updated", p)
            changed += 1
    return changed


# === Codemod 2: Add missing typing imports ===
TYPING_NAMES = {"Optional", "List", "Dict", "Tuple", "Callable", "Any", "Sequence", "Union", "Set"}


class TypingUsageCollector(cst.CSTVisitor):
    def __init__(self) -> None:
        self.used: Set[str] = set()

    def visit_Name(self, node: cst.Name) -> None:
        if node.value in TYPING_NAMES:
            self.used.add(node.value)


def run_add_typing_imports(root: Path) -> int:
    changed = 0
    for p in iter_py_files(root):
        src = read_text(p)
        try:
            mod = cst.parse_module(src)
        except Exception:
            continue
        collector = TypingUsageCollector()
        mod.visit(collector)
        used = collector.used
        if not used:
            continue
        missing = {n for n in used if f"from typing import {n}" not in src and "import typing" not in src}
        if missing:
            import_line = f"from typing import {', '.join(sorted(missing))}\n\n"
            new = import_line + src
            p.write_text(new, encoding="utf8")
            print("add_typing_imports: inserted", missing, "into", p)
            changed += 1
    return changed


# === Codemod 3: Optionalize params defaulting to None ===
class OptionalizeParams(cst.CSTTransformer):
    def __init__(self) -> None:
        self.add_optional = False

    def leave_Param(self, original: cst.Param, updated: cst.Param) -> cst.Param:
        default = updated.default
        ann = updated.annotation
        if default and m.matches(default, m.Name("None")) and ann:
            inner = ann.annotation
            if not (m.matches(inner, m.Subscript(m.Name("Optional"))) or m.matches(inner, m.Subscript(m.Name("Union")))):
                self.add_optional = True
                new_ann = cst.Annotation(
                    cst.Subscript(
                        value=cst.Name("Optional"),
                        slice=[cst.SubscriptElement(slice=cst.Index(value=inner))],
                    )
                )
                return updated.with_changes(annotation=new_ann)
        return updated


def run_optionalize_defaults(root: Path) -> int:
    changed = 0
    for p in iter_py_files(root):
        src = read_text(p)
        # skip tests by default (optionalize tends not to be needed in tests)
        if any(part == "tests" for part in p.parts):
            continue
        try:
            mod = cst.parse_module(src)
        except Exception:
            continue
        fixer = OptionalizeParams()
        new_mod = mod.visit(fixer)
        code = new_mod.code
        if fixer.add_optional:
            if "from typing import Optional" not in code and "import typing" not in code:
                code = "from typing import Optional\n\n" + code
        if code != src:
            p.write_text(code, encoding="utf8")
            print("optionalize_defaults: updated", p)
            changed += 1
    return changed


# === Codemod 4: Add Any annotations to simple untyped assignments ===
class AddAnyAnn(cst.CSTTransformer):
    def __init__(self) -> None:
        self.add_any = False

    def leave_Assign(self, original: cst.Assign, updated: cst.Assign):
        # Only transform simple single-target Name assignments that are not annotated
        if len(updated.targets) != 1:
            return updated
        tgt = updated.targets[0].target
        if m.matches(tgt, m.Name()) and not isinstance(updated, cst.AnnAssign):
            name = tgt.value
            self.add_any = True
            ann = cst.AnnAssign(target=cst.Name(name), annotation=cst.Annotation(cst.Name("Any")), value=updated.value, simple=1)
            return ann
        return updated


def run_add_any_annotations(root: Path) -> int:
    changed = 0
    for p in iter_py_files(root):
        # avoid tests by default
        if any(part == "tests" for part in p.parts):
            continue
        src = read_text(p)
        try:
            mod = cst.parse_module(src)
        except Exception:
            continue
        fixer = AddAnyAnn()
        new_mod = mod.visit(fixer)
        code = new_mod.code
        if fixer.add_any:
            if "from typing import Any" not in code and "import typing" not in code:
                code = "from typing import Any\n\n" + code
        if code != src:
            p.write_text(code, encoding="utf8")
            print("add_any_annotations: updated", p)
            changed += 1
    return changed


# === Codemod 5: Widen edit_payload operations (targeted file replacement) ===
def run_widen_edit_payload(root: Path) -> int:
    target = root / EDIT_PAYLOAD_FILE
    if not target.exists():
        print("widen_edit_payload: target file not found:", target)
        return 0
    src = read_text(target)
    if re.search(EDIT_PAYLOAD_OLD, src):
        new = re.sub(EDIT_PAYLOAD_OLD, EDIT_PAYLOAD_NEW, src)
        target.write_text(new, encoding="utf8")
        print("widen_edit_payload: updated", target)
        return 1
    print("widen_edit_payload: pattern not found in", target)
    return 0


# === Runner ===
ALL_TRANSFORMS = {
    "fix_callable": run_fix_callable,
    "add_typing_imports": run_add_typing_imports,
    "optionalize_defaults": run_optionalize_defaults,
    "add_any_annotations": run_add_any_annotations,
    "widen_edit_payload": run_widen_edit_payload,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", help="Project root (overrides auto-detected parent of this script)", default=None)
    parser.add_argument("--only", help="Comma-separated list of transforms to run (names)", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    script_path = Path(__file__)
    override_root = Path(args.root).resolve() if args.root else None
    root = project_root_from_script(script_path, override_root)
    print("Project root:", root)

    requested = None
    if args.only:
        requested = {name.strip() for name in args.only.split(",")}

    total_changed = 0
    for name, fn in ALL_TRANSFORMS.items():
        if requested and name not in requested:
            continue
        print("Running:", name)
        try:
            changed = fn(root)
            total_changed += changed
        except Exception as exc:
            print(f"Transform {name} failed: {exc}", file=sys.stderr)

    print("Done. Files changed:", total_changed)
    print("Inspect changes with 'git status' and 'git diff'. Commit changes if OK.")


if __name__ == "__main__":
    main()