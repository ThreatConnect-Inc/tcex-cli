# Release Notes

## 1.0.6

-   APP-4863 - [Package] Added a check to ensure the “package.app_name” value in “tcex.json” doesn't contain spaces
-   APP-4916 - [Migrate] Updated to support more replacement patterns
-   APP-4917 - [Run] Updated “app_inputs.json” file to support environment variables
-   APP-4918 - [Run] Updated output to exclude staged variables
-   APP-4919 - [App-Inputs] Added a new command to generate “app_inputs.json” from “install.json” params
-   APP-4920 - [Run] - Updated run command to support system apps
-   APP-5036 - [Message-Broker] Updated message broker connection to not set tls_version
-   APP-5055 - [Message-Broker] Updated Paho MQTT library and message broker reconnect logic

## 1.0.5

-   APP-4732 - [Package] Fixed dependency issue with python-dotenv
-   APP-4733 - [Package] Migrated to "uv" for package management
-   APP-4734 - [Package] Switched linters to "ruff" (including linting fixes)

## 1.0.4

-   APP-4563 - [Spec-Tool] Added Minimum Server Version to the README.md
-   APP-4661 - [Migrate] Added new patterns to migrate for TcEx 2 to TcEx 4
-   APP-4662 - [Spec-Tool] Fixed issue for Boolean type in spec-tool
-   APP-4663 - [Spec-Tool] Updated install.json generation to support service field for service Apps
-   APP-4689 - [Deps] Added support for "uv"
-   APP-4690 - [Spec-Tool] Updated app_inputs.py gen to support Annotated typing
-   APP-4720 - [Package] Added new patterns and updated filtering logic
-   APP-4721 - [Run] Removed keyboard shortcuts
-   APP-4722 - [Run] Added fake Redis server (only starts if Redis is not running)

## 1.0.3

-   APP-4397 - [Package] Updated feature generation logic to make runtimeVariable on be added for Playbook Apps
-   APP-4439 - [Package] Changed appId creation logic to used UUID4 instead of UUID5 for App Builder
-   APP-4440 - [Migrate] Added new command to assist in migration of TcEx 3 Apps to TcEx 4

## 1.0.2

-   APP-4171 - [Deps] Updated deps command to add a link to lib_latest for current Python version for App Builder
-   APP-4172 - [Cli] Minor enhancement to output of multiple commands
-   APP-4773 - [Submodule] Minor update to config submodule

## 1.0.1

-   APP-3915 - [Config] Added validation to ensure displayPath is always in the install.json for API Services
-   APP-4060 - [Cli] Updated proxy inputs to use environment variables
-   APP-4077 - [Spec-Tool] Updated spec-tool to create an example app_input.py file and to display a mismatch report
-   APP-4112 - [Config] Updated config submodule (tcex.json model) to support legacy App Builder Apps
-   APP-4113 - [Config] Updated App Spec model to normalize App features


## 1.0.0

-   APP-3926 - Split CLI module of TcEx into tcex-cli project
-   APP-3912 - [Cli] Updated `tcex` command to use "project.scripts" setting in pyproject.toml
-   APP-3913 - [Deps] Updated `deps` command to build **"deps"** or **"lib_"** depending on TcEx version
-   APP-3819 - [List] Updated the `list` to choose the appropriate template branch depending on TcEx version
-   APP-3820 - [Deps] Updated the `deps` to choose the appropriate template branch depending on TcEx version
-   APP-4053 - [Cli] Updated CLI tools to work with changes in App Builder released in ThreatConnect version 7.2
-   APP-4059 - [Cli] Added proxy support to commands where applicable
