# -*- coding: utf-8 -*-

"""PyOBO's Gilda Service."""

from typing import Iterable, Optional

import click
import flask
import gilda.term
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from gilda.generate_terms import filter_out_duplicates
from gilda.grounder import Grounder
from gilda.process import normalize
from more_click import host_option, port_option, run_app, with_gunicorn_option, workers_option
from tqdm import tqdm
from wtforms.fields import StringField, SubmitField
from wtforms.validators import DataRequired

from pyobo import get_id_name_mapping, get_id_synonyms_mapping
from pyobo.cli_utils import verbose_option
from pyobo.io_utils import multidict


class Form(FlaskForm):
    """Form for submitting a query."""

    text = StringField('Text', validators=[DataRequired()])
    submit = SubmitField()

    def make_response(self):
        """Make a response with the text."""
        return flask.redirect(flask.url_for('ground', text=self.text.data))


def get_app(prefix: str, url: Optional[str] = None):
    """Make an app for grounding the text."""
    grounder = get_grounder(prefix, url=url)

    app = flask.Flask(__name__)
    app.config['WTF_CSRF_ENABLED'] = False
    Bootstrap(app)

    @app.route('/', methods=['GET', 'POST'])
    def home():
        """Ground the given text."""
        form = Form()
        if form.validate_on_submit():
            return form.make_response()
        return flask.render_template('home.html', form=form)

    @app.route('/ground/<text>')
    def ground(text: str):
        """Ground the given text."""
        return flask.jsonify([
            scored_match.to_json()
            for scored_match in grounder.ground(text)
        ])

    return app


def get_grounder(prefix, url: Optional[str] = None) -> Grounder:
    """Get a Gilda grounder for the given namespace."""
    terms = list(get_gilda_terms(prefix, url=url))
    terms = filter_out_duplicates(terms)
    terms = multidict((term.norm_text, term) for term in terms)
    return Grounder(terms)


def get_gilda_terms(prefix: str, url: Optional[str] = None) -> Iterable[gilda.term.Term]:
    """Get gilda terms for the given namespace."""
    id_to_name = get_id_name_mapping(prefix, url=url)
    for identifier, name in tqdm(id_to_name.items(), desc='mapping names'):
        yield gilda.term.Term(
            norm_text=normalize(name),
            text=name,
            db=prefix,
            id=identifier,
            entry_name=name,
            status='name',
            source=prefix,
        )

    id_to_synonyms = get_id_synonyms_mapping(prefix, url=url)
    for identifier, synonyms in tqdm(id_to_synonyms.items(), desc='mapping synonyms'):
        name = id_to_name[identifier]
        for synonym in synonyms:
            yield gilda.term.Term(
                norm_text=normalize(synonym),
                text=synonym,
                db=prefix,
                id=identifier,
                entry_name=name,
                status='synonym',
                source=prefix,
            )


@click.command()
@click.argument('prefix')
@verbose_option
@host_option
@workers_option
@port_option
@with_gunicorn_option
def main(prefix: str, host: str, port: str, with_gunicorn: bool, workers: int):
    """Run the Gilda service for this database."""
    app = get_app(prefix)
    run_app(app, host=host, port=port, with_gunicorn=with_gunicorn, workers=workers)


if __name__ == '__main__':
    main()
