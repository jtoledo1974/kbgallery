# -*- coding: utf-8 -*-
from datetime import datetime

from kivy import platform
from kivy.app import App
from kivy.config import Config
from kivy.logger import Logger
from kivy.loader import Loader

from image import CachedImage, clear_cache  # Used in the kv file
from imagedir import ImageDir, ImageCarousel

if platform == 'android':
    Logger.debug('KBGALLERY: Importando %s' % datetime.now())
    import android
    from jnius import autoclass, cast
    from android.runnable import run_on_ui_thread
    Intent = autoclass('android.content.Intent')
    String = autoclass('java.lang.String')
    PythonActivity = autoclass('org.renpy.android.PythonActivity')
    activity = PythonActivity.mActivity

if platform == 'win' or platform == 'linux':
    Config.set('graphics', 'width', 480)
    Config.set('graphics', 'height', 756)

APP = 'KBGALLERY'
DIR = 'dir'
FILE = 'file'
__version__ = "0.0.1"


class KBGalleryApp(App):

    def build(self):
        Logger.debug("%s: build %s " % (APP, datetime.now()))
        self.use_kivy_settings = False
        return self.root

    def build_config(self, config):
        Logger.debug("%s: build_config %s " % (APP, datetime.now()))
        config.setdefaults('general', {
            'server_url': 'http://www.lazaro.es:8888/',
        })

    def build_settings(self, settings):
        Logger.debug("%s: build_settings %s " % (APP, datetime.now()))
        settings.add_json_panel('KBGallery', self.config, 'settings.json')

    def on_pause(self):
        return True

    def on_resume(self):
        Logger.debug("%s: On resume %s" % (APP, datetime.now()))

    def on_new_intent(self, intent):
        Logger.debug("%s: on_new_intent %s %s" % (
            APP, datetime.now(), intent.toString()))

    def on_keypress(self, window, keycode1, keycode2, text, modifiers):
        # Logger.debug("%s: on_keypress k1: %s, k2: %s, text: %s, mod: %s" % (
        #     APP, keycode1, keycode2, text, modifiers))

        if keycode1 in [27, 1001]:
            if self._app_settings in self._app_window.children:
                self.close_settings()
                return True
            else:
                self.load_previous()
                return True
        return False

    def on_start(self):
        Logger.debug("%s: on_start %s" % (APP, datetime.now()))

        from kivy.core.window import Window
        Window.bind(on_keyboard=self.on_keypress)

        if platform == 'android':
            android.map_key(android.KEYCODE_BACK, 1001)

            import android.activity as python_activity
            python_activity.bind(on_new_intent=self.on_new_intent)
            self.on_new_intent(activity.getIntent())

        self.server_url = self.config.get('general', 'server_url')

        imagedir = ImageDir(server_url=self.server_url)
        wp = 'with_previous'
        imagedir.bind(
            on_navigate_top=lambda *a: setattr(self.root, wp, False),
            on_navigate_down=lambda *a: setattr(self.root, wp, True),
            on_img_selected=self.load_carousel,
            path=lambda w,v: setattr(self.root, 'title', v))
        self.imagedir = imagedir

        self.root.container.add_widget(imagedir)
        self.root.bind(on_touch_down=lambda *a: Loader.pause(),
                       on_touch_up=lambda *a: Loader.resume())
        Loader.max_upload_per_frame = 1  # Maximize interactivity

    def on_stop(self):
        pass

    def reload_content(self):
        content = self.root.container.children[0]
        content.reload()

    def clear_image_cache(self):
        clear_cache()
        return True

    def load_previous(self, *args):
        try:
            content = self.root.container.children[0]
        except:
            return
        if type(content) == ImageDir:
            self.imagedir.load_previous()
        elif type(content) == ImageCarousel:
            self.root.container.remove_widget(self.imagecarousel)
            self.root.container.add_widget(self.imagedir)
            self.imagecarousel = None
        else:
            Logger.error("Unknown content type %s" % type(content))

    def load_carousel(self, widget, path, fn):
        self.root.container.remove_widget(self.imagedir)
        imagecarousel = ImageCarousel(server_url=self.server_url, path=path)
        self.root.container.add_widget(imagecarousel)
        self.imagecarousel = imagecarousel

    def on_config_change(self, config, section, key, value):
        Logger.debug("%s: on_config_change key %s %s" % (
            APP, key, value))
        try:
            content = self.root.container.children[0]
        except:
            return
        if key == 'server_url':
            if type(content) == ImageCarousel:
                self.load_previous()
            content.server_url = value

    if platform == 'android':
        @run_on_ui_thread
        def toast(self, text="texto", short=True):
            Logger.debug("%s: texto %s, short %s" % (
                APP, text.encode('ascii', 'ignore'), short))
            Toast = autoclass('android.widget.Toast')
            Gravity = autoclass('android.view.Gravity')
            duration = Toast.LENGTH_SHORT if short else Toast.LENGTH_LONG
            t = Toast.makeText(activity, String(text), duration)
            t.setGravity(Gravity.BOTTOM, 0, 0)
            t.show()
    else:
        def toast(*args, **kwargs):
            pass

    def send_log(self):
        if platform != 'android':
            return
        Logger.debug("%s: send_log %s" % (APP, datetime.now()))

        from subprocess import Popen
        Uri = autoclass('android.net.Uri')
        File = autoclass('java.io.File')
        FileOutputStream = autoclass('java.io.FileOutputStream')
        Build = autoclass('android.os.Build')
        BV = autoclass('android.os.Build$VERSION')

        try:
            f = open("log.txt", "w")
            fa = File(activity.getExternalFilesDir(None), "log.txt")
            p1 = Popen(["/system/bin/logcat", "-d"], stdout=f)
            p1.wait()
            out = FileOutputStream(fa)
            f.close()
            f = open("log.txt", "r")
            out.write("".join(f.readlines()))
        except Exception as e:
            Logger.debug("%s: Log creation failed %s" % (APP, str(e)))
        finally:
            f.close()
            out.close()

        texto = "%s\n%s\n%s\n%s\n\n" % (
            Build.MANUFACTURER, Build.MODEL, BV.RELEASE, self.about())

        intent = Intent(Intent.ACTION_SEND).setType('message/rfc822')
        intent = intent.putExtra(Intent.EXTRA_TEXT, String(texto))
        intent = intent.putExtra(Intent.EXTRA_EMAIL, ["toledo+kbgallery@lazaro.es"])
        intent = intent.putExtra(Intent.EXTRA_SUBJECT, String("KBGallery Log"))
        try:
            intent = intent.putExtra(
                Intent.EXTRA_STREAM,
                cast('android.os.Parcelable', Uri.fromFile(fa)))

            activity.startActivity(Intent.createChooser(
                intent, String("Send Log with:")))
        except Exception as e:
            Logger.debug("%s: Log delivery failed %s" % (APP, str(e)))

    def about(self):
        try:
            with open("version.txt") as f:
                v = f.read()[:-1]
        except:
            v = "undefined"
        self.toast(text="KBGallery %s\nJuan Toledo" % v, short=False)
        return v

if __name__ == '__main__':
    Logger.debug("%s: End imports. %s KBGalleryApp().run()" % (
        APP, datetime.now()))
    KBGalleryApp().run()
