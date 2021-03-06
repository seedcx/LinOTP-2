# -*- coding: utf-8 -*-
#
#    LinOTP - the open source solution for two factor authentication
#    Copyright (C) 2010 - 2019 KeyIdentity GmbH
#
#    This file is part of LinOTP server.
#
#    This program is free software: you can redistribute it and/or
#    modify it under the terms of the GNU Affero General Public
#    License, version 3, as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the
#               GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#    E-mail: linotp@keyidentity.com
#    Contact: www.linotp.org
#    Support: www.keyidentity.com
#
"""This is the BaseClass for logging Audit Trails"""

import logging
log = logging.getLogger(__name__)
import os
import socket

from subprocess import check_call

from flask import current_app
from linotp.lib.token import get_used_tokens_count
from linotp.lib.support import get_license_type

from linotp.lib.context import request_context as context
from linotp.model import meta


def getAudit(config):

    audit_url = config.get("AUDIT_DATABASE_URI")

    if audit_url is None:
        # Default to shared database if not set
        audit_url = 'SHARED'

    if audit_url == 'OFF':
        log.warning("Audit logging is disabled because the URL has been configured to %s", audit_url)
        audit = AuditBase(config)
    else:
        from . import SQLAudit
        if audit_url == 'SHARED':
            # Share with main database
            audit = SQLAudit.AuditLinOTPDB(config)
        else:
            audit = SQLAudit.Audit(config, audit_url)
    return audit


def get_token_num_info():
    """
    get the current token / token user count

    :return: literal about the number of used tokens / user tokens
    """

    tokens = get_used_tokens_count()
    token_count_type = 'tokennum'

    if get_license_type() == 'user-num' :
        token_count_type = 'token users'

    return "%s = %d" % (token_count_type, tokens)


class AuditBase(object):

    name = "AuditBase"

    def __init__(self, config):
        self.config = config

        rootdir = current_app.getConfigRootDirectory()

        self.publicKeyFilename = self.config.get("AUDIT_PUBLIC_KEYFILE")
        if not self.publicKeyFilename:
            self.publicKeyFilename = os.path.join(rootdir, "public.pem")

        self.privateKeyFilename = self.config.get("AUDIT_PRIVATE_KEYFILE")
        if not self.privateKeyFilename:
            self.privateKeyFilename = os.path.join(rootdir, "private.pem")

    def initialize(self, request, client=None):
        # defaults
        audit = {'action_detail': '',
                 'info': '',
                 'log_level': 'INFO',
                 'administrator': '',
                 'value': '',
                 'key': '',
                 'serial': '',
                 'token_type': '',
                 'clearance_level': 0,
                 'linotp_server': socket.gethostname(),
                 'realm': '',
                 'user': '',
                 'client': '',
                 'success': False,
                }
        audit['action'] = request.path
        if client:
            audit['client'] = client
        return audit

    def createKeys(self):
        """
        Create audit keys using the configured filenames
        """
        if not os.path.exists(self.privateKeyFilename) and not os.path.exists(self.publicKeyFilename):
            log.info("Generating audit keypair")
            check_call("openssl genrsa -out %s 2048" % self.privateKeyFilename, shell=True)
            check_call("openssl rsa -in %s -pubout -out %s" % (self.privateKeyFilename, self.publicKeyFilename), shell=True)

    def readKeys(self):
        self.createKeys()

        try:
            f = open(self.privateKeyFilename, "r")
            self.private = f.read()
            f.close()
        except Exception as e:
            log.exception("[readKeys] Error reading private key %s: (%r)" % (self.privateKeyFilename, e))

        try:
            f = open(self.publicKeyFilename, "r")
            self.public = f.read()
            f.close()
        except Exception as e:
            log.exception("[readKeys] Error reading public key %s: (%r)" % (self.publicKeyFilename, e))

        return

    def getAuditId(self):
        return self.name

    def getTotal(self, param, AND=True, display_error=True):
        '''
        This method returns the total number of audit entries in the audit store
        '''
        return 0

    def log(self, param):
        '''
        This method is used to log the data.
        It should hash the data and do a hash chain and sign the data
        '''
        pass

    def initialize_log(self, param):
        '''
        This method initialized the log state.
        The fact, that the log state was initialized, also needs to be logged.
        Therefor the same params are passed as i the log method.
        '''
        pass

    def set(self):
        '''
        This function could be used to set certain things like the signing key.
        But maybe it should only be read from linotp.ini?
        '''
        pass

    def search(self, param, AND=True, display_error=True, rp_dict=None):
        '''
        This function is used to search audit events.

        param:
            Search parameters can be passed.

        return:
            A list of dictionaries is return.
            Each list element denotes an audit event.
        '''
        result = [ {} ]
        return result

    def searchQuery(self, param, AND=True, display_error=True, rp_dict=None):
        '''
        This function is used to search audit events.

        param:
            Search parameters can be passed.

        return:
            An iterator is returned.
        '''
        return iter([])


def search(param, user=None, columns=None):

    audit = context['Audit']
    search_dict = {}

    if "query" in param:
        if "extsearch" == param['qtype']:
            # search patterns are delimitered with ;
            search_list = param['query'].split(";")
            for s in search_list:
                key, _e, value = s.partition("=")
                key = key.strip()
                value = value.strip()
                search_dict[key] = value

        else:
            search_dict[param['qtype']] = param["query"]
    else:
        for k, v in list(param.items()):
            search_dict[k] = v

    rp_dict = {}
    page = 1
    if 'page' in param:
        rp_dict['page'] = param.get('page')
        page = param.get('page')

    if 'rp' in param:
        rp_dict['rp'] = param.get('rp')
    if 'sortname' in param:
        rp_dict['sortname'] = param.get('sortname')
    if 'sortorder' in param:
        rp_dict['sortorder'] = param.get('sortorder')

    if user:
        search_dict['user'] = user.login
        search_dict['realm'] = user.realm

    result = audit.searchQuery(search_dict, rp_dict=rp_dict)

    lines = []

    if not columns:
        columns = ['number', 'date', 'sig_check', 'missing_line',
               'action', 'success', 'serial', 'token_type',
               'user', 'realm', 'administrator', 'action_detail',
               'info', 'linotp_server', 'client', 'log_level',
               'clearance_level']

    # In this case we have only a limited list of columns, like in
    # the selfservice portal
    for row in result:
        a = dict(list(row.items()))
        if 'number' not in a and 'id' in a:
            a['number'] = a['id']
        if 'date' not in a and 'timestamp' in a:
            a['date'] = a['timestamp']
        if 'token_type' not in a and 'tokentype' in a:
            a['token_type'] = a['tokentype']

        cell = []
        for colname in columns:
            if len(a['serial']) > 0:
                pass
            cell.append(a.get(colname))
        lines.append({'id': a['id'], 'cell': cell})

    # get the complete number of audit logs
    total = audit.getTotal(search_dict)

    return lines, total, page



###eof#########################################################################
