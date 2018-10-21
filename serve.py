#!/usr/bin/env python

import re
import os
import time
import argparse
from glob import glob
from xml.dom import minidom
from string import Template

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

DEFAULT_PORT = 8080
TAGPATTERN = re.compile(r'<(\w+)>(\w+)', re.I + re.M)

class Handler(BaseHTTPRequestHandler):

    def do_POST(self):
        assert self.headers['SOAPAction'], 'Invalid request'

        action = self.headers['SOAPAction'].strip('"')
        path = 'responses/%s.xml' % action
        self.log_message(action)

        if not os.path.exists(path):
            msg = 'Sorry, unkown action %s' % action
            self.send_error(404, msg)
            return

        if os.getenv('GSX_THROTTLE'):
            t = int(os.getenv('GSX_THROTTLE'))
            self.log_message('Throttling for %d seconds' % t)
            time.sleep(t)
        
        try:
            context = {}
            l = int(self.headers['Content-Length'])
            xml = self.rfile.read(l).decode('utf8')
            dom = minidom.parseString(xml)

            # Build a dictionary of all simple text elements
            for v in re.findall(TAGPATTERN, xml):
                k = '$' + v[0]
                context[k] = v[1]

            print("****** REQUEST ****** (%s) \n%s" % (context, dom.toprettyxml('  ')))

            self.send_response(200)
            self.send_header('Content-Type', 'text/xml; charset="UTF-8"')
            self.end_headers()

            def reflect(m):
                k = '$' + m.group(1)
                if context.get(k):
                    return '<%s>%s' % (m.group(1), context[k])
                
                return m.group(0)

            with open(path, 'r') as f:
                xml = f.read()
                xml = re.sub(TAGPATTERN, reflect, xml, re.I + re.M)
                xml = Template(xml).safe_substitute(context)
                print("****** RESPONSE ****** \n%s" % xml)

                self.send_header('Content-Length', len(xml))
                self.wfile.write(xml.encode())

        except Exception as e:
            self.send_error(500, 'Invalid request: %s' % e)
            print(e)


def validate_responses():
    """
    Checks that the response XML files are parseable
    """
    for r in glob('responses/*.xml'):
        try:
            minidom.parse(r)
        except Exception:
            raise Exception('Invalid XML response: %s' % r)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--address',
        help='Address to host server on',
        default='localhost')
    parser.add_argument('-p', '--port',
        help='Port number to host server on [%s]' % DEFAULT_PORT,
        default=DEFAULT_PORT,
        type=int)
    args = parser.parse_args()

    print('Validating XML responses...')
    validate_responses()

    with HTTPServer((args.address, args.port), Handler) as httpd:
        print('GSX mock server serving on http://%s:%d' % (args.address, args.port))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('GSX mock server shutting down...')
            httpd.shutdown()
