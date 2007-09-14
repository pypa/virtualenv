"""
Refresh any files in support-files/ that come from elsewhere
"""

import os
import urllib

here = os.path.dirname(__file__)
support_files = os.path.join(here, 'support-files')

files = [
    ('http://peak.telecommunity.com/dist/ez_setup.py', 'ez_setup.py'),
    ]

def main():
    for url, filename in files:
        print 'fetching', url,
        f = urllib.urlopen(url)
        print 'done.'
        content = f.read()
        f.close()
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
    
            
