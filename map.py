import os
import sqlite3 as sqlite


class App(object):
    def __init__(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response

    def get_layers(self):
        layers = dict((s.rsplit('.', 1)[0], s) for s in os.listdir('layers'))
        return layers

    def not_found(self, reason: str = b'Not found'):
        self.start_response('404 Not found', [('Access-Control-Allow-Origin', '*')])
        return [reason.encode('utf-8')]

    def ok(self, output: bytes, content_type):
        response_headers = [
            ('Content-type', content_type),
            ('Content-Length', str(len(output))),
            ('Access-Control-Allow-Origin', '*')]
        self.start_response('200 OK', response_headers)
        return [output]

    def viewer(self):
        html = '''
<!DOCTYPE html>
<html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.3.1/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.3.1/dist/leaflet.js"></script>
        <script src="https://rawgithub.com/mlevans/leaflet-hash/master/leaflet-hash.js"></script>
        <style>
            body, html, #map {
             height: 100%%;
            }
        </style>

        <script>
            var layers = %s;

            function setUpMap(){
                 map = new L.Map('map', {fadeAnimation: false});
                 baseMaps = {};
                 for (i=0; i < layers.length; i++) {
                    name = layers[i][0];
                    url = layers[i][1];
                    layer  = new L.TileLayer(url, {tms: true});
                    baseMaps[name] = layer;
                    if (i==0) {
                        layer.addTo(map);
                    }
                 }
                 L.control.layers(baseMaps, {}, {collapsed: false}).addTo(map);
                 map.setView([55, 36], 9);
                 var hash = new L.Hash(map);
            }

            window.onload = setUpMap;
        </script>
    </head>
    <body style="margin: 0">
        <div id="map"></div>

    </body>
</html>
'''
        import json
        layers = self.get_layers().keys()
        layers = [(layer, '%s://%s/%s/{z}/{x}/{y}' % (self.environ.get('UWSGI_SCHEME', 'http'), self.environ['HTTP_HOST'], layer)) for layer in layers]
        return self.ok((html % json.dumps(layers)).encode('utf-8'), 'text/html')
        
#    def layers(self):
#        import json
#        layers = self.get_layers().keys()
#        urls = ['%s://%s/%s/{z}/{x}/{y}' % (self.environ['UWSGI_SCHEME'], self.environ['HTTP_HOST'], layer) for layer in layers]
#        return self.ok(json.dumps(urls), 'text/plain')
    
    def tile(self):
        path = self.environ['PATH_INFO'].strip('/').split('/')
        if len(path) < 4:
            return self.not_found('Path invalid')
        layer, z, x, y = path[-4:]
        y = y.split('.', 1)[0]
        layers = self.get_layers()
        if layer not in layers:
            return self.not_found('Layer %s' % layer)
        filename = 'layers/' + layers[layer]
        conn = sqlite.connect(filename)
        row = conn.execute('select tile_data from tiles where zoom_level=? AnD tile_column=? AND tile_row=?', (z, x, y)).fetchone()
        if row is None:
            return self.not_found('Tile z=%s x=%s y=%s' % (z, x, y))
        return self.ok(row[0], 'image/png')

    def route(self):
        path = self.environ['PATH_INFO']
        if path == '/':
            return self.viewer()
#        elif path in ('/layers', '/layers/'):
#            return self.layers()
        else:
            return self.tile()


def application(environ, start_response):
    return App(environ, start_response).route()


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    make_server('127.0.0.1', 8080, application).serve_forever()
