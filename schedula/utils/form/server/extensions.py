# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the database.
"""
from flask_sqlalchemy import SQLAlchemy


class Database(SQLAlchemy):
    def __init__(self):
        super().__init__()
        self.seeds = []

    def add_seed(self, seed):
        self.seeds.append(seed)

    def create_all(self):
        super().create_all()
        for seed in self.seeds:
            seed()


db = Database()
