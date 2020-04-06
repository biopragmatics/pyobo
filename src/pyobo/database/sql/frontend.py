# -*- coding: utf-8 -*-

"""Web interface for PyOBO database."""

from flask import Flask
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from .backend import Reference, Resource, Term, session

__all__ = [
    'app',
    'admin',
]

app = Flask(__name__)
admin = Admin(app, template_mode='bootstrap3', url='/')


class View(ModelView):
    """Base view."""

    # can_create = False
    # can_edit = False
    # can_delete = False


admin.add_view(View(Resource, session))
admin.add_view(View(Reference, session))


class TermView(View):
    """A view for Terms."""

    column_hide_backrefs = False
    column_list = ('reference', 'synonyms', 'xrefs')
    # column_searchable_list = ['reference', 'synonyms']


admin.add_view(TermView(Term, session))

if __name__ == '__main__':
    app.run()
