import datetime
import threading
import urwid

def convert_mpv_timestring(t_str):
    hours, minutes, seconds = list(map(int, t_str.split(':')))
    epoch = hours*3600 + minutes*60 + seconds
    cur_dt = datetime.datetime.fromtimestamp(epoch)
    return cur_dt.strftime('%Y-%m-%d %H:%M:%S')

class WatchTeleboyGUI:

    autoplay = True

    palette = [
        ('title', '', '', '', '#008,bold', '#fdf'),
        ('body', '', '', '', 'default', 'default'),
        ('focus', '', '', '', 'default', '#ddd'),
        ('focus_u', '', '', '', 'default,underline', '#ddd'),
        ('underline', '', '', '', 'default,underline', 'default'),
        ('button', '', '', '', 'default,bold', '#dff'),
        ('border', '', '', '', '#a4f', 'default')
    ]

    line_box_chars = {
        'tlcorner': '\N{Lower half block}',
        'trcorner': '\N{Lower half block}',
        'brcorner': '\N{Upper half block}',
        'blcorner': '\N{Upper half block}',
        'lline': '\N{Full block}',
        'rline': '\N{Full block}',
        'tline': '\N{Lower half block}',
        'bline': '\N{Upper half block}'
    }

    def __init__(self, wt_session, wt_player):
        # wt_session is expected to be an instance of WatchTeleboySession
        # wt_player is expected to be an instance of WatchTeleboyPlayer
        self.wt_session = wt_session
        self.wt_player = wt_player
        self.channels = self.wt_session.get_channels()
        self.video_representation = None
        self.audio_language = None

        # init some widgets
        self.div = urwid.Divider()
        self.pp_placeholder = urwid.WidgetPlaceholder(urwid.Text('----'))
        self.mpv_output_w = urwid.Text('')

        # main title
        title_bt = urwid.BigText(('title', "watchteleboy"), urwid.HalfBlock5x4Font())
        title_am = urwid.AttrMap(urwid.Padding(title_bt, width='clip', align='center'), 'title')
        title = urwid.Pile([self.div, title_am, self.div])

        # Box "Channel:" (left part)
        ch_sel_header = urwid.AttrMap(urwid.Padding(urwid.Text('Channel:'), width=('relative', 100)), 'title')
        ch_sel_group = []
        ch_sel_radios = [
            urwid.AttrMap(
                urwid.RadioButton(ch_sel_group, channel, state=False, on_state_change=self.switch_channel, user_data=channel),
                None, focus_map='focus')
            for channel in self.channels]
        ch_list = urwid.ListBox(urwid.SimpleFocusListWalker(ch_sel_radios))
        left_content = urwid.Pile([
            ('pack', ch_sel_header),
            ('pack', self.div),
            ch_list,
            ('pack', self.div)
        ])
        left = urwid.LineBox(left_content)

        # Settings and stuff (right part)
        # Box "Control:"
        ctrl_header = urwid.AttrMap(urwid.Padding(urwid.Text('Control:'), width=('relative', 100)), 'title')
        autoplay = urwid.AttrMap(urwid.CheckBox('Autoplay', state=self.autoplay, on_state_change=self.set_autoplay), '', focus_map='focus')
        self.play = urwid.Button('Play', on_press=self.start_playback)
        self.stop = urwid.Button('Stop', on_press=self.stop_playback)
        self.pp_placeholder.original_widget = self.play
        left_button = urwid.Padding(urwid.AttrMap(urwid.LineBox(self.pp_placeholder), 'button', focus_map='focus'), width=10)
        quit = urwid.Padding(urwid.AttrMap(urwid.LineBox(urwid.Button('Quit', on_press=self.quit_program)), 'button', focus_map='focus'), width=10, align='right')
        playstop_quit = urwid.Columns([left_button, quit])
        right1_pile = urwid.Pile([
            ('pack', ctrl_header),
            ('pack', self.div),
            ('pack', autoplay),
            ('pack', self.div),
            ('pack', playstop_quit),
            urwid.SolidFill(' ')
        ])
        right1_content = urwid.BoxAdapter(right1_pile, height=7)
        right1_box = urwid.LineBox(right1_content)

        # Box "Quality:"
        repr_header = urwid.AttrMap(urwid.Padding(urwid.Text('Quality:'), width=('relative', 100)), 'title')
        self.repr_radios = urwid.WidgetPlaceholder(urwid.ListBox(urwid.SimpleListWalker([])))
        right2_pile = urwid.Pile([
            ('pack', repr_header),
            ('pack', self.div),
            self.repr_radios
        ])
        right2_content = urwid.BoxAdapter(right2_pile, height=8)
        right2_box = urwid.LineBox(right2_content)

        # Box "Audio:"
        lang_header = urwid.AttrMap(urwid.Padding(urwid.Text('Audio:'), width=('relative', 100)), 'title')
        self.lang_radios = urwid.WidgetPlaceholder(urwid.ListBox(urwid.SimpleListWalker([])))
        right3_pile = urwid.Pile([
            ('pack', lang_header),
            ('pack', self.div),
            self.lang_radios
        ])
        right3_content = urwid.BoxAdapter(right3_pile, height=5)
        right3_box = urwid.LineBox(right3_content)

        # Box "Time:"
        time_header = urwid.AttrMap(urwid.Padding(urwid.Text('Time:'), width=('relative', 100)), 'title')
        time_sep = urwid.Text(':')
        time_hours = urwid.IntEdit(caption='', default=20)
        time_minutes = urwid.IntEdit(caption='', default=15)
        time_seconds = urwid.IntEdit(caption='', default=00)
        time = urwid.GridFlow([time_hours, time_sep, time_minutes, time_sep, time_seconds], 2, 0, 1, 'left')
        right4_pile = urwid.Pile([
            ('pack', time_header),
            ('pack', self.div),
            ('pack', time),
            urwid.SolidFill(' ')
        ])
        right4_content = urwid.BoxAdapter(right4_pile, height=3)
        right4_box = urwid.LineBox(right4_content)

        # Stitching boxes together
        right = urwid.Pile([
            ('pack', right1_box),
            ('pack', right2_box),
            ('pack', right3_box),
            ('pack', right4_box),
            urwid.LineBox(urwid.SolidFill(' '))
        ])

        # footer
        mpv_status = urwid.AttrMap(urwid.Padding(self.mpv_output_w, align='center', width=52), 'title')
        footer = urwid.Pile([self.div, mpv_status, self.div])

        # Overall Layout
        columns = urwid.Padding(urwid.Columns([left, right], dividechars=2), left=2, right=2)
        content = urwid.AttrMap(urwid.Frame(columns, header=title, footer=footer), 'body')
        lbc = urwid.LineBox(content, **self.line_box_chars)
        hlbc = urwid.AttrMap(urwid.Padding(lbc, left=1, right=1), 'border')
        self.loop = urwid.MainLoop(hlbc, palette=self.palette)
        self.loop.screen.set_terminal_properties(colors=256)

        # mpv output
        self.mpv_stdout = self.loop.watch_pipe(self._player_receive_output)

    def run(self):
        self.loop.run()

    def _player_wait(self, player):
        player.wait()
        self.pp_placeholder.original_widget = self.play
        try:
            self.loop.draw_screen()
        except AssertionError:
            pass

    def _player_receive_output(self, mpv_out):
        output = mpv_out[4:-1].decode('utf8')
        output_list = output.split(' ')
        try:
            output_list[1] = convert_mpv_timestring(output_list[1])
            output_list[3] = convert_mpv_timestring(output_list[3]).split(' ')[1]
        except (IndexError, ValueError):
            pass
        self.mpv_output_w.set_text(' '.join(output_list))

    def refresh_languages(self):
        langs = self.wt_player.get_audio_languages()
        if not self.audio_language:
            self.audio_language = langs[0]
        lang_group = []
        lang_radios = [urwid.AttrMap(
            urwid.RadioButton(lang_group, lang,
                state=(True if lang == self.audio_language else False),
                on_state_change=self.switch_language, user_data=lang),
            None, focus_map='focus')
            for lang in langs]
        self.lang_radios.original_widget = urwid.ListBox(urwid.SimpleListWalker(lang_radios))

    def refresh_representations(self):
        reprs = self.wt_player.get_video_representations()
        if not self.video_representation:
            self.video_representation = min(reprs.keys())
        repr_group = []
        repr_radios = [urwid.AttrMap(
            urwid.RadioButton(repr_group, f"{dict(reprs[rid])['width']}x{dict(reprs[rid])['height']}@{dict(reprs[rid])['frameRate']}Hz",
                state=(True if rid == self.video_representation else False),
                on_state_change=self.switch_representation, user_data=rid),
            None, focus_map='focus')
            for rid in reprs.keys()]
        self.repr_radios.original_widget = urwid.ListBox(urwid.SimpleListWalker(repr_radios))

    def switch_channel(self, button, state, channel):
        if state:
            self.channel, mpd_url = self.wt_session.get_stream_url(channel)
            self.wt_player.set_mpd_url(mpd_url, self.channel)
            self.refresh_representations()
            self.refresh_languages()
            if self.autoplay:
                self.start_playback(None)

    def switch_representation(self, button, state, r_id):
        if state:
            self.wt_player.set_video_representation(representation_id=r_id)
            self.video_representation = r_id

    def switch_language(self, button, state, lang):
        if state:
            self.wt_player.set_audio_language(lang=lang)
            self.audio_language = lang

    def set_autoplay(self, button, state):
        self.autoplay = state

    def start_playback(self, button):
        self.pp_placeholder.original_widget = self.stop
        self.wt_player.play(output_fd=self.mpv_stdout)
        # thread that waits for wt_player to stop
        waiter = threading.Thread(target=self._player_wait, args=(self.wt_player,))
        waiter.start()

    def stop_playback(self, button):
        self.pp_placeholder.original_widget = self.play
        self.wt_player.stop()

    def quit_program(self, button):
        self.wt_player.stop()
        raise urwid.ExitMainLoop()

