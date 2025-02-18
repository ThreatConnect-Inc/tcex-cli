# Release Notes

## 1.0.4

-   APP-4563 - [SPEC-TOOL] Added Minimum Server Version to the README.md
-   APP-4661 - [MIGRATE] Added new patterns to migrate for TcEx 2 to TcEx 4
-   APP-4662 - [SPEC-TOOL] Fixed issue for Boolean type in spec-tool
-   APP-4663 - [SPEC-TOOL] Updated install.json generation to support service field for service Apps
-   APP-4689 - [DEPS] Added support for "uv"
-   APP-4690 - [SPEC-TOOL] Updated app_inputs.py gen to support Annotated typing
-   APP-4720 - [PACKAGE] Added new patterns and updated filtering logic
-   APP-4721 - [RUN] Removed keyboard shortcuts
-   APP-4722 - [RUN] Added fake Redis server (only starts if Redis is not running)

## 1.0.3

-   APP-4397 - [PACKAGE] Updated feature generation logic to make runtimeVariable on be added for Playbook Apps
-   APP-4439 - [PACKAGE] Changed appId creation logic to used UUID4 instead of UUID5 for App Builder
-   APP-4440 - [MIGRATE] Added new command to assist in migration of TcEx 3 Apps to TcEx 4

## 1.0.2

-   APP-4171 - [DEPS] Updated deps command to add a link to lib_latest for current Python version for App Builder
-   APP-4172 - [CLI] Minor enhancement to output of multiple commands
-   APP-4773 - [SUBMODULE] Minor update to config submodule

## 1.0.1

-   APP-3915 - [CONFIG] Added validation to ensure displayPath is always in the install.json for API Services
-   APP-4060 - [CLI] Updated proxy inputs to use environment variables
-   APP-4077 - [SPEC-TOOL] Updated spec-tool to create an example app_input.py file and to display a mismatch report
-   APP-4112 - [CONFIG] Updated config submodule (tcex.json model) to support legacy App Builder Apps
-   APP-4113 - [CONFIG] Updated App Spec model to normalize App features


## 1.0.0

-   APP-3926 - Split CLI module of TcEx into tcex-cli project
-   APP-3912 - [CLI] Updated `tcex` command to use "project.scripts" setting in pyproject.toml
-   APP-3913 - [DEPS] Updated `deps` command to build **"deps"** or **"lib_"** depending on TcEx version
-   APP-3819 - [LIST] Updated the `list` to choose the appropriate template branch depending on TcEx version
-   APP-3820 - [DEPS] Updated the `deps` to choose the appropriate template branch depending on TcEx version
-   APP-4053 - [CLI] Updated CLI tools to work with changes in App Builder released in ThreatConnect version 7.2
-   APP-4059 - [CLI] Added proxy support to commands where applicable
