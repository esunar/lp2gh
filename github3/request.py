from concurrent.futures import thread
import requests
import urllib


class Request(object):
    def __init__(self, username=None, oauth_token=None):
        self._username = username
        self._oauth_token = oauth_token
        self._headers = {"Authorization": "Bearer " +
                         self._oauth_token, "accept": "application/vnd.github+json"}

    def head(self, url, **kw):
        url = '%s?%s' % (url, urllib.parse.urlencode(kw))
        return self._execute(method='HEAD', url=url)

    def get(self, url, **kw):
        url = '%s?%s' % (url, urllib.parse.urlencode(kw))
        return self._execute(method='GET', url=url)

    def post(self, url, **kw):
        return self._execute(method='POST', url=url, json=kw)

    def patch(self, url, **kw):
        return self._execute(method='PATCH', url=url, json=kw)

    def put(self, url, **kw):
        return self._execute(method='PUT', url=url, json=kw)

    def delete(self, url, **kw):
        url = '%s?%s' % (url, urllib.parse.urlencode(kw))
        return self._execute(method='DELETE', url=url)


    def _check_result(self, response):
        return response

    def _execute(self, method, url, json = None):
        respone = requests.request(method=method, url=url, headers=self._headers, json=json)
        return self._check_result(respone)

 
