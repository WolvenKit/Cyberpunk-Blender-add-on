# This is not how pytest would operate, but having all test functions imported in one place allows them to be executed inside of blender more easily.
# The blender_addon_tester > pyest toolchain does not use this
from tests.test_import import test_import_mesh, test_cube
ALL_TEST_FUNCS = [test_import_mesh, test_cube]

def run_all_tests():
    for test_func in ALL_TEST_FUNCS:
        test_func()

