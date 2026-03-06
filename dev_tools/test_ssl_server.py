#!/usr/bin/env python3
import tornado.ioloop
import tornado.web
import tornado.httpserver
import os

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world! The SSL server is working.")

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    ssl_options = {
        "certfile": os.path.join("UHRH.crt"),
        "keyfile": os.path.join("UHRH.key"),
    }
    http_server = tornado.httpserver.HTTPServer(app, ssl_options=ssl_options)
    http_server.listen(8891)
    print("SSL Test server started on https://localhost:8891")
    tornado.ioloop.IOLoop.current().start()