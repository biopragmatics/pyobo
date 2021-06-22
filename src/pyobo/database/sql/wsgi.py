# -*- coding: utf-8 -*-

"""Web interface for PyOBO database."""

from flask import Flask
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from .models import Alt, Reference, Resource, Synonym, Xref, session

__all__ = [
    "app",
    "admin",
]

app = Flask(__name__)
admin = Admin(app, template_mode="bootstrap3", url="/")


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


class AltView(View):
    """A view for references."""

    column_searchable_list = ["identifier", "alt"]


admin.add_view(ResourceView(Resource, session))

admin.add_view(ReferenceView(Reference, session))
admin.add_view(AltView(Alt, session))
admin.add_view(View(Synonym, session))
admin.add_view(View(Xref, session))

if __name__ == "__main__":
    app.run()
