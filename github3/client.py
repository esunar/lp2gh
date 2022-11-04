from github3 import request


def _resource_factory(client, data):
    """Helper function for mapping responses into Resources."""
    return Resource(client, data.get('url'), data)


class Client(request.Request):
    def repo(self, user, repo_):
        return Repo(client=self, user=user, repo=repo_)


class Repo(object):
    BASE_URL = "https://api.github.com/repos"

    def __init__(self, client, user, repo):
        self.client = client
        self.user = user
        self.repo = repo
        self.org = False

    def issues(self, **kw):
        """Return a PaginatedResourceList of issues."""
        url = f'{self.BASE_URL}/{self.user}/{self.repo}/issues'
        resp = self.client.get(url, **kw)
        return PaginatedResourceList.from_response(self.client, resp)

    def issue(self, id_):
        """Return a Resource of an issue."""
        url = f'{self.BASE_URL}/{self.user}/{self.repo}/issues/{id_}'
        resp = self.client.get(url)
        return Resource(self.client, url, resp.json())
      

    def milestones(self, **kw):
        """Return a PaginatedResourceList of milestones."""
        url = f'{self.BASE_URL}/{self.user}/{self.repo}/milestones'
        resp = self.client.get(url, **kw)
        return PaginatedResourceList.from_response(self.client, resp)

       

    def labels(self, **kw):
        """Return a PaginatedResourceList of labels."""
        url = f'{self.BASE_URL}/{self.user}/{self.repo}/labels'
        resp = self.client.get(url, **kw)
        return PaginatedResourceList.from_response(self.client, resp)

    def comments(self, issue, **kw):
        """Return a PaginatedResourceList of comments for an issue."""
        url = f'{self.BASE_URL}/{self.user}/{self.repo}/issues/{issue}/comments'
        resp = self.client.get(url, **kw)
        return PaginatedResourceList.from_response(self.client, resp)    
        


class ResourceList(object):
    def __init__(self, client, url, datalist=None):
        self.client = client
        self.url = url
        self.datalist = datalist

    @classmethod
    def from_response(cls, client, response):
        return cls(client,
                   response.geturl(),
                   [_resource_factory(client, x) for x in response.json()])

    def append(self, **kw):
        rv = self.client.post(self.url, **kw)
        json = rv.json()
        if (rv.status_code == 403 and "You have exceeded" in json.get("message", "")):
            raise RateLimitExceededError(rv)

        return json

    def __iter__(self):
        return iter(self.datalist)


class PaginatedResourceList(ResourceList):
    def __init__(self, client, url, datalist=None, next_page=None):
        super(PaginatedResourceList, self).__init__(client, url, datalist)
        self.next_page = next_page

    @classmethod
    def from_response(cls, client, response):
        next_page = response.headers.get('X-Next')
        return cls(client,
                   response.url,
                   [_resource_factory(client, x)
                    for x in cls.extract_json(response)],
                   next_page=next_page)

    @classmethod
    def extract_json(cls, response):
        try:
            return response.json()
        except Exception:
            return {}

    def __iter__(self):
        i = 0
        while True:
            try:
                yield self.datalist[i]
            except IndexError:
                if self.next_page:
                    response = self.client.get(self.next_page)
                    self.next_page = response.headers().get('X-Next')
                    self.datalist.extend(
                        [_resource_factory(self.client, x) for x in response.json()])
                    yield self.datalist[i]
                else:
                    raise StopIteration

            i += 1


class Resource(dict):
    def __init__(self, client, url, data=None):
        self.client = client
        self.url = url
        dict.__init__(self, **data)

    def __setitem__(self, key, val):
        """Remote resource"""
        pass

    def __delitem__(self, key):
        """Remote resource"""
        pass

    def update(self, kw):
        rv = self.client.patch(self.url, **kw)
        dict.update(self, kw)
        return rv.json()

    def delete(self):
        self.client.delete(self.url)


class RateLimitExceededError(Exception):
    """Exception raised for errors in cas of github request rate exceeded

    Attributes:
        response -- raw response
        message -- explanation of the error
    """

    def __init__(self, response, message="Rate Limit Exceeded!!!"):
        self.response = response
        self.message = message
        super().__init__(self.message)
