import os

import gflags
from launchpadlib import launchpad


FLAGS = gflags.FLAGS
gflags.DEFINE_string('project', None, 'which project to export')
gflags.DEFINE_string('username', None, 'github username')
gflags.DEFINE_string('token', None, 'github password')
gflags.DEFINE_string('repo_user', None, 'github repo user')
gflags.DEFINE_string('repo_name', None, 'github repo name')
gflags.DEFINE_string('milestones_map', None,
                     'file with mapping data for milestones')
gflags.DEFINE_string('bugs_map', None,
                     'file with mapping data for bugs')
gflags.DEFINE_string('blueprints_map', None,
                     'file with mapping data for blueprints')
gflags.DEFINE_boolean('lp_login', False, 'login to launchpad to access private projects')


class Client():
    def __init__(self):
        self.__conn = None

    @property
    def conn(self):
        if not self.__conn:
            cachedir = os.path.abspath('./cachedir')
            if not os.path.exists(cachedir):
                os.mkdir(cachedir)
            if FLAGS.lp_login:
                lp = launchpad.Launchpad.login_with(
                    'lp2gh', 'production', cachedir, version='devel')
            else:
                lp = launchpad.Launchpad.login_anonymously(
                    'lp2gh', 'production', cachedir, version='devel')
            self.__conn = lp
        return self.__conn

    def project(self, name):
        return self.conn.projects[name]
