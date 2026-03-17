# -*- coding: utf-8 -*-
"""
X-radia Metadata Extractor - Setup Wizard
==========================================

Interactive setup wizard to help users configure the X-radia Metadata Extractor.
This wizard guides you through:
- Verifying system requirements
- Installing dependencies
- Configuring the environment
- Setting up PyCharm integration

Run this script after downloading the repository:
    python setup_wizard.py
"""

from __future__ import print_function
import sys
import os
import subprocess
import platform

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def supports_color():
    if os.name == 'nt':
        return os.environ.get('ANSICON') is not None
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

def colored(text, color):
    if supports_color():
        return color + text + Colors.END
    return text

def print_banner():
    """Print setup wizard banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║       X-radia Metadata Extractor - Setup Wizard          ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """
    print(colored(banner, Colors.HEADER + Colors.BOLD))

def print_step(step_num, total, description):
    """Print a step header"""
    print("\n" + "─" * 60)
    print(colored("Step {0}/{1}: {2}".format(step_num, total, description), Colors.BOLD + Colors.BLUE))
    print("─" * 60)

def get_input(prompt, valid_options=None, default=None):
    """Get user input with validation"""
    if default:
        prompt = "{0} [{1}]: ".format(prompt, default)
    else:
        prompt = "{0}: ".format(prompt)
    
    while True:
        try:
            response = raw_input(prompt).strip()
        except NameError:
            response = input(prompt).strip()
        
        if not response and default:
            return default
        
        if valid_options and response.lower() not in [v.lower() for v in valid_options]:
            print("Please enter one of: {0}".format(", ".join(valid_options)))
            continue
        
        return response

def run_command(command, shell=True, capture=True):
    """Run a shell command and return output"""
    try:
        if capture:
            result = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = result.communicate()
            return result.returncode, stdout, stderr
        else:
            return subprocess.call(command, shell=shell), None, None
    except Exception as e:
        return -1, None, str(e)

def check_python():
    """Check Python version"""
    version = sys.version_info
    return version.major == 2 and version.minor == 7

def check_pip():
    """Check if pip is available"""
    code, _, _ = run_command("pip --version")
    return code == 0

def install_dependencies():
    """Install Python dependencies"""
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    
    if not os.path.exists(req_file):
        print(colored("[ERROR] requirements.txt not found!", Colors.RED))
        return False
    
    print("Installing dependencies from requirements.txt...")
    code, _, _ = run_command("pip install -r {0}".format(req_file), capture=False)
    
    return code == 0

def create_env_file():
    """Create .env file from template"""
    env_example = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.example")
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    
    if os.path.exists(env_file):
        print(colored("[INFO] .env file already exists", Colors.BLUE))
        return True
    
    if os.path.exists(env_example):
        try:
            with open(env_example, 'r') as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
            print(colored("[OK] Created .env file from template", Colors.GREEN))
            return True
        except Exception as e:
            print(colored("[ERROR] Failed to create .env: {0}".format(str(e)), Colors.RED))
            return False
    else:
        print(colored("[INFO] No .env.example template found", Colors.BLUE))
        return True

def setup_pycharm_config():
    """Create PyCharm run configuration"""
    idea_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".idea")
    runconfig_dir = os.path.join(idea_dir, "runConfigurations")
    
    if not os.path.exists(runconfig_dir):
        os.makedirs(runconfig_dir)
    
    # Main run configuration
    main_config = """<?xml version="1.0" encoding="UTF-8"?>
<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="Run X-radia Metadata Extractor" type="PythonConfigurationType" factoryName="Python">
    <module name="X-radia-metadata" />
    <option name="INTERPRETER_OPTIONS" value="" />
    <option name="PARENT_ENVS" value="true" />
    <envs>
      <env name="PYTHONUNBUFFERED" value="1" />
    </envs>
    <option name="SDK_HOME" value="" />
    <option name="WORKING_DIRECTORY" value="$PROJECT_DIR$" />
    <option name="IS_MODULE_SDK" value="true" />
    <option name="ADD_CONTENT_ROOTS" value="true" />
    <option name="ADD_SOURCE_ROOTS" value="true" />
    <option name="SCRIPT_NAME" value="$PROJECT_DIR$/new_enhanced_interactive/main.py" />
    <option name="PARAMETERS" value="" />
    <option name="SHOW_COMMAND_LINE" value="false" />
    <option name="EMULATE_TERMINAL" value="true" />
    <option name="MODULE_MODE" value="false" />
    <option name="REDIRECT_INPUT" value="false" />
    <option name="INPUT_FILE" value="" />
    <method v="2" />
  </configuration>
</component>
"""
    
    # System check configuration
    check_config = """<?xml version="1.0" encoding="UTF-8"?>
<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="System Check" type="PythonConfigurationType" factoryName="Python">
    <module name="X-radia-metadata" />
    <option name="INTERPRETER_OPTIONS" value="" />
    <option name="PARENT_ENVS" value="true" />
    <envs>
      <env name="PYTHONUNBUFFERED" value="1" />
    </envs>
    <option name="SDK_HOME" value="" />
    <option name="WORKING_DIRECTORY" value="$PROJECT_DIR$" />
    <option name="IS_MODULE_SDK" value="true" />
    <option name="ADD_CONTENT_ROOTS" value="true" />
    <option name="ADD_SOURCE_ROOTS" value="true" />
    <option name="SCRIPT_NAME" value="$PROJECT_DIR$/system_check.py" />
    <option name="PARAMETERS" value="" />
    <option name="SHOW_COMMAND_LINE" value="false" />
    <option name="EMULATE_TERMINAL" value="true" />
    <option name="MODULE_MODE" value="false" />
    <option name="REDIRECT_INPUT" value="false" />
    <option name="INPUT_FILE" value="" />
    <method v="2" />
  </configuration>
</component>
"""
    
    try:
        with open(os.path.join(runconfig_dir, "Run_X_radia_Metadata_Extractor.xml"), 'w') as f:
            f.write(main_config)
        with open(os.path.join(runconfig_dir, "System_Check.xml"), 'w') as f:
            f.write(check_config)
        print(colored("[OK] Created PyCharm run configurations", Colors.GREEN))
        return True
    except Exception as e:
        print(colored("[WARNING] Could not create PyCharm configs: {0}".format(str(e)), Colors.YELLOW))
        return False

def find_python27():
    """Try to find Python 2.7 installation"""
    possible_paths = []
    
    if os.name == 'nt':  # Windows
        possible_paths = [
            r"C:\Python27\python.exe",
            r"C:\Program Files\Python27\python.exe",
            r"C:\Program Files (x86)\Python27\python.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python27\python.exe"),
        ]
    else:  # Unix-like
        possible_paths = [
            "/usr/bin/python2.7",
            "/usr/local/bin/python2.7",
            "/opt/local/bin/python2.7",
            os.path.expanduser("~/.pyenv/versions/2.7.18/bin/python"),
        ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Try which/where command
    cmd = "where python27" if os.name == 'nt' else "which python2.7"
    code, stdout, _ = run_command(cmd)
    if code == 0 and stdout:
        return stdout.decode().strip().split('\n')[0]
    
    return None

def main():
    """Main setup wizard"""
    print_banner()
    
    total_steps = 5
    
    # Step 1: System Check
    print_step(1, total_steps, "Checking System Requirements")
    
    print("\nCurrent Python: {0}".format(sys.version))
    print("Platform: {0}".format(platform.platform()))
    
    python_ok = check_python()
    if python_ok:
        print(colored("[OK] Python 2.7 detected", Colors.GREEN))
    else:
        print(colored("[WARNING] Python 2.7 required for XradiaPy compatibility", Colors.YELLOW))
        
        python27_path = find_python27()
        if python27_path:
            print(colored("[INFO] Found Python 2.7 at: {0}".format(python27_path), Colors.BLUE))
            print("Please re-run this wizard with Python 2.7:")
            print("  {0} setup_wizard.py".format(python27_path))
        else:
            print(colored("[INFO] Python 2.7 not found on this system", Colors.YELLOW))
            print("\nTo install Python 2.7:")
            if os.name == 'nt':
                print("  - Download from: https://www.python.org/downloads/release/python-2718/")
            elif sys.platform == 'darwin':
                print("  - Using Homebrew: brew install python@2")
                print("  - Or use pyenv: pyenv install 2.7.18")
            else:
                print("  - Ubuntu/Debian: sudo apt install python2.7")
                print("  - Or use pyenv: pyenv install 2.7.18")
    
    proceed = get_input("\nContinue with current Python?", ["y", "n"], "y")
    if proceed.lower() != 'y':
        print("\nExiting wizard. Please install Python 2.7 and run again.")
        return 1
    
    # Step 2: Check/Install Dependencies
    print_step(2, total_steps, "Installing Dependencies")
    
    if not check_pip():
        print(colored("[ERROR] pip is not available", Colors.RED))
        print("Please install pip first: https://pip.pypa.io/en/stable/installation/")
        return 1
    
    install_deps = get_input("Install Python dependencies from requirements.txt?", ["y", "n"], "y")
    if install_deps.lower() == 'y':
        if install_dependencies():
            print(colored("[OK] Dependencies installed successfully", Colors.GREEN))
        else:
            print(colored("[WARNING] Some dependencies may have failed to install", Colors.YELLOW))
    
    # Step 3: XradiaPy Check
    print_step(3, total_steps, "Checking XradiaPy Library")
    
    try:
        import XradiaPy
        print(colored("[OK] XradiaPy is available", Colors.GREEN))
    except ImportError:
        print(colored("[WARNING] XradiaPy is not installed", Colors.YELLOW))
        print("\nXradiaPy is a proprietary library from Zeiss/Xradia.")
        print("To install XradiaPy:")
        print("  1. Install the Xradia Software Suite from Zeiss")
        print("  2. Ensure Python bindings are included in the installation")
        print("  3. Add the Xradia Python directory to your PYTHONPATH")
        print("\nCommon Xradia Python paths:")
        if os.name == 'nt':
            print("  - C:\\Program Files\\Xradia\\Python")
            print("  - C:\\Program Files (x86)\\Zeiss\\Xradia\\Python")
        else:
            print("  - /opt/xradia/python")
            print("  - /Applications/Xradia/Python")
    
    # Step 4: Environment Configuration
    print_step(4, total_steps, "Setting Up Environment")
    
    create_env = get_input("Create environment configuration file (.env)?", ["y", "n"], "y")
    if create_env.lower() == 'y':
        create_env_file()
    
    # Step 5: PyCharm Configuration
    print_step(5, total_steps, "PyCharm Integration")
    
    setup_pycharm = get_input("Create PyCharm run configurations?", ["y", "n"], "y")
    if setup_pycharm.lower() == 'y':
        setup_pycharm_config()
    
    # Summary
    print("\n" + "═" * 60)
    print(colored("  Setup Complete!", Colors.GREEN + Colors.BOLD))
    print("═" * 60)
    
    print("\nNext Steps:")
    print("  1. Run 'python system_check.py' to verify your setup")
    print("  2. Open this folder in PyCharm")
    print("  3. Configure Python 2.7 interpreter with XradiaPy")
    print("  4. Run 'main.py' or use the run configuration")
    print("\nFor detailed instructions, see:")
    print("  - INSTALL.md - Installation guide")
    print("  - README.md  - Full documentation")
    
    print("\n" + colored("Happy metadata extracting!", Colors.GREEN))
    return 0

if __name__ == "__main__":
    sys.exit(main())
