# -*- coding: utf-8 -*-
"""
X-radia Metadata Extractor - Smart Start
=========================================

One-click startup that automatically:
1. Detects what's installed (with versions)
2. Shows a friendly status dashboard
3. Offers to install only what's missing
4. Guides you to start the app

Just run: python start.py
"""

from __future__ import print_function
import sys
import os
import platform
import subprocess

# ============================================================================
# VISUAL FORMATTING
# ============================================================================

class Colors:
    """Terminal colors (works on most systems)"""
    if os.name == 'nt':
        # Enable ANSI on Windows 10+
        os.system('')
    
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def supports_color():
    """Check if terminal supports colors"""
    if os.name == 'nt':
        return True  # Windows 10+ with ANSI enabled
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

def c(text, color):
    """Colorize text if supported"""
    if supports_color():
        return color + str(text) + Colors.END
    return str(text)

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

# ============================================================================
# STATUS ICONS AND FORMATTING
# ============================================================================

def icon_ok():
    return c("[OK]", Colors.GREEN + Colors.BOLD)

def icon_missing():
    return c("[MISSING]", Colors.RED + Colors.BOLD)

def icon_warning():
    return c("[!]", Colors.YELLOW + Colors.BOLD)

def icon_info():
    return c("[i]", Colors.BLUE)

def version_text(version):
    """Format version string"""
    if version:
        return c("v" + str(version), Colors.DIM)
    return c("(unknown version)", Colors.DIM)

# ============================================================================
# DEPENDENCY DETECTION
# ============================================================================

def get_package_version(package_name):
    """Get installed package version, or None if not installed"""
    try:
        module = __import__(package_name)
        # Try common version attributes
        for attr in ['__version__', 'VERSION', 'version']:
            if hasattr(module, attr):
                ver = getattr(module, attr)
                if callable(ver):
                    ver = ver()
                return str(ver)
        return "installed"
    except ImportError:
        return None

def check_all_dependencies():
    """
    Check all dependencies and return status dict.
    Returns: {name: {'installed': bool, 'version': str, 'required': bool, 'description': str}}
    """
    deps = {}
    
    # Core dependencies
    core = [
        ("numpy", "Numerical computing", True),
        ("configparser", "Configuration parsing", True),
        ("future", "Python 2/3 compatibility", True),
        ("six", "Python 2/3 utilities", False),
    ]
    
    # Optional dependencies
    optional = [
        ("requests", "GitHub integration", False),
        ("subprocess32", "Subprocess backport", False),
    ]
    
    # Special: XradiaPy
    deps["XradiaPy"] = {
        "installed": False,
        "version": None,
        "required": True,
        "description": "Zeiss X-radia library (from Xradia Software Suite)",
        "category": "xradia"
    }
    try:
        import XradiaPy
        deps["XradiaPy"]["installed"] = True
        deps["XradiaPy"]["version"] = getattr(XradiaPy, '__version__', 'installed')
    except ImportError:
        pass
    
    for name, desc, required in core + optional:
        version = get_package_version(name)
        deps[name] = {
            "installed": version is not None,
            "version": version,
            "required": required,
            "description": desc,
            "category": "python"
        }
    
    return deps

def get_python_info():
    """Get Python version and path info"""
    v = sys.version_info
    return {
        "version": "{0}.{1}.{2}".format(v.major, v.minor, v.micro),
        "major": v.major,
        "minor": v.minor,
        "path": sys.executable,
        "is_27": v.major == 2 and v.minor == 7,
        "is_3": v.major == 3,
    }

def find_xradia_paths():
    """Find Xradia installation paths"""
    paths = []
    
    if os.name == 'nt':
        candidates = [
            r"C:\Program Files\Xradia",
            r"C:\Program Files (x86)\Xradia",
            r"C:\Program Files\Zeiss\Xradia",
            r"C:\Program Files (x86)\Zeiss\Xradia",
        ]
    elif sys.platform == 'darwin':
        candidates = [
            "/Applications/Xradia",
            "/Applications/Zeiss/Xradia",
        ]
    else:
        candidates = [
            "/opt/xradia",
            "/opt/zeiss/xradia",
            "/usr/local/xradia",
        ]
    
    for path in candidates:
        if os.path.exists(path):
            paths.append(path)
    
    return paths

# ============================================================================
# DISPLAY FUNCTIONS
# ============================================================================

def print_banner():
    """Print a nice banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   ██╗  ██╗      ██████╗  █████╗ ██████╗ ██╗ █████╗           ║
    ║   ╚██╗██╔╝      ██╔══██╗██╔══██╗██╔══██╗██║██╔══██╗          ║
    ║    ╚███╔╝ █████╗██████╔╝███████║██║  ██║██║███████║          ║
    ║    ██╔██╗ ╚════╝██╔══██╗██╔══██║██║  ██║██║██╔══██║          ║
    ║   ██╔╝ ██╗      ██║  ██║██║  ██║██████╔╝██║██║  ██║          ║
    ║   ╚═╝  ╚═╝      ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═╝          ║
    ║                                                               ║
    ║            M E T A D A T A   E X T R A C T O R               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(c(banner, Colors.CYAN + Colors.BOLD))

def print_section(title):
    """Print a section header"""
    print("\n" + c("━" * 65, Colors.DIM))
    print(c("  " + title, Colors.BOLD + Colors.HEADER))
    print(c("━" * 65, Colors.DIM))

def print_status_table(deps, python_info):
    """Print a nice status table showing what's installed"""
    
    print_section("SYSTEM STATUS DASHBOARD")
    
    # Python status
    print("\n  " + c("Python Environment", Colors.BOLD))
    print("  " + "─" * 50)
    
    if python_info["is_27"]:
        status = icon_ok()
        note = c("Perfect for XradiaPy!", Colors.GREEN)
    elif python_info["is_3"]:
        status = icon_warning()
        note = c("XradiaPy needs Python 2.7", Colors.YELLOW)
    else:
        status = icon_missing()
        note = c("Unsupported version", Colors.RED)
    
    print("  {0} Python {1}  {2}".format(
        status,
        c(python_info["version"], Colors.CYAN + Colors.BOLD),
        note
    ))
    print("      " + c(python_info["path"], Colors.DIM))
    print("      " + c(platform.platform(), Colors.DIM))
    
    # XradiaPy status (special)
    print("\n  " + c("XradiaPy Library", Colors.BOLD))
    print("  " + "─" * 50)
    
    xradia = deps.get("XradiaPy", {})
    if xradia.get("installed"):
        print("  {0} XradiaPy {1}".format(
            icon_ok(),
            version_text(xradia.get("version"))
        ))
    else:
        print("  {0} XradiaPy".format(icon_missing()))
        print("      " + c("Required: Install Zeiss Xradia Software Suite", Colors.DIM))
    
    # Python packages
    print("\n  " + c("Python Packages", Colors.BOLD))
    print("  " + "─" * 50)
    
    # Required packages
    required_pkgs = [(k, v) for k, v in deps.items() 
                     if v.get("category") == "python" and v.get("required")]
    optional_pkgs = [(k, v) for k, v in deps.items() 
                     if v.get("category") == "python" and not v.get("required")]
    
    print("  " + c("Required:", Colors.DIM))
    for name, info in sorted(required_pkgs):
        if info["installed"]:
            print("    {0} {1} {2}  {3}".format(
                icon_ok(),
                c(name.ljust(15), Colors.CYAN),
                version_text(info["version"]),
                c(info["description"], Colors.DIM)
            ))
        else:
            print("    {0} {1}  {2}".format(
                icon_missing(),
                c(name.ljust(15), Colors.RED),
                c(info["description"], Colors.DIM)
            ))
    
    print("\n  " + c("Optional:", Colors.DIM))
    for name, info in sorted(optional_pkgs):
        if info["installed"]:
            print("    {0} {1} {2}  {3}".format(
                icon_ok(),
                c(name.ljust(15), Colors.CYAN),
                version_text(info["version"]),
                c(info["description"], Colors.DIM)
            ))
        else:
            print("    {0} {1}  {2}".format(
                icon_info(),
                c(name.ljust(15), Colors.DIM),
                c(info["description"] + " (not installed)", Colors.DIM)
            ))

def print_summary(deps, python_info):
    """Print a summary of what's ready and what's missing"""
    
    print_section("SUMMARY")
    
    # Count issues
    missing_required = [k for k, v in deps.items() 
                        if v.get("required") and not v.get("installed")]
    python_ok = python_info["is_27"]
    
    ready = len(missing_required) == 0 and python_ok
    
    if ready:
        print("\n  " + c("✓ ALL SYSTEMS GO!", Colors.GREEN + Colors.BOLD))
        print("    Your system is ready to extract metadata.")
        print("\n    " + c("Press Enter to start the metadata extractor...", Colors.CYAN))
    else:
        print("\n  " + c("! SETUP NEEDED", Colors.YELLOW + Colors.BOLD))
        
        if not python_ok:
            print("\n    " + icon_warning() + " Python 2.7 recommended for XradiaPy")
            print("      Current: Python {0}".format(python_info["version"]))
        
        if "XradiaPy" in missing_required:
            print("\n    " + icon_missing() + " XradiaPy not found")
            print("      → Install Zeiss Xradia Software Suite")
            xradia_paths = find_xradia_paths()
            if xradia_paths:
                print("      → Found Xradia at: " + c(xradia_paths[0], Colors.CYAN))
                print("      → Add to PYTHONPATH: {0}/Python".format(xradia_paths[0]))
        
        pip_missing = [k for k in missing_required 
                       if deps[k].get("category") == "python" and k != "XradiaPy"]
        if pip_missing:
            print("\n    " + icon_missing() + " Missing packages: " + 
                  c(", ".join(pip_missing), Colors.YELLOW))
            print("      → Run: " + c("pip install -r requirements.txt", Colors.CYAN))
    
    return ready

# ============================================================================
# INSTALLATION HELPERS
# ============================================================================

def install_pip_packages():
    """Install missing pip packages"""
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    
    if not os.path.exists(req_file):
        print(c("  [!] requirements.txt not found", Colors.RED))
        return False
    
    print("\n  Installing packages...")
    print(c("  ─" * 30, Colors.DIM))
    
    try:
        result = subprocess.call(
            [sys.executable, "-m", "pip", "install", "-r", req_file],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        return result == 0
    except Exception as e:
        print(c("  Error: {0}".format(str(e)), Colors.RED))
        return False

def get_input(prompt, valid=None, default=None):
    """Get user input"""
    if default:
        prompt = "{0} [{1}]: ".format(prompt, default)
    else:
        prompt = "{0}: ".format(prompt)
    
    try:
        response = raw_input(prompt).strip()
    except NameError:
        response = input(prompt).strip()
    
    if not response and default:
        return default
    
    if valid and response.lower() not in [v.lower() for v in valid]:
        return None
    
    return response

# ============================================================================
# MAIN MENU
# ============================================================================

def show_menu(ready):
    """Show interactive menu"""
    
    print_section("WHAT WOULD YOU LIKE TO DO?")
    print()
    
    if ready:
        print("    " + c("1", Colors.GREEN + Colors.BOLD) + " → " + 
              c("Start Metadata Extractor", Colors.BOLD))
    else:
        print("    " + c("1", Colors.DIM) + " → " + 
              c("Start Metadata Extractor", Colors.DIM) + " (setup needed)")
    
    print("    " + c("2", Colors.CYAN + Colors.BOLD) + " → " + 
          c("Install Missing Packages", Colors.BOLD) + " (pip install)")
    
    print("    " + c("3", Colors.BLUE + Colors.BOLD) + " → " + 
          c("Full System Check", Colors.BOLD) + " (detailed report)")
    
    print("    " + c("4", Colors.YELLOW + Colors.BOLD) + " → " + 
          c("Setup Wizard", Colors.BOLD) + " (guided setup)")
    
    print("    " + c("q", Colors.RED + Colors.BOLD) + " → " + 
          c("Quit", Colors.BOLD))
    
    print()
    return get_input("  Enter choice", valid=["1", "2", "3", "4", "q"], default="1" if ready else "2")

def run_extractor():
    """Run the metadata extractor"""
    main_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "new_enhanced_interactive",
        "main.py"
    )
    
    if os.path.exists(main_script):
        print("\n" + c("  Starting Metadata Extractor...", Colors.GREEN))
        print(c("  " + "═" * 50, Colors.DIM))
        print()
        
        # Run in same process for better integration
        exec(compile(open(main_script).read(), main_script, 'exec'))
    else:
        print(c("  [!] Main script not found: {0}".format(main_script), Colors.RED))

def run_system_check():
    """Run detailed system check"""
    check_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "system_check.py"
    )
    
    if os.path.exists(check_script):
        subprocess.call([sys.executable, check_script])
    else:
        print(c("  [!] system_check.py not found", Colors.RED))

def run_setup_wizard():
    """Run setup wizard"""
    wizard_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "setup_wizard.py"
    )
    
    if os.path.exists(wizard_script):
        subprocess.call([sys.executable, wizard_script])
    else:
        print(c("  [!] setup_wizard.py not found", Colors.RED))

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    while True:
        clear_screen()
        print_banner()
        
        # Detect everything
        python_info = get_python_info()
        deps = check_all_dependencies()
        
        # Show status
        print_status_table(deps, python_info)
        ready = print_summary(deps, python_info)
        
        # Show menu
        choice = show_menu(ready)
        
        if choice == "1":
            if ready:
                run_extractor()
                break
            else:
                print(c("\n  Please complete setup first.", Colors.YELLOW))
                get_input("\n  Press Enter to continue...")
        
        elif choice == "2":
            print_section("INSTALLING PACKAGES")
            if install_pip_packages():
                print(c("\n  ✓ Installation complete!", Colors.GREEN))
            else:
                print(c("\n  ! Some packages may have failed", Colors.YELLOW))
            get_input("\n  Press Enter to continue...")
        
        elif choice == "3":
            run_system_check()
            get_input("\n  Press Enter to continue...")
        
        elif choice == "4":
            run_setup_wizard()
            get_input("\n  Press Enter to continue...")
        
        elif choice and choice.lower() == "q":
            print(c("\n  Goodbye!\n", Colors.CYAN))
            break
        
        else:
            print(c("\n  Invalid choice. Please try again.", Colors.YELLOW))
            get_input("\n  Press Enter to continue...")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
