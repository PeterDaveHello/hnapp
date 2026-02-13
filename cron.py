# -*- coding: utf-8 -*-

import sys
from datetime import datetime

import click
import sqlalchemy
from flask.cli import with_appcontext

from hnapp import app, db
from models.item import Item


def _create_scraper():
	from scraper import Scraper
	scraper = Scraper()
	scraper.connect()
	return scraper


@click.group()
def cli() -> None:
	"""Management commands for hnapp cron workflows."""


@cli.command()
@with_appcontext
def test() -> None:
	"""Verify scraper connectivity."""
	_create_scraper()
	click.echo('Scraper connection established')


@cli.command('fix_ask_items')
@with_appcontext
def fix_ask_items() -> None:
	"""Fix ask HN items mistakenly stored as link posts."""
	scraper = _create_scraper()
	statement = (
		sqlalchemy.select(Item.id)
		.where(Item.subkind == 'ask')
		.order_by(sqlalchemy.desc(Item.id))
	)
	item_ids = db.session.execute(statement).scalars().all()

	def save(item_data):
		scraper.save_item(item_data)
		click.echo(f"fixed {item_data['id']}")

	scraper.fetch_items(item_ids, callback=save)


@cli.command('init')
@with_appcontext
def init() -> None:
	"""Fetch and persist the newest items once."""
	scraper = _create_scraper()
	scraper.save_newest_items()


@cli.command('update')
@click.argument('from_id')
@click.argument('to_id')
@click.argument('backsort')
@with_appcontext
def update(from_id: str, to_id: str, backsort: str) -> None:
	"""Update items between given Hacker News IDs."""
	try:
		start = int(from_id)
		end = int(to_id)
	except ValueError as exc:
		raise click.BadParameter('from_id and to_id must be integers') from exc
	if start <= 0 or end <= 0:
		raise click.BadParameter('from_id and to_id must be positive integers')
	if backsort not in ('0', '1'):
		raise click.BadParameter('backsort must be 0 or 1')

	scraper = _create_scraper()
	item_ids = range(start, end)
	if backsort == '1':
		item_ids = reversed(range(start, end))

	scraper.fetch_items(item_ids, callback=lambda item_data: scraper.save_item(item_data))


@cli.command('every_1_min')
@with_appcontext
def every_1_min() -> None:
	"""Run scheduled scraping tasks based on the current minute."""
	minute = datetime.utcnow().minute
	scraper = _create_scraper()

	if minute % 2 == 0:
		scraper.save_newest_existing_stories(count=30, min_delay=90)

	if minute % 10 == 0:
		scraper.save_newest_existing_stories(start_from=30, count=60, min_delay=5*60)
		scraper.save_top_stories(front_page=False, start_from=30, count=60, min_delay=5*60)

	if minute % 5 == 0:
		scraper.save_newest_items()
		scraper.save_top_stories(front_page=True, count=30, min_delay=3*60)


cli.add_command(fix_ask_items, 'fix-ask-items')
cli.add_command(every_1_min, 'every-1-min')
app.cli.add_command(cli, 'cron')


def main(argv=None):
	"""Dispatch commands both via Flask CLI and direct execution."""
	args = list(argv or [])
	with app.app_context():
		try:
			cli.main(args=args, prog_name='cron.py', standalone_mode=True)
		except SystemExit as exc:
			return exc.code
		return 0


if __name__ == '__main__':
	result = main(sys.argv[1:])
	if isinstance(result, int):
		sys.exit(result)
	elif result is None:
		sys.exit(0)
	else:
		sys.exit(result)
