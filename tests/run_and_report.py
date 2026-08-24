# -*- coding: utf-8 -*-
import sys, io, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
r = subprocess.run([sys.executable, "tests/acceptance_test.py"],
                   cwd=r"c:\Users\阳光\Desktop\OPCorder\opc-diet-advisor",
                   capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stdout.write("RC=" + str(r.returncode) + "\n")
