# -*- coding: utf-8 -*-
"""
X-radia Metadata Extractor - System Checker
============================================

This script automatically detects and validates your system configuration
for running the X-radia Metadata Extractor tool.

Features:
- Detects Python version and installation path
- Checks for XradiaPy library availability
- Validates required dependencies
- Identifies Xradia software installation
- Provides setup recommendations

Run this script first to diagnose any setup issues:
    python system_check.py
"""

from __future__ import print_function
import sys
import os
import platform
import subprocess

# ANSI color codes for terminal output
class Colors:
    """Terminal color codes for formatted output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def supports_color():
    """Check if the terminal supports color output"""
    if os.name == 'nt':
        return os.environ.get('ANSICON') is not None
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

def colored(text, color):
    """Return colored text if supported, otherwise plain text"""
    if supports_color():
        return color + text + Colors.END
    return text

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(colored(title, Colors.BOLD + Colors.HEADER))
    print("=" * 60)

def print_success(message):
    """Print success message in green"""
    print(colored("[OK] ", Colors.GREEN) + message)

def print_warning(message):
    """Print warning message in yellow"""
    print(colored("[WARNING] ", Colors.YELLOW) + message)

def print_error(message):
    """Print error message in red"""
    print(colored("[ERROR] ", Colors.RED) + message)

def print_info(message):
    """Print info message in blue"""
    print(colored("[INFO] ", Colors.BLUE) + message)

def check_python_version():
    """Check Python version and installation details"""
    print_header("Python Environment")
    
    version_info = sys.version_info
    version_str = "{0}.{1}.{2}".format(version_info.major, version_info.minor, version_info.micro)
    
    print("Python Version: {0}".format(version_str))
    print("Python Path: {0}".format(sys.executable))
    print("Platform: {0}".format(platform.platform()))
    
    # Check if Python 2.7
    if version_info.major == 2 and version_info.minor == 7:
        print_success("Python 2.7 detected - Compatible with XradiaPy")
        return True
    elif version_info.major == 3:
        print_warning("Python 3.x detected")
        print_info("XradiaPy requires Python 2.7")
        print_info("You may need to install Python 2.7 or use a virtual environment")
        return False
    else:
        print_error("Unsupported Python version")
        return False

def check_xradiaPy():
    """Check for XradiaPy library installation"""
    print_header("XradiaPy Library")
    
    try:
        import XradiaPy
        print_success("XradiaPy is installed and importable")
        
        # Try to get version info if available
        if hasattr(XradiaPy, '__version__'):
            print("XradiaPy Version: {0}".format(XradiaPy.__version__))
        
        # Check for Data module
        if hasattr(XradiaPy, 'Data'):
            print_success("XradiaPy.Data module available")
        else:
            print_warning("XradiaPy.Data module not found")
        
        return True
    except ImportError as e:
        print_error("XradiaPy is NOT installed or not in Python path")
        print_info("Error details: {0}".format(str(e)))
        return False

def find_xradia_installation():
    """Attempt to find Xradia software installation"""
    print_header("Xradia Software Detection")
    
    # Common installation paths
    common_paths = []
    
    if os.name == 'nt':  # Windows
        common_paths = [
            r"C:\Program Files\Xradia",
            r"C:\Program Files (x86)\Xradia",
            r"C:\Program Files\Zeiss\Xradia",
            r"C:\Program Files (x86)\Zeiss\Xradia",
            r"C:\Xradia",
            os.path.expandvars(r"%PROGRAMFILES%\Xradia"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Xradia"),
        ]
    elif sys.platform == 'darwin':  # macOS
        common_paths = [
            "/Applications/Xradia",
            "/Applications/Zeiss/Xradia",
            os.path.expanduser("~/Applications/Xradia"),
        ]
    else:  # Linux
        common_paths = [
            "/opt/xradia",
            "/opt/zeiss/xradia",
            "/usr/local/xradia",
            os.path.expanduser("~/xradia"),
        ]
    
    found_paths = []
    for path in common_paths:
        if os.path.exists(path):
            found_paths.append(path)
    
    if found_paths:
        print_success("Found Xradia installation(s):")
        for path in found_paths:
            print("  - {0}".format(path))
        return found_paths
    else:
        print_warning("No Xradia installation found in common locations")
        print_info("If Xradia is installed elsewhere, add it to PYTHONPATH")
        return []

def check_dependencies():
    """Check for required Python dependencies"""
    print_header("Python Dependencies")
    
    dependencies = [
        ("numpy", "Numerical computing"),
        ("configparser", "Configuration file parsing"),
        ("future", "Python 2/3 compatibility"),
    ]
    
    optional_deps = [
        ("requests", "GitHub integration (optional)"),
        ("subprocess32", "Python 2.7 subprocess backport"),
    ]
    
    all_ok = True
    
    print("\nRequired dependencies:")
    for module, description in dependencies:
        try:
            __import__(module)
            print_success("{0} - {1}".format(module, description))
        except ImportError:
            print_error("{0} - {1} [NOT INSTALLED]".format(module, description))
            all_ok = False
    
    print("\nOptional dependencies:")
    for module, description in optional_deps:
        try:
            __import__(module)
            print_success("{0} - {1}".format(module, description))
        except ImportError:
            print_info("{0} - {1} [Not installed]".format(module, description))
    
    return all_ok

def check_pythonpath():
    """Display Python path information"""
    print_header("Python Path Configuration")
    
    print("sys.path entries:")
    for i, path in enumerate(sys.path):
        print("  {0}: {1}".format(i, path))
    
    pythonpath = os.environ.get('PYTHONPATH', '')
    if pythonpath:
        print("\nPYTHONPATH environment variable:")
        for path in pythonpath.split(os.pathsep):
            print("  - {0}".format(path))
    else:
        print_info("PYTHONPATH environment variable is not set")

def check_permissions():
    """Check for admin/elevated permissions"""
    print_header("Permissions Check")
    
    try:
        if os.name == 'nt':  # Windows
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        else:  # Unix-like
            is_admin = os.geteuid() == 0
        
        if is_admin:
            print_success("Running with administrator/root privileges")
        else:
            print_info("Running as standard user (may affect some operations)")
        return is_admin
    except Exception as e:
        print_warning("Could not determine privilege level: {0}".format(str(e)))
        return None

def generate_recommendations(python_ok, xradiaPy_ok, deps_ok, xradia_paths):
    """Generate setup recommendations based on checks"""
    print_header("Recommendations")
    
    recommendations = []
    
    if not python_ok:
        recommendations.append(
            "1. Install Python 2.7:\n"
            "   - Windows: Download from https://www.python.org/downloads/release/python-2718/\n"
            "   - macOS: Use pyenv or download installer\n"
            "   - Linux: Use your package manager (e.g., apt install python2.7)"
        )
    
    if not xradiaPy_ok:
        recommendations.append(
            "2. Install XradiaPy:\n"
            "   - Install the Xradia Software Suite from Zeiss\n"
            "   - Ensure the Python bindings are included in installation\n"
            "   - Add the Xradia Python directory to PYTHONPATH"
        )
        
        if xradia_paths:
            recommendations.append(
                "   Found Xradia at: {0}\n"
                "   Try adding this to PYTHONPATH:\n"
                "   - Windows: set PYTHONPATH=%PYTHONPATH%;{0}\\Python\n"
                "   - Unix: export PYTHONPATH=$PYTHONPATH:{0}/Python".format(xradia_paths[0])
            )
    
    if not deps_ok:
        recommendations.append(
            "3. Install missing dependencies:\n"
            "   pip install -r requirements.txt"
        )
    
    if recommendations:
        print("\nSetup steps needed:")
        for rec in recommendations:
            print(rec)
    else:
        print_success("Your system is ready to run X-radia Metadata Extractor!")
        print("\nTo get started, run:")
        print("  python main.py")
        print("\nOr from the new_enhanced_interactive package:")
        print("  python -m new_enhanced_interactive.main")

def main():
    """Run all system checks"""
    print(colored("\n" + "=" * 60, Colors.BOLD))
    print(colored("  X-radia Metadata Extractor - System Check", Colors.BOLD + Colors.HEADER))
    print(colored("=" * 60 + "\n", Colors.BOLD))
    
    # Run all checks
    python_ok = check_python_version()
    xradiaPy_ok = check_xradiaPy()
    xradia_paths = find_xradia_installation()
    deps_ok = check_dependencies()
    check_pythonpath()
    check_permissions()
    
    # Generate recommendations
    generate_recommendations(python_ok, xradiaPy_ok, deps_ok, xradia_paths)
    
    print("\n" + "=" * 60)
    
    # Return exit code based on checks
    if python_ok and xradiaPy_ok and deps_ok:
        print(colored("System check PASSED - Ready to run!", Colors.GREEN + Colors.BOLD))
        return 0
    else:
        print(colored("System check found issues - See recommendations above", Colors.YELLOW + Colors.BOLD))
        return 1

if __name__ == "__main__":
    sys.exit(main())
