#!/usr/bin/env python3
"""
Streamlit App Launcher

This script runs the Streamlit OCR Parsing Pipeline application.
Usage: python run_app.py
"""

import subprocess
import sys
import os


def main():
    """Launch the Streamlit application"""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the streamlit app
    app_path = os.path.join(script_dir, "streamlit_app.py")
    
    # Check if streamlit_app.py exists
    if not os.path.exists(app_path):
        print(f"Error: {app_path} not found!")
        sys.exit(1)
    
    print("🚀 Launching Streamlit OCR Parsing Pipeline...")
    print(f"📄 App location: {app_path}")
    print("-" * 60)
    
    try:
        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", app_path,
            "--server.port", "8501",
            "--server.headless", "true"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error running Streamlit app: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Streamlit app stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
