#!/usr/bin/python3
"""Zabbix improved API module"""

import logging
from pyzabbix import ZabbixAPI, ZabbixAPIException


logger = logging.getLogger('pyzabbix')


class ImprovedZabbixAPI(ZabbixAPI):
    """Imroved Zabbix API host methods"""

    def __init__(self, *args, safe_mode=False, **kwargs):
        self.safe_mode = safe_mode
        super().__init__(*args,**kwargs)

    def host_tags(self, host_object, tags, action='set'):
        """Updating host tags"""
        new_tags = []
        del_tags = []
        for tag in tags:
            if not 'value' in tag:
                tag['value'] = ''
            if action == 'set':
                # Adding to update only those tags that are not yet set
                if not any(t == tag for t in host_object['tags']):
                    new_tags.append(tag)
            elif action == 'delete':
                # Adding to update only those tags that are not deleting
                for hosttag in host_object['tags']:
                    if hosttag != tag:
                        new_tags.append(hosttag)
                    else:
                        del_tags.append(tag)
        if action == 'set':
            if not new_tags:
                return False
            # Concatinating with host tags
            update_tags = new_tags + host_object['tags']
            logger.info("Set tags '%s' for %s", new_tags, host_object['host'])
        elif action == 'delete':
            if new_tags == host_object['tags']:
                return False
            update_tags = new_tags
            logger.info("Delete tags '%s' for %s", del_tags, host_object['host'])
        if not self.safe_mode:
            try:
                self.host.update(hostid=host_object['hostid'], tags=update_tags)
            except ZabbixAPIException as err:
                logger.error("Unable to update tags for %s: %s", host_object['host'], err)
                return False
        return True

    def host_templates(self, host_object, templateids, action='set'):
        """Updating templates for host"""
        update_templates_obj = []
        update_templates_arr = []
        if isinstance(templateids, (int,str)):
            templateids = [templateids]
        # Creating array of templates objects and ids for API
        for templateid in templateids:
            if action == 'set':
                # When adding, include in the request only templates not found on the host
                if not any(t['templateid'] == str(templateid) for t in host_object['parentTemplates']):
                    update_templates_obj.append({'templateid': templateid})
                    update_templates_arr.append(templateid)
            elif action == 'delete':
                # When deleting, include in the request only templates found on the host
                if any(t['templateid'] == str(templateid) for t in host_object['parentTemplates']):
                    update_templates_arr.append(templateid)
        if not update_templates_arr:
            return False
        try:
            templates = self.template.get(templateids=update_templates_arr, output=['name'])
            if action == 'set' and not self.safe_mode:
                self.template.massadd(templates=update_templates_obj, hosts=[{'hostid': host_object['hostid']}])
            elif action == 'delete' and not self.safe_mode:
                self.template.massremove(templateids=update_templates_arr, hostids=host_object['hostid'])
        except ZabbixAPIException as err:
            logger.error("Unable to %s templates '%s' for %s: %s", action, templates, host_object['host'], err)
            return False
        logger.info("%s templates '%s' for %s", action.title(), templates, host_object['host'])
        return True

    def host_groups(self, host_object, groupids, action='set'):
        """Updating hostgroups for host"""
        update_groups_obj = []
        update_groups_arr = []
        if isinstance(groupids, (int,str)):
            groupids = [groupids]
        # Creating array of hostgroups objects and ids for API
        for groupid in groupids:
            if action == 'set':
                # When adding, include in the request only groups not found on the host
                if not any(g['groupid'] == str(groupid) for g in host_object['groups']):
                    update_groups_obj.append({'groupid': groupid})
                    update_groups_arr.append(groupid)
            elif action == 'delete':
                # When deleting, include in the request only groups found on the host
                if any(g['groupid'] == str(groupid) for g in host_object['groups']):
                    update_groups_arr.append(groupid)
        if not update_groups_arr:
            return False
        try:
            hostgroups = self.hostgroup.get(groupids=update_groups_arr, output=['name'])
            if action == 'set' and not self.safe_mode:
                self.hostgroup.massadd(groups=update_groups_obj, hosts=[{'hostid': host_object['hostid']}])
            elif action == 'delete' and not self.safe_mode:
                self.hostgroup.massremove(groupids=update_groups_arr, hostids=host_object['hostid'])
        except ZabbixAPIException as err:
            logger.error("Unable to %s hostgroups '%s' for %s: %s", action, hostgroups, host_object['host'], err)
            return False
        logger.info("%s hostgroups '%s' for %s", action.title(), hostgroups, host_object['host'])
        return True

    def host_name(self, host_object, name):
        """Changing host name"""
        if not self.safe_mode:
            try:
                self.host.update(hostid=host_object['hostid'], host=name)
            except ZabbixAPIException as err:
                logger.error("Unable to change hostname '%s' to '%s' in Zabbix: %s", host_object['host'], name, err)
                return False
        logger.info("Changing hostname '%s' to '%s' in Zabbix", host_object['host'], name)
        return True

    def item_update(self, host_object, item):
        """Running check now task for item"""
        try:
            self.task.create(type=6, request={'itemid': item['itemid']})
        except ZabbixAPIException as err:
            logger.warning("Unable to execute '%s' check for %s: %s", item['name'], host_object['host'], err)
            return False
        logger.info("Executing '%s' check for %s", item['name'], host_object['host'])
        return True
