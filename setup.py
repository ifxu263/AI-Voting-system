import subprocess
import sys

def install_requirements():
    print("Installing all project requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("\nAll dependencies installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\nInstallation failed: {e}")

if __name__ == "__main__":
    install_requirements()