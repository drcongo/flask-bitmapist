# -*- coding: utf-8 -*-
"""
    flask_bitmapist.views
    ~~~~~~~~~~~~~~~~~~~~~
    This module provides the views for Flask-Bitmapist's web interface.

    :copyright: (c) 2016 by Cuttlesoft, LLC.
    :license: MIT, see LICENSE for more details.
"""

import json, os

from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from bitmapist import get_event_names, DayEvents, WeekEvents, MonthEvents, YearEvents  # BitOpAnd, BitOpOr

from .utils import get_cohort, get_event_data



root = os.path.abspath(os.path.dirname(__file__))

bitmapist_bp = Blueprint('bitmapist', 'flask_bitmapist',
                         template_folder=os.path.join(root, 'templates'),
                         static_folder=os.path.join(root, 'static'),
                         url_prefix='/bitmapist')


@bitmapist_bp.context_processor
def inject_version():
    from . import __version__
    return dict(version=__version__)


@bitmapist_bp.route('/')
def index():
    now = datetime.utcnow()

    day_events = len(list(DayEvents('user:logged_in', now.year, now.month, now.day)))
    week_events = len(list(WeekEvents('user:logged_in', now.year, now.isocalendar()[1])))
    month_events = len(list(MonthEvents('user:logged_in', now.year, now.month)))
    year_events = len(list(YearEvents('user:logged_in', now.year)))
    # return render_template('bitmapist/data.html', ...
    return render_template('bitmapist/index.html', events=get_event_names(), day_events=day_events, week_events=week_events, month_events=month_events, year_events=year_events)


@bitmapist_bp.route('/cohort', methods=['GET', 'POST'])
def cohort():
    if request.method == 'GET':
        now = datetime.utcnow()
        event_names = get_event_names()
        # TEMPORARY? for display niceness
        event_options = []
        for event_name in event_names:
            if 'user:' in event_name:
                formatted = event_name.replace('user:', '').replace('_', ' ')
                # such hackery
                formatted = ('were ' + formatted).replace('were logged', 'logged')
                # /hackery
                event_options.append([formatted, event_name])
        event_options = sorted(event_options)
        # user_events = [e for e in event_names if 'user' in e]
        # event_options = [u.replace('user_', '') for u in user_events]

        # TEMPORARY: for listing of totals per event
        events = {}
        for event_name in event_names:
            # TODO: + hourly
            day = len(DayEvents(event_name, now.year, now.month, now.day))
            week = len(WeekEvents(event_name, now.year, now.isocalendar()[1]))
            month = len(MonthEvents(event_name, now.year, now.month))
            year = len(YearEvents(event_name, now.year))
            event = (year, month, week, day)
            events[event_name] = event
        # END TEMP

        time_groups = ['day', 'week', 'month', 'year']
        return render_template('bitmapist/cohort.html', event_options=event_options, time_groups=time_groups, events=events)

    elif request.method == 'POST':
        data = json.loads(request.data)

        # Cohort events
        primary_event = data.get('primary_event')
        secondary_event = data.get('secondary_event')
        additional_events = data.get('additional_events', [])
        # Cohort settings
        time_group = data.get('time_group', 'days')
        as_percent = data.get('as_percent', True)
        num_rows = int(data.get('num_rows', 20))
        num_cols = int(data.get('num_cols', 10))

        if time_group == 'years':
            # Three shall be the number thou shalt count, and the number of the
            # counting shall be three. Four shalt thou not count, neither count thou
            # two, excepting that thou then proceed to three. Five is right out.
            num_rows = 3

        # Columns > rows would extend into future and thus would just be empty
        num_cols = num_rows if num_cols > num_rows else num_cols

        # Get cohort data and associated dates
        cohort, dates, row_totals = get_cohort(primary_event, secondary_event,
                                   additional_events=additional_events,
                                   time_group=time_group,
                                   num_rows=num_rows,
                                   num_cols=num_cols)

        # Format dates for table
        if time_group == 'years':
            dt_format = '%Y'
        elif time_group == 'months':
            dt_format = '%b %Y'
        elif time_group == 'weeks':
            dt_format = 'Week %U - %d %b %Y'
        else:
            dt_format = '%d %b %Y'

        date_strings = [dt.strftime(dt_format) for dt in dates]

        # Get column totals, averages, and percent values
        col_totals = [0] * num_cols
        col_counts = [0] * num_cols
        for i, row in enumerate(cohort):
            for j, val in enumerate(row):
                if val is not None:
                    col_totals[j] += val
                    col_counts[j] += 1  # exclude non-zero empties from averages

            if as_percent and row_totals[i]:
                cohort[i] = [float(r) / row_totals[i] if r is not None else r for r in row]

        # Get averages for table
        overall_total = sum(row_totals)
        averages = []
        for idx, col_total in enumerate(col_totals):
            if as_percent:
                average = float(col_total) / overall_total
            else:
                col_count = col_counts[idx]
                average = float(col_total) / col_count if col_count else 0
            averages.append(average)

        # TODO: remove unnecessary keys from json return
        cohort_data = {
            'cohort': cohort,
            'dates': date_strings,
            'total': overall_total,
            'totals': row_totals,
            'averages': averages,
            'time_group': time_group,
            'as_percent': as_percent,
            'num_rows': num_rows,
            'num_cols': num_cols
        }

        if request.args.get('json'):
            return json.dumps(cohort_data, indent=4)
        else:
            return render_template('bitmapist/_heatmap.html', **cohort_data)
