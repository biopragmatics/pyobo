# -*- coding: utf-8 -*-

"""Web interface for PyOBO database."""

from flask import Flask
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from .models import Alt, Definition, Reference, session


class View(ModelView):
    """Base view."""

    can_create = False
    can_edit = False
    can_delete = False


class ResourceView(View):
    """A view for resources."""

    column_searchable_list = ["prefix", "name"]


class ReferenceView(View):
    """A view for references."""

    column_searchable_list = ["identifier", "name"]


class DefinitionView(View):
    """A view for definitions."""

    column_searchable_list = ["identifier", "definition"]


class AltView(View):
    """A view for references."""

    column_searchable_list = ["identifier", "alt"]


def get_admin() -> Admin:
    """Get admin instance."""
    admin = Admin(template_mode="bootstrap3", url="/")
    # admin.add_view(ResourceView(Resource, session))
    admin.add_view(ReferenceView(Reference, session))
    admin.add_view(AltView(Alt, session))
    admin.add_view(DefinitionView(Definition, session))
    # admin.add_view(View(Synonym, session))
    # admin.add_view(View(Xref, session))
    return admin


def get_app() -> Flask:
    """Get flask app."""
    rv = Flask(__name__)
    admin = get_admin()
    admin.init_app(rv)
    return rv


app = get_app()

if __name__ == "__main__":
    app.run()
