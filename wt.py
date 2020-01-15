import json
import pickle
import re
import requests
import sys
from xml.dom import minidom
from threading import Thread
import time
import os

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

    def get_stream_url(self, channel=None, station_id=None):
        try:
            self.channel_ids
        except AttributeError:
            self.__retrieve_channel_ids(selection='all')
        if station_id is None:
            station_id = self.channel_ids[channel]
        api_url = f'https://tv.api.teleboy.ch/users/{self.user_id}/stream/live/{station_id}'
        r = self.api.get(api_url)
        try:
            assert r.status_code == 200
        except AssertionError:
            print('failed to retrieve channel data')
            raise
        channel_data = json.loads(r.content.decode())
        return channel_data['data']['stream']['url']

    def list_channels(self):
        """
        print all available channels
        """
        try:
            self.channel_ids
        except AttributeError:
            self.__retrieve_channel_ids(selection='all')
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
            self.s.cookies['cinergy_auth']
            if self.cache_file:
                self.__dump_session()
            return True
        except KeyError:
            print('Login failed')
            return False

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

    def __retrieve_channel_ids(self, selection='all'):
        assert selection in ['all', 'custom']
        try:
            assert self.__set_api_env()
        except AssertionError:
            print('Setting environment failed...')
            raise
        if selection == 'all':
            api_channellist_url = 'https://tv.api.teleboy.ch/epg/broadcasts/now?expand=station&stream=true'
        elif selection == 'custom':
            api_channellist_url = f'https://tv.api.teleboy.ch/users/{self.user_id}/broadcasts/now?expand=station&stream=true'
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
        self.channel_ids['__selection__'] = selection
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

    def download_stream(self, outfile):
        max_tries = 5
        self._stop = False
        fd = os.open(outfile, os.O_WRONLY)
        try_count = max_tries
        while not self.initialize_outfile(fd):
            try_count = -1
            if try_count <= 0:
                os.close(fd)
                return False
        try_count = max_tries
        while not self._stop:
            try:
                assert self.append_media_segment(fd)
                self.bump_timestamp()
                try_count = max_tries
            except AssertionError:
                time.sleep(self.segment_duration/self.segment_timescale)
                try_count -= 1
                if try_count <= 0:
                    os.close(fd)
                    return False
        os.close(fd)
        return True

    def stop(self):
        self._stop = True

    def nb_download_stream(self, outfile):
        self.download_thread = Thread(target=self.download_stream, args=(outfile,))
        self.download_thread.start()

    def initialize_outfile(self, fd):
        bw_pattern = r'\$Bandwidth\$'
        bandwidth = dict(self.selected_representation)['bandwidth']
        stream_header_url = self.base_url + re.sub(bw_pattern, str(bandwidth), self.segment_header_template)
        r = requests.get(stream_header_url)
        os.write(fd, r.content)
        return r.ok

    def append_media_segment(self, fd):
        bw_pattern = r'\$Bandwidth\$'
        ts_pattern = r'\$Time\$'
        bandwidth = dict(self.selected_representation)['bandwidth']
        time = self.segment_current_timestamp
        stream_segment_url = self.base_url + re.sub(bw_pattern, str(bandwidth), self.segment_media_template)
        stream_segment_url = re.sub(ts_pattern, str(time), stream_segment_url)
        r = requests.get(stream_segment_url)
        os.write(fd, r.content)
        return r.ok

class WatchTeleboyStreamContainer:
    """
    This class parses an MPD file from given URL (supposedly from a Teleboy streaming server)
    and extracts the necessary information to create individual streams for
    video, audio, and text. It creates the Handler classes that perform the actual download.
    """

    def __init__(self, url):
        self.base_url = '/'.join(url.split('/')[:-1]) + '/'
        self.data = requests.get(url).content
        self.root = minidom.parseString(self.data)
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

