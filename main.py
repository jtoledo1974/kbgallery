# -*- coding: utf-8 -*-
from datetime import datetime
from urllib import quote
from posixpath import join as urljoin

from kivy.app import App
from kivy.config import Config
from kivy.uix.image import AsyncImage
from kivy.uix.listview import ListView
from kivy.adapters.listadapter import ListAdapter
from kivy import platform
from kivy.logger import Logger
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.network.urlrequest import UrlRequest

if platform == 'android':
    Logger.debug('KBGALLERY: Importando %s' % datetime.now())
    import android
    from plyer.platforms.android import activity
    from jnius import autoclass, cast
    from android.runnable import run_on_ui_thread
    Intent = autoclass('android.content.Intent')
    String = autoclass('java.lang.String')

if platform == 'win' or platform == 'linux':
    Config.set('graphics', 'width', 480)
    Config.set('graphics', 'height', 756)

APP = 'KBGALLERY'


class RotImage(AsyncImage):
    angle = NumericProperty(0)
    orientation = NumericProperty(1)

    def on_orientation(self, widget, value):
        self.angle = {1: 0, 3: 180, 6: 270, 8: 90}[value]


class Dirlist(ListView):

    def __init__(self, root="", path="", **kwargs):

        self.root = root
        self.path = path

        def args_converter(row_index, rec):
            return {'dir1': rec[0]['direntry'],
                    'dir2': rec[1]['direntry'],
                    'thumb1': rec[0]['thumb_url'],
                    'thumb2': rec[1]['thumb_url'],
                    'orientation1': rec[0]['orientation'],
                    'orientation2': rec[1]['orientation']}

        self.adapter = adapter = ListAdapter(
            data=[],
            args_converter=args_converter,
            template='DirentryListRow',
            selection_mode='none'
            )

        super(ListView, self).__init__(adapter=adapter, **kwargs)

        UrlRequest(root+quote((path).encode('utf-8')),
                   on_success=self.got_dirlist, debug=True)

    def got_dirlist(self, req, res):
        Logger.debug("%s: got_dirlist (req %s, results %s" % (APP, req, res))

        turl = self.root + urljoin('thumb',
                                   quote(res['dir'].encode('utf-8')))
        ld = [{'direntry': de,
               'thumb_url': urljoin(turl, quote(de.encode('utf-8'))),
               'orientation': orientation}
              for (de, orientation) in res['listdir']]

        data = [(ld[i*2], ld[i*2+1]) for i in range(len(ld)/2)]
        self.adapter.data = self.adapter.data + data
        self._reset_spopulate()


class KBGalleryApp(App):

    def build(self):
        Logger.debug("%s: build %s " % (APP, datetime.now()))
        self.use_kivy_settings = False
        return self.root

    def build_config(self, config):
        Logger.debug("%s: build_config %s " % (APP, datetime.now()))
        config.setdefaults('general', {
            'server_url': 'http://localhost:8080/',
        })

    def build_settings(self, settings):
        Logger.debug("%s: build_settings %s " % (APP, datetime.now()))
        # settings.add_json_panel('Planilla', self.config, 'settings.json')

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
                if platform == 'android':
                    activity.moveTaskToBack(True)
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
        self.server_url = 'http://192.168.1.40:8888/'
        self.dirlist = dirlist = Dirlist(root=self.server_url)
        self.navigation = []
        self.root.add_widget(dirlist)

    def direntry_selected(self, direntry):
        Logger.debug("%s: on_direntry_selected %s" % (APP, direntry))

        # TODO Cancelar los requests anteriores si posible
        # El servidor se puede quedar pillado haciendo thumbnails
        # antes de responder al cambio de directorio

        self.root.remove_widget(self.dirlist)
        self.navigation.append(self.dirlist)
        self.dirlist = Dirlist(root=self.server_url,
                               path=self.dirlist.path+direntry+'/')
        self.root.add_widget(self.dirlist)
        self.root.with_previous = True

    def load_previous(self):
        self.root.remove_widget(self.dirlist)
        previous = self.navigation.pop(-1)
        self.root.add_widget(previous)
        self.dirlist = previous
        if not len(self.navigation):
            self.root.with_previous = False

    def on_stop(self):
        pass

    def on_config_change(self, config, section, key, value):
        Logger.debug("%s: on_config_change key %s %s" % (
            APP, key, value))

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
