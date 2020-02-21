import datetime
import os
import threading
import urwid

def convert_mpv_timestring(t_str):
    hours, minutes, seconds = list(map(int, t_str.split(':')))
    epoch = hours*3600 + minutes*60 + seconds
    cur_dt = datetime.datetime.fromtimestamp(epoch)
    return cur_dt.strftime('%Y-%m-%d %H:%M:%S')

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
        quit_btn = urwid.Button('Quit')
        urwid.connect_signal(quit_btn, 'click', self.exit_program)
        quit = urwid.Pile([urwid.Divider(), urwid.Padding(
            urwid.AttrMap(quit_btn, 'title'), align='center', width=8)])
        body = []
        for channel in channels:
            button = urwid.RadioButton(body, channel, on_state_change=self.now_playing, user_data=channel)
        chanlist = urwid.ListBox(urwid.SimpleListWalker(body))
        self.channel_selection_w = urwid.Columns([
            urwid.Frame(chanlist, header=title, footer=quit),
            urwid.SolidFill('+')
        ], dividechars=2)

        # mpv output widget
        self.mpv_output_w = urwid.Text('')
        background = urwid.Frame(urwid.SolidFill(' '), footer=urwid.Padding(self.mpv_output_w, align='center', width=52))

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

    def now_playing(self, button, state, channel):
        if state:
            ch, mpd_url = self.wt_session.get_stream_url(channel)
            self.wt_player.set_mpd_url(mpd_url, ch)
            self.wt_player.play(output_fd=self.mpv_stdout)
            response = urwid.Text(('title', ['Now playing ', ch, '\n']))
            representation_radio = []
            stop = urwid.Button(u'Stop')
            urwid.connect_signal(stop, 'click', self.stop_playing)
            pile = urwid.Pile([
                    urwid.Divider(),
                    response,
                    urwid.Divider(),
                    urwid.AttrMap(stop, None, focus_map='reversed'),
            ])
            now_playing_w = urwid.Filler(pile, valign='top')
            self.switch_widget(button, now_playing_w)
            # thread that waits for wt_player to stop
            waiter = threading.Thread(target=self._player_wait, args=(self.wt_player,))
            waiter.start()

    def stop_playing(self, button):
        self.wt_player.stop()
        self.switch_widget(button, self.channel_selection_w)

    def _player_wait(self, player):
        player.wait()
        self.switch_widget(None, self.channel_selection_w)
        self.loop.draw_screen()

    def _player_receive_output(self, mpv_out):
        output = mpv_out[4:-1].decode('utf8')
        output_list = output.split(' ')
        try:
            output_list[1] = convert_mpv_timestring(output_list[1])
            output_list[3] = convert_mpv_timestring(output_list[3]).split(' ')[1]
        except (IndexError, ValueError):
            pass
        self.mpv_output_w.set_text(' '.join(output_list))

    def exit_program(self, button):
        raise urwid.ExitMainLoop()
