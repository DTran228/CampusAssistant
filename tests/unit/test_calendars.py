from datetime import datetime, timezone
import pytest
from icalendar import Calendar
from campus_assistant.calendars import expand_calendar, upload_calendar, owned_calendar
from campus_assistant.errors import DomainError

START = "2026-10-26T00:00:00Z"
END = "2026-11-09T00:00:00Z"


def ics(body):
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + body + "\r\nEND:VCALENDAR\r\n").encode()


def vevent(lines):
    return "BEGIN:VEVENT\r\nUID:class\r\n" + lines + "\r\nEND:VEVENT"


def test_recurring_dst_exdate_moved_and_cancelled():
    body = vevent("DTSTART;TZID=America/New_York:20261026T090000\r\nDTEND;TZID=America/New_York:20261026T100000\r\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4\r\nEXDATE;TZID=America/New_York:20261028T090000")
    intervals = expand_calendar(ics(body), START, END, "America/New_York")
    assert [i["start"].hour for i in intervals] == [13, 14, 14]  # DST on Nov 1
    moved = vevent("RECURRENCE-ID;TZID=America/New_York:20261102T090000\r\nDTSTART;TZID=America/New_York:20261102T110000\r\nDTEND;TZID=America/New_York:20261102T120000")
    cancelled = vevent("RECURRENCE-ID;TZID=America/New_York:20261104T090000\r\nSTATUS:CANCELLED")
    intervals = expand_calendar(ics(body + "\r\n" + moved + "\r\n" + cancelled), START, END, "America/New_York")
    assert len(intervals) == 2 and intervals[1]["start"].hour == 16


def test_all_day_exclusive_end_and_transparency():
    body = vevent("DTSTART;VALUE=DATE:20261027\r\nDTEND;VALUE=DATE:20261029")
    intervals = expand_calendar(ics(body), START, END, "America/New_York")
    assert intervals[0]["start"].isoformat() == "2026-10-27T04:00:00+00:00"
    assert intervals[0]["end"].isoformat() == "2026-10-29T04:00:00+00:00"
    assert not expand_calendar(ics(body.replace("DTSTART", "TRANSP:TRANSPARENT\r\nDTSTART")), START, END, "America/New_York")


def test_floating_requires_timezone_and_unknown_tzid_rejected():
    body = vevent("DTSTART:20261027T090000\r\nDTEND:20261027T100000")
    with pytest.raises(DomainError, match="floating"):
        expand_calendar(ics(body), START, END)
    assert len(expand_calendar(ics(body), START, END, "America/New_York")) == 1
    with pytest.raises(DomainError):
        expand_calendar(ics(body.replace("DTSTART:", "DTSTART;TZID=Mars/Unknown:")), START, END, "America/New_York")


@pytest.mark.parametrize("extra", ["RRULE:FREQ=SECONDLY", "RDATE:20261028T090000Z", "RRULE:FREQ=DAILY;BYSECOND=0", "RECURRENCE-ID;RANGE=THISANDFUTURE:20261027T090000Z"])
def test_unsupported_never_silently_available(extra):
    body = vevent("DTSTART:20261027T090000Z\r\nDTEND:20261027T100000Z\r\n" + extra)
    with pytest.raises(DomainError) as error:
        expand_calendar(ics(body), START, END, "UTC")
    assert error.value.code == "calendar_unsupported"


def test_private_calendar_horizon_and_minimal_storage(db):
    one, two = db.create_profile(), db.create_profile()
    body = vevent("DTSTART:20261027T090000Z\r\nDTEND:20261027T100000Z\r\nSUMMARY:PRIVATE TITLE")
    ref = upload_calendar(db, one, ics(body), START, END, "UTC")["calendar_ref"]
    with db.connect() as conn:
        assert len(owned_calendar(conn, one, ref, START, END)) == 1
        with pytest.raises(DomainError):
            owned_calendar(conn, two, ref, START, END)
        with pytest.raises(DomainError, match="exceeds"):
            owned_calendar(conn, one, ref, START, "2026-11-10T00:00:00Z")
    assert b"PRIVATE TITLE" not in db.path.read_bytes()


def test_spring_dst_nonexistent_and_fall_ambiguous_explicit_error():
    body = vevent("DTSTART;TZID=America/New_York:20260308T023000\r\nDTEND;TZID=America/New_York:20260308T033000")
    with pytest.raises(DomainError, match="Nonexistent"):
        expand_calendar(ics(body), "2026-03-08T00:00:00Z", "2026-03-10T00:00:00Z", "America/New_York")
    body = vevent("DTSTART;TZID=America/New_York:20261101T013000\r\nDTEND;TZID=America/New_York:20261101T023000")
    with pytest.raises(DomainError, match="Ambiguous"):
        expand_calendar(ics(body), START, END, "America/New_York")
