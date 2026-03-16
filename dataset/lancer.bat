@echo off
echo Generation du dataset Hackathon 2026...
echo Train: 500  Test: 100  Degradation: activee
echo.
"C:\Users\chaou\AppData\Local\Python\pythoncore-3.14-64\python.exe" generate_dataset.py --n_train 500 --n_test 100 --degrade
echo.
pause
