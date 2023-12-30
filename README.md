# Download from [Releases](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/releases) >>>
Download the latest version from [Releases](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/releases), unless you specifically want the source code.

# Cyberpunk Blender Add-on

![blender add-on banner panam](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/assets/65016231/a0489b07-68af-4a90-b53e-1ad3ef271f4a)

The Cyberpunk IO Suite is part of the Cyberpunk 2077 modding toolchain, bridging the gap between [WolvenKit](https://wiki.redmodding.org/wolvenkit) and Blender.

You can find detailed documentation (and much else) on the [Cyberpunk 2077 modding wiki](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite).

# Features

![blender add-on yaiba exampe](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/assets/65016231/fffb9aab-c5f0-4f77-9a63-bdbee941708e)

## Import:
- [Meshes](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export): Import Cyberpunk 2077 meshes from Wovlenkit with a fully automated setup of the game's complex shaders — in just a few clicks.
  > Hint: The add-on doesn't support all Cyberpunk shaders yet, but we're working on it!

- [Characters](https://wiki.redmodding.org/wolvenkit/modding-community/exporting-to-blender) and [vehicles](https://wiki.redmodding.org/wolvenkit/modding-community/exporting-vehicles): Point the plugin at the Wolvenkit export and it will include all meshes and materials from your project, setting them up to match the in-game appearance you specified.

- Colliders (phys.json): Import colliders from Wolvenkit exported .phys files for easy visualization and editing

- Cyberpunk 2077 [animations](https://wiki.redmodding.org/wolvenkit/modding-community/exporting-to-blender/exporting-rigs-and-anims): Play animations directly on your exported models — either by [importing them from file](https://wiki.redmodding.org/wolvenkit/modding-community/exporting-to-blender/exporting-rigs-and-anims), or by using the bundled rig resources via the Cyberpunk Animations Panel

- [Level data (streamingsectors)](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-guides/world-editing): Import the map(.streamingsector) from Cyberpunk 2077 into Blender and change the world — literally.

## Export:

- [Mesh to .glb](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export): The plugin's export functions aims for maximum compatibility with Wolvenkit. Our exporter supports shapekeys and GarmentSupport and checks for common things that will cause the Wolvenkit export to fail. Where issues are found, the plugin provides simplified solutions to speed up your workflow.

- [Animations](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#animations-1): Export new and edited animations to GLB

- Collisions: Export modified collision shapes to .phys.json

## Tools and Shortcuts:
> Hint: You can find more detailed documentation on the [Cyberpunk 2077 Modding Wiki](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite)

### Animation Tools Panel
- shortcuts for playing, renaming and deleting existing animations
- add new actions and insert keyframes
- all from outside Blender's animations tab

### Mesh Tools Panel
- [Auto refit clothing meshes](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-akl-autofitter) to a variety of different modded and vanilla body shapes.  
*This functionality is based on research and work by AllKnowingLion*
- Simplified weight transfer shortcut with the best settings - no more hassle for you
- Mesh clean up panel can automatically assign ungrouped vertices to the nearest bone
- UV Checker: switch the currently active material for a coloured grid with numbers for easier UV editing - and back!

### Collision Tools and Generator
- Automatic generation of convex colliders matched perfectly to the shape of your mesh, the number of vertices to sample should be set to match the number set in the .phys file in order to ensure successful export.
- Generate box and capsule colliders with either user specified sizing or sized automatically to match the selected mesh
- Export edited collision bodies back to .phys ***currently requires a wolvenkit converted .phys.json file

### Material Exports
- [Hair profiles](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#hair-profiles-.hp): export custom hair profiles to `.hp.json` for easy import with Wolvenkit.  
*The .hp.json will be named after the material in blender and will be automatically deposited in the raw folder of the project that the hair mesh was exported from. The material name in blender must end with _cards to match the setup of imported vanilla hair profiles (_cards will not be part of the .hp.json export)*
- .mlsetup (experimental/WIP): After activating this feature in the plugin's preferences, write changes back to .mlsetup files. This feature is currently in development.
*For in-depth editing of .mlsetup files, you should use Neurolinked's fantastic [MlSetup builder}(https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/mlsetup-builder) software.*

---

# Requirements

1) **Blender** version 4.0 is supported
<br>**Blender** version 3.6 or higher is *highly recommended*
<br>**Blender** version 3.1 or higher is *required*
<br>https://www.blender.org/<br/>

2) **WolvenKit** version 8.11 or higher
<br>https://github.com/WolvenKit/WolvenKit<br/>

---

# Usage

## Installation

> **_NOTE:_** You can find step-by-step instructions on the [Cyberpunk 2077 Modding Wiki](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/installing-the-wolvenkit-blender-plugin).

1) Download the .ZIP file from the [*Releases*](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/releases) section

2) Install the downloaded zip from Blender's preferences (**Edit \ Preferences \ Add-ons \ Install...**).

3) Be sure the add-on is **enabled** (filter the list of installed add-ons and ).

3) When installed Cyberpunk options should be available under **File \ Import** and **File \ Export**

# Meshes and animations

### [Mesh Import](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export)

1) [Export a mesh with materials](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#export-from-wolvenkit) from WolvenKit

2) [Import it into Blender](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#importing-into-blender) from the menu (**File \ Import \ Cyberpunk GLTF**) by selecting the exported glTF/glb file. Within the import options, choose the same texture format as the WolvenKit export. (PNG is default)

### [Mesh Export as GLB](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#exporting-from-blender)

1) Follow the steps above to import and edit your meshes.
2) Select the mesh you want to export
3) Navigate within Blender to **File \ Export \ Export Selection to GLB for Cyberpunk
4) Select the desired file path and name
5) Export

The plugin will automatically apply the correct settings to ensure your mesh imports back into WolvenKit for use with your mod.

### [Animation import](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#export-from-wolvenkit-1)

1) [Export the animation from Wolvenkit](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#export-from-wolvenkit-1). The default settings are fine.

2) [Import it into Blender](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#importing-into-blender) from the menu (**File \ Import \ Cyberpunk GLTF**) and select the exported glTF/glb file. You can ignore materials.

### Animation export

1) Follow the [community guides](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-guides/animations/poses-animations-make-your-own) in order to import your anims to Blender and make the necessary edits
2) Select the armature that you want to export
3) Export it via menu (**File \ Export \ Export Selection to GLB for Cyberpunk)
4) Check the "Export as Photomode Pose" box
5) Select the desired file path and name
6) Export

The plugin will apply the correct settings to ensure your animation imports back into WolvenKit and is correct in game.

## Entity Import

1) [Export your .ent from Wolvenkit](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#export-from-wolvenkit-2) by running the correct script from Wolvenkit's script manager

2) [Import the `.ent.json`](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#importing-into-blender-2) from the menu (**File \ Import \ Cyberpunk Entity**).

> Hint: You can enter the appearance you want in the import options, this requires the appearanceName from the entity appearances info. Enter ALL for all appearances.

## Streaming Sector Import

1) [Export your .streamingsector](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#export-from-wolvenkit-3) by running the correct script from Wolvenkit's script manager.

2) [Import the `.cpmodproj`](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#importing-into-blender-3) from the menu (**File \ Import \ Cyberpunk StreamingSectors**). All sector file jsons found in the project raw folders will be imported.

## Streaming Sector Export
To export changes in streaming sectors, you have to run a Python script as of version 1.5.1. Detailed documentation can be found [on the wiki](https://wiki.redmodding.org/cyberpunk-2077-modding/for-mod-creators/modding-tools/wolvenkit-blender-io-suite/wkit-blender-plugin-import-export#exporting-from-blender-3).

---

# Contributing

Anybody is welcome contribute to the Cyberpunk Blender Add-on by opening a [pull request](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/pulls) with this repository. If you're interested in chatting or getting involved with the project please consider reaching out to us on our Discord, [Cyberpunk 2077 Modding Community.](https://discord.gg/Epkq79kd96)

---

# About the add-on

This add-on was originally created by [@HitmanHimself](https://github.com/HitmanHimself) as [CP77research](https://github.com/HitmanHimself/cp77research) as one of multiple projects to study and reverse-engineer elements of Cyberpunk 2077. It was originally based on [@Turk645](https://github.com/Turk645)'s research and implementation.  

As of 2023, it is now maintained by the RED Modding GitHub community to continue support and centralize development.
