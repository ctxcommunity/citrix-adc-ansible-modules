#!/usr/bin/python
# -*- coding: utf-8 -*-

#  Copyright (c) 2017 Citrix Systems
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

import json
from ansible.module_utils.basic import env_fallback


class ConfigProxyError(Exception):
    pass


class ConfigProxy(object):

    def __init__(self, actual, client, attribute_values_dict, readwrite_attrs, readonly_attrs, json_encodes=[]):

        # Actual config object from nitro sdk
        self.actual = actual

        # nitro client
        self.client = client

        # ansible attribute_values_dict
        self.attribute_values_dict = attribute_values_dict

        self.readwrite_attrs = readwrite_attrs
        self.readonly_attrs = readonly_attrs
        self.json_encodes = json_encodes

        self._copy_attributes_to_actual()

    def _copy_attributes_to_actual(self):
        for attribute in self.readwrite_attrs:
            if attribute in self.attribute_values_dict:
                attribute_value = self.attribute_values_dict[attribute]
                if attribute_value is None:
                    continue

                # Fallthrough
                if attribute in self.json_encodes:
                    attribute_value = json.JSONEncoder().encode(attribute_value).strip('"')
                setattr(self.actual, attribute, attribute_value)

    def __getattr__(self, name):
        if name in self.attribute_values_dict:
            return self.attribute_values_dict[name]
        else:
            raise AttributeError('No attribute %s found' % name)

    def actual_exists(self):
        pass

    def actual_identical(self):
        pass

    def add(self):
        self.actual.__class__.add(self.client, self.actual)

    def update(self):
        return self.actual.__class__.update(self.client, self.actual)

    def delete(self):
        self.actual.__class__.delete(self.client, self.actual)

    def get(self, *args, **kwargs):
        result = self.actual.__class__.get(self.client, *args, **kwargs)

        return result

    def has_equal_attributes(self, other):
        if self.diff_object(other) == {}:
            return True
        else:
            return False

    def diff_object(self, other):
        diff_dict = {}
        for attribute in self.attribute_values_dict:
            # Skip readonly attributes
            if attribute not in self.readwrite_attrs:
                continue

            # Skip attributes not present in module arguments
            if self.attribute_values_dict[attribute] is None:
                continue

            # Check existence
            if hasattr(other, attribute):
                attribute_value = getattr(other, attribute)
            else:
                diff_dict[attribute] = 'missing from other'
                continue

            # Compare values
            param_type = self.attribute_values_dict[attribute].__class__
            if param_type(attribute_value) != self.attribute_values_dict[attribute]:
                str_tuple = (
                    type(self.attribute_values_dict[attribute]),
                    self.attribute_values_dict[attribute],
                    type(attribute_value),
                    attribute_value,
                )
                diff_dict[attribute] = 'difference. ours: (%s) %s other: (%s) %s' % str_tuple
        return diff_dict

    def get_actual_rw_attributes(self, filter='name'):
        if self.actual.__class__.count_filtered(self.client, '%s:%s' % (filter, self.attribute_values_dict[filter])) == 0:
            return {}
        server_list = self.actual.__class__.get_filtered(self.client, '%s:%s' % (filter, self.attribute_values_dict[filter]))
        actual_instance = server_list[0]
        print('actual_instance %s' % actual_instance)
        ret_val = {}
        for attribute in self.readwrite_attrs:
            if not hasattr(actual_instance, attribute):
                continue
            ret_val[attribute] = getattr(actual_instance, attribute)
        return ret_val

    def get_actual_ro_attributes(self, filter='name'):
        if self.actual.__class__.count_filtered(self.client, '%s:%s' % (filter, self.attribute_values_dict[filter])) == 0:
            return {}
        server_list = self.actual.__class__.get_filtered(self.client, '%s:%s' % (filter, self.attribute_values_dict[filter]))
        actual_instance = server_list[0]
        print('actual_instance %s' % actual_instance)
        ret_val = {}
        for attribute in self.readonly_attrs:
            if not hasattr(actual_instance, attribute):
                continue
            ret_val[attribute] = getattr(actual_instance, attribute)
        return ret_val

    def get_missing_rw_attributes(self):
        return list(set(self.readwrite_attrs) - set(self.get_actual_rw_attributes().keys()))

    def get_missing_ro_attributes(self):
        return list(set(self.readonly_attrs) - set(self.get_actual_ro_attributes().keys()))


def ensure_feature_is_enabled(client, feature_str):
    enabled_features = client.get_enabled_features()
    if feature_str not in enabled_features:
        client.enable_features(feature_str)
        client.save_config()


def get_nitro_client(module):
    from nssrc.com.citrix.netscaler.nitro.service.nitro_service import nitro_service

    client = nitro_service(module.params['nsip'], module.params['nitro_protocol'])
    client.set_credential(module.params['nitro_user'], module.params['nitro_pass'])
    client.timeout = float(module.params['nitro_timeout'])
    client.certvalidation = module.params['ssl_cert_validation']
    return client


netscaler_common_arguments = dict(
    nsip=dict(
        required=True,
        fallback=(env_fallback, ['NETSCALER_NSIP']),
    ),
    nitro_user=dict(
        required=True,
        fallback=(env_fallback, ['NETSCALER_NITRO_USER']),
        no_log=True
    ),
    nitro_pass=dict(
        required=True,
        fallback=(env_fallback, ['NETSCALER_NITRO_PASS']),
        no_log=True
    ),
    nitro_protocol=dict(
        choices=['http', 'https'],
        fallback=(env_fallback, ['NETSCALER_NITRO_PROTOCOL']),
        default='http'
    ),
    ssl_cert_validation=dict(
        default=False,
        type='bool'
    ),
    nitro_timeout=dict(default=310, type='float'),
    operation=dict(
        required=True,
        choices=[
            'present',
            'absent',
        ]
    )
)


loglines = []


def log(msg):
    loglines.append(msg)
