English | [Русский](./README-ru.md)
# discoparser
Zabbix discovered devices parser

This script is intended for grouping, assigning templates and setting tags depending on the host name and device vendor. The SNMP sysName and sysDescr values are used to define these settings.

## Installation
The script requires Python version 3.6 or higher, as well as packages: pyzabbix, requests, yaml, urllib3, certifi, chardet, idna, semantic_version.

## Description

### Operating procedure
- When launched, the script gets all objects from the selected hosts group (by default '*Discovered hosts*').
- All active hosts are checked for the presence of the **standard template**. If the template is not installed, then the script installs it. Further actions with the host in this case are not performed.

*Standard template is required in order to get the current sysName and sysDescr values. The template is set for all discovered devices in the Zabbix* discovery actions.
- After successfully validating the template, the script gets the last values of the items containing sysName and sysDescr. If the value is not received, then an immediate passive check is started on the data element. In the absence of any of these values, the transition to the next network node is performed.

*In the standard template, the polling interval must be set to no more than 24 hours and throttling must be disabled, otherwise the latest values may not be received (with Zabbix default settings)*.
- The value of sysName is compared with the hostname in Zabbix. If the name is different, then the script attempts to change the current host name.
- The host is checked against each rule from the **rule set**.
    - Values are checked against masks using regular expressions.
    - If the host name matches the mask from the hostname section, then the appropriate groups, templates, or tags are applied to the device.
    - If the rule contains the devices section, then the sysDescr value is checked against the masks from this section. If there is a match, additional settings are applied depending on the type of device.
    - Rules by device type are only applied within a single rule by device name. For each mask by name, a separate section of rules on device masks is used.

All actions are recorded in **logs/discoparser.log**. The maximum size of the log file is 1MB, rotation with the preservation of the last 5 copies.

### Settings
The configuration file **config/discoparser.cfg** contains the main parameters of the script:
```ini
[api]
# Zabbix API credentials
user = api_user
# User password
password = api_password
# Zabbix server address
url=https://192.168.0.1

[parser]
# The group ID of discovered devices
# Default 5 (Discovered hosts)
group=5
# Standard template ID
template = 11
# Item key containing sysName
hostname_key = host.name
# Item key containing sysDescr
device_key = host.descr
# Logging level
log = INFO
# Safe mode
# (if enabled, the script does not make any changes)
safe_mode=on

```

The ruleset file **config/masks.yaml** contains condition masks and their corresponding actions:
```yaml
- description: Test Device    # The rule description
  hostname:                   # Set of hostname rules
    mask: '[Tt][Ee][Ss][Tt]'  # Host name mask (sysName) in regex format
    groups: [11]              # Groups IDs assigned by hostname (optional)
    tags:                     # Tags assigned by hostname (optional)
      - tag: Device           # Tag name assigned by hostname
        value: TEST           # Tag value assigned by hostname (optional)
    templates: [11]           # Templates IDs assigned by hostname (optional)
  devices:                    # Set of rules for device types (optional)
    - mask: '[Cc]isco'        # First device type mask (sysDescr) in regex format
      templates: [22]         # Templates IDs to assign to first mask (optional)
      groups: [22]            # Group IDs to assign to the first mask (optional)
    - mask: '[Hh]uawei'       # Second device type mask (sysDescr) in regex format (optional)
      templates: [33]         # Templates IDs to assign to second mask (optional)
      tags:                   # Tags to assign to the second mask (optional)
        - tag: Huawei         # Tag name assigned by device type
```
