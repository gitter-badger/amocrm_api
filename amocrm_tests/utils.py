# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import json
import os
import time
from functools import wraps

import six
if six.PY2:
    from urlparse import urlparse, parse_qsl
else:
    from urllib.parse import urlparse, parse_qsl

from responses import RequestsMock

DIR = os.path.normpath(os.path.dirname(__file__))
FILE_DIR = os.path.join(DIR, 'generated.json')


def check_auth(func):
    @wraps(func)
    def _call(self, obj, params):
        if self._check_auth(params):
            return func(self, obj, params)
        return json.dumps({'status': 'error', 'auth': False})

    return _call


class FakeApi(object):
    """docstring for FakeApi"""
    def __init__(self):
        self.login, self.hash = None, None
        self._data = json.loads(open(FILE_DIR).read())

    def _check_auth(self, params):
        login = params.pop('USER_LOGIN', None)
        _hash = params.pop('USER_HASH', None)
        if login == self.login and _hash == self.hash:
            return True
        return False

    def _auth(self, obj, params):
        r = {'auth': False}
        if self._check_auth(params):
            r['auth'] = True
        return json.dumps(r)

    @check_auth
    def _list(self, obj, params):
        if params is None:
            return json.dumps({'status': 'error'})
        _id, query = params.get('id'), params.get('query')
        if _id is not None:
            resp = [i for i in self._data[obj] if int(i['id']) == int(_id)]
        elif query:
            query = json.loads(query)
            resp = [i for i in self._data[obj] if all([j in i.items() for j in query.items()])]
        else:
            resp = self._data[obj]
        if 'limit_rows' in params:
            resp = resp[int(params.get('limit_offset', 0)):int(params.get('limit_rows'))]
        return json.dumps({'response': {obj: resp}})

    @check_auth
    def _set(self, obj, params):
        resp = {}
        try:
            params = params['request'][obj]
        except KeyError:
            pass
        if params:
            if 'update' in params:
                update = params['update']
                update = json.loads(update) \
                    if isinstance(update, str) else update
                update['last_modified'] = time.time()
                target_id = update['id']
                update_obj = (i for i in self._data[obj]
                              if i['id'] == target_id).next()
                update_obj.update(update)
                resp = {'update': {'id': target_id}}
            elif 'add' in params:
                add = params['add']
                add = json.loads(add) if isinstance(add, str) else add
                add['last_modified'] = time.time()
                max_id = max(map(lambda x: int(x['id']), self._data[obj]))\
                            if self._data[obj] else 0
                _id = max_id + 1
                add['id'] = _id
                self._data[obj].append(add)
                resp = {'add': {'id': _id, 'request_id': 1}}
        return json.dumps({'response': {obj: resp}})

    @check_auth
    def _current(self, obj, params):
        return json.dumps({'response': {obj: self._data[obj]}})


class AmoApiMock(RequestsMock):
    _objects = ('contacts', 'notes', 'company', 'tasks', 'leads')
    _base_url = 'https://%(domain)s.amocrm.ru/private/api/v2/%(format)s%(name)s%(path)s'
    _format = 'json'

    def reset(self):
        super(AmoApiMock, self).reset()
        self._faker = FakeApi()

    def _find_match(self, request):
        result = super(AmoApiMock, self)._find_match(request)
        if not result:
            result = self._get_response(request)
        return result

    def _get_response(self, request):
        url_parsed = urlparse(request.url)
        if url_parsed.query or request.body:
            url_qsl = dict(parse_qsl(url_parsed.query) + parse_qsl(request.body))
            try:
                body_data = json.loads(request.body)
            except ValueError:
                pass
            else:
                if body_data:
                    url_qsl.update(body_data)
        else:
            url_qsl = {}
        obj, method = url_parsed.path.split('/')[-2:]
        method = method.split('.')[0]
        body = getattr(self._faker, '_%s' % method)(obj, url_qsl)
        return {
            'body': body,
            'content_type': 'text/plain',
            'status': 200,
            'adding_headers': None,
            'stream': False
        }

    def set_login_params(self, login, _hash):
        self._faker.login = login
        self._faker.hash = _hash


amomock = AmoApiMock()