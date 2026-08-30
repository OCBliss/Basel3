#!/usr/bin/env python3
"""Run the Basel III Python pipeline described by YAML.

The ``execution`` section is authoritative and ordered. Dependencies validate
the plan; they never pull omitted work into a run. Each execution list item is
a barrier, so phase types such as ``intermediate_steps`` may be revisited.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shlex
import subprocess
import sys
import threading
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parent
SOURCE_DIR = PROJECT_ROOT / "src"
DEFAULT_CONFIG = PIPELINE_DIR / "pipeline_config_dynamic.yaml"
PHASE_KEYS = {
    "sequential",
    "intermediate_steps",
    "concurrent_groups",
    "concurrent_branches",
}
SCRIPT_KEYS = {"path", "args", "inputs", "outputs", "create_dirs", "cwd"}


class ConfigError(Exception):
    """Raised when the pipeline configuration is invalid."""


class PipelineError(Exception):
    """Raised when pipeline execution cannot continue."""


class StepFailure(PipelineError):
    """Raised when a concrete pipeline step fails."""


class PipelineCancelled(PipelineError):
    """Raised in work cancelled after another step fails."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: MappingNode, deep: bool = False
) -> Dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: Dict[Any, Any] = {}
    first_marks: Dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if duplicate:
            first = first_marks[key]
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key {key!r}; first defined on line {first.line + 1}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
        first_marks[key] = key_node.start_mark
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


@dataclass(frozen=True)
class Phase:
    kind: str
    payload: Any
    location: str


@dataclass(frozen=True)
class ScriptSpec:
    step_id: str
    path: Path
    args: Tuple[str, ...]
    inputs: Tuple[Path, ...]
    outputs: Tuple[Path, ...]
    create_dirs: Tuple[Path, ...]
    cwd: Path


@dataclass(frozen=True)
class PipelineConfig:
    path: Path
    scripts: Mapping[str, ScriptSpec]
    dependents: Mapping[str, Tuple[str, ...]]
    prerequisites: Mapping[str, Tuple[str, ...]]
    execution: Tuple[Phase, ...]
    max_parallel_steps: int
    log_root: Path


def _shell_join(command: Sequence[str]) -> str:
    join = getattr(shlex, "join", None)
    if join is not None:
        return join(command)
    return " ".join(shlex.quote(part) for part in command)


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read config {path}: {error}") from error
    try:
        loaded = yaml.load(text, Loader=UniqueKeyLoader)
    except yaml.YAMLError as error:
        raise ConfigError(f"invalid YAML in {path}: {error}") from error
    if not isinstance(loaded, Mapping):
        raise ConfigError("the YAML document must be a mapping")
    return loaded


def _resolve_path(value: Any, base: Path, location: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{location} must be a non-empty path string")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve(strict=False)


def _path_list(value: Any, base: Path, location: str) -> Tuple[Path, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    elif isinstance(value, Mapping):
        values = list(value.values())
    else:
        raise ConfigError(f"{location} must be a path, list, or mapping")
    return tuple(
        _resolve_path(item, base, f"{location}[{index}]")
        for index, item in enumerate(values)
    )


def _artifact_exists(path: Path) -> bool:
    """Return whether a literal path or glob pattern has at least one match."""
    pattern = str(path)
    if glob.has_magic(pattern):
        return next(glob.iglob(pattern, recursive=True), None) is not None
    return path.exists()


def _step_list(value: Any, location: str, scripts: Set[str]) -> Tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{location} must be a non-empty list of step IDs")
    steps: List[str] = []
    for index, step in enumerate(value):
        if not isinstance(step, str) or step not in scripts:
            raise ConfigError(f"{location}[{index}] references unknown step {step!r}")
        if step in steps:
            raise ConfigError(f"{location} repeats step {step!r}")
        steps.append(step)
    return tuple(steps)


def _normalize_phases(
    node: Any, location: str, scripts: Set[str]
) -> Tuple[Phase, ...]:
    if not isinstance(node, list) or not node:
        raise ConfigError(f"{location} must be a non-empty ordered list")

    phases: List[Phase] = []
    for index, mapping in enumerate(node):
        phase_location = f"{location}[{index}]"
        if not isinstance(mapping, Mapping) or len(mapping) != 1:
            raise ConfigError(
                f"{phase_location} must contain exactly one phase mapping"
            )
        kind, payload = next(iter(mapping.items()))
        if kind not in PHASE_KEYS:
            raise ConfigError(f"{phase_location} has unknown phase type {kind!r}")
        location_with_kind = f"{phase_location}.{kind}"

        if kind in {"sequential", "intermediate_steps"}:
            phases.append(
                Phase(kind, _step_list(payload, location_with_kind, scripts), location_with_kind)
            )
        elif kind == "concurrent_groups":
            if isinstance(payload, list):
                groups = (("group", _step_list(payload, location_with_kind, scripts)),)
            elif isinstance(payload, Mapping) and payload:
                groups = tuple(
                    (
                        str(name),
                        _step_list(steps, f"{location_with_kind}.{name}", scripts),
                    )
                    for name, steps in payload.items()
                )
            else:
                raise ConfigError(
                    f"{location_with_kind} must be a step list or named groups"
                )
            phases.append(Phase(kind, groups, location_with_kind))
        else:
            if not isinstance(payload, Mapping) or not payload:
                raise ConfigError(f"{location_with_kind} must contain named branches")
            branches = tuple(
                (
                    str(name),
                    _normalize_phases(
                        branch, f"{location_with_kind}.{name}", scripts
                    ),
                )
                for name, branch in payload.items()
            )
            phases.append(Phase(kind, branches, location_with_kind))
    return tuple(phases)


def _validate_dependency_graph(
    raw: Any, scripts: Set[str]
) -> Tuple[Dict[str, Tuple[str, ...]], Dict[str, Tuple[str, ...]]]:
    if not isinstance(raw, Mapping):
        raise ConfigError("dependencies must be a mapping")
    dependents: Dict[str, Tuple[str, ...]] = {step: tuple() for step in scripts}
    prerequisite_lists: Dict[str, List[str]] = {step: [] for step in scripts}
    for parent, raw_children in raw.items():
        if not isinstance(parent, str) or parent not in scripts:
            raise ConfigError(f"dependencies has unknown prerequisite {parent!r}")
        children = _step_list(raw_children, f"dependencies.{parent}", scripts)
        if parent in children:
            raise ConfigError(f"step {parent!r} may not depend on itself")
        dependents[parent] = children
        for child in children:
            prerequisite_lists[child].append(parent)

    colors = {step: 0 for step in scripts}
    stack: List[str] = []

    def visit(step: str) -> None:
        colors[step] = 1
        stack.append(step)
        for child in dependents[step]:
            if colors[child] == 0:
                visit(child)
            elif colors[child] == 1:
                start = stack.index(child)
                raise ConfigError(
                    "dependency cycle detected: "
                    + " -> ".join(stack[start:] + [child])
                )
        stack.pop()
        colors[step] = 2

    for step in scripts:
        if colors[step] == 0:
            visit(step)
    prerequisites = {
        step: tuple(parents) for step, parents in prerequisite_lists.items()
    }
    return dependents, prerequisites


def _execution_steps(phases: Sequence[Phase]) -> List[str]:
    steps: List[str] = []
    for phase in phases:
        if phase.kind in {"sequential", "intermediate_steps"}:
            steps.extend(phase.payload)
        elif phase.kind == "concurrent_groups":
            for _, group_steps in phase.payload:
                steps.extend(group_steps)
        else:
            for _, branch_phases in phase.payload:
                steps.extend(_execution_steps(branch_phases))
    return steps


def load_config(path: Path = DEFAULT_CONFIG) -> PipelineConfig:
    config_path = path.expanduser().resolve(strict=False)
    raw = _load_yaml(config_path)
    allowed_top_level = {
        "scripts",
        "dependencies",
        "execution",
        "max_parallel_steps",
        "log_root",
    }
    unknown = set(raw) - allowed_top_level
    if unknown:
        raise ConfigError(f"unknown top-level configuration fields: {sorted(unknown)}")
    for required in ("scripts", "dependencies", "execution"):
        if required not in raw:
            raise ConfigError(f"configuration is missing {required!r}")

    raw_scripts = raw["scripts"]
    if not isinstance(raw_scripts, Mapping) or not raw_scripts:
        raise ConfigError("scripts must be a non-empty mapping")
    scripts: Dict[str, ScriptSpec] = {}
    for step_id, definition in raw_scripts.items():
        if not isinstance(step_id, str) or not step_id:
            raise ConfigError(f"invalid script ID {step_id!r}")
        if not isinstance(definition, Mapping):
            raise ConfigError(f"scripts.{step_id} must be a mapping")
        unknown_fields = set(definition) - SCRIPT_KEYS
        if unknown_fields:
            raise ConfigError(
                f"scripts.{step_id} has unknown fields: {sorted(unknown_fields)}"
            )
        if "path" not in definition:
            raise ConfigError(f"scripts.{step_id} is missing path")
        script_path = _resolve_path(
            definition["path"], SOURCE_DIR, f"scripts.{step_id}.path"
        )
        args = definition.get("args", [])
        if not isinstance(args, list):
            raise ConfigError(f"scripts.{step_id}.args must be a list")
        cwd = _resolve_path(
            definition.get("cwd", str(PROJECT_ROOT)),
            PROJECT_ROOT,
            f"scripts.{step_id}.cwd",
        )
        scripts[step_id] = ScriptSpec(
            step_id=step_id,
            path=script_path,
            args=tuple(str(arg) for arg in args),
            inputs=_path_list(
                definition.get("inputs"), PROJECT_ROOT, f"scripts.{step_id}.inputs"
            ),
            outputs=_path_list(
                definition.get("outputs"), PROJECT_ROOT, f"scripts.{step_id}.outputs"
            ),
            create_dirs=_path_list(
                definition.get("create_dirs"),
                PROJECT_ROOT,
                f"scripts.{step_id}.create_dirs",
            ),
            cwd=cwd,
        )

    script_ids = set(scripts)
    dependents, prerequisites = _validate_dependency_graph(
        raw["dependencies"], script_ids
    )
    execution = _normalize_phases(raw["execution"], "execution", script_ids)
    scheduled = _execution_steps(execution)
    duplicates = sorted(step for step in set(scheduled) if scheduled.count(step) > 1)
    if duplicates:
        raise ConfigError(f"execution schedules steps more than once: {duplicates}")
    if set(scheduled) != script_ids:
        raise ConfigError(
            "execution/script mismatch; "
            f"missing={sorted(script_ids - set(scheduled))}, "
            f"unknown={sorted(set(scheduled) - script_ids)}"
        )

    max_parallel_steps = raw.get("max_parallel_steps", min(8, len(scripts)))
    if not isinstance(max_parallel_steps, int) or max_parallel_steps < 1:
        raise ConfigError("max_parallel_steps must be a positive integer")
    log_root = _resolve_path(
        raw.get("log_root", "pipeline_logs"), PROJECT_ROOT, "log_root"
    )
    return PipelineConfig(
        path=config_path,
        scripts=scripts,
        dependents=dependents,
        prerequisites=prerequisites,
        execution=execution,
        max_parallel_steps=max_parallel_steps,
        log_root=log_root,
    )


class PipelineRunner:
    """Execute a validated pipeline with bounded concurrency and fail-fast cleanup."""

    def __init__(
        self, config: PipelineConfig, *, dry_run: bool = False, run_id: Optional[str] = None
    ) -> None:
        self.config = config
        self.dry_run = dry_run
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.log_dir = config.log_root / self.run_id
        self.stop_event = threading.Event()
        self.console_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.process_lock = threading.Lock()
        self.step_semaphore = threading.BoundedSemaphore(config.max_parallel_steps)
        self.step_futures: Dict[str, Future[ScriptSpec]] = {}
        self.completed: Set[str] = set()
        self.active_processes: Dict[str, subprocess.Popen[str]] = {}
        self.plan_counter = 0

    def preflight(self) -> None:
        """Validate scripts, working directories, and output collisions."""
        output_owners: Dict[Path, str] = {}
        for step_id, spec in self.config.scripts.items():
            if not spec.path.is_file():
                raise ConfigError(f"scripts.{step_id}.path does not exist: {spec.path}")
            if not spec.cwd.is_dir() and spec.cwd not in spec.create_dirs:
                raise ConfigError(
                    f"scripts.{step_id}.cwd does not exist: {spec.cwd}"
                )
            for output in spec.outputs:
                owner = output_owners.get(output)
                if owner is not None:
                    raise ConfigError(
                        f"output collision: steps {owner} and {step_id} both write {output}"
                    )
                output_owners[output] = step_id

    def initialize_logs(self) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=False)
        except OSError as error:
            raise PipelineError(f"cannot create log directory {self.log_dir}: {error}") from error

    def console(self, message: str, end: str = "\n") -> None:
        with self.console_lock:
            print(message, end=end, flush=True)

    def request_stop(self) -> None:
        self.stop_event.set()
        with self.process_lock:
            processes = list(self.active_processes.values())
        for process in processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass

    def _show_step(self, spec: ScriptSpec) -> None:
        self.plan_counter += 1
        command = [sys.executable, "-u", str(spec.path), *spec.args]
        self.console(f"[{self.plan_counter:02d}] {spec.step_id}")
        self.console(f"     cwd: {spec.cwd}")
        self.console(f"     command: {_shell_join(command)}")
        if spec.inputs:
            self.console("     inputs: " + ", ".join(str(path) for path in spec.inputs))
        if spec.outputs:
            self.console("     outputs: " + ", ".join(str(path) for path in spec.outputs))

    def _execute_step(self, spec: ScriptSpec) -> None:
        if self.stop_event.is_set():
            raise PipelineCancelled(f"step {spec.step_id} cancelled")
        with self.state_lock:
            missing_prerequisites = set(self.config.prerequisites[spec.step_id]) - self.completed
        if missing_prerequisites:
            raise StepFailure(
                f"step {spec.step_id} reached before prerequisite(s) "
                f"{sorted(missing_prerequisites)}"
            )
        missing_inputs = [path for path in spec.inputs if not _artifact_exists(path)]
        if missing_inputs:
            raise StepFailure(
                f"step {spec.step_id} has missing inputs: {missing_inputs}"
            )
        for directory in spec.create_dirs:
            directory.mkdir(parents=True, exist_ok=True)

        command = [sys.executable, "-u", str(spec.path), *spec.args]
        log_path = self.log_dir / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', spec.step_id)}.log"
        self.console(f"RUN  {spec.step_id}: {_shell_join(command)}")
        try:
            with log_path.open("w", encoding="utf-8", buffering=1) as log_file:
                log_file.write(f"cwd: {spec.cwd}\n")
                log_file.write(f"command: {_shell_join(command)}\n")
                process = subprocess.Popen(
                    command,
                    cwd=str(spec.cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                with self.process_lock:
                    self.active_processes[spec.step_id] = process
                assert process.stdout is not None
                for line in process.stdout:
                    log_file.write(line)
                    self.console(f"[{spec.step_id}] {line}", end="")
                process.stdout.close()
                return_code = process.wait()
        except OSError as error:
            raise StepFailure(f"could not run step {spec.step_id}: {error}") from error
        finally:
            with self.process_lock:
                self.active_processes.pop(spec.step_id, None)

        if return_code != 0:
            raise StepFailure(
                f"step {spec.step_id} exited with status {return_code}; log: {log_path}"
            )
        missing_outputs = [path for path in spec.outputs if not _artifact_exists(path)]
        if missing_outputs:
            raise StepFailure(
                f"step {spec.step_id} did not create outputs: {missing_outputs}"
            )
        with self.state_lock:
            self.completed.add(spec.step_id)
        self.console(f"DONE {spec.step_id}")

    def ensure_step(self, step_id: str) -> ScriptSpec:
        with self.state_lock:
            future = self.step_futures.get(step_id)
            if future is None:
                future = Future()
                self.step_futures[step_id] = future
                owner = True
            else:
                owner = False
        if not owner:
            return future.result()

        spec = self.config.scripts[step_id]
        try:
            if self.dry_run:
                self._show_step(spec)
                with self.state_lock:
                    self.completed.add(step_id)
            else:
                with self.step_semaphore:
                    self._execute_step(spec)
            future.set_result(spec)
            return spec
        except BaseException as error:
            future.set_exception(error)
            if not self.dry_run:
                self.request_stop()
            raise

    def _run_parallel(self, jobs: Sequence[Tuple[str, Any]]) -> None:
        if self.dry_run:
            for _, job in jobs:
                job()
            return
        executor = ThreadPoolExecutor(
            max_workers=min(len(jobs), self.config.max_parallel_steps),
            thread_name_prefix="pipeline",
        )
        futures = {executor.submit(job): name for name, job in jobs}
        errors: List[BaseException] = []
        try:
            for future in as_completed(futures):
                try:
                    future.result()
                except CancelledError:
                    continue
                except BaseException as error:
                    errors.append(error)
                    self.request_stop()
                    for other in futures:
                        if other is not future:
                            other.cancel()
            if errors:
                raise errors[0]
        finally:
            executor.shutdown(wait=True)

    def run_phases(self, phases: Sequence[Phase], scope: str = "pipeline") -> None:
        for index, phase in enumerate(phases, start=1):
            if self.stop_event.is_set() and not self.dry_run:
                raise PipelineCancelled(f"{scope} cancelled")
            self.console(f"\n== {scope} phase {index} ({phase.kind}) ==")
            if phase.kind in {"sequential", "intermediate_steps"}:
                for step in phase.payload:
                    self.ensure_step(step)
            elif phase.kind == "concurrent_groups":
                for name, steps in phase.payload:
                    self.console(f"Parallel barrier {scope}/{name}: {', '.join(steps)}")
                    self._run_parallel(
                        [
                            (step, lambda selected=step: self.ensure_step(selected))
                            for step in steps
                        ]
                    )
            else:
                self._run_parallel(
                    [
                        (
                            name,
                            lambda branch=name, nested=branch_phases: self.run_phases(
                                nested, f"{scope}/{branch}"
                            ),
                        )
                        for name, branch_phases in phase.payload
                    ]
                )

    def run(self) -> None:
        self.run_phases(self.config.execution)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true", dest="list_steps")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_{os.getpid()}"
    try:
        config = load_config(args.config)
        runner = PipelineRunner(config, dry_run=True, run_id=run_id)
        runner.preflight()
        if args.list_steps:
            for step_id, spec in config.scripts.items():
                prerequisites = config.prerequisites[step_id]
                print(
                    f"{step_id}: {spec.path.relative_to(SOURCE_DIR)} "
                    f"(needs: {', '.join(prerequisites) if prerequisites else '-'})"
                )
            return 0

        runner = PipelineRunner(config, dry_run=args.dry_run, run_id=run_id)
        if args.dry_run:
            print("Dry run only; no directories, logs, or subprocesses will be created.")
        else:
            runner.initialize_logs()
        runner.run()
        if args.dry_run:
            print(f"\nDry-run plan complete: {runner.plan_counter} unique steps.")
        else:
            print(f"\nPipeline completed successfully. Logs: {runner.log_dir}")
        return 0
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        if "runner" in locals():
            runner.request_stop()
        print("Pipeline interrupted.", file=sys.stderr)
        return 130
    except PipelineError as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
