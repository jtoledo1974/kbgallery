import errno
from os import makedirs, lstat, unlink
from zlib import crc32
from shutil import rmtree
from os.path import join, dirname
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.properties import AliasProperty, BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.image import AsyncImage
from kivy.uix.floatlayout import FloatLayout
from kivy.network.urlrequest import UrlRequest

APP = "KBImage"

Builder.load_string('''
<CachedImage>:
    image: image
    scatter: scatter
    Scatter:
        id: scatter
        do_rotation: False
        do_scale: False
        do_translation: False
        scale_min: 1.0
        on_scale: root.on_scatter_scale(*args)
        RotImage:
            id: image
            x: root.x
            y: root.y
            width: root.width
            height: root.height
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

    def get_norm_image_size(self):
        if not self.texture:
            return self.size
        ratio = self.image_ratio
        s = self.size
        if self._rotate:
            w, h = s[1], s[0]
        else:
            w, h = s
        tw, th = self.texture.size

        # ensure that the width is always maximized to the containter width
        if self.allow_stretch:
            if not self.keep_ratio:
                return w, h
            iw = w
        else:
            iw = min(w, tw)
        # calculate the appropriate height
        ih = iw / ratio
        # if the height is too higher, take the height of the container
        # and calculate appropriate width. no need to test further. :)
        if ih > h:
            if self.allow_stretch:
                ih = h
            else:
                ih = min(h, th)
            iw = ih * ratio

        return iw, ih

    norm_image_size = AliasProperty(get_norm_image_size, None, bind=(
        'texture', 'size', 'image_ratio', 'allow_stretch'))
    '''Normalized image size within the widget box.

    This size will always fit the widget size and will preserve the image
    ratio.

    :attr:`norm_image_size` is a :class:`~kivy.properties.AliasProperty` and is
    read-only.
    '''

    def __init__(self, **kwargs):
        self.previous_orientation = 1
        self._rotate = False
        super(RotImage, self).__init__(**kwargs)

    def on_orientation(self, widget, value):
        self.angle = {1: 0, 3: 180, 6: 270, 8: 90}[value]
        p, n = self.previous_orientation, value  # previous, new
        if (p, n) in [(1, 6), (1, 8), (3, 6), (3, 8),
                      (6, 1), (6, 3), (8, 1), (8, 3)]:
            self._rotate = True
        self.previous_orientation = value

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
    scatter = ObjectProperty()
    load = BooleanProperty(True)
    allow_scale = BooleanProperty(False)
    image_scale = NumericProperty(1.0)  # To be used by parent widgets

    def __init__(self, **kwargs):
        super(CachedImage, self).__init__(**kwargs)
        self.on_source(self, self.source)
        self.on_allow_scale(self, self.allow_scale)

    def on_allow_scale(self, widget, allow):
        if not self.scatter:
            return
        if allow:
            self.scatter.do_scale = True
        else:
            self.scatter.do_scale = False

    def on_scatter_scale(self, widget, scale):
        scatter = self.scatter
        self.image_scale = scale  # To be used by parent widgets
        if scale <= 1.0:
            scatter.scale = 1.0
            scatter.do_translation = False
            scatter.apply_transform(scatter.transform_inv)
        elif scale > 1 and self.allow_scale:
            scatter.do_translation = True

    def on_source(self, widget, source):
        if not source or not self.image or not self.load:
            return
        fn = "{0:x}.jpg".format(crc32(source) & 0xffffffff)
        self.fn = fn = join(cache_root, fn[:2], fn)
        try:
            open(fn)  # Keep for reference: getattr(os.lstat(fn), 'st_size')
            self.image.source = fn
        except:
            try:
                makedirs(dirname(fn))
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    raise
            UrlRequest(url=source, on_success=self.img_downloaded, file_path=fn,
                       on_failure=self.cleanup, on_error=self.cleanup)

    def on_load(self, widget, load):
        if not load or not self.source:
            return
        self.on_source(self, self.source)

    def img_downloaded(self, req, res):
        Logger.debug("%s: img_downloaded %s %s" % (APP, req, res))
        self.image.source = self.fn

    def cleanup(self, *args):
        try:
            unlink(self.fn)
        except:
            pass
