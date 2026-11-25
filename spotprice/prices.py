"""
Price data parsing and time helpers for SpotPrice Display.

The device clock runs in UTC (set via NTP). All timestamps here are Unix
epoch seconds in UTC; local (Finnish) time is only used for display labels.
"""

import time

SLOT_SECONDS = 15 * 60


def _days_from_civil(y, m, d):
    """Days since 1970-01-01 for a proleptic Gregorian date (timezone-free)."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def parse_iso_timestamp(timestamp):
    """Parse an ISO 8601 UTC timestamp (e.g. 2025-01-01T12:00:00.000Z) to epoch seconds.

    Computed directly instead of via time.mktime(), which interprets the
    struct as *local* time and gives different answers on a dev machine.
    Returns 0 on malformed input.
    """
    try:
        days = _days_from_civil(
            int(timestamp[0:4]), int(timestamp[5:7]), int(timestamp[8:10])
        )
        return (
            days * 86400
            + int(timestamp[11:13]) * 3600
            + int(timestamp[14:16]) * 60
            + int(timestamp[17:19])
        )
    except (ValueError, TypeError, IndexError):
        return 0


_MONTHS = "JanFebMarAprMayJunJulAugSepOctNovDec"


def parse_http_date(value):
    """Parse an HTTP Date header ("Wed, 25 Nov 2026 19:03:00 GMT") to epoch.

    Fallback clock source when NTP (UDP 123) is blocked. Returns 0 if invalid.
    """
    try:
        _, day, mon, year, hms = value.split()[:5]
        i = _MONTHS.index(mon)
        if len(mon) != 3 or i % 3:  # reject substrings like "anF"
            return 0
        month = i // 3 + 1
        h, m, s = hms.split(":")
        return (
            _days_from_civil(int(year), month, int(day)) * 86400
            + int(h) * 3600
            + int(m) * 60
            + int(s)
        )
    except (ValueError, AttributeError, TypeError):
        return 0


def parse_prices(entries):
    """Convert raw API entries into a sorted list of (start, end, price) tuples.

    Done once per fetch so the ISO strings can be freed and we don't re-parse
    ~200 timestamps on every display refresh.
    """
    slots = []
    for entry in entries:
        start = parse_iso_timestamp(entry["startDate"])
        end_text = entry["endDate"]
        end = parse_iso_timestamp(end_text)
        # The API gives inclusive ends like 12:14:59.999Z; make them exclusive
        # (12:15:00) so the last second of each slot still has a price.
        if end_text[19:23] == ".999":
            end += 1
        if start and end:
            slots.append((start, end, entry["price"]))
    slots.sort()
    return slots


def _current_index(slots, now):
    for i, (start, end, _) in enumerate(slots):
        if start <= now < end:
            return i
    return None


def find_current_price(slots, now=None):
    """Return the price for the slot containing `now`, or None."""
    if now is None:
        now = time.time()
    idx = _current_index(slots, now)
    return None if idx is None else slots[idx][2]


def current_slot_start(slots, now=None):
    """Return the start timestamp of the current slot, or None."""
    if now is None:
        now = time.time()
    idx = _current_index(slots, now)
    return None if idx is None else slots[idx][0]


def future_coverage(slots, now=None):
    """Seconds of price data remaining after `now` (0 if none)."""
    if now is None:
        now = time.time()
    if not slots:
        return 0
    return max(0, slots[-1][1] - now)


def get_upcoming_prices(slots, count=24, now=None):
    """Return prices for the next `count` slots, starting with the current one."""
    if now is None:
        now = time.time()
    return [price for _, end, price in slots if end > now][:count]


def get_prices_with_history(slots, future_slots=24, past_slots=4, now=None):
    """
    Get prices around the current slot for graphing.

    Args:
        slots: Sorted (start, end, price) tuples from parse_prices()
        future_slots: Number of slots to include from the current one onward
        past_slots: Number of slots to include before the current one
        now: Override current time (for testing)

    Returns:
        tuple: (price_list, now_index, first_start) where now_index is the
        position of the current slot in price_list and first_start is the
        start timestamp of price_list[0]. Returns ([], 0, 0) if the current
        time isn't covered by the data.
    """
    if now is None:
        now = time.time()
    current_idx = _current_index(slots, now)
    if current_idx is None:
        return [], 0, 0

    start_idx = max(0, current_idx - past_slots)
    end_idx = min(len(slots), current_idx + future_slots)

    result = [price for _, _, price in slots[start_idx:end_idx]]
    return result, current_idx - start_idx, slots[start_idx][0]


# --- Finnish local time (EET/EEST) -----------------------------------------


def _last_sunday_utc(year, month):
    """Epoch seconds of 01:00 UTC on the last Sunday of the given month (EU DST switch)."""
    # Last day of month: day 0 of next month
    if month == 12:
        last = _days_from_civil(year + 1, 1, 1) - 1
    else:
        last = _days_from_civil(year, month + 1, 1) - 1
    # 1970-01-01 was a Thursday; weekday with Monday=0 is (days + 3) % 7
    weekday = (last + 3) % 7
    last_sunday = last - ((weekday - 6) % 7)
    return last_sunday * 86400 + 3600


def utc_offset(ts, std_offset=2 * 3600):
    """UTC offset in seconds for Finland (EET, +1h EU summer time)."""
    year = time.localtime(ts).tm_year
    if _last_sunday_utc(year, 3) <= ts < _last_sunday_utc(year, 10):
        return std_offset + 3600
    return std_offset


def local_time(ts):
    """struct_time for `ts` in Finnish local time."""
    return time.localtime(ts + utc_offset(ts))


def _local_day_start(ts):
    """Finnish local midnight of the day containing `ts`, as 'local epoch'."""
    local = ts + utc_offset(ts)
    return local - local % 86400


def _local_to_utc(local_epoch):
    """Convert a 'local epoch' (UTC epoch + offset) back to UTC.

    Ambiguous only during the 1-hour DST switch at 03:00-04:00 local, which
    none of the scheduled times fall in.
    """
    return local_epoch - utc_offset(local_epoch - 2 * 3600)


def _at(day_start, hm, extra=0):
    return _local_to_utc(day_start + hm[0] * 3600 + hm[1] * 60) + extra


def has_tomorrow(data_end, now):
    """True if data reaches the end of tomorrow (Finnish local day)."""
    return data_end >= _local_to_utc(_local_day_start(now) + 2 * 86400)


def plan_next_fetch(
    now,
    data_end,
    publish=(14, 5),
    fast_until=(15, 30),
    give_up=(22, 0),
    retry_fast=15 * 60,
    retry_slow=45 * 60,
    jitter=0,
):
    """UTC time of the next fetch after a successful one.

    Args:
        now: current UTC epoch
        data_end: end of the last price slot we have (UTC epoch)
        publish/fast_until/give_up: (hour, minute) in Finnish local time
        jitter: per-device seconds added to the daily publish time
    """
    if data_end <= now:
        return now + retry_fast  # no current price at all: keep trying
    # Never sleep past the end of the data we have
    return min(
        data_end,
        _plan(
            now, data_end, publish, fast_until, give_up, retry_fast, retry_slow, jitter
        ),
    )


def _plan(now, data_end, publish, fast_until, give_up, retry_fast, retry_slow, jitter):
    today = _local_day_start(now)
    if has_tomorrow(data_end, now):
        return _at(today + 86400, publish, jitter)  # done until tomorrow

    publish_today = _at(today, publish, jitter)
    if now < publish_today:
        return publish_today
    if now < _at(today, fast_until):
        return now + retry_fast
    if now + retry_slow <= _at(today, give_up):
        return now + retry_slow
    # Gave up for today; current data lasts until ~01:00, retry when it ends
    return data_end
