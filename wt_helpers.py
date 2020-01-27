import configparser
from datetime import date, datetime, time, timedelta
import os
import random
import sys

config_template = """[watchteleboy]
# watchteleboy configuration

# Teleboy Login Credentials
teleboy_user = {teleboy_user}
teleboy_pass = {teleboy_pass}

# Teleboy users may customize the channel selection and the channel
# ordering. You may chose whether you want watchteleboy to display
# all available channels (in default order) or use a customized
# channel list in user-defined order. You may visit
# http://www.teleboy.ch/en/sender to customize your personal
# channel selection. Allowed values: 'all', 'customized'
channel_selection = {channel_selection}

# Additional flags passed to mpv
mpv_opts = {mpv_opts}

# This can be overridden by the -p/--path flag:
record_dir = {record_dir}

# Several variants of a stream are available. The
# variants come with different bitrates and different video
# resolutions.
# Bitrate:    |   Resolution
# ------------+--------------
#   250000    |   400x224/12.5fps
#   452000    |   512x288/25fps
#   700000    |   512x288/25fps
#  1300000    |   768x432/25fps
#  2800000    |   1280x720/25fps
#  4800000    |   1280x720/50fps
# Per default watchteleboy automatically selects the variant
# with the highest quality. When max_bitrate is set, the variant
# that still fits the constraint is selected.
max_bitrate = {max_bitrate}
"""

##################################################################################
# SOME HELPER FUNCTIONS
##################################################################################

def parse_time_string(rawstring):
    """
    Returns a datetime object from a string containing time. It does some magic
    to guess the datepart (if not specified). It understands 'yesterday' and
    'tomorrow' as dates.
    Format: [YYYY-MM-DD ]HH:MM[:ss]
    """
    def guess_date(start):
        # if midnight is not long ago, assume evening times to be
        # from yesterday
        extend_old_day_hours = 4
        now = datetime.now()
        today = now.date()
        dt1 = datetime.combine(today, time(0, 0)) + timedelta(hours=extend_old_day_hours)
        dt2 = datetime.combine(today, time(0, 0)) - timedelta(hours=extend_old_day_hours)
        past_midnight = dt1.time()
        before_midnight = dt2.time()
        if now.time() < past_midnight and start.time() > before_midnight:
            return today - timedelta(days=1)
        return today

    def evaluate_time(tstr):
        try:
            return time(*list(map(int, tstr.split(':'))))
        except ValueError:
            print('Cannot parse given time: ' + tstr)
            raise

    def evaluate_date(dstr):
        try:
            if dstr == 'tomorrow':
                return date.today() + timedelta(days=1)
            elif dstr == 'yesterday':
                return date.today() + timedelta(days=-1)
            else:
                return date(*list(map(int, dstr.split('-'))))
        except ValueError:
            print('Cannot parse given date: '  + dstr)
            raise

    dtstr = rawstring.split(' ')
    if len(dtstr) == 1:
        timepart = evaluate_time(dtstr[0])
        datepart = guess_date(timepart)
    elif len(dtstr) == 2:
        datepart = evaluate_date(dtstr[0])
        timepart = evaluate_time(dtstr[1])
    else:
        print('Cannot parse given time: ' + tstr)
        raise ValueError
    return datetime.datetime.combine(datepart, timepart)

def create_env(defaults):
    home_dir = os.path.expanduser('~')
    defaults['wt_dir'] = defaults['wt_dir'].format(home_dir=home_dir)
    defaults['record_dir'] = defaults['record_dir'].format(wt_dir=defaults['wt_dir'])
    defaults['configfile'] = defaults['configfile'].format(wt_dir=defaults['wt_dir'])
    defaults['session_cache'] = defaults['session_cache'].format(wt_dir=defaults['wt_dir'])
    defaults['wt_instance'] = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for i in range(8))
    defaults['fifo'] = defaults['fifo'].format(wt_dir=defaults['wt_dir'],
        wt_instance=defaults['wt_instance'], content_type='{content_type}', id='{id}')
    try:
        os.mkdir(defaults['wt_dir'])
    except FileExistsError:
        pass
    try:
        env = read_config(defaults)
    except KeyError:
        create_config(defaults)
        env = read_config(defaults)
    return {**defaults, **env}

def create_config(defaults):
    from wt_classes import WatchTeleboySession
    wts = WatchTeleboySession(defaults['session_cache'])
    while not wts.logged_in():
        try:
            user = input("Please enter your teleboy username: ")
            password = input("Please enter your teleboy password: ")
        except KeyboardInterrupt:
            sys.exit()
        wts.login(user=user, password=password)
    consent = input("Password is written in plain text to config. OK? [y/n] ")
    if consent == 'n':
        sys.exit()
    config_content = config_template.format(
        teleboy_user=user,
        teleboy_pass=password,
        mpv_opts=defaults['mpv_opts'],
        record_dir=defaults['record_dir'],
        channel_selection=defaults['channel_selection'],
        max_bitrate=defaults['max_bitrate'])
    with open(defaults['configfile'], 'w') as configfile:
        configfile.write(config_content)

def read_config(defaults):
    config = configparser.ConfigParser()
    config.read(defaults['configfile'])
    return config['watchteleboy']
