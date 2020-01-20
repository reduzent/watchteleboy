import datetime

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
        now = datetime.datetime.now()
        today = now.date()
        delta_past_midnight = now - datetime.datetime.combine(today, datetime.time(0, 0))
        if delta_past_midnight.seconds < (extend_old_day_hours * 60 * 60):
            delta_start_now =  datetime.datetime.combine(today, start) - now
            if delta_start_now.seconds > ((24 - extend_old_day_hours) * 60 * 60):
                return today - datetime.timedelta(days=1)
        return today

    def evaluate_time(tstr):
        try:
            return datetime.time(*list(map(int, tstr.split(':'))))
        except ValueError:
            print('Cannot parse given time: ' + tstr)
            raise

    def evaluate_date(dstr):
        try:
            if dstr == 'tomorrow':
                return datetime.date.today() + datetime.timedelta(days=1)
            elif dstr == 'yesterday':
                return datetime.date.today() + datetime.timedelta(days=-1)
            else:
                return datetime.date(*list(map(int, dstr.split('-'))))
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

