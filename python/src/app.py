from flask import Flask, render_template

app = Flask(__name__)


@app.route("/hello")
def hello():
    return "Hello World!"


@application.route("/")
def root():
    return render_template("index.html")