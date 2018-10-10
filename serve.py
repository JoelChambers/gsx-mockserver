#!/usr/bin/env python

import re
import os
import time
import argparse
from glob import glob
from string import Template
import xml.etree.ElementTree as ET

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):

    def do_POST(self):
        assert self.headers['SOAPAction'], 'Invalid request'

        self.action = self.headers['SOAPAction'].strip('"')
        self.path = 'responses/%s.xml' % self.action
        self.log_message(self.action)

        if not os.path.exists(self.path):
            msg = 'Sorry, unkown action %s' % self.action
            self.send_error(404, msg)
            return

        if os.getenv('GSX_THROTTLE'):
            t = int(os.getenv('GSX_THROTTLE'))
            self.log_message('Throttling for %d seconds' % t)
            time.sleep(t)
        
        try:
            l = int(self.headers['Content-Length'])
            xml = self.rfile.read(l).decode('utf8')
            context = {}

            for v in re.findall(r'<(\w+)>(\w+)', xml, re.I + re.M):
                k = '$' + v[0]
                context[k] = v[1]

            print("****** REQUEST ****** (%s) \n%s" % (context, xml))

            self.send_response(200)
            self.send_header('Content-Type', 'text/xml; charset="UTF-8"')
            self.end_headers()

            def reflect(m):
                k = '$' + m.group(1)
                if context.get(k):
                    return '<%s>%s' % (k, context[k])
                
                return m.group(0)

            with open(self.path, 'r') as f:
                xml = f.read()
                xml = re.sub(r'<(\w+)>\w+', reflect, xml, re.I + re.M)
                xml = Template(xml).safe_substitute(context)
                print("****** RESPONSE ****** \n%s" % xml)

                self.send_header('Content-Length', len(xml))
                self.wfile.write(xml.encode())

        except Exception as e:
            print(e)
            self.send_error(500, 'Invalid request')
            return


def validate_responses():
    for r in glob('responses/*.xml'):
        try:
            ET.parse(r)
        except ET.ParseError:
            raise Exception('Invalid XML response: %s' % r)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--address',
        help='Address to host server on', default='localhost')
    parser.add_argument('-p', '--port',
        help='Port number to host server on', default=8080, type=int)
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
