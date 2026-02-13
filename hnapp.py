# -*- coding: utf-8 -*-

import time
import json

import flask
import sqlalchemy
from flask import Response

from atom_feed import AtomFeed
from extensions import db

# Initialize application and database session
app = flask.Flask(
	__name__,
	template_folder='templates',
	static_folder='static',
	static_url_path=''
)
app.config.from_pyfile('config.py')
app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
db.init_app(app)

# Import hnapp components. These require app & db to be set
# <<< TODO is there a better way? Doesn't feel right...
from models.item import Item
from models.lost_item import LostItem
from models.status import Status
from search import Search
from utils import time_since, num_digits, query_url
import cron  # Register Flask CLI commands





@app.route('/rss', methods=['GET'])
@app.route('/json', methods=['GET'])
@app.route('/bare', methods=['GET'])
@app.route('/', methods=['GET'])
def route_search():

	# Get query
	text_query = flask.request.args.get('q', None)
	page_num_raw = flask.request.args.get('page', '1')
	show_syntax_raw = flask.request.args.get('show_syntax', '0')

	# Fail if bad parameters provided
	try:
		page_num = max(int(page_num_raw), 1)
		show_syntax = bool(int(show_syntax_raw))
	except (TypeError, ValueError):
		flask.abort(400)

	items = None
	has_more_items = False
	
	# Search page
	if text_query is not None:
		per_page = app.config['ITEMS_PER_PAGE']
		offset = (page_num - 1) * per_page
		results = Search.query(
			text_query,
			page_num,
			offset=offset,
			count=per_page + 1
		)
		if len(results) > per_page:
			items = results[:-1]
			has_more_items = True
		else:
			items = results
		query_title = text_query if text_query else 'HN Firehose'
		meta_og_title = u'hnapp search: "%s"' % query_title
		title = u'%s – hnapp' % query_title

	# Front page
	else:
		title = u'hnapp – Hacker News Search With RSS & JSON Feeds'
		meta_og_title = u'hnapp – Hacker News RSS'


	# Meta SEO tags
	meta_keywords = u'Hacker News,RSS,hnapp'
	meta_description = u'Get only the stories and comments you want. Follow users, keywords, jobs, mentions of your product, etc.'


	# Get format
	request_path = flask.request.path
	output_format = None
	html_template = 'search.html'
	if request_path != '/':
		if text_query is None:
			flask.abort(400)
		output_format = request_path.lstrip('/')
		if output_format == 'bare':
			html_template = 'parts/items.html'


	# Those users who created their filters on alpha version new.hnapp.com
	# don't expect comments, so we fix it for them
	if flask.request.args.get('legacy', '0') == '1':
		# Not a search – redirect to home page
		if text_query is None:
			return flask.redirect(query_url(None, output_format=None), code=302)
		else:
			return flask.redirect(query_url('type:story '+text_query, output_format=output_format), code=302)


	# Web page or bare HTML
	if output_format in (None, 'bare'):
		page_data = {
			'is_app': True,
			'title': title,
			'meta_og_title': meta_og_title,
			'meta_keywords': meta_keywords,
			'meta_description': meta_description,
			'show_syntax': show_syntax,
			'query': text_query,
			'items': items,
			'has_more_items': int(has_more_items),
			'page_expires_at': int(time.time()) + 60*5, # Cache pages for this many seconds
			'this_url': None,
			'prev_url': query_url(text_query, page_num=page_num-1) if text_query is not None else None,
			'next_url': query_url(text_query, page_num=page_num+1) if text_query is not None else None,
			'rss_url': query_url(text_query, output_format='rss') if text_query is not None else None,
			'json_url': query_url(text_query, output_format='json') if text_query is not None else None,
			'page_num': page_num,
			'ga_id': app.config['GA_ID'],
			'HOST_NAME': app.config['HOST_NAME']
		}
		raw_qs = flask.request.query_string
		this_url = flask.request.base_url
		if raw_qs:
			def _decode_non_ascii(qs_text):
				out = []
				data = bytearray(qs_text.encode('ascii', 'ignore'))
				i = 0
				while i < len(data):
					if data[i] == 37 and i + 2 < len(data):  # '%'
						try:
							b = int(data[i+1:i+3], 16)
						except ValueError:
							out.append('%')
							i += 1
							continue
						# ASCII percent-encoded stays encoded
						if b < 128:
							out.append('%%%02X' % b)
							i += 3
							continue
						bytes_seq = bytearray([b])
						i += 3
						while i < len(data) and data[i] == 37 and i + 2 < len(data):
							try:
								next_b = int(data[i+1:i+3], 16)
							except ValueError:
								break
							if next_b < 0x80 or next_b > 0xBF:
								break
							bytes_seq.append(next_b)
							i += 3
						try:
							decoded = bytes(bytes_seq).decode('utf-8')
						except UnicodeDecodeError:
							out.append(''.join('%%%02X' % b for b in bytes_seq))
						else:
							out.append(decoded)
						continue
					out.append(chr(data[i]))
					i += 1
				return ''.join(out)

			this_url += '?' + _decode_non_ascii(raw_qs.decode('utf-8', 'ignore'))
		page_data['this_url'] = this_url
		return flask.render_template(html_template, **page_data)


	# RSS
	elif output_format == 'rss':
		feed = AtomFeed(
			title=title.encode('ascii', 'xmlcharrefreplace').decode('ascii'),
			title_type='html',
			feed_url=query_url(text_query, output_format='rss'),
			author='via hnapp',
			url=query_url(text_query),
			generator=('hnapp', app.config['HOST_NAME'], None)
		)
		for item in items or []:
			feed.add(**item.feed_entry())
		return feed.get_response()


	# JSON
	elif output_format == 'json':

		feed = {
			'has_more_items': has_more_items,
			'query': text_query,
			'items': [item.json_entry() for item in (items or [])],
		}
		body = json.dumps(feed, indent=2, sort_keys=True, separators=(', ', ': '))
		return Response(body, mimetype='application/json')


	# output_format defined but query is not
	# not supposed to happen, we checked for this above
	else:
		flask.abort(500)



@app.route('/status', methods=['GET'])
def route_status():

	statuses = db.session.execute(sqlalchemy.select(Status)).scalars().all()
	max_item_id = db.session.execute(sqlalchemy.text('SELECT MAX(id) FROM item')).scalar()
	min_item_id = db.session.execute(sqlalchemy.text('SELECT MIN(id) FROM item')).scalar()
	item_count = db.session.execute(sqlalchemy.text('SELECT COUNT(*) FROM item')).scalar()
	page_data = {
		'is_app': False,
		'title': u'hnapp – Status',
		'meta_og_title': u'hnapp – Status',
		'statuses': statuses,
		'max_item_id': max_item_id,
		'min_item_id': min_item_id,
		'item_count': item_count,
		'ga_id': app.config['GA_ID'],
		'HOST_NAME': app.config['HOST_NAME']
		}
	return flask.render_template('status.html', **page_data)



@app.errorhandler(400)
def error(e):
	return flask.render_template('error.html',
								 is_app=False,
								 error=u'400 – Bad Request',
								 ga_id=app.config['GA_ID']
								 ), 400



@app.errorhandler(404)
def error(e):
	return flask.render_template('error.html',
								 is_app=False,
								 error=u'404 – Page Not Found',
								 ga_id=app.config['GA_ID']
								 ), 404



@app.errorhandler(403)
def error(e):
	return flask.render_template('error.html',
								 is_app=False,
								 error=u'403 – Access Denied',
								 ga_id=app.config['GA_ID']
								 ), 403



@app.errorhandler(500)
def error(e):
	return flask.render_template('error.html',
								 is_app=False,
								 error=u'500 – Internal Server Error',
								 ga_id=app.config['GA_ID']
								 ), 500
