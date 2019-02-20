import logging
import os
import re
import time
from os import listdir as os_listdir, makedirs as os_makedirs, walk as os_walk
from os.path import isdir as os_path_isdir, isfile as os_path_isfile, join as os_path_join

import gevent

from pywb.manager.manager import CollectionsManager


# =============================================================================
class AutoIndexer(object):
    EXT_RX = re.compile('.*\.w?arc(\.gz)?$')
    AUTO_INDEX_FILE = 'autoindex.cdxj'

    def __init__(self, colls_dir=None, interval=30, keep_running=True):
        self.manager = CollectionsManager('', colls_dir=colls_dir, must_exist=False)

        self.root_path = self.manager.colls_dir

        self.keep_running = keep_running

        self.interval = interval

        self.last_size = {}

        self.ge = None

    def is_newer_than(self, path1, path2, track=False):
        try:
            mtime1 = os.path.getmtime(path1)
            mtime2 = os.path.getmtime(path2)
            newer = mtime1 > mtime2
        except Exception:
            newer = True

        if track:
            size = os.path.getsize(path1)
            try:
                if size != self.last_size[path1]:
                    newer = True
            except Exception:
                pass

            self.last_size[path1] = size

        return newer

    def do_index(self, files):
        logging.info('Auto-Indexing... ' + str(files))
        self.manager.index_merge(files, self.AUTO_INDEX_FILE)
        logging.info('...Done')

    def check_path(self):
        for coll in os_listdir(self.root_path):
            coll_dir = os_path_join(self.root_path, coll)
            if not os_path_isdir(coll_dir):
                continue

            self.manager.change_collection(coll)

            archive_dir = self.manager.archive_dir

            if not os_path_isdir(archive_dir):
                continue

            index_file = os_path_join(self.manager.indexes_dir, self.AUTO_INDEX_FILE)

            if not os_path_isfile(index_file):
                try:
                    os_makedirs(self.manager.indexes_dir)
                except Exception as e:
                    pass

            logging.info('Checking Collection: ' + coll)
            to_index = []
            to_index_append = to_index.append

            self_EXT_RX_match = self.EXT_RX.match
            self_is_newer_than = self.is_newer_than

            for dirpath, dirnames, filenames in os_walk(archive_dir):
                for filename in filenames:
                    if not self_EXT_RX_match(filename):
                        continue

                    full_filename = os_path_join(dirpath, filename)

                    if self_is_newer_than(full_filename, index_file, True):
                        to_index_append(full_filename)

            if to_index:
                self.do_index(to_index)

    def run(self):
        try:
            # If running in uwsgi, run AutoIndexer only in first worker!
            import uwsgi
            if uwsgi.worker_id() != 1:
                return
        except Exception:
            pass

        try:
            while self.keep_running:
                self.check_path()
                if not self.interval:
                    break

                time.sleep(self.interval)
        except KeyboardInterrupt:  # pragma: no cover
            return

    def start(self):
        self.ge = gevent.spawn(self.run)

    def stop(self):
        self.interval = 0
        self.keep_running = False
