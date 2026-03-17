python -m pip install pyinstaller
python -m PyInstaller --onefile --noconsole -n nts-app --distpath release --workpath build --specpath build main.py
