apt-get update && apt-get install -y libgl1 libxi6 libxkbcommon-x11-0   
python -m pip install pytest blender_addon_tester-0.10.2-py3-none-any.whl
python run_tests_console.py
