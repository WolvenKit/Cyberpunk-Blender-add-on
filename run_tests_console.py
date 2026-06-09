import sys
try:
    import blender_addon_tester as BAT
except Exception as e:
    print(e)
    sys.exit(1)

def main():
    try:
        exit_val = BAT.test_blender_addon(addon_path="./i_scene_cp77_gltf", blender_revision="4.2", config={"coverage": False})
    except Exception as e:
        print(e)
        exit_val = 1
    sys.exit(exit_val)

if __name__ == "__main__":
    main()
