#!/usr/bin/env python

import os
import time
import argparse
from glob import glob
from io import BytesIO
from string import Template

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from lxml import etree


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
            self.log_message('Throttling for %d' % t)
            time.sleep(t)

        self.send_response(200)
        l = int(self.headers['Content-Length'])
        request = etree.parse(BytesIO(self.rfile.read(l)))

        print(etree.tostring(request, pretty_print=True).decode())

        context = {}
        r = request.xpath('//repairData|//requestData|//MarkRepairCompleteRequest')

        if r:
            for i in r[0].iterchildren():
                context[i.tag] = i.text

        self.send_header('Content-Type', 'text/xml; charset="UTF-8"')
        self.end_headers()

        with open(self.path, 'r') as f:
            xml = f.read()
            xml = Template(xml).safe_substitute(context)
            self.send_header('Content-Length', len(xml))
            self.wfile.write(xml.encode())
            print(xml)


def validate_responses():
    for r in glob('responses/*.xml'):
        try:
            etree.parse(r)
        except etree.XMLSyntaxError:
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
