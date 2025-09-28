#!/usr/bin/env python3
import os
import tornado.web
import tornado.ioloop

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        print("MainHandler called")
        # 模拟 UHRR 的 MainHandler 逻辑
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        # 直接读取并返回文件内容而不是使用 render
        try:
            with open("www/index.html", "r") as f:
                content = f.read()
                self.write(content)
        except Exception as e:
            print(f"Error reading file: {e}")
            self.write("Error loading page")

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/(.*)", tornado.web.StaticFileHandler, {"path": "www"}),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8890)
    print("Debug server started on port 8890")
    tornado.ioloop.IOLoop.current().start()