#!/usr/bin/env python
"""Zabbix disovered devices parser"""

import re
import sys
import logging
from logging.handlers import RotatingFileHandler
import configparser
# Non-standard import
import requests
import yaml
import urllib3
from zapi import ImprovedZabbixAPI


def log_config(level):
    """Logging configuration"""
    mylogger = logging.getLogger('pyzabbix')
    mylogger.setLevel(level)
    handler_console = logging.StreamHandler(stream=sys.stdout)
    #handler_file = TimedRotatingFileHandler('logs/discoparser.log', when='midnight', backupCount=7)
    handler_file = RotatingFileHandler('logs/discoparser.log', maxBytes=1024*1024, backupCount=5)
    handler_console.setFormatter(logging.Formatter(fmt='%(message)s'))
    handler_file.setFormatter(logging.Formatter(fmt='%(asctime)s: [%(levelname)s] %(message)s'))
    mylogger.addHandler(handler_console)
    mylogger.addHandler(handler_file)
    return mylogger


def refresh_host(zabbix_api, host_object):
    """Refreshing host data"""
    host_object = zabbix_api.host.get(output=['host','status'], hostids=host_object['hostid'],
            selectGroups='groupid', selectParentTemplates='templateid', selectTags='extend')[0]
    return host_object


def get_values(zabbix_api, host_object, keys_list):
    """Getting and checking items values"""
    if isinstance(keys_list, str):
        keys_list = [keys_list]
    values = {k:'' for k in keys_list}
    empty_values = 0
    for key in keys_list:
        values[key] = zabbix_api.item.get(hostids=host_object['hostid'],
            output=['hostid', 'name', 'lastvalue'], filter={'key_': key})[0]
        if not values[key]['lastvalue']:
            logger.info("Empty '%s' last value for %s", key, host_object['host'])
            zabbix_api.item_update(host_object, values[key])
            empty_values += 1
    if empty_values > 0:
        return False
    return values


def apply_rule(zabbix_api, host_object, item_value, ruleset, mode='save'):
    """Applying rule set for host"""
    if re.search(ruleset['mask'], item_value):
        action = 'set'
    else:
        if mode == 'save':
            return False
        action = 'delete'
        host_object = refresh_host(zabbix_api, host_object)
    if 'groups' in ruleset:
        result = zabbix_api.host_groups(host_object, ruleset['groups'], action=action)
    if 'templates' in ruleset:
        result = zabbix_api.host_templates(host_object, ruleset['templates'], action=action)
    if 'tags' in ruleset:
        if host_object['modified']:
            host_object = refresh_host(zabbix_api, host_object)
        result = zabbix_api.host_tags(host_object, ruleset['tags'], action=action)
    if result:
        # Returning host modified flag
        return 1
    return True


def count_check(count, lastcount = 0):
    """Checks last run hosts count and save current"""
    try:
        with open('logs/hosts.num') as file:
            lastcount = int(file.read())
    except (OSError, ValueError):
        pass
    if count > lastcount and lastcount != 0:
        logger.info('Found %s new host(s) from last run', count - lastcount)
    with open('logs/hosts.num', 'w') as file:
        file.write(str(count))


if __name__ == '__main__':
    # Configuration section
    config = configparser.ConfigParser()
    config.read('config/discoparser.cfg')
    api = config['api']
    parser = config['parser']
    # Setting logging parameters
    logger = log_config(parser['log'])
    logger.info('Starting discovered devices parser')
    # Loading rules YAML
    with open('config/masks.yaml', encoding='utf-8') as yamlfile:
        masks = yaml.safe_load(yamlfile)
    # Setting up Zabbix API connection
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.auth = ('http user', 'http password')
    session.verify = False
    zapi = ImprovedZabbixAPI(api['url'], session=session, safe_mode=config['parser'].getboolean('safe_mode'))

    # Connecting to Zabbix API
    zapi.login(api['user'], api['password'])
    if zapi.safe_mode:
        logger.warning("Safe mode is ON: rules will NOT be applied")

    # Getting hosts from discovery group
    discogroup = zapi.hostgroup.get(groupids=parser['group'], output=['name'])[0]
    hosts = zapi.host.get(output=['host','status'], groupids=discogroup['groupid'], sortfield='host',
        selectGroups='groupid', selectParentTemplates='templateid', selectTags='extend')
    hosts_count = len(hosts)
    logger.info("Loaded %s hosts from %s",hosts_count, discogroup['name'])
    count_check(hosts_count)

    for host in hosts:
        if host['status'] ==  '1':
            logger.info("Skipping deactivated host %s", host['host'])
            continue

        # Checking generic template
        if not any(t['templateid'] == parser['template'] for t in host['parentTemplates']):
            logger.warning("Generic template is not set for %s", host['host'])
            zapi.host_templates(host, parser['template'])
            continue

        # Getting items values
        hostname = parser['hostname_key']
        device = parser['device_key']
        items = get_values(zapi, host, [hostname, device])
        if not items:
            continue

        # Checking zabbix host name
        if host['host'] != items[hostname]['lastvalue']:
            logger.warning("Hostname '%s' changed to '%s'", host['host'], items[hostname]['lastvalue'])
            zapi.host_name(host, items[hostname]['lastvalue'])

        # Applying the rules
        host['modified'] = False
        for rule in masks:
            logger.debug("Applying rule %s for %s", rule['description'], host['host'])
            # Setting host parameters by hostname mask
            rule_result = apply_rule(zapi, host, items[hostname]['lastvalue'], rule['hostname'])
            if not rule_result:
                continue
            elif rule_result == 1:
                host['modified'] = True
            # Setting host parameters by device mask
            if not 'devices' in rule:
                continue
            for device_rule in rule['devices']:
                rule_result = apply_rule(zapi, host, items[device]['lastvalue'], device_rule)
                if rule_result == 1:
                    host['modified'] = True

    # Logout from Zabbix
    zapi.user.logout()
    logger.info('Finished parsing process\n')
