# -*- coding: utf-8 -*-
import errno
from os import makedirs
from json import loads, dumps
from urllib import quote
from os.path import join
from posixpath import join as urljoin
from itertools import islice, izip
from functools import partial

from kivy import platform
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.logger import Logger
from kivy.graphics import Color, Rectangle
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.core.window import Window
from kivy.uix.label import Label
from kivy.uix.listview import ListView
from kivy.uix.carousel import Carousel
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.network.urlrequest import UrlRequest
from kivy.adapters.listadapter import ListAdapter

from image import CachedImage

APP = 'KBContentList'
DIR = 'dir'
FILE = 'file'


Builder.load_string('''
<Imgentry@ButtonBehavior+FloatLayout>:
    text: ''
    source: None
    orientation: 1
    CachedImage:
        x: root.x
        y: root.y
        source: root.source
        fill: True
        orientation: root.orientation
        load: not app.delay_image_loading

<ImglistRow>:
    size_hint_y: None
    height: 160
    Imgentry:
        text: root.f1
        source: root.t1
        orientation: root.o1
        on_release: root.img_selected(root.f1)
    Imgentry:
        text: root.f2
        source: root.t2
        orientation: root.o2
        on_release: root.img_selected(root.f2)
    Imgentry:
        text: root.f3
        source: root.t3
        orientation: root.o3
        on_release: root.img_selected(root.f3)
''')


def pad_modulo(list, padding, modulo):
    length_modulo = len(list) % modulo
    if length_modulo in (0, modulo):
        return list
    else:
        return list + padding * (modulo - length_modulo)


def group(lst, n):
    """group([0,3,4,10,2,3], 2) => iterator

    Group an iterable into an n-tuples iterable. Incomplete tuples
    are discarded e.g.

    >>> list(group(range(10), 3))
    [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    """
    return izip(*[islice(lst, i, None, n) for i in range(n)])


class ResCache():
    def __init__(self):
        self.o = {}
        filename = join(".kbimgcache", "rescache.json")
        try:
            self.o_file = open(filename, "r+")
            self.o = loads(self.o_file.read())
        except:
            try:
                try:
                    makedirs(".kbimgcache")
                except OSError as exception:
                    if exception.errno != errno.EEXIST:
                        raise
                self.o_file = open(filename, "w")
            except:
                Logger.warning(
                    "Error trying to open ResCache file %s for writing"
                    % filename)

    def _save(self):
        self.o_file.seek(0)
        self.o_file.truncate()
        self.o_file.write(dumps(self.o))
        self.o_file.flush()

    def set(self, url, res):
        Logger.debug("Setting res %s for url %s" % (res, url))
        self.o[url] = res
        self._save()

    def get(self, url):
        try:
            return self.o[url]
        except:
            Logger.warning("Res not found for url %s" % url)
            return None

rescache = ResCache()

_direntries = []


def get_direntries(res):
        # TODO Fix this if we want to be able to handle to requests
        # at the same time
        global _direntries
        direntries = []
        sdir = None
        for l in res.split("\n"):
            try:
                d = loads(l)
                try:
                    sdir = d['dir']  # Server dir
                except:
                    # If we get a partial result, only append
                    # the new direntries
                    if d not in _direntries:
                        direntries.append(d)
                        _direntries.append(d)
            except:
                pass
        _direntries = []
        return sdir, direntries


# <Direntry@ButtonBehavior+FloatLayout>:
#     text: ''
#     source: None
#     orientation: 1
#     canvas:
#         Color:
#             rgba: 0, 0, 0, 1
#         Rectangle:
#             size: (self.size[0], self.size[1]*.25)
#             pos: self.pos
#     CachedImage:
#         pos_hint: {'x': 0, 'y': 0.25}
#         size_hint: (1, 0.75)
#         source: root.source
#         fill: True
#         orientation: root.orientation
#         load: not app.delay_image_loading
#         canvas.before:
#             Color:
#                 rgba: 0,0,0,1
#             Rectangle:
#                 size: self.size
#                 pos: self.pos
#     Label:
#         pos_hint: {'x': 0.02, 'top': 0.24}
#         text_size: (root.width*0.96, None)
#         text: root.text
#         size: self.texture_size
#         size_hint: (None, None)

class Direntry(ButtonBehavior, FloatLayout):
    text = StringProperty("")
    source = StringProperty("")
    orientation = NumericProperty(1)

    def __init__(self, **kwargs):
        super(Direntry, self).__init__(**kwargs)

        with self.canvas:
            Color(0, 0, 0, 1)
            self.r = Rectangle()

        self.ci = CachedImage(pos_hint={'x': 0, 'y': 0.25},
                              size_hint=(1, 0.75),
                              fill=True)
        with self.ci.canvas.before:
            Color(0, 0, 0, 1)
            self.ci.r = Rectangle()
        self.add_widget(self.ci)

        self.l = Label(pos_hint={'x': 0.02, 'top': 0.24},
                           size_hint=(None, None))
        self.l.bind(texture_size=lambda *a: setattr(self.l, 'size', a[1]))
        self.add_widget(self.l)

        self.bind(pos=self.update_pos, size=self.update_size,
                  source=self.update_source,
                  orientation=self.update_orientation,
                  text=self.update_text)

        self.update_source(None, self.source)
        self.update_orientation(None, self.orientation)
        self.update_text(None, self.text)

    def update_pos(self, widget, pos):
        self.r.pos = pos
        self.ci.r.pos = pos

    def update_size(self, widget, size):
        self.r.size = (size[0], size[1]*0.25)
        self.ci.r.size = size
        self.l.text_size = (size[0]*0.96, None)

    def update_source(self, i, source):
        self.ci.source = source

    def update_orientation(self, i, orientation):
        self.ci.orientation = orientation

    def update_text(self, i, text):
        self.l.text = text


class ImageDir(FloatLayout, EventDispatcher):

    server_url = StringProperty()
    path = StringProperty("")

    __events__ = ('on_navigate_down', 'on_navigate_top', 'on_img_selected',
                  'on_loading_start', 'on_loading_stop')

    def __init__(self, **kwargs):

        self.navigation = []

        # Currently displayed content widget (dirlist, imglist)
        self._direntries = []  # The direntries already received
        self.content = None   # The Dirlist widget currently displayed

        super(ImageDir, self).__init__(**kwargs)

    def on_server_url(self, *args):
        self.reload()

    def fetch_dir(self, path=''):  # Server dir
        root = self.server_url
        self.path = path
        path = quote((path).encode('utf-8'))
        url = urljoin(root, path, '')
        self.req = UrlRequest(url,
                              on_success=self.got_dirlist,
                              debug=True)
        self.dispatch('on_loading_start')
        self.req.cancel = False

        res = rescache.get(url)
        if res:
            # Create the widget content from the cache data, but since this is
            # called from the parent's init, wait until this object is fully
            # initialized
            callback = partial(self.got_dirlist, None, res)
            Clock.schedule_once(callback, 0)

    def got_dirlist(self, req, res, dt=0):
        # Logger.debug("%s: got_dirlist (req %s, results %s" % (APP, req, res))
        if req and req.cancel:
            return
        elif req:
            self.dispatch('on_loading_stop')
            if res == rescache.get(req.url):
                return
            rescache.set(req.url, res)

        # TODO in partial results sdir may be None
        sdir, direntries = get_direntries(res)

        directories = [de for de in direntries if de[2] == DIR]
        files = [de for de in direntries if de[2] == FILE]

        turl = self.server_url + urljoin('thumb',
                                         quote(sdir.encode('utf-8')))
        if len(directories):
            listclass = Dirlist
            listing = directories
            cols = 2
            arg_dict = {'direntry_selected': self.direntry_selected}
        elif len(files):
            listclass = Imglist
            listing = files
            cols = 3
            arg_dict = {'img_selected': self.img_selected}
        else:
            Logger.warning("Empty directory %s" % urljoin(self.path, sdir))
            return

        ld = [dict(arg_dict.items() +
                   {'direntry': de,
                    'thumb_url': urljoin(turl,
                                         quote(de.encode('utf-8')+'.jpg')),
                    'orientation': orientation}.items())
              for (de, orientation, file_type) in listing]
        ld = pad_modulo(ld, [{'direntry': '', 'thumb_url': '',
                             'orientation': 1}], cols)

        data = group(ld, cols)
        listwidget = listclass(root=self.server_url, path=self.path)
        listwidget.adapter.data = data
        listwidget._reset_spopulate()

        if req and self.content:
            self.remove_widget(self.content)
        self.add_widget(listwidget)
        self.content = listwidget

    def direntry_selected(self, direntry):
        Logger.debug("%s: on_direntry_selected %s" % (
            APP, direntry.encode('ascii','replace')))

        # return

        # TODO Cancelar los requests anteriores si posible
        # El servidor se puede quedar pillado haciendo thumbnails
        # antes de responder al cambio de directorio

        self.remove_widget(self.content)
        self.navigation.append(self.content)
        self.fetch_dir(path=urljoin(self.content.path, direntry, ''))
        self.dispatch('on_navigate_down')

    def img_selected(self, direntry):
        fn = urljoin(self.content.path, direntry)
        Logger.debug("%s: img_selected %s" % (
            APP, fn.encode('ascii', 'replace')))
        self.dispatch('on_img_selected', self.content.path, direntry)

        # TODO Cancelar los requests anteriores si posible
        # El servidor se puede quedar pillado haciendo thumbnails
        # antes de responder al cambio de directorio

        # self.root.container.remove_widget(self.dirlist)
        # self.navigation.append(self.dirlist)
        # self.fetch_dir(path=urljoin(self.dirlist.path, direntry, ''))
        # self.root.with_previous = True

    def reload(self):
        try:
            try:
                path = self.content.path
            except:
                path = self.path
            try:
                self.req.cancel = True
            except:
                pass
            top = not len(self.navigation)
            self.load_previous()
            try:
                self.remove_widget(self.content)
                self.navigation.append(self.content)
            except:
                pass
            self.fetch_dir(path)
            if not top:
                self.dispatch('on_navigate_down')

        except Exception as e:
            Logger.error("%s: Unable to reload content: %s" % (APP, e))

    def load_previous(self):
        try:
            previous = self.navigation.pop(-1)
            self.req.cancel = True
            self.remove_widget(self.content)
            self.add_widget(previous)
            self.content = previous
            self.path = previous.path
        except IndexError:
            pass

        if not len(self.navigation):
            self.dispatch('on_navigate_top')

    def on_navigate_down(self):
        pass

    def on_navigate_top(self):
        pass

    def on_img_selected(self, path, fn):
        pass

    def on_loading_start(self):
        pass

    def on_loading_stop(self):
        pass


class ImglistRow(BoxLayout):
    f1 = StringProperty()  # Filepath 1, 2, 3
    f2 = StringProperty()
    f3 = StringProperty()
    t1 = StringProperty()  # Thumbpath 1, 2, 3
    t2 = StringProperty()
    t3 = StringProperty()
    o1 = NumericProperty(1)  # Orientation 1, 2, 3
    o2 = NumericProperty(1)
    o3 = NumericProperty(1)
    img_selected = ObjectProperty()


class Imglist(ListView):

    def __init__(self, root="", path="", **kwargs):

        self.path = path

        def args_converter(row_index, rec):
            return {'f1': rec[0]['direntry'],
                    'f2': rec[1]['direntry'],
                    'f3': rec[2]['direntry'],
                    't1': rec[0]['thumb_url'],
                    't2': rec[1]['thumb_url'],
                    't3': rec[2]['thumb_url'],
                    'o1': rec[0]['orientation'],
                    'o2': rec[1]['orientation'],
                    'o3': rec[2]['orientation'],
                    'img_selected': rec[0]['img_selected']
                    }

        self.adapter = adapter = ListAdapter(
            data=[],
            args_converter=args_converter,
            cls=ImglistRow,
            selection_mode='none'
            )

        super(Imglist, self).__init__(adapter=adapter, **kwargs)

        scrollview = self.children[0]
        scrollview.scroll_timeout = 500
        scrollview.scroll_distance = 5

# <DirlistRow>:
#     size_hint_y: None
#     height: 240
#     padding: 5
#     spacing: 5
#     canvas:
#         Color:
#             rgba: 0.1, 0.1, 0.1, 1
#         Rectangle:
#             size: self.size
#             pos: self.pos
#     Direntry:
#         text: root.dir1
#         source: root.thumb1
#         orientation: root.orientation1
#         on_release: root.direntry_selected(root.dir1)
#     Direntry:
#         text: root.dir2
#         source: root.thumb2
#         orientation: root.orientation2
#         on_release: root.direntry_selected(root.dir2)


class DirlistRow(BoxLayout):

    dir1 = StringProperty()
    dir2 = StringProperty()
    thumb1 = StringProperty()
    thumb2 = StringProperty()
    orientation1 = NumericProperty(1)
    orientation2 = NumericProperty(1)
    direntry_selected = ObjectProperty()

    def __init__(self, **kwargs):
        super(DirlistRow, self).__init__(**kwargs)

        self.size_hint_y = None
        self.height = 240
        self.padding = 5
        self.spacing = 5

        with self.canvas.before:
            Color(0.1, 0.1, 0.1, 1)
            self.r = Rectangle()

        self.de1 = Direntry(text=self.dir1,
                            source=self.thumb1,
                            orientation=self.orientation1,
                            on_release=lambda *a: self.direntry_selected(self.dir1))

        self.de2 = Direntry(text=self.dir2,
                            source=self.thumb2,
                            orientation=self.orientation2,
                            on_release=lambda *a: self.direntry_selected(self.dir2))

        self.add_widget(self.de1)
        self.add_widget(self.de2)

        self.bind(pos=self.update_pos, size=self.update_size)

    def update_pos(self, i, pos):
        self.r.pos = pos

    def update_size(self, i, size):
        self.r.size = size


class Dirlist(ListView):

    def __init__(self, root="", path="", **kwargs):

        self.path = path

        def args_converter(row_index, rec):
            return {'dir1': rec[0]['direntry'],
                    'dir2': rec[1]['direntry'],
                    'thumb1': rec[0]['thumb_url'],
                    'thumb2': rec[1]['thumb_url'],
                    'orientation1': rec[0]['orientation'],
                    'orientation2': rec[1]['orientation'],
                    'direntry_selected': rec[0]['direntry_selected']}

        self.adapter = adapter = ListAdapter(
            data=[],
            args_converter=args_converter,
            cls=DirlistRow,
            selection_mode='none'
            )

        super(Dirlist, self).__init__(adapter=adapter, **kwargs)

        scrollview = self.children[0]
        scrollview.scroll_timeout = 500
        scrollview.scroll_distance = 5


class ImageCarousel(Carousel):
    server_url = StringProperty("")
    path = StringProperty("")
    filename = StringProperty("")   # To indicate which image to show first

    def __init__(self, **kwargs):
        super(ImageCarousel, self).__init__(**kwargs)
        if platform in ('linux', 'windows'):
            self._keyboard = Window.request_keyboard(
                self._keyboard_closed, self, 'text')
            self._keyboard.bind(on_key_down=self._on_keyboard_down)

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        if keycode[1] == 'escape':
            keyboard.release()
        elif keycode[1] == 'left':
            self.load_previous()
        elif keycode[1] == 'right':
            self.load_next()

        # Return True to accept the key. Otherwise, it will be used by
        # the system.
        return False

    def on_path(self, widget, path):
        if not self.server_url:
            return
        self.clear_widgets()
        url = urljoin(self.server_url, quote((path).encode('utf-8')), "")
        UrlRequest(url, on_success=self.got_dir)
        res = rescache.get(url)
        if res:
            # Create the widget content from the cache data, but since this is
            # called from the parent's init, wait until this object is fully
            # initialized
            callback = partial(self.got_dir, None, res)
            Clock.schedule_once(callback, 0)

    def on_server_url(self, widget, server_url):
        self.on_path(None, self.path)

    def got_dir(self, req, res, dt=0):
        if req:
            if res == rescache.get(req.url):
                return
            else:
                self.clear_widgets()
                rescache.set(req.url, res)

        sdir, direntries = get_direntries(res)

        files = [de for de in direntries if de[2] == FILE]

        jurl = self.server_url + urljoin('jpeg',
                                         quote(sdir.encode('utf-8')), '')
        url = self.server_url + urljoin(quote(sdir.encode('utf-8')), '')

        index = i = 0
        for (fn, orig_orientation, file_type) in files:
            fn = quote(fn.encode('utf-8'))
            if fn[-4:].lower() in (".jpg", "jpeg"):
                file_url = url + fn
            else:
                file_url = jurl + fn + '.jpg'

            orientation = orig_orientation
            if platform == 'android':
                orientation = {1: 8, 3: 6, 6: 6, 8: 8}[orig_orientation]

            image = CachedImage(source=file_url, orientation=orientation,
                                load=False, allow_scale=True)
            image.orig_orientation = orig_orientation
            image.bind(image_scale=self.on_image_scale)
            self.add_widget(image)

            if fn == self.filename:
                index = i
            i +=1

        self.index = index

    def reload(self):
        Logger.error("%s: Carousel reload not implemented" % APP)

    def on_image_scale(self, widget, scale):
        if scale > 1.0:
            self.scroll_timeout = 1;
        else:
            self.scroll_timeout = 200;

    def _insert_visible_slides(self, _next_slide=None, _prev_slide=None):
        super(ImageCarousel, self)._insert_visible_slides(_next_slide, _prev_slide)
        if self._current:
            self._current.children[0].load = True
        if self._next:
            self._next.children[0].load = True
        if self._prev:
            self._prev.children[0].load = True
