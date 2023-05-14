from flask import Flask, render_template, redirect, url_for

app = Flask(__name__)

@app.route("/")
def hello_world():
    # return "<p>Hello, World! aqil</p>"
    return render_template("index.html")
    

