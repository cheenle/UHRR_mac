#!/usr/bin/env python3
import tornado.ioloop
import tornado.web

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world! The server is working.")

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/(.*)", tornado.web.StaticFileHandler, {"path": "www"}),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8889)
    print("Test server started on port 8889")
    tornado.ioloop.IOLoop.current().start()