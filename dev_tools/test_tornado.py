#!/usr/bin/env python3
import tornado.web
import tornado.ioloop

class TestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, World!")

def make_app():
    return tornado.web.Application([
        (r"/", TestHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8889)
    print("Test server started on port 8889")
    tornado.ioloop.IOLoop.current().start()