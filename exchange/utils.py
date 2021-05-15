from datetime import timedelta


def get_intervals(interval):
    int_dict = {a: [int(a.rstrip(a[-1])), a[-1]] for a in interval}
    ms_dict = {}
    for key in int_dict:
        digit, time = int_dict[key]
        if time == 'm':
            ms_time = timedelta(minutes=digit).total_seconds() * 1000
        if time == 'h':
            ms_time = timedelta(hours=digit).total_seconds() * 1000
        if time == 'd':
            ms_time = timedelta(days=digit).total_seconds() * 1000
        if time == 'w':
            ms_time = timedelta(weeks=digit).total_seconds() * 1000
        if time == 'M':
            ms_time = timedelta(days=digit*30).total_seconds() * 1000
        ms_dict.update({key: ms_time})
    return ms_dict
