# Cyberpunk Blender Add-on

![image](https://user-images.githubusercontent.com/65016231/130711162-301926fa-c7a0-4e08-b7c7-414bfa558205.png)


The Cyberpunk Blender add-on is designed to fully automate the shader setup for Cyberpunk 2077 mesh files. The add-on integrates with files created by WolvenKit. To learn more about WolvenKit visit the [dedicated WolvenKit wiki.](https://wiki.redmodding.org/wolvenkit)

---

# Requirements

1) **Blender** version 3.1 or higher
<br>https://www.blender.org/<br/>

2) **WolvenKit** version 8.8.1 or higher
<br>https://github.com/WolvenKit/WolvenKit<br/>

---

# Usage

The latest version of the Cyberpunk add-on requires Blender 3.1 or higher. Not all Cyberpunk shaders are currently supported by the add-on. If you're interested in adding support for a new shader please consider reaching out to us on our Discord, [Cyberpunk 2077 Modding Community.](https://discord.gg/Epkq79kd96)

## Installation

1) Download the .ZIP file from the [*Releases*](https://github.com/WolvenKit/Cyberpunk-Blender-add-on/releases) section

2) Install the Cyberpunk add-on for Blender by navigating within Blender to **Edit \ Preferences \ Add-ons \ Install...** and locating the downloaded .ZIP file. Be sure the add-on is enabled by marking the checkbox within the installed add-on list.

3) When installed Cyberpunk options should be available under **File \ Import** and **File \ Export**

## Mesh Import

1) Export a mesh with materials using WolvenKit [Learn more](https://wiki.redmodding.org/wolvenkit/wolvenkit-app/usage/blender-integration)

2) Navigate within Blender to **File \ Import \ Cyberpunk GLTF** and select the exported gLTF/glb file. Within the import options choose the same texture format as the WolvenKit export. (PNG is default)

## Entity Import

1) Convert the ent file to json and export all the meshes used using WolvenKit, a wscript to automate this is available on Discord in the wolvenkit-scripts channel.

2) Navigate within Blender to **File \ Import \ Cyberpunk Entity** and select the exported json file. You can enter the appearance you want in the import options, this requires the appearanceName from the entity appearances info. Enter ALL for all appearances.

## Streaming Sector Import

1) Convert the streaming sectors you want to import from WolvenKit as json, and export all the meshes used using WolvenKit, a wscript to automate this is available on Discord in the wolvenkit-scripts channel.

2) Navigate within Blender to **File \ Import \ Cyberpunk StreamingSectors** and select the wkit project file for the project they were added to. All sector file jsons found in the project raw folders will be imported.

## Meshes Export

1) Follow the steps above to import and edit your meshes.
2) Select the mesh you want to export
3) Navigate within Blender to **File \ Export \ Export Selection to GLB for Cyberpunk
4) Select the desired file path and name
5) Export

The plugin will automatically apply the correct settings to ensure your mesh imports back into Wolvenkit for use with your mod.

## Export Animations For Photomode Poses
**Should work for all types of animation 
1) Follow the community guides in order to import your anims to Blender and make the necessary edits
2) Select the armature which contains the animations you'd like to export
3) Navigate within Blender to **File \ Export \ Export Selection to GLB for Cyberpunk
4) Check the "Export as Photomode Pose" box
5) Select the desired file path and name
6) Export

The plugin will apply the correct settings to ensure your animation imports back into Wolvenkit and is correct in game.

---

# About the add-on

This repository was originally created by [@HitmanHimself](https://github.com/HitmanHimself) as [CP77research](https://github.com/HitmanHimself/cp77research)
 to help study and reverse engineer elements of Cyberpunk 2077. HitmanHimself's cp77research contained various modding-related projects and documentation, including the Cyberpunk add-on for Blender. The add-on HitmanHimself created was based on research and initial python implementation by [@Turk645](https://github.com/Turk645). The add-on is now maintained here by the RED Modding GitHub organization to continue support and centralize development.
