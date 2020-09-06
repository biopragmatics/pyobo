# -*- coding: utf-8 -*-

"""Web interface for PyOBO database."""

from flask import Flask
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from .models import Reference, Resource, Synonym, session

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


class ResourceView(View):
    """A view for resources."""

    column_searchable_list = ['prefix', 'name']


admin.add_view(ResourceView(Resource, session))


class ReferenceView(View):
    """A view for references."""

    column_searchable_list = ['identifier', 'name']


admin.add_view(ReferenceView(Reference, session))
admin.add_view(View(Synonym, session))

if __name__ == '__main__':
    app.run()
