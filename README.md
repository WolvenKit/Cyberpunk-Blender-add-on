# Cyberpunk Blender Add-on

![blender add-on banner panam](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/assets/65016231/a0489b07-68af-4a90-b53e-1ad3ef271f4a)

The Cyberpunk IO Suite integrates with files created by WolvenKit to streamline the import/export and modifcation of assets from Cyberpunm 2077. 

To learn more about modding Cyberpunk 2077 visit [the Cyberpunk Modding wiki.](https://wiki.redmodding.org/cyberpunk-2077-modding)


To learn more about WolvenKit visit the [dedicated WolvenKit wiki.](https://wiki.redmodding.org/wolvenkit)

# Features

![blender add-on yaiba exampe](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/assets/65016231/fffb9aab-c5f0-4f77-9a63-bdbee941708e)

## Import functions:

- Import Cyberpunk 2077 models with materials for fully automated setup of the games complex shaders in just a few clicks

- Import characters and vehicles from Wolvenkit exported .ent.json files. The plugin will automatically import the meshes and materials from your project and correctly distribute them to match the specified in game appearance

- Import colliders from Wolvenkit exported .phys files for easy visualization and editing

- Import Cyberpunk 2077 animations to play on your models exported with rigs, or take advantage of the bundled rig resources conveniently available at the press of a button in the Cyberpunk Animations Panel

- Import Cyberpunk 2077 level data (streaming sectors)

## Export Functions:

- Export meshes to glb with optimized export options to ensure compatibility with Wolvenkit. Our exporter supports shapekey and garmentsupport attribute export and checks for common editing issues which cause Wolvenkit import to fail. Where issues are found, the plugin provides automatic or simplified solutions to speed up your workflow. 

- Export modified collision shapes to .phys.json

- Export new and edited animations to GLB

## Tools and Shortcuts:

- Animation Tools Panel
    - shortcuts for playing, renaming and deleting existing animations
    - add new actions and insert keyframes 
    - all from outside Blender's animations tab

- Mesh Tools Panel
    - Auto refit clothing meshes to a variety of different modded and vanilla body shapes. this functionality is based on research and work by AllKnowingLion
    - Simplified weight transfer shortcut applies the usual best settings and makes this process much easier to understand 
    - Mesh clean up panel includes automatically assigning ungrouped vertices to their nearest group
    - UV Checker: toggle a coloured, labelled grid as the active material on your mesh to make texturing and troubleshooting easier. If the currently selected mesh is currently using the UV checker, the button will change to easily allow you to restore the original material and remove the UV checker from your meshes material slots

- Collision Tools and Generator
    - Automatic generation of convex colliders matched perfectly to the shape of your mesh, the number of vertices to sample should be set to match the number set in the .phys file in order to ensure successful export.
    - Generate box and capsule colliders with either user specified sizing or sized automatically to match the selected mesh
    - Export edited collision bodies back to .phys ***currently requires a wolvenkit converted .phys.json file

- Material Exports
    - export custom and edited hair profiles to .hp.json which can be imported to wolvenkit. supports both edited vanilla files and totally custom setups based on the same node structure. the .hp.json will be named after the material in blender and will be automatically deposited in the raw folder of the project that the hair mesh was exported from. The material name in blender must end with _cards to match the setup of imported vanilla hair profiles (_cards will not be part of the .hp.json export)
    - export some changes to .mlsetup files. This is an experimental feature which must be toggled on in the plugins preferences. Currently only some changes are supported. For indepth editing of .mlsetup files, you should use the fantastic MlSetup builder software by Neurolinked

---

# Requirements

1) **Blender** version 3.6 or higher is *highly recommended*
<br>**Blender** version 3.1 or higher is *required*
<br>https://www.blender.org/<br/>

2) **WolvenKit** version 8.9.0 or higher
<br>https://github.com/WolvenKit/WolvenKit<br/>

---

# Usage

> Not all Cyberpunk shaders are currently supported by the add-on.

## Installation

1) Download the .ZIP file from the [*Releases*](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/releases) section

2) Install the Cyberpunk add-on for Blender by navigating within Blender to **Edit \ Preferences \ Add-ons \ Install...** and locating the downloaded .ZIP file. Be sure the add-on is enabled by marking the checkbox within the installed add-on list.

3) When installed Cyberpunk options should be available under **File \ Import** and **File \ Export**

## Mesh Import

1) Export a mesh with materials using WolvenKit [Learn more](https://wiki.redmodding.org/wolvenkit/wolvenkit-app/usage/blender-integration)

2) Navigate within Blender to **File \ Import \ Cyberpunk GLTF** and select the exported glTF/glb file. Within the import options choose the same texture format as the WolvenKit export. (PNG is default)

## Entity Import

1) Convert the ent file to json and export all the meshes used using WolvenKit, a wscript to automate this is available in wolvenkit under Tools -> Script Manager.

2) Navigate within Blender to **File \ Import \ Cyberpunk Entity** and select the exported json file. You can enter the appearance you want in the import options, this requires the appearanceName from the entity appearances info. Enter ALL for all appearances.

## Streaming Sector Import

1) Convert the streaming sectors you want to import from WolvenKit as json, and export all the meshes used using WolvenKit, a wscript to automate this is available on Discord in the wolvenkit-scripts channel.

2) Navigate within Blender to **File \ Import \ Cyberpunk StreamingSectors** and select the wkit project file for the project they were added to. All sector file jsons found in the project raw folders will be imported.

## Mesh Export as GLB

1) Follow the steps above to import and edit your meshes.
2) Select the mesh you want to export
3) Navigate within Blender to **File \ Export \ Export Selection to GLB for Cyberpunk
4) Select the desired file path and name
5) Export

The plugin will automatically apply the correct settings to ensure your mesh imports back into WolvenKit for use with your mod.

## Export Animations For Photomode
**Should work for all types of animation 

1) Follow the community guides in order to import your anims to Blender and make the necessary edits
2) Select the armature which contains the animations you'd like to export
3) Navigate within Blender to **File \ Export \ Export Selection to GLB for Cyberpunk
4) Check the "Export as Photomode Pose" box
5) Select the desired file path and name
6) Export

The plugin will apply the correct settings to ensure your animation imports back into WolvenKit and is correct in game.

---

# Contributing

Anybody is welcome contribute to the Cyberpunk Blender Add-on by opening a Pull Request with this repository. If you're interested in chatting or getting involved with the project please consider reaching out to us on our Discord, [Cyberpunk 2077 Modding Community.](https://discord.gg/Epkq79kd96)

---

# About the add-on

This repository was originally created by [@HitmanHimself](https://github.com/HitmanHimself) as [CP77research](https://github.com/HitmanHimself/cp77research)
 to help study and reverse engineer elements of Cyberpunk 2077. HitmanHimself's cp77research contained various modding-related projects and documentation, including the Cyberpunk add-on for Blender. The add-on HitmanHimself created was based on research and initial python implementation by [@Turk645](https://github.com/Turk645). The add-on is now maintained here by the RED Modding GitHub organization to continue support and centralize development.
