"""
Refresh any files in support-files/ that come from elsewhere
"""

import os
import urllib
import sys

here = os.path.dirname(__file__)
support_files = os.path.join(here, 'support-files')

files = [
    ('http://peak.telecommunity.com/dist/ez_setup.py', 'ez_setup.py'),
    ('http://pypi.python.org/packages/2.5/s/setuptools/setuptools-0.6c8-py2.5.egg', 'setuptools-0.6c8-py2.5.egg'),
    ('http://pypi.python.org/packages/2.4/s/setuptools/setuptools-0.6c8-py2.4.egg', 'setuptools-0.6c8-py2.4.egg'),
    ]

def main():
    for url, filename in files:
        print 'fetching', url, '...',
        sys.stdout.flush()
        f = urllib.urlopen(url)
        content = f.read()
        f.close()
        print 'done.'
        filename = os.path.join(support_files, filename)
        if os.path.exists(filename):
            f = open(filename, 'rb')
            cur_content = f.read()
            f.close()
        else:
            cur_content = ''
        if cur_content == content:
            print '  %s up-to-date' % filename
        else:
            print '  overwriting %s' % filename
            f = open(filename, 'wb')
            f.write(content)
            f.close()

if __name__ == '__main__':
    main()
    
            
