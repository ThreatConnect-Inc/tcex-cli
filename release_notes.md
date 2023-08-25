# Release Notes

### 1.0.1

-   APP-3915 - [CONFIG] Added validation to ensure displayPath is always in the install.json for API Services
-   APP-4060 - [CLI] Updated proxy inputs to use environment variables
-   APP-4077 - [SPEC-TOOL] Updated spec-tool to create an example app_input.py file and to display a mismatch report
-   APP-4112 - [CONFIG] Updated config submodule (tcex.json model) to support legacy App Builder Apps
-   APP-4113 - [CONFIG] Updated App Spec model to normalize App features


### 1.0.0

-   APP-3926 - Split CLI module of TcEx into tcex-cli project
-   APP-3912 - [CLI] Updated `tcex` command to use "project.scripts" setting in pyproject.toml
-   APP-3913 - [DEPS] Updated `deps` command to build **"deps"** or **"lib_"** depending on TcEx version
-   APP-3819 - [LIST] Updated the `list` to choose the appropriate template branch depending on TcEx version
-   APP-3820 - [DEPS] Updated the `deps` to choose the appropriate template branch depending on TcEx version
-   APP-4053 - [CLI] Updated CLI tools to work with changes in App Builder released in ThreatConnect version 7.2
-   APP-4059 - [CLI] Added proxy support to commands where applicable
