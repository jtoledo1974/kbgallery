import errno
from os import makedirs
from zlib import crc32
from shutil import rmtree
from os.path import join, dirname
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.image import AsyncImage
from kivy.uix.floatlayout import FloatLayout
from kivy.network.urlrequest import UrlRequest

APP = "KBImage"

Builder.load_string('''
<CachedImage>:
    image: image
    RotImage:
        id: image
        x: root.x
        y: root.y
        orientation: root.orientation

<RotImage>:
    angle: 0
    orientation: 1
    color: [0, 0, 0, 1]
    nocache: True
    canvas.before:
        PushMatrix
        Rotate:
            angle:root.angle
            axis: 0, 0, 1
            origin: root.center
    canvas.after:
        PopMatrix
''')

cache_root = ".kbimgcache"


def set_cache_dir(root):
    global cache_root
    cache_root = root


def get_cache_dir():
    return cache_root


def clear_cache():
    try:
        rmtree(cache_root)
        Logger.info("%s: Cleared cache dir %s" % (APP, cache_root))
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


class RotImage(AsyncImage):
    angle = NumericProperty(0)
    orientation = NumericProperty(1)

    def on_orientation(self, widget, value):
        self.angle = {1: 0, 3: 180, 6: 270, 8: 90}[value]

    def _on_source_load(self, value):
        super(RotImage, self)._on_source_load(value)
        self.color = [1, 1, 1, 1]
        self.allow_stretch = True


class CachedImage(FloatLayout):
    x = NumericProperty()
    y = NumericProperty()
    angle = NumericProperty(0)
    orientation = NumericProperty(1)
    source = StringProperty("", allownone=True)
    image = ObjectProperty()

    def on_source(self, widget, source):
        if not source:
            return
        fn = "{0:x}.jpg".format(crc32(source) & 0xffffffff)
        self.fn = fn = join(cache_root, fn[:2], fn)
        try:
            open(fn)
            self.image.source = fn
        except:
            try:
                makedirs(dirname(fn))
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise
            UrlRequest(url=source, on_success=self.img_downloaded,
                       file_path=fn)

    def img_downloaded(self, req, res):
        Logger.debug("%s: img_downloaded %s %s" % (APP, req, res))
        self.image.source = self.fn