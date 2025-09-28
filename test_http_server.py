#!/usr/bin/env python3
import tornado.ioloop
import tornado.web
import os

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world! The HTTP server is working.")

class StaticFileHandler(tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        # Disable cache for testing
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/(.*)", StaticFileHandler, {"path": "www"}),
    ], debug=True)

if __name__ == "__main__":
    app = make_app()
    app.listen(8890)
    print("HTTP Test server started on http://localhost:8890")
    tornado.ioloop.IOLoop.current().start()