# -*- coding: utf-8 -*-

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from extensions import db


class LostItem(db.Model):
	
	__tablename__ = 'lost_item'
	
	id = Column(Integer, primary_key=True)
	reason = Column(String)
	response = Column(Text, nullable=True, default=None)
	traceback = Column(Text, nullable=True, default=None)
	date_found = Column(DateTime, default=datetime.utcnow)
	

