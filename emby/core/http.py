# -*- coding: utf-8 -*-
import json
import logging
import time
import requests
import emby.core.exceptions
import xbmc

if int(xbmc.getInfoLabel('System.BuildVersion')[:2]) >= 19:
    unicode = str

class HTTP():
    def __init__(self, client):
        self.LOG = logging.getLogger('emby.core.HTTP')
        self.session = None
        self.keep_alive = False
        self.client = client
        self.config = client['config']

    def __shortcuts__(self, key):
        if key == "request":
            return self.request

        return

    def start_session(self):
        self.session = requests.Session()
        """
        max_retries = self.config['http.max_retries']
        self.session.mount("http://", requests.adapters.HTTPAdapter(max_retries=max_retries))
        self.session.mount("https://", requests.adapters.HTTPAdapter(max_retries=max_retries))
        """

    def stop_session(self):
        if self.session is None:
            return

        try:
            self.LOG.warning("--<[ session/%s ]", id(self.session))
            self.session.close()
        except Exception as error:
            self.LOG.warning("The requests session could not be terminated: %s", error)

    def _replace_user_info(self, string):
        if '{server}' in string:
            if self.config['auth.server']:
                string = string.replace("{server}", self.config['auth.server'])
            else:
                raise Exception("Server address not set.")

        if '{UserId}'in string:
            if self.config['auth.user_id']:
                string = string.replace("{UserId}", self.config['auth.user_id'])
            else:
                raise Exception("UserId is not set.")

        return string

    def request(self, data, session=None):
        ''' Give a chance to retry the connection. Emby sometimes can be slow to answer back
            data dictionary can contain:
            type: GET, POST, etc.
            url: (optional)
            handler: not considered when url is provided (optional)
            params: request parameters (optional)
            json: request body (optional)
            headers: (optional),
            verify: ssl certificate, True (verify using device built-in library) or False
        '''
        if not data:
            raise AttributeError("Request cannot be empty")

        data = self._request(data)
        self.LOG.debug("--->[ http ] %s", json.dumps(data, indent=4))
        retry = data.pop('retry', 5)

        def _retry(current):
            if current:
                current -= 1
                time.sleep(1)

            return current

        while True:
            try:
                r = self._requests(session or self.session or requests, data.pop('type', "GET"), **data)
                r.content # release the connection

                if not self.keep_alive and self.session is not None:
                    self.stop_session()

                r.raise_for_status()
            except requests.exceptions.ConnectionError as error:
                retry = _retry(retry)

                if retry:
                    continue

                self.LOG.error(error)
                self.client['callback']("ServerUnreachable", {'ServerId': self.config['auth.server-id']})
                raise emby.core.exceptions.HTTPException("ServerUnreachable", error)
            except requests.exceptions.ReadTimeout as error:
                retry = _retry(retry)

                if retry:
                    continue

                self.LOG.error(error)
                raise emby.core.exceptions.HTTPException("ReadTimeout", error)

            except requests.exceptions.HTTPError as error:
                self.LOG.error(error)

                if r.status_code == 401:
                    if 'X-Application-Error-Code' in r.headers:
                        self.client['callback']("AccessRestricted", {'ServerId': self.config['auth.server-id']})
                        raise emby.core.exceptions.HTTPException("AccessRestricted", error)

                    self.client['callback']("Unauthorized", {'ServerId': self.config['auth.server-id']})
                    self.client['auth/revoke-token']
                    raise emby.core.exceptions.HTTPException("Unauthorized", error)
                elif r.status_code == 500: # log and ignore.
                    self.LOG.error("--[ 500 response ] %s", error)
                    return
                elif r.status_code == 400: # log and ignore.
                    self.LOG.error("--[ 400 response ] %s", error)
                    return
                elif r.status_code == 404: # log and ignore.
                    self.LOG.error("--[ 404 response ] %s", error)
                    return
                elif r.status_code == 502:
                    retry = _retry(retry)

                    if retry:
                        continue
                elif r.status_code == 503:
                    retry = _retry(retry)

                    if retry:
                        continue

                raise emby.core.exceptions.HTTPException(r.status_code, error)
            except requests.exceptions.MissingSchema as error:
                raise emby.core.exceptions.HTTPException("MissingSchema", {'ServerId': self.config['auth.server']})
            except Exception as error:
                raise
            else:
                elapsed = int(r.elapsed.total_seconds() * 1000)
                self.LOG.debug("---<[ http ][%s ms]", elapsed)

                try:
                    self.config['server-time'] = r.headers['Date']

                    if r.status_code == 204:
                        # return, because there is no response
                        return

                    response = r.json()

                    try:
                        self.LOG.debug(json.dumps(response, indent=4))
                    except Exception:
                        self.LOG.debug(response)

                    return response
                except ValueError:
                    return

    def _request(self, data):
        if 'url' not in data:
            data['url'] = "%s/emby/%s" % (self.config['auth.server'], data.pop('handler', ""))

        self._get_header(data)
        data['timeout'] = data.get('timeout') or self.config['http.timeout']
        data['url'] = self._replace_user_info(data['url'])

        if data.get('verify') is None:
            if self.config['auth.ssl'] is None:
                data['verify'] = data['url'].startswith('https')
            else:
                data['verify'] = self.config['auth.ssl']

        self._process_params(data.get('params') or {})
        self._process_params(data.get('json') or {})
        return data

    def _process_params(self, params):
        for key in params:
            value = params[key]

            if isinstance(value, dict):
                self._process_params(value)

            if isinstance(value, (str, unicode)):
                params[key] = self._replace_user_info(value)

    def _get_header(self, data):
        data['headers'] = data.setdefault('headers', {})

        if not data['headers']:
            data['headers'].update({
                'Content-type': "application/json",
                'Accept-Charset': "UTF-8,*",
                'Accept-encoding': "gzip",
                'User-Agent': self.config['http.user_agent'] or "%s/%s" % (self.config['app.name'], self.config['app.version'])
            })

        if 'Authorization' not in data['headers']:
            self._authorization(data)

        return data

    def _authorization(self, data):
        if not self.config['app.device_name']:
            raise KeyError("Device name cannot be null")

        auth = "MediaBrowser "
        auth += "Client=%s, " % self.config['app.name']
        auth += "Device=%s, " % self.config['app.device_name']
        auth += "DeviceId=%s, " % self.config['app.device_id']
        auth += "Version=%s" % self.config['app.version']
        data['headers'].update({'Authorization': auth})

        if self.config['auth.token'] and self.config['auth.user_id']:
            auth += ', UserId=%s' % self.config['auth.user_id']
            data['headers'].update({'Authorization': auth, 'X-MediaBrowser-Token': self.config['auth.token']})

        return data

    def _requests(self, session, action, **kwargs):
        if action == "GET":
            return session.get(**kwargs)
        elif action == "POST":
            return session.post(**kwargs)
        elif action == "HEAD":
            return session.head(**kwargs)
        elif action == "DELETE":
            return session.delete(**kwargs)
