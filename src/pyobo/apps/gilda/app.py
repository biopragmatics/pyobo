# -*- coding: utf-8 -*-

"""PyOBO's Gilda Service."""

from typing import Iterable, Union

import flask
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields import StringField, SubmitField
from wtforms.validators import DataRequired

from pyobo.gilda_utils import get_grounder


class Form(FlaskForm):
    """Form for submitting a query."""

    text = StringField("Text", validators=[DataRequired()])
    submit = SubmitField()

    def make_response(self):
        """Make a response with the text."""
        return flask.redirect(flask.url_for("ground", text=self.text.data))


def get_app(prefix: Union[str, Iterable[str]]):
    """Make an app for grounding the text."""
    grounder = get_grounder(prefix)

    app = flask.Flask(__name__)
    app.config["WTF_CSRF_ENABLED"] = False
    Bootstrap(app)

    @app.route("/", methods=["GET", "POST"])
    def home():
        """Ground the given text."""
        form = Form()
        if form.validate_on_submit():
            return form.make_response()
        return flask.render_template("home.html", form=form)

    @app.route("/ground/<text>")
    def ground(text: str):
        """Ground the given text."""
        return flask.jsonify([scored_match.to_json() for scored_match in grounder.ground(text)])

    return app
