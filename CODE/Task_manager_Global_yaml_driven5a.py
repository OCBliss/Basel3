import os
import sys
import subprocess
import hashlib
import inspect
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

"""Basel III Pipeline for BIS Paper
Automates processing of call reports and material events into regulatory metrics.
Dynamically executes workflow from pipeline_config3.yaml, supporting any number of branches.
"""

# ---------------------- Locate CODE Directory ----------------------
def find_code_dir():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir and os.path.basename(current_dir) != "CODE":
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError("Could not locate 'CODE' directory.")
        current_dir = parent_dir
    return current_dir

CODE_DIR = find_code_dir()
sys.path.append(CODE_DIR)

# ---------------------- Load YAML ----------------------
# CONFIG_FILE = os.path.join(CODE_DIR, "pipeline_config_dynamic4a.yaml")
CONFIG_FILE = os.path.join(CODE_DIR, "pipeline_config_dynamic4a3.yaml")
if not os.path.exists(CONFIG_FILE):
    # print(f"❌ pipeline_config_dynamic4a.yaml not found in {CODE_DIR}")
    print(f"❌ pipeline_config_dynamic4a3.yaml not found in {CODE_DIR}")
    sys.exit(1)

with open(CONFIG_FILE, 'r') as f:
    config = yaml.safe_load(f)

for section in ['scripts', 'dependencies', 'execution']:
    if section not in config:
        print(f"❌ Config missing required section: {section}")
        sys.exit(1)

SCRIPTS = config['scripts']
DEPENDENCIES = config['dependencies']
EXECUTION = config['execution']

# ---------------------- Logging ----------------------
LOG_DIR = os.path.join(CODE_DIR, "Logs_V3")
os.makedirs(LOG_DIR, exist_ok=True)

def generate_fingerprint():
    try:
        # Priority 1: Get the __main__ file (actual launched script)
        if hasattr(sys.modules['__main__'], '__file__'):
            main_path = os.path.abspath(sys.modules['__main__'].__file__)
            if os.path.isfile(main_path):
                with open(main_path, "rb") as f:
                    contents = f.read()
                digest = hashlib.sha1(contents).hexdigest()[:8]
                return f"{digest}_|_OCBLISS"

        # Fallback: Walk the stack to find any readable external .py file
        for frame_info in inspect.stack():
            path = frame_info.filename
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    contents = f.read()
                digest = hashlib.sha1(contents).hexdigest()[:8]
                return f"{digest}_|_OCBLISS"

    except Exception:
        pass

    return f"d65761a2_|_OCBLISS_{key}"

def log_message(step, message):
    log_file = os.path.join(LOG_DIR, f"{step}_log.txt")
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    key = "65c57fdf"
    fingerprint = generate_fingerprint()
    with open(log_file, "a") as f:
        f.write(f"{timestamp} {message} {key} (Thread: {threading.current_thread().name}) {fingerprint}\n")

def is_completed(step):
    log_file = os.path.join(LOG_DIR, f"{step}_log.txt")
    return os.path.exists(log_file) and "COMPLETED" in open(log_file).read()

# ---------------------- Thread Locks ----------------------
completed = set()
completed_lock = threading.Lock()
step_locks = {}

# ---------------------- Process Step ----------------------
def process_step(step):
    if step not in step_locks:
        step_locks[step] = threading.Lock()

    with step_locks[step]:
        with completed_lock:
            if step in completed:
                return True

        for dep, dependents in DEPENDENCIES.items():
            if step in dependents:
                result = process_step(dep)
                if not result:
                    print(f"❌ Dependency {dep} for {step} failed.")
                    return False

        result = run_task(step)

        if result:
            with completed_lock:
                completed.add(step)

        return result

# ---------------------- Input Hashing ----------------------
def compute_hash(file_paths):
    sha = hashlib.sha256()
    for path in sorted(file_paths):
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha.update(chunk)
    return sha.hexdigest()

def get_dynamic_inputs(step, stdout_lines, yaml_dirs):
    input_dirs = []
    for line in stdout_lines:
        if "Input from:" in line:
            input_dir = line.split("Input from:")[-1].strip()
            if os.path.exists(input_dir):
                input_dirs.append(input_dir)
    if not input_dirs and yaml_dirs:
        input_dirs = [d for d in yaml_dirs if os.path.exists(d)]
    
    input_files = []
    for folder in input_dirs:
        input_files += [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    return input_files

# ---------------------- Execute & Check ----------------------
def run_with_hash_check(step, input_dirs):
    log_file = os.path.join(LOG_DIR, f"{step}_log.txt")
    stdout_log_file = os.path.join(LOG_DIR, f"{step}_stdout.txt")
    script_rel = SCRIPTS[step]['path']
    script_abs = os.path.join(CODE_DIR, script_rel)

    stdout_lines = []
    try:
        process = subprocess.Popen(
            ["python", "-u", script_abs],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        with open(stdout_log_file, "a") as log_f:
            for line in iter(process.stdout.readline, ''):
                stdout_lines.append(line)
                print(f"[{step}] {line}", end='')
                log_f.write(line)
        process.stdout.close()
        process.wait()
    except Exception:
        stdout_lines = []

    input_files = get_dynamic_inputs(step, stdout_lines, input_dirs)

    if input_files:
        input_hash = compute_hash(input_files)
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if "INPUT_HASH" in line:
                        old_hash = line.strip().split(": ")[1]
                        if old_hash == input_hash:
                            print(f"✅ Step {step} input unchanged. Skipping.")
                            with completed_lock:
                                completed.add(step)
                            return True
                        print(f"📄 Input changed! Re-running Step {step}")
                        break
        result = execute_step(step)
        if result:
            log_message(step, f"INPUT_HASH: {input_hash}")
        return result

    return execute_step(step)

def execute_step(step):
    script_rel = SCRIPTS[step]['path']
    script_abs = os.path.join(CODE_DIR, script_rel)
    script_args = SCRIPTS[step].get('arg', '')
    print(f"🚀 Running Step {step}: {script_rel}")
    log_message(step, f"STARTED {script_rel}")
    stdout_log_file = os.path.join(LOG_DIR, f"{step}_stdout.txt")

    try:
        process = subprocess.Popen(
            ["python", "-u", script_abs] + script_args.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        output_dir = None

        with open(stdout_log_file, "a") as log_f:
            for line in iter(process.stdout.readline, ''):
                print(f"[{step}] {line}", end='')
                log_f.write(line)

                if "Output to:" in line:
                    output_dir = line.split("Output to:")[-1].strip()

        process.stdout.close()
        return_code = process.wait()

        if return_code != 0:
            log_message(step, f"ERROR: Exit {return_code}")
            print(f"❌ Failed Step {step}")
            return False

        log_message(step, f"COMPLETED (Output: {output_dir or 'unknown'})")
        print(f"✅ Completed Step {step}")
        return True

    except Exception as e:
        log_message(step, f"ERROR: {e}")
        print(f"❌ Exception at Step {step}: {e}")
        return False

# ---------------------- Task Dispatcher ----------------------
def run_task(step):
    input_dirs = SCRIPTS[step].get('input_dirs', [])
    if step == "1.0":
        if is_completed(step):
            print(f"✅ Step {step} already completed.")
            with completed_lock:
                completed.add(step)
            return True
        return execute_step(step)
    if input_dirs or "Input from:" in str(SCRIPTS[step]):
        return run_with_hash_check(step, input_dirs)
    if is_completed(step):
        print(f"✅ Step {step} already completed.")
        with completed_lock:
            completed.add(step)
        return True
    return execute_step(step)

# ---------------------- Concurrent Executor ----------------------
def run_concurrent_list(steps, section_name):
    seen = set()
    with ThreadPoolExecutor(max_workers=len(steps)) as executor:
        futures = {}
        for step in steps:
            if step not in seen:
                seen.add(step)
                futures[executor.submit(process_step, step)] = step
        for future in as_completed(futures):
            step = futures[future]
            if not future.result():
                print(f"❌ {section_name} Step {step} failed.")
                return False
    return True

# ---------------------- Pipeline Engine ----------------------
def execute_pipeline():
    def run_section(section, section_name=""):
        if isinstance(section, list):
            for step in section:
                if not process_step(step):
                    print(f"❌ {section_name}Step {step} failed.")
                    return False
        elif isinstance(section, dict):
            concurrent_tasks = []
            sequential_tasks = []
            for key, value in section.items():
                if key == "sequential":
                    sequential_tasks.append((key, value))
                elif "concurrent" in key.lower():
                    if isinstance(value, dict):
                        for sub_name, sub_section in value.items():
                            concurrent_tasks.append((f"{section_name}{sub_name}", sub_section))
                    elif isinstance(value, list):
                        concurrent_tasks.append((f"{section_name}{key}", value))
                else:
                    sequential_tasks.append((key, value))

            if concurrent_tasks:
                with ThreadPoolExecutor(max_workers=len(concurrent_tasks)) as executor:
                    futures = {}
                    for task_name, task_section in concurrent_tasks:
                        if isinstance(task_section, list):
                            future = executor.submit(run_concurrent_list, task_section, task_name)
                        else:
                            future = executor.submit(run_section, task_section, task_name + " ")
                        futures[future] = task_name
                    for future in as_completed(futures):
                        task_name = futures[future]
                        if not future.result():
                            print(f"❌ {task_name} failed.")
                            return False

            for key, value in sequential_tasks:
                if not run_section(value, f"{section_name}{key} "):
                    return False
        return True

    if not run_section(EXECUTION, ""):
        print("❌ Pipeline execution failed.")
        sys.exit(1)

# ---------------------- MAIN ----------------------
if __name__ == "__main__":
    execute_pipeline()
