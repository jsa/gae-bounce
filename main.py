from itertools import chain, ifilter, tee
import logging
import os

from google.appengine.api import images, memcache
from google.appengine.ext import db, webapp
from google.appengine.ext.webapp.util import run_wsgi_app


def ugroupby(key_fn, iterable):
    """itertools.groupby clone w/ support for unsorted iterables."""
    seen = set()
    keys = iter(iterable)
    while True:
        next = keys.next()
        key = key_fn(next)
        if key not in seen:
            keys, values = tee(keys, 2)
            seen.add(key)
            yield key, chain((next,), ifilter(lambda i: key_fn(i) == key, values))


class Redirect(db.Model):
    domain = db.StringProperty(required=True)
    path = db.StringProperty(default='/')
    status = db.IntegerProperty(default=301)
    location = db.StringProperty(required=True)
    append_path = db.BooleanProperty(default=False)


def cached_redirs():
    redirs = memcache.get('redirects')
    if redirs is None:
        ents = Redirect.all().fetch(1000)
        redirs = {}
        for domain, ents in ugroupby(lambda r: r.domain, ents):
            redirs[domain] = dict((r.path, (r.location, r.append_path, r.status))
                                  for r in ents)
        memcache.set('redirects', redirs, 60 * 60)
    return redirs


class RedirHandler(webapp.RequestHandler):

    def get(self):
        dom, path = os.environ['SERVER_NAME'], os.environ['PATH_INFO']
        dom = cached_redirs()[dom]
        location, append, status = dom.get(path) or dom.get('/')
        if path:
            self.response.set_status(status)
            if append:
                location = location + path
            self.response.headers['Location'] = location
        else:
            self.response.set_status(404)

#    def handle_exception(self, exc, debug_mode):

def main():
    application = webapp.WSGIApplication([
          ('/.*$', RedirHandler),
          ], debug=True)
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
