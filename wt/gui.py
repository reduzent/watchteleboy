import urwid
import threading
import os

class WatchTeleboyGUI:

    palette = [
        ('outer', '', '', '', '#fdf', '#408'),
        ('border', '', '', '', '#80f', '#fdf'),
        ('inner', '', '', '', '#006', '#fdf'),
        ('title', '', '', '', '#006,bold', '#fdf'),
        ('reversed', '', '', '', '#fdf', '#006')
    ]

    line_box_chars = {
        'tlcorner': '\N{Full block}',
        'trcorner': '\N{Full block}',
        'brcorner': '\N{Full block}',
        'blcorner': '\N{Full block}',
        'lline': '\N{Full block}',
        'rline': '\N{Full block}',
        'tline': '\N{Upper half block}',
        'bline': '\N{Lower half block}'
    }

    def __init__(self, wt_session, wt_player):
        # wt_session is expected to be an instance of WatchTeleboySession
        # wt_player is expected to be an instance of WatchTeleboyPlayer
        self.wt_session = wt_session
        self.wt_player = wt_player
        channels = self.wt_session.get_channels()

        # channel selection
        div = urwid.Divider()
        title = urwid.Pile([div, urwid.Text(('title', 'Select a channel:')), div])
        quit = urwid.Button('Quit')
        urwid.connect_signal(quit, 'click', self.exit_program)
        footer = urwid.Pile([urwid.Divider(), urwid.Padding(
            urwid.AttrMap(quit, 'title'), align='center', width=8)])
        body = []
        for channel in channels:
            button = urwid.Button(channel)
            urwid.connect_signal(button, 'click', self.now_playing, channel)
            body.append(urwid.AttrMap(button, None, focus_map='reversed'))
        chanlist = urwid.ListBox(urwid.SimpleListWalker(body))
        self.channel_selection_w = urwid.Frame(chanlist, header=title, footer=footer)

        # mpv output widget
        self.mpv_output_w = urwid.Text('')
        background = urwid.Frame(urwid.SolidFill(' '), footer=urwid.Padding(self.mpv_output_w, align='center', width=50))

        # embed main widget (initially channel_selection_w)
        self.container = urwid.Padding(self.channel_selection_w, left=1, right=1)
        guts = urwid.AttrMap(self.container, 'inner')
        linebox = urwid.LineBox(guts, title='WatchTeleboy', **self.line_box_chars)
        frame = urwid.AttrMap(linebox, 'border')
        main = urwid.Overlay(frame, urwid.AttrMap(background, 'outer'),
                align=('relative', 50), width=('relative', 50),
                valign='middle', height=('relative', 80))
        self.loop = urwid.MainLoop(main,self.palette)
        self.loop.screen.set_terminal_properties(colors=256)

        # mpv output
        self.mpv_stdout = self.loop.watch_pipe(self._player_receive_output)

    def run(self):
        self.loop.run()

    def switch_widget(self, button, widget):
        self.container.original_widget = widget

    def now_playing(self, button, channel):
        ch, mpd_url = self.wt_session.get_stream_url(channel)
        self.wt_player.set_mpd_url(mpd_url, ch)
        self.wt_player.play(output_fd=self.mpv_stdout)
        response = urwid.Text(('title', ['Now playing ', ch, '\n']))
        stop = urwid.Button(u'Stop')
        urwid.connect_signal(stop, 'click', self.stop_playing)
        pile = urwid.Pile([urwid.Divider(), response,
            urwid.AttrMap(stop, None, focus_map='reversed')])
        now_playing_w = urwid.Filler(pile, valign='top')
        self.switch_widget(button, now_playing_w)
        # thread that waits for wt_player to stop
        waiter = threading.Thread(target=self._player_wait, args=(self.wt_player,))
        waiter.start()

    def stop_playing(self, button):
        self.wt_player.stop()
        try:
            os.close(self.mpv_stdout)
        except OSError:
            pass
        self.switch_widget(button, self.channel_selection_w)

    def _player_wait(self, player):
        player.wait()
        #os.close(self.mpv_stdout)
        self.switch_widget(None, self.channel_selection_w)
        self.loop.draw_screen()

    def _player_receive_output(self, mpv_out):
        self.mpv_output_w.set_text( mpv_out[4:-1].decode('utf8'))

    def exit_program(self, button):
        raise urwid.ExitMainLoop()
