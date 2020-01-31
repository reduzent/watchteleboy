import json
import os
import pickle
import re
import requests
import subprocess
import sys
import threading
from time import sleep
from xml.dom import minidom
from wt_helpers import *

##################################################################################
# SOME CLASSES
##################################################################################

class WatchTeleboyError(BaseException):
    pass

class WatchTeleboySession:

    user_agent = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:71.0) Gecko/20100101 Firefox/71.0'
    login_url = 'https://www.teleboy.ch/login_check'
    userenv_url = 'https://www.teleboy.ch/live'
    headers = {
        'User-Agent': user_agent
    }
    api_key = '6ca99ddb3e659e57bbb9b1874055a711b254425815905abaacf262b64f02eb3d'

    def __init__(self, cachefile=None):
        self.cache_file = cachefile
        try:
            assert self.cache_file is not None
            self.__restore_session()
        except (AssertionError, FileNotFoundError):
            # create new session
            self.s = requests.Session()
            self.s.headers.update(self.headers)
        self.channel_selection = 'all'

    def get_stream_url(self, channel=None, station_id=None):
        try:
            self.channel_ids
        except AttributeError:
            self.__retrieve_channel_ids()
        if station_id is None:
            for ch in self.channel_ids.keys():
                if ch.lower() == channel.lower():
                    channel = ch
                    break
            else:
                print(f'No such channel: {channel}')
                return None
            station_id = self.channel_ids[channel]
        api_url = f'https://tv.api.teleboy.ch/users/{self.user_id}/stream/live/{station_id}'
        r = self.api.get(api_url)
        try:
            assert r.status_code == 200
        except AssertionError:
            print('failed to retrieve channel data')
            raise
        channel_data = json.loads(r.content.decode())
        return (channel, channel_data['data']['stream']['url'])

    def list_channels(self):
        """
        print all available channels
        """
        try:
            self.channel_ids
        except AttributeError:
            self.__retrieve_channel_ids()
        for ch in self.channel_ids:
            if ch[0:2] != '__':
                print(ch)

    def login(self, user=None, password=None):
        """
        log in to www.teleboy.ch
        """
        try:
            assert user is not None and password is not None
        except AssertionError:
            print("Please provide both user and password")
            return False
        data = {
            'login': user,
            'password': password,
            'keep_login': '1'
            }
        r = self.s.post(self.login_url, data=data)
        try:
            assert r.status_code != 429
        except AssertionError:
            print("Your login is blocked. Please login via browser and answer captcha.")
            print("Visit https://www.teleboy.ch/ and try again.")
            return False
        try:
            self.s.cookies['cinergy_auth']
        except KeyError:
            print('Login failed')
            return False
        else:
            if self.cache_file:
                self.__dump_session()
            return True

    def logged_in(self):
        """
        return True when session is authenticated, False if not
        """
        try:
            self.s.cookies.clear_expired_cookies()
            self.s.cookies['cinergy_auth']
            return True
        except KeyError:
            return False

    def set_channel_selection(self, channel_selection):
        try:
            assert channel_selection in ['all', 'custom']
        except AssertionError:
            print(f'Invalid channel_selection: {channel_selection}')
            print('Falling back to default')
        else:
            self.channel_selection = channel_selection

    def __retrieve_channel_ids(self):
        try:
            assert self.__set_api_env()
        except AssertionError:
            print('Setting environment failed...')
            raise
        if self.channel_selection == 'custom':
            api_channellist_url = f'https://tv.api.teleboy.ch/users/{self.user_id}/broadcasts/now?expand=station&stream=true'
        else:
            api_channellist_url = 'https://tv.api.teleboy.ch/epg/broadcasts/now?expand=station&stream=true'
        self.api = requests.Session()
        headers = {
            'x-teleboy-apikey': self.api_key,
            'x-teleboy-session': self.session_id
        }
        self.api.headers.update(headers)
        self.api.headers.update(self.headers)
        r = self.api.get(api_channellist_url)
        try:
            assert r.status_code == 200
        except AssertionError:
            print('failed to retrieve channel ids')
            return False
        channels = json.loads(r.content.decode())
        self.channel_ids = {channel['station_label']: channel['station_id'] for channel in channels['data']['items']}
        self.channel_ids['__selection__'] = self.channel_selection
        return True

    def __restore_session(self):
        with open(self.cache_file, 'rb') as fd:
            self.s = pickle.load(fd)
        assert isinstance(self.s, requests.sessions.Session)
        assert self.logged_in()

    def __dump_session(self):
        with open(self.cache_file, 'wb') as fd:
            pickle.dump(self.s, fd)

    def __set_api_env(self):
        try:
            assert self.logged_in()
            r = self.s.get(self.userenv_url)
            assert r.status_code == 200
            c = r.content.decode()
            uid_raw = re.findall(r'\s+\.setId\(\d+\)', c, re.MULTILINE)[0]
            self.user_id = uid_raw[uid_raw.find('(')+1:uid_raw.find(')')]
            self.session_id = self.s.cookies['cinergy_s']
            return True
        except AssertionError:
            return False

class WatchTeleboyStreamHandler:
    """
    Parses the given AdaptationSet, selects a representation, and downloads a single
    media stream onto local disk in a non-blocking way.
    """

    def __init__(self, adaptationset, base_url):
        self.adaptationset = adaptationset
        self.base_url = base_url
        assert isinstance(self.adaptationset, minidom.Element)
        self.content_type = self.adaptationset.attributes.get('contentType').value
        self.id = self.adaptationset.attributes.get('id').value
        try:
            self.language = self.adaptationset.attributes.get('lang').value
        except AttributeError:
            self.language = None
        self.representation_elements = self.adaptationset.getElementsByTagName('Representation')
        self.segment_template = self.adaptationset.getElementsByTagName('SegmentTemplate')[0]
        self.segment_timeline = self.segment_template.getElementsByTagName('SegmentTimeline')[0]
        self.segment_timeline_s = self.segment_timeline.getElementsByTagName('S')[0]
        self.segment_start_timestamp = int(self.segment_timeline_s.attributes.get('t').value)
        self.segment_current_timestamp = self.segment_start_timestamp
        self.segment_last_timestamp = sys.maxsize
        self.segment_duration = int(self.segment_timeline_s.attributes.get('d').value)
        self.segment_timescale = int(self.segment_template.attributes.get('timescale').value)
        self.segment_header_template = self.segment_template.attributes.get('initialization').value
        self.segment_media_template = self.segment_template.attributes.get('media').value
        self.representations = self.parse_representations()
        self.select_representation()

    def parse_representations(self):
        representations = {}
        for representation in self.representation_elements:
            repr_id = int(representation.attributes.get('id').value)
            attributes = representation.attributes.items()
            representations[repr_id] = attributes
        return representations

    def select_representation(self, representation_id=None):
        if representation_id is None:
            representation_id = min(dict(self.representations).keys())
        self.selected_representation = self.representations[representation_id]
        return self.selected_representation

    def bump_timestamp(self):
        self.segment_current_timestamp += self.segment_duration
        return self.segment_current_timestamp

    def _download_thread(self, outfile):
        max_tries = 5
        fd = os.open(outfile, os.O_WRONLY | os.O_CREAT)
        try_count = max_tries
        while not self.initialize_outfile(fd):
            try_count = -1
            if try_count <= 0:
                os.close(fd)
                return False
        try_count = max_tries
        while not self.download_stop_event.is_set():
            if self.segment_current_timestamp >= self.segment_last_timestamp:
                break
            try:
                r = self.append_media_segment(fd)
                assert r.status_code == 200
                self.bump_timestamp()
                try_count = max_tries
            except AssertionError:
                if not self.download_stop_event.wait(timeout=self.segment_duration/self.segment_timescale):
                    try_count -= 1
                    if try_count <= 0:
                        os.close(fd)
                        return False
        os.close(fd)
        return True

    def stop(self):
        self.download_stop_event.set()

    def set_start_time(self, st_obj):
        # st_obj is expected to be a datetime.datetime object
        start_time = st_obj.timestamp() * self.segment_timescale
        start_time = start_time - (start_time % self.segment_duration) # quantize to segment duration
        if start_time > self.segment_start_timestamp:
            print('Cannot watch content from the future')
            raise WatchTeleboyError()
        self.segment_current_timestamp = start_time

    def set_stop_time(self, st_obj):
        # st_obj is expected to be a datetime.datetime object
        stop_time = st_obj.timestamp() * self.segment_timescale
        stop_time = stop_time - (stop_time % self.segment_duration) # quantize to segment duration
        if stop_time <= self.segment_current_timestamp:
            print('--endtime must be after --starttime')
            raise WatchTeleboyError()
        self.segment_last_timestamp = stop_time

    def start_download(self, outfile, stop_event):
        self.download_stop_event = stop_event
        self.download_thread = threading.Thread(target=self._download_thread, args=(outfile,))
        self.download_thread.start()

    def initialize_outfile(self, fd):
        bw_pattern = r'\$Bandwidth\$'
        bandwidth = dict(self.selected_representation)['bandwidth']
        stream_header_url = self.base_url + re.sub(bw_pattern, str(bandwidth), self.segment_header_template)
        r = requests.get(stream_header_url)
        try:
            os.write(fd, r.content)
        except BrokenPipeError:
            self.stop()
        return r.ok

    def append_media_segment(self, fd):
        bw_pattern = r'\$Bandwidth\$'
        ts_pattern = r'\$Time\$'
        bandwidth = dict(self.selected_representation)['bandwidth']
        time = self.segment_current_timestamp
        segment_url = self.base_url + re.sub(bw_pattern, str(bandwidth), self.segment_media_template)
        segment_url = re.sub(ts_pattern, str(time), segment_url)
        r = requests.get(segment_url)
        if r.status_code == 404 and self.segment_current_timestamp < self.segment_start_timestamp:
            print("Segment not available. Maybe too old?")
            self.stop() # 404 on segment from the past means caches on server expired
        try:
            os.write(fd, r.content)
        except BrokenPipeError:
            self.stop() # this happens only when mpv stopped reading from fifo
        return r

    def wait(self):
        self.download_thread.join()

class WatchTeleboyStreamContainer:
    """
    This class parses an MPD file from given URL (supposedly from a Teleboy streaming server)
    and extracts the necessary information to create individual streams for
    video, audio, and text. It creates the Handler classes that perform the actual download.
    """

    def __init__(self, url):
        self.base_url = '/'.join(url.split('/')[:-1]) + '/'
        r = requests.get(url)
        try:
            assert r.status_code == 200
        except AssertionError:
            print('Failed to download manifest')
            raise WatchTeleboyError()
        try:
            self.root = minidom.parseString(r.content)
        except xml.parsers.expat.ExpatError:
            print('Failed to parse manifest')
            raise WatchTeleboyError()
        self.mpd_element = self.root.getElementsByTagName('MPD')[0]
        self.period_element = self.mpd_element.getElementsByTagName('Period')[0]
        self.adaptationset_elements = self.period_element.getElementsByTagName('AdaptationSet')

    def extract_stream(self, content, lang=None):
        for adaptationset in self.adaptationset_elements:
            if lang is None:
                if adaptationset.attributes.get('contentType').value == content:
                    return WatchTeleboyStreamHandler(adaptationset, self.base_url)
            else:
                if adaptationset.attributes.get('contentType').value == content and \
                    adaptationset.attributes.get('lang').value == lang:
                    return WatchTeleboyStreamHandler(adaptationset, self.base_url)
        return None

    def extract_video_stream(self):
        return self.extract_stream('video')

    def extract_audio_stream(self, lang=None):
        return self.extract_stream('audio', lang)

    def extract_subtitle_stream(self, lang=None):
        return self.extract_stream('text', lang)

    def list_audio_languages(self):
        languages = []
        for adaptationset in self.adaptationset_elements:
            if adaptationset.attributes.get('contentType').value == 'audio':
                languages.append(adaptationset.attributes.get('lang').value)
        return languages

class WatchTeleboyPlayer:
    """
    Player for MPD URLs. Controls stream download and playback with mpv.
    """
    def __init__(self, env):
        self.env = env
        self.stop_event = threading.Event()

    def set_mpd_url(self, mpd_url, channel=None):
        self.stop_event.clear()
        self.manifest = WatchTeleboyStreamContainer(mpd_url)
        self.channel = channel if not None else '-' # channel is used in Window Title
        self.audio = self.manifest.extract_audio_stream()
        self.video = self.manifest.extract_video_stream()
        if self.env['starttime'] is not None:
            stobj = parse_time_string(self.env['starttime'])
            self.audio.set_start_time(stobj)
            self.video.set_start_time(stobj)
        if self.env['endtime'] is not None:
            etobj = parse_time_string(self.env['endtime'])
            self.audio.set_stop_time(etobj)
            self.video.set_stop_time(etobj)

    def play(self):
        player = threading.Thread(target=self._player_thread)
        player.start()

    def _player_thread(self):
        audio_fifo = self.env['fifo'].format(content_type=self.audio.content_type, id=self.audio.id)
        video_fifo = self.env['fifo'].format(content_type=self.video.content_type, id=self.video.id)
        os.mkfifo(audio_fifo)
        os.mkfifo(video_fifo)
        self.audio.start_download(audio_fifo, self.stop_event)
        self.video.start_download(video_fifo, self.stop_event)
        try:
            self._run_player(audio_file=audio_fifo, video_file=video_fifo)
        except KeyboardInterrupt:
            self.stop_event.set()
        os.unlink(audio_fifo)
        os.unlink(video_fifo)

    def record(self):
        recorder = threading.Thread(target=self._recorder_thread)
        recorder.start()

    def _recorder_thread(self):
        if not self.env['showname']:
            showname = f'{self.channel}-{datetime.now().strftime("%Y%m%d%H%M%S")}'
        else:
            showname = self.env['showname']
        rec_dir = self.env['path'] or self.env['record_dir']
        audio_file = f'{rec_dir}/{showname}.m4a'
        video_file = f'{rec_dir}/{showname}.mp4'
        self.audio.start_download(audio_file, self.stop_event)
        self.video.start_download(video_file, self.stop_event)
        try:
            self.audio.wait()
            self.video.wait()
        except KeyboardInterrupt:
            pass
        self.stop_event.set()

    def _run_player(self, audio_file=None, video_file=None):
        mpv_command = [
            self.env['mpv'],
            *self.env['mpv_args'],
            f'--title={self.channel}',
            f'--audio-file={audio_file}',
            video_file
        ]
        mpv = subprocess.Popen(mpv_command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        while mpv.poll() is None:
            if self.stop_event.wait(timeout=0.1):
                mpv.terminate()
                break
            sleep(0.1)
        self.stop_event.set()

    def stop(self):
        self.stop_event.set()

    def wait(self, timeout=None):
        self.stop_event.wait(timeout=timeout)

