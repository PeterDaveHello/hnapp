# -*- coding: utf-8 -*-
"""
Compatibility Atom feed generator modeled after werkzeug.contrib.atom (Py2-safe).
"""

from __future__ import unicode_literals

try:
	import html  # py3
	_escape_html = html.escape
except ImportError:
	# py2 fallback
	import cgi
	_escape_html = cgi.escape
import uuid
from datetime import datetime
try:
	from datetime import timezone
	UTC = timezone.utc
except ImportError:
	# Python 2 fallback
	class _UTC(object):
		def __repr__(self):
			return 'UTC'
	UTC = None

from flask import Response

XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"


def _escape(value):
	if value is None:
		return ''
	if isinstance(value, bytes):
		value = value.decode('utf-8', 'ignore')
	escaped = _escape_html(value, quote=False)
	return escaped.replace('"', '&quot;')


def _make_text_block(name, content, content_type=None):
	if content_type == 'xhtml':
		return '<{0} type="xhtml"><div xmlns="{1}">{2}</div></{0}>\n'.format(
			name, XHTML_NAMESPACE, content
		)
	if not content_type:
		return '<{0}>{1}</{0}>\n'.format(name, _escape(content))
	return '<{0} type="{1}">{2}</{0}>\n'.format(name, content_type, _escape(content))


def _format_iso8601(value):
	if UTC is not None and value.tzinfo is None:
		value = value.replace(tzinfo=UTC)
	value = value.replace(microsecond=0)
	offset = value.utcoffset() if hasattr(value, 'utcoffset') else None
	if offset is None or (hasattr(offset, 'total_seconds') and offset.total_seconds() == 0):
		return value.replace(tzinfo=None).isoformat() + 'Z'
	return value.isoformat()


class FeedEntry(object):
	def __init__(self, title=None, content=None, feed_url=None, **kwargs):
		self.title = title
		self.title_type = kwargs.get('title_type', 'text')
		self.content = content
		self.content_type = kwargs.get('content_type', 'html')
		self.url = kwargs.get('url')
		self.id = kwargs.get('id', self.url)
		self.updated = kwargs.get('updated')
		self.summary = kwargs.get('summary')
		self.summary_type = kwargs.get('summary_type', 'html')
		self.author = kwargs.get('author', ())
		self.published = kwargs.get('published')
		self.rights = kwargs.get('rights')
		self.links = kwargs.get('links', [])
		self.categories = kwargs.get('categories', [])
		self.xml_base = kwargs.get('xml_base', feed_url)

		if self.title is None or self.id is None:
			raise ValueError('FeedEntry requires title and id')

		if self.updated is None:
			self.updated = datetime.utcnow()

		if not hasattr(self.author, '__iter__') or isinstance(self.author, (str, dict)):
			self.author = [self.author]
		self.author = [
			author if isinstance(author, dict) else {'name': author}
			for author in self.author
		]

	def generate(self):
		base = ''
		if self.xml_base:
			base = ' xml:base="{0}"'.format(_escape(self.xml_base))
		yield '<entry{0}>\n'.format(base)
		yield '  ' + _make_text_block('title', self.title, self.title_type)
		yield '  <id>{0}</id>\n'.format(_escape(self.id))
		yield '  <updated>{0}</updated>\n'.format(_format_iso8601(self.updated))
		if self.published:
			yield '  <published>{0}</published>\n'.format(_format_iso8601(self.published))
		if self.url:
			yield '  <link href="{0}" />\n'.format(_escape(self.url))
		for author in self.author:
			yield '  <author>\n'
			yield '    <name>{0}</name>\n'.format(_escape(author.get('name', '')))
			if 'uri' in author:
				yield '    <uri>{0}</uri>\n'.format(_escape(author['uri']))
			if 'email' in author:
				yield '    <email>{0}</email>\n'.format(_escape(author['email']))
			yield '  </author>\n'
		for link in self.links:
			yield '  <link {0}/>\n'.format(''.join(
				'{0}="{1}" '.format(k, _escape(link[k])) for k in link
			))
		for category in self.categories:
			yield '  <category {0}/>\n'.format(''.join(
				'{0}="{1}" '.format(k, _escape(category[k])) for k in category
			))
		if self.summary:
			yield '  ' + _make_text_block('summary', self.summary, self.summary_type)
		if self.content:
			yield '  ' + _make_text_block('content', self.content, self.content_type)
		yield '</entry>\n'


class AtomFeed(object):
	default_generator = ('Werkzeug', None, None)

	def __init__(self, title=None, entries=None, **kwargs):
		self.title = title
		self.title_type = kwargs.get('title_type', 'text')
		self.url = kwargs.get('url')
		self.feed_url = kwargs.get('feed_url', self.url)
		self.id = kwargs.get('id', self.feed_url)
		self.updated = kwargs.get('updated')
		self.author = kwargs.get('author', ())
		self.icon = kwargs.get('icon')
		self.logo = kwargs.get('logo')
		self.rights = kwargs.get('rights')
		self.rights_type = kwargs.get('rights_type')
		self.subtitle = kwargs.get('subtitle')
		self.subtitle_type = kwargs.get('subtitle_type', 'text')
		self.generator = kwargs.get('generator', self.default_generator)
		self.links = list(kwargs.get('links', []))
		self.entries = list(entries) if entries else []

		if not hasattr(self.author, '__iter__') or isinstance(self.author, (str, dict)):
			self.author = [self.author]
		self.author = [
			author if isinstance(author, dict) else {'name': author}
			for author in self.author
		]

		if not self.id:
			self.id = 'urn:uuid:{0}'.format(uuid.uuid4())

		if not self.title:
			raise ValueError('title is required')
		if not self.id:
			raise ValueError('id is required')
		for author in self.author:
			if 'name' not in author:
				raise TypeError('author must contain at least a name')

	def add(self, *args, **kwargs):
		if len(args) == 1 and not kwargs and isinstance(args[0], FeedEntry):
			entry = args[0]
		else:
			kwargs['feed_url'] = self.feed_url
			if 'updated' not in kwargs or kwargs.get('updated') is None:
				kwargs['updated'] = datetime.utcnow()
			entry = FeedEntry(*args, **kwargs)
		self.entries.append(entry)

	def generate(self):
		if not self.author:
			if any(not entry.author for entry in self.entries):
				self.author = ({'name': 'Unknown author'},)

		if not self.updated:
			dates = sorted(entry.updated for entry in self.entries if entry.updated)
			self.updated = dates[-1] if dates else datetime.utcnow()

		yield '<?xml version="1.0" encoding="utf-8"?>\n'
		yield '<feed xmlns="http://www.w3.org/2005/Atom">\n'
		yield '  ' + _make_text_block('title', self.title, self.title_type)
		yield '  <id>{0}</id>\n'.format(_escape(self.id))
		yield '  <updated>{0}</updated>\n'.format(_format_iso8601(self.updated))
		if self.url:
			yield '  <link href="{0}" />\n'.format(_escape(self.url))
		if self.feed_url:
			yield '  <link href="{0}" rel="self" />\n'.format(_escape(self.feed_url))
		for link in self.links:
			yield '  <link {0}/>\n'.format(''.join(
				'{0}="{1}" '.format(k, _escape(link[k])) for k in link
			))
		for author in self.author:
			yield '  <author>\n'
			yield '    <name>{0}</name>\n'.format(_escape(author['name']))
			if 'uri' in author:
				yield '    <uri>{0}</uri>\n'.format(_escape(author['uri']))
			if 'email' in author:
				yield '    <email>{0}</email>\n'.format(_escape(author['email']))
			yield '  </author>\n'
		if self.subtitle:
			yield '  ' + _make_text_block('subtitle', self.subtitle, self.subtitle_type)
		if self.icon:
			yield '  <icon>{0}</icon>\n'.format(_escape(self.icon))
		if self.logo:
			yield '  <logo>{0}</logo>\n'.format(_escape(self.logo))
		if self.rights:
			yield '  ' + _make_text_block('rights', self.rights, self.rights_type)
		gen_name, gen_url, gen_version = self.generator
		if gen_name or gen_url or gen_version:
			tmp = ['  <generator']
			if gen_url:
				tmp.append(' uri="{0}"'.format(_escape(gen_url)))
			if gen_version:
				tmp.append(' version="{0}"'.format(_escape(gen_version)))
			tmp.append('>{0}</generator>\n'.format(_escape(gen_name or '')))
			yield ''.join(tmp)
		for entry in self.entries:
			for line in entry.generate():
				yield '  ' + line
		yield '</feed>\n'

	def to_string(self):
		return ''.join(self.generate())

	def get_response(self):
		return Response(self.to_string(), mimetype='application/atom+xml')

	__call__ = get_response
