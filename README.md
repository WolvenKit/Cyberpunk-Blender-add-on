# Cyberpunk Blender Add-on

![image](https://user-images.githubusercontent.com/65016231/130711162-301926fa-c7a0-4e08-b7c7-414bfa558205.png)


The Cyberpunk Blender add-on is designed to fully automate the shader setup for Cyberpunk 2077 mesh files. The add-on integrates with files created by WolvenKit. To learn more about WolvenKit visit the [dedicated WolvenKit wiki.](https://wiki.redmodding.org/wolvenkit)

---

# Requirements

1) **Blender** version 3.1 or higher
<br>https://www.blender.org/<br/>

2) **WolvenKit** version 8.7 or higher
<br>https://github.com/WolvenKit/WolvenKit<br/>

---

# Usage

The latest version of the Cyberpunk add-on requires Blender 3.1 or higher. Not all Cyberpunk shaders are currently supported by the add-on. If you're interested in adding support for a new shader please consider reaching out to us on our Discord, [Cyberpunk 2077 Modding Community.](https://discord.gg/Epkq79kd96)

1) Download the .ZIP file from the *Releases* section

2) Install the Cyberpunk add-on for Blender by navigating within Blender to **Edit \ Preferences \ Add-ons \ Install...** and locating the downloaded .ZIP file. Be sure the add-on is enabled by marking the checkbox within the installed add-on list.

3) Export a mesh with materials using WolvenKit [Learn more](https://wiki.redmodding.org/wolvenkit/wolvenkit-app/editor/import-export/blender-integration)

4) Navigate within Blender to **File \ Import \ Cyberpunk GLTF** and select the exported gLTF/glb file. Within the import options choose the same texture format as the WolvenKit export. (PNG is default)

---

# About the add-on

This repository was originally created by [@HitmanHimself](https://github.com/HitmanHimself) as [CP77research](https://github.com/HitmanHimself/cp77research)
 to help study and reverse engineer elements of Cyberpunk 2077. HitmanHimself's cp77research contained various modding-related projects and documentation, including the Cyberpunk add-on for Blender. The add-on HitmanHimself created was based on reserach and initial python implementation by [@Turk645](https://github.com/Turk645). The add-on is now maintained here by the RED Modding GitHub organization to continue support and centralize development.
